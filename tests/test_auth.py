import json
import time

import pytest

from gsuite import oauth
from gsuite.config import ConfigStore
from gsuite.errors import AuthError, CLIError

CLIENT = {"client_id": "cid", "client_secret": "csec"}


@pytest.fixture
def store(config_dir):
    s = ConfigStore()
    s.save_client(CLIENT)
    return s


def fake_authorizer(client, scopes):
    return "auth-code-123", "http://127.0.0.1:9999/"


def add_token_route(ft, access="tok", refresh="ref"):
    ft.add("POST", "oauth2.googleapis.com/token",
           {"access_token": access, "refresh_token": refresh,
            "expires_in": 3600, "token_type": "Bearer"})


# -- scope registry ----------------------------------------------------------

def test_scopes_for_known_services():
    scopes = oauth.scopes_for(["gmail", "calendar"])
    assert any("gmail" in s for s in scopes)
    assert any("calendar" in s for s in scopes)
    assert "https://www.googleapis.com/auth/userinfo.email" in scopes


def test_scopes_for_unknown_service_raises():
    with pytest.raises(CLIError, match="unknown service"):
        oauth.scopes_for(["gmail", "frobnicator"])


# -- flow building blocks ----------------------------------------------------

def test_build_auth_url():
    url = oauth.build_auth_url(CLIENT, ["scope-a"], "http://127.0.0.1:1/", "st8")
    assert "client_id=cid" in url
    assert "access_type=offline" in url
    assert "state=st8" in url
    assert "scope-a" in url


def test_parse_redirect_extracts_code_and_state():
    assert oauth.parse_redirect("/?code=abc&state=xyz") == ("abc", "xyz")


def test_parse_redirect_error_raises():
    with pytest.raises(AuthError, match="access_denied"):
        oauth.parse_redirect("/?error=access_denied")


def test_exchange_code_posts_grant(fake_transport):
    add_token_route(fake_transport)
    token = oauth.exchange_code(CLIENT, "thecode", "http://127.0.0.1:1/")
    assert token["access_token"] == "tok"
    assert token["refresh_token"] == "ref"
    assert token["expiry"] > time.time() + 3000
    body = fake_transport.calls[0]["data"].decode()
    assert "grant_type=authorization_code" in body
    assert "code=thecode" in body


def test_refresh_keeps_refresh_token(fake_transport):
    fake_transport.add("POST", "oauth2.googleapis.com/token",
                       {"access_token": "new", "expires_in": 3600})
    old = {"access_token": "old", "refresh_token": "keepme", "expiry": 0}
    new = oauth.refresh_access_token(CLIENT, old)
    assert new["access_token"] == "new"
    assert new["refresh_token"] == "keepme"


def test_get_access_token_returns_fresh_token_without_refresh(store, fake_transport):
    store.add_account("a@x.com")
    store.save_token("a@x.com", {"access_token": "fresh",
                                 "refresh_token": "r",
                                 "expiry": time.time() + 3600})
    assert oauth.get_access_token(store, "a@x.com") == "fresh"
    assert fake_transport.calls == []


def test_get_access_token_refreshes_expired(store, fake_transport):
    add_token_route(fake_transport, access="renewed")
    store.add_account("a@x.com")
    store.save_token("a@x.com", {"access_token": "stale",
                                 "refresh_token": "r", "expiry": 1})
    assert oauth.get_access_token(store, "a@x.com") == "renewed"
    assert store.load_token("a@x.com")["access_token"] == "renewed"


def test_get_access_token_without_login_raises(store):
    with pytest.raises(AuthError, match="auth login"):
        oauth.get_access_token(store, "nobody@x.com")


# -- CLI commands ------------------------------------------------------------

def test_auth_login_adds_account(store, fake_transport, monkeypatch, run_cli):
    monkeypatch.setattr(oauth, "loopback_authorizer", fake_authorizer)
    add_token_route(fake_transport)
    out = run_cli("auth", "login", "me@x.com", "--services", "gmail,calendar")
    assert "me@x.com" in out
    assert store.load_token("me@x.com")["access_token"] == "tok"
    accounts = store.list_accounts()
    assert accounts[0]["services"] == ["calendar", "gmail"]
    assert store.default_account() == "me@x.com"


def test_auth_login_discovers_email_via_userinfo(store, fake_transport,
                                                 monkeypatch, run_cli):
    monkeypatch.setattr(oauth, "loopback_authorizer", fake_authorizer)
    add_token_route(fake_transport)
    fake_transport.add("GET", "openidconnect.googleapis.com/v1/userinfo",
                       {"email": "found@x.com"})
    out = run_cli("auth", "login")
    assert "found@x.com" in out


def test_auth_login_without_client_credentials_fails(config_dir, run_cli):
    out = run_cli("auth", "login", "me@x.com", expect=1)


def test_auth_credentials_set_accepts_gcp_installed_format(config_dir, tmp_path,
                                                           run_cli):
    f = tmp_path / "client.json"
    f.write_text(json.dumps({"installed": {"client_id": "i", "client_secret": "s",
                                           "junk": "x"}}))
    run_cli("auth", "credentials", "set", str(f))
    assert ConfigStore().load_client() == {"client_id": "i", "client_secret": "s"}


def test_auth_list_marks_default_and_token_state(store, run_cli):
    store.add_account("a@x.com", ["gmail"])
    store.add_account("b@x.com")
    store.save_token("a@x.com", {"access_token": "t", "refresh_token": "r",
                                 "expiry": time.time() + 999})
    out = run_cli("auth", "list")
    assert "a@x.com" in out and "b@x.com" in out
    assert "*" in out.split("\n")[0 if "a@x.com" in out.split("\n")[0] else 1]
    assert "valid" in out and "missing" in out


def test_auth_switch_and_logout(store, run_cli):
    store.add_account("a@x.com")
    store.add_account("b@x.com")
    run_cli("auth", "switch", "b@x.com")
    assert store.default_account() == "b@x.com"
    run_cli("auth", "logout", "b@x.com")
    assert store.default_account() == "a@x.com"


def test_auth_alias_set_and_list(store, run_cli):
    store.add_account("work@x.com")
    run_cli("auth", "alias", "set", "w", "work@x.com")
    assert "w" in run_cli("auth", "alias", "list")
    assert ConfigStore().resolve("w") == "work@x.com"


def test_auth_token_prints_access_token(store, run_cli):
    store.add_account("a@x.com")
    store.save_token("a@x.com", {"access_token": "sekret", "refresh_token": "r",
                                 "expiry": time.time() + 999})
    assert run_cli("auth", "token").strip() == "sekret"


def test_auth_doctor_reports_problems(config_dir, run_cli):
    out = run_cli("auth", "doctor", expect=1)
    assert "FAIL" in out


def test_auth_doctor_ok(store, run_cli):
    store.add_account("a@x.com")
    store.save_token("a@x.com", {"access_token": "t", "refresh_token": "r",
                                 "expiry": time.time() + 999})
    out = run_cli("auth", "doctor")
    assert "FAIL" not in out
