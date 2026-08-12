import pytest

from gsuite.config import ConfigStore, default_config_dir
from gsuite.errors import CLIError


@pytest.fixture
def store(tmp_path):
    return ConfigStore(tmp_path / "cfg")


def test_add_and_list_accounts(store):
    store.add_account("a@example.com", services=["gmail"])
    store.add_account("b@example.com", services=["drive", "calendar"])
    accounts = store.list_accounts()
    assert [a["email"] for a in accounts] == ["a@example.com", "b@example.com"]
    assert accounts[1]["services"] == ["calendar", "drive"]


def test_first_account_becomes_default(store):
    store.add_account("a@example.com")
    store.add_account("b@example.com")
    assert store.default_account() == "a@example.com"


def test_set_default_requires_known_account(store):
    store.add_account("a@example.com")
    with pytest.raises(CLIError):
        store.set_default("nobody@example.com")
    store.add_account("b@example.com")
    store.set_default("b@example.com")
    assert store.default_account() == "b@example.com"


def test_alias_resolution(store):
    store.add_account("work@example.com")
    store.set_alias("work", "work@example.com")
    assert store.resolve("work") == "work@example.com"
    assert store.resolve("work@example.com") == "work@example.com"
    assert store.resolve(None) == "work@example.com"  # falls back to default


def test_resolve_unknown_account_raises(store):
    with pytest.raises(CLIError):
        store.resolve("ghost@example.com")
    with pytest.raises(CLIError):
        store.resolve(None)  # no accounts at all


def test_alias_to_unknown_account_raises(store):
    with pytest.raises(CLIError):
        store.set_alias("w", "nobody@example.com")


def test_remove_account_clears_default_alias_and_token(store):
    store.add_account("a@example.com")
    store.set_alias("me", "a@example.com")
    store.save_token("a@example.com", {"access_token": "t"})
    store.remove_account("a@example.com")
    assert store.list_accounts() == []
    assert store.default_account() is None
    assert store.load_token("a@example.com") is None
    with pytest.raises(CLIError):
        store.resolve("me")


def test_token_roundtrip_and_private_perms(store):
    store.save_token("a@example.com", {"access_token": "x", "refresh_token": "r"})
    assert store.load_token("a@example.com")["refresh_token"] == "r"
    path = store.token_path("a@example.com")
    assert path.stat().st_mode & 0o777 == 0o600


def test_client_credentials_roundtrip(store):
    assert store.load_client() is None
    store.save_client({"client_id": "id", "client_secret": "s"})
    assert store.load_client()["client_id"] == "id"


def test_env_var_overrides_config_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("GSUITE_CONFIG_DIR", str(tmp_path / "elsewhere"))
    assert default_config_dir() == tmp_path / "elsewhere"
