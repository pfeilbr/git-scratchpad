"""The browser hand-off, exercised for real.

`loopback_authorizer` binds a socket, opens a browser and blocks on the
redirect — so every other test replaces it with a stub, leaving the most
user-facing code in the tool unexecuted. These tests run the real function
and play the part of the browser: a fake `webbrowser.open` performs the
redirect request the browser would have made.
"""
import threading
import urllib.parse
import urllib.request

import pytest

from gsuite import oauth
from gsuite.errors import AuthError

CLIENT = {"client_id": "cid", "client_secret": "csec"}


class FakeBrowser:
    """Stands in for webbrowser.open: answers the consent URL with `query`.

    gsuite opens the browser on a daemon thread and returns as soon as the
    redirect is handled, so `done` lets a test wait for this side to finish
    recording before it asserts.
    """

    def __init__(self, query: str):
        self.query = query
        self.consent: dict = {}
        self.page_status = None
        self.page = ""
        self.done = threading.Event()

    def open(self, url: str) -> None:
        try:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            self.consent = {k: v[0] for k, v in params.items()}
            target = (f"{self.consent['redirect_uri']}?"
                      f"{self.query.format(state=self.consent['state'])}")
            # Bypass any ambient proxy: this is a loopback address.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(target, timeout=10) as resp:
                self.page_status, self.page = resp.status, resp.read().decode()
        finally:
            self.done.set()

    def wait(self):
        assert self.done.wait(timeout=10), "browser stand-in never finished"
        return self


def install(monkeypatch, query: str) -> FakeBrowser:
    fake = FakeBrowser(query)
    monkeypatch.setattr(oauth.webbrowser, "open", fake.open)
    return fake


def test_loopback_flow_returns_the_code_and_serves_a_page(monkeypatch, capsys):
    fake = install(monkeypatch, "code=the-code&state={state}")

    code, redirect_uri = oauth.loopback_authorizer(CLIENT, ["scope-a"])
    fake.wait()

    assert code == "the-code"
    assert redirect_uri.startswith("http://127.0.0.1:")
    # The consent URL the browser was sent to is the real thing.
    assert fake.consent["client_id"] == "cid"
    assert fake.consent["scope"] == "scope-a"
    assert fake.consent["access_type"] == "offline"
    assert fake.consent["prompt"] == "consent"   # always re-issue a refresh token
    assert fake.consent["redirect_uri"] == redirect_uri
    # The user sees a readable page, not a bare 200.
    assert fake.page_status == 200
    assert "authorization complete" in fake.page.lower()
    # And the URL is printed, so a headless machine can still complete login.
    printed = capsys.readouterr().out
    assert fake.consent["state"] in printed
    assert "accounts.google.com" in printed


def test_loopback_rejects_a_mismatched_state(monkeypatch):
    """A forged callback must not be accepted as a login."""
    fake = install(monkeypatch, "code=injected&state=not-the-state")
    with pytest.raises(AuthError, match="state mismatch"):
        oauth.loopback_authorizer(CLIENT, ["scope-a"])
    fake.wait()


def test_loopback_surfaces_a_denied_consent(monkeypatch):
    fake = install(monkeypatch, "error=access_denied")
    with pytest.raises(AuthError, match="access_denied"):
        oauth.loopback_authorizer(CLIENT, ["scope-a"])
    fake.wait()


def test_loopback_can_run_twice(monkeypatch):
    """Back-to-back logins must not collide on a still-bound socket."""
    first = install(monkeypatch, "code=one&state={state}")
    code1, uri1 = oauth.loopback_authorizer(CLIENT, ["s"])
    first.wait()

    second = install(monkeypatch, "code=two&state={state}")
    code2, uri2 = oauth.loopback_authorizer(CLIENT, ["s"])
    second.wait()

    assert (code1, code2) == ("one", "two")
    assert first.consent["state"] != second.consent["state"]  # fresh each time


def test_login_flow_exchanges_the_code_through_the_real_authorizer(
        monkeypatch, fake_transport):
    """End to end: browser hand-off -> token exchange -> scopes recorded."""
    fake = install(monkeypatch, "code=flow-code&state={state}")
    fake_transport.add("POST", "oauth2.googleapis.com/token",
                       {"access_token": "at", "refresh_token": "rt",
                        "expires_in": 3600})

    token = oauth.login_flow(CLIENT, ["scope-a"])
    fake.wait()

    assert token["access_token"] == "at"
    assert token["scopes"] == ["scope-a"]
    body = fake_transport.calls[0]["data"].decode()
    assert "code=flow-code" in body
    assert "grant_type=authorization_code" in body
