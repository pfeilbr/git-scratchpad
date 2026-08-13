"""`gsuite gmail` — search, read, threads, attachments, send, reply,
forward, labels, drafts, trash, settings (vacation, signature, filters),
batch label edits."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
from email.message import EmailMessage

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, Group, arg, max_flag, register_service
from gsuite.errors import CLIError
from gsuite.output import confirm, emit, emit_obj

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

COMPOSE_ARGS = (arg("--to", required=True), arg("--subject", default=""),
                arg("--body", default=""), arg("--cc"), arg("--bcc"),
                arg("--attach", action="append", metavar="FILE",
                    help="attach a file (repeatable)"))


def _b64u_bytes(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


def _b64u_decode(data: str) -> str:
    return _b64u_bytes(data).decode(errors="replace")


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
                bcc: str | None = None, extra_headers: dict | None = None,
                attachments: list[str] | None = None) -> str:
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
    for path in attachments or []:
        ctype, _ = mimetypes.guess_type(path)
        maintype, _, subtype = (ctype or "application/octet-stream").partition("/")
        with open(path, "rb") as fh:
            msg.add_attachment(fh.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(path))
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


def cmd_thread(args) -> int:
    client = Client.for_args(args)
    thread = client.get(f"{BASE}/threads/{args.id}", params={"format": "full"})
    if getattr(args, "json", False):
        print(json.dumps(thread, indent=2, sort_keys=True))
        return 0
    blocks = []
    for message in thread.get("messages", []):
        headers = _headers(message)
        blocks.append("\n".join([
            f"from: {headers.get('from', '')}",
            f"date: {headers.get('date', '')}",
            f"subject: {headers.get('subject', '')}",
            "",
            _plain_body(message.get("payload", {})),
        ]))
    print("\n\n".join(blocks))
    return 0


def _attachment_parts(payload: dict):
    """Depth-first walk yielding parts that are downloadable attachments."""
    if payload.get("filename") and payload.get("body", {}).get("attachmentId"):
        yield payload
    for part in payload.get("parts", []):
        yield from _attachment_parts(part)


def cmd_attachments(args) -> int:
    client = Client.for_args(args)
    message = client.get(f"{BASE}/messages/{args.id}", params={"format": "full"})
    parts = list(_attachment_parts(message.get("payload", {})))
    if not args.output:
        emit(args, [{"filename": p.get("filename", ""),
                     "mime": p.get("mimeType", ""),
                     "size": p.get("body", {}).get("size", "")} for p in parts],
             [("FILENAME", "filename"), ("MIME", "mime"), ("SIZE", "size")])
        return 0
    os.makedirs(args.output, exist_ok=True)
    for part in parts:
        att_id = part["body"]["attachmentId"]
        att = client.get(f"{BASE}/messages/{args.id}/attachments/{att_id}")
        data = _b64u_bytes(att.get("data", ""))
        path = os.path.join(args.output, os.path.basename(part["filename"]))
        with open(path, "wb") as fh:
            fh.write(data)
        print(f"wrote {len(data)} bytes to {path}")
    return 0


def _send(client: Client, raw: str, thread_id: str | None = None) -> dict:
    body: dict = {"raw": raw}
    if thread_id:
        body["threadId"] = thread_id
    sent = client.post(f"{BASE}/messages/send", json_body=body)
    confirm("sent", sent.get("id"))
    return sent


def cmd_send(args) -> int:
    raw = _build_mime(args.to, args.subject, args.body, cc=args.cc,
                      bcc=args.bcc, attachments=args.attach)
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
    raw = _build_mime(args.to, args.subject, args.body, cc=args.cc,
                      bcc=args.bcc, attachments=args.attach)
    draft = Client.for_args(args).post(f"{BASE}/drafts",
                                       json_body={"message": {"raw": raw}})
    confirm("draft", draft.get("id"))
    return 0


def cmd_vacation_show(args) -> int:
    settings = Client.for_args(args).get(f"{BASE}/settings/vacation")
    emit_obj(args, {
        "enabled": settings.get("enableAutoReply", False),
        "subject": settings.get("responseSubject", ""),
        "body": settings.get("responseBodyPlainText", ""),
    })
    return 0


def cmd_vacation_set(args) -> int:
    Client.for_args(args).put(f"{BASE}/settings/vacation", json_body={
        "enableAutoReply": True,
        "responseSubject": args.subject,
        "responseBodyPlainText": args.body,
    })
    confirm("vacation responder enabled")
    return 0


def cmd_vacation_off(args) -> int:
    Client.for_args(args).put(f"{BASE}/settings/vacation",
                              json_body={"enableAutoReply": False})
    confirm("vacation responder disabled")
    return 0


def _send_as_entry(client: Client, email: str | None) -> dict:
    """The send-as entry for `email`, or the primary one when no email given."""
    entries = client.get(f"{BASE}/settings/sendAs").get("sendAs", [])
    for entry in entries:
        wanted = (entry.get("sendAsEmail") == email if email
                  else entry.get("isPrimary"))
        if wanted:
            return entry
    raise CLIError(f"no such send-as address: {email}" if email
                   else "no primary send-as address")


def cmd_signature_show(args) -> int:
    entry = _send_as_entry(Client.for_args(args), args.send_as)
    print(entry.get("signature", ""))
    return 0


def cmd_signature_set(args) -> int:
    client = Client.for_args(args)
    email = _send_as_entry(client, args.send_as)["sendAsEmail"]
    client.patch(f"{BASE}/settings/sendAs/{quote_id(email)}",
                 json_body={"signature": args.html})
    confirm("signature updated for", email)
    return 0


def cmd_filters_list(args) -> int:
    filters = Client.for_args(args).get(f"{BASE}/settings/filters").get("filter", [])
    emit(args, filters, [
        ("ID", "id"),
        ("FROM", lambda f: f.get("criteria", {}).get("from", "")),
        ("QUERY", lambda f: f.get("criteria", {}).get("query", "")),
        ("ADD", lambda f: ",".join(f.get("action", {}).get("addLabelIds", []))),
        ("REMOVE", lambda f: ",".join(f.get("action", {}).get("removeLabelIds", []))),
    ])
    return 0


def cmd_filters_create(args) -> int:
    sender = getattr(args, "from")
    if not sender and not args.query:
        raise CLIError("give at least one criterion: --from or --query")
    if not args.add_label and not args.delete:
        raise CLIError("give an action: --add-label or --delete")
    criteria = {}
    if sender:
        criteria["from"] = sender
    if args.query:
        criteria["query"] = args.query
    client = Client.for_args(args)
    action = {"addLabelIds": [_label_id(client, args.add_label)
                              if args.add_label else "TRASH"]}
    created = client.post(f"{BASE}/settings/filters",
                          json_body={"criteria": criteria, "action": action})
    confirm("created", created.get("id"))
    return 0


def cmd_filters_rm(args) -> int:
    Client.for_args(args).delete(f"{BASE}/settings/filters/{args.id}")
    confirm("deleted", args.id)
    return 0


def cmd_batch_modify(args) -> int:
    if not args.add_label and not args.remove_label:
        raise CLIError("give --add-label and/or --remove-label")
    client = Client.for_args(args)
    ids = [ref["id"] for ref in client.paged(f"{BASE}/messages",
                                             params={"q": args.query},
                                             key="messages", limit=args.max)]
    if not ids:
        print("no messages matched")
        return 0
    body: dict = {"ids": ids}
    if args.add_label:
        body["addLabelIds"] = [_label_id(client, args.add_label)]
    if args.remove_label:
        body["removeLabelIds"] = [_label_id(client, args.remove_label)]
    client.post(f"{BASE}/messages/batchModify", json_body=body)
    confirm("modified", len(ids), "message(s)")
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "gmail", "search, read, send, labels, drafts", [
        Cmd("search", cmd_search, "search messages (Gmail query syntax)",
            (arg("query"), max_flag(20))),
        Cmd("get", cmd_get, "read a message (plain-text body)", (arg("id"),)),
        Cmd("thread", cmd_thread, "read a whole thread (every message)",
            (arg("id"),)),
        Cmd("attachments", cmd_attachments, "list or download attachments",
            (arg("id"),
             arg("-o", "--output", metavar="DIR",
                 help="download attachments into this directory"))),
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
        Group("vacation", "auto-reply (vacation responder) settings", (
            Cmd("show", cmd_vacation_show),
            Cmd("set", cmd_vacation_set,
                args=(arg("--subject", required=True),
                      arg("--body", required=True))),
            Cmd("off", cmd_vacation_off),
        )),
        Group("signature", "send-as signatures", (
            Cmd("show", cmd_signature_show,
                args=(arg("--send-as", metavar="EMAIL",
                          help="send-as address (default: primary)"),)),
            Cmd("set", cmd_signature_set,
                args=(arg("--html", required=True),
                      arg("--send-as", metavar="EMAIL",
                          help="send-as address (default: primary)"))),
        )),
        Group("filters", "manage filters", (
            Cmd("list", cmd_filters_list),
            Cmd("create", cmd_filters_create,
                args=(arg("--from", help="match sender"),
                      arg("--query", help="match a Gmail search query"),
                      arg("--add-label", metavar="NAME",
                          help="apply this label to matches"),
                      arg("--delete", action="store_true",
                          help="send matches to trash"))),
            Cmd("rm", cmd_filters_rm, args=(arg("id"),)),
        )),
        Cmd("batch-modify", cmd_batch_modify,
            "add/remove a label across all query matches",
            (arg("--query", required=True),
             arg("--add-label", metavar="NAME"),
             arg("--remove-label", metavar="NAME"), max_flag(500))),
    ])
