"""`gsuite chat` — spaces, messages, send."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.output import confirm
from gsuite.services._common import emit_paged

BASE = "https://chat.googleapis.com/v1"


def cmd_spaces(args) -> int:
    emit_paged(args, f"{BASE}/spaces",
               [("NAME", "name"), ("DISPLAY", "displayName"),
                ("TYPE", "spaceType")], key="spaces")
    return 0


def cmd_messages(args) -> int:
    emit_paged(args, f"{BASE}/{args.space}/messages",
               [("NAME", "name"), ("TIME", "createTime"),
                ("SENDER", lambda m: m.get("sender", {}).get("name", "")),
                ("TEXT", "text")],
               key="messages", limit=args.max)
    return 0


def cmd_send(args) -> int:
    message = Client.for_args(args).post(f"{BASE}/{args.space}/messages",
                                         json_body={"text": args.text})
    confirm("sent", message.get("name"))
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "chat", "Google Chat spaces and messages", [
        Cmd("spaces", cmd_spaces, "list spaces"),
        Cmd("messages", cmd_messages, "list messages in a space",
            (arg("space", help="e.g. spaces/AAAA"), max_flag(50))),
        Cmd("send", cmd_send, "send a text message to a space",
            (arg("space"), arg("--text", required=True))),
    ])
