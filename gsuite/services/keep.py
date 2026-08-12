"""`gsuite keep` — list, get, create notes."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.output import confirm, emit_obj
from gsuite.services._common import emit_paged

BASE = "https://keep.googleapis.com/v1"


def cmd_list(args) -> int:
    emit_paged(args, f"{BASE}/notes", [("NAME", "name"), ("TITLE", "title")],
               key="notes", limit=args.max)
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
    confirm("created", note.get("name"))
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "keep", "Google Keep notes", [
        Cmd("list", cmd_list, "list notes", (max_flag(50),)),
        Cmd("get", cmd_get, "show a note", (arg("id"),)),
        Cmd("create", cmd_create, "create a text note",
            (arg("--title", default=""), arg("--text", required=True))),
    ])
