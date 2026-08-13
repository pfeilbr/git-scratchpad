"""`gsuite slides` — create, info, cat, add."""
from __future__ import annotations

import secrets

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, register_service
from gsuite.output import confirm, emit_obj

BASE = "https://slides.googleapis.com/v1/presentations"


def _slide_text(slide: dict) -> str:
    chunks: list[str] = []
    for element in slide.get("pageElements", []):
        for te in element.get("shape", {}).get("text", {}).get("textElements", []):
            content = te.get("textRun", {}).get("content", "")
            if content:
                chunks.append(content)
    return "".join(chunks)


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


def cmd_cat(args) -> int:
    pres = Client.for_args(args).get(f"{BASE}/{args.id}")
    if getattr(args, "json", False):
        emit_obj(args, pres)  # raw presentation JSON
        return 0
    for n, slide in enumerate(pres.get("slides", []), start=1):
        print(f"-- slide {n} --")
        text = _slide_text(slide)
        if text:
            print(text, end="" if text.endswith("\n") else "\n")
    return 0


def cmd_add(args) -> int:
    title_id = f"title_{secrets.token_hex(8)}"
    body_id = f"body_{secrets.token_hex(8)}"
    requests = [
        {"createSlide": {
            "slideLayoutReference": {"predefinedLayout": "TITLE_AND_BODY"},
            "placeholderIdMappings": [
                {"layoutPlaceholder": {"type": "TITLE"}, "objectId": title_id},
                {"layoutPlaceholder": {"type": "BODY"}, "objectId": body_id},
            ],
        }},
        {"insertText": {"objectId": title_id, "text": args.title}},
    ]
    if args.body:
        requests.append({"insertText": {"objectId": body_id, "text": args.body}})
    Client.for_args(args).post(f"{BASE}/{args.id}:batchUpdate",
                               json_body={"requests": requests})
    confirm("added slide to", args.id)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "slides",
                     "presentations: create, info, cat, add", [
        Cmd("create", cmd_create, "create a presentation",
            (arg("--title", required=True),)),
        Cmd("info", cmd_info, "show title and slide count", (arg("id"),)),
        Cmd("cat", cmd_cat, "print each slide's text", (arg("id"),)),
        Cmd("add", cmd_add, "append a title-and-body slide",
            (arg("id"), arg("--title", required=True),
             arg("--body", help="body placeholder text"))),
    ])
