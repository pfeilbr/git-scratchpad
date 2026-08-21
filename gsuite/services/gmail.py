"""`gsuite gmail` — search, triage, read, threads, attachments, send, reply,
reply-all, forward, labels, drafts, trash, settings (vacation, signature,
filters, send-as, delegates, forwarding), batch label edits."""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from email.message import EmailMessage
from email.utils import formataddr, getaddresses
from typing import Sequence

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, Group, _add_cmd, arg, max_flag, register_service
from gsuite.errors import CLIError
from gsuite.output import confirm, emit, emit_obj
from gsuite.services._common import make_dir, read_file, write_file

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# The settings collections, named once because several commands share each.
SENDAS = f"{BASE}/settings/sendAs"

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


def _header(label: str, value: str) -> str:
    """Return `value` if it is safe to store in a header, else raise.

    A line break in a header value is header injection: it can smuggle extra
    headers (a hidden `Bcc:`) or end the header block early. `email` refuses
    most of these itself, but with a bare ValueError (a traceback, not a
    CLI error) and it lets a *trailing* CR/LF through, which is then silently
    RFC 2047-encoded into a corrupt address. Reject both, naming the source.

    The test is `splitlines()` rather than a CR/LF scan because that is the
    same rule `email` applies: it also splits on the vertical tab, form feed,
    NEL and the Unicode line/paragraph separators, each of which otherwise
    reached the library and raised. An empty value is fine — an empty subject
    is ordinary — and only headers are checked: newlines in a body are normal.
    """
    if value and value.splitlines() != [value]:
        raise CLIError(f"{label} may not contain a line break")
    return value


def _build_mime(to: str, subject: str, body: str, cc: str | None = None,
                bcc: str | None = None, extra_headers: dict | None = None,
                attachments: list[str] | None = None) -> str:
    msg = EmailMessage()
    msg["To"] = _header("--to", to)
    if cc:
        msg["Cc"] = _header("--cc", cc)
    if bcc:
        msg["Bcc"] = _header("--bcc", bcc)
    msg["Subject"] = _header("--subject", subject)
    # Values copied off a fetched message are untrusted too (a hostile
    # Message-ID on received mail lands here via `reply`).
    for name, value in (extra_headers or {}).items():
        msg[name] = _header(name, value)
    msg.set_content(body)
    for path in attachments or []:
        ctype, _ = mimetypes.guess_type(path)
        maintype, _, subtype = (ctype or "application/octet-stream").partition("/")
        msg.add_attachment(read_file(path), maintype=maintype,
                           subtype=subtype,
                           filename=os.path.basename(path))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


# `format=metadata` returns *only* the headers named here, so a header left
# off this list reads as absent on every real message — which is how `reply`
# came to prefer a Reply-To it never asked for. Cc and Reply-To earn their
# place: `reply-all` addresses from them and `reply` prefers Reply-To.
META_HEADERS = ["From", "To", "Cc", "Reply-To", "Subject", "Date", "Message-ID"]

# What `triage` means by "needs attention": unread, and still in the inbox.
TRIAGE_QUERY = "is:unread in:inbox"


def _fetch_meta(client: Client, msg_id: str) -> dict:
    return client.get(f"{BASE}/messages/{quote_id(msg_id)}", params={
        "format": "metadata",
        "metadataHeaders": META_HEADERS,
    })


def _summaries(client: Client, query: str, limit: int) -> list[dict]:
    """Search, then fetch each hit's headers: one row per matching message.

    A search response carries ids and nothing else, so every listing that
    shows who a message is from costs one round trip per hit. Both listings
    that do (`search`, `triage`) differ only in the query they start from.
    """
    rows = []
    for ref in client.paged(f"{BASE}/messages", params={"q": query},
                            key="messages", limit=limit):
        message = _fetch_meta(client, ref["id"])
        headers = _headers(message)
        rows.append({"id": message["id"], "date": headers.get("date", ""),
                     "from": headers.get("from", ""),
                     "subject": headers.get("subject", ""),
                     "snippet": message.get("snippet", "")})
    return rows


def cmd_search(args) -> int:
    rows = _summaries(Client.for_args(args), args.query, args.max)
    emit(args, rows, [("ID", "id"), ("DATE", "date"), ("FROM", "from"),
                      ("SUBJECT", "subject")])
    return 0


def cmd_triage(args) -> int:
    rows = _summaries(Client.for_args(args), TRIAGE_QUERY, args.max)
    # Sender and subject lead — triage is read left to right, deciding per
    # row — but the id still comes first, because the whole point of the
    # listing is to feed the id to the command that deals with the message.
    emit(args, rows, [("ID", "id"), ("FROM", "from"), ("SUBJECT", "subject"),
                      ("DATE", "date")])
    return 0


def cmd_get(args) -> int:
    client = Client.for_args(args)
    message = client.get(f"{BASE}/messages/{quote_id(args.id)}", params={"format": "full"})
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
    thread = client.get(f"{BASE}/threads/{quote_id(args.id)}", params={"format": "full"})
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
    message = client.get(f"{BASE}/messages/{quote_id(args.id)}", params={"format": "full"})
    parts = list(_attachment_parts(message.get("payload", {})))
    if not args.output:
        emit(args, [{"filename": p.get("filename", ""),
                     "mime": p.get("mimeType", ""),
                     "size": p.get("body", {}).get("size", "")} for p in parts],
             [("FILENAME", "filename"), ("MIME", "mime"), ("SIZE", "size")])
        return 0
    make_dir(args.output)
    for part in parts:
        att_id = part["body"]["attachmentId"]
        att = client.get(f"{BASE}/messages/{quote_id(args.id)}/attachments/{quote_id(att_id)}")
        data = _b64u_bytes(att.get("data", ""))
        path = os.path.join(args.output, os.path.basename(part["filename"]))
        write_file(path, data)
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


def _addresses(label: str, raw: str) -> list[tuple[str, str]]:
    """One recipient header as (display name, address) pairs.

    The value is checked with `_header` *before* it is parsed, not after:
    `getaddresses` treats a smuggled `\\nBcc:` differently depending on the
    Python patch level — older ones hand the smuggled header back as one
    more address, newer ones return nothing at all — so leaving the check
    until afterwards would either forward the injection or silently reply
    to no one. Both are worse than saying which header is malformed.
    """
    _header(label, raw)
    return [(name, addr) for name, addr in getaddresses([raw]) if addr]


def _reply_all_recipients(headers: dict, me: str) -> tuple[str, str]:
    """(To, Cc) for a reply to everyone still worth replying to.

    Reply-all is the sender plus everyone they addressed, minus you: mail
    you sent yourself a copy of should not land in your own inbox again.
    Addresses are compared case-insensitively (the local part is officially
    case-sensitive, but no mail provider treats it that way) and each one is
    kept only the first time it appears, since the sender is usually on the
    To line too and nobody wants two copies.
    """
    seen = {me.lower()} if me else set()

    def pick(label: str, raw: str) -> str:
        kept = []
        for name, address in _addresses(label, raw):
            if address.lower() in seen:
                continue
            seen.add(address.lower())
            kept.append(formataddr((name, address)))
        return ", ".join(kept)

    sender = ("Reply-To", headers["reply-to"]) if headers.get("reply-to") \
        else ("From", headers.get("from", ""))
    to = ", ".join(part for part in (pick(*sender),
                                     pick("To", headers.get("to", "")))
                   if part)
    return to, pick("Cc", headers.get("cc", ""))


def _reply(args, *, to_all: bool) -> int:
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
    cc = None
    if to_all:
        to, cc = _reply_all_recipients(headers, client.email)
        if not to:
            raise CLIError(f"no one to reply to on {args.id}: "
                           "you are the only participant")
    else:
        to = headers.get("reply-to") or headers.get("from", "")
    raw = _build_mime(to, subject, args.body, cc=cc, extra_headers=extra)
    _send(client, raw, thread_id=original.get("threadId"))
    return 0


def cmd_reply(args) -> int:
    return _reply(args, to_all=False)


def cmd_reply_all(args) -> int:
    return _reply(args, to_all=True)


def cmd_forward(args) -> int:
    client = Client.for_args(args)
    original = client.get(f"{BASE}/messages/{quote_id(args.id)}", params={"format": "full"})
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
    Client.for_args(args).post(f"{BASE}/messages/{quote_id(args.id)}/trash")
    confirm("trashed", args.id)
    return 0


def cmd_untrash(args) -> int:
    Client.for_args(args).post(f"{BASE}/messages/{quote_id(args.id)}/untrash")
    confirm("untrashed", args.id)
    return 0


def _system_label_cmd(verb: str, add: Sequence[str] = (),
                      remove: Sequence[str] = ()):
    """Build a handler that flips fixed system labels on one message.

    The triage verbs (archive, read/unread, spam) all differ only in which
    system label ids they add or remove and in how they say so afterwards.
    System ids are literal, so no name lookup is needed.
    """
    def handler(args) -> int:
        body: dict = {}
        if add:
            body["addLabelIds"] = list(add)
        if remove:
            body["removeLabelIds"] = list(remove)
        Client.for_args(args).post(f"{BASE}/messages/{quote_id(args.id)}/modify",
                                   json_body=body)
        confirm(verb, args.id)
        return 0
    return handler


cmd_archive = _system_label_cmd("archived", remove=("INBOX",))
cmd_unarchive = _system_label_cmd("moved to inbox", add=("INBOX",))
cmd_mark_read = _system_label_cmd("marked read", remove=("UNREAD",))
cmd_mark_unread = _system_label_cmd("marked unread", add=("UNREAD",))
cmd_spam = _system_label_cmd("marked spam", add=("SPAM",), remove=("INBOX",))
cmd_unspam = _system_label_cmd("unmarked spam", add=("INBOX",), remove=("SPAM",))


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
    client.post(f"{BASE}/messages/{quote_id(args.id)}/modify",
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
    entries = client.get(SENDAS).get("sendAs", [])
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
    client.patch(f"{SENDAS}/{quote_id(email)}",
                 json_body={"signature": args.html})
    confirm("signature updated for", email)
    return 0


# -- settings: send-as addresses --------------------------------------------
#
# Signatures are deliberately absent from `create` and `update`: `gmail
# signature set` already writes that field, and two commands writing one
# field is how the two of them drift apart. `get` still shows the signature,
# because showing is not owning.

def cmd_sendas_list(args) -> int:
    entries = Client.for_args(args).get(SENDAS).get("sendAs", [])
    emit(args, entries, [
        ("EMAIL", "sendAsEmail"),
        ("NAME", "displayName"),
        ("PRIMARY", lambda e: "yes" if e.get("isPrimary") else ""),
        ("DEFAULT", lambda e: "yes" if e.get("isDefault") else ""),
        # Blank for the primary address, which needs no verifying.
        ("VERIFIED", "verificationStatus"),
    ])
    return 0


def cmd_sendas_get(args) -> int:
    entry = Client.for_args(args).get(f"{SENDAS}/{quote_id(args.email)}")
    emit_obj(args, {
        "email": entry.get("sendAsEmail", ""),
        "name": entry.get("displayName", ""),
        "reply-to": entry.get("replyToAddress", ""),
        "primary": entry.get("isPrimary", False),
        "default": entry.get("isDefault", False),
        "verified": entry.get("verificationStatus", ""),
        "alias": entry.get("treatAsAlias", False),
        "signature": entry.get("signature", ""),
    })
    return 0


def cmd_sendas_create(args) -> int:
    body = {"sendAsEmail": args.email}
    if args.name:
        body["displayName"] = args.name
    if args.reply_to:
        body["replyToAddress"] = args.reply_to
    if args.treat_as_alias:
        body["treatAsAlias"] = True
    created = Client.for_args(args).post(SENDAS, json_body=body)
    # Any address that is not already yours gets a confirmation mail, and
    # cannot send until someone follows the link — so say which it was.
    confirm("created", created.get("sendAsEmail", args.email),
            created.get("verificationStatus", ""))
    return 0


def cmd_sendas_update(args) -> int:
    body: dict = {}
    # `is not None`, not truthiness: `--name ""` asks for the display name to
    # be cleared, which is a change, while omitting --name asks for nothing.
    if args.name is not None:
        body["displayName"] = args.name
    if args.reply_to is not None:
        body["replyToAddress"] = args.reply_to
    if args.default:
        body["isDefault"] = True
    if not body:
        raise CLIError("give at least one field to change: "
                       "--name, --reply-to or --default")
    updated = Client.for_args(args).patch(f"{SENDAS}/{quote_id(args.email)}",
                                          json_body=body)
    confirm("updated", updated.get("sendAsEmail", args.email))
    return 0


def cmd_sendas_delete(args) -> int:
    Client.for_args(args).delete(f"{SENDAS}/{quote_id(args.email)}")
    confirm("deleted send-as", args.email)
    return 0


def cmd_sendas_verify(args) -> int:
    Client.for_args(args).post(f"{SENDAS}/{quote_id(args.email)}/verify")
    confirm("verification email sent to", args.email)
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
    Client.for_args(args).delete(f"{BASE}/settings/filters/{quote_id(args.id)}")
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


def _sub_action(parser) -> argparse._SubParsersAction:
    """The subcommand action argparse hung on `parser`."""
    return next(a for a in parser._actions
                if isinstance(a, argparse._SubParsersAction))


def _add_nested(group_sub, group: Group) -> None:
    """Attach a Group *inside* a group — a third level of commands.

    `register_service` nests exactly one level: a service holds Groups and a
    Group holds Cmds, and handing it a Group inside a Group is an
    AttributeError. The Gmail settings surface is three deep — `gmail
    settings sendas list` — because that is how the API names it, how `gog`
    names it, and how the Gmail UI reads. Flattening it to `settings
    sendas-list` would put this CLI's only compound verb at exactly the
    place a user is most likely to guess the name from upstream, so the
    third level is worth these few lines of argparse.

    cmdreg's own `_add_cmd` builds the leaves rather than a copy of it, so a
    Cmd keeps meaning here exactly what it means everywhere else.
    """
    parser = group_sub.add_parser(group.name, help=group.help)
    sub = parser.add_subparsers(dest=f"{group.name}_command",
                                metavar="<command>")
    for cmd in group.commands:
        _add_cmd(sub, cmd)


# Flags shared by `settings sendas create` and `settings sendas update`.
# `update` defaults them to None so that an empty value can still be told
# apart from an absent one; see cmd_sendas_update.
SENDAS_FIELDS = (arg("--name", metavar="DISPLAY",
                     help="display name on outgoing mail"),
                 arg("--reply-to", metavar="EMAIL",
                     help="address replies should go to"))

SETTINGS_GROUPS = (
    Group("sendas", "send-as addresses", (
        Cmd("list", cmd_sendas_list, "list send-as addresses"),
        Cmd("get", cmd_sendas_get, "show one send-as address",
            (arg("email"),)),
        Cmd("create", cmd_sendas_create, "add a send-as address",
            (arg("email"), *SENDAS_FIELDS,
             arg("--treat-as-alias", action="store_true",
                 help="treat mail to this address as mail to you"))),
        Cmd("update", cmd_sendas_update, "change a send-as address",
            (arg("email"), *SENDAS_FIELDS,
             arg("--default", action="store_true",
                 help="send new mail from this address by default"))),
        Cmd("delete", cmd_sendas_delete, "remove a send-as address",
            (arg("email"),)),
        Cmd("verify", cmd_sendas_verify,
            "send the ownership confirmation mail again", (arg("email"),)),
    )),
)


def register(subparsers) -> None:
    gmail = register_service(subparsers, "gmail",
                             "search, read, send, labels, drafts", [
        Cmd("search", cmd_search, "search messages (Gmail query syntax)",
            (arg("query"), max_flag(20))),
        Cmd("triage", cmd_triage, "summarize unread inbox mail",
            (max_flag(20),)),
        Cmd("get", cmd_get, "read a message (plain-text body)", (arg("id"),)),
        Cmd("thread", cmd_thread, "read a whole thread (every message)",
            (arg("id"),)),
        Cmd("attachments", cmd_attachments, "list or download attachments",
            (arg("id"),
             arg("-o", "--output", metavar="DIR",
                 help="download attachments into this directory"))),
        Cmd("send", cmd_send, "send an email", COMPOSE_ARGS),
        Cmd("reply", cmd_reply, "reply to the sender, on the original thread",
            (arg("id"), arg("--body", required=True))),
        Cmd("reply-all", cmd_reply_all,
            "reply to every participant, on the original thread",
            (arg("id"), arg("--body", required=True))),
        Cmd("forward", cmd_forward, "forward a message",
            (arg("id"), arg("--to", required=True), arg("--body", default=""))),
        Cmd("archive", cmd_archive, "remove a message from the inbox",
            (arg("id"),)),
        Cmd("unarchive", cmd_unarchive, "move a message back to the inbox",
            (arg("id"),)),
        Cmd("mark-read", cmd_mark_read, "mark a message read", (arg("id"),)),
        Cmd("mark-unread", cmd_mark_unread, "mark a message unread",
            (arg("id"),)),
        Cmd("spam", cmd_spam, "mark a message as spam", (arg("id"),)),
        Cmd("unspam", cmd_unspam, "take a message out of spam", (arg("id"),)),
        Cmd("trash", cmd_trash, "move a message to trash", (arg("id"),)),
        Cmd("untrash", cmd_untrash, "restore a message from trash",
            (arg("id"),)),
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
        # Declared empty on purpose: its members are groups themselves, one
        # level deeper than register_service nests. _add_nested fills it in
        # below — and explains why the depth is worth having.
        Group("settings", "mailbox settings: send-as addresses", ()),
        Cmd("batch-modify", cmd_batch_modify,
            "add/remove a label across all query matches",
            (arg("--query", required=True),
             arg("--add-label", metavar="NAME"),
             arg("--remove-label", metavar="NAME"), max_flag(500))),
    ])
    settings = _sub_action(_sub_action(gmail).choices["settings"])
    for group in SETTINGS_GROUPS:
        _add_nested(settings, group)
