"""On-disk configuration: accounts, aliases, tokens, OAuth client.

Layout, under the config dir ($GSUITE_CONFIG_DIR, else %APPDATA%\\gsuite on
Windows, else $XDG_CONFIG_HOME/gsuite, else ~/.config/gsuite — see
`default_config_dir()`):
  accounts.json          accounts, aliases, default account
  accounts.json.lock     the lock serializing edits to accounts.json (empty)
  client.json            OAuth client credentials (Desktop app type)
  tokens/<email>.json    per-account token set

Everything here holds credentials, so every write goes through
`_write_atomic()`: directories gsuite creates are 0700, files are created 0600
before a byte of payload reaches them, and the destination is published with a
rename so an interrupted run can never leave a half-written store behind.
Text is UTF-8 everywhere, independent of the platform's locale.

accounts.json is the one file two gsuite runs edit at the same time — two
`gsuite auth login`s, a shell loop setting aliases — and an atomic write alone
does not make that safe: both runs read the same store and the second write
drops the first run's account. So every read-modify-write of it runs inside
`ConfigStore._locked()` (see there for the platform details); reads take no
lock at all, since the atomic replace already hands a reader one whole version
or the other.
"""
from __future__ import annotations

import contextlib
import errno
import json
import os
import tempfile
import time
from pathlib import Path

from gsuite.errors import CLIError

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows has msvcrt instead
    fcntl = None
try:  # Windows
    import msvcrt
except ImportError:  # pragma: no cover - POSIX has fcntl instead
    msvcrt = None

DIR_MODE = 0o700   # config dirs: owner-only, so `ls` cannot enumerate accounts
FILE_MODE = 0o600  # tokens, client secret, accounts: owner-only
ENCODING = "utf-8"  # JSON is UTF-8 by spec; never the platform default
LOCK_NAME = "accounts.json.lock"
LOCK_TIMEOUT = 5.0  # seconds; the guarded section is a read, an edit and a write
LOCK_POLL = 0.01    # how often to retry while waiting for the holder to finish

# Every errno the two lock APIs use for "somebody else holds it". Anything else
# means the lock itself is broken (no locking on this filesystem, say), which is
# a different error with different advice — never something to keep polling.
_BUSY = frozenset(
    code for code in (getattr(errno, name, None) for name in
                      ("EACCES", "EAGAIN", "EWOULDBLOCK", "EDEADLOCK", "EDEADLK"))
    if code is not None
)


def _windows() -> bool:
    """Whether to use Windows conventions.

    A seam so tests can pin the platform. They cannot patch ``os.name``
    directly: ``pathlib`` picks ``PosixPath`` vs ``WindowsPath`` off it at
    every ``Path()`` call, so a patched value makes path construction raise
    on the host platform ("cannot instantiate 'WindowsPath' on your system").
    """
    return os.name == "nt"


def default_config_dir() -> Path:
    """Directory holding accounts, tokens, and the OAuth client.

    Resolution order, first match wins. An env var set to the empty string
    counts as unset — a bare ``GSUITE_CONFIG_DIR=`` in a shell script must not
    scatter config into the current directory:

    1. ``$GSUITE_CONFIG_DIR`` — explicit override, honored on every platform.
    2. Windows: ``%APPDATA%\\gsuite``, or ``~/.gsuite`` if APPDATA is unset.
    3. ``$XDG_CONFIG_HOME/gsuite`` — the XDG Base Directory spec gives the
       variable precedence over its default.
    4. ``~/.config/gsuite`` — that XDG default, and the common case.
    """
    override = os.environ.get("GSUITE_CONFIG_DIR")
    if override:
        return Path(override)
    if _windows():
        appdata = os.environ.get("APPDATA")
        return Path(appdata) / "gsuite" if appdata else Path.home() / ".gsuite"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "gsuite"
    return Path.home() / ".config" / "gsuite"


def _ensure_private_dir(path: Path) -> None:
    """Create `path` and any missing parents, readable only by their owner.

    Only directories this call actually creates are chmod-ed. $GSUITE_CONFIG_DIR
    may sit under a directory shared with other tools (/tmp, a group home);
    silently locking that down is a worse surprise than leaving it as found.

    `mkdir(mode=...)` is masked by the umask — it can only ever take bits away,
    so 0700 never leaks, but an exotic umask (0o277, say) would leave the dir
    unwritable. The explicit chmod makes the result the same everywhere.
    """
    missing = []
    probe = path
    while not probe.exists():
        missing.append(probe)
        if probe.parent == probe:  # filesystem root; nothing left to create
            break
        probe = probe.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=DIR_MODE)
        except FileExistsError:  # lost a race; not ours to re-permission
            continue
        directory.chmod(DIR_MODE)


def _write_atomic(path: Path, text: str, mode: int = FILE_MODE) -> None:
    """Publish `text` at `path` atomically, never at the process umask.

    The payload is staged in a temp file in the destination's own directory —
    same filesystem, so `os.replace()` is an atomic rename on POSIX and on
    Windows — and only then takes the destination's name. Interrupt this at
    any point and what survives is either the old file or the new one, never a
    truncated one.

    `mkstemp` opens at 0600, so a refresh token is never on disk world-readable,
    not even for the instant between `open()` and a `chmod()`. The chmod after
    the rename is what tightens a destination an older gsuite left loose (the
    renamed file carries the temp file's mode, so it is a no-op otherwise).
    """
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=ENCODING) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())  # rename publishes content, not intent
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, mode)


def _try_lock(fd: int) -> bool:
    """Take the exclusive lock on `fd`; False if another run already holds it.

    Never blocks — the caller polls — so the wait can be bounded and a wedged
    holder cannot wedge everyone else forever (see `ConfigStore._locked`).

    The two platforms are not equally well covered, and this is the honest
    version of the difference:

    * POSIX uses `fcntl.flock`. The lock belongs to the open file description,
      so it serializes threads in one process as well as separate processes,
      and the kernel drops it when the holder's last handle closes — including
      when the process is killed. It is only as good as the filesystem: an
      NFSv3 mount with no lock daemon may not enforce it at all, in which case
      concurrent logins can still lose an update.
    * Windows uses `msvcrt.locking` on a single byte, which is a mandatory
      byte-range lock released when the handle closes, so it excludes other
      processes the same way. It is the same shape of guarantee, but this
      branch is not exercised by the test suite (which runs on POSIX), so
      treat Windows as untested rather than proven.
    """
    if _windows():
        os.lseek(fd, 0, os.SEEK_SET)  # msvcrt locks a range at the cursor
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in _BUSY:
                return False
            raise
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in _BUSY:
            return False
        raise
    return True


def _unlock(fd: int) -> None:
    """Drop the lock on `fd`. Closing the handle would do it too; this is tidier."""
    if _windows():
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return
    fcntl.flock(fd, fcntl.LOCK_UN)


def _dumps(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


class ConfigStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_config_dir()

    # -- low-level ---------------------------------------------------------

    def _accounts_path(self) -> Path:
        return self.root / "accounts.json"

    def _lock_path(self) -> Path:
        return self.root / LOCK_NAME

    @contextlib.contextmanager
    def _locked(self):
        """Hold the account store's exclusive lock for the block.

        Every read-modify-write of accounts.json runs in here — the read, the
        edit and the write are one indivisible step — so two gsuite runs
        compose instead of clobbering: the loser waits, then reads back what
        the winner published and adds its own change on top. Serializing in
        this one place is the whole of the mechanism; the mutators below just
        wrap themselves in it.

        The lock is a file of its own beside the store rather than
        accounts.json itself, because `_write_atomic()` *replaces* that file:
        a lock taken on it would end up held on an unlinked inode that no
        later run can even name, excluding nobody. The lock file is never
        deleted, for exactly the same reason — unlinking it after use would
        let the next run create a fresh inode and walk straight into the
        critical section beside a waiter still holding the old one. It stays
        put, empty, 0600, and costs one inode.

        Readers deliberately do not come through here: `gsuite auth list` must
        never hang behind someone else's login, and the atomic replace already
        gives a reader one whole version of the file or the other.

        The wait is bounded by `LOCK_TIMEOUT`. A holder that dies drops the
        lock with its handle, but one that merely hangs does not, and the CLI
        has to fail with something the user can act on rather than block
        forever.
        """
        path = self._lock_path()
        _ensure_private_dir(self.root)
        # Created 0600 like everything else here; the umask can only take bits
        # away, so it never leaks, and the chmod makes an exotic one (or a lock
        # file left loose by an older gsuite) deterministic either way.
        fd = os.open(path, os.O_RDWR | os.O_CREAT, FILE_MODE)
        try:
            os.chmod(path, FILE_MODE)
            deadline = time.monotonic() + LOCK_TIMEOUT
            while True:
                try:
                    if _try_lock(fd):
                        break
                except OSError as exc:  # not contention: locking is unavailable
                    raise CLIError(
                        f"cannot lock {path} ({exc}) — the config directory may "
                        "be on a filesystem without file locking; point "
                        "$GSUITE_CONFIG_DIR at a local one"
                    ) from exc
                if time.monotonic() >= deadline:
                    raise CLIError(
                        f"timed out after {LOCK_TIMEOUT:g}s waiting for "
                        f"{path} — another gsuite run is still writing the "
                        "account store. If none is running, remove that lock "
                        "file and try again"
                    )
                time.sleep(LOCK_POLL)
            try:
                yield
            finally:
                _unlock(fd)
        finally:
            os.close(fd)

    def token_path(self, email: str) -> Path:
        return self.root / "tokens" / f"{email}.json"

    def _read(self) -> dict:
        path = self._accounts_path()
        try:
            return json.loads(path.read_text(encoding=ENCODING))
        except FileNotFoundError:
            return {"default": None, "accounts": {}, "aliases": {}}
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            # Not a CLIError otherwise: every command, including the ones that
            # would let the user recover, would die with a stack trace.
            raise CLIError(
                f"{path} is not valid JSON ({exc}) — fix or remove it, then "
                "re-run `gsuite auth login <email>`"
            ) from exc

    def _write(self, data: dict) -> None:
        text = _dumps(data)  # serialize first: nothing touches disk on error
        _ensure_private_dir(self.root)
        _write_atomic(self._accounts_path(), text)

    @staticmethod
    def _write_private(path: Path, payload: dict) -> None:
        text = _dumps(payload)
        _ensure_private_dir(path.parent)
        _write_atomic(path, text)

    # -- accounts ----------------------------------------------------------

    def add_account(self, email: str, services: list[str] | None = None) -> None:
        with self._locked():
            data = self._read()
            data["accounts"][email] = {"services": sorted(set(services or []))}
            if data["default"] is None:
                data["default"] = email
            self._write(data)

    def remove_account(self, email: str) -> None:
        with self._locked():
            data = self._read()
            data["accounts"].pop(email, None)
            data["aliases"] = {a: e for a, e in data["aliases"].items()
                               if e != email}
            if data["default"] == email:
                data["default"] = next(iter(sorted(data["accounts"])), None)
            self._write(data)
        # Outside the lock: a token file is this account's alone, so dropping
        # it races with nobody, and the lock stays as narrow as the store.
        try:
            self.token_path(email).unlink()
        except FileNotFoundError:
            pass

    def list_accounts(self) -> list[dict]:
        data = self._read()
        return [
            {"email": email, "default": email == data["default"], **info}
            for email, info in sorted(data["accounts"].items())
        ]

    def default_account(self) -> str | None:
        return self._read()["default"]

    def set_default(self, email: str) -> None:
        with self._locked():
            data = self._read()
            if email not in data["accounts"]:
                raise CLIError(
                    f"unknown account: {email} (add it with `gsuite auth login`)")
            data["default"] = email
            self._write(data)

    def set_alias(self, alias: str, email: str) -> None:
        with self._locked():
            data = self._read()
            if email not in data["accounts"]:
                raise CLIError(
                    f"unknown account: {email} (add it with `gsuite auth login`)")
            data["aliases"][alias] = email
            self._write(data)

    def remove_alias(self, alias: str) -> None:
        with self._locked():
            data = self._read()
            data["aliases"].pop(alias, None)
            self._write(data)

    def resolve(self, name: str | None) -> str:
        """Resolve an alias/email/None (=default) to a configured account."""
        data = self._read()
        if name is None:
            if data["default"] is None:
                raise CLIError("no accounts configured — run `gsuite auth login <email>`")
            return data["default"]
        if name in data["aliases"]:
            return data["aliases"][name]
        if name in data["accounts"]:
            return name
        raise CLIError(f"unknown account or alias: {name}")

    # -- tokens ------------------------------------------------------------

    def save_token(self, email: str, token: dict) -> None:
        self._write_private(self.token_path(email), token)

    def load_token(self, email: str) -> dict | None:
        try:
            return json.loads(self.token_path(email).read_text(encoding=ENCODING))
        except FileNotFoundError:
            return None

    # -- OAuth client credentials -------------------------------------------

    def save_client(self, client: dict) -> None:
        self._write_private(self.root / "client.json", client)

    def load_client(self) -> dict | None:
        try:
            return json.loads((self.root / "client.json").read_text(encoding=ENCODING))
        except FileNotFoundError:
            return None
