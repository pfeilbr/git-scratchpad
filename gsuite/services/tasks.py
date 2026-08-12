"""`gsuite tasks` — lists, list, add, done, rm."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.output import emit

BASE = "https://tasks.googleapis.com/tasks/v1"


def cmd_lists(args) -> int:
    lists = Client.for_args(args).paged(f"{BASE}/users/@me/lists")
    emit(args, list(lists), [("ID", "id"), ("TITLE", "title")])
    return 0


def cmd_list(args) -> int:
    tasks = Client.for_args(args).paged(
        f"{BASE}/lists/{args.list}/tasks",
        params={"showCompleted": "true" if args.all else "false"},
        limit=args.max)
    emit(args, list(tasks), [("ID", "id"), ("STATUS", "status"),
                             ("DUE", "due"), ("TITLE", "title")])
    return 0


def cmd_add(args) -> int:
    body: dict = {"title": args.title}
    if args.due:
        body["due"] = args.due if "T" in args.due else f"{args.due}T00:00:00Z"
    if args.notes:
        body["notes"] = args.notes
    task = Client.for_args(args).post(f"{BASE}/lists/{args.list}/tasks",
                                      json_body=body)
    print(f"added {task.get('id', '')} {task.get('title', '')}".strip())
    return 0


def cmd_done(args) -> int:
    Client.for_args(args).patch(f"{BASE}/lists/{args.list}/tasks/{args.id}",
                                json_body={"status": "completed"})
    print(f"completed {args.id}")
    return 0


def cmd_rm(args) -> int:
    Client.for_args(args).delete(f"{BASE}/lists/{args.list}/tasks/{args.id}")
    print(f"deleted {args.id}")
    return 0


def _add_list_flag(parser) -> None:
    parser.add_argument("--list", default="@default",
                        help="task list id (default: @default)")


def register(subparsers) -> None:
    p = subparsers.add_parser("tasks", help="task lists and tasks")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    sub.add_parser("lists", help="list task lists").set_defaults(func=cmd_lists)

    lst = sub.add_parser("list", help="list tasks")
    _add_list_flag(lst)
    lst.add_argument("--all", action="store_true", help="include completed")
    lst.add_argument("--max", type=int, default=100)
    lst.set_defaults(func=cmd_list)

    add = sub.add_parser("add", help="add a task")
    add.add_argument("title")
    _add_list_flag(add)
    add.add_argument("--due", help="YYYY-MM-DD or RFC3339")
    add.add_argument("--notes")
    add.set_defaults(func=cmd_add)

    done = sub.add_parser("done", help="mark a task completed")
    done.add_argument("id")
    _add_list_flag(done)
    done.set_defaults(func=cmd_done)

    rm = sub.add_parser("rm", help="delete a task")
    rm.add_argument("id")
    _add_list_flag(rm)
    rm.set_defaults(func=cmd_rm)
