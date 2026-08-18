import contextlib
import json
import os
import subprocess
import sys
import threading
import time

import pytest

import gsuite.config
from gsuite.config import ConfigStore, default_config_dir
from gsuite.errors import CLIError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


# -- on-disk hardening: permissions, atomic writes, encoding ----------------
#
# How the credentials hit disk. Three of these properties are invisible once a
# write has finished — a token that was briefly world-readable ends up 0600
# either way, and an in-place write that is never interrupted leaves a
# perfectly good file — so each is sampled at the instant it matters, with a
# fault injected at a real syscall.
#
# Mode assertions pin the umask explicitly (the developer's shell must not
# decide whether they pass) and are skipped where mode bits are not a thing.
# The platform comes from the gsuite.config._windows() seam, never a patched
# os.name: pathlib picks PosixPath vs WindowsPath off os.name at every Path()
# call, so faking it breaks pytest itself.

posix_only = pytest.mark.skipif(
    gsuite.config._windows(), reason="POSIX mode bits: Windows has no 0600/0700"
)

LOOSE_UMASK = 0o022  # the common default: group and other keep read access
NON_ASCII = "jürgen@example.com"


@contextlib.contextmanager
def pinned_umask(mask=LOOSE_UMASK):
    old = os.umask(mask)
    try:
        yield
    finally:
        os.umask(old)


def mode_of(path):
    return path.stat().st_mode & 0o777


@posix_only
def test_token_is_never_observably_world_readable(store, monkeypatch):
    """The token must be *created* private, not created loose and tightened.

    Writing first and chmod-ing after leaves a window in which the OAuth
    refresh token sits on disk at the process umask — 0644 on a stock box,
    readable by every account on the machine. The window is invisible
    afterwards, so the mode is sampled from inside the code's own chmod call:
    the last instant at which the file may still wear its creation mode.
    """
    seen = {}
    real_chmod = os.chmod

    def spy(path, mode, *args, **kwargs):
        seen.setdefault(str(path), os.stat(path).st_mode & 0o777)
        return real_chmod(path, mode, *args, **kwargs)

    with pinned_umask():
        monkeypatch.setattr(os, "chmod", spy)
        try:
            store.save_token("a@example.com", {"refresh_token": "secret"})
        finally:
            monkeypatch.undo()  # in a finally: pytest's own cleanup chmods too

    path = store.token_path("a@example.com")
    assert str(path) in seen, "the token file was never chmod-ed at all"
    assert seen[str(path)] == 0o600, (
        f"token existed as {oct(seen[str(path)])} before the chmod tightened it"
    )
    assert mode_of(path) == 0o600


@posix_only
def test_config_and_token_dirs_are_private(store):
    """A listable tokens/ leaks which accounts exist, and to whom they belong."""
    with pinned_umask():
        store.add_account("a@example.com")
        store.save_token("a@example.com", {"refresh_token": "secret"})
        store.save_client({"client_id": "id", "client_secret": "s"})
    assert mode_of(store.root) == 0o700
    assert mode_of(store.root / "tokens") == 0o700


@posix_only
def test_a_pre_existing_config_parent_is_left_alone(tmp_path):
    """gsuite locks down what it creates, not what it was pointed at.

    $GSUITE_CONFIG_DIR can sit under a directory shared with other tools;
    silently chmod-ing that is a worse surprise than leaving it loose. The
    second assertion is the red one; the first pins the blast radius, so the
    fix cannot buy privacy by tightening directories it does not own.
    """
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o755)
    with pinned_umask():
        ConfigStore(shared / "gsuite").add_account("a@example.com")
    assert mode_of(shared) == 0o755
    assert mode_of(shared / "gsuite") == 0o700


def test_a_failed_publish_leaves_the_previous_accounts_file_intact(store, monkeypatch):
    """An interrupted save leaves the old store, never a half-written one.

    The crash is injected at the rename that publishes the new content — the
    one point at which a store staged in a temp file can still fail safely.
    An in-place write has no such point: by the time anything can go wrong the
    destination is already truncated. So before the fix nothing calls
    os.replace, the clobbering write simply succeeds, and the assertion below
    catches the new account in a file that was never meant to be published.
    """
    store.add_account("keeper@example.com")
    before = store._accounts_path().read_bytes()

    def crash(*args, **kwargs):
        raise RuntimeError("interrupted before the new file was published")

    monkeypatch.setattr(os, "replace", crash)
    try:
        with contextlib.suppress(RuntimeError):
            store.add_account("newcomer@example.com")
    finally:
        monkeypatch.undo()  # in a finally: pytest renames files of its own

    assert store._accounts_path().read_bytes() == before
    assert [a["email"] for a in store.list_accounts()] == ["keeper@example.com"]
    assert sorted(p.name for p in store.root.iterdir()) == \
        ["accounts.json", "accounts.json.lock"], "a temp file was left behind"


def test_a_failed_serialization_leaves_the_previous_accounts_file_intact(store):
    """Same guarantee, one step earlier: a payload that cannot be serialized.

    (Green before the fix too — json.dumps runs before the file is opened —
    so this is a regression pin on the order of operations in the rewrite:
    nothing may touch the destination until the bytes exist.)
    """
    store.add_account("keeper@example.com")
    before = store._accounts_path().read_bytes()
    with pytest.raises(TypeError):
        store._write({"default": None, "aliases": {},
                      "accounts": {"x@example.com": {"services": object()}}})
    assert store._accounts_path().read_bytes() == before


def test_corrupt_accounts_file_is_a_cli_error_naming_it(store):
    """A truncated store is a user problem, not a traceback.

    json.JSONDecodeError is not a CLIError, so before the fix every command —
    including the ones that would let the user recover — dies with a stack
    trace and no hint about which file is at fault.
    """
    store.add_account("a@example.com")
    store._accounts_path().write_text('{"default": "a@exa', encoding="utf-8")
    with pytest.raises(CLIError, match=r"accounts\.json"):
        store.list_accounts()
    with pytest.raises(CLIError, match=r"accounts\.json"):
        store.resolve(None)


CHILD_READS_CONFIG = '''\
"""Read a UTF-8 config store, printing the platform encoding it used."""
import json
import locale
import sys

sys.path.insert(0, sys.argv[1])
from gsuite.config import ConfigStore

print(getattr(locale, "getencoding", None) and locale.getencoding()
      or locale.getpreferredencoding(False))
print(json.dumps([a["email"] for a in ConfigStore(sys.argv[2]).list_accounts()]))
'''


def test_utf8_config_reads_back_under_a_non_utf8_locale(tmp_path):
    """accounts.json is UTF-8 by spec, not "whatever the platform defaults to".

    read_text()/write_text() with no encoding= use the locale's encoding —
    cp1252 on a Western Windows box — which mangles or rejects a non-ASCII
    account name that an editor, or another gsuite install, wrote as UTF-8.
    Rather than fake a platform (see the note above about os.name), this runs
    a real interpreter under a C locale, where the default encoding is ASCII.
    """
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "accounts.json").write_bytes(json.dumps(
        {"default": NON_ASCII, "accounts": {NON_ASCII: {"services": []}},
         "aliases": {}}, ensure_ascii=False).encode("utf-8"))
    script = tmp_path / "child.py"
    script.write_text(CHILD_READS_CONFIG, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script), ROOT, str(cfg)],
        capture_output=True, text=True,
        env={**os.environ, "LC_ALL": "C", "LANG": "C",
             "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"},
    )
    assert result.stdout, f"child printed nothing:\n{result.stderr}"
    encoding, *rest = result.stdout.splitlines()
    if "utf" in encoding.lower().replace("-", ""):
        pytest.skip(f"this interpreter stays on UTF-8 under a C locale ({encoding})")
    assert result.returncode == 0, (
        f"reading a UTF-8 accounts.json under {encoding} failed:\n{result.stderr}"
    )
    assert json.loads(rest[0]) == [NON_ASCII]


def test_non_ascii_names_and_aliases_round_trip(store):
    """The in-process half of the encoding story, on any platform."""
    store.add_account(NON_ASCII, services=["gmail"])
    store.set_alias("jürgen", NON_ASCII)
    store.save_token(NON_ASCII, {"refresh_token": "geheim-ü"})
    assert store.resolve("jürgen") == NON_ASCII
    assert store.load_token(NON_ASCII)["refresh_token"] == "geheim-ü"
    assert [a["email"] for a in store.list_accounts()] == [NON_ASCII]
    json.loads(store._accounts_path().read_text(encoding="utf-8"))


def test_ordinary_account_flows_are_unchanged(run_cli, config_dir):
    """The everyday paths, end to end: add, list, alias, switch, token reuse.

    Nothing a user sees changes when the writes become atomic and private.
    (Green before the fix — a regression pin on the rewrite.)
    """
    store = ConfigStore()
    store.add_account("a@example.com", services=["gmail"])
    store.save_token("a@example.com", {"access_token": "t", "refresh_token": "r",
                                       "expiry": time.time() + 3600})
    store.add_account("b@example.com")

    run_cli("auth", "alias", "set", "me", "b@example.com")
    listing = run_cli("auth", "list")
    assert "* a@example.com  token:valid  services:gmail" in listing
    assert "  b@example.com  token:missing  services:-" in listing
    assert run_cli("auth", "alias", "list").strip() == "me -> b@example.com"

    run_cli("auth", "switch", "me")
    assert ConfigStore().default_account() == "b@example.com"
    assert ConfigStore().load_token("a@example.com")["refresh_token"] == "r"


# -- concurrent mutation ----------------------------------------------------
#
# Two gsuite runs can mutate accounts.json at the same time: `gsuite auth login
# a@x.com` and `... b@x.com` from two shells, or a loop doing `alias set` in
# parallel. Atomic writes keep the file parseable but do nothing about the lost
# update — both runs read the same store, both write their own edit back, and
# the loser's account is simply gone.
#
# None of these tests race two threads and hope. The interleaving is pinned
# with events, and every wait is bounded, so a regression fails the suite
# instead of hanging it. Two ConfigStore instances on one root stand in for two
# processes; the last test uses real ones.

JOIN_TIMEOUT = 10.0     # only ever reached when something is genuinely wedged
HELD_LOCK_PROBE = 0.3   # long enough to show a waiter really is still waiting
PAUSED_WRITE_GRACE = 1.0  # see test_a_paused_write_cannot_clobber...
LOCK_NAME = "accounts.json.lock"


def _spawn(fn, errors):
    """Run `fn` in a daemon thread, capturing whatever it raises."""

    def body():
        try:
            fn()
        except BaseException as exc:  # never swallowed; asserted on by callers
            errors.append(exc)

    thread = threading.Thread(target=body, daemon=True)
    thread.start()
    return thread


def _lock_of(store):
    held = getattr(store, "_locked", None)
    assert held is not None, "ConfigStore has no account-store lock"
    return held


def test_a_paused_write_cannot_clobber_a_concurrent_addition(tmp_path):
    """The lost update, pinned deterministically rather than raced.

    Run A is stopped between its read and its write; run B is only then let
    loose. Without serialization B's account reaches disk and is immediately
    overwritten by A's stale copy, and exactly one of the two survives. With
    the read-modify-write serialized B cannot start until A is finished, so
    B's own read already contains a@x.com and both survive.

    A's pause is bounded on purpose: after the fix B never completes while A
    holds the lock, so A has to be able to stop waiting and go on. Nothing
    here can deadlock, before the fix or after it.
    """
    root = tmp_path / "cfg"
    a, b = ConfigStore(root), ConfigStore(root)
    at_write, b_done, errors = threading.Event(), threading.Event(), []
    real_write = a._write

    def paused_write(data):
        at_write.set()
        b_done.wait(PAUSED_WRITE_GRACE)
        real_write(data)

    a._write = paused_write  # only run A pauses; run B is an ordinary store
    ta = _spawn(lambda: a.add_account("a@x.com"), errors)
    assert at_write.wait(JOIN_TIMEOUT), "run A never reached its write"

    def run_b():
        b.add_account("b@x.com")
        b_done.set()

    tb = _spawn(run_b, errors)
    tb.join(JOIN_TIMEOUT)
    ta.join(JOIN_TIMEOUT)
    assert not (ta.is_alive() or tb.is_alive()), "a run never finished"
    assert errors == [], f"a run raised: {errors}"
    assert [x["email"] for x in ConfigStore(root).list_accounts()] == \
        ["a@x.com", "b@x.com"], "one login overwrote the other"


def test_a_second_mutation_waits_for_a_held_lock_and_then_composes(tmp_path):
    """A mutation that arrives mid-write waits, then edits what it finds.

    The lock is held open for the length of the `with`, so the waiter's state
    is observable rather than inferred: it is still running, and it has not
    published anything, until the holder lets go.
    """
    root = tmp_path / "cfg"
    a, b = ConfigStore(root), ConfigStore(root)
    a.add_account("a@x.com")
    errors = []
    with _lock_of(a)():
        t = _spawn(lambda: b.add_account("b@x.com"), errors)
        t.join(HELD_LOCK_PROBE)
        assert t.is_alive(), "the second mutation did not wait for the lock"
        during = [x["email"] for x in ConfigStore(root).list_accounts()]
    t.join(JOIN_TIMEOUT)
    assert not t.is_alive(), "the waiter never got the lock"
    assert errors == [], f"the waiter raised: {errors}"
    assert during == ["a@x.com"], "a waiter published its write early"
    assert [x["email"] for x in ConfigStore(root).list_accounts()] == \
        ["a@x.com", "b@x.com"]


def test_a_lock_held_past_the_timeout_raises_a_cli_error_naming_it(
        tmp_path, monkeypatch):
    """A wedged holder must not wedge everyone else forever.

    A process that dies drops its lock with its file handle, but one that
    hangs (a stuck OAuth flow, a suspended shell job) keeps it. The wait is
    bounded and the error has to be actionable on its own: which file, and
    what to do about it.
    """
    root = tmp_path / "cfg"
    a, b = ConfigStore(root), ConfigStore(root)
    a.add_account("a@x.com")
    held = _lock_of(a)
    monkeypatch.setattr(gsuite.config, "LOCK_TIMEOUT", 0.2)
    errors = []
    with held():
        t = _spawn(lambda: b.add_account("b@x.com"), errors)
        t.join(JOIN_TIMEOUT)
        assert not t.is_alive(), "a stale lock wedged the CLI"
    assert len(errors) == 1, f"expected one failure, got {errors}"
    message = str(errors[0])
    assert isinstance(errors[0], CLIError), f"not a CLIError: {errors[0]!r}"
    assert LOCK_NAME in message, f"the error does not name the lock file: {message}"
    assert "remove" in message.lower(), f"no way out of it: {message}"


def test_reads_never_block_on_the_write_lock(tmp_path):
    """`gsuite auth list` must not hang behind someone else's login.

    Readers take no lock at all: the atomic replace already hands them either
    the old store or the new one, never a torn one.
    """
    root = tmp_path / "cfg"
    a = ConfigStore(root)
    a.add_account("a@x.com")
    a.set_alias("me", "a@x.com")
    reader = ConfigStore(root)
    seen, done, errors = {}, threading.Event(), []

    def read_everything():
        seen["list"] = [x["email"] for x in reader.list_accounts()]
        seen["resolve"] = reader.resolve("me")
        seen["default"] = reader.default_account()
        done.set()

    with _lock_of(a)():
        t = _spawn(read_everything, errors)
        assert done.wait(HELD_LOCK_PROBE * 3), \
            "a read blocked behind the write lock"
    t.join(JOIN_TIMEOUT)
    assert errors == [], f"the reader raised: {errors}"
    assert seen == {"list": ["a@x.com"], "resolve": "a@x.com",
                    "default": "a@x.com"}


def test_the_lock_file_is_private_and_beside_the_account_store(store):
    """Where the lock lives, how it is created, and that it stays put.

    It is a file of its own rather than accounts.json itself, because
    `_write_atomic()` replaces that file — a lock taken on it would sit on an
    inode no later run can even name. Deleting the lock file after use has the
    same flaw, so it is created once and left alone; the inode check is what
    pins that.
    """
    with pinned_umask():
        store.add_account("a@example.com")
    lock = store.root / LOCK_NAME
    assert lock.exists(), "no lock file beside accounts.json"
    assert [x["email"] for x in store.list_accounts()] == ["a@example.com"], \
        "the lock file confused the store itself"
    if gsuite.config._windows():  # POSIX mode bits and inodes: not a thing
        return
    assert mode_of(lock) == 0o600, "the lock file is not owner-only"
    assert mode_of(store.root) == 0o700
    inode = lock.stat().st_ino
    with pinned_umask():
        store.set_alias("me", "a@example.com")
    assert lock.stat().st_ino == inode, \
        "the lock file was recreated — a lock on an unlinked inode excludes nobody"


def test_every_mutator_still_composes_in_a_single_process(store):
    """All five mutating calls in sequence, one after another, one process.

    (Green before the fix too — a regression pin: serializing the
    read-modify-write must not change what any of them actually does.)
    """
    store.add_account("a@example.com", services=["gmail"])
    store.add_account("b@example.com", services=["drive"])
    store.set_alias("me", "b@example.com")
    store.set_alias("other", "a@example.com")
    store.set_default("b@example.com")
    store.remove_alias("other")
    store.remove_account("a@example.com")
    assert [x["email"] for x in store.list_accounts()] == ["b@example.com"]
    assert store.default_account() == "b@example.com"
    assert store.resolve("me") == "b@example.com"
    with pytest.raises(CLIError):
        store.resolve("other")


CHILD_ADDS_ACCOUNT = '''\
"""Add one account at a start time shared with every sibling process."""
import sys
import time

sys.path.insert(0, sys.argv[1])
from gsuite.config import ConfigStore

time.sleep(max(0.0, float(sys.argv[4]) - time.time()))
ConfigStore(sys.argv[2]).add_account(sys.argv[3])
'''


def test_six_real_processes_logging_in_at_once_all_survive(tmp_path):
    """The actual scenario, with actual processes.

    Robust by construction rather than by timing: the assertion is that every
    account survives, which serialization guarantees however the six happen to
    interleave. (Before the fix it fails whenever any two overlap — most runs,
    but not reliably every run, which is why the tests above are the ones that
    pin the bug.)
    """
    cfg = tmp_path / "cfg"
    script = tmp_path / "child.py"
    script.write_text(CHILD_ADDS_ACCOUNT, encoding="utf-8")
    emails = [f"user{n}@example.com" for n in range(6)]
    start = time.time() + 1.0  # all six are up and waiting before any of them writes
    procs = [
        subprocess.Popen(
            [sys.executable, str(script), ROOT, str(cfg), email, repr(start)],
            stderr=subprocess.PIPE, text=True)
        for email in emails
    ]
    failures = []
    for proc, email in zip(procs, emails):
        _, err = proc.communicate(timeout=60)
        if proc.returncode != 0:
            failures.append(f"{email}: {err.strip()}")
    assert failures == [], "\n".join(failures)
    assert [x["email"] for x in ConfigStore(cfg).list_accounts()] == emails
