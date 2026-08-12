"""`gsuite keep` — list, get, create notes."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.output import emit, emit_obj

BASE = "https://keep.googleapis.com/v1"


def cmd_list(args) -> int:
    notes = Client.for_args(args).paged(f"{BASE}/notes", key="notes",
                                        limit=args.max)
    emit(args, list(notes), [("NAME", "name"), ("TITLE", "title")])
    return 0


def cmd_get(args) -> int:
    name = args.id if args.id.startswith("notes/") else f"notes/{args.id}"
    note = Client.for_args(args).get(f"{BASE}/{name}")
    emit_obj(args, {
        "name": note.get("name"),
        "title": note.get("title", ""),
        "text": note.get("body", {}).get("text", {}).get("text", ""),
    })
    return 0


def cmd_create(args) -> int:
    note = Client.for_args(args).post(f"{BASE}/notes", json_body={
        "title": args.title,
        "body": {"text": {"text": args.text}},
    })
    print(f"created {note.get('name', '')}".strip())
    return 0


def register(subparsers) -> None:
    p = subparsers.add_parser("keep", help="Google Keep notes")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    lst = sub.add_parser("list", help="list notes")
    lst.add_argument("--max", type=int, default=50)
    lst.set_defaults(func=cmd_list)

    get = sub.add_parser("get", help="show a note")
    get.add_argument("id")
    get.set_defaults(func=cmd_get)

    create = sub.add_parser("create", help="create a text note")
    create.add_argument("--title", default="")
    create.add_argument("--text", required=True)
    create.set_defaults(func=cmd_create)
