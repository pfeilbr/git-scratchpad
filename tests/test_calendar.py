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


def test_update_sends_only_provided_fields(cal):
    ft, run = cal
    ft.add("PATCH", "events/e1", {"id": "e1"})
    out = run("calendar", "update", "e1", "--summary", "New name",
              "--start", "2026-01-05T10:00")
    call = ft.calls[0]
    assert call["method"] == "PATCH"
    body = json.loads(call["data"])
    assert body == {"summary": "New name",
                    "start": {"dateTime": "2026-01-05T10:00:00"}}
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


def test_freebusy_body_and_output(cal):
    ft, run = cal
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
