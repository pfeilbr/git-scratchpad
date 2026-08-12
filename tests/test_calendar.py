import json

import pytest

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
    run("calendar", "create", "--summary", "Sync",
        "--start", "2026-01-05T09:00", "--end", "2026-01-05T09:30",
        "--attendees", "a@x.com,b@x.com", "--location", "HQ")
    body = json.loads(ft.calls[0]["data"])
    assert body["summary"] == "Sync"
    assert body["start"] == {"dateTime": "2026-01-05T09:00:00"}
    assert body["end"] == {"dateTime": "2026-01-05T09:30:00"}
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
