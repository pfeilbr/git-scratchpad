"""`gsuite admin` — Workspace Directory users and groups (GAM-style)."""
from __future__ import annotations

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, Group, arg, max_flag, register_service
from gsuite.output import confirm, emit_obj
from gsuite.services._common import emit_paged

BASE = "https://admin.googleapis.com/admin/directory/v1"


# -- users ---------------------------------------------------------------------

def cmd_users_list(args) -> int:
    params: dict = {"customer": "my_customer", "maxResults": 100}
    if args.query:
        params["query"] = args.query
    if args.domain:
        params["domain"] = args.domain
        params.pop("customer")
    emit_paged(args, f"{BASE}/users", [
        ("EMAIL", "primaryEmail"),
        ("NAME", lambda u: u.get("name", {}).get("fullName", "")),
        ("SUSPENDED", lambda u: "yes" if u.get("suspended") else ""),
        ("ADMIN", lambda u: "yes" if u.get("isAdmin") else ""),
    ], params=params, key="users", limit=args.max)
    return 0


def cmd_users_info(args) -> int:
    user = Client.for_args(args).get(f"{BASE}/users/{quote_id(args.email)}")
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
    confirm("created", user.get("primaryEmail"))
    return 0


def _set_suspended(args, value: bool) -> int:
    Client.for_args(args).patch(f"{BASE}/users/{quote_id(args.email)}",
                                json_body={"suspended": value})
    confirm("suspended" if value else "unsuspended", args.email)
    return 0


def cmd_users_suspend(args) -> int:
    return _set_suspended(args, True)


def cmd_users_unsuspend(args) -> int:
    return _set_suspended(args, False)


def cmd_users_delete(args) -> int:
    Client.for_args(args).delete(f"{BASE}/users/{quote_id(args.email)}")
    confirm("deleted", args.email)
    return 0


# -- groups ---------------------------------------------------------------------

def cmd_groups_list(args) -> int:
    emit_paged(args, f"{BASE}/groups",
               [("EMAIL", "email"), ("NAME", "name"),
                ("MEMBERS", "directMembersCount")],
               params={"customer": "my_customer"}, key="groups", limit=args.max)
    return 0


def cmd_groups_create(args) -> int:
    group = Client.for_args(args).post(f"{BASE}/groups", json_body={
        "email": args.email, "name": args.name or args.email})
    confirm("created", group.get("email"))
    return 0


def cmd_groups_members(args) -> int:
    emit_paged(args, f"{BASE}/groups/{quote_id(args.group)}/members",
               [("EMAIL", "email"), ("ROLE", "role"), ("STATUS", "status")],
               key="members")
    return 0


def cmd_groups_add_member(args) -> int:
    Client.for_args(args).post(
        f"{BASE}/groups/{quote_id(args.group)}/members",
        json_body={"email": args.email, "role": args.role})
    confirm("added", args.email, "to", args.group)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "admin", "Workspace admin: users, groups", [
        Group("users", "manage users", (
            Cmd("list", cmd_users_list,
                args=(arg("--query", help="Directory API query, e.g. name:Jane"),
                      arg("--domain"), max_flag(100))),
            Cmd("info", cmd_users_info, args=(arg("email"),)),
            Cmd("create", cmd_users_create,
                args=(arg("--email", required=True),
                      arg("--first", required=True),
                      arg("--last", required=True),
                      arg("--password", required=True))),
            Cmd("suspend", cmd_users_suspend, args=(arg("email"),)),
            Cmd("unsuspend", cmd_users_unsuspend, args=(arg("email"),)),
            Cmd("delete", cmd_users_delete, args=(arg("email"),)),
        )),
        Group("groups", "manage groups", (
            Cmd("list", cmd_groups_list, args=(max_flag(100),)),
            Cmd("create", cmd_groups_create,
                args=(arg("--email", required=True), arg("--name"))),
            Cmd("members", cmd_groups_members, args=(arg("group"),)),
            Cmd("add-member", cmd_groups_add_member,
                args=(arg("group"), arg("email"),
                      arg("--role", default="MEMBER",
                          choices=["MEMBER", "MANAGER", "OWNER"]))),
        )),
    ])
