"""`gsuite docs` — create, cat, append."""
from __future__ import annotations

from gsuite.api import Client

BASE = "https://docs.googleapis.com/v1/documents"


def _extract_text(document: dict) -> str:
    chunks: list[str] = []
    for element in document.get("body", {}).get("content", []):
        for pe in element.get("paragraph", {}).get("elements", []):
            chunks.append(pe.get("textRun", {}).get("content", ""))
    return "".join(chunks)


def cmd_create(args) -> int:
    doc = Client.for_args(args).post(BASE, json_body={"title": args.title})
    print(f"created {doc.get('documentId', '')} {doc.get('title', '')}".strip())
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
    print(f"appended to {args.id}")
    return 0


def register(subparsers) -> None:
    p = subparsers.add_parser("docs", help="Google Docs: create, cat, append")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    create = sub.add_parser("create", help="create a document")
    create.add_argument("--title", required=True)
    create.set_defaults(func=cmd_create)

    cat = sub.add_parser("cat", help="print a document's plain text")
    cat.add_argument("id")
    cat.set_defaults(func=cmd_cat)

    append = sub.add_parser("append", help="append text to a document")
    append.add_argument("id")
    append.add_argument("--text", required=True)
    append.set_defaults(func=cmd_append)
