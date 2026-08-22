"""`gsuite workflow` — the cross-service compositions.

Each command here reaches two or more Google APIs and prints one answer, so
the tests program one route per underlying call, in the order the command
makes them. Two properties get more attention than they would in a
single-API service:

* **Partial replies.** A composition reads fields out of several unrelated
  payloads; a key missing from any one of them must not become a KeyError.
* **The first unauthorized API.** A composition dies at whichever service the
  account has not granted, and Google's reply says nothing about the ones it
  never reached — so the message has to name them itself.
"""
import datetime as dt
import json

import pytest

from gsuite.cli import main
from gsuite.services import calendar as calendar_svc

# Google's own wording for the one 403 a user can act on; `api._hint` keys
# off this text to suggest a re-login, and the workflow wrapper adds the
# services the composition never got to.
SCOPE_403 = {"error": {"code": 403, "status": "PERMISSION_DENIED",
                       "message": "Request had insufficient authentication "
                                  "scopes."}}


@pytest.fixture
def wf(authed, fake_transport, run_cli):
    return fake_transport, run_cli


# -- standup-report ----------------------------------------------------------

def test_standup_report_lists_todays_meetings_then_open_tasks(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": [
        {"id": "e1", "summary": "Standup",
         "start": {"dateTime": "2026-01-05T09:00:00-05:00"}},
        {"id": "e2", "summary": "Design review",
         "start": {"dateTime": "2026-01-05T14:00:00-05:00"}},
    ]})
    ft.add("GET", "lists/@default/tasks", {"items": [
        {"id": "t1", "title": "File expenses", "due": "2026-01-09T00:00:00Z"},
        {"id": "t2", "title": "Review RFC"},
    ]})
    out = run("workflow", "standup-report", "--date", "2026-01-05",
              "--tz", "America/New_York")

    header, *rows = out.splitlines()
    assert "KIND" in header and "WHEN" in header and "ITEM" in header
    # Meetings come first and in start order, then the open tasks.
    assert [r.split()[0] for r in rows] == ["meeting", "meeting", "task", "task"]
    assert "Standup" in rows[0] and "2026-01-05T09:00:00-05:00" in rows[0]
    assert "Design review" in rows[1]
    assert "File expenses" in rows[2] and "2026-01-09T00:00:00Z" in rows[2]
    assert "Review RFC" in rows[3]

    calendar_call, tasks_call = ft.calls
    assert "singleEvents=true" in calendar_call["url"]
    assert "orderBy=startTime" in calendar_call["url"]
    # Completed work is not standup material.
    assert "showCompleted=false" in tasks_call["url"]


def test_standup_report_day_bounds_are_local_midnight_not_utc(wf):
    """The window comes from Calendar's own day bounds, offset and all."""
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": []})
    ft.add("GET", "lists/@default/tasks", {"items": []})
    run("workflow", "standup-report", "--date", "2026-01-05",
        "--tz", "America/New_York")
    url = ft.calls[0]["url"]
    assert "timeMin=2026-01-05T00%3A00%3A00-05%3A00" in url
    assert "timeMax=2026-01-06T00%3A00%3A00-05%3A00" in url
    assert "00%3A00%3A00Z" not in url


def test_standup_report_without_tz_uses_the_resolved_local_zone(wf, monkeypatch):
    ft, run = wf
    monkeypatch.setattr(calendar_svc, "_local_zone",
                        lambda: dt.timezone(dt.timedelta(hours=9)))
    ft.add("GET", "calendars/primary/events", {"items": []})
    ft.add("GET", "lists/@default/tasks", {"items": []})
    run("workflow", "standup-report", "--date", "2026-01-05")
    assert "timeMin=2026-01-05T00%3A00%3A00%2B09%3A00" in ft.calls[0]["url"]


def test_standup_report_defaults_to_today_in_the_effective_zone(wf):
    ft, run = wf
    zone = dt.timezone(dt.timedelta(hours=14))  # Pacific/Kiritimati, no DST
    ft.add("GET", "calendars/primary/events", {"items": []})
    ft.add("GET", "lists/@default/tasks", {"items": []})
    before = dt.datetime.now(zone).date()
    run("workflow", "standup-report", "--tz", "Pacific/Kiritimati")
    after = dt.datetime.now(zone).date()
    url = ft.calls[0]["url"]
    # Either date, so a run straddling midnight cannot flake.
    assert any(f"timeMin={day.isoformat()}T00%3A00%3A00%2B14%3A00" in url
               for day in {before, after})


def test_standup_report_honours_the_calendar_and_list_flags(wf):
    ft, run = wf
    ft.add("GET", "calendars/team%40x.com/events", {"items": []})
    ft.add("GET", "lists/MDk5/tasks", {"items": []})
    run("workflow", "standup-report", "--date", "2026-01-05",
        "--calendar", "team@x.com", "--list", "MDk5")
    # Both ids are escaped by the service module that owns the URL.
    assert "/calendars/team%40x.com/events" in ft.calls[0]["url"]
    assert "/lists/MDk5/tasks" in ft.calls[1]["url"]


def test_standup_report_survives_replies_that_are_missing_every_field(wf):
    """Two APIs, two chances for a KeyError. Neither may fire."""
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": [{}]})
    ft.add("GET", "lists/@default/tasks", {"items": [{}]})
    out = run("workflow", "standup-report", "--date", "2026-01-05")
    assert "meeting" in out and "task" in out


def test_standup_report_emits_json_rows(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": [
        {"summary": "Standup", "start": {"date": "2026-01-05"}}]})
    ft.add("GET", "lists/@default/tasks", {"items": []})
    out = run("--json", "workflow", "standup-report", "--date", "2026-01-05")
    assert json.loads(out) == [
        {"item": "Standup", "kind": "meeting", "when": "2026-01-05"}]


def test_standup_report_caps_the_task_list(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": []})
    ft.add("GET", "lists/@default/tasks",
           {"items": [{"title": f"t{n}"} for n in range(5)],
            "nextPageToken": "more"})
    out = run("workflow", "standup-report", "--date", "2026-01-05",
              "--max-tasks", "2")
    assert out.count("task") == 2
    # The cap stops the paging, so the second page is never fetched.
    assert len(ft.calls) == 2


def test_standup_report_scope_error_names_every_service_it_needs(authed,
                                                                fake_transport,
                                                                capsys):
    """The first unauthorized API must not hide the ones behind it.

    Calendar answers, Tasks refuses. Google's own text names Tasks only, so
    a user who acts on it alone re-authorizes once, re-runs, and discovers
    Calendar next. The composition knows both up front and says so.
    """
    fake_transport.add("GET", "calendars/primary/events", {"items": []})
    fake_transport.add("GET", "lists/@default/tasks", SCOPE_403, status=403)
    assert main(["workflow", "standup-report", "--date", "2026-01-05"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: tasks:")  # which leg failed
    assert "insufficient authentication scopes" in err  # Google's own text
    assert "gsuite auth login --services calendar,tasks" in err


def test_standup_report_reports_an_ordinary_api_error_without_a_login_hint(
        authed, fake_transport, capsys):
    """A 404 is not an authorization problem; do not send the user to login."""
    fake_transport.add("GET", "calendars/primary/events",
                       {"error": {"code": 404, "message": "Not Found"}},
                       status=404)
    assert main(["workflow", "standup-report", "--date", "2026-01-05"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: calendar:")
    assert "auth login" not in err


def test_standup_report_rejects_a_date_it_cannot_read(authed, fake_transport,
                                                      capsys):
    assert main(["workflow", "standup-report", "--date", "tomorrow"]) == 1
    assert "bad date: tomorrow" in capsys.readouterr().err
    assert not fake_transport.calls  # nothing was sent


# -- meeting-prep ------------------------------------------------------------

NEXT_MEETING = {
    "id": "e9",
    "summary": "Design review",
    "location": "Room 4",
    "description": "Agenda: ship it.\nPre-read: "
                   "https://docs.google.com/document/d/DOC1234567/edit",
    "start": {"dateTime": "2026-01-07T14:00:00-05:00"},
    "end": {"dateTime": "2026-01-07T15:00:00-05:00"},
    "attendees": [
        {"email": "ada@x.com", "displayName": "Ada Lovelace",
         "responseStatus": "accepted"},
        {"email": "bob@x.com", "responseStatus": "needsAction"},
    ],
    "attachments": [
        {"fileId": "SHEET7654321", "title": "Budget (stale name)",
         "fileUrl": "https://docs.google.com/spreadsheets/d/SHEET7654321"},
    ],
}


def test_meeting_prep_summarizes_the_next_meeting(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events",
           {"items": [NEXT_MEETING, {"id": "later", "summary": "Retro"}]})
    ft.add("GET", "drive/v3/files/SHEET7654321",
           {"name": "Q1 budget", "webViewLink": "https://drive.example/sheet"})
    ft.add("GET", "drive/v3/files/DOC1234567",
           {"name": "Design doc", "webViewLink": "https://drive.example/doc"})
    out = run("workflow", "meeting-prep", "--tz", "Asia/Tokyo")

    assert "summary: Design review" in out
    assert "start: 2026-01-07T14:00:00-05:00" in out
    assert "end: 2026-01-07T15:00:00-05:00" in out
    assert "location: Room 4" in out
    # The name and the response, per attendee.
    assert "Ada Lovelace (accepted)" in out and "bob@x.com (needsAction)" in out
    assert "Agenda: ship it." in out
    # Only the *next* meeting is prepared for.
    assert "Retro" not in out


def test_meeting_prep_window_starts_now_in_the_effective_zone(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": []})
    run("workflow", "meeting-prep", "--tz", "Asia/Tokyo")
    url = ft.calls[0]["url"]
    assert "orderBy=startTime" in url and "singleEvents=true" in url
    # A bound with no offset would mean "now, in UTC" — nine hours wrong.
    assert "%2B09%3A00" in url


def test_meeting_prep_resolves_linked_files_through_drive(wf):
    """Attachments and links in the agenda both become named Drive files."""
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": [NEXT_MEETING]})
    ft.add("GET", "drive/v3/files/SHEET7654321",
           {"name": "Q1 budget", "webViewLink": "https://drive.example/sheet"})
    ft.add("GET", "drive/v3/files/DOC1234567",
           {"name": "Design doc", "webViewLink": "https://drive.example/doc"})
    out = run("workflow", "meeting-prep")

    # Drive is asked about the attachment and about the link found in the body.
    assert "drive/v3/files/SHEET7654321" in ft.calls[1]["url"]
    assert "drive/v3/files/DOC1234567" in ft.calls[2]["url"]
    # Shared-drive files resolve the same way `drive info` resolves them.
    assert "supportsAllDrives=true" in ft.calls[1]["url"]
    # Drive's current name wins over the one frozen into the invitation.
    assert "Q1 budget" in out and "Budget (stale name)" not in out
    assert "Design doc" in out and "https://drive.example/doc" in out


def test_meeting_prep_does_not_call_drive_when_nothing_is_linked(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": [
        {"summary": "1:1", "start": {"dateTime": "2026-01-07T14:00:00Z"}}]})
    out = run("workflow", "meeting-prep")
    assert len(ft.calls) == 1
    assert "summary: 1:1" in out


def test_meeting_prep_tolerates_a_linked_file_it_cannot_open(wf):
    """A doc shared with the room but not with you must not sink the prep.

    Attachments outlive access: someone leaves, a file moves, a folder is
    re-shared. Losing the whole briefing over one unreadable link would make
    the command useless exactly when a meeting is imminent.
    """
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": [NEXT_MEETING]})
    ft.add("GET", "drive/v3/files/SHEET7654321",
           {"error": {"code": 404, "message": "File not found"}}, status=404)
    ft.add("GET", "drive/v3/files/DOC1234567",
           {"name": "Design doc", "webViewLink": "https://drive.example/doc"})
    out = run("workflow", "meeting-prep")
    # The invitation's own title is the fallback, and the rest still arrives.
    assert "Budget (stale name)" in out
    assert "Design doc" in out


def test_meeting_prep_says_so_when_nothing_is_coming_up(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": []})
    out = run("workflow", "meeting-prep")
    assert "no upcoming meetings" in out
    assert len(ft.calls) == 1


def test_meeting_prep_survives_an_event_with_no_fields(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": [{}]})
    out = run("workflow", "meeting-prep")
    assert "summary:" in out


def test_meeting_prep_survives_an_attendee_with_no_email(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": [
        {"summary": "Sync", "attendees": [{}, {"email": "b@x.com"}]}]})
    out = run("workflow", "meeting-prep")
    assert "b@x.com" in out


def test_meeting_prep_scope_error_names_calendar_and_drive(authed,
                                                           fake_transport,
                                                           capsys):
    fake_transport.add("GET", "calendars/primary/events", SCOPE_403, status=403)
    assert main(["workflow", "meeting-prep"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: calendar:")
    assert "gsuite auth login --services calendar,drive" in err


# -- weekly-digest -----------------------------------------------------------

WEEK_EVENTS = {"items": [
    {"summary": "Standup", "start": {"dateTime": "2026-01-05T09:00:00-05:00"}},
    {"summary": "1:1", "start": {"dateTime": "2026-01-05T11:00:00-05:00"}},
    {"summary": "Offsite", "start": {"date": "2026-01-07"}},
]}


def test_weekly_digest_spans_the_local_week_and_counts_unread(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", WEEK_EVENTS)
    ft.add("GET", "gmail/v1/users/me/labels/UNREAD",
           {"id": "UNREAD", "messagesUnread": 12, "threadsUnread": 9})
    out = run("workflow", "weekly-digest", "--date", "2026-01-07",
              "--tz", "America/New_York")

    # Any day in the week digests that whole week, Monday to Sunday.
    url = ft.calls[0]["url"]
    assert "timeMin=2026-01-05T00%3A00%3A00-05%3A00" in url
    assert "timeMax=2026-01-12T00%3A00%3A00-05%3A00" in url
    assert "00%3A00%3A00Z" not in url

    assert "from: 2026-01-05" in out
    assert "to: 2026-01-11" in out          # the last day, not the bound
    assert "meetings: 3" in out
    assert "days: 2026-01-05 (2), 2026-01-07 (1)" in out
    assert "unread: 12" in out


def test_weekly_digest_reads_gmails_own_unread_counter(wf):
    """One label read, not a paged search: the count is a fact Gmail keeps."""
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": []})
    ft.add("GET", "gmail/v1/users/me/labels/UNREAD", {"messagesUnread": 0})
    run("workflow", "weekly-digest", "--date", "2026-01-07")
    assert len(ft.calls) == 2
    assert ft.calls[1]["url"].endswith(
        "https://gmail.googleapis.com/gmail/v1/users/me/labels/UNREAD")


def test_weekly_digest_survives_replies_missing_every_field(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": [{}]})
    ft.add("GET", "gmail/v1/users/me/labels/UNREAD", {})
    out = run("workflow", "weekly-digest", "--date", "2026-01-07")
    assert "meetings: 1" in out
    assert "unread:" in out


def test_weekly_digest_defaults_to_the_week_containing_today(wf):
    ft, run = wf
    ft.add("GET", "calendars/primary/events", {"items": []})
    ft.add("GET", "gmail/v1/users/me/labels/UNREAD", {"messagesUnread": 1})
    out = run("workflow", "weekly-digest", "--tz", "UTC")
    monday = dt.datetime.now(dt.timezone.utc).date()
    monday -= dt.timedelta(days=monday.weekday())
    assert f"from: {monday.isoformat()}" in out


def test_weekly_digest_scope_error_names_calendar_and_gmail(authed,
                                                            fake_transport,
                                                            capsys):
    fake_transport.add("GET", "calendars/primary/events", {"items": []})
    fake_transport.add("GET", "gmail/v1/users/me/labels/UNREAD",
                       SCOPE_403, status=403)
    assert main(["workflow", "weekly-digest", "--date", "2026-01-07"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: gmail:")
    assert "gsuite auth login --services calendar,gmail" in err


# -- email-to-task -----------------------------------------------------------

MESSAGE_META = {
    "id": "19ab3f",
    "threadId": "19ab30",
    "snippet": "can you take a look",
    "payload": {"headers": [
        {"name": "From", "value": "alice@example.com"},
        {"name": "Subject", "value": "Q1 roadmap"},
        {"name": "Date", "value": "Mon, 5 Jan 2026 09:14:00 -0500"},
    ]},
}


def test_email_to_task_turns_the_subject_into_a_task_that_links_back(wf):
    ft, run = wf
    ft.add("GET", "messages/19ab3f", MESSAGE_META)
    ft.add("POST", "lists/@default/tasks", {"id": "t9", "title": "Q1 roadmap"})
    out = run("workflow", "email-to-task", "19ab3f")

    # Only the headers are fetched — the body is not needed to make a task.
    assert "format=metadata" in ft.calls[0]["url"]
    body = json.loads(ft.calls[1]["data"])
    assert body["title"] == "Q1 roadmap"
    assert "https://mail.google.com/mail/u/0/#all/19ab3f" in body["notes"]
    assert "alice@example.com" in body["notes"]
    assert "Mon, 5 Jan 2026 09:14:00 -0500" in body["notes"]
    assert "due" not in body
    assert "added t9 Q1 roadmap" in out


def test_email_to_task_accepts_a_title_and_a_due_date(wf):
    ft, run = wf
    ft.add("GET", "messages/19ab3f", MESSAGE_META)
    ft.add("POST", "lists/L1/tasks", {"id": "t9", "title": "Reply to Alice"})
    run("workflow", "email-to-task", "19ab3f", "--title", "Reply to Alice",
        "--due", "2026-01-09", "--list", "L1")
    body = json.loads(ft.calls[1]["data"])
    assert body["title"] == "Reply to Alice"
    # A bare date becomes the RFC3339 form `tasks add` already sends.
    assert body["due"] == "2026-01-09T00:00:00Z"
    assert "/lists/L1/tasks" in ft.calls[1]["url"]


def test_email_to_task_falls_back_when_the_mail_has_no_subject(wf):
    ft, run = wf
    ft.add("GET", "messages/19ab3f", {"id": "19ab3f", "payload": {}})
    ft.add("POST", "lists/@default/tasks", {"id": "t9"})
    run("workflow", "email-to-task", "19ab3f")
    # Gmail's own wording for the same thing, rather than a blank task.
    assert json.loads(ft.calls[1]["data"])["title"] == "(no subject)"


def test_email_to_task_escapes_the_message_id_everywhere_it_lands(wf):
    ft, run = wf
    ft.add("GET", "messages/a%3Fb%23c", MESSAGE_META)
    ft.add("POST", "lists/@default/tasks", {"id": "t9"})
    run("workflow", "email-to-task", "a?b#c")
    # In the request path...
    assert "/messages/a%3Fb%23c" in ft.calls[0]["url"]
    # ...and in the link written into the task, where a raw `#` would
    # truncate the URL at the fragment.
    notes = json.loads(ft.calls[1]["data"])["notes"]
    assert "#all/a%3Fb%23c" in notes


def test_email_to_task_is_refused_under_readonly(authed, fake_transport,
                                                 capsys):
    fake_transport.add("GET", "messages/19ab3f", MESSAGE_META)
    assert main(["--readonly", "workflow", "email-to-task", "19ab3f"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: tasks: readonly mode")
    # A refusal is local, not an authorization problem: no login advice.
    assert "auth login" not in err


def test_email_to_task_scope_error_names_gmail_and_tasks(authed,
                                                         fake_transport,
                                                         capsys):
    fake_transport.add("GET", "messages/19ab3f", SCOPE_403, status=403)
    assert main(["workflow", "email-to-task", "19ab3f"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: gmail:")
    assert "gsuite auth login --services gmail,tasks" in err


# -- file-announce -----------------------------------------------------------

DRIVE_FILE = {"id": "1AbC", "name": "Q1 budget",
              "mimeType": "application/vnd.google-apps.spreadsheet",
              "webViewLink": "https://docs.google.com/spreadsheets/d/1AbC"}


def test_file_announce_posts_the_files_name_and_link_to_a_space(wf):
    ft, run = wf
    ft.add("GET", "drive/v3/files/1AbC", DRIVE_FILE)
    ft.add("POST", "spaces/AAAA/messages",
           {"name": "spaces/AAAA/messages/BBBB"})
    out = run("workflow", "file-announce", "1AbC", "--space", "spaces/AAAA")

    assert "supportsAllDrives=true" in ft.calls[0]["url"]
    text = json.loads(ft.calls[1]["data"])["text"]
    assert "Q1 budget" in text
    assert "https://docs.google.com/spreadsheets/d/1AbC" in text
    assert "sent spaces/AAAA/messages/BBBB" in out


def test_file_announce_puts_the_note_above_the_link(wf):
    ft, run = wf
    ft.add("GET", "drive/v3/files/1AbC", DRIVE_FILE)
    ft.add("POST", "spaces/AAAA/messages", {"name": "spaces/AAAA/messages/B"})
    run("workflow", "file-announce", "1AbC", "--space", "spaces/AAAA",
        "--text", "Numbers are final")
    text = json.loads(ft.calls[1]["data"])["text"]
    assert text.splitlines()[0] == "Numbers are final"
    assert "Q1 budget" in text.splitlines()[-1]


def test_file_announce_survives_a_file_with_no_name_or_link(wf):
    ft, run = wf
    ft.add("GET", "drive/v3/files/1AbC", {})
    ft.add("POST", "spaces/AAAA/messages", {"name": "spaces/AAAA/messages/B"})
    run("workflow", "file-announce", "1AbC", "--space", "spaces/AAAA")
    assert "1AbC" in json.loads(ft.calls[1]["data"])["text"]


def test_file_announce_escapes_the_file_id(wf):
    ft, run = wf
    ft.add("GET", "drive/v3/files/a%3Fb", DRIVE_FILE)
    ft.add("POST", "spaces/AAAA/messages", {"name": "spaces/AAAA/messages/B"})
    run("workflow", "file-announce", "a?b", "--space", "spaces/AAAA")
    assert "/files/a%3Fb" in ft.calls[0]["url"]


def test_file_announce_rejects_a_bad_space_before_spending_a_request(authed,
                                                                    fake_transport,
                                                                    capsys):
    """Check what can be checked locally first.

    The Chat space is only validated where the message is posted, which is
    after Drive has already been asked about the file. Announcing to
    `../../v1/elsewhere` was never going to work, and a mutation that reads
    first and refuses second wastes a round trip to say so.
    """
    assert main(["workflow", "file-announce", "1AbC",
                 "--space", "../../v1/elsewhere"]) == 1
    assert "invalid resource name" in capsys.readouterr().err
    assert not fake_transport.calls


def test_file_announce_scope_error_names_drive_and_chat(authed, fake_transport,
                                                        capsys):
    fake_transport.add("GET", "drive/v3/files/1AbC", SCOPE_403, status=403)
    assert main(["workflow", "file-announce", "1AbC",
                 "--space", "spaces/AAAA"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: drive:")
    assert "gsuite auth login --services drive,chat" in err


# -- registration ------------------------------------------------------------

def test_workflow_is_a_registered_service():
    from gsuite.cli import SERVICE_MODULES

    assert "workflow" in SERVICE_MODULES
