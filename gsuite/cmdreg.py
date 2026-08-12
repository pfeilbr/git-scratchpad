"""Declarative command registration — one table per service, zero argparse
boilerplate in service modules.

A service describes its surface as a list of Cmd / Group entries;
register_service() turns that into the argparse tree:

    def register(subparsers):
        register_service(subparsers, "tasks", "task lists and tasks", [
            Cmd("lists", cmd_lists, "list task lists"),
            Cmd("add", cmd_add, "add a task", (arg("title"), LIST_FLAG)),
            Group("labels", "manage labels", (Cmd("list", cmd_labels_list),)),
        ])
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


def arg(*flags: str, **kwargs) -> tuple:
    """One add_argument() call, as data."""
    return (flags, kwargs)


def max_flag(default: int) -> tuple:
    return arg("--max", type=int, default=default,
               help=f"maximum results (default: {default})")


@dataclass(frozen=True)
class Cmd:
    name: str
    func: Callable
    help: str = ""
    args: Sequence[tuple] = ()


@dataclass(frozen=True)
class Group:
    """A nested command group (e.g. `gmail labels <command>`)."""
    name: str
    help: str = ""
    commands: Sequence[Cmd] = ()


def _add_cmd(subparsers, cmd: Cmd) -> None:
    parser = subparsers.add_parser(cmd.name, help=cmd.help)
    for flags, kwargs in cmd.args:
        parser.add_argument(*flags, **kwargs)
    parser.set_defaults(func=cmd.func)


def register_service(subparsers, name: str, help_text: str,
                     entries: Sequence[Cmd | Group]):
    parser = subparsers.add_parser(name, help=help_text)
    sub = parser.add_subparsers(dest="subcommand", metavar="<command>")
    for entry in entries:
        if isinstance(entry, Group):
            group_parser = sub.add_parser(entry.name, help=entry.help)
            group_sub = group_parser.add_subparsers(
                dest=f"{entry.name.replace('-', '_')}_command",
                metavar="<command>")
            for cmd in entry.commands:
                _add_cmd(group_sub, cmd)
        else:
            _add_cmd(sub, entry)
    return parser
