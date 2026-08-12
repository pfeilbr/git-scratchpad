"""Minimal HTTP transport on urllib — a single seam for tests to fake.

Everything network-touching in gsuite funnels through request(); tests
monkeypatch this module's `request` attribute with a FakeTransport.
"""
from __future__ import annotations

import urllib.error
import urllib.request


def request(method: str, url: str, headers: dict | None = None,
            data: bytes | None = None, timeout: int = 30):
    """Return (status, headers, body-bytes); HTTP errors are returned, not raised."""
    req = urllib.request.Request(url, method=method, data=data,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()
