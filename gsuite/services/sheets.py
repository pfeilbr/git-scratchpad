"""`gsuite sheets` — create, read, append, update, clear."""
from __future__ import annotations

import json
import urllib.parse

from gsuite.api import Client

BASE = "https://sheets.googleapis.com/v4/spreadsheets"


def _values_url(sheet_id: str, cell_range: str, suffix: str = "") -> str:
    quoted = urllib.parse.quote(cell_range, safe="")
    return f"{BASE}/{sheet_id}/values/{quoted}{suffix}"


def parse_values(spec: str) -> list[list[str]]:
    """'a,b;c,d' -> [[a,b],[c,d]] (rows split on ';', cells on ',')."""
    return [[cell.strip() for cell in row.split(",")]
            for row in spec.split(";") if row.strip()]


def cmd_create(args) -> int:
    sheet = Client.for_args(args).post(
        BASE, json_body={"properties": {"title": args.title}})
    print(f"created {sheet.get('spreadsheetId', '')}".strip())
    return 0


def cmd_read(args) -> int:
    data = Client.for_args(args).get(_values_url(args.id, args.range))
    if getattr(args, "json", False):
        print(json.dumps(data.get("values", []), indent=2))
        return 0
    for row in data.get("values", []):
        print("\t".join(str(cell) for cell in row))
    return 0


def cmd_append(args) -> int:
    result = Client.for_args(args).post(
        _values_url(args.id, args.range, ":append"),
        params={"valueInputOption": "USER_ENTERED"},
        json_body={"values": parse_values(args.values)})
    rows = result.get("updates", {}).get("updatedRows", "")
    print(f"appended {rows} row(s)".strip())
    return 0


def cmd_update(args) -> int:
    Client.for_args(args).put(
        _values_url(args.id, args.range),
        params={"valueInputOption": "USER_ENTERED"},
        json_body={"values": parse_values(args.values)})
    print(f"updated {args.range}")
    return 0


def cmd_clear(args) -> int:
    Client.for_args(args).post(_values_url(args.id, args.range, ":clear"))
    print(f"cleared {args.range}")
    return 0


def register(subparsers) -> None:
    p = subparsers.add_parser("sheets", help="spreadsheets: read/append/update")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    create = sub.add_parser("create", help="create a spreadsheet")
    create.add_argument("--title", required=True)
    create.set_defaults(func=cmd_create)

    read = sub.add_parser("read", help="print a range (tab-separated)")
    read.add_argument("id")
    read.add_argument("range", help="A1 notation, e.g. Sheet1!A1:B10")
    read.set_defaults(func=cmd_read)

    append = sub.add_parser("append", help="append rows after a range")
    append.add_argument("id")
    append.add_argument("range")
    append.add_argument("--values", required=True,
                        help="rows separated by ';', cells by ','")
    append.set_defaults(func=cmd_append)

    update = sub.add_parser("update", help="overwrite a range")
    update.add_argument("id")
    update.add_argument("range")
    update.add_argument("--values", required=True)
    update.set_defaults(func=cmd_update)

    clear = sub.add_parser("clear", help="clear a range")
    clear.add_argument("id")
    clear.add_argument("range")
    clear.set_defaults(func=cmd_clear)
