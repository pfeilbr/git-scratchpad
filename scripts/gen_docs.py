#!/usr/bin/env python3
"""Generate docs/reference/*.md from the live argparse tree.

The command reference can never drift from the code: pages are rendered
from build_parser() itself, and `--check` (run by scripts/verify.py and
the test suite) fails the build when a page on disk is stale.

  python3 scripts/gen_docs.py          rewrite docs/reference/
  python3 scripts/gen_docs.py --check  exit 1 if any page is stale
"""
from __future__ import annotations

import argparse
import os
import sys

os.environ["COLUMNS"] = "80"  # deterministic argparse usage-line wrapping

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gsuite.cli import SERVICE_MODULES, build_parser  # noqa: E402

REFERENCE_DIR = os.path.join(ROOT, "docs", "reference")

# (title, command, sample output) triples rendered under "## Examples".
EXAMPLES: dict[str, list[tuple[str, str, str]]] = {
    "auth": [
        ("First login (browser opens, email auto-detected)",
         "gsuite auth login --services gmail,calendar,drive",
         "Logged in as you@example.com (services: calendar, drive, gmail)"),
        ("Multiple accounts with aliases",
         "gsuite auth login work@corp.com\n"
         "gsuite auth alias set work work@corp.com\n"
         "gsuite -a work auth status",
         "account: work@corp.com\ntoken: valid"),
        ("Diagnose a broken setup",
         "gsuite auth doctor",
         "OK   OAuth client configured\n"
         "OK   at least one account\n"
         "OK   token usable: you@example.com"),
    ],
    "gmail": [
        ("Find unread mail from a sender",
         "gsuite gmail search 'is:unread from:alice@example.com' --max 5",
         "ID      DATE                    FROM               SUBJECT\n"
         "19ab3f  Mon, 5 Jan 2026 09:14   alice@example.com  Q1 roadmap"),
        ("Send an email",
         'gsuite gmail send --to bob@example.com --subject "Lunch?" '
         '--body "12:30 at the usual spot"',
         "sent 19ab41"),
        ("Reply within the original thread",
         'gsuite gmail reply 19ab3f --body "Sounds good — shipping Friday."',
         "sent 19ab42"),
        ("Label triage",
         "gsuite gmail labels create follow-up\n"
         "gsuite gmail labels apply 19ab3f follow-up",
         "applied follow-up to 19ab3f"),
    ],
    "calendar": [
        ("Today's agenda",
         "gsuite calendar agenda",
         "ID     START                 SUMMARY   LOCATION\n"
         "e1a2   2026-01-05T09:00:00Z  Standup   Zoom"),
        ("Create a timed event with attendees",
         "gsuite calendar create --summary 'Design review' "
         "--start 2026-01-07T14:00 --end 2026-01-07T15:00 "
         "--attendees alice@example.com,bob@example.com",
         "created e9f3 https://www.google.com/calendar/event?eid=..."),
    ],
    "drive": [
        ("List a folder and upload into it",
         "gsuite drive ls\n"
         "gsuite drive upload report.pdf --parent 1AbCdEf",
         "uploaded 1XyZ9 report.pdf"),
        ("Export a Google Doc as PDF",
         "gsuite drive export 1DocId --mime application/pdf -o notes.pdf",
         "wrote 24576 bytes to notes.pdf"),
        ("Audit link-shared files",
         "gsuite drive audit",
         "ID     NAME        TYPE       MODIFIED              SIZE  LINK\n"
         "1XyZ9  budget.xlsx submitted  2026-01-04T12:00:00Z  9812  https://…"),
    ],
    "docs": [
        ("Create, append, read back",
         "gsuite docs create --title 'Meeting notes'\n"
         "gsuite docs append 1DocId --text 'Decisions: ship it.'\n"
         "gsuite docs cat 1DocId",
         "Decisions: ship it."),
    ],
    "sheets": [
        ("Append rows, then read a range",
         "gsuite sheets append 1SheetId 'Sheet1!A1' --values 'jan,100;feb,120'\n"
         "gsuite sheets read 1SheetId 'Sheet1!A1:B2'",
         "jan\t100\nfeb\t120"),
    ],
    "slides": [
        ("Create a deck and inspect it",
         "gsuite slides create --title 'Q1 review'\n"
         "gsuite slides info 1PresId",
         "id: 1PresId\ntitle: Q1 review\nslides: 1"),
    ],
    "contacts": [
        ("Search, then add a contact",
         "gsuite contacts search ada\n"
         "gsuite contacts create --name 'Ada Lovelace' --email ada@example.com",
         "created people/c123"),
    ],
    "tasks": [
        ("Add a task with a due date and complete it",
         "gsuite tasks add 'File expenses' --due 2026-01-09\n"
         "gsuite tasks done t1",
         "completed t1"),
    ],
    "chat": [
        ("Message a space",
         "gsuite chat spaces\n"
         "gsuite chat send spaces/AAAA --text 'Deploy done ✅'",
         "sent spaces/AAAA/messages/BBBB.CCCC"),
    ],
    "keep": [
        ("Capture a note",
         "gsuite keep create --title Ideas --text 'One CLI for everything'",
         "created notes/n123"),
    ],
    "admin": [
        ("Onboard a user and add them to a group",
         "gsuite admin users create --email new@corp.com --first New "
         "--last Person --password 'temp-Passw0rd!'\n"
         "gsuite admin groups add-member eng@corp.com new@corp.com",
         "added new@corp.com to eng@corp.com"),
        ("Find suspended accounts",
         "gsuite --json admin users list --query 'isSuspended=true'",
         '[\n  {"primaryEmail": "left@corp.com", "suspended": true}\n]'),
    ],
    "forms": [
        ("Create a form and inspect it",
         "gsuite forms create --title 'Team survey'\n"
         "gsuite forms get 1FormId",
         "id: 1FormId\ntitle: Team survey\n"
         "url: https://docs.google.com/forms/d/e/…/viewform\nitems: 0"),
        ("Review the latest responses",
         "gsuite forms responses 1FormId --max 2",
         "ID    SUBMITTED\n"
         "r9a1  2026-01-05T10:00:00Z\n"
         "r9a2  2026-01-06T11:30:00Z"),
    ],
    "api": [
        ("Call any endpoint (no dedicated command needed)",
         "gsuite api call GET drive/v3/about --param fields=user",
         '{\n  "user": {\n    "emailAddress": "you@example.com"\n  }\n}'),
        ("Discover what an API offers",
         "gsuite api describe forms",
         "METHOD               HTTP  PATH             DESCRIPTION\n"
         "forms.forms.create   POST  v1/forms         Create a new form."),
    ],
}


def _sub_action(parser) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _arg_rows(parser) -> list[tuple[str, str, str, str]]:
    rows = []
    formatter = parser._get_formatter()
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction,
                               argparse._SubParsersAction)):
            continue
        name = formatter._format_action_invocation(action)
        if action.option_strings:
            required = "yes" if action.required else ""
        else:
            required = "" if action.nargs in ("?", "*") else "yes"
        default = ""
        if action.default not in (None, False, "", argparse.SUPPRESS):
            default = f"`{action.default}`"
        rows.append((f"`{name}`", required, default, action.help or ""))
    return rows


def _sentence(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


def _render_leaf(lines: list[str], parser) -> None:
    lines += ["```text", parser.format_usage().strip(), "```", ""]
    rows = _arg_rows(parser)
    if rows:
        lines += ["| Argument | Required | Default | Description |",
                  "| --- | --- | --- | --- |"]
        lines += [f"| {n} | {r} | {d} | {h} |" for n, r, d, h in rows]
        lines += [""]


def _render_command(lines: list[str], prefix: str, name: str, parser,
                    help_text: str, depth: int) -> None:
    lines += [f"{'#' * depth} `{prefix} {name}`", ""]
    if help_text:
        lines += [f"{_sentence(help_text)}.", ""]
    sub = _sub_action(parser)
    if sub is None:
        _render_leaf(lines, parser)
        return
    helps = {ca.dest: ca.help or "" for ca in sub._choices_actions}
    for child_name, child_parser in sub.choices.items():
        _render_command(lines, f"{prefix} {name}", child_name, child_parser,
                        helps.get(child_name, ""), depth + 1)


def render_service(name: str, parser, help_text: str) -> str:
    lines = [f"# gsuite {name}", ""]
    if help_text:
        lines += [f"{_sentence(help_text)}.", ""]
    lines += ["```text", parser.format_usage().strip(), "```", "",
              "Global flags `-a/--account <email|alias>` and `--json` go "
              "*before* the service name.", "", "## Commands", ""]
    sub = _sub_action(parser)
    helps = {ca.dest: ca.help or "" for ca in sub._choices_actions}
    for child_name, child_parser in sub.choices.items():
        _render_command(lines, f"gsuite {name}", child_name, child_parser,
                        helps.get(child_name, ""), 3)
    lines += ["## Examples", ""]
    for title, command, output in EXAMPLES[name]:
        shown = "\n".join(f"$ {c}" for c in command.split("\n"))
        lines += [f"**{title}**", "", "```console", shown, output, "```", ""]
    return "\n".join(lines).rstrip() + "\n"


def render_index(service_helps: dict[str, str]) -> str:
    lines = [
        "# Command reference", "",
        "One page per service, generated from the CLI's own parser tree by",
        "`scripts/gen_docs.py` (never edit these pages by hand — the",
        "`verify.py` gate fails if they drift from the code).", "",
        "| Service | Description |", "| --- | --- |",
    ]
    for name in SERVICE_MODULES:
        lines.append(f"| [`gsuite {name}`]({name}.md) | {service_helps[name]} |")
    return "\n".join(lines) + "\n"


def build_pages() -> dict[str, str]:
    missing = [s for s in SERVICE_MODULES if not EXAMPLES.get(s)]
    if missing:
        raise SystemExit(f"gen_docs: no EXAMPLES for: {', '.join(missing)}")
    root = build_parser()
    sub = _sub_action(root)
    helps = {ca.dest: ca.help or "" for ca in sub._choices_actions}
    pages = {os.path.join(REFERENCE_DIR, "index.md"): render_index(helps)}
    for name in SERVICE_MODULES:
        pages[os.path.join(REFERENCE_DIR, f"{name}.md")] = render_service(
            name, sub.choices[name], helps[name])
    return pages


def main() -> int:
    check = "--check" in sys.argv[1:]
    pages = build_pages()
    stale = []
    for path, content in pages.items():
        try:
            current = open(path).read()
        except FileNotFoundError:
            current = None
        if current != content:
            stale.append(os.path.relpath(path, ROOT))
            if not check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as fh:
                    fh.write(content)
    if check and stale:
        print("stale reference docs (run scripts/gen_docs.py):")
        print("\n".join(f"  {p}" for p in stale))
        return 1
    print(f"reference docs: {len(pages)} pages "
          f"({'in sync' if not stale else f'{len(stale)} rewritten'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
