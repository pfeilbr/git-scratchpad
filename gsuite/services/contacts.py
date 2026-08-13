"""`gsuite contacts` — list, search, get, update, groups (People API)."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, Group, arg, max_flag, register_service
from gsuite.errors import CLIError
from gsuite.output import confirm, emit, emit_obj
from gsuite.services._common import emit_paged

BASE = "https://people.googleapis.com/v1"
PERSON_FIELDS = "names,emailAddresses,phoneNumbers"
COLUMNS = [
    ("RESOURCE", "resourceName"),
    ("NAME", lambda p: (p.get("names") or [{}])[0].get("displayName", "")),
    ("EMAIL", lambda p: (p.get("emailAddresses") or [{}])[0].get("value", "")),
    ("PHONE", lambda p: (p.get("phoneNumbers") or [{}])[0].get("value", "")),
]
GROUP_COLUMNS = [
    ("RESOURCE", "resourceName"),
    ("NAME", "name"),
    ("MEMBERS", "memberCount"),
]


def cmd_list(args) -> int:
    emit_paged(args, f"{BASE}/people/me/connections", COLUMNS,
               params={"personFields": PERSON_FIELDS, "pageSize": 100},
               key="connections", limit=args.max)
    return 0


def cmd_search(args) -> int:
    result = Client.for_args(args).get(
        f"{BASE}/people:searchContacts",
        params={"query": args.query, "readMask": PERSON_FIELDS})
    people = [r.get("person", {}) for r in result.get("results", [])]
    emit(args, people, COLUMNS)
    return 0


def cmd_create(args) -> int:
    body: dict = {"names": [{"unstructuredName": args.name}]}
    if args.email:
        body["emailAddresses"] = [{"value": args.email}]
    if args.phone:
        body["phoneNumbers"] = [{"value": args.phone}]
    person = Client.for_args(args).post(f"{BASE}/people:createContact",
                                        json_body=body)
    confirm("created", person.get("resourceName"))
    return 0


def cmd_rm(args) -> int:
    Client.for_args(args).delete(f"{BASE}/{args.resource}:deleteContact")
    confirm("deleted", args.resource)
    return 0


def cmd_get(args) -> int:
    person = Client.for_args(args).get(
        f"{BASE}/{args.resource}",
        params={"personFields": f"{PERSON_FIELDS},organizations"})
    emit_obj(args, person, [
        ("resource", "resourceName"),
        ("name", lambda p: (p.get("names") or [{}])[0].get("displayName", "")),
        ("email",
         lambda p: (p.get("emailAddresses") or [{}])[0].get("value", "")),
        ("phone", lambda p: (p.get("phoneNumbers") or [{}])[0].get("value", "")),
        ("org", lambda p: (p.get("organizations") or [{}])[0].get("name", "")),
    ])
    return 0


def cmd_update(args) -> int:
    updates: dict = {}
    if args.name:
        updates["names"] = [{"unstructuredName": args.name}]
    if args.email:
        updates["emailAddresses"] = [{"value": args.email}]
    if args.phone:
        updates["phoneNumbers"] = [{"value": args.phone}]
    if not updates:
        raise CLIError("nothing to update (pass --name, --email and/or --phone)")
    fields = ",".join(updates)
    client = Client.for_args(args)
    etag = client.get(f"{BASE}/{args.resource}",
                      params={"personFields": fields}).get("etag")
    client.patch(f"{BASE}/{args.resource}:updateContact",
                 params={"updatePersonFields": fields},
                 json_body={"etag": etag, **updates})
    confirm("updated", args.resource)
    return 0


def cmd_groups_list(args) -> int:
    emit_paged(args, f"{BASE}/contactGroups", GROUP_COLUMNS,
               key="contactGroups")
    return 0


def cmd_groups_create(args) -> int:
    group = Client.for_args(args).post(
        f"{BASE}/contactGroups", json_body={"contactGroup": {"name": args.name}})
    confirm("created", group.get("resourceName"))
    return 0


def cmd_groups_add(args) -> int:
    Client.for_args(args).post(
        f"{BASE}/{args.group}/members:modify",
        json_body={"resourceNamesToAdd": [args.person]})
    confirm("added", args.person, "to", args.group)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "contacts", "list, search, create contacts", [
        Cmd("list", cmd_list, "list contacts", (max_flag(100),)),
        Cmd("search", cmd_search, "search contacts", (arg("query"),)),
        Cmd("get", cmd_get, "show one contact",
            (arg("resource", help="e.g. people/c123"),)),
        Cmd("create", cmd_create, "create a contact",
            (arg("--name", required=True), arg("--email"), arg("--phone"))),
        Cmd("update", cmd_update, "update contact fields",
            (arg("resource", help="e.g. people/c123"),
             arg("--name"), arg("--email"), arg("--phone"))),
        Cmd("rm", cmd_rm, "delete a contact by resource name",
            (arg("resource", help="e.g. people/c123"),)),
        Group("groups", "manage contact groups", (
            Cmd("list", cmd_groups_list, "list contact groups"),
            Cmd("create", cmd_groups_create, "create a contact group",
                (arg("--name", required=True),)),
            Cmd("add", cmd_groups_add, "add a person to a group",
                (arg("group", help="e.g. contactGroups/abc"),
                 arg("person", help="e.g. people/c123"))),
        )),
    ])
