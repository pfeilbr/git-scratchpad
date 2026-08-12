"""`gsuite calendar` — calendars, events, create, agenda."""
from __future__ import annotations

import datetime as dt

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.errors import CLIError
from gsuite.output import confirm, emit, emit_obj
from gsuite.services._common import emit_paged

BASE = "https://www.googleapis.com/calendar/v3"

CALENDAR_FLAG = arg("--calendar", default="primary",
                    help="calendar id (default: primary)")
EVENT_COLUMNS = [("ID", "id"), ("START", lambda e: _when(e)),
                 ("SUMMARY", "summary"), ("LOCATION", "location")]


def _cal_url(calendar_id: str, suffix: str = "") -> str:
    return f"{BASE}/calendars/{quote_id(calendar_id)}{suffix}"


def _when(event: dict, key: str = "start") -> str:
    slot = event.get(key, {})
    return slot.get("dateTime") or slot.get("date") or ""


def _parse_point(value: str) -> tuple[str, str]:
    """'2026-01-05' -> all-day; '2026-01-05T09:00' -> timed. Returns (kind, value)."""
    if "T" in value:
        try:
            parsed = dt.datetime.fromisoformat(value)
        except ValueError as exc:
            raise CLIError(f"bad datetime: {value} (want YYYY-MM-DDTHH:MM)") from exc
        return "dateTime", parsed.isoformat()
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise CLIError(f"bad date: {value} (want YYYY-MM-DD)") from exc
    return "date", value


def _day_bounds(date_str: str) -> tuple[str, str]:
    day = dt.date.fromisoformat(date_str)
    return (f"{day.isoformat()}T00:00:00Z",
            f"{(day + dt.timedelta(days=1)).isoformat()}T00:00:00Z")


def _to_rfc3339(value: str | None) -> str | None:
    if value is None:
        return None
    return value if "T" in value else f"{value}T00:00:00Z"


def _emit_window(args, time_min: str | None, time_max: str | None,
                 limit: int | None) -> None:
    params = {"singleEvents": "true", "orderBy": "startTime"}
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max
    emit_paged(args, _cal_url(args.calendar, "/events"), EVENT_COLUMNS,
               params=params, limit=limit)


def cmd_calendars(args) -> int:
    emit_paged(args, f"{BASE}/users/me/calendarList",
               [("ID", "id"), ("SUMMARY", "summary"),
                ("PRIMARY", lambda c: "yes" if c.get("primary") else "")])
    return 0


def cmd_events(args) -> int:
    _emit_window(args, _to_rfc3339(getattr(args, "from")),
                 _to_rfc3339(args.to), args.max)
    return 0


def cmd_agenda(args) -> int:
    date = args.date or dt.date.today().isoformat()
    time_min, time_max = _day_bounds(date)
    _emit_window(args, time_min, time_max, None)
    return 0


def cmd_create(args) -> int:
    kind, start = _parse_point(args.start)
    body: dict = {"summary": args.summary, "start": {kind: start}}
    if args.end:
        end_kind, end = _parse_point(args.end)
        body["end"] = {end_kind: end}
    elif kind == "date":
        next_day = dt.date.fromisoformat(start) + dt.timedelta(days=1)
        body["end"] = {"date": next_day.isoformat()}
    else:
        raise CLIError("--end is required for timed events")
    if args.attendees:
        body["attendees"] = [{"email": a.strip()}
                             for a in args.attendees.split(",") if a.strip()]
    if args.description:
        body["description"] = args.description
    if args.location:
        body["location"] = args.location
    created = Client.for_args(args).post(_cal_url(args.calendar, "/events"),
                                         json_body=body)
    confirm("created", created.get("id"), created.get("htmlLink"))
    return 0


def cmd_get(args) -> int:
    event = Client.for_args(args).get(_cal_url(args.calendar, f"/events/{args.id}"))
    emit_obj(args, {"id": event.get("id"), "summary": event.get("summary"),
                    "start": _when(event), "end": _when(event, "end"),
                    "location": event.get("location", ""),
                    "description": event.get("description", "")})
    return 0


def cmd_delete(args) -> int:
    Client.for_args(args).delete(_cal_url(args.calendar, f"/events/{args.id}"))
    confirm("deleted", args.id)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "calendar", "calendars, events, agenda", [
        Cmd("calendars", cmd_calendars, "list calendars"),
        Cmd("events", cmd_events, "list events in a time window",
            (CALENDAR_FLAG,
             arg("--from", dest="from", metavar="WHEN",
                 help="RFC3339 or YYYY-MM-DD lower bound"),
             arg("--to", help="RFC3339 or YYYY-MM-DD upper bound"),
             max_flag(50))),
        Cmd("agenda", cmd_agenda, "events for one day (default: today)",
            (CALENDAR_FLAG, arg("--date", help="YYYY-MM-DD"))),
        Cmd("create", cmd_create, "create an event",
            (CALENDAR_FLAG, arg("--summary", required=True),
             arg("--start", required=True,
                 help="YYYY-MM-DD (all-day) or YYYY-MM-DDTHH:MM"),
             arg("--end"), arg("--attendees", help="comma-separated emails"),
             arg("--description"), arg("--location"))),
        Cmd("get", cmd_get, "show one event", (CALENDAR_FLAG, arg("id"))),
        Cmd("delete", cmd_delete, "delete an event", (CALENDAR_FLAG, arg("id"))),
    ])
