"""`gsuite tasks` — lists, list, add, done, rm."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.output import confirm
from gsuite.services._common import emit_paged

BASE = "https://tasks.googleapis.com/tasks/v1"

LIST_FLAG = arg("--list", default="@default",
                help="task list id (default: @default)")


def cmd_lists(args) -> int:
    emit_paged(args, f"{BASE}/users/@me/lists",
               [("ID", "id"), ("TITLE", "title")])
    return 0


def cmd_list(args) -> int:
    emit_paged(args, f"{BASE}/lists/{args.list}/tasks",
               [("ID", "id"), ("STATUS", "status"), ("DUE", "due"),
                ("TITLE", "title")],
               params={"showCompleted": "true" if args.all else "false"},
               limit=args.max)
    return 0


def cmd_add(args) -> int:
    body: dict = {"title": args.title}
    if args.due:
        body["due"] = args.due if "T" in args.due else f"{args.due}T00:00:00Z"
    if args.notes:
        body["notes"] = args.notes
    task = Client.for_args(args).post(f"{BASE}/lists/{args.list}/tasks",
                                      json_body=body)
    confirm("added", task.get("id"), task.get("title"))
    return 0


def cmd_done(args) -> int:
    Client.for_args(args).patch(f"{BASE}/lists/{args.list}/tasks/{args.id}",
                                json_body={"status": "completed"})
    confirm("completed", args.id)
    return 0


def cmd_rm(args) -> int:
    Client.for_args(args).delete(f"{BASE}/lists/{args.list}/tasks/{args.id}")
    confirm("deleted", args.id)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "tasks", "task lists and tasks", [
        Cmd("lists", cmd_lists, "list task lists"),
        Cmd("list", cmd_list, "list tasks",
            (LIST_FLAG, arg("--all", action="store_true",
                            help="include completed"), max_flag(100))),
        Cmd("add", cmd_add, "add a task",
            (arg("title"), LIST_FLAG, arg("--due", help="YYYY-MM-DD or RFC3339"),
             arg("--notes"))),
        Cmd("done", cmd_done, "mark a task completed", (arg("id"), LIST_FLAG)),
        Cmd("rm", cmd_rm, "delete a task", (arg("id"), LIST_FLAG)),
    ])
