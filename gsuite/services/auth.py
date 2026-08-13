"""`gsuite auth` — login, accounts, aliases, tokens, doctor."""
from __future__ import annotations

import json
import time

from gsuite import oauth
from gsuite.cmdreg import Cmd, Group, arg, register_service
from gsuite.config import ConfigStore
from gsuite.errors import CLIError


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


def cmd_login(args) -> int:
    store = ConfigStore()
    services = _requested_services(args.services)
    scopes = oauth.scopes_for(services)
    client = oauth.get_client(store)
    token = oauth.login_flow(client, scopes)
    email = args.email or oauth.fetch_email(token)
    store.add_account(email, services)
    store.save_token(email, token)
    print(f"Logged in as {email} (services: {', '.join(sorted(services))})")
    return 0


def cmd_logout(args) -> int:
    store = ConfigStore()
    email = store.resolve(args.email)
    store.remove_account(email)
    print(f"Logged out {email}")
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
        state = _token_state(store.load_token(acct["email"]))
        check(state in ("valid", "expired"), f"token usable: {acct['email']}",
              f"state={state}; run `gsuite auth login {acct['email']}`")
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
        Cmd("logout", cmd_logout, "remove an account and its token",
            (arg("email"),)),
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
