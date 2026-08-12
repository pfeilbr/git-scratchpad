"""`gsuite gmail` — search, read, send, reply, forward, labels, drafts, trash."""
from __future__ import annotations

import base64
from email.message import EmailMessage

from gsuite.api import Client
from gsuite.cmdreg import Cmd, Group, arg, max_flag, register_service
from gsuite.errors import CLIError
from gsuite.output import confirm, emit, emit_obj

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

COMPOSE_ARGS = (arg("--to", required=True), arg("--subject", default=""),
                arg("--body", default=""), arg("--cc"), arg("--bcc"))


def _b64u_decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode(errors="replace")


def _headers(message: dict) -> dict:
    return {h["name"].lower(): h["value"]
            for h in message.get("payload", {}).get("headers", [])}


def _plain_body(payload: dict) -> str:
    """Depth-first search for the first text/plain part."""
    if payload.get("mimeType", "").startswith("text/plain"):
        data = payload.get("body", {}).get("data")
        return _b64u_decode(data) if data else ""
    for part in payload.get("parts", []):
        text = _plain_body(part)
        if text:
            return text
    return ""


def _build_mime(to: str, subject: str, body: str, cc: str | None = None,
                bcc: str | None = None, extra_headers: dict | None = None) -> str:
    msg = EmailMessage()
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    msg["Subject"] = subject
    for name, value in (extra_headers or {}).items():
        msg[name] = value
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def _fetch_meta(client: Client, msg_id: str) -> dict:
    return client.get(f"{BASE}/messages/{msg_id}", params={
        "format": "metadata",
        "metadataHeaders": ["From", "To", "Subject", "Date", "Message-ID"],
    })


def cmd_search(args) -> int:
    client = Client.for_args(args)
    refs = client.paged(f"{BASE}/messages", params={"q": args.query},
                        key="messages", limit=args.max)
    rows = []
    for ref in refs:
        message = _fetch_meta(client, ref["id"])
        headers = _headers(message)
        rows.append({"id": message["id"], "date": headers.get("date", ""),
                     "from": headers.get("from", ""),
                     "subject": headers.get("subject", ""),
                     "snippet": message.get("snippet", "")})
    emit(args, rows, [("ID", "id"), ("DATE", "date"), ("FROM", "from"),
                      ("SUBJECT", "subject")])
    return 0


def cmd_get(args) -> int:
    client = Client.for_args(args)
    message = client.get(f"{BASE}/messages/{args.id}", params={"format": "full"})
    headers = _headers(message)
    emit_obj(args, {
        "id": message.get("id"),
        "thread": message.get("threadId"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "date": headers.get("date", ""),
        "subject": headers.get("subject", ""),
        "body": _plain_body(message.get("payload", {})),
    })
    return 0


def _send(client: Client, raw: str, thread_id: str | None = None) -> dict:
    body: dict = {"raw": raw}
    if thread_id:
        body["threadId"] = thread_id
    sent = client.post(f"{BASE}/messages/send", json_body=body)
    confirm("sent", sent.get("id"))
    return sent


def cmd_send(args) -> int:
    raw = _build_mime(args.to, args.subject, args.body, cc=args.cc, bcc=args.bcc)
    _send(Client.for_args(args), raw)
    return 0


def cmd_reply(args) -> int:
    client = Client.for_args(args)
    original = _fetch_meta(client, args.id)
    headers = _headers(original)
    subject = headers.get("subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    extra = {}
    if headers.get("message-id"):
        extra["In-Reply-To"] = headers["message-id"]
        extra["References"] = headers["message-id"]
    raw = _build_mime(headers.get("reply-to") or headers.get("from", ""),
                      subject, args.body, extra_headers=extra)
    _send(client, raw, thread_id=original.get("threadId"))
    return 0


def cmd_forward(args) -> int:
    client = Client.for_args(args)
    original = client.get(f"{BASE}/messages/{args.id}", params={"format": "full"})
    headers = _headers(original)
    subject = headers.get("subject", "")
    if not subject.lower().startswith("fwd:"):
        subject = f"Fwd: {subject}"
    quoted = (f"---------- Forwarded message ----------\n"
              f"From: {headers.get('from', '')}\n"
              f"Date: {headers.get('date', '')}\n"
              f"Subject: {headers.get('subject', '')}\n\n"
              f"{_plain_body(original.get('payload', {}))}")
    body = f"{args.body}\n\n{quoted}" if args.body else quoted
    _send(client, _build_mime(args.to, subject, body))
    return 0


def cmd_trash(args) -> int:
    Client.for_args(args).post(f"{BASE}/messages/{args.id}/trash")
    confirm("trashed", args.id)
    return 0


def _label_id(client: Client, name: str) -> str:
    labels = client.get(f"{BASE}/labels").get("labels", [])
    for label in labels:
        if label["name"] == name or label["id"] == name:
            return label["id"]
    raise CLIError(f"no such label: {name}")


def cmd_labels_list(args) -> int:
    labels = Client.for_args(args).get(f"{BASE}/labels").get("labels", [])
    emit(args, sorted(labels, key=lambda l: l["name"]),
         [("ID", "id"), ("NAME", "name"), ("TYPE", "type")])
    return 0


def cmd_labels_create(args) -> int:
    created = Client.for_args(args).post(f"{BASE}/labels",
                                         json_body={"name": args.name})
    confirm("created", created.get("id"), created.get("name"))
    return 0


def _modify_labels(args, action_key: str, verb: str, preposition: str) -> int:
    client = Client.for_args(args)
    label_id = _label_id(client, args.label)
    client.post(f"{BASE}/messages/{args.id}/modify",
                json_body={action_key: [label_id]})
    confirm(verb, args.label, preposition, args.id)
    return 0


def cmd_labels_apply(args) -> int:
    return _modify_labels(args, "addLabelIds", "applied", "to")


def cmd_labels_remove(args) -> int:
    return _modify_labels(args, "removeLabelIds", "removed", "from")


def cmd_drafts_list(args) -> int:
    drafts = Client.for_args(args).get(f"{BASE}/drafts").get("drafts", [])
    emit(args, drafts, [("ID", "id"), ("MESSAGE", lambda d: d["message"]["id"])])
    return 0


def cmd_drafts_create(args) -> int:
    raw = _build_mime(args.to, args.subject, args.body, cc=args.cc, bcc=args.bcc)
    draft = Client.for_args(args).post(f"{BASE}/drafts",
                                       json_body={"message": {"raw": raw}})
    confirm("draft", draft.get("id"))
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "gmail", "search, read, send, labels, drafts", [
        Cmd("search", cmd_search, "search messages (Gmail query syntax)",
            (arg("query"), max_flag(20))),
        Cmd("get", cmd_get, "read a message (plain-text body)", (arg("id"),)),
        Cmd("send", cmd_send, "send an email", COMPOSE_ARGS),
        Cmd("reply", cmd_reply, "reply on the original thread",
            (arg("id"), arg("--body", required=True))),
        Cmd("forward", cmd_forward, "forward a message",
            (arg("id"), arg("--to", required=True), arg("--body", default=""))),
        Cmd("trash", cmd_trash, "move a message to trash", (arg("id"),)),
        Group("labels", "manage labels", (
            Cmd("list", cmd_labels_list),
            Cmd("create", cmd_labels_create, args=(arg("name"),)),
            Cmd("apply", cmd_labels_apply, args=(arg("id"), arg("label"))),
            Cmd("remove", cmd_labels_remove, args=(arg("id"), arg("label"))),
        )),
        Group("drafts", "manage drafts", (
            Cmd("list", cmd_drafts_list),
            Cmd("create", cmd_drafts_create, args=COMPOSE_ARGS),
        )),
    ])
