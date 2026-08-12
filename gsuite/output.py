"""Human tables by default, machine JSON with --json."""
from __future__ import annotations

import json


def _get(row: dict, getter):
    if callable(getter):
        value = getter(row)
    else:
        value = row.get(getter, "")
    return "" if value is None else str(value)


def emit(args, rows: list[dict], columns: list[tuple]) -> None:
    """columns: [(header, key-or-callable), ...]"""
    if getattr(args, "json", False):
        print(json.dumps(rows, indent=2, sort_keys=True))
        return
    table = [[_get(row, getter) for _, getter in columns] for row in rows]
    headers = [header for header, _ in columns]
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
    if getattr(args, "json", False):
        print(json.dumps(obj, indent=2, sort_keys=True))
        return
    if fields is None:
        fields = [(k, k) for k in obj]
    for label, getter in fields:
        print(f"{label}: {_get(obj, getter)}")
