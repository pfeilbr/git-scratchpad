#!/usr/bin/env python3
"""Drive every command with hostile input; fail on any traceback.

A CLI has one universal contract: whatever the user types, they get a
message and an exit code — never a Python traceback. This project has broken
that contract six times in ways no unit test caught (a closed pipe, a DNS
failure, a non-JSON reply, a corrupt config file, an odd line separator in a
mail header, a missing --attach file), each found by hand. This script looks
for the next one automatically.

It walks the real parser tree, synthesises an invocation for every leaf
command, and runs each one in-process against a stubbed transport, so it is
offline and makes no Google calls. Deterministic: a fixed list of hostile
values, no randomness, same result every run.

  python3 scripts/fuzz_cli.py           terse summary, exit 1 on any traceback
  python3 scripts/fuzz_cli.py -v        list every case as it runs
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
import tempfile
import traceback

os.environ["COLUMNS"] = "80"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import gsuite.transport as transport_mod  # noqa: E402
from gsuite import oauth  # noqa: E402
from gsuite.cli import build_parser  # noqa: E402

# Values chosen to poke at the failure modes that have actually bitten:
# path traversal, URL punctuation, line breaks in headers, empty strings,
# non-ASCII, and filesystem paths that do not exist.
HOSTILE_VALUES = [
    "x",                        # the benign control
    "",                         # empty
    "../../../etc/passwd",      # traversal
    "a?b#c&d=e",                # URL punctuation
    "line\nbreak",              # header injection shape
    "\x0bvertical",             # the separator `email` splits on
    "'quote\\backslash",        # query-literal escaping
    "会議 🍜",                   # non-ASCII, wide, emoji
    "/nonexistent/path.bin",    # a file that is not there
    "-",                        # stdin sentinel / option-lookalike
]

# Canned replies, so a command gets far enough to exercise its own parsing.
RESPONSES = [
    (200, b'{"id": "x", "items": [], "files": [], "messages": []}'),
    (200, b"not json at all"),
    (404, b'{"error": {"message": "not found", "code": 404}}'),
    (200, b""),
]


def _sub(parser):
    return next((a for a in parser._actions
                 if isinstance(a, argparse._SubParsersAction)), None)


def leaf_commands(parser, prefix=()):
    """Every runnable command as a tuple of path words."""
    sub = _sub(parser)
    if sub is None:
        yield prefix, parser
        return
    for name, child in sub.choices.items():
        yield from leaf_commands(child, prefix + (name,))


def invocations(path, parser, value):
    """One argv for this command, filling every argument with `value`."""
    argv = list(path)
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._VersionAction,
                               argparse._SubParsersAction)):
            continue
        if action.option_strings:
            if not action.required:
                continue
            argv.append(action.option_strings[-1])
            if action.nargs != 0:
                argv.append(_fit(action, value))
        elif action.nargs not in ("?", "*"):
            argv.append(_fit(action, value))
    return argv


def _fit(action, value):
    """Respect `choices`, so argparse's own validation is not what we test."""
    if action.choices:
        return str(next(iter(action.choices)))
    return value


def _capture():
    """A stdout stand-in that behaves like the real one.

    `io.StringIO` has no `.buffer`, but a real process's stdout does, and
    `drive download` writes binary through it. Capturing with a plain
    StringIO reported an AttributeError that no user could ever hit — a
    finding about the harness, not the tool. Wrapping a BytesIO gives a
    text stream with a working `.buffer`, so the capture is faithful.
    """
    return io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="replace")


def run_case(argv, response):
    """Run one invocation; return a traceback string, or "" if well-behaved."""
    status, body = response
    transport_mod.request = lambda *a, **k: (status, {}, body)
    # Never open a browser or bind a port for `auth login`.
    oauth.loopback_authorizer = lambda client, scopes: ("code", "http://x/")
    out, err = _capture(), _capture()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            from gsuite.cli import main
            main(argv)
    except SystemExit:
        pass
    except BaseException:  # noqa: BLE001 — the whole point is to catch these
        return traceback.format_exc()
    return ""


def main() -> int:
    verbose = "-v" in sys.argv[1:]
    parser = build_parser()
    # Sandbox everything a command might touch on disk.
    home = tempfile.mkdtemp(prefix="gsuite-fuzz-")
    os.environ.update({"HOME": home,
                       "GSUITE_CONFIG_DIR": os.path.join(home, "config"),
                       "GSUITE_ACCESS_TOKEN": "fuzz-token",
                       "GOOGLE_APPLICATION_CREDENTIALS": home + "/none.json"})

    failures, cases = [], 0
    for path, leaf in leaf_commands(parser):
        for value in HOSTILE_VALUES:
            argv = invocations(path, leaf, value)
            for response in RESPONSES:
                cases += 1
                tb = run_case(list(argv), response)
                if verbose:
                    print(f"  {'!!' if tb else 'ok'} {' '.join(argv)}")
                if tb:
                    failures.append((argv, response[0], tb))
                    break  # one report per invocation is enough

    for argv, status, tb in failures[:10]:
        print(f"TRACEBACK: gsuite {' '.join(argv)}   (HTTP {status})")
        print("   " + tb.strip().splitlines()[-1])
    if failures:
        print(f"FUZZ FAIL: {len(failures)} of {cases} cases raised")
        return 1
    print(f"FUZZ OK: {cases} cases, no tracebacks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
