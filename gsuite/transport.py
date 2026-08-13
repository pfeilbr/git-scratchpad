"""Minimal HTTP transport on urllib — a single seam for tests to fake.

Everything network-touching in gsuite funnels through request(); tests
monkeypatch this module's `request` attribute with a FakeTransport.

`--debug` sets DEBUG here, which traces one line per request and one per
response to stderr. The trace is deliberately metadata-only: no request or
response bodies, no headers (the Authorization bearer token lives there).
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request

# Set by gsuite.cli.main() when --debug is passed.
DEBUG = False


def _trace(line: str) -> None:
    if DEBUG:
        print(line, file=sys.stderr)


def request(method: str, url: str, headers: dict | None = None,
            data: bytes | None = None, timeout: int = 30):
    """Return (status, headers, body-bytes); HTTP errors are returned, not raised."""
    req = urllib.request.Request(url, method=method, data=data,
                                 headers=headers or {})
    _trace(f"→ {method} {url}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, resp_headers, body = resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as err:
        status, resp_headers, body = err.code, dict(err.headers), err.read()
    _trace(f"← {status} {len(body or b'')} bytes")
    return status, resp_headers, body
