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


def cmd_create_space(args) -> int:
    space = Client.for_args(args).post(
        f"{BASE}/spaces",
        json_body={"displayName": args.name, "spaceType": args.type})
    confirm("created", space.get("name"))
    return 0


def cmd_members(args) -> int:
    emit_paged(args, f"{BASE}/{args.space}/members",
               [("NAME", "name"),
                ("MEMBER", lambda m: m.get("member", {}).get("name", "")),
                ("TYPE", lambda m: m.get("member", {}).get("type", "")),
                ("ROLE", "role")],
               key="memberships")
    return 0


def cmd_add_member(args) -> int:
    user = args.user if args.user.startswith("users/") else f"users/{args.user}"
    Client.for_args(args).post(
        f"{BASE}/{args.space}/members",
        json_body={"member": {"name": user, "type": "HUMAN"}})
    confirm("added", user, "to", args.space)
    return 0


def cmd_reply(args) -> int:
    message = Client.for_args(args).post(
        f"{BASE}/{args.space}/messages",
        params={"messageReplyOption": "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"},
        json_body={"text": args.text, "thread": {"name": args.thread}})
    confirm("sent", message.get("name"))
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "chat", "Google Chat spaces and messages", [
        Cmd("spaces", cmd_spaces, "list spaces"),
        Cmd("create-space", cmd_create_space, "create a space",
            (arg("--name", required=True, help="display name"),
             arg("--type", default="SPACE", choices=["SPACE", "GROUP_CHAT"]))),
        Cmd("members", cmd_members, "list members of a space",
            (arg("space", help="e.g. spaces/AAAA"),)),
        Cmd("add-member", cmd_add_member, "add a user to a space",
            (arg("space"), arg("user", help="user id or users/<id>"))),
        Cmd("messages", cmd_messages, "list messages in a space",
            (arg("space", help="e.g. spaces/AAAA"), max_flag(50))),
        Cmd("send", cmd_send, "send a text message to a space",
            (arg("space"), arg("--text", required=True))),
        Cmd("reply", cmd_reply, "reply in a message thread",
            (arg("space"), arg("--thread", required=True,
                               help="e.g. spaces/AAAA/threads/TTTT"),
             arg("--text", required=True))),
    ])
