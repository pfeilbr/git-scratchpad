import json
import os
import sys

import pytest

# Make the in-repo package importable without an install step.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeTransport:
    """Programmable stand-in for gsuite.transport.request."""

    def __init__(self):
        self.calls = []
        self.routes = []

    def add(self, method, url_part, body, status=200):
        self.routes.append((method, url_part, status, body))

    def __call__(self, method, url, headers=None, data=None, timeout=30):
        self.calls.append(
            {"method": method, "url": url, "headers": headers or {}, "data": data}
        )
        # one-shot FIFO: each programmed route answers exactly one request,
        # so ordered sequences (e.g. 401 then 200) are expressible.
        for route in self.routes:
            m, part, status, body = route
            if m == method and part in url:
                self.routes.remove(route)
                payload = body if isinstance(body, bytes) else json.dumps(body).encode()
                return status, {"content-type": "application/json"}, payload
        raise AssertionError(f"unexpected request: {method} {url}")


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    d = tmp_path / "gsuite-config"
    monkeypatch.setenv("GSUITE_CONFIG_DIR", str(d))
    return d


@pytest.fixture
def fake_transport(monkeypatch):
    import gsuite.transport

    ft = FakeTransport()
    monkeypatch.setattr(gsuite.transport, "request", ft)
    return ft


@pytest.fixture
def authed(config_dir):
    """A config store with a logged-in default account and fresh token."""
    import time

    from gsuite.config import ConfigStore

    store = ConfigStore()
    store.save_client({"client_id": "cid", "client_secret": "csec"})
    store.add_account("a@x.com")
    store.save_token("a@x.com", {"access_token": "tok", "refresh_token": "ref",
                                 "expiry": time.time() + 3600})
    return store


@pytest.fixture
def run_cli(capsys):
    def _run(*argv, expect=0):
        from gsuite.cli import main

        code = main(list(argv))
        out, err = capsys.readouterr()
        assert code == expect, f"exit {code} (wanted {expect})\nstdout:{out}\nstderr:{err}"
        return out
    return _run
