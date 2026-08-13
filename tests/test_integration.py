"""Real sockets, real subprocess, no fakes.

Everywhere else the transport is monkeypatched, so nothing proved that the
assembled stack — parser → Client → oauth → transport → HTTP → output —
actually works. These tests run the CLI as a subprocess against a local
HTTP server, which is a genuine round-trip while staying entirely offline.
"""
import http.server
import json
import os
import subprocess
import sys
import threading

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.BaseHTTPRequestHandler):
    """Answers like a Google API: JSON bodies, Google-shaped errors."""

    def _respond(self):
        path = self.path.split("?")[0]
        if path == "/notfound":
            code, payload = 404, {"error": {"message": "File not found.",
                                            "code": 404}}
        elif path == "/flaky":
            # 429 once per server instance, then success: proves the retry
            # path works over a real socket, not just against a fake.
            first = not self.server.seen_flaky
            self.server.seen_flaky = True
            code = 429 if first else 200
            payload = ({"error": {"message": "rate limited"}} if first
                       else {"ok": True, "attempts": 2})
        else:
            payload = {"path": path,
                       "auth": self.headers.get("Authorization"),
                       "method": self.command}
        body = json.dumps(payload).encode()
        self.send_response(code if path in ("/notfound", "/flaky") else 200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_DELETE = _respond

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    httpd.seen_flaky = False
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture
def cli(tmp_path):
    """Run the CLI as a real subprocess with sandboxed credentials."""
    def _run(*argv, token="test-token", config=None):
        env = {**os.environ, "PYTHONPATH": ROOT,
               "HOME": str(tmp_path),
               "GSUITE_CONFIG_DIR": str(config or tmp_path / "config"),
               "GOOGLE_APPLICATION_CREDENTIALS": str(tmp_path / "no-adc.json"),
               # Never let an ambient proxy intercept the loopback server.
               "NO_PROXY": "127.0.0.1,localhost",
               "no_proxy": "127.0.0.1,localhost"}
        if token:
            env["GSUITE_ACCESS_TOKEN"] = token
        else:
            env.pop("GSUITE_ACCESS_TOKEN", None)
        return subprocess.run([sys.executable, "-m", "gsuite.cli", *argv],
                              capture_output=True, text=True, env=env,
                              cwd=ROOT, timeout=60)
    return _run


def test_end_to_end_get_sends_bearer_and_prints_json(cli, server):
    result = cli("api", "call", "GET", f"{server}/about")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["auth"] == "Bearer test-token"   # env token really used
    assert payload["method"] == "GET"


def test_end_to_end_http_error_becomes_a_clean_message(cli, server):
    result = cli("api", "call", "GET", f"{server}/notfound")
    assert result.returncode == 1
    assert "HTTP 404" in result.stderr and "File not found." in result.stderr
    assert "Traceback" not in result.stderr


def test_end_to_end_retry_recovers_from_a_real_429(cli, server):
    result = cli("api", "call", "GET", f"{server}/flaky")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["attempts"] == 2


def test_debug_traces_a_real_request_to_stderr(cli, server):
    result = cli("--debug", "api", "call", "GET", f"{server}/about")
    assert result.returncode == 0
    assert f"→ GET {server}/about" in result.stderr
    assert "← 200" in result.stderr
    assert "test-token" not in result.stderr   # never trace the bearer token


def test_readonly_refuses_a_real_mutation_before_it_leaves(cli, server):
    result = cli("--readonly", "api", "call", "POST", f"{server}/about",
                 "--body", "{}")
    assert result.returncode == 1
    assert "readonly mode: refusing POST" in result.stderr


def test_readonly_refusal_does_not_depend_on_configured_credentials(cli, server):
    """The guard is the point: it must fire even with no credentials at all."""
    result = cli("--readonly", "api", "call", "DELETE", f"{server}/about",
                 token=None)
    assert result.returncode == 1
    assert "readonly mode: refusing DELETE" in result.stderr, result.stderr
