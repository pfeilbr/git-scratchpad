"""`gsuite workflow` — cross-service helpers: one answer from several APIs.

Every other service module wraps exactly one Google API. These wrap two or
more: a standup report is Calendar *and* Tasks, a meeting prep is Calendar
*and* Drive. That is the whole point — the questions people actually ask
("what does my day look like?") do not respect API boundaries.

Nothing here speaks to Google in its own words. Each command borrows the URL
builders, day bounds and field readers from the service module that already
owns that API — including the underscore-prefixed ones, which mark a helper
private to the CLI rather than private to a module. A composition that
restated `.../calendars/{id}/events` would be a second place to fix the next
time an id needs escaping differently, and this project has already paid once
for a duplicated date window: the local-midnight bug in `calendar`. Borrowing
means these commands inherit that fix instead of re-earning it.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import re

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, arg, register_service
from gsuite.errors import APIError, CLIError
from gsuite.output import emit, emit_obj
from gsuite.services import calendar, chat, drive, gmail, tasks
from gsuite.services._common import resource_path

# Statuses that mean "you were not allowed to ask", as opposed to any other
# way a request can fail. Only these earn the re-login advice below.
_AUTHORIZATION_STATUSES = {401, 403}

# All that is wanted of a linked file: what to call it and where to open it.
_FILE_FIELDS = "name,webViewLink"

# How many linked files one meeting may cost in Drive round trips. An agenda
# that pastes a dozen links is a reading list, not a briefing, and a prep
# command that stalls is one nobody runs before walking into the room.
MAX_LINKED_FILES = 10

# The two shapes a Drive link actually takes in an invitation: `/d/<id>/edit`
# for anything opened in an editor, and `open?id=<id>` for the share dialog's
# copy. Deliberately narrow — this reads other people's prose, so guessing at
# a looser pattern would turn ordinary text into bogus Drive lookups.
_DRIVE_LINK = re.compile(
    r"https://(?:docs|drive)\.google\.com/\S*?(?:/d/|[?&]id=)([\w-]{10,})")

MAX_TASKS_FLAG = arg("--max-tasks", type=int, default=25, metavar="N",
                     help="maximum open tasks to include (default: 25)")


@contextlib.contextmanager
def _step(service: str, needs: tuple[str, ...]):
    """Run one leg of a composition, naming the API it was talking to.

    A composition stops at the first service the account has not authorized,
    and Google's reply knows nothing about the ones it never reached: the 403
    that ends `workflow standup-report` halfway through reads exactly like a
    403 from `gsuite tasks list`. A user who acts on that text alone grants
    Tasks, re-runs, and discovers Calendar was missing too. The command knows
    both services before it sends anything, so it says so once.

    Only authorization failures get that advice — telling someone to log in
    again because a calendar id was misspelled would be worse than silence.
    Every other failure still gets the leg's name, which is the part Google
    cannot supply.

    The re-raise is a plain `CLIError`: once the message is about the
    composition rather than about one request, `APIError.status` no longer
    describes it.
    """
    try:
        yield
    except CLIError as exc:
        hint = ""
        if isinstance(exc, APIError) and exc.status in _AUTHORIZATION_STATUSES:
            hint = (f" — this command also needs {', '.join(needs)}; "
                    f"authorize them in one go with `gsuite auth login "
                    f"--services {','.join(needs)}`")
        raise CLIError(f"{service}: {exc}{hint}") from exc


def _events(client: Client, args, time_min: str, time_max: str | None,
            limit: int | None = None) -> list[dict]:
    """Single, ordered events in a window, through Calendar's own URL builder.

    `singleEvents` expands a recurring series into the occurrences that
    actually fall in the window; without it a weekly standup arrives once, as
    the master event, dated whenever the series began. An open-ended window
    (`time_max` of None) is how "the next one, whenever it is" is asked for.
    """
    params = {"singleEvents": "true", "orderBy": "startTime",
              "timeMin": time_min}
    if time_max:
        params["timeMax"] = time_max
    return list(client.paged(calendar._cal_url(args.calendar, "/events"),
                             params=params, limit=limit))


# -- standup-report ----------------------------------------------------------

STANDUP_NEEDS = ("calendar", "tasks")


def cmd_standup_report(args) -> int:
    client = Client.for_args(args)
    tz = calendar._zone(args.tz)
    # "Today" is a fact about the effective zone, and a day runs from local
    # midnight to local midnight. Calendar resolves both; recomputing them
    # here is how the UTC-midnight bug got written the first time.
    date = args.date or dt.datetime.now(tz).date().isoformat()
    time_min, time_max = calendar._day_bounds(date, tz)

    with _step("calendar", STANDUP_NEEDS):
        meetings = _events(client, args, time_min, time_max)
    with _step("tasks", STANDUP_NEEDS):
        open_tasks = list(client.paged(tasks._list_url(args, "/tasks"),
                                       params={"showCompleted": "false"},
                                       limit=args.max_tasks))

    rows = [{"kind": "meeting", "when": calendar._when(event),
             "item": event.get("summary", "")} for event in meetings]
    rows += [{"kind": "task", "when": task.get("due", ""),
              "item": task.get("title", "")} for task in open_tasks]
    emit(args, rows, [("KIND", "kind"), ("WHEN", "when"), ("ITEM", "item")])
    return 0


# -- meeting-prep ------------------------------------------------------------

PREP_NEEDS = ("calendar", "drive")


def _linked_files(event: dict) -> dict[str, str]:
    """{file id: the title the invitation gave it}, in the order they appear.

    Two places hold the same kind of thing. `attachments` is the structured
    one — Calendar's own "add a file" — and carries a title. The rest are
    links somebody pasted into the agenda, which carry nothing but an id.
    Attachments go first so their titles survive the de-duplication when the
    same document is both attached and mentioned.
    """
    found: dict[str, str] = {}
    for attachment in event.get("attachments") or []:
        file_id = attachment.get("fileId")
        if file_id:
            found.setdefault(file_id, attachment.get("title", ""))
    for file_id in _DRIVE_LINK.findall(event.get("description") or ""):
        found.setdefault(file_id, "")
    return dict(list(found.items())[:MAX_LINKED_FILES])


def _describe_file(client: Client, file_id: str, fallback: str) -> str:
    """One linked file as `name (link)`, asking Drive what it is called now.

    The title inside an invitation is a copy taken when the file was
    attached; Drive holds the name it has today. The lookup can also fail on
    its own: attachments outlive access, so a file shared with the room but
    not with you answers 404. That is one link going quiet, not a reason to
    abandon the briefing five minutes before the meeting — fall back to
    whatever the invitation said. Anything else (a scope refusal above all)
    still propagates, because that one is about the account, not the file.
    """
    try:
        meta = client.get(f"{drive.BASE}/files/{quote_id(file_id)}",
                          params=drive._with_shared({"fields": _FILE_FIELDS}))
    except APIError as exc:
        if exc.status != 404:
            raise
        return f"{fallback or file_id} (unavailable)"
    link = meta.get("webViewLink", "")
    name = meta.get("name") or fallback or file_id
    return f"{name} ({link})" if link else name


def _attendee(attendee: dict) -> str:
    """One attendee as `who (response)` — all that matters before walking in."""
    who = attendee.get("displayName") or attendee.get("email") or ""
    status = attendee.get("responseStatus")
    return f"{who} ({status})" if who and status else who


def cmd_meeting_prep(args) -> int:
    client = Client.for_args(args)
    tz = calendar._zone(args.tz)
    # "The next meeting" is the first event that has not started yet, and
    # "yet" is a moment in the effective zone — a bound with no offset would
    # be read as UTC and skip (or invent) hours of the day.
    now = dt.datetime.now(tz).replace(microsecond=0).isoformat()
    with _step("calendar", PREP_NEEDS):
        # Ordered, so one event is enough; paging further would only cost a
        # round trip to learn about meetings this command is not about.
        upcoming = _events(client, args, now, None, limit=1)
    if not upcoming:
        print("no upcoming meetings")
        return 0
    event = upcoming[0]

    files = []
    with _step("drive", PREP_NEEDS):
        for file_id, title in _linked_files(event).items():
            files.append(_describe_file(client, file_id, title))

    emit_obj(args, {
        "summary": event.get("summary", ""),
        "start": calendar._when(event),
        "end": calendar._when(event, "end"),
        "location": event.get("location", ""),
        "attendees": ", ".join(
            filter(None, (_attendee(a) for a in event.get("attendees") or []))),
        "files": ", ".join(files),
        "agenda": event.get("description", ""),
    })
    return 0


# -- weekly-digest -----------------------------------------------------------

DIGEST_NEEDS = ("calendar", "gmail")

# Gmail keeps a running count on every label, so the number of unread
# messages is one cheap read of the system UNREAD label. The alternative —
# paging `messages.list?q=is:unread` — costs a request per hundred messages
# to arrive at the same figure, and `resultSizeEstimate` is, as named, an
# estimate.
UNREAD_LABEL_URL = f"{gmail.BASE}/labels/UNREAD"


def _week_bounds(date_str: str) -> tuple[dt.date, dt.date]:
    """(Monday, the following Monday) for the week `date_str` falls in.

    Dates only. The two are turned into instants by `calendar._midnight`,
    which is what puts the local offset on them.
    """
    day = calendar._date(date_str)
    monday = day - dt.timedelta(days=day.weekday())
    return monday, monday + dt.timedelta(days=7)


def _per_day(events: list[dict]) -> str:
    """The week's shape in one line: `2026-01-05 (2), 2026-01-07 (1)`.

    A week of meetings listed one per row buries the thing a digest is for:
    which days are already gone. Counting them keeps that visible without
    the output growing with the calendar. The date is sliced off the start
    rather than parsed, because a start this command cannot read is not
    worth an error — an all-day event and a timed one both begin with
    YYYY-MM-DD, and anything else simply does not get a day.
    """
    counts: dict[str, int] = {}
    for event in events:
        day = calendar._when(event)[:10]
        if day:
            counts[day] = counts.get(day, 0) + 1
    return ", ".join(f"{day} ({n})" for day, n in sorted(counts.items()))


def cmd_weekly_digest(args) -> int:
    client = Client.for_args(args)
    tz = calendar._zone(args.tz)
    date = args.date or dt.datetime.now(tz).date().isoformat()
    monday, next_monday = _week_bounds(date)

    with _step("calendar", DIGEST_NEEDS):
        meetings = _events(client, args, calendar._midnight(monday, tz),
                           calendar._midnight(next_monday, tz))
    with _step("gmail", DIGEST_NEEDS):
        unread = client.get(UNREAD_LABEL_URL)

    emit_obj(args, {
        "from": monday.isoformat(),
        # The last day of the week, not the exclusive bound sent to Google:
        # "to: 2026-01-12" would read as a week of eight days.
        "to": (next_monday - dt.timedelta(days=1)).isoformat(),
        "meetings": len(meetings),
        "days": _per_day(meetings),
        "unread": unread.get("messagesUnread", ""),
    })
    return 0


# -- email-to-task -----------------------------------------------------------

TASK_NEEDS = ("gmail", "tasks")

# The permalink Gmail's own "copy link" produces. `#all` rather than
# `#inbox`, because the point of turning mail into a task is that the mail
# gets archived — a link into the inbox would go dead the moment it worked.
MESSAGE_LINK = "https://mail.google.com/mail/u/0/#all/{}"


def _delegate_args(args, **overrides):
    """`args` with the fields another service's handler expects filled in.

    A copy, not a mutation: the global flags (`-a`, `--json`, `--readonly`,
    `--fields`) have to reach the borrowed handler intact, and the caller's
    own namespace must not be left rewritten for whatever reads it next.
    """
    return argparse.Namespace(**{**vars(args), **overrides})


def cmd_email_to_task(args) -> int:
    client = Client.for_args(args)
    with _step("gmail", TASK_NEEDS):
        # Headers only: a task needs the subject and the sender, never the
        # body, and `metadata` is the cheaper format.
        message = gmail._fetch_meta(client, args.id)
    headers = gmail._headers(message)
    # Gmail's own wording for a subject line that is not there.
    title = args.title or headers.get("subject") or "(no subject)"
    notes = "\n".join(filter(None, [
        f"From: {headers['from']}" if headers.get("from") else "",
        f"Date: {headers['date']}" if headers.get("date") else "",
        # Escaped, because the id lands in a URL the user will click: a bare
        # `#` in it would cut the link off at the fragment.
        MESSAGE_LINK.format(quote_id(args.id)),
    ]))
    # Handed to `tasks add` rather than posted here, so the task list URL,
    # the bare-date-to-RFC3339 rule and the confirmation wording all stay in
    # the one module that owns them.
    with _step("tasks", TASK_NEEDS):
        return tasks.cmd_add(_delegate_args(args, title=title, notes=notes,
                                            due=args.due))


# -- file-announce -----------------------------------------------------------

ANNOUNCE_NEEDS = ("drive", "chat")


def cmd_file_announce(args) -> int:
    # The space is only checked where the message is posted, which is after
    # Drive has been asked about the file. Rejecting an impossible space up
    # front costs nothing and saves a request that was never going to help.
    resource_path(args.space)

    client = Client.for_args(args)
    with _step("drive", ANNOUNCE_NEEDS):
        meta = client.get(f"{drive.BASE}/files/{quote_id(args.id)}",
                          params=drive._with_shared({"fields": _FILE_FIELDS}))
    name = meta.get("name") or args.id
    link = meta.get("webViewLink", "")
    headline = f"{name} — {link}" if link else name
    # Delegated for the same reason as `email-to-task`: `chat send` owns the
    # space escaping, the message URL and the confirmation line.
    with _step("chat", ANNOUNCE_NEEDS):
        return chat.cmd_send(_delegate_args(
            args, text=f"{args.text}\n{headline}" if args.text else headline))


def register(subparsers) -> None:
    register_service(subparsers, "workflow",
                     "cross-service helpers built from several APIs", [
        Cmd("standup-report", cmd_standup_report,
            "today's meetings and open tasks, as one list",
            (calendar.CALENDAR_FLAG, arg("--date", help="YYYY-MM-DD"),
             calendar.TZ_FLAG, tasks.LIST_FLAG, MAX_TASKS_FLAG)),
        Cmd("meeting-prep", cmd_meeting_prep,
            "brief for your next meeting: agenda, attendees, linked files",
            (calendar.CALENDAR_FLAG, calendar.TZ_FLAG)),
        Cmd("weekly-digest", cmd_weekly_digest,
            "this week's meetings and the unread-mail count",
            (calendar.CALENDAR_FLAG,
             arg("--date",
                 help="YYYY-MM-DD — any day in the week (default: today)"),
             calendar.TZ_FLAG)),
        Cmd("email-to-task", cmd_email_to_task,
            "turn a Gmail message into a task that links back to it",
            (arg("id", help="Gmail message id"), tasks.LIST_FLAG,
             arg("--title", help="task title (default: the mail's subject)"),
             arg("--due", help="YYYY-MM-DD or RFC3339"))),
        Cmd("file-announce", cmd_file_announce,
            "post a Drive file's name and link to a Chat space",
            (arg("id", help="Drive file id"),
             arg("--space", required=True, help="e.g. spaces/AAAA"),
             arg("--text", help="a note to put above the link"))),
    ])
