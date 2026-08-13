"""Human tables by default, machine JSON with --json, CSV with --csv.

`--fields a,b` narrows any of those shapes to the named columns, matched
against the table HEADERs case-insensitively and emitted in the order the
user asked for.
"""
from __future__ import annotations

import csv
import json
import sys

from gsuite.errors import CLIError


def _get(row: dict, getter):
    value = _raw(row, getter)
    return "" if value is None else str(value)


def _raw(row: dict, getter):
    """The column's value, uncoerced: callable getters are called."""
    return getter(row) if callable(getter) else row.get(getter)


def check_flags(args) -> None:
    """Reject output flag combinations that ask for two shapes at once."""
    if getattr(args, "json", False) and getattr(args, "csv", False):
        raise CLIError("--json and --csv are mutually exclusive")


def _select(args, columns: list[tuple]) -> list[tuple]:
    """The columns named by --fields, in the requested order (all, if unset)."""
    requested = getattr(args, "fields", None)
    if not requested:
        return columns
    names = [n.strip() for n in str(requested).split(",") if n.strip()]
    by_header = {header.lower(): (header, getter) for header, getter in columns}
    chosen = []
    for name in names:
        col = by_header.get(name.lower())
        if col is None:
            valid = ", ".join(header for header, _ in columns)
            raise CLIError(f"unknown field: {name} (valid fields: {valid})")
        chosen.append(col)
    return chosen


def emit(args, rows: list[dict], columns: list[tuple]) -> None:
    """columns: [(header, key-or-callable), ...]"""
    check_flags(args)
    selected = _select(args, columns)
    if getattr(args, "json", False):
        if selected is not columns:
            rows = [{header.lower(): _raw(row, getter)
                     for header, getter in selected} for row in rows]
        print(json.dumps(rows, indent=2, sort_keys=True))
        return
    table = [[_get(row, getter) for _, getter in selected] for row in rows]
    headers = [header for header, _ in selected]
    if getattr(args, "csv", False):
        writer = csv.writer(sys.stdout)
        writer.writerow(headers)
        writer.writerows(table)
        return
    widths = [max(len(headers[i]), *(len(r[i]) for r in table), 0) if table
              else len(headers[i]) for i in range(len(headers))]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip())
    for row in table:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip())


def confirm(*parts) -> None:
    """Action confirmation line: joins the non-empty parts with spaces."""
    print(" ".join(str(p) for p in parts if p not in (None, "")))


def emit_obj(args, obj: dict, fields: list[tuple] | None = None) -> None:
    """Single-object output: `key: value` lines, or full JSON with --json."""
    check_flags(args)
    if fields is None:
        fields = [(k, k) for k in obj]
    selected = _select(args, fields)
    if getattr(args, "json", False):
        if selected is not fields:
            obj = {label.lower(): _raw(obj, getter)
                   for label, getter in selected}
        print(json.dumps(obj, indent=2, sort_keys=True))
        return
    for label, getter in selected:
        print(f"{label}: {_get(obj, getter)}")
