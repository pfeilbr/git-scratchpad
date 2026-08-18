"""User-supplied ids must not be able to change *which* URL is requested.

Two shapes of value reach a URL path in this CLI, and they need different
encodings:

* one opaque segment — a spreadsheet/document/file/form/task-list id — which
  is escaped with `quote_id` (``safe=""``), so even a ``/`` is encoded;
* a multi-segment *resource name* — ``spaces/AAA``, ``people/c123``,
  ``notes/n1``, ``conferenceRecords/c1`` — which is escaped with
  `resource_path`, keeping ``/`` (encoding it would break every one of those
  commands) but refusing traversal.

Either way ``?``, ``#``, a space or a ``..`` segment must never survive
unescaped into the request line.

`resource_path` is imported inside each test so this module still collects
cleanly before the helper exists.
"""
import pytest

from gsuite.errors import CLIError


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


# -- the helper itself -------------------------------------------------------

def test_resource_path_keeps_slashes_and_encodes_everything_else():
    from gsuite.services._common import resource_path

    assert resource_path("spaces/AAA") == "spaces/AAA"
    assert (resource_path("conferenceRecords/c1/participants/p1")
            == "conferenceRecords/c1/participants/p1")
    assert resource_path("spaces/A?x=1#f") == "spaces/A%3Fx%3D1%23f"
    assert resource_path("notes/n 1") == "notes/n%201"


@pytest.mark.parametrize("bad", [
    "../../v1/other",       # walks up to a different API path
    "notes/../../v1/other",  # ... even after a service prefixes the name
    "spaces/./A",
    "..",
    "/spaces/A",            # absolute: reroots the path
    "spaces\\A",            # backslash: normalized to `/` by some stacks
])
def test_resource_path_refuses_traversal_and_absolute_names(bad):
    from gsuite.services._common import resource_path

    with pytest.raises(CLIError):
        resource_path(bad)


# -- single-segment ids: `/` gets encoded too --------------------------------

def test_sheets_read_encodes_a_spreadsheet_id_holding_a_query_char(svc):
    ft, run = svc
    ft.add("GET", "spreadsheets/ss1%3Fx%3D1/values/A1", {"values": [["v"]]})
    run("sheets", "read", "ss1?x=1", "A1")
    url = ft.calls[0]["url"]
    assert "/spreadsheets/ss1%3Fx%3D1/values/A1" in url
    assert "ss1?x=1" not in url


def test_tasks_list_encodes_a_list_id_holding_a_fragment_char(svc):
    ft, run = svc
    ft.add("GET", "lists/tl%231/tasks", {"items": []})
    run("tasks", "list", "--list", "tl#1")
    url = ft.calls[0]["url"]
    assert "/lists/tl%231/tasks" in url
    assert "tl#1" not in url


def test_docs_cat_confines_a_traversal_id_to_one_path_segment(svc):
    ft, run = svc
    ft.add("GET", "documents/..%2F..%2Fv1%2Fother", {"body": {"content": []}})
    run("docs", "cat", "../../v1/other")
    url = ft.calls[0]["url"]
    assert url == ("https://docs.googleapis.com/v1/documents/"
                   "..%2F..%2Fv1%2Fother")


def test_drive_info_encodes_a_file_id_holding_a_space(svc):
    ft, run = svc
    ft.add("GET", "files/f%201", {"id": "f 1", "name": "n"})
    run("drive", "info", "f 1")
    assert "/files/f%201?" in ft.calls[0]["url"]


# -- resource names: `/` survives, the dangerous characters do not -----------

def test_chat_messages_encodes_a_query_char_inside_a_space_name(svc):
    ft, run = svc
    ft.add("GET", "spaces/A%3Fx%3D1/messages", {"messages": []})
    run("chat", "messages", "spaces/A?x=1")
    assert "/v1/spaces/A%3Fx%3D1/messages" in ft.calls[0]["url"]


def test_chat_messages_refuses_a_traversal_space_name(svc):
    ft, run = svc
    run("chat", "messages", "../../v1/spaces", expect=1)
    assert ft.calls == [], "a refused id must not reach the network"


def test_keep_get_refuses_a_traversal_note_id(svc):
    ft, run = svc
    run("keep", "get", "../../v1/notes", expect=1)
    assert ft.calls == [], "a refused id must not reach the network"


# -- regression pins: these pass before the fix and must keep passing --------

def test_slash_bearing_resource_names_still_reach_the_wire_intact(svc):
    """Regression pin: `quote_id` here would break every one of these."""
    ft, run = svc
    ft.add("GET", "spaces/AAA/messages", {"messages": []})
    ft.add("GET", "people/c123", {"resourceName": "people/c123"})
    ft.add("GET", "keep.googleapis.com/v1/notes/n1", {"name": "notes/n1"})
    ft.add("GET", "conferenceRecords/c1/participants", {"participants": []})
    run("chat", "messages", "spaces/AAA")
    run("contacts", "get", "people/c123")
    run("keep", "get", "notes/n1")
    run("meet", "participants", "conferenceRecords/c1")
    urls = [call["url"] for call in ft.calls]
    assert urls[0] == "https://chat.googleapis.com/v1/spaces/AAA/messages"
    assert urls[1].startswith("https://people.googleapis.com/v1/people/c123?")
    assert urls[2] == "https://keep.googleapis.com/v1/notes/n1"
    assert urls[3] == ("https://meet.googleapis.com/v2/"
                       "conferenceRecords/c1/participants")


def test_ordinary_ids_produce_byte_identical_urls(svc):
    """Regression pin: encoding must be a no-op for everyday ids."""
    ft, run = svc
    ft.add("GET", "documents/doc1", {"body": {"content": []}})
    ft.add("GET", "spreadsheets/ss1/values/A1", {"values": []})
    ft.add("GET", "v1/forms/f1", {"formId": "f1"})
    ft.add("GET", "lists/@default/tasks", {"items": []})
    ft.add("POST", "properties/123:runRealtimeReport",
           {"metricHeaders": [{"name": "activeUsers"}], "rows": []})
    run("docs", "cat", "doc1")
    run("sheets", "read", "ss1", "A1")
    run("forms", "get", "f1")
    run("tasks", "list")
    run("analytics", "realtime", "123")
    assert [call["url"] for call in ft.calls] == [
        "https://docs.googleapis.com/v1/documents/doc1",
        "https://sheets.googleapis.com/v4/spreadsheets/ss1/values/A1",
        "https://forms.googleapis.com/v1/forms/f1",
        "https://tasks.googleapis.com/tasks/v1/lists/@default/tasks"
        "?showCompleted=false",
        "https://analyticsdata.googleapis.com/v1beta/properties/123"
        ":runRealtimeReport",
    ]
