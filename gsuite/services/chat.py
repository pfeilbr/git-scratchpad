"""`gsuite chat` — spaces, messages, send."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.output import emit

BASE = "https://chat.googleapis.com/v1"


def cmd_spaces(args) -> int:
    spaces = Client.for_args(args).paged(f"{BASE}/spaces", key="spaces")
    emit(args, list(spaces), [("NAME", "name"), ("DISPLAY", "displayName"),
                              ("TYPE", "spaceType")])
    return 0


def cmd_messages(args) -> int:
    messages = Client.for_args(args).paged(
        f"{BASE}/{args.space}/messages", key="messages", limit=args.max)
    emit(args, list(messages),
         [("NAME", "name"), ("TIME", "createTime"),
          ("SENDER", lambda m: m.get("sender", {}).get("name", "")),
          ("TEXT", "text")])
    return 0


def cmd_send(args) -> int:
    message = Client.for_args(args).post(f"{BASE}/{args.space}/messages",
                                         json_body={"text": args.text})
    print(f"sent {message.get('name', '')}".strip())
    return 0


def register(subparsers) -> None:
    p = subparsers.add_parser("chat", help="Google Chat spaces and messages")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    sub.add_parser("spaces", help="list spaces").set_defaults(func=cmd_spaces)

    messages = sub.add_parser("messages", help="list messages in a space")
    messages.add_argument("space", help="e.g. spaces/AAAA")
    messages.add_argument("--max", type=int, default=50)
    messages.set_defaults(func=cmd_messages)

    send = sub.add_parser("send", help="send a text message to a space")
    send.add_argument("space")
    send.add_argument("--text", required=True)
    send.set_defaults(func=cmd_send)
