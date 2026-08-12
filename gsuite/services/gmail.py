"""`gsuite gmail` — search, read, send, reply, forward, labels, drafts, trash."""
from __future__ import annotations

import base64
from email.message import EmailMessage

from gsuite.api import Client
from gsuite.errors import CLIError
from gsuite.output import emit, emit_obj

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


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
    return client.post(f"{BASE}/messages/send", json_body=body)


def cmd_send(args) -> int:
    client = Client.for_args(args)
    raw = _build_mime(args.to, args.subject, args.body, cc=args.cc, bcc=args.bcc)
    sent = _send(client, raw)
    print(f"sent {sent.get('id', '')}".strip())
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
    sent = _send(client, raw, thread_id=original.get("threadId"))
    print(f"sent {sent.get('id', '')}".strip())
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
    sent = _send(client, _build_mime(args.to, subject, body))
    print(f"sent {sent.get('id', '')}".strip())
    return 0


def cmd_trash(args) -> int:
    Client.for_args(args).post(f"{BASE}/messages/{args.id}/trash")
    print(f"trashed {args.id}")
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
    print(f"created {created.get('id', '')} {created.get('name', '')}".strip())
    return 0


def cmd_labels_apply(args) -> int:
    client = Client.for_args(args)
    label_id = _label_id(client, args.label)
    client.post(f"{BASE}/messages/{args.id}/modify",
                json_body={"addLabelIds": [label_id]})
    print(f"applied {args.label} to {args.id}")
    return 0


def cmd_labels_remove(args) -> int:
    client = Client.for_args(args)
    label_id = _label_id(client, args.label)
    client.post(f"{BASE}/messages/{args.id}/modify",
                json_body={"removeLabelIds": [label_id]})
    print(f"removed {args.label} from {args.id}")
    return 0


def cmd_drafts_list(args) -> int:
    drafts = Client.for_args(args).get(f"{BASE}/drafts").get("drafts", [])
    emit(args, drafts, [("ID", "id"), ("MESSAGE", lambda d: d["message"]["id"])])
    return 0


def cmd_drafts_create(args) -> int:
    raw = _build_mime(args.to, args.subject, args.body, cc=args.cc, bcc=args.bcc)
    draft = Client.for_args(args).post(f"{BASE}/drafts",
                                       json_body={"message": {"raw": raw}})
    print(f"draft {draft.get('id', '')}".strip())
    return 0


def _add_compose_flags(parser, require_to=True) -> None:
    parser.add_argument("--to", required=require_to)
    parser.add_argument("--subject", default="")
    parser.add_argument("--body", default="")
    parser.add_argument("--cc")
    parser.add_argument("--bcc")


def register(subparsers) -> None:
    p = subparsers.add_parser("gmail", help="search, read, send, labels, drafts")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    search = sub.add_parser("search", help="search messages (Gmail query syntax)")
    search.add_argument("query")
    search.add_argument("--max", type=int, default=20)
    search.set_defaults(func=cmd_search)

    get = sub.add_parser("get", help="read a message (plain-text body)")
    get.add_argument("id")
    get.set_defaults(func=cmd_get)

    send = sub.add_parser("send", help="send an email")
    _add_compose_flags(send)
    send.set_defaults(func=cmd_send)

    reply = sub.add_parser("reply", help="reply on the original thread")
    reply.add_argument("id")
    reply.add_argument("--body", required=True)
    reply.set_defaults(func=cmd_reply)

    fwd = sub.add_parser("forward", help="forward a message")
    fwd.add_argument("id")
    fwd.add_argument("--to", required=True)
    fwd.add_argument("--body", default="")
    fwd.set_defaults(func=cmd_forward)

    trash = sub.add_parser("trash", help="move a message to trash")
    trash.add_argument("id")
    trash.set_defaults(func=cmd_trash)

    labels = sub.add_parser("labels", help="manage labels")
    labels_sub = labels.add_subparsers(dest="labels_command", metavar="<command>")
    labels_sub.add_parser("list").set_defaults(func=cmd_labels_list)
    l_create = labels_sub.add_parser("create")
    l_create.add_argument("name")
    l_create.set_defaults(func=cmd_labels_create)
    l_apply = labels_sub.add_parser("apply")
    l_apply.add_argument("id")
    l_apply.add_argument("label")
    l_apply.set_defaults(func=cmd_labels_apply)
    l_remove = labels_sub.add_parser("remove")
    l_remove.add_argument("id")
    l_remove.add_argument("label")
    l_remove.set_defaults(func=cmd_labels_remove)

    drafts = sub.add_parser("drafts", help="manage drafts")
    drafts_sub = drafts.add_subparsers(dest="drafts_command", metavar="<command>")
    drafts_sub.add_parser("list").set_defaults(func=cmd_drafts_list)
    d_create = drafts_sub.add_parser("create")
    _add_compose_flags(d_create)
    d_create.set_defaults(func=cmd_drafts_create)
