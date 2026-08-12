"""`gsuite calendar` — calendars, events, create, agenda."""
from __future__ import annotations

import datetime as dt
import urllib.parse

from gsuite.api import Client
from gsuite.errors import CLIError
from gsuite.output import emit, emit_obj

BASE = "https://www.googleapis.com/calendar/v3"


def _cal_url(calendar_id: str, suffix: str = "") -> str:
    return f"{BASE}/calendars/{urllib.parse.quote(calendar_id, safe='')}{suffix}"


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


def _emit_events(args, events: list[dict]) -> None:
    emit(args, events, [("ID", "id"), ("START", _when),
                        ("SUMMARY", "summary"), ("LOCATION", "location")])


def cmd_calendars(args) -> int:
    items = list(Client.for_args(args).paged(f"{BASE}/users/me/calendarList"))
    emit(args, items, [("ID", "id"), ("SUMMARY", "summary"),
                       ("PRIMARY", lambda c: "yes" if c.get("primary") else "")])
    return 0


def _list_events(args, time_min: str | None, time_max: str | None,
                 limit: int | None) -> list[dict]:
    params = {"singleEvents": "true", "orderBy": "startTime"}
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max
    return list(Client.for_args(args).paged(_cal_url(args.calendar, "/events"),
                                            params=params, limit=limit))


def _to_rfc3339(value: str | None) -> str | None:
    if value is None:
        return None
    return value if "T" in value else f"{value}T00:00:00Z"


def cmd_events(args) -> int:
    events = _list_events(args, _to_rfc3339(getattr(args, "from")),
                          _to_rfc3339(args.to), args.max)
    _emit_events(args, events)
    return 0


def cmd_agenda(args) -> int:
    date = args.date or dt.date.today().isoformat()
    time_min, time_max = _day_bounds(date)
    events = _list_events(args, time_min, time_max, None)
    _emit_events(args, events)
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
    print(f"created {created.get('id', '')} {created.get('htmlLink', '')}".strip())
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
    print(f"deleted {args.id}")
    return 0


def _add_calendar_flag(parser) -> None:
    parser.add_argument("--calendar", default="primary",
                        help="calendar id (default: primary)")


def register(subparsers) -> None:
    p = subparsers.add_parser("calendar", help="calendars, events, agenda")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    sub.add_parser("calendars", help="list calendars").set_defaults(
        func=cmd_calendars)

    events = sub.add_parser("events", help="list events in a time window")
    _add_calendar_flag(events)
    events.add_argument("--from", dest="from", metavar="WHEN",
                        help="RFC3339 or YYYY-MM-DD lower bound")
    events.add_argument("--to", help="RFC3339 or YYYY-MM-DD upper bound")
    events.add_argument("--max", type=int, default=50)
    events.set_defaults(func=cmd_events)

    agenda = sub.add_parser("agenda", help="events for one day (default: today)")
    _add_calendar_flag(agenda)
    agenda.add_argument("--date", help="YYYY-MM-DD")
    agenda.set_defaults(func=cmd_agenda)

    create = sub.add_parser("create", help="create an event")
    _add_calendar_flag(create)
    create.add_argument("--summary", required=True)
    create.add_argument("--start", required=True,
                        help="YYYY-MM-DD (all-day) or YYYY-MM-DDTHH:MM")
    create.add_argument("--end")
    create.add_argument("--attendees", help="comma-separated emails")
    create.add_argument("--description")
    create.add_argument("--location")
    create.set_defaults(func=cmd_create)

    get = sub.add_parser("get", help="show one event")
    _add_calendar_flag(get)
    get.add_argument("id")
    get.set_defaults(func=cmd_get)

    delete = sub.add_parser("delete", help="delete an event")
    _add_calendar_flag(delete)
    delete.add_argument("id")
    delete.set_defaults(func=cmd_delete)
