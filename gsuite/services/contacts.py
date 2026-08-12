"""`gsuite contacts` — list, search, create, rm (People API)."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.output import emit

BASE = "https://people.googleapis.com/v1"
PERSON_FIELDS = "names,emailAddresses,phoneNumbers"
COLUMNS = [
    ("RESOURCE", "resourceName"),
    ("NAME", lambda p: (p.get("names") or [{}])[0].get("displayName", "")),
    ("EMAIL", lambda p: (p.get("emailAddresses") or [{}])[0].get("value", "")),
    ("PHONE", lambda p: (p.get("phoneNumbers") or [{}])[0].get("value", "")),
]


def cmd_list(args) -> int:
    people = Client.for_args(args).paged(
        f"{BASE}/people/me/connections",
        params={"personFields": PERSON_FIELDS, "pageSize": 100},
        key="connections", limit=args.max)
    emit(args, list(people), COLUMNS)
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
    print(f"created {person.get('resourceName', '')}".strip())
    return 0


def cmd_rm(args) -> int:
    Client.for_args(args).delete(f"{BASE}/{args.resource}:deleteContact")
    print(f"deleted {args.resource}")
    return 0


def register(subparsers) -> None:
    p = subparsers.add_parser("contacts", help="list, search, create contacts")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    lst = sub.add_parser("list", help="list contacts")
    lst.add_argument("--max", type=int, default=100)
    lst.set_defaults(func=cmd_list)

    search = sub.add_parser("search", help="search contacts")
    search.add_argument("query")
    search.set_defaults(func=cmd_search)

    create = sub.add_parser("create", help="create a contact")
    create.add_argument("--name", required=True)
    create.add_argument("--email")
    create.add_argument("--phone")
    create.set_defaults(func=cmd_create)

    rm = sub.add_parser("rm", help="delete a contact by resource name")
    rm.add_argument("resource", help="e.g. people/c123")
    rm.set_defaults(func=cmd_rm)
