"""`gsuite auth` — login, accounts, aliases, tokens, doctor."""
from __future__ import annotations

import json
import time

from gsuite import oauth
from gsuite.cmdreg import Cmd, Group, arg, register_service
from gsuite.config import ConfigStore
from gsuite.errors import AuthError, CLIError
from gsuite.output import confirm

# Where a human can finish the job when revocation could not be done here.
PERMISSIONS_URL = "https://myaccount.google.com/permissions"


def _token_state(token: dict | None) -> str:
    if token is None:
        return "missing"
    if token.get("expiry", 0) > time.time():
        return "valid"
    return "expired" if token.get("refresh_token") else "stale"


def _requested_services(spec: str | None) -> list[str]:
    """`--services` as a service list; the literal `all` means every service."""
    if not spec:
        return list(oauth.DEFAULT_SERVICES)
    names = [s.strip() for s in spec.split(",") if s.strip()]
    if "all" in names:
        return sorted(oauth.SERVICE_SCOPES)
    return names


def _uncovered(services: list[str], token: dict | None) -> list[str]:
    """Of `services`, those the token's granted scopes do not actually cover.

    A token from before scopes were recorded — or none at all — carries no
    evidence either way, so it accuses nobody: empty list.
    """
    if not token or "scopes" not in token:
        return []
    granted = set(oauth.granted_services(token["scopes"]))
    return [s for s in services if s not in granted]


def cmd_login(args) -> int:
    store = ConfigStore()
    requested = _requested_services(args.services)
    scopes = oauth.scopes_for(requested)
    client = oauth.get_client(store)
    token = oauth.login_flow(client, scopes)
    email = args.email or oauth.fetch_email(token)
    # The consent screen can hand back less than was asked for. Record what
    # was granted, so `auth list` and `auth doctor` describe the real token.
    declined = _uncovered(requested, token)
    services = sorted(s for s in requested if s not in declined)
    store.add_account(email, services)
    store.save_token(email, token)
    print(f"Logged in as {email} (services: {', '.join(services) or 'none'})")
    if declined:
        names = ", ".join(sorted(declined))
        print(f"warning: consent was partial — Google did not grant: {names}")
        print(f"  Commands for {names} will fail with HTTP 403 until you "
              "re-authorize and approve every box:")
        print(f"  gsuite auth login {email} --services {','.join(requested)}")
    return 0  # the login itself succeeded; it simply covers less


def _revoke_stored_token(store: ConfigStore, email: str) -> tuple[str, str]:
    """Revoke an account's token at Google: ("revoked"|"skipped"|"failed", why).

    Deliberately returns the outcome instead of raising: `logout` has to
    remove the account even when Google is unreachable — the user asked to
    log out — so each caller decides what a failure means.
    """
    if oauth.env_access_token():
        return "skipped", (f"${oauth.ACCESS_TOKEN_ENV} is the credential "
                           "source — that token is not gsuite's to revoke")
    token = store.load_token(email)
    if token is None:
        return "skipped", "no stored token — nothing to revoke"
    try:
        oauth.revoke_token(token)
    except CLIError as exc:  # HTTP error, or the network never got there
        return "failed", str(exc)
    return "revoked", "token revoked at Google"


def cmd_logout(args) -> int:
    # Revoke first: once the local file is gone the refresh token is only
    # recoverable from a backup, and it would stay valid at Google forever.
    store = ConfigStore()
    email = store.resolve(args.email)
    if args.no_revoke:
        outcome = "skipped"
        detail = "--no-revoke: the token stays valid at Google"
    else:
        outcome, detail = _revoke_stored_token(store, email)
    if outcome == "failed":
        confirm(f"warning: could not revoke the token at Google: {detail} —",
                f"it may still be valid; revoke it at {PERMISSIONS_URL}")
        detail = "removed locally only"
    store.remove_account(email)
    confirm(f"Logged out {email} ({detail})")
    return 0


def cmd_revoke(args) -> int:
    store = ConfigStore()
    email = store.resolve(args.email)
    outcome, detail = _revoke_stored_token(store, email)
    if outcome == "failed":
        raise AuthError(f"could not revoke the token for {email}: {detail} "
                        "— the account is still configured, and the token may "
                        f"still be valid ({PERMISSIONS_URL})")
    confirm(f"{email}: {detail}")
    if outcome == "revoked":
        confirm("The account is still configured — run "
                f"`gsuite auth login {email}` to get a new token.")
    return 0


def cmd_list(args) -> int:
    store = ConfigStore()
    accounts = store.list_accounts()
    if not accounts:
        print("no accounts — run `gsuite auth login <email>`")
        return 0
    for acct in accounts:
        marker = "*" if acct["default"] else " "
        state = _token_state(store.load_token(acct["email"]))
        services = ",".join(acct["services"]) or "-"
        print(f"{marker} {acct['email']}  token:{state}  services:{services}")
    return 0


def cmd_status(args) -> int:
    store = ConfigStore()
    email = store.resolve(args.account)
    token = store.load_token(email)
    print(f"account: {email}\ntoken: {_token_state(token)}")
    return 0


def cmd_switch(args) -> int:
    store = ConfigStore()
    store.set_default(store.resolve(args.email))
    print(f"default account: {args.email}")
    return 0


def cmd_alias_set(args) -> int:
    ConfigStore().set_alias(args.name, args.email)
    print(f"alias {args.name} -> {args.email}")
    return 0


def cmd_alias_rm(args) -> int:
    ConfigStore().remove_alias(args.name)
    return 0


def cmd_alias_list(args) -> int:
    data = ConfigStore()._read()
    for name, email in sorted(data["aliases"].items()):
        print(f"{name} -> {email}")
    return 0


def cmd_credentials_set(args) -> int:
    try:
        payload = json.loads(open(args.file).read())
    except (OSError, ValueError) as exc:
        raise CLIError(f"cannot read client file: {exc}") from exc
    # Accept both the raw form and the GCP console "installed"/"web" wrapper.
    inner = payload.get("installed") or payload.get("web") or payload
    if "client_id" not in inner or "client_secret" not in inner:
        raise CLIError("file does not contain client_id/client_secret")
    ConfigStore().save_client(
        {"client_id": inner["client_id"], "client_secret": inner["client_secret"]}
    )
    print("OAuth client credentials saved")
    return 0


def cmd_token(args) -> int:
    store = ConfigStore()
    email = store.resolve(args.account)
    print(oauth.get_access_token(store, email))
    return 0


def cmd_adc(args) -> int:
    """Report on Application Default Credentials: path, existence, type."""
    path = oauth.adc_path()
    print(f"path: {path}")
    try:
        adc = oauth.load_adc()
    except CLIError as exc:
        kind = "service_account" if "service_account" in str(exc) else "unusable"
        print(f"exists: yes\ntype: {kind}\nusable: no — {exc}")
        return 1
    if adc is None:
        print("exists: no\ntype: missing\nusable: no — run "
              "`gcloud auth application-default login`")
        return 1
    print("exists: yes\ntype: authorized_user\nusable: yes")
    return 0


def cmd_doctor(args) -> int:
    store = ConfigStore()
    problems = 0

    def check(ok: bool, label: str, hint: str = ""):
        nonlocal problems
        if ok:
            print(f"OK   {label}")
        else:
            problems += 1
            print(f"FAIL {label}{' — ' + hint if hint else ''}")

    try:
        oauth.get_client(store)
        has_client = True
    except CLIError:
        has_client = False
    check(has_client, "OAuth client configured",
          "run `gsuite auth credentials set <client.json>`")
    accounts = store.list_accounts()
    check(bool(accounts), "at least one account",
          "run `gsuite auth login <email>`")
    for acct in accounts:
        token = store.load_token(acct["email"])
        state = _token_state(token)
        check(state in ("valid", "expired"), f"token usable: {acct['email']}",
              f"state={state}; run `gsuite auth login {acct['email']}`")
        # A partial consent stays invisible otherwise: the account looks
        # authorized right up until a command comes back 403.
        uncovered = _uncovered(acct["services"], token)
        check(not uncovered, f"scopes cover services: {acct['email']}",
              f"granted scopes do not cover {', '.join(uncovered)}; "
              f"run `gsuite auth login {acct['email']} --services "
              f"{','.join(acct['services'])}` and approve every box")
    source = oauth.credential_source(store, store.default_account())
    check(not source.startswith("none"), f"credential source: {source}",
          "run `gsuite auth login`, set GSUITE_ACCESS_TOKEN, or configure ADC")
    return 1 if problems else 0


def register(subparsers) -> None:
    register_service(subparsers, "auth", "login, accounts, aliases, tokens", [
        Cmd("login", cmd_login, "sign in via browser (loopback OAuth)",
            (arg("email", nargs="?",
                 help="account email (auto-detected if omitted)"),
             arg("--services", help="comma-separated services to authorize, "
                 "or `all` for every service "
                 f"(default: {','.join(oauth.DEFAULT_SERVICES)})"))),
        Cmd("logout", cmd_logout,
            "revoke the token at Google, then remove the account locally",
            (arg("email"),
             arg("--no-revoke", action="store_true",
                 help="remove the account locally without revoking its token "
                      "at Google (offline, or deliberately keeping it alive)"))),
        Cmd("revoke", cmd_revoke,
            "revoke an account's token at Google, keeping the account",
            (arg("email", nargs="?",
                 help="account email or alias (default: the default account)"),)),
        Cmd("list", cmd_list, "list accounts"),
        Cmd("status", cmd_status, "show current account and token state"),
        Cmd("switch", cmd_switch, "set the default account", (arg("email"),)),
        Group("alias", "manage account aliases", (
            Cmd("set", cmd_alias_set, args=(arg("name"), arg("email"))),
            Cmd("rm", cmd_alias_rm, args=(arg("name"),)),
            Cmd("list", cmd_alias_list),
        )),
        Group("credentials", "manage the OAuth client", (
            Cmd("set", cmd_credentials_set,
                "store a Desktop-app OAuth client JSON", (arg("file"),)),
        )),
        Cmd("token", cmd_token, "print a fresh access token (for scripts)"),
        Cmd("adc", cmd_adc, "show Application Default Credentials status"),
        Cmd("doctor", cmd_doctor, "diagnose auth setup"),
    ])
