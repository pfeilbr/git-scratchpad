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
