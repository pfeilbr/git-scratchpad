"""`gsuite docs` — create, cat, append."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, register_service
from gsuite.output import confirm

BASE = "https://docs.googleapis.com/v1/documents"


def _extract_text(document: dict) -> str:
    chunks: list[str] = []
    for element in document.get("body", {}).get("content", []):
        for pe in element.get("paragraph", {}).get("elements", []):
            chunks.append(pe.get("textRun", {}).get("content", ""))
    return "".join(chunks)


def cmd_create(args) -> int:
    doc = Client.for_args(args).post(BASE, json_body={"title": args.title})
    confirm("created", doc.get("documentId"), doc.get("title"))
    return 0


def cmd_cat(args) -> int:
    doc = Client.for_args(args).get(f"{BASE}/{args.id}")
    print(_extract_text(doc), end="")
    return 0


def cmd_append(args) -> int:
    Client.for_args(args).post(f"{BASE}/{args.id}:batchUpdate", json_body={
        "requests": [{"insertText": {"endOfSegmentLocation": {},
                                     "text": args.text}}],
    })
    confirm("appended to", args.id)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "docs", "Google Docs: create, cat, append", [
        Cmd("create", cmd_create, "create a document",
            (arg("--title", required=True),)),
        Cmd("cat", cmd_cat, "print a document's plain text", (arg("id"),)),
        Cmd("append", cmd_append, "append text to a document",
            (arg("id"), arg("--text", required=True))),
    ])
