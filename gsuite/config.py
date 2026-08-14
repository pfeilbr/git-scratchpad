"""On-disk configuration: accounts, aliases, tokens, OAuth client.

Layout, under the config dir ($GSUITE_CONFIG_DIR, else %APPDATA%\\gsuite on
Windows, else $XDG_CONFIG_HOME/gsuite, else ~/.config/gsuite — see
`default_config_dir()`):
  accounts.json          accounts, aliases, default account
  client.json            OAuth client credentials (Desktop app type)
  tokens/<email>.json    per-account token set

Everything here holds credentials, so every write goes through
`_write_atomic()`: directories gsuite creates are 0700, files are created 0600
before a byte of payload reaches them, and the destination is published with a
rename so an interrupted run can never leave a half-written store behind.
Text is UTF-8 everywhere, independent of the platform's locale.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from gsuite.errors import CLIError

DIR_MODE = 0o700   # config dirs: owner-only, so `ls` cannot enumerate accounts
FILE_MODE = 0o600  # tokens, client secret, accounts: owner-only
ENCODING = "utf-8"  # JSON is UTF-8 by spec; never the platform default


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


def _dumps(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


class ConfigStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_config_dir()

    # -- low-level ---------------------------------------------------------

    def _accounts_path(self) -> Path:
        return self.root / "accounts.json"

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
        data = self._read()
        data["accounts"][email] = {"services": sorted(set(services or []))}
        if data["default"] is None:
            data["default"] = email
        self._write(data)

    def remove_account(self, email: str) -> None:
        data = self._read()
        data["accounts"].pop(email, None)
        data["aliases"] = {a: e for a, e in data["aliases"].items() if e != email}
        if data["default"] == email:
            data["default"] = next(iter(sorted(data["accounts"])), None)
        self._write(data)
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
        data = self._read()
        if email not in data["accounts"]:
            raise CLIError(f"unknown account: {email} (add it with `gsuite auth login`)")
        data["default"] = email
        self._write(data)

    def set_alias(self, alias: str, email: str) -> None:
        data = self._read()
        if email not in data["accounts"]:
            raise CLIError(f"unknown account: {email} (add it with `gsuite auth login`)")
        data["aliases"][alias] = email
        self._write(data)

    def remove_alias(self, alias: str) -> None:
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
