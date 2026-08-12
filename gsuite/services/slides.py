"""`gsuite slides` — create, info."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.output import emit_obj

BASE = "https://slides.googleapis.com/v1/presentations"


def cmd_create(args) -> int:
    pres = Client.for_args(args).post(BASE, json_body={"title": args.title})
    print(f"created {pres.get('presentationId', '')}".strip())
    return 0


def cmd_info(args) -> int:
    pres = Client.for_args(args).get(f"{BASE}/{args.id}")
    emit_obj(args, {
        "id": pres.get("presentationId"),
        "title": pres.get("title"),
        "slides": len(pres.get("slides", [])),
    })
    return 0


def register(subparsers) -> None:
    p = subparsers.add_parser("slides", help="presentations: create, info")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    create = sub.add_parser("create", help="create a presentation")
    create.add_argument("--title", required=True)
    create.set_defaults(func=cmd_create)

    info = sub.add_parser("info", help="show title and slide count")
    info.add_argument("id")
    info.set_defaults(func=cmd_info)
