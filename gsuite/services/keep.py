"""`gsuite keep` — list, get, create, delete, share notes."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.errors import CLIError
from gsuite.output import confirm, emit_obj
from gsuite.services._common import emit_paged

BASE = "https://keep.googleapis.com/v1"


def _note_name(note_id: str) -> str:
    """Accept `notes/x` or a bare `x`; return the full resource name."""
    return note_id if note_id.startswith("notes/") else f"notes/{note_id}"


def cmd_list(args) -> int:
    emit_paged(args, f"{BASE}/notes", [("NAME", "name"), ("TITLE", "title")],
               key="notes", limit=args.max)
    return 0


def cmd_get(args) -> int:
    name = _note_name(args.id)
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


def cmd_rm(args) -> int:
    name = _note_name(args.id)
    Client.for_args(args).delete(f"{BASE}/{name}")
    confirm("deleted", name)
    return 0


def cmd_share(args) -> int:
    name = _note_name(args.id)
    Client.for_args(args).post(f"{BASE}/{name}/permissions:batchCreate",
                               json_body={"requests": [{
                                   "parent": name,
                                   "permission": {"role": "WRITER",
                                                  "email": args.email},
                               }]})
    confirm("shared", name, "with", args.email)
    return 0


def cmd_unshare(args) -> int:
    name = _note_name(args.id)
    client = Client.for_args(args)
    note = client.get(f"{BASE}/{name}")
    perm = next((p for p in note.get("permissions", [])
                 if p.get("email") == args.email), None)
    if perm is None:
        raise CLIError(f"no permission for {args.email} on {name}")
    client.post(f"{BASE}/{name}/permissions:batchDelete",
                json_body={"names": [perm["name"]]})
    confirm("unshared", args.email, "from", name)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "keep", "Google Keep notes", [
        Cmd("list", cmd_list, "list notes", (max_flag(50),)),
        Cmd("get", cmd_get, "show a note", (arg("id"),)),
        Cmd("create", cmd_create, "create a text note",
            (arg("--title", default=""), arg("--text", required=True))),
        Cmd("rm", cmd_rm, "delete a note", (arg("id"),)),
        Cmd("share", cmd_share, "grant an email write access to a note",
            (arg("id"), arg("email"))),
        Cmd("unshare", cmd_unshare, "revoke an email's access to a note",
            (arg("id"), arg("email"))),
    ])
