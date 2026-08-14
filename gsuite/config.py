"""On-disk configuration: accounts, aliases, tokens, OAuth client.

Layout, under the config dir ($GSUITE_CONFIG_DIR, else %APPDATA%\\gsuite on
Windows, else $XDG_CONFIG_HOME/gsuite, else ~/.config/gsuite — see
`default_config_dir()`):
  accounts.json          accounts, aliases, default account
  client.json            OAuth client credentials (Desktop app type)
  tokens/<email>.json    per-account token set, mode 0600
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from gsuite.errors import CLIError


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


class ConfigStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_config_dir()

    # -- low-level ---------------------------------------------------------

    def _accounts_path(self) -> Path:
        return self.root / "accounts.json"

    def token_path(self, email: str) -> Path:
        return self.root / "tokens" / f"{email}.json"

    def _read(self) -> dict:
        try:
            return json.loads(self._accounts_path().read_text())
        except FileNotFoundError:
            return {"default": None, "accounts": {}, "aliases": {}}

    def _write(self, data: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._accounts_path().write_text(json.dumps(data, indent=2, sort_keys=True))

    @staticmethod
    def _write_private(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        path.chmod(0o600)

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
            return json.loads(self.token_path(email).read_text())
        except FileNotFoundError:
            return None

    # -- OAuth client credentials -------------------------------------------

    def save_client(self, client: dict) -> None:
        self._write_private(self.root / "client.json", client)

    def load_client(self) -> dict | None:
        try:
            return json.loads((self.root / "client.json").read_text())
        except FileNotFoundError:
            return None
