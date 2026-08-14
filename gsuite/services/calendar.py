"""`gsuite calendar` — calendars, events, create, agenda."""
from __future__ import annotations

import datetime as dt
import os
from zoneinfo import ZoneInfo

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.errors import CLIError
from gsuite.output import confirm, emit, emit_obj
from gsuite.services._common import emit_paged

BASE = "https://www.googleapis.com/calendar/v3"

CALENDAR_FLAG = arg("--calendar", default="primary",
                    help="calendar id (default: primary)")
TZ_FLAG = arg("--tz", metavar="NAME",
              help="IANA timezone for bare dates and times, e.g. "
                   "America/New_York (default: the system timezone)")
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


def _slot(kind: str, value: str, tz: dt.tzinfo) -> dict:
    """An event endpoint: all-day dates stand alone, timed ones name their zone."""
    return {kind: value} if kind == "date" else {kind: value, "timeZone": str(tz)}


def _local_zone() -> dt.tzinfo:
    """The machine's own timezone (the seam tests replace for determinism).

    Named, not a snapshot: `datetime.now().astimezone().tzinfo` is a *fixed*
    offset taken from today, so it would put a January day an hour off when
    asked in July — and its name ("EDT") is not one Google accepts. $TZ and
    the /etc/localtime symlink both name a real zone; the snapshot is only
    the last resort for systems where neither does.
    """
    name = os.environ.get("TZ", "").lstrip(":")
    if not name:
        name = os.path.realpath("/etc/localtime").rpartition("/zoneinfo/")[2]
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        return dt.datetime.now().astimezone().tzinfo


def _zone(name: str | None) -> dt.tzinfo:
    """`--tz NAME` as a tzinfo; the system zone when the flag is absent."""
    if not name:
        return _local_zone()
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError) as exc:  # ZoneInfoNotFoundError is a KeyError
        raise CLIError(f"unknown timezone: {name} "
                       "(want an IANA name like America/New_York)") from exc


def _midnight(day: dt.date, tz: dt.tzinfo) -> str:
    """Midnight *in tz*, e.g. '2026-01-05T00:00:00-05:00' — never UTC midnight."""
    return dt.datetime.combine(day, dt.time(), tz).isoformat().replace(
        "+00:00", "Z")


def _day_bounds(date_str: str, tz: dt.tzinfo) -> tuple[str, str]:
    day = dt.date.fromisoformat(date_str)
    return _midnight(day, tz), _midnight(day + dt.timedelta(days=1), tz)


def _to_rfc3339(value: str | None, tz: dt.tzinfo) -> str | None:
    """A bare YYYY-MM-DD means local midnight; a full instant passes through."""
    if value is None or "T" in value:
        return value
    return _midnight(dt.date.fromisoformat(value), tz)


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
    tz = _zone(args.tz)
    _emit_window(args, _to_rfc3339(getattr(args, "from"), tz),
                 _to_rfc3339(args.to, tz), args.max)
    return 0


def cmd_agenda(args) -> int:
    tz = _zone(args.tz)
    # "today" is a fact about the effective zone, not about UTC.
    date = args.date or dt.datetime.now(tz).date().isoformat()
    time_min, time_max = _day_bounds(date, tz)
    _emit_window(args, time_min, time_max, None)
    return 0


def cmd_create(args) -> int:
    tz = _zone(args.tz)
    kind, start = _parse_point(args.start)
    body: dict = {"summary": args.summary, "start": _slot(kind, start, tz)}
    if args.end:
        end_kind, end = _parse_point(args.end)
        body["end"] = _slot(end_kind, end, tz)
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


def cmd_update(args) -> int:
    body: dict = {}
    for field in ("summary", "location", "description"):
        value = getattr(args, field)
        if value is not None:
            body[field] = value
    for field in ("start", "end"):
        value = getattr(args, field)
        if value is not None:
            kind, point = _parse_point(value)
            body[field] = {kind: point}
    if not body:
        raise CLIError("nothing to update (pass --summary, --start, --end, "
                       "--location, or --description)")
    Client.for_args(args).patch(_cal_url(args.calendar, f"/events/{args.id}"),
                                json_body=body)
    confirm("updated", args.id)
    return 0


def cmd_respond(args) -> int:
    client = Client.for_args(args)
    url = _cal_url(args.calendar, f"/events/{args.id}")
    event = client.get(url)
    attendees = event.get("attendees", [])
    mine = next((a for a in attendees
                 if a.get("self") or a.get("email") == client.email), None)
    if mine is None:
        raise CLIError(f"{client.email} is not an attendee of {args.id}")
    mine["responseStatus"] = args.as_
    client.patch(url, json_body={"attendees": attendees})
    confirm("responded", args.as_, "to", event.get("id") or args.id)
    return 0


def cmd_freebusy(args) -> int:
    calendars = [c.strip() for c in (args.calendars or "primary").split(",")
                 if c.strip()]
    body = {"timeMin": _to_rfc3339(getattr(args, "from"), dt.timezone.utc),
            "timeMax": _to_rfc3339(args.to, dt.timezone.utc),
            "items": [{"id": c} for c in calendars]}
    result = Client.for_args(args).post(f"{BASE}/freeBusy", json_body=body)
    rows = [{"calendar": cal_id, "from": block.get("start", ""),
             "to": block.get("end", "")}
            for cal_id, info in result.get("calendars", {}).items()
            for block in info.get("busy", [])]
    emit(args, rows, [("CALENDAR", "calendar"), ("BUSY-FROM", "from"),
                      ("BUSY-TO", "to")])
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "calendar", "calendars, events, agenda", [
        Cmd("calendars", cmd_calendars, "list calendars"),
        Cmd("events", cmd_events, "list events in a time window",
            (CALENDAR_FLAG,
             arg("--from", dest="from", metavar="WHEN",
                 help="RFC3339 or YYYY-MM-DD lower bound"),
             arg("--to", help="RFC3339 or YYYY-MM-DD upper bound"),
             TZ_FLAG, max_flag(50))),
        Cmd("agenda", cmd_agenda, "events for one day (default: today)",
            (CALENDAR_FLAG, arg("--date", help="YYYY-MM-DD"), TZ_FLAG)),
        Cmd("create", cmd_create, "create an event",
            (CALENDAR_FLAG, arg("--summary", required=True),
             arg("--start", required=True,
                 help="YYYY-MM-DD (all-day) or YYYY-MM-DDTHH:MM"),
             arg("--end"), arg("--attendees", help="comma-separated emails"),
             arg("--description"), arg("--location"), TZ_FLAG)),
        Cmd("get", cmd_get, "show one event", (CALENDAR_FLAG, arg("id"))),
        Cmd("update", cmd_update, "update fields of an event",
            (CALENDAR_FLAG, arg("id"), arg("--summary"),
             arg("--start", help="YYYY-MM-DD (all-day) or YYYY-MM-DDTHH:MM"),
             arg("--end", help="YYYY-MM-DD (all-day) or YYYY-MM-DDTHH:MM"),
             arg("--location"), arg("--description"))),
        Cmd("respond", cmd_respond, "respond to an event invitation",
            (CALENDAR_FLAG, arg("id"),
             arg("--as", dest="as_", required=True,
                 choices=["accepted", "declined", "tentative"],
                 help="response status"))),
        Cmd("freebusy", cmd_freebusy, "busy blocks per calendar in a window",
            (arg("--from", dest="from", metavar="WHEN", required=True,
                 help="RFC3339 or YYYY-MM-DD lower bound"),
             arg("--to", metavar="WHEN", required=True,
                 help="RFC3339 or YYYY-MM-DD upper bound"),
             arg("--calendars",
                 help="comma-separated calendar ids (default: primary)"))),
        Cmd("delete", cmd_delete, "delete an event", (CALENDAR_FLAG, arg("id"))),
    ])
