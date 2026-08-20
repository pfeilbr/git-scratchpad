#!/usr/bin/env python3
"""Measure the command surface against the two tools this one set out to combine.

The project exists to merge Google's `gws` and steipete's `gog` into one CLI.
That is a claim about coverage, and a claim about coverage that nothing checks
is a claim that quietly stops being true. This turns it into a number with a
ratchet under it.

Two files hold the two different kinds of knowledge, and they are kept apart
on purpose:

* `parity/upstream.tsv` is *evidence* — the upstream command lists, fetched
  from the projects themselves, stamped with the URL, the date and a digest of
  what was read. Never hand-edited. `--refresh` rewrites it and is the only
  part that touches the network.
* `parity/mapping.tsv` is *judgment* — which upstream commands this tool
  provides under a different name, and which it deliberately will not provide,
  each with a reason someone can argue with.

Everything else is derived. `--check` is offline and deterministic, so it can
run in CI:

    python3 scripts/parity.py              # the coverage table
    python3 scripts/parity.py --check      # CI gate: fail on regression or drift
    python3 scripts/parity.py --update     # accept the current numbers as the floor
    python3 scripts/parity.py --refresh    # re-fetch upstream (manual, needs network)

The ratchet compares covered-command counts against `parity/baseline.json` and
fails if either drops. It deliberately does *not* fail on commands that are
merely missing: 586 of them are, and a gate that is red from the first day is
a gate people learn to skip. Missing is the roadmap; regression is the alarm.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PARITY = os.path.join(ROOT, "parity")
UPSTREAM = os.path.join(PARITY, "upstream.tsv")
MAPPING = os.path.join(PARITY, "mapping.tsv")
BASELINE = os.path.join(PARITY, "baseline.json")
README = os.path.join(ROOT, "README.md")

BEGIN = "<!-- BEGIN GENERATED PARITY -->"
END = "<!-- END GENERATED PARITY -->"

SOURCES = {
    # gog generates a docs page per command from its own live schema, so its
    # index is an exact surface listing rather than a curated selection.
    "gog": "https://raw.githubusercontent.com/openclaw/gogcli/main/"
           "docs/commands/README.md",
    # gws builds its surface from Google's Discovery service at runtime, so it
    # has no static list to read. What *is* enumerable — and what a
    # hand-written CLI has to match deliberately — is its table of `+helper`
    # commands, the ergonomic verbs it ships on top of Discovery.
    "gws": "https://raw.githubusercontent.com/googleworkspace/cli/main/README.md",
}


# -- our own surface ---------------------------------------------------------

def our_commands() -> set[str]:
    """Every leaf command in this CLI, as a space-joined path."""
    from gsuite.cli import build_parser

    def leaves(parser, prefix=()):
        sub = next((a for a in parser._actions
                    if isinstance(a, argparse._SubParsersAction)), None)
        if sub is None:
            yield " ".join(prefix)
            return
        for name, child in sub.choices.items():
            yield from leaves(child, prefix + (name,))

    return set(leaves(build_parser()))


# -- upstream extraction -----------------------------------------------------

def extract_gog(text: str) -> list[str]:
    """Leaf commands from gog's generated command index.

    The index is a nested bullet tree of every command, parents included. A
    parent is not a runnable command, so anything another entry extends is
    dropped — otherwise `gog gmail` would count alongside `gog gmail search`
    and inflate the denominator.
    """
    lines = text.splitlines()
    start = lines.index("## All Commands")
    entries = [m.group(1) for ln in lines[start + 1:]
               if (m := re.match(r'^\s*- \[(gog[^\]]*)\]', ln))]
    seen = set(entries)
    leaves = [e for e in entries
              if not any(o != e and o.startswith(e + " ") for o in seen)]
    # Strip the binary name; keep the command path.
    return sorted({e.split(None, 1)[1] for e in leaves if " " in e})


def extract_gws(text: str) -> list[str]:
    """gws's `+helper` commands, from the "Full helper reference" table.

    Rows look like `| `gmail` | `+send` | Send an email |`. The Discovery-
    generated surface is not listed here because gws does not list it either;
    see the note on SOURCES and the `api call` exclusion in mapping.tsv.
    """
    rows = re.findall(r'^\|\s*`([a-z]+)`\s*\|\s*`(\+[a-z-]+)`\s*\|',
                      text, re.M)
    return sorted({f"{service} {helper}" for service, helper in rows})


EXTRACTORS = {"gog": extract_gog, "gws": extract_gws}


# -- files -------------------------------------------------------------------

def read_rows(path: str) -> list[list[str]]:
    with open(path) as fh:
        return [ln.rstrip("\n").split("\t") for ln in fh
                if ln.strip() and not ln.startswith("#")]


def read_upstream() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for tool, command in read_rows(UPSTREAM):
        out.setdefault(tool, []).append(command)
    return out


def read_mapping() -> dict[tuple[str, str], tuple[str, str]]:
    return {(t, c): (status, value) for t, c, status, value in read_rows(MAPPING)}


def refresh() -> int:
    """Re-fetch both upstream surfaces. The only code here that goes online."""
    import urllib.request

    today = dt.date.today().isoformat()
    header, body = [], []
    for tool, url in SOURCES.items():
        with urllib.request.urlopen(url, timeout=60) as resp:
            raw = resp.read()
        commands = EXTRACTORS[tool](raw.decode())
        digest = hashlib.sha256(raw).hexdigest()
        header.append(f"# source\t{tool}\t{url}\t{today}\tsha256:{digest}\n")
        body += [f"{tool}\t{c}\n" for c in commands]
        print(f"fetched {len(commands):4d} {tool} commands")
    os.makedirs(PARITY, exist_ok=True)
    with open(UPSTREAM, "w") as fh:
        fh.write("# Upstream command surfaces — fetched evidence, not hand-edited.\n"
                 "# Regenerate: python3 scripts/parity.py --refresh  (needs network)\n"
                 "#\n")
        fh.writelines(header)
        fh.write("#\n")
        fh.writelines(body)
    print(f"wrote {UPSTREAM}")
    return 0


# -- the measurement ---------------------------------------------------------

def measure() -> dict[str, dict]:
    ours = our_commands()
    mapping = read_mapping()
    report: dict[str, dict] = {}
    for tool, commands in sorted(read_upstream().items()):
        covered, excluded, missing, broken = [], [], [], []
        for command in commands:
            status, value = mapping.get((tool, command), ("", ""))
            if status == "excluded":
                excluded.append((command, value))
            elif status == "alias":
                # An alias is a promise that some command of ours does this.
                # Trusting the row instead of checking it would let a deleted
                # command keep its coverage, and the ratchet would sit green
                # through the one event it exists to catch.
                (covered if value in ours else broken).append(command)
            elif command in ours:
                covered.append(command)
            else:
                missing.append(command)
        report[tool] = {"covered": covered, "excluded": excluded,
                        "missing": missing, "broken": broken,
                        "total": len(commands)}
    report["_ours"] = {"total": len(ours)}
    return report


def _pct(part: int, whole: int) -> str:
    return f"{(100 * part / whole):.0f}%" if whole else "—"


def render_table(report: dict) -> str:
    """The generated README block: the claim, as a number."""
    lines = [
        "| Upstream tool | Commands | Provided here | Deliberately out of scope | Not yet |",
        "| --- | --- | --- | --- | --- |",
    ]
    for tool in ("gws", "gog"):
        r = report[tool]
        n = len(r["covered"])
        in_scope = r["total"] - len(r["excluded"])
        lines.append(f"| `{tool}` | {r['total']} | {n} ({_pct(n, in_scope)} of "
                     f"in-scope) | {len(r['excluded'])} | {len(r['missing'])} |")
    lines.append("")
    lines.append(f"`gsuite` ships **{report['_ours']['total']} commands**. "
                 "Percentages are of the in-scope surface — the exclusions and "
                 "their reasons are in "
                 "[`parity/mapping.tsv`](parity/mapping.tsv), and the upstream "
                 "lists in [`parity/upstream.tsv`](parity/upstream.tsv) carry "
                 "the URL and digest they were read from. Regenerate with "
                 "`python3 scripts/parity.py`.")
    return "\n".join(lines)


def readme_with_table(report: dict) -> tuple[str, str]:
    """The README as it is, and as it should be. Pure — nothing is written."""
    text = open(README).read()
    if BEGIN not in text:
        raise SystemExit(f"README.md has no {BEGIN} marker")
    before, rest = text.split(BEGIN, 1)
    _stale, after = rest.split(END, 1)
    return text, f"{before}{BEGIN}\n\n{render_table(report)}\n\n{END}{after}"


def write_readme(report: dict) -> bool:
    """Splice the table into README; return True if it changed."""
    current, wanted = readme_with_table(report)
    if current == wanted:
        return False
    with open(README, "w") as fh:
        fh.write(wanted)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="CI gate: fail on coverage regression or README drift")
    ap.add_argument("--update", action="store_true",
                    help="record the current coverage as the new floor")
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch the upstream lists (needs network)")
    ap.add_argument("--missing", metavar="TOOL", choices=sorted(SOURCES),
                    help="list what TOOL has that this does not (the roadmap)")
    args = ap.parse_args()

    if args.refresh:
        return refresh()

    report = measure()

    if args.missing:
        for command in report[args.missing]["missing"]:
            print(command)
        return 0

    # --check must leave the tree exactly as it found it: it is the step CI
    # runs to *detect* drift, so repairing the drift on the way past would
    # make the second run disagree with the first and hide the problem.
    current, wanted = readme_with_table(report)
    stale = current != wanted
    if not args.check:
        write_readme(report)
    baseline = json.load(open(BASELINE)) if os.path.exists(BASELINE) else {}

    if args.update or not baseline:
        with open(BASELINE, "w") as fh:
            json.dump({t: {"covered": len(r["covered"]), "total": r["total"]}
                       for t, r in report.items() if not t.startswith("_")},
                      fh, indent=2)
            fh.write("\n")
        print("baseline updated")
        return 0

    for tool in ("gws", "gog"):
        r = report[tool]
        print(f"{tool}: {len(r['covered'])} covered, {len(r['excluded'])} "
              f"out of scope, {len(r['missing'])} missing of {r['total']}")

    broken = {t: report[t]["broken"] for t in ("gws", "gog") if report[t]["broken"]}
    if broken:
        for tool, commands in broken.items():
            print(f"PARITY BROKEN MAPPING: {tool} {', '.join(commands)} "
                  "— aliased to a command that no longer exists")
        return 1

    if args.check:
        regressed = [
            f"{t}: {len(report[t]['covered'])} covered, baseline was {b['covered']}"
            for t, b in baseline.items()
            if len(report[t]["covered"]) < b["covered"]]
        if regressed:
            print("PARITY REGRESSED: " + "; ".join(regressed))
            return 1
        if stale:
            print("PARITY: README is out of date — "
                  "run `python3 scripts/parity.py` and commit the result")
            return 1
        print("PARITY OK: no coverage regression")
    return 0


if __name__ == "__main__":
    sys.exit(main())
