"""`gsuite sheets` — create, read, append, update, clear, tabs."""
from __future__ import annotations

import json

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, arg, register_service
from gsuite.output import confirm, emit

BASE = "https://sheets.googleapis.com/v4/spreadsheets"

RANGE_ARG = arg("range", help="A1 notation, e.g. Sheet1!A1:B10")
VALUES_FLAG = arg("--values", required=True,
                  help="rows separated by ';', cells by ','")


def _values_url(sheet_id: str, cell_range: str, suffix: str = "") -> str:
    return (f"{BASE}/{quote_id(sheet_id)}"
            f"/values/{quote_id(cell_range)}{suffix}")


def parse_values(spec: str) -> list[list[str]]:
    """'a,b;c,d' -> [[a,b],[c,d]] (rows split on ';', cells on ',')."""
    return [[cell.strip() for cell in row.split(",")]
            for row in spec.split(";") if row.strip()]


def cmd_create(args) -> int:
    sheet = Client.for_args(args).post(
        BASE, json_body={"properties": {"title": args.title}})
    confirm("created", sheet.get("spreadsheetId"))
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
    confirm("appended", result.get("updates", {}).get("updatedRows"), "row(s)")
    return 0


def cmd_update(args) -> int:
    Client.for_args(args).put(
        _values_url(args.id, args.range),
        params={"valueInputOption": "USER_ENTERED"},
        json_body={"values": parse_values(args.values)})
    confirm("updated", args.range)
    return 0


def cmd_clear(args) -> int:
    Client.for_args(args).post(_values_url(args.id, args.range, ":clear"))
    confirm("cleared", args.range)
    return 0


TABS_FIELDS = ("sheets(properties(sheetId,title,index,"
               "gridProperties(rowCount,columnCount)))")


def cmd_tabs(args) -> int:
    data = Client.for_args(args).get(f"{BASE}/{quote_id(args.id)}",
                                     params={"fields": TABS_FIELDS})
    tabs = [sheet.get("properties", {}) for sheet in data.get("sheets", [])]
    emit(args, tabs, [
        ("ID", "sheetId"), ("TITLE", "title"),
        ("ROWS", lambda p: p.get("gridProperties", {}).get("rowCount")),
        ("COLS", lambda p: p.get("gridProperties", {}).get("columnCount")),
    ])
    return 0


def cmd_add_tab(args) -> int:
    result = Client.for_args(args).post(
        f"{BASE}/{quote_id(args.id)}:batchUpdate",
        json_body={"requests": [
            {"addSheet": {"properties": {"title": args.title}}}]})
    props = (result.get("replies", [{}])[0]
             .get("addSheet", {}).get("properties", {}))
    confirm("added tab", props.get("sheetId"), props.get("title"))
    return 0


def cmd_rm_tab(args) -> int:
    Client.for_args(args).post(
        f"{BASE}/{quote_id(args.id)}:batchUpdate",
        json_body={"requests": [{"deleteSheet": {"sheetId": int(args.tab)}}]})
    confirm("removed tab", args.tab)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "sheets", "spreadsheets: read/append/update", [
        Cmd("create", cmd_create, "create a spreadsheet",
            (arg("--title", required=True),)),
        Cmd("read", cmd_read, "print a range (tab-separated)",
            (arg("id"), RANGE_ARG)),
        Cmd("append", cmd_append, "append rows after a range",
            (arg("id"), RANGE_ARG, VALUES_FLAG)),
        Cmd("update", cmd_update, "overwrite a range",
            (arg("id"), RANGE_ARG, VALUES_FLAG)),
        Cmd("clear", cmd_clear, "clear a range", (arg("id"), RANGE_ARG)),
        Cmd("tabs", cmd_tabs, "list tabs (sheets) in a spreadsheet",
            (arg("id"),)),
        Cmd("add-tab", cmd_add_tab, "add a tab",
            (arg("id"), arg("--title", required=True))),
        Cmd("rm-tab", cmd_rm_tab, "remove a tab",
            (arg("id"), arg("--tab", required=True,
                            help="numeric sheet id (see `sheets tabs`)"))),
    ])
