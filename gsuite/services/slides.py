"""`gsuite slides` — create, info."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, register_service
from gsuite.output import confirm, emit_obj

BASE = "https://slides.googleapis.com/v1/presentations"


def cmd_create(args) -> int:
    pres = Client.for_args(args).post(BASE, json_body={"title": args.title})
    confirm("created", pres.get("presentationId"))
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
    register_service(subparsers, "slides", "presentations: create, info", [
        Cmd("create", cmd_create, "create a presentation",
            (arg("--title", required=True),)),
        Cmd("info", cmd_info, "show title and slide count", (arg("id"),)),
    ])
