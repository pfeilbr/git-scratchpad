"""`gsuite admin` — Workspace Directory users and groups (GAM-style)."""
from __future__ import annotations

import urllib.parse

from gsuite.api import Client
from gsuite.output import emit, emit_obj

BASE = "https://admin.googleapis.com/admin/directory/v1"


def _quoted(email: str) -> str:
    return urllib.parse.quote(email, safe="")


# -- users ---------------------------------------------------------------------

def cmd_users_list(args) -> int:
    params: dict = {"customer": "my_customer", "maxResults": 100}
    if args.query:
        params["query"] = args.query
    if args.domain:
        params["domain"] = args.domain
        params.pop("customer")
    users = Client.for_args(args).paged(f"{BASE}/users", params=params,
                                        key="users", limit=args.max)
    emit(args, list(users), [
        ("EMAIL", "primaryEmail"),
        ("NAME", lambda u: u.get("name", {}).get("fullName", "")),
        ("SUSPENDED", lambda u: "yes" if u.get("suspended") else ""),
        ("ADMIN", lambda u: "yes" if u.get("isAdmin") else ""),
    ])
    return 0


def cmd_users_info(args) -> int:
    user = Client.for_args(args).get(f"{BASE}/users/{_quoted(args.email)}")
    emit_obj(args, {
        "email": user.get("primaryEmail"),
        "name": user.get("name", {}).get("fullName", ""),
        "suspended": user.get("suspended", False),
        "admin": user.get("isAdmin", False),
        "orgUnit": user.get("orgUnitPath", ""),
        "lastLogin": user.get("lastLoginTime", ""),
    })
    return 0


def cmd_users_create(args) -> int:
    user = Client.for_args(args).post(f"{BASE}/users", json_body={
        "primaryEmail": args.email,
        "name": {"givenName": args.first, "familyName": args.last},
        "password": args.password,
    })
    print(f"created {user.get('primaryEmail', '')}".strip())
    return 0


def _set_suspended(args, value: bool) -> int:
    Client.for_args(args).patch(f"{BASE}/users/{_quoted(args.email)}",
                                json_body={"suspended": value})
    print(f"{'suspended' if value else 'unsuspended'} {args.email}")
    return 0


def cmd_users_suspend(args) -> int:
    return _set_suspended(args, True)


def cmd_users_unsuspend(args) -> int:
    return _set_suspended(args, False)


def cmd_users_delete(args) -> int:
    Client.for_args(args).delete(f"{BASE}/users/{_quoted(args.email)}")
    print(f"deleted {args.email}")
    return 0


# -- groups ---------------------------------------------------------------------

def cmd_groups_list(args) -> int:
    groups = Client.for_args(args).paged(
        f"{BASE}/groups", params={"customer": "my_customer"},
        key="groups", limit=args.max)
    emit(args, list(groups), [("EMAIL", "email"), ("NAME", "name"),
                              ("MEMBERS", "directMembersCount")])
    return 0


def cmd_groups_create(args) -> int:
    group = Client.for_args(args).post(f"{BASE}/groups", json_body={
        "email": args.email, "name": args.name or args.email})
    print(f"created {group.get('email', '')}".strip())
    return 0


def cmd_groups_members(args) -> int:
    members = Client.for_args(args).paged(
        f"{BASE}/groups/{_quoted(args.group)}/members", key="members")
    emit(args, list(members), [("EMAIL", "email"), ("ROLE", "role"),
                               ("STATUS", "status")])
    return 0


def cmd_groups_add_member(args) -> int:
    Client.for_args(args).post(
        f"{BASE}/groups/{_quoted(args.group)}/members",
        json_body={"email": args.email, "role": args.role})
    print(f"added {args.email} to {args.group}")
    return 0


def register(subparsers) -> None:
    p = subparsers.add_parser("admin", help="Workspace admin: users, groups")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    users = sub.add_parser("users", help="manage users")
    users_sub = users.add_subparsers(dest="users_command", metavar="<command>")

    u_list = users_sub.add_parser("list")
    u_list.add_argument("--query", help="Directory API query, e.g. name:Jane")
    u_list.add_argument("--domain")
    u_list.add_argument("--max", type=int, default=100)
    u_list.set_defaults(func=cmd_users_list)

    u_info = users_sub.add_parser("info")
    u_info.add_argument("email")
    u_info.set_defaults(func=cmd_users_info)

    u_create = users_sub.add_parser("create")
    u_create.add_argument("--email", required=True)
    u_create.add_argument("--first", required=True)
    u_create.add_argument("--last", required=True)
    u_create.add_argument("--password", required=True)
    u_create.set_defaults(func=cmd_users_create)

    for name, func in (("suspend", cmd_users_suspend),
                       ("unsuspend", cmd_users_unsuspend),
                       ("delete", cmd_users_delete)):
        sp = users_sub.add_parser(name)
        sp.add_argument("email")
        sp.set_defaults(func=func)

    groups = sub.add_parser("groups", help="manage groups")
    groups_sub = groups.add_subparsers(dest="groups_command", metavar="<command>")

    g_list = groups_sub.add_parser("list")
    g_list.add_argument("--max", type=int, default=100)
    g_list.set_defaults(func=cmd_groups_list)

    g_create = groups_sub.add_parser("create")
    g_create.add_argument("--email", required=True)
    g_create.add_argument("--name")
    g_create.set_defaults(func=cmd_groups_create)

    g_members = groups_sub.add_parser("members")
    g_members.add_argument("group")
    g_members.set_defaults(func=cmd_groups_members)

    g_add = groups_sub.add_parser("add-member")
    g_add.add_argument("group")
    g_add.add_argument("email")
    g_add.add_argument("--role", default="MEMBER",
                       choices=["MEMBER", "MANAGER", "OWNER"])
    g_add.set_defaults(func=cmd_groups_add_member)
