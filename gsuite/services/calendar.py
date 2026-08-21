"""`gsuite calendar` — events, agendas, conflicts, calendars and sharing.

Two families of command share this module and are easy to confuse, so the
names say which is which: `create`/`delete` act on an *event*, while
`create-calendar`/`delete-calendar` act on the calendar itself and
`subscribe`/`unsubscribe` only change which calendars this account lists.
"""
from __future__ import annotations

import datetime as dt
import os
from zoneinfo import ZoneInfo

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, Group, arg, max_flag, register_service
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

# Calendar ACL vocabulary, spelled exactly as the API expects it. "none"
# revokes without deleting the rule; "default" as a scope type means the
# public, which is why it is the one type that carries no value.
ACL_ROLES = ["none", "freeBusyReader", "reader", "writer", "owner"]
SCOPE_TYPES = ["user", "group", "domain", "default"]

# Short names for the API's autoDeclineMode values. The CLI default is
# "none" on purpose: declining other people's meetings is a visible act on
# their calendars, and nobody should trigger it by forgetting a flag.
DECLINE_MODES = {"none": "declineNone",
                 "new": "declineOnlyNewConflictingInvitations",
                 "all": "declineAllConflictingInvitations"}

# How far back `changed` looks, and how far ahead `conflicts` looks, when
# the user names no window of their own.
CHANGED_DAYS = 7
CONFLICT_DAYS = 7

CONFLICT_COLUMNS = [("FROM", "from"), ("TO", "to"), ("EVENT", "event"),
                    ("ID", "id"), ("CONFLICTS-WITH", "with"),
                    ("WITH-ID", "with_id")]

# The flags `out-of-office` and `focus-time` share; only the summary default
# and focus time's chat status differ between them.
SPECIAL_EVENT_ARGS = (
    CALENDAR_FLAG,
    arg("--start", required=True, metavar="WHEN",
        help="YYYY-MM-DDTHH:MM (these blocks are always timed)"),
    arg("--end", required=True, metavar="WHEN",
        help="YYYY-MM-DDTHH:MM (these blocks are always timed)"),
    arg("--decline", default="none", choices=sorted(DECLINE_MODES),
        help="auto-decline conflicting invitations (default: none)"),
    arg("--message", help="text sent with an automatic decline"),
    TZ_FLAG,
)


def _cal_url(calendar_id: str, suffix: str = "") -> str:
    return f"{BASE}/calendars/{quote_id(calendar_id)}{suffix}"


def _event_url(args, suffix: str = "") -> str:
    """One event's URL. The id is user data, so it is escaped like the calendar.

    Event ids are opaque strings the user pastes from somewhere else; an id
    carrying a `/` (or a `?`) was interpolated raw and silently addressed a
    different endpoint than the command named.
    """
    return _cal_url(args.calendar, f"/events/{quote_id(args.id)}{suffix}")


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
    _date(value)
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


def _stamp(moment: dt.datetime, tz: dt.tzinfo) -> str:
    """A moment on the user's own clock, in this module's RFC3339 spelling."""
    return moment.astimezone(tz).isoformat().replace("+00:00", "Z")


def _midnight(day: dt.date, tz: dt.tzinfo) -> str:
    """Midnight *in tz*, e.g. '2026-01-05T00:00:00-05:00' — never UTC midnight."""
    return _stamp(dt.datetime.combine(day, dt.time(), tz), tz)


def _instant(slot: dict, tz: dt.tzinfo) -> dt.datetime | None:
    """One event endpoint as an absolute moment, or None if it cannot be read.

    An all-day endpoint is a *date*, and a date is only a moment once a zone
    says where its midnight falls — the same rule `_day_bounds` follows for a
    query window, and the reason a holiday does not run 00:00Z to 24:00Z.

    Nothing here raises. These values come from Google, not from something
    the user typed, so there is no typo for them to fix; a reply we cannot
    read costs one dropped event rather than the whole report.
    """
    stamp = slot.get("dateTime")
    if stamp:
        try:
            # Python 3.10's fromisoformat still rejects a trailing "Z".
            moment = dt.datetime.fromisoformat(
                str(stamp).replace("Z", "+00:00"))
        except ValueError:
            return None
        # Google always sends an offset; a naive value would otherwise fail
        # to compare against the aware ones at all.
        return moment if moment.tzinfo else moment.replace(tzinfo=tz)
    day = slot.get("date")
    if not day:
        return None
    try:
        return dt.datetime.combine(dt.date.fromisoformat(str(day)),
                                   dt.time(), tz)
    except ValueError:
        return None


def _date(value: str) -> dt.date:
    """A calendar date the user typed, or a CLIError saying what was wanted.

    `--date tomorrow` and `--from "next week"` are the natural things to try,
    and argparse accepts both as plain strings. Bare `date.fromisoformat`
    then raised ValueError through main() as a traceback; `_parse_point`
    already guarded `create`/`update` this way, so `agenda` and `freebusy`
    were the two that still bit.
    """
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise CLIError(f"bad date: {value} (want YYYY-MM-DD)") from exc


def _day_bounds(date_str: str, tz: dt.tzinfo) -> tuple[str, str]:
    day = _date(date_str)
    return _midnight(day, tz), _midnight(day + dt.timedelta(days=1), tz)


def _to_rfc3339(value: str | None, tz: dt.tzinfo) -> str | None:
    """A bare YYYY-MM-DD means local midnight; a full instant passes through."""
    if value is None or "T" in value:
        return value
    return _midnight(_date(value), tz)


def _emit_window(args, time_min: str | None, time_max: str | None,
                 limit: int | None, query: str | None = None) -> None:
    params = {"singleEvents": "true", "orderBy": "startTime"}
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max
    if query:
        params["q"] = query
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


def cmd_search(args) -> int:
    tz = _zone(args.tz)
    _emit_window(args, _to_rfc3339(getattr(args, "from"), tz),
                 _to_rfc3339(args.to, tz), args.max, query=args.query)
    return 0


def cmd_create_calendar(args) -> int:
    """Make a new secondary calendar (`create` makes an *event* on one)."""
    body: dict = {"summary": args.summary}
    if args.description:
        body["description"] = args.description
    if args.tz:
        # Validated rather than passed through: Google accepts an unknown zone
        # name here and silently falls back to the account default, so a typo
        # would otherwise produce a calendar quietly set to the wrong zone.
        body["timeZone"] = str(_zone(args.tz))
    created = Client.for_args(args).post(f"{BASE}/calendars", json_body=body)
    confirm("created", created.get("id"), created.get("summary"))
    return 0


def cmd_delete_calendar(args) -> int:
    """Destroy a calendar for everyone — not the same as `unsubscribe`."""
    Client.for_args(args).delete(_cal_url(args.calendar))
    confirm("deleted calendar", args.calendar)
    return 0


def cmd_subscribe(args) -> int:
    """Add an existing calendar to this account's list. Nothing is created."""
    body: dict = {"id": args.calendar}
    if args.color:
        body["colorId"] = args.color
    entry = Client.for_args(args).post(f"{BASE}/users/me/calendarList",
                                       json_body=body)
    confirm("subscribed to", entry.get("id") or args.calendar,
            entry.get("summary"))
    return 0


def cmd_unsubscribe(args) -> int:
    """Drop a calendar from this account's list; the calendar itself stays."""
    Client.for_args(args).delete(
        f"{BASE}/users/me/calendarList/{quote_id(args.calendar)}")
    confirm("unsubscribed from", args.calendar)
    return 0


def _blocks_time(event: dict, email: str) -> bool:
    """Whether an event actually occupies the slot it sits in.

    Three kinds of entry hold a place on the grid without claiming the time,
    and counting them would bury the real double-bookings under noise: one
    that was cancelled, one its organiser marked "free" rather than "busy",
    and one this account has already declined.
    """
    if event.get("status") == "cancelled":
        return False
    if event.get("transparency") == "transparent":
        return False
    for attendee in event.get("attendees", []):
        if attendee.get("self") or (email and attendee.get("email") == email):
            return attendee.get("responseStatus") != "declined"
    return True


def cmd_conflicts(args) -> int:
    """Overlapping events in a window — the double-bookings, as pairs.

    Two events clash when each starts before the other ends, strictly: a
    meeting that ends exactly as the next begins is a full day, not a
    conflict, and reporting it would make the command useless by lunchtime.
    """
    tz = _zone(args.tz)
    today = dt.datetime.now(tz).date()
    time_min = _to_rfc3339(getattr(args, "from") or today.isoformat(), tz)
    time_max = _to_rfc3339(
        args.to or (today + dt.timedelta(days=CONFLICT_DAYS)).isoformat(), tz)
    client = Client.for_args(args)
    spans = []
    for event in client.paged(_cal_url(args.calendar, "/events"),
                              params={"singleEvents": "true",
                                      "orderBy": "startTime",
                                      "timeMin": time_min,
                                      "timeMax": time_max},
                              limit=args.max):
        if not _blocks_time(event, client.email):
            continue
        # All-day events overlap every meeting of the day by definition, so
        # holidays and PTO would drown out the real clashes unless asked for.
        if "date" in event.get("start", {}) and not args.include_all_day:
            continue
        start = _instant(event.get("start", {}), tz)
        end = _instant(event.get("end", {}), tz)
        if start is not None and end is not None:
            spans.append((start, end, event))

    spans.sort(key=lambda span: span[0])
    rows = []
    for index, (_start, end, event) in enumerate(spans):
        for other_start, other_end, other in spans[index + 1:]:
            if other_start >= end:
                # Sorted by start: everything further along starts later
                # still, so nothing after this can reach back into `event`.
                break
            rows.append({"from": _stamp(other_start, tz),
                         "to": _stamp(min(end, other_end), tz),
                         "event": event.get("summary", ""),
                         "id": event.get("id", ""),
                         "with": other.get("summary", ""),
                         "with_id": other.get("id", "")})
    emit(args, rows, CONFLICT_COLUMNS)
    return 0


def cmd_changed(args) -> int:
    """Events touched since a moment, deletions included.

    `singleEvents` is deliberately left off: expanding a recurrence into its
    instances discards the cancelled parent records, and a cancellation is
    the single most interesting thing "what changed" can report.
    """
    tz = _zone(args.tz)
    since = args.since or (
        dt.datetime.now(tz).date() - dt.timedelta(days=CHANGED_DAYS)
    ).isoformat()
    emit_paged(args, _cal_url(args.calendar, "/events"),
               [("ID", "id"), ("UPDATED", "updated"), ("STATUS", "status"),
                ("SUMMARY", "summary"), ("START", lambda e: _when(e))],
               params={"showDeleted": "true", "orderBy": "updated",
                       "updatedMin": _to_rfc3339(since, tz)},
               limit=args.max)
    return 0


def _timed_span(args, tz: dt.tzinfo) -> tuple[dict, dict]:
    """(start, end) slots for the event types that cannot be all-day."""
    slots = []
    for field in ("start", "end"):
        value = getattr(args, field)
        kind, point = _parse_point(value)
        if kind != "dateTime":
            raise CLIError(
                f"--{field} must name a time (YYYY-MM-DDTHH:MM): {value} is a "
                "whole day, and out-of-office and focus-time blocks are timed")
        slots.append(_slot(kind, point, tz))
    return slots[0], slots[1]


def _create_special(args, event_type: str, props_key: str,
                    props: dict) -> int:
    """Create one of Google's typed blocks — the shape is the same for both."""
    tz = _zone(args.tz)
    start, end = _timed_span(args, tz)
    body = {"summary": args.summary, "eventType": event_type,
            "start": start, "end": end,
            props_key: {"autoDeclineMode": DECLINE_MODES[args.decline],
                        **props}}
    created = Client.for_args(args).post(_cal_url(args.calendar, "/events"),
                                         json_body=body)
    confirm("created", created.get("id"), created.get("htmlLink"))
    return 0


def cmd_out_of_office(args) -> int:
    props = {"declineMessage": args.message} if args.message else {}
    return _create_special(args, "outOfOffice", "outOfOfficeProperties", props)


def cmd_focus_time(args) -> int:
    props = {}
    if args.message:
        props["declineMessage"] = args.message
    if args.chat:
        props["chatStatus"] = args.chat
    return _create_special(args, "focusTime", "focusTimeProperties", props)


def cmd_acl_list(args) -> int:
    emit_paged(args, _cal_url(args.calendar, "/acl"),
               [("ID", "id"), ("ROLE", "role"),
                ("TYPE", lambda r: r.get("scope", {}).get("type", "")),
                ("WHO", lambda r: r.get("scope", {}).get("value", ""))])
    return 0


def cmd_acl_add(args) -> int:
    scope: dict = {"type": args.type}
    if args.type == "default":
        # "default" is the entire scope — it means "anybody" — and Google
        # rejects the rule if a value rides along with it.
        if args.scope:
            raise CLIError("--type default takes no scope: it already means "
                           "everyone (public free/busy or more)")
    elif not args.scope:
        raise CLIError(f"--type {args.type} needs a scope "
                       "(an email address, a group address, or a domain)")
    else:
        scope["value"] = args.scope
    rule = Client.for_args(args).post(_cal_url(args.calendar, "/acl"),
                                      json_body={"role": args.role,
                                                 "scope": scope})
    confirm("granted", args.role, "to", rule.get("id") or args.scope,
            "on", args.calendar)
    return 0


def cmd_acl_remove(args) -> int:
    Client.for_args(args).delete(
        _cal_url(args.calendar, f"/acl/{quote_id(args.rule)}"))
    confirm("removed", args.rule, "from", args.calendar)
    return 0


def _color_order(entry: tuple) -> tuple:
    """Sort colour ids as the numbers they are, so 11 follows 2, not 1.

    They arrive as strings, and only Google decides what is in there; an id
    that is not numeric sorts last by name rather than raising.
    """
    key = entry[0]
    return (0, int(key), "") if key.isdigit() else (1, 0, key)


def cmd_colors(args) -> int:
    """The two fixed palettes: `event` colours an event, `calendar` a calendar.

    The ids are what `subscribe --color` and the API's own colorId fields
    take, and they are meaningless without this table — nothing else says
    that event colour 11 is red.
    """
    palette = Client.for_args(args).get(f"{BASE}/colors")
    rows = []
    for kind in ("calendar", "event"):
        if args.kind not in (None, kind):
            continue
        for color_id, spec in sorted(palette.get(kind, {}).items(),
                                     key=_color_order):
            rows.append({"kind": kind, "id": color_id,
                         "background": spec.get("background", ""),
                         "foreground": spec.get("foreground", "")})
    emit(args, rows, [("KIND", "kind"), ("ID", "id"),
                      ("BACKGROUND", "background"),
                      ("FOREGROUND", "foreground")])
    return 0


def cmd_get(args) -> int:
    event = Client.for_args(args).get(_event_url(args))
    emit_obj(args, {"id": event.get("id"), "summary": event.get("summary"),
                    "start": _when(event), "end": _when(event, "end"),
                    "location": event.get("location", ""),
                    "description": event.get("description", "")})
    return 0


def cmd_delete(args) -> int:
    Client.for_args(args).delete(_event_url(args))
    confirm("deleted", args.id)
    return 0


def cmd_move(args) -> int:
    """Hand an event to another calendar, keeping its id and its guest list."""
    moved = Client.for_args(args).post(_event_url(args, "/move"),
                                       params={"destination": args.to})
    confirm("moved", moved.get("id") or args.id, "to", args.to)
    return 0


def cmd_update(args) -> int:
    tz = _zone(args.tz)
    body: dict = {}
    for field in ("summary", "location", "description"):
        value = getattr(args, field)
        if value is not None:
            body[field] = value
    for field in ("start", "end"):
        value = getattr(args, field)
        if value is not None:
            kind, point = _parse_point(value)
            body[field] = _slot(kind, point, tz)
    if not body:
        raise CLIError("nothing to update (pass --summary, --start, --end, "
                       "--location, or --description)")
    Client.for_args(args).patch(_event_url(args), json_body=body)
    confirm("updated", args.id)
    return 0


def cmd_respond(args) -> int:
    client = Client.for_args(args)
    url = _event_url(args)
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
    tz = _zone(args.tz)
    body = {"timeMin": _to_rfc3339(getattr(args, "from"), tz),
            "timeMax": _to_rfc3339(args.to, tz),
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
    register_service(subparsers, "calendar",
                     "calendars, events, agenda, conflicts, sharing", [
        Cmd("calendars", cmd_calendars, "list calendars"),
        Cmd("events", cmd_events, "list events in a time window",
            (CALENDAR_FLAG,
             arg("--from", dest="from", metavar="WHEN",
                 help="RFC3339 or YYYY-MM-DD lower bound"),
             arg("--to", help="RFC3339 or YYYY-MM-DD upper bound"),
             TZ_FLAG, max_flag(50))),
        Cmd("agenda", cmd_agenda, "events for one day (default: today)",
            (CALENDAR_FLAG, arg("--date", help="YYYY-MM-DD"), TZ_FLAG)),
        Cmd("search", cmd_search, "search events by text",
            (arg("query", help="free text matched against summary, "
                               "description, location and attendees"),
             CALENDAR_FLAG,
             arg("--from", dest="from", metavar="WHEN",
                 help="RFC3339 or YYYY-MM-DD lower bound"),
             arg("--to", metavar="WHEN",
                 help="RFC3339 or YYYY-MM-DD upper bound"),
             TZ_FLAG, max_flag(50))),
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
             arg("--location"), arg("--description"), TZ_FLAG)),
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
                 help="comma-separated calendar ids (default: primary)"),
             TZ_FLAG)),
        Cmd("delete", cmd_delete, "delete an event", (CALENDAR_FLAG, arg("id"))),
        Cmd("move", cmd_move, "move an event to another calendar",
            (arg("id"),
             arg("--to", metavar="CALENDAR", required=True,
                 help="destination calendar id"),
             arg("--calendar", default="primary",
                 help="calendar the event is on now (default: primary)"))),
        Cmd("create-calendar", cmd_create_calendar,
            "create a calendar (not an event)",
            (arg("--summary", required=True, help="the calendar's name"),
             arg("--description"),
             arg("--tz", metavar="NAME",
                 help="IANA timezone the calendar defaults to, e.g. "
                      "America/New_York"))),
        Cmd("delete-calendar", cmd_delete_calendar,
            "delete a calendar for everyone",
            (arg("calendar", help="calendar id"),)),
        Cmd("subscribe", cmd_subscribe,
            "add an existing calendar to your calendar list",
            (arg("calendar", help="calendar id"),
             arg("--color", metavar="ID",
                 help="colorId to show it in (see `calendar colors`)"))),
        Cmd("unsubscribe", cmd_unsubscribe,
            "remove a calendar from your calendar list",
            (arg("calendar", help="calendar id"),)),
        Group("acl", "manage who a calendar is shared with", (
            Cmd("list", cmd_acl_list, "list sharing rules",
                (CALENDAR_FLAG,)),
            Cmd("add", cmd_acl_add, "share a calendar with someone",
                (arg("scope", nargs="?",
                     help="email address, group address, or domain "
                          "(omit for --type default)"),
                 arg("--role", required=True, choices=ACL_ROLES,
                     help="what the grantee may do"),
                 arg("--type", default="user", choices=SCOPE_TYPES,
                     help="who the scope names (default: user)"),
                 CALENDAR_FLAG)),
            Cmd("remove", cmd_acl_remove, "revoke a sharing rule",
                (arg("rule", help="rule id, e.g. user:alice@example.com"),
                 CALENDAR_FLAG)),
        )),
        Cmd("colors", cmd_colors, "list the available event/calendar colors",
            (arg("--kind", choices=["event", "calendar"],
                 help="show only one palette (default: both)"),)),
        Cmd("conflicts", cmd_conflicts,
            "find overlapping events in a window",
            (CALENDAR_FLAG,
             arg("--from", dest="from", metavar="WHEN",
                 help="RFC3339 or YYYY-MM-DD lower bound (default: today)"),
             arg("--to", metavar="WHEN",
                 help="RFC3339 or YYYY-MM-DD upper bound "
                      f"(default: {CONFLICT_DAYS} days out)"),
             arg("--include-all-day", action="store_true",
                 help="count all-day events too (holidays and PTO overlap "
                      "everything, so they are skipped by default)"),
             TZ_FLAG, max_flag(250))),
        Cmd("changed", cmd_changed,
            "events changed recently, deletions included",
            (CALENDAR_FLAG,
             arg("--since", metavar="WHEN",
                 help="RFC3339 or YYYY-MM-DD lower bound on the last "
                      f"change (default: {CHANGED_DAYS} days ago)"),
             TZ_FLAG, max_flag(50))),
        Cmd("out-of-office", cmd_out_of_office,
            "block time as out of office",
            (arg("--summary", default="Out of office"),
             *SPECIAL_EVENT_ARGS)),
        Cmd("focus-time", cmd_focus_time, "block time as focus time",
            (arg("--summary", default="Focus time"), *SPECIAL_EVENT_ARGS,
             arg("--chat", choices=["available", "doNotDisturb"],
                 help="chat status while the block is on"))),
    ])
