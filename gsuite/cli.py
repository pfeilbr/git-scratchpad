"""Root argument parser and dispatch for the gsuite CLI."""
from __future__ import annotations

import argparse
import importlib
import sys

from gsuite import __version__
from gsuite.errors import CLIError

# Service modules register their own subcommands. Appended to as the CLI
# grows service by service (red-green, one increment per service).
SERVICE_MODULES: list[str] = ["auth", "gmail", "calendar", "drive", "docs",
                              "sheets", "slides", "contacts", "tasks",
                              "chat", "keep", "admin", "forms", "meet", "api"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gsuite",
        description="Unified Google Workspace CLI (gws + gog command surfaces).",
    )
    parser.add_argument(
        "--version", action="version", version=f"gsuite {__version__}"
    )
    parser.add_argument(
        "-a", "--account",
        help="account email or alias to act as (default: the default account)",
    )
    parser.add_argument(
        "--json", action="store_true", help="machine-readable JSON output"
    )
    parser.add_argument(
        "--readonly", action="store_true",
        help="refuse any request that could modify data (only GET is allowed)",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<service>")
    for name in SERVICE_MODULES:
        module = importlib.import_module(f"gsuite.services.{name}")
        module.register(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help(sys.stderr)
        return 2
    try:
        return func(args) or 0
    except CLIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()
