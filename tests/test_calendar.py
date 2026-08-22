import datetime as dt
import json
from zoneinfo import ZoneInfo

import pytest

from gsuite.errors import CLIError
from gsuite.services import calendar as calendar_svc

BASE = "www.googleapis.com/calendar/v3"


@pytest.fixture
def cal(authed, fake_transport, run_cli):
    return fake_transport, run_cli


def test_calendars_list(cal):
    ft, run = cal
    ft.add("GET", "users/me/calendarList", {"items": [
        {"id": "primary-id", "summary": "Work", "primary": True},
        {"id": "team-id", "summary": "Team"},
    ]})
    out = run("calendar", "calendars")
    assert "Work" in out and "team-id" in out


def test_events_list_uses_time_window(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        {"id": "e1", "summary": "Standup",
         "start": {"dateTime": "2026-01-05T09:00:00Z"}},
        {"id": "e2", "summary": "Holiday", "start": {"date": "2026-01-06"}},
    ]})
    out = run("calendar", "events", "--from", "2026-01-05", "--to", "2026-01-07")
    url = ft.calls[0]["url"]
    assert "timeMin=2026-01-05" in url and "timeMax=2026-01-07" in url
    assert "singleEvents=true" in url
    assert "Standup" in out and "2026-01-06" in out


def test_events_create_timed(cal):
    ft, run = cal
    ft.add("POST", "calendars/primary/events", {"id": "new1",
                                                "htmlLink": "http://cal/x"})
    run("calendar", "create", "--summary", "Sync", "--tz", "America/New_York",
        "--start", "2026-01-05T09:00", "--end", "2026-01-05T09:30",
        "--attendees", "a@x.com,b@x.com", "--location", "HQ")
    body = json.loads(ft.calls[0]["data"])
    assert body["summary"] == "Sync"
    assert body["start"] == {"dateTime": "2026-01-05T09:00:00",
                             "timeZone": "America/New_York"}
    assert body["end"] == {"dateTime": "2026-01-05T09:30:00",
                           "timeZone": "America/New_York"}
    assert body["attendees"] == [{"email": "a@x.com"}, {"email": "b@x.com"}]
    assert body["location"] == "HQ"


def test_events_create_all_day_gets_exclusive_end(cal):
    ft, run = cal
    ft.add("POST", "calendars/primary/events", {"id": "new2"})
    run("calendar", "create", "--summary", "Offsite", "--start", "2026-01-05")
    body = json.loads(ft.calls[0]["data"])
    assert body["start"] == {"date": "2026-01-05"}
    assert body["end"] == {"date": "2026-01-06"}


def test_event_get_and_delete(cal):
    ft, run = cal
    ft.add("GET", "events/e1", {"id": "e1", "summary": "Standup",
                                "start": {"dateTime": "2026-01-05T09:00:00Z"},
                                "end": {"dateTime": "2026-01-05T09:15:00Z"}})
    assert "Standup" in run("calendar", "get", "e1")
    ft.add("DELETE", "events/e1", {})
    run("calendar", "delete", "e1")
    assert ft.calls[-1]["method"] == "DELETE"


def test_agenda_for_explicit_date(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        {"id": "e1", "summary": "Standup",
         "start": {"dateTime": "2026-01-05T09:00:00Z"},
         "end": {"dateTime": "2026-01-05T09:15:00Z"}},
    ]})
    out = run("calendar", "agenda", "--date", "2026-01-05")
    url = ft.calls[0]["url"]
    assert "timeMin=2026-01-05T00" in url and "timeMax=2026-01-06T00" in url
    assert "Standup" in out


def test_events_list_other_calendar(cal):
    ft, run = cal
    ft.add("GET", "calendars/team%40group.calendar.google.com/events",
           {"items": []})
    run("calendar", "events", "--calendar", "team@group.calendar.google.com")


def test_update_sends_only_provided_fields(cal, monkeypatch):
    ft, run = cal
    # No --tz here, so pin the resolved zone: the body must not depend on
    # which machine runs the suite.
    monkeypatch.setattr(calendar_svc, "_local_zone", lambda: ZoneInfo("Asia/Tokyo"))
    ft.add("PATCH", "events/e1", {"id": "e1"})
    out = run("calendar", "update", "e1", "--summary", "New name",
              "--start", "2026-01-05T10:00")
    call = ft.calls[0]
    assert call["method"] == "PATCH"
    body = json.loads(call["data"])
    assert body == {"summary": "New name",
                    "start": {"dateTime": "2026-01-05T10:00:00",
                              "timeZone": "Asia/Tokyo"}}
    assert "updated" in out and "e1" in out


def test_update_with_no_fields_errors(cal):
    ft, run = cal
    run("calendar", "update", "e1", expect=1)
    assert ft.calls == []


def test_respond_flips_own_attendee_entry(cal):
    ft, run = cal
    ft.add("GET", "events/e1", {"id": "e1", "attendees": [
        {"email": "b@x.com", "responseStatus": "accepted"},
        {"email": "a@x.com", "self": True, "responseStatus": "needsAction"},
    ]})
    ft.add("PATCH", "events/e1", {"id": "e1"})
    out = run("calendar", "respond", "e1", "--as", "declined")
    body = json.loads(ft.calls[-1]["data"])
    assert body == {"attendees": [
        {"email": "b@x.com", "responseStatus": "accepted"},
        {"email": "a@x.com", "self": True, "responseStatus": "declined"},
    ]}
    assert "declined" in out and "e1" in out


def test_respond_errors_when_not_an_attendee(cal):
    ft, run = cal
    ft.add("GET", "events/e2", {"id": "e2", "attendees": [
        {"email": "b@x.com", "responseStatus": "accepted"},
    ]})
    run("calendar", "respond", "e2", "--as", "accepted", expect=1)
    assert all(c["method"] != "PATCH" for c in ft.calls)


def test_freebusy_body_and_output(cal, monkeypatch):
    ft, run = cal
    # No --tz here, so pin the resolved zone: the window is a fact about the
    # user's day, and this test is about the body shape and the rows.
    monkeypatch.setattr(calendar_svc, "_local_zone", lambda: ZoneInfo("UTC"))
    ft.add("POST", "freeBusy", {"calendars": {
        "primary": {"busy": [
            {"start": "2026-01-05T09:00:00Z", "end": "2026-01-05T09:30:00Z"},
            {"start": "2026-01-05T13:00:00Z", "end": "2026-01-05T14:00:00Z"},
        ]},
        "team@x.com": {"busy": []},
    }})
    out = run("calendar", "freebusy", "--from", "2026-01-05",
              "--to", "2026-01-06", "--calendars", "primary,team@x.com")
    body = json.loads(ft.calls[0]["data"])
    assert body == {"timeMin": "2026-01-05T00:00:00Z",
                    "timeMax": "2026-01-06T00:00:00Z",
                    "items": [{"id": "primary"}, {"id": "team@x.com"}]}
    lines = [l for l in out.splitlines() if l.startswith("primary")]
    assert len(lines) == 2
    assert "2026-01-05T09:00:00Z" in lines[0]
    assert "2026-01-05T09:30:00Z" in lines[0]
    assert not [l for l in out.splitlines() if l.startswith("team@x.com")]


def test_freebusy_defaults_to_primary(cal):
    ft, run = cal
    ft.add("POST", "freeBusy", {"calendars": {"primary": {"busy": []}}})
    run("calendar", "freebusy", "--from", "2026-01-05", "--to", "2026-01-06")
    body = json.loads(ft.calls[0]["data"])
    assert body["items"] == [{"id": "primary"}]


# -- timezone handling -------------------------------------------------------
#
# A day starts at *local* midnight, so every bound must carry a real UTC
# offset. These tests never read the machine's zone: each drives an explicit
# --tz, or monkeypatches the one helper that resolves the system zone.


def test_agenda_tz_bounds_are_local_midnight_not_utc(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": []})
    run("calendar", "agenda", "--date", "2026-01-05", "--tz", "America/New_York")
    url = ft.calls[0]["url"]
    # ':' percent-encodes, so -05:00 arrives as -05%3A00.
    assert "timeMin=2026-01-05T00%3A00%3A00-05%3A00" in url
    assert "timeMax=2026-01-06T00%3A00%3A00-05%3A00" in url
    # regression: the old UTC-midnight form must not survive anywhere.
    assert "00%3A00%3A00Z" not in url and "00:00:00Z" not in url


def test_agenda_without_tz_uses_resolved_local_zone(cal, monkeypatch):
    ft, run = cal
    monkeypatch.setattr(calendar_svc, "_local_zone", lambda: ZoneInfo("Asia/Tokyo"))
    ft.add("GET", "calendars/primary/events", {"items": []})
    run("calendar", "agenda", "--date", "2026-01-05")
    url = ft.calls[0]["url"]
    assert "timeMin=2026-01-05T00%3A00%3A00%2B09%3A00" in url
    assert "timeMax=2026-01-06T00%3A00%3A00%2B09%3A00" in url
    assert "00%3A00%3A00Z" not in url


def test_agenda_default_date_is_today_in_the_effective_zone(cal):
    ft, run = cal
    zone = ZoneInfo("Pacific/Kiritimati")  # UTC+14 year-round
    ft.add("GET", "calendars/primary/events", {"items": []})
    before = dt.datetime.now(zone).date()
    run("calendar", "agenda", "--tz", "Pacific/Kiritimati")
    after = dt.datetime.now(zone).date()
    url = ft.calls[0]["url"]
    # Accept either date so a run straddling midnight cannot flake.
    assert any(f"timeMin={day.isoformat()}T00%3A00%3A00%2B14%3A00" in url
               for day in {before, after})


def test_events_bare_dates_get_the_offset_and_rfc3339_passes_through(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": []})
    run("calendar", "events", "--tz", "America/New_York",
        "--from", "2026-01-05", "--to", "2026-06-10T12:30:00Z")
    url = ft.calls[0]["url"]
    assert "timeMin=2026-01-05T00%3A00%3A00-05%3A00" in url
    assert "timeMin=2026-01-05T00%3A00%3A00Z" not in url
    # an explicit instant is already unambiguous — leave it alone.
    assert "timeMax=2026-06-10T12%3A30%3A00Z" in url


def test_create_timed_event_declares_its_timezone(cal, monkeypatch):
    ft, run = cal
    monkeypatch.setattr(calendar_svc, "_local_zone", lambda: ZoneInfo("Asia/Tokyo"))
    ft.add("POST", "calendars/primary/events", {"id": "n1"})
    run("calendar", "create", "--summary", "Sync",
        "--start", "2026-01-05T09:00", "--end", "2026-01-05T09:30")
    body = json.loads(ft.calls[0]["data"])
    assert body["start"] == {"dateTime": "2026-01-05T09:00:00",
                             "timeZone": "Asia/Tokyo"}
    assert body["end"] == {"dateTime": "2026-01-05T09:30:00",
                           "timeZone": "Asia/Tokyo"}

    ft.add("POST", "calendars/primary/events", {"id": "n2"})
    run("calendar", "create", "--summary", "Offsite", "--start", "2026-01-05",
        "--tz", "America/New_York")
    all_day = json.loads(ft.calls[1]["data"])
    assert all_day["start"] == {"date": "2026-01-05"}
    assert all_day["end"] == {"date": "2026-01-06"}
    assert "timeZone" not in json.dumps(all_day)


def test_local_zone_is_named_and_dst_aware(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    zone = calendar_svc._local_zone()
    # A fixed offset snapshotted from "now" would pin one of these two.
    assert calendar_svc._day_bounds("2026-01-05", zone)[0].endswith("-05:00")
    assert calendar_svc._day_bounds("2026-07-05", zone)[0].endswith("-04:00")
    # ...and Google only accepts an IANA name here, never an abbreviation.
    assert str(zone) == "America/New_York"


def test_unknown_timezone_is_a_clean_error(cal):
    ft, run = cal
    run("calendar", "agenda", "--date", "2026-01-05", "--tz", "Mars/Olympus",
        expect=1)
    assert ft.calls == []
    with pytest.raises(CLIError, match="Mars/Olympus"):
        calendar_svc._zone("Mars/Olympus")


def test_freebusy_bare_dates_use_the_requested_zone(cal):
    ft, run = cal
    ft.add("POST", "freeBusy", {"calendars": {"primary": {"busy": []}}})
    run("calendar", "freebusy", "--from", "2026-01-05", "--to", "2026-01-06",
        "--tz", "America/New_York")
    body = json.loads(ft.calls[0]["data"])
    # The window is the user's day, not UTC's: 00:00-05:00, not 00:00Z.
    assert body["timeMin"] == "2026-01-05T00:00:00-05:00"
    assert body["timeMax"] == "2026-01-06T00:00:00-05:00"


def test_freebusy_without_tz_uses_resolved_local_zone(cal, monkeypatch):
    ft, run = cal
    monkeypatch.setattr(calendar_svc, "_local_zone", lambda: ZoneInfo("Asia/Tokyo"))
    ft.add("POST", "freeBusy", {"calendars": {"primary": {"busy": []}}})
    run("calendar", "freebusy", "--from", "2026-01-05", "--to", "2026-01-06")
    body = json.loads(ft.calls[0]["data"])
    assert body["timeMin"] == "2026-01-05T00:00:00+09:00"
    assert body["timeMax"] == "2026-01-06T00:00:00+09:00"


def test_freebusy_tz_utc_keeps_the_z_form(cal):
    ft, run = cal
    ft.add("POST", "freeBusy", {"calendars": {"primary": {"busy": []}}})
    run("calendar", "freebusy", "--from", "2026-01-05",
        "--to", "2026-01-06T12:30:00Z", "--tz", "UTC")
    body = json.loads(ft.calls[0]["data"])
    # Asking for UTC still yields exactly what freebusy always sent.
    assert body["timeMin"] == "2026-01-05T00:00:00Z"
    # ...and an explicit instant is already unambiguous — leave it alone.
    assert body["timeMax"] == "2026-01-06T12:30:00Z"


def test_update_timed_start_declares_its_timezone(cal):
    ft, run = cal
    ft.add("PATCH", "events/e1", {"id": "e1"})
    run("calendar", "update", "e1", "--start", "2026-01-05T10:00",
        "--end", "2026-01-05T11:00", "--tz", "America/New_York")
    body = json.loads(ft.calls[0]["data"])
    # A naive dateTime would be read in the calendar's own zone, not the
    # caller's — name the zone the same way create does.
    assert body == {"start": {"dateTime": "2026-01-05T10:00:00",
                              "timeZone": "America/New_York"},
                    "end": {"dateTime": "2026-01-05T11:00:00",
                            "timeZone": "America/New_York"}}


def test_update_all_day_start_stays_a_bare_date(cal):
    ft, run = cal
    ft.add("PATCH", "events/e1", {"id": "e1"})
    run("calendar", "update", "e1", "--start", "2026-01-05",
        "--tz", "America/New_York")
    body = json.loads(ft.calls[0]["data"])
    # An all-day date names no zone, whatever --tz says.
    assert body == {"start": {"date": "2026-01-05"}}


# -- dates the user typed wrong ----------------------------------------------

@pytest.mark.parametrize("argv", [
    ("calendar", "agenda", "--date", "not-a-date"),
    ("calendar", "agenda", "--date", "2026-13-45"),
    ("calendar", "freebusy", "--from", "tomorrow", "--to", "2026-01-06"),
    ("calendar", "freebusy", "--from", "2026-01-05", "--to", "next week"),
    ("calendar", "changed", "--since", "yesterday"),
])
def test_unparseable_dates_are_clean_errors(cal, argv):
    """`--date tomorrow` is an ordinary typo, not a crash.

    `_parse_point` guards the date arguments of `create`/`update`, but
    `_day_bounds` and `_to_rfc3339` — the ones behind `agenda` and
    `freebusy` — called `date.fromisoformat` bare, so a value argparse
    happily accepted as a string reached the stdlib and raised ValueError
    through main().
    """
    ft, run = cal
    run(*argv, expect=1)
    assert ft.calls == [], "a bad date must be caught before any request"


def test_the_date_error_names_the_value_and_the_format(cal):
    ft, run = cal
    with pytest.raises(CLIError) as exc:
        calendar_svc._day_bounds("tomorrow", ZoneInfo("UTC"))
    assert "tomorrow" in str(exc.value) and "YYYY-MM-DD" in str(exc.value)


# -- ids in the URL path -----------------------------------------------------
#
# Calendar ids are email addresses and event ids are opaque strings, so both
# are user data that has to be escaped into a single path segment. `_cal_url`
# always did; the event id was interpolated raw, so an id containing a slash
# addressed a different endpoint than the one the command named.


@pytest.mark.parametrize("argv, method", [
    (("calendar", "get", "a/b"), "GET"),
    (("calendar", "delete", "a/b"), "DELETE"),
    (("calendar", "update", "a/b", "--summary", "x"), "PATCH"),
])
def test_event_id_is_escaped_as_one_path_segment(cal, argv, method):
    ft, run = cal
    ft.add(method, "events/a%2Fb", {"id": "a/b"})
    run(*argv)
    url = ft.calls[0]["url"]
    assert "events/a%2Fb" in url
    assert "events/a/b" not in url


@pytest.mark.parametrize("event_id, encoded", [
    ("a/b", "a%2Fb"),
    ("abc?x=1", "abc%3Fx%3D1"),
    ("abc#frag", "abc%23frag"),
    ("has space", "has%20space"),
    ("../../../oauth2/v1/tokeninfo", "..%2F..%2F..%2Foauth2%2Fv1%2Ftokeninfo"),
])
def test_event_id_cannot_break_out_of_its_path_segment(cal, event_id, encoded):
    """The characters that end a path, spelled out one by one.

    Unescaped, `?` starts a query string, `#` starts a fragment and `/`
    walks to a different endpoint — so the request would go somewhere other
    than the event the command named, and none of it raises, which is why
    the fuzzer stayed green over this for so long.
    """
    ft, run = cal
    ft.add("GET", f"events/{encoded}", {"id": event_id})
    run("calendar", "get", event_id)
    segment = ft.calls[0]["url"].split("/events/")[1]
    assert segment == encoded
    assert not any(ch in segment for ch in "?# ")


def test_move_escapes_the_event_id(cal):
    ft, run = cal
    ft.add("POST", "events/abc%3Fx%3D1/move", {"id": "abc?x=1"})
    run("calendar", "move", "abc?x=1", "--to", "team@x.com")
    assert "events/abc%3Fx%3D1/move" in ft.calls[0]["url"]


def test_respond_escapes_the_event_id(cal):
    ft, run = cal
    ft.add("GET", "events/a%2Fb", {"id": "a/b", "attendees": [
        {"email": "a@x.com", "self": True, "responseStatus": "needsAction"},
    ]})
    ft.add("PATCH", "events/a%2Fb", {"id": "a/b"})
    run("calendar", "respond", "a/b", "--as", "accepted")
    assert all("events/a%2Fb" in c["url"] for c in ft.calls)


# -- search ------------------------------------------------------------------


def test_search_passes_the_query_and_the_window(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        {"id": "e1", "summary": "Standup",
         "start": {"dateTime": "2026-01-05T09:00:00Z"}},
    ]})
    out = run("calendar", "search", "standup", "--from", "2026-01-05",
              "--to", "2026-01-31", "--tz", "UTC")
    url = ft.calls[0]["url"]
    assert "q=standup" in url
    assert "singleEvents=true" in url
    assert "timeMin=2026-01-05T00%3A00%3A00Z" in url
    assert "timeMax=2026-01-31T00%3A00%3A00Z" in url
    assert "Standup" in out


def test_search_without_a_window_sends_no_bounds(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": []})
    run("calendar", "search", "roadmap")
    url = ft.calls[0]["url"]
    assert "q=roadmap" in url
    assert "timeMin" not in url and "timeMax" not in url


def test_search_other_calendar_escapes_the_id(cal):
    ft, run = cal
    ft.add("GET", "calendars/team%40group.calendar.google.com/events",
           {"items": []})
    run("calendar", "search", "offsite",
        "--calendar", "team@group.calendar.google.com")


# -- move --------------------------------------------------------------------


def test_move_posts_to_move_with_the_destination(cal):
    ft, run = cal
    ft.add("POST", "events/e1/move", {"id": "e1"})
    out = run("calendar", "move", "e1",
              "--to", "team@group.calendar.google.com",
              "--calendar", "src@group.calendar.google.com")
    call = ft.calls[0]
    assert call["method"] == "POST"
    assert ("calendars/src%40group.calendar.google.com/events/e1/move"
            in call["url"])
    # The destination rides in the query string, where urlencode escapes it.
    assert "destination=team%40group.calendar.google.com" in call["url"]
    assert "moved" in out and "e1" in out


# -- calendars, as opposed to events -----------------------------------------
#
# Four commands that are easy to confuse with each other and with `create`.
# `create-calendar`/`delete-calendar` make and destroy a calendar; `subscribe`/
# `unsubscribe` only add or drop an existing one from *this* account's list,
# and leave the calendar itself alone. The endpoints differ accordingly, so
# these tests pin which collection each one touches.


def test_create_calendar_posts_summary_description_and_zone(cal):
    ft, run = cal
    ft.add("POST", "calendar/v3/calendars",
           {"id": "new@group.calendar.google.com", "summary": "Team"})
    out = run("calendar", "create-calendar", "--summary", "Team",
              "--description", "Team events", "--tz", "America/New_York")
    call = ft.calls[0]
    assert call["method"] == "POST"
    assert json.loads(call["data"]) == {"summary": "Team",
                                        "description": "Team events",
                                        "timeZone": "America/New_York"}
    assert "created" in out and "new@group.calendar.google.com" in out


def test_create_calendar_rejects_an_unknown_timezone(cal):
    ft, run = cal
    run("calendar", "create-calendar", "--summary", "Team",
        "--tz", "Mars/Olympus", expect=1)
    assert ft.calls == [], "a bad zone must be caught before any request"


def test_delete_calendar_targets_the_calendar_itself(cal):
    ft, run = cal
    ft.add("DELETE", "calendars/team%40group.calendar.google.com", {})
    out = run("calendar", "delete-calendar", "team@group.calendar.google.com")
    call = ft.calls[0]
    assert call["method"] == "DELETE"
    # Not the calendar *list* — that would merely unsubscribe.
    assert "calendarList" not in call["url"]
    assert "deleted" in out


def test_subscribe_adds_the_calendar_to_this_accounts_list(cal):
    ft, run = cal
    ft.add("POST", "users/me/calendarList",
           {"id": "team@x.com", "summary": "Team"})
    out = run("calendar", "subscribe", "team@x.com", "--color", "5")
    assert json.loads(ft.calls[0]["data"]) == {"id": "team@x.com",
                                               "colorId": "5"}
    assert "subscribed" in out and "team@x.com" in out


def test_unsubscribe_only_touches_the_calendar_list(cal):
    ft, run = cal
    ft.add("DELETE", "users/me/calendarList/team%40group.calendar.google.com",
           {})
    out = run("calendar", "unsubscribe", "team@group.calendar.google.com")
    call = ft.calls[0]
    assert call["method"] == "DELETE"
    assert "calendarList" in call["url"]
    assert "unsubscribed" in out


# -- sharing rules -----------------------------------------------------------


def test_acl_list_shows_the_role_and_who_holds_it(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/acl", {"items": [
        {"id": "user:alice@x.com", "role": "writer",
         "scope": {"type": "user", "value": "alice@x.com"}},
        {"id": "default", "role": "freeBusyReader",
         "scope": {"type": "default"}},
    ]})
    out = run("calendar", "acl", "list")
    assert "writer" in out and "alice@x.com" in out
    assert "freeBusyReader" in out and "default" in out


def test_acl_add_wraps_the_scope_in_its_type(cal):
    ft, run = cal
    ft.add("POST", "calendars/primary/acl", {"id": "user:bob@x.com"})
    out = run("calendar", "acl", "add", "bob@x.com", "--role", "writer")
    assert json.loads(ft.calls[0]["data"]) == {
        "role": "writer", "scope": {"type": "user", "value": "bob@x.com"}}
    assert "writer" in out and "bob@x.com" in out


def test_acl_add_domain_scope(cal):
    ft, run = cal
    ft.add("POST", "calendars/primary/acl", {"id": "domain:x.com"})
    run("calendar", "acl", "add", "x.com", "--type", "domain",
        "--role", "reader")
    assert json.loads(ft.calls[0]["data"]) == {
        "role": "reader", "scope": {"type": "domain", "value": "x.com"}}


def test_acl_add_default_scope_carries_no_value(cal):
    ft, run = cal
    ft.add("POST", "calendars/primary/acl", {"id": "default"})
    run("calendar", "acl", "add", "--type", "default",
        "--role", "freeBusyReader")
    # "default" already means everyone; Google rejects a value beside it.
    assert json.loads(ft.calls[0]["data"]) == {
        "role": "freeBusyReader", "scope": {"type": "default"}}


def test_acl_add_without_a_scope_is_a_clean_error(cal):
    ft, run = cal
    run("calendar", "acl", "add", "--role", "reader", expect=1)
    assert ft.calls == []


def test_acl_remove_escapes_the_rule_id(cal):
    ft, run = cal
    # Rule ids embed a colon ("user:alice@x.com"), which is one segment.
    ft.add("DELETE", "acl/user%3Aalice%40x.com", {})
    out = run("calendar", "acl", "remove", "user:alice@x.com")
    assert ft.calls[0]["method"] == "DELETE"
    assert "removed" in out


# -- colors ------------------------------------------------------------------


COLORS = {
    "event": {"11": {"background": "#dc2127", "foreground": "#1d1d1d"},
              "2": {"background": "#51b749", "foreground": "#1d1d1d"}},
    "calendar": {"1": {"background": "#ac725e", "foreground": "#1d1d1d"}},
}


def test_colors_lists_both_palettes_with_numeric_ids_in_order(cal):
    ft, run = cal
    ft.add("GET", "calendar/v3/colors", COLORS)
    out = run("calendar", "colors")
    lines = out.splitlines()
    assert lines[0].split() == ["KIND", "ID", "BACKGROUND", "FOREGROUND"]
    rows = [line.split() for line in lines[1:]]
    assert [r[0] for r in rows] == ["calendar", "event", "event"]
    # ids are numeric strings, so 11 must sort after 2, not after 1.
    assert [r[1] for r in rows] == ["1", "2", "11"]
    assert rows[0][2] == "#ac725e"


def test_colors_can_be_narrowed_to_one_kind(cal):
    ft, run = cal
    ft.add("GET", "calendar/v3/colors", COLORS)
    out = run("calendar", "colors", "--kind", "event")
    assert not [l for l in out.splitlines() if l.startswith("calendar")]
    assert len([l for l in out.splitlines() if l.startswith("event")]) == 2


# -- recently changed --------------------------------------------------------


def test_changed_asks_for_deletions_ordered_by_update_time(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        {"id": "e1", "summary": "Standup", "status": "confirmed",
         "updated": "2026-01-06T08:00:00Z",
         "start": {"dateTime": "2026-01-07T09:00:00Z"}},
        {"id": "e2", "summary": "Dropped", "status": "cancelled",
         "updated": "2026-01-06T09:00:00Z"},
    ]})
    out = run("calendar", "changed", "--since", "2026-01-05", "--tz", "UTC")
    url = ft.calls[0]["url"]
    assert "showDeleted=true" in url
    assert "orderBy=updated" in url
    assert "updatedMin=2026-01-05T00%3A00%3A00Z" in url
    # Expanding recurrences would hide the cancelled parent records, which
    # are exactly what "what changed" is being asked for.
    assert "singleEvents" not in url
    assert "cancelled" in out and "e2" in out
    assert "Standup" in out


def test_changed_defaults_to_the_last_week_in_the_effective_zone(cal,
                                                                monkeypatch):
    ft, run = cal
    zone = ZoneInfo("Asia/Tokyo")
    monkeypatch.setattr(calendar_svc, "_local_zone", lambda: zone)
    ft.add("GET", "calendars/primary/events", {"items": []})
    before = dt.datetime.now(zone).date()
    run("calendar", "changed")
    after = dt.datetime.now(zone).date()
    url = ft.calls[0]["url"]
    # A week back from local midnight — never UTC midnight.
    assert any(f"updatedMin={(day - dt.timedelta(days=7)).isoformat()}"
               "T00%3A00%3A00%2B09%3A00" in url for day in {before, after})
    assert "00%3A00%3A00Z" not in url


# -- out of office and focus time --------------------------------------------


def test_out_of_office_sets_the_event_type_and_decline_mode(cal):
    ft, run = cal
    ft.add("POST", "calendars/primary/events", {"id": "ooo1",
                                                "htmlLink": "http://cal/o"})
    out = run("calendar", "out-of-office", "--start", "2026-01-05T09:00",
              "--end", "2026-01-09T17:00", "--tz", "America/New_York",
              "--decline", "all", "--message", "Back Monday")
    body = json.loads(ft.calls[0]["data"])
    assert body["eventType"] == "outOfOffice"
    assert body["summary"] == "Out of office"
    assert body["start"] == {"dateTime": "2026-01-05T09:00:00",
                             "timeZone": "America/New_York"}
    assert body["outOfOfficeProperties"] == {
        "autoDeclineMode": "declineAllConflictingInvitations",
        "declineMessage": "Back Monday"}
    assert "created" in out and "ooo1" in out


def test_out_of_office_declines_nothing_unless_asked(cal):
    ft, run = cal
    ft.add("POST", "calendars/primary/events", {"id": "ooo2"})
    run("calendar", "out-of-office", "--start", "2026-01-05T09:00",
        "--end", "2026-01-05T17:00", "--tz", "UTC")
    body = json.loads(ft.calls[0]["data"])
    # Declining a colleague's meeting is not something a forgotten flag
    # should do on the user's behalf.
    assert body["outOfOfficeProperties"] == {"autoDeclineMode": "declineNone"}


def test_focus_time_carries_its_own_properties(cal):
    ft, run = cal
    ft.add("POST", "calendars/primary/events", {"id": "ft1"})
    run("calendar", "focus-time", "--start", "2026-01-05T09:00",
        "--end", "2026-01-05T11:00", "--tz", "UTC",
        "--summary", "Deep work", "--chat", "doNotDisturb")
    body = json.loads(ft.calls[0]["data"])
    assert body["eventType"] == "focusTime"
    assert body["summary"] == "Deep work"
    assert body["focusTimeProperties"] == {"autoDeclineMode": "declineNone",
                                           "chatStatus": "doNotDisturb"}
    assert "outOfOfficeProperties" not in body


@pytest.mark.parametrize("command", ["out-of-office", "focus-time"])
def test_special_events_reject_whole_day_dates(cal, command):
    """Both types are blocks of time; Google has no all-day form for them."""
    ft, run = cal
    run("calendar", command, "--start", "2026-01-05", "--end", "2026-01-06",
        expect=1)
    assert ft.calls == []


# -- conflicts ---------------------------------------------------------------
#
# What counts as an overlap is the whole substance of this command. Two
# meetings that merely touch are not a clash; an all-day event covers a
# *local* day, not a UTC one; and an event nobody is attending — cancelled,
# declined, or marked free — does not occupy the slot it sits in.


def _timed(event_id, summary, start, end, **extra):
    return {"id": event_id, "summary": summary,
            "start": {"dateTime": start}, "end": {"dateTime": end}, **extra}


def _all_day(event_id, summary, start, end):
    return {"id": event_id, "summary": summary,
            "start": {"date": start}, "end": {"date": end}}


def _rows(out):
    return out.splitlines()[1:]  # everything after the header line


def test_conflicts_reports_the_overlapping_span(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        _timed("e1", "Standup", "2026-01-05T09:00:00Z", "2026-01-05T09:30:00Z"),
        _timed("e2", "Design review", "2026-01-05T09:15:00Z",
               "2026-01-05T10:00:00Z"),
    ]})
    out = run("calendar", "conflicts", "--from", "2026-01-05",
              "--to", "2026-01-06", "--tz", "UTC")
    assert "singleEvents=true" in ft.calls[0]["url"]
    lines = out.splitlines()
    assert lines[0].split() == ["FROM", "TO", "EVENT", "ID",
                                "CONFLICTS-WITH", "WITH-ID"]
    assert len(_rows(out)) == 1
    row = _rows(out)[0]
    # The reported span is the overlap itself, not either event's own span.
    assert "2026-01-05T09:15:00Z" in row and "2026-01-05T09:30:00Z" in row
    assert "Standup" in row and "Design review" in row
    assert "e1" in row and "e2" in row


def test_conflicts_does_not_count_back_to_back_meetings(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        _timed("e1", "First", "2026-01-05T09:00:00Z", "2026-01-05T10:00:00Z"),
        _timed("e2", "Second", "2026-01-05T10:00:00Z", "2026-01-05T11:00:00Z"),
    ]})
    out = run("calendar", "conflicts", "--from", "2026-01-05",
              "--to", "2026-01-06", "--tz", "UTC")
    assert _rows(out) == [], "an event ending as the next begins is not a clash"


def test_conflicts_reports_every_overlapping_pair(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        _timed("e1", "One", "2026-01-05T09:00:00Z", "2026-01-05T10:00:00Z"),
        _timed("e2", "Two", "2026-01-05T09:15:00Z", "2026-01-05T10:15:00Z"),
        _timed("e3", "Three", "2026-01-05T09:30:00Z", "2026-01-05T10:30:00Z"),
    ]})
    out = run("calendar", "conflicts", "--from", "2026-01-05",
              "--to", "2026-01-06", "--tz", "UTC")
    assert len(_rows(out)) == 3


def test_conflicts_skips_all_day_events_by_default(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        _all_day("h1", "Holiday", "2026-01-05", "2026-01-06"),
        _timed("e1", "Standup", "2026-01-05T09:00:00Z", "2026-01-05T09:30:00Z"),
    ]})
    out = run("calendar", "conflicts", "--from", "2026-01-05",
              "--to", "2026-01-06", "--tz", "UTC")
    # A holiday overlaps every meeting that day; counted by default it would
    # bury the double-bookings the command exists to surface.
    assert _rows(out) == []


def test_conflicts_can_include_all_day_events(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        _all_day("h1", "Holiday", "2026-01-05", "2026-01-06"),
        _timed("e1", "Standup", "2026-01-05T09:00:00Z", "2026-01-05T09:30:00Z"),
    ]})
    out = run("calendar", "conflicts", "--from", "2026-01-05",
              "--to", "2026-01-06", "--tz", "UTC", "--include-all-day")
    rows = _rows(out)
    assert len(rows) == 1
    # The whole meeting falls inside the day, so the meeting *is* the overlap.
    assert "2026-01-05T09:00:00Z" in rows[0]
    assert "2026-01-05T09:30:00Z" in rows[0]


def test_an_all_day_event_covers_the_local_day_not_the_utc_day(cal):
    """The timezone bug class, in overlap form.

    An all-day event on 2026-01-05 in Tokyo runs from 15:00Z on the 4th to
    15:00Z on the 5th. A 16:00Z meeting on the 5th therefore falls *outside*
    it — though a UTC-midnight reading of the same date would say it clashes.
    """
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        _all_day("h1", "Holiday", "2026-01-05", "2026-01-06"),
        _timed("e1", "Late call", "2026-01-05T16:00:00Z",
               "2026-01-05T17:00:00Z"),
    ]})
    out = run("calendar", "conflicts", "--from", "2026-01-05",
              "--to", "2026-01-07", "--tz", "Asia/Tokyo", "--include-all-day")
    assert _rows(out) == []


def test_conflicts_ignores_events_that_do_not_occupy_their_slot(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        _timed("e1", "Standup", "2026-01-05T09:00:00Z", "2026-01-05T09:30:00Z"),
        _timed("e2", "Declined", "2026-01-05T09:00:00Z",
               "2026-01-05T10:00:00Z",
               attendees=[{"email": "a@x.com", "self": True,
                           "responseStatus": "declined"}]),
        _timed("e3", "Marked free", "2026-01-05T09:00:00Z",
               "2026-01-05T10:00:00Z", transparency="transparent"),
        _timed("e4", "Cancelled", "2026-01-05T09:00:00Z",
               "2026-01-05T10:00:00Z", status="cancelled"),
    ]})
    out = run("calendar", "conflicts", "--from", "2026-01-05",
              "--to", "2026-01-06", "--tz", "UTC")
    assert _rows(out) == []


def test_conflicts_still_counts_a_meeting_the_user_accepted(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        _timed("e1", "Standup", "2026-01-05T09:00:00Z", "2026-01-05T09:30:00Z"),
        _timed("e2", "Review", "2026-01-05T09:00:00Z", "2026-01-05T10:00:00Z",
               attendees=[{"email": "a@x.com", "self": True,
                           "responseStatus": "accepted"}]),
    ]})
    out = run("calendar", "conflicts", "--from", "2026-01-05",
              "--to", "2026-01-06", "--tz", "UTC")
    assert len(_rows(out)) == 1


def test_conflicts_skips_events_it_cannot_place_in_time(cal):
    ft, run = cal
    ft.add("GET", "calendars/primary/events", {"items": [
        {"id": "bad", "summary": "Broken", "start": {"dateTime": "whenever"},
         "end": {"dateTime": "whenever"}},
        {"id": "empty", "summary": "No times"},
        _timed("e1", "Standup", "2026-01-05T09:00:00Z", "2026-01-05T09:30:00Z"),
        _timed("e2", "Review", "2026-01-05T09:15:00Z", "2026-01-05T10:00:00Z"),
    ]})
    out = run("calendar", "conflicts", "--from", "2026-01-05",
              "--to", "2026-01-06", "--tz", "UTC")
    # A reply we cannot read is the server's problem, not the user's: drop
    # the event rather than fail the whole report.
    assert len(_rows(out)) == 1


def test_conflicts_defaults_to_the_week_ahead_in_the_effective_zone(
        cal, monkeypatch):
    ft, run = cal
    zone = ZoneInfo("Asia/Tokyo")
    monkeypatch.setattr(calendar_svc, "_local_zone", lambda: zone)
    ft.add("GET", "calendars/primary/events", {"items": []})
    before = dt.datetime.now(zone).date()
    run("calendar", "conflicts")
    after = dt.datetime.now(zone).date()
    url = ft.calls[0]["url"]
    assert any(f"timeMin={day.isoformat()}T00%3A00%3A00%2B09%3A00" in url
               for day in {before, after})
    assert any(f"timeMax={(day + dt.timedelta(days=7)).isoformat()}"
               "T00%3A00%3A00%2B09%3A00" in url for day in {before, after})
    assert "00%3A00%3A00Z" not in url
