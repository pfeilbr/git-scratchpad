"""Human tables by default, machine JSON with --json, CSV with --csv.

`--fields a,b` narrows any of those shapes to the named columns, matched
against the table HEADERs case-insensitively and emitted in the order the
user asked for.
"""
from __future__ import annotations

import csv
import json
import sys
import unicodedata

from gsuite.errors import CLIError

# Marks and format controls a terminal draws in no cells of its own.
_ZERO_WIDTH_CATEGORIES = frozenset({"Mn", "Me", "Cf"})


def display_width(text: str) -> int:
    """How many terminal cells `text` occupies, for lining up table columns.

    Terminals lay text out in fixed cells, and `len()` counts code points
    instead: East Asian Wide and Fullwidth characters (CJK, kana, fullwidth
    forms, most emoji) draw two cells, while combining marks and zero-width
    format characters draw none. Everything else draws one.

    Deliberately not a grapheme segmenter. Sequences joined with U+200D --
    family and skin-tone emoji, say -- are measured code point by code
    point, so they can still come out wider than a terminal draws them.
    That is the price of staying dependency-free, and it is enough to keep
    ordinary subjects, file names and contact names in their columns.
    """
    width = 0
    for char in text:
        if (unicodedata.combining(char)
                or unicodedata.category(char) in _ZERO_WIDTH_CATEGORIES):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def _pad(text: str, width: int) -> str:
    """`text` followed by enough spaces to fill `width` display cells."""
    return text + " " * max(0, width - display_width(text))


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
    # Widths are in terminal cells, not code points, so a CJK subject or an
    # emoji in one row does not shove every later column out of line.
    widths = [max(display_width(headers[i]),
                  *(display_width(r[i]) for r in table), 0) if table
              else display_width(headers[i]) for i in range(len(headers))]
    print("  ".join(_pad(h, w) for h, w in zip(headers, widths)).rstrip())
    for row in table:
        print("  ".join(_pad(cell, w) for cell, w in zip(row, widths)).rstrip())


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
