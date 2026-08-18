"""`gsuite forms` — create, get, questions, responses."""
from __future__ import annotations

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.output import confirm, emit, emit_obj
from gsuite.services._common import emit_paged

BASE = "https://forms.googleapis.com/v1"


def _question_type(item: dict) -> str:
    question = item.get("questionItem", {}).get("question", {})
    return next(iter(question), "-")


def cmd_create(args) -> int:
    form = Client.for_args(args).post(
        f"{BASE}/forms", json_body={"info": {"title": args.title}})
    confirm("created", form.get("formId"),
            form.get("info", {}).get("title"))
    return 0


def cmd_get(args) -> int:
    form = Client.for_args(args).get(f"{BASE}/forms/{quote_id(args.id)}")
    emit_obj(args, {
        "id": form.get("formId"),
        "title": form.get("info", {}).get("title"),
        "description": form.get("info", {}).get("description"),
        "url": form.get("responderUri"),
        "items": len(form.get("items", [])),
    })
    return 0


def cmd_questions(args) -> int:
    form = Client.for_args(args).get(f"{BASE}/forms/{quote_id(args.id)}")
    emit(args, form.get("items", []),
         [("ID", "itemId"), ("TITLE", "title"), ("TYPE", _question_type)])
    return 0


def cmd_responses(args) -> int:
    emit_paged(args, f"{BASE}/forms/{quote_id(args.id)}/responses",
               [("ID", "responseId"), ("SUBMITTED", "lastSubmittedTime")],
               key="responses", limit=args.max)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "forms", "Google Forms: create, inspect, responses", [
        Cmd("create", cmd_create, "create a form",
            (arg("--title", required=True),)),
        Cmd("get", cmd_get, "show form metadata", (arg("id"),)),
        Cmd("questions", cmd_questions, "list a form's questions",
            (arg("id"),)),
        Cmd("responses", cmd_responses, "list form responses",
            (arg("id"), max_flag(50))),
    ])
