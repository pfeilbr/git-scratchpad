"""Minimal HTTP transport on urllib — a single seam for tests to fake.

Everything network-touching in gsuite funnels through request(); tests
monkeypatch this module's `request` attribute with a FakeTransport.

`--debug` sets DEBUG here, which traces one line per request and one per
response to stderr. The trace is deliberately metadata-only: no request or
response bodies, no headers (the Authorization bearer token lives there).

`--timeout` / $GSUITE_TIMEOUT set TIMEOUT here, which request() uses for
any caller that does not pass a timeout of its own.
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.parse
import urllib.request

from gsuite.errors import CLIError

# Set by gsuite.cli.main() when --debug is passed.
DEBUG = False

# Seconds to wait on a request; set by gsuite.cli.main() from --timeout or
# $GSUITE_TIMEOUT.
DEFAULT_TIMEOUT = 30.0
TIMEOUT = DEFAULT_TIMEOUT


def _trace(line: str) -> None:
    if DEBUG:
        print(line, file=sys.stderr)


def _timed_out(err: BaseException) -> bool:
    """True for a socket timeout, bare or wrapped in a URLError."""
    return isinstance(err, TimeoutError) or isinstance(
        getattr(err, "reason", None), TimeoutError)


def _reason(err: BaseException) -> str:
    """The underlying cause, unwrapped from URLError's envelope."""
    inner = getattr(err, "reason", None)
    return str(err if inner is None else inner) or type(err).__name__


def _unreachable(url: str, err: BaseException, timeout: float) -> str:
    host = urllib.parse.urlsplit(url).hostname or url
    if _timed_out(err):
        return (f"timed out after {timeout:g}s talking to {host} "
                f"(raise the limit with --timeout SECONDS)")
    return f"cannot reach {host}: {_reason(err)}"


def request(method: str, url: str, headers: dict | None = None,
            data: bytes | None = None, timeout: float | None = None):
    """Return (status, headers, body-bytes); HTTP errors are returned, not raised.

    A network failure (DNS, refused, TLS, timeout) never reached a server, so
    it has no status to return: it is raised as a CLIError, which main() turns
    into `error: …` and exit 1 instead of a traceback.
    """
    if timeout is None:
        timeout = TIMEOUT
    req = urllib.request.Request(url, method=method, data=data,
                                 headers=headers or {})
    _trace(f"→ {method} {url}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, resp_headers, body = resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as err:
        # A real HTTP response (4xx/5xx). Must be caught before URLError, its
        # base class, so callers keep seeing statuses rather than errors.
        status, resp_headers, body = err.code, dict(err.headers), err.read()
    except OSError as err:
        # Every other way urllib can fail — URLError (DNS, refused, TLS) and
        # TimeoutError/socket.timeout — is an OSError.
        _trace(f"← error: {_reason(err)}")
        raise CLIError(_unreachable(url, err, timeout)) from err
    _trace(f"← {status} {len(body or b'')} bytes")
    return status, resp_headers, body
