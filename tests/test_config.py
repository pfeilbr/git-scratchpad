import os

import pytest

import gsuite.config
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


# -- config dir resolution ------------------------------------------------
#
# Every case pins the platform and the whole env explicitly: these assert on
# the resolution rules, never on the platform or home dir the tests run on.
#
# The platform is pinned via gsuite.config._windows rather than by patching
# os.name, because pathlib picks PosixPath vs WindowsPath off os.name at every
# Path() call. A patched os.name therefore makes path construction raise on the
# host platform ("cannot instantiate 'WindowsPath' on your system") — in the
# code under test, and in pytest's own reporting and tmp_path cleanup. Patching
# the seam keeps pathlib on the real platform, so these run anywhere.


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """Non-Windows, a throwaway HOME, and none of the three env vars set."""
    home = tmp_path / "home"
    monkeypatch.setattr(gsuite.config, "_windows", lambda: False)
    monkeypatch.setenv("HOME", str(home))  # Path.home() on POSIX
    monkeypatch.setenv("USERPROFILE", str(home))  # ...and on Windows
    for var in ("GSUITE_CONFIG_DIR", "XDG_CONFIG_HOME", "APPDATA"):
        monkeypatch.delenv(var, raising=False)
    return home


def _pin_windows(monkeypatch):
    monkeypatch.setattr(gsuite.config, "_windows", lambda: True)


def test_default_config_dir_is_xdg_default(clean_env):
    assert default_config_dir() == clean_env / ".config" / "gsuite"


def test_gsuite_config_dir_wins_over_everything(clean_env, monkeypatch, tmp_path):
    _pin_windows(monkeypatch)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("GSUITE_CONFIG_DIR", str(tmp_path / "explicit"))
    assert default_config_dir() == tmp_path / "explicit"


def test_xdg_config_home_is_honored(clean_env, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert default_config_dir() == tmp_path / "xdg" / "gsuite"


def test_empty_xdg_config_home_falls_through_to_home(clean_env, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    assert default_config_dir() == clean_env / ".config" / "gsuite"


def test_empty_gsuite_config_dir_is_treated_as_unset(clean_env, monkeypatch):
    monkeypatch.setenv("GSUITE_CONFIG_DIR", "")
    # An empty override must not resolve to the current working directory.
    assert default_config_dir() == clean_env / ".config" / "gsuite"


def test_windows_uses_appdata(clean_env, monkeypatch, tmp_path):
    _pin_windows(monkeypatch)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))  # loses to APPDATA
    assert default_config_dir() == tmp_path / "AppData" / "gsuite"


def test_windows_without_appdata_falls_back_to_home(clean_env, monkeypatch):
    _pin_windows(monkeypatch)
    monkeypatch.setenv("APPDATA", "")  # empty is as good as unset
    assert default_config_dir() == clean_env / ".gsuite"


def test_windows_flag_tracks_os_name(monkeypatch):
    """The seam the tests pin above is really just `os.name == "nt"`."""

    def flag_when(name: str) -> bool:
        # undo() in a finally rather than at teardown: os.name has to be back
        # to normal before anything can raise, or pytest's own traceback
        # formatting dies trying to construct a Path.
        monkeypatch.setattr(os, "name", name)
        try:
            return gsuite.config._windows()
        finally:
            monkeypatch.undo()

    assert (flag_when("nt"), flag_when("posix")) == (True, False)
