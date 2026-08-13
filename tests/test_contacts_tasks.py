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


def test_contacts_get_shows_fields(svc):
    ft, run = svc
    person = dict(PERSON, organizations=[{"name": "Analytical Engines"}])
    ft.add("GET", "people/c1", person)
    out = run("contacts", "get", "people/c1")
    url = ft.calls[0]["url"]
    assert ("personFields=names%2CemailAddresses%2CphoneNumbers"
            "%2Corganizations") in url
    assert "resource: people/c1" in out
    assert "name: Ada Lovelace" in out
    assert "email: ada@x.com" in out
    assert "phone: +1 555" in out
    assert "org: Analytical Engines" in out


def test_contacts_update_sends_etag_and_only_changed_fields(svc):
    ft, run = svc
    ft.add("GET", "people/c1", {"etag": "E1"})
    ft.add("PATCH", "people/c1:updateContact", PERSON)
    out = run("contacts", "update", "people/c1",
              "--name", "Ada King", "--email", "ada@k.com")
    assert "personFields=names%2CemailAddresses" in ft.calls[0]["url"]
    assert "updatePersonFields=names%2CemailAddresses" in ft.calls[1]["url"]
    assert json.loads(ft.calls[1]["data"]) == {
        "etag": "E1",
        "names": [{"unstructuredName": "Ada King"}],
        "emailAddresses": [{"value": "ada@k.com"}],
    }
    assert "updated" in out and "people/c1" in out


def test_contacts_update_without_flags_errors(svc):
    ft, run = svc
    run("contacts", "update", "people/c1", expect=1)
    assert ft.calls == []


def test_contacts_groups_list(svc):
    ft, run = svc
    ft.add("GET", "contactGroups", {"contactGroups": [
        {"resourceName": "contactGroups/g1", "name": "Friends",
         "memberCount": 3}]})
    out = run("contacts", "groups", "list")
    assert "RESOURCE" in out and "NAME" in out and "MEMBERS" in out
    assert "contactGroups/g1" in out and "Friends" in out and "3" in out


def test_contacts_groups_create(svc):
    ft, run = svc
    ft.add("POST", "contactGroups", {"resourceName": "contactGroups/g2",
                                     "name": "Team"})
    out = run("contacts", "groups", "create", "--name", "Team")
    assert json.loads(ft.calls[0]["data"]) == {"contactGroup": {"name": "Team"}}
    assert "created" in out and "contactGroups/g2" in out


def test_contacts_groups_add(svc):
    ft, run = svc
    ft.add("POST", "contactGroups/g1/members:modify", {})
    out = run("contacts", "groups", "add", "contactGroups/g1", "people/c1")
    assert json.loads(ft.calls[0]["data"]) == {
        "resourceNamesToAdd": ["people/c1"]}
    assert "added" in out and "people/c1" in out and "contactGroups/g1" in out


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


def test_tasks_update_patches_only_given_fields(svc):
    ft, run = svc
    ft.add("PATCH", "lists/@default/tasks/t1", {"id": "t1"})
    out = run("tasks", "update", "t1", "--title", "New title",
              "--due", "2026-02-01")
    assert json.loads(ft.calls[0]["data"]) == {
        "title": "New title", "due": "2026-02-01T00:00:00Z"}
    assert "updated" in out and "t1" in out


def test_tasks_update_without_fields_errors(svc):
    ft, run = svc
    run("tasks", "update", "t1", expect=1)
    assert ft.calls == []


def test_tasks_move_sends_query_params(svc):
    ft, run = svc
    ft.add("POST", "lists/@default/tasks/t1/move", {"id": "t1"})
    out = run("tasks", "move", "t1", "--after", "t9", "--parent", "p1")
    url = ft.calls[0]["url"]
    assert "/lists/@default/tasks/t1/move" in url
    assert "previous=t9" in url and "parent=p1" in url
    assert "moved" in out and "t1" in out


def test_tasks_clear_completed(svc):
    ft, run = svc
    ft.add("POST", "lists/tl9/clear", {})
    out = run("tasks", "clear-completed", "--list", "tl9")
    assert ft.calls[0]["url"].endswith("lists/tl9/clear")
    assert "cleared completed tasks in" in out and "tl9" in out
