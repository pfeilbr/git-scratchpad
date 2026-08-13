"""`gsuite tasks` — lists, list, add, update, move, done, rm."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.errors import CLIError
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


def cmd_update(args) -> int:
    body: dict = {}
    if args.title is not None:
        body["title"] = args.title
    if args.notes is not None:
        body["notes"] = args.notes
    if args.due is not None:
        body["due"] = args.due if "T" in args.due else f"{args.due}T00:00:00Z"
    if not body:
        raise CLIError("nothing to update (pass --title, --notes, or --due)")
    Client.for_args(args).patch(f"{BASE}/lists/{args.list}/tasks/{args.id}",
                                json_body=body)
    confirm("updated", args.id)
    return 0


def cmd_move(args) -> int:
    params: dict = {}
    if args.after:
        params["previous"] = args.after
    if args.parent:
        params["parent"] = args.parent
    Client.for_args(args).post(f"{BASE}/lists/{args.list}/tasks/{args.id}/move",
                               params=params or None)
    confirm("moved", args.id)
    return 0


def cmd_clear_completed(args) -> int:
    Client.for_args(args).post(f"{BASE}/lists/{args.list}/clear")
    confirm("cleared completed tasks in", args.list)
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
        Cmd("update", cmd_update, "update a task's fields",
            (arg("id"), LIST_FLAG, arg("--title"), arg("--notes"),
             arg("--due", help="YYYY-MM-DD or RFC3339"))),
        Cmd("move", cmd_move, "reorder or re-parent a task",
            (arg("id"), LIST_FLAG,
             arg("--after", help="place after this task id"),
             arg("--parent", help="make a subtask of this task id"))),
        Cmd("done", cmd_done, "mark a task completed", (arg("id"), LIST_FLAG)),
        Cmd("rm", cmd_rm, "delete a task", (arg("id"), LIST_FLAG)),
        Cmd("clear-completed", cmd_clear_completed,
            "remove completed tasks from a list", (LIST_FLAG,)),
    ])
