"""Root argument parser and dispatch for the gsuite CLI."""
from __future__ import annotations

import argparse
import importlib
import math
import os
import sys

import gsuite.transport
from gsuite import __version__
from gsuite.errors import CLIError
from gsuite.output import check_flags

# Service modules register their own subcommands. Appended to as the CLI
# grows service by service (red-green, one increment per service).
SERVICE_MODULES: list[str] = ["auth", "gmail", "calendar", "drive", "docs",
                              "sheets", "slides", "contacts", "tasks",
                              "chat", "keep", "admin", "forms", "meet",
                              "searchconsole", "analytics",
                              "classroom", "workflow", "api", "completion"]

TIMEOUT_ENV = "GSUITE_TIMEOUT"


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
    parser.add_argument(
        "--csv", action="store_true",
        help="CSV output with a header row (not with --json)",
    )
    parser.add_argument(
        "--fields", metavar="A,B",
        help="restrict output to these columns, in this order",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="trace HTTP requests and response statuses on stderr",
    )
    parser.add_argument(
        "--timeout", metavar="SECONDS",
        help="seconds to wait on each HTTP request "
             f"(default: {gsuite.transport.DEFAULT_TIMEOUT:g}, "
             f"or ${TIMEOUT_ENV})",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<service>")
    for name in SERVICE_MODULES:
        module = importlib.import_module(f"gsuite.services.{name}")
        module.register(subparsers)
    return parser


def _timeout(args) -> float:
    """--timeout, else $GSUITE_TIMEOUT, else the transport default."""
    value, source = getattr(args, "timeout", None), "--timeout"
    if value is None:
        value, source = (os.environ.get(TIMEOUT_ENV) or "").strip(), TIMEOUT_ENV
    if not value:
        return gsuite.transport.DEFAULT_TIMEOUT
    try:
        seconds = float(value)
    except ValueError:
        raise CLIError(f"invalid {source} value: {value} "
                       f"(want seconds, e.g. 30)") from None
    # `inf`/`nan` parse as floats but blow up inside socket.settimeout().
    if not (math.isfinite(seconds) and seconds > 0):
        raise CLIError(f"invalid {source} value: {value} (must be positive)")
    return seconds


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help(sys.stderr)
        return 2
    if getattr(args, "debug", False):
        gsuite.transport.DEBUG = True
    try:
        gsuite.transport.TIMEOUT = _timeout(args)
        check_flags(args)
        return func(args) or 0
    except CLIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:
        # A downstream reader closed the pipe (`gsuite … | head`). Behave
        # like a UNIX filter: point stdout at devnull so the interpreter's
        # exit-time flush cannot raise again, and use the shell's 128+SIGPIPE.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 141


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()
