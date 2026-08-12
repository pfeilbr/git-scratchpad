"""`gsuite auth` — login, accounts, aliases, tokens, doctor."""
from __future__ import annotations

import json
import time

from gsuite import oauth
from gsuite.config import ConfigStore
from gsuite.errors import CLIError


def _token_state(token: dict | None) -> str:
    if token is None:
        return "missing"
    if token.get("expiry", 0) > time.time():
        return "valid"
    return "expired" if token.get("refresh_token") else "stale"


def cmd_login(args) -> int:
    store = ConfigStore()
    services = ([s.strip() for s in args.services.split(",") if s.strip()]
                if args.services else list(oauth.DEFAULT_SERVICES))
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
    return 1 if problems else 0


def register(subparsers) -> None:
    p = subparsers.add_parser("auth", help="login, accounts, aliases, tokens")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    login = sub.add_parser("login", help="sign in via browser (loopback OAuth)")
    login.add_argument("email", nargs="?", help="account email (auto-detected if omitted)")
    login.add_argument("--services", help="comma-separated services to authorize "
                       f"(default: {','.join(oauth.DEFAULT_SERVICES)})")
    login.set_defaults(func=cmd_login)

    logout = sub.add_parser("logout", help="remove an account and its token")
    logout.add_argument("email")
    logout.set_defaults(func=cmd_logout)

    sub.add_parser("list", help="list accounts").set_defaults(func=cmd_list)

    status = sub.add_parser("status", help="show current account and token state")
    status.set_defaults(func=cmd_status)

    switch = sub.add_parser("switch", help="set the default account")
    switch.add_argument("email")
    switch.set_defaults(func=cmd_switch)

    alias = sub.add_parser("alias", help="manage account aliases")
    alias_sub = alias.add_subparsers(dest="alias_command", metavar="<command>")
    a_set = alias_sub.add_parser("set")
    a_set.add_argument("name")
    a_set.add_argument("email")
    a_set.set_defaults(func=cmd_alias_set)
    a_rm = alias_sub.add_parser("rm")
    a_rm.add_argument("name")
    a_rm.set_defaults(func=cmd_alias_rm)
    alias_sub.add_parser("list").set_defaults(func=cmd_alias_list)

    creds = sub.add_parser("credentials", help="manage the OAuth client")
    creds_sub = creds.add_subparsers(dest="credentials_command", metavar="<command>")
    c_set = creds_sub.add_parser("set", help="store a Desktop-app OAuth client JSON")
    c_set.add_argument("file")
    c_set.set_defaults(func=cmd_credentials_set)

    token = sub.add_parser("token", help="print a fresh access token (for scripts)")
    token.set_defaults(func=cmd_token)

    sub.add_parser("doctor", help="diagnose auth setup").set_defaults(func=cmd_doctor)
