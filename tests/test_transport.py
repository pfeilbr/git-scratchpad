"""--debug HTTP tracing, network-failure reporting and --timeout at the
transport seam."""
import socket
import urllib.error
import urllib.request

import pytest

import gsuite.transport as transport
from gsuite.cli import main
from gsuite.errors import CLIError

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


@pytest.fixture
def clean_timeout(monkeypatch):
    """No ambient $GSUITE_TIMEOUT, and main()'s write to TIMEOUT undone after."""
    monkeypatch.delenv("GSUITE_TIMEOUT", raising=False)
    monkeypatch.setattr(transport, "TIMEOUT", transport.DEFAULT_TIMEOUT)


DNS_FAILURE = socket.gaierror(-2, "Name or service not known")
DEAD_URL = "https://nonexistent.invalid/x"


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


# -- network failures are errors, not tracebacks ------------------------------


def test_url_error_becomes_a_cli_error_naming_host_and_reason(urlopen):
    urlopen(error=urllib.error.URLError(DNS_FAILURE))
    with pytest.raises(CLIError) as exc:
        transport.request("GET", DEAD_URL, headers=HEADERS)
    message = str(exc.value)
    assert "nonexistent.invalid" in message
    assert "Name or service not known" in message


def test_socket_timeout_says_so_and_points_at_the_flag(urlopen):
    urlopen(error=socket.timeout("timed out"))
    with pytest.raises(CLIError) as exc:
        transport.request("GET", URL, headers=HEADERS, timeout=5)
    message = str(exc.value)
    assert "timed out" in message.lower()
    assert "--timeout" in message
    assert "5" in message


def test_timeout_wrapped_in_a_url_error_still_reads_as_a_timeout(urlopen):
    # How a connect timeout actually surfaces: urllib re-raises it as URLError.
    urlopen(error=urllib.error.URLError(socket.timeout("timed out")))
    with pytest.raises(CLIError) as exc:
        transport.request("GET", URL, headers=HEADERS)
    assert "--timeout" in str(exc.value)


def test_http_error_is_still_returned_not_raised(urlopen):
    err_body = b'{"error": {"message": "boom"}}'
    failure = urllib.error.HTTPError(URL, 500, "Server Error",
                                     {"x-trace": "abc"}, None)
    failure.read = lambda: err_body
    urlopen(error=failure)
    status, resp_headers, body = transport.request("GET", URL, headers=HEADERS)
    assert (status, body) == (500, err_body)
    assert resp_headers["x-trace"] == "abc"


def test_debug_traces_the_failure_without_leaking_headers(urlopen, debug,
                                                          capsys):
    urlopen(error=urllib.error.URLError(
        ConnectionRefusedError(111, "Connection refused")))
    with pytest.raises(CLIError):
        transport.request("POST", URL, headers=HEADERS, data=SECRET_BODY)
    err = capsys.readouterr().err
    lines = err.splitlines()
    assert lines[0] == f"→ POST {URL}"
    assert lines[-1].startswith("← error:")
    assert "Connection refused" in lines[-1]
    assert "Authorization" not in err
    assert "super-secret-token" not in err
    assert "do-not-log-me" not in err


def test_cli_network_failure_exits_1(authed, run_cli, urlopen, clean_timeout):
    urlopen(error=urllib.error.URLError(DNS_FAILURE))
    run_cli("api", "call", "GET", DEAD_URL, expect=1)


def test_cli_network_failure_prints_an_error_line(authed, capsys, urlopen,
                                                  clean_timeout):
    urlopen(error=urllib.error.URLError(DNS_FAILURE))
    assert main(["api", "call", "GET", DEAD_URL]) == 1
    err = capsys.readouterr().err
    assert ("error: cannot reach nonexistent.invalid: "
            "[Errno -2] Name or service not known") in err
    assert "Traceback" not in err


# -- --timeout / $GSUITE_TIMEOUT ----------------------------------------------


def test_timeout_flag_reaches_the_transport(authed, fake_transport, run_cli,
                                            clean_timeout):
    fake_transport.add("GET", "labels", {"labels": []})
    run_cli("--timeout", "5", "gmail", "labels", "list")
    assert transport.TIMEOUT == 5.0


def test_timeout_env_var_is_the_fallback(authed, fake_transport, run_cli,
                                         clean_timeout, monkeypatch):
    monkeypatch.setenv("GSUITE_TIMEOUT", "7.5")
    fake_transport.add("GET", "labels", {"labels": []})
    run_cli("gmail", "labels", "list")
    assert transport.TIMEOUT == 7.5
    fake_transport.add("GET", "labels", {"labels": []})
    run_cli("--timeout", "5", "gmail", "labels", "list")
    assert transport.TIMEOUT == 5.0  # the explicit flag wins


@pytest.mark.parametrize("bad", ["abc", "0", "-5", "nan", "inf"])
def test_invalid_timeout_exits_1_naming_the_value(authed, capsys, urlopen,
                                                  clean_timeout, bad):
    urlopen(error=AssertionError("no request should be attempted"))
    assert main(["--timeout", bad, "gmail", "labels", "list"]) == 1
    err = capsys.readouterr().err
    assert bad in err
    assert "--timeout" in err
    assert "Traceback" not in err
