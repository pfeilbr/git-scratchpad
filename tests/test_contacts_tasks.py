import json

import pytest


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


PERSON = {
    "resourceName": "people/c1",
    "names": [{"displayName": "Ada Lovelace"}],
    "emailAddresses": [{"value": "ada@x.com"}],
    "phoneNumbers": [{"value": "+1 555"}],
}


def test_contacts_list(svc):
    ft, run = svc
    ft.add("GET", "people/me/connections", {"connections": [PERSON]})
    out = run("contacts", "list")
    assert "Ada Lovelace" in out and "ada@x.com" in out
    assert "personFields=" in ft.calls[0]["url"]


def test_contacts_search(svc):
    ft, run = svc
    ft.add("GET", "people:searchContacts", {"results": [{"person": PERSON}]})
    out = run("contacts", "search", "ada")
    assert "Ada Lovelace" in out
    assert "query=ada" in ft.calls[0]["url"]


def test_contacts_create(svc):
    ft, run = svc
    ft.add("POST", "people:createContact", PERSON)
    run("contacts", "create", "--name", "Ada Lovelace",
        "--email", "ada@x.com", "--phone", "+1 555")
    body = json.loads(ft.calls[0]["data"])
    assert body["names"] == [{"unstructuredName": "Ada Lovelace"}]
    assert body["emailAddresses"] == [{"value": "ada@x.com"}]
    assert body["phoneNumbers"] == [{"value": "+1 555"}]


def test_contacts_rm(svc):
    ft, run = svc
    ft.add("DELETE", "people/c1:deleteContact", {})
    run("contacts", "rm", "people/c1")


def test_tasks_lists(svc):
    ft, run = svc
    ft.add("GET", "users/@me/lists", {"items": [{"id": "tl1",
                                                 "title": "My Tasks"}]})
    assert "My Tasks" in run("tasks", "lists")


def test_tasks_list_default(svc):
    ft, run = svc
    ft.add("GET", "lists/@default/tasks", {"items": [
        {"id": "t1", "title": "Buy milk", "status": "needsAction",
         "due": "2026-01-05T00:00:00Z"}]})
    out = run("tasks", "list")
    assert "Buy milk" in out and "needsAction" in out


def test_tasks_add_with_due_and_notes(svc):
    ft, run = svc
    ft.add("POST", "lists/@default/tasks", {"id": "t2", "title": "Call"})
    run("tasks", "add", "Call", "--due", "2026-01-05", "--notes", "about x")
    body = json.loads(ft.calls[0]["data"])
    assert body["title"] == "Call"
    assert body["due"].startswith("2026-01-05T")
    assert body["notes"] == "about x"


def test_tasks_done_patches_status(svc):
    ft, run = svc
    ft.add("PATCH", "lists/@default/tasks/t1", {"id": "t1",
                                                "status": "completed"})
    run("tasks", "done", "t1")
    assert json.loads(ft.calls[0]["data"]) == {"status": "completed"}


def test_tasks_rm_custom_list(svc):
    ft, run = svc
    ft.add("DELETE", "lists/tl9/tasks/t1", {})
    run("tasks", "rm", "t1", "--list", "tl9")
