"""`gsuite contacts` — list, search, create, rm (People API)."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.output import confirm, emit
from gsuite.services._common import emit_paged

BASE = "https://people.googleapis.com/v1"
PERSON_FIELDS = "names,emailAddresses,phoneNumbers"
COLUMNS = [
    ("RESOURCE", "resourceName"),
    ("NAME", lambda p: (p.get("names") or [{}])[0].get("displayName", "")),
    ("EMAIL", lambda p: (p.get("emailAddresses") or [{}])[0].get("value", "")),
    ("PHONE", lambda p: (p.get("phoneNumbers") or [{}])[0].get("value", "")),
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


def register(subparsers) -> None:
    register_service(subparsers, "contacts", "list, search, create contacts", [
        Cmd("list", cmd_list, "list contacts", (max_flag(100),)),
        Cmd("search", cmd_search, "search contacts", (arg("query"),)),
        Cmd("create", cmd_create, "create a contact",
            (arg("--name", required=True), arg("--email"), arg("--phone"))),
        Cmd("rm", cmd_rm, "delete a contact by resource name",
            (arg("resource", help="e.g. people/c123"),)),
    ])
