import json

import pytest


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


SPACE = {
    "name": "spaces/abc",
    "meetingUri": "https://meet.google.com/xxx-yyyy-zzz",
    "meetingCode": "xxx-yyyy-zzz",
    "config": {"accessType": "TRUSTED"},
    "activeConference": {"conferenceRecord": "conferenceRecords/c1"},
}


def test_meet_create_default_body(svc):
    ft, run = svc
    ft.add("POST", "meet.googleapis.com/v2/spaces", SPACE)
    out = run("meet", "create")
    assert "created spaces/abc https://meet.google.com/xxx-yyyy-zzz" in out
    call = ft.calls[0]
    assert call["url"].startswith("https://meet.googleapis.com/v2/spaces")
    assert json.loads(call["data"]) == {}


def test_meet_create_with_access(svc):
    ft, run = svc
    ft.add("POST", "meet.googleapis.com/v2/spaces", SPACE)
    run("meet", "create", "--access", "RESTRICTED")
    assert json.loads(ft.calls[0]["data"]) == {
        "config": {"accessType": "RESTRICTED"}}


def test_meet_get_normalizes_and_emits_fields(svc):
    ft, run = svc
    ft.add("GET", "v2/spaces/abc", SPACE)
    out = run("meet", "get", "abc")
    assert "https://meet.googleapis.com/v2/spaces/abc" in ft.calls[0]["url"]
    assert "name: spaces/abc" in out
    assert "code: xxx-yyyy-zzz" in out
    assert "uri: https://meet.google.com/xxx-yyyy-zzz" in out
    assert "access: TRUSTED" in out
    assert "active: conferenceRecords/c1" in out
    # already-prefixed input is not double-prefixed; no active conference -> ""
    ft.add("GET", "v2/spaces/abc", {"name": "spaces/abc"})
    out = run("meet", "get", "spaces/abc")
    assert ft.calls[1]["url"].endswith("/v2/spaces/abc")
    active_line = next(l for l in out.splitlines() if l.startswith("active"))
    assert active_line.strip() == "active:"


def test_meet_end(svc):
    ft, run = svc
    ft.add("POST", "spaces/abc:endActiveConference", {})
    out = run("meet", "end", "abc")
    assert ft.calls[0]["url"] == (
        "https://meet.googleapis.com/v2/spaces/abc:endActiveConference")
    assert "ended active conference in spaces/abc" in out


def test_meet_conferences(svc):
    ft, run = svc
    ft.add("GET", "v2/conferenceRecords", {"conferenceRecords": [
        {"name": "conferenceRecords/c1", "startTime": "2026-01-05T10:00:00Z",
         "endTime": "2026-01-05T11:00:00Z", "space": "spaces/abc"},
        {"name": "conferenceRecords/c2", "startTime": "2026-01-06T09:00:00Z",
         "endTime": "2026-01-06T09:30:00Z", "space": "spaces/def"},
    ]})
    out = run("meet", "conferences")
    assert "https://meet.googleapis.com/v2/conferenceRecords" in ft.calls[0]["url"]
    header = out.splitlines()[0]
    assert ("NAME" in header and "START" in header and "END" in header
            and "SPACE" in header)
    assert "conferenceRecords/c1" in out and "2026-01-05T10:00:00Z" in out
    assert "2026-01-05T11:00:00Z" in out and "spaces/def" in out


def test_meet_participants_displayname_fallback(svc):
    ft, run = svc
    ft.add("GET", "v2/conferenceRecords/c1/participants", {"participants": [
        {"name": "conferenceRecords/c1/participants/p1",
         "signedinUser": {"displayName": "Ada Lovelace"},
         "earliestStartTime": "2026-01-05T10:00:00Z"},
        {"name": "conferenceRecords/c1/participants/p2",
         "anonymousUser": {"displayName": "Guest"},
         "earliestStartTime": "2026-01-05T10:05:00Z"},
        {"name": "conferenceRecords/c1/participants/p3",
         "phoneUser": {"displayName": "+1 555-0100"},
         "earliestStartTime": "2026-01-05T10:10:00Z"},
    ]})
    out = run("meet", "participants", "c1")
    assert ("https://meet.googleapis.com/v2/conferenceRecords/c1/participants"
            in ft.calls[0]["url"])
    assert "Ada Lovelace" in out and "Guest" in out and "+1 555-0100" in out
    assert "2026-01-05T10:10:00Z" in out
    # already-prefixed record id is accepted as-is
    ft.add("GET", "v2/conferenceRecords/c1/participants", {"participants": []})
    run("meet", "participants", "conferenceRecords/c1")
    assert ft.calls[1]["url"].endswith("/v2/conferenceRecords/c1/participants")


def test_meet_scopes_registered():
    from gsuite.oauth import SERVICE_SCOPES

    assert SERVICE_SCOPES["meet"] == [
        "https://www.googleapis.com/auth/meetings.space.created",
        "https://www.googleapis.com/auth/meetings.space.readonly",
    ]
