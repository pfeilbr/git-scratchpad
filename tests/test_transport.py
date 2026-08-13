"""--debug HTTP tracing at the transport seam."""
import urllib.error
import urllib.request

import pytest

import gsuite.transport as transport

URL = "https://example.googleapis.com/v1/things"
SECRET_BODY = b'{"topSecretPayload": "do-not-log-me"}'
HEADERS = {"Authorization": "Bearer super-secret-token"}


class FakeResponse:
    def __init__(self, status=200, body=SECRET_BODY):
        self.status = status
        self.headers = {"content-type": "application/json"}
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def urlopen(monkeypatch):
    """Stub urllib so request() runs for real without touching the network."""
    def _install(response=None, error=None):
        def fake(req, timeout=30):
            if error is not None:
                raise error
            return response or FakeResponse()
        monkeypatch.setattr(urllib.request, "urlopen", fake)
    return _install


@pytest.fixture
def debug(monkeypatch):
    """Turn tracing on, restored automatically after the test."""
    monkeypatch.setattr(transport, "DEBUG", True)


def test_debug_off_by_default_keeps_stderr_empty(urlopen, capsys):
    assert transport.DEBUG is False
    urlopen()
    transport.request("GET", URL, headers=HEADERS)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


def test_debug_traces_request_and_response(urlopen, debug, capsys):
    urlopen()
    transport.request("GET", URL, headers=HEADERS)
    lines = capsys.readouterr().err.splitlines()
    assert lines[0] == f"→ GET {URL}"
    assert lines[1] == f"← 200 {len(SECRET_BODY)} bytes"


def test_debug_never_leaks_credentials_or_body(urlopen, debug, capsys):
    urlopen()
    transport.request("POST", URL, headers=HEADERS, data=b'{"in": "put"}')
    err = capsys.readouterr().err
    assert "Authorization" not in err
    assert "super-secret-token" not in err
    assert "do-not-log-me" not in err
    assert "put" not in err


def test_debug_traces_http_error_responses(urlopen, debug, capsys):
    err_body = b'{"error": {"message": "nope"}}'
    failure = urllib.error.HTTPError(URL, 404, "Not Found", {}, None)
    failure.read = lambda: err_body  # body without a real socket
    urlopen(error=failure)
    status, _, body = transport.request("GET", URL, headers=HEADERS)
    assert status == 404
    lines = capsys.readouterr().err.splitlines()
    assert lines[-1] == f"← 404 {len(err_body)} bytes"


def test_cli_debug_flag_switches_transport_debug(authed, fake_transport,
                                                 run_cli, monkeypatch):
    monkeypatch.setattr(transport, "DEBUG", False)
    seen = []
    original = fake_transport.__call__

    def watching(method, url, headers=None, data=None, timeout=30):
        seen.append(transport.DEBUG)
        return original(method, url, headers=headers, data=data,
                        timeout=timeout)

    monkeypatch.setattr(transport, "request", watching)
    fake_transport.add("GET", "labels", {"labels": []})
    run_cli("--debug", "gmail", "labels", "list")
    assert seen == [True]


def test_cli_without_debug_leaves_transport_quiet(authed, fake_transport,
                                                  run_cli, monkeypatch):
    monkeypatch.setattr(transport, "DEBUG", False)
    seen = []
    original = fake_transport.__call__

    def watching(method, url, headers=None, data=None, timeout=30):
        seen.append(transport.DEBUG)
        return original(method, url, headers=headers, data=data,
                        timeout=timeout)

    monkeypatch.setattr(transport, "request", watching)
    fake_transport.add("GET", "labels", {"labels": []})
    run_cli("gmail", "labels", "list")
    assert seen == [False]
