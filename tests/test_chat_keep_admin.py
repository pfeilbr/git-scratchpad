import json

import pytest


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


# -- chat ---------------------------------------------------------------------

def test_chat_spaces(svc):
    ft, run = svc
    ft.add("GET", "chat.googleapis.com/v1/spaces", {"spaces": [
        {"name": "spaces/A", "displayName": "Team room", "spaceType": "SPACE"}]})
    out = run("chat", "spaces")
    assert "Team room" in out and "spaces/A" in out


def test_chat_send(svc):
    ft, run = svc
    ft.add("POST", "spaces/A/messages", {"name": "spaces/A/messages/1"})
    run("chat", "send", "spaces/A", "--text", "hello team")
    assert json.loads(ft.calls[0]["data"]) == {"text": "hello team"}


def test_chat_messages(svc):
    ft, run = svc
    ft.add("GET", "spaces/A/messages", {"messages": [
        {"name": "spaces/A/messages/1", "text": "hi",
         "sender": {"name": "users/7"}, "createTime": "2026-01-05T00:00:00Z"}]})
    assert "hi" in run("chat", "messages", "spaces/A")


# -- keep ---------------------------------------------------------------------

def test_keep_list(svc):
    ft, run = svc
    ft.add("GET", "keep.googleapis.com/v1/notes", {"notes": [
        {"name": "notes/n1", "title": "Groceries"}]})
    assert "Groceries" in run("keep", "list")


def test_keep_get(svc):
    ft, run = svc
    ft.add("GET", "notes/n1", {"name": "notes/n1", "title": "Groceries",
                               "body": {"text": {"text": "milk\neggs"}}})
    out = run("keep", "get", "notes/n1")
    assert "milk" in out


def test_keep_create(svc):
    ft, run = svc
    ft.add("POST", "keep.googleapis.com/v1/notes", {"name": "notes/n2"})
    run("keep", "create", "--title", "Ideas", "--text", "build a cli")
    body = json.loads(ft.calls[0]["data"])
    assert body["title"] == "Ideas"
    assert body["body"]["text"]["text"] == "build a cli"


# -- admin ---------------------------------------------------------------------

def test_admin_users_list(svc):
    ft, run = svc
    ft.add("GET", "admin/directory/v1/users", {"users": [
        {"primaryEmail": "u@corp.com", "name": {"fullName": "U Ser"},
         "suspended": False, "isAdmin": True}]})
    out = run("admin", "users", "list")
    assert "u@corp.com" in out and "U Ser" in out
    assert "customer=my_customer" in ft.calls[0]["url"]


def test_admin_users_create(svc):
    ft, run = svc
    ft.add("POST", "admin/directory/v1/users", {"primaryEmail": "n@corp.com"})
    run("admin", "users", "create", "--email", "n@corp.com",
        "--first", "New", "--last", "Person", "--password", "hunter22")
    body = json.loads(ft.calls[0]["data"])
    assert body["primaryEmail"] == "n@corp.com"
    assert body["name"] == {"givenName": "New", "familyName": "Person"}
    assert body["password"] == "hunter22"


def test_admin_users_suspend_and_delete(svc):
    ft, run = svc
    ft.add("PATCH", "users/u%40corp.com", {})
    run("admin", "users", "suspend", "u@corp.com")
    assert json.loads(ft.calls[0]["data"]) == {"suspended": True}
    ft.add("DELETE", "users/u%40corp.com", {})
    run("admin", "users", "delete", "u@corp.com")


def test_admin_groups_and_members(svc):
    ft, run = svc
    ft.add("GET", "admin/directory/v1/groups", {"groups": [
        {"email": "eng@corp.com", "name": "Engineering",
         "directMembersCount": "5"}]})
    assert "eng@corp.com" in run("admin", "groups", "list")
    ft.add("GET", "groups/eng%40corp.com/members", {"members": [
        {"email": "u@corp.com", "role": "MEMBER", "status": "ACTIVE"}]})
    assert "u@corp.com" in run("admin", "groups", "members", "eng@corp.com")
    ft.add("POST", "groups/eng%40corp.com/members", {"email": "new@corp.com"})
    run("admin", "groups", "add-member", "eng@corp.com", "new@corp.com")
    assert json.loads(ft.calls[-1]["data"]) == {"email": "new@corp.com",
                                                "role": "MEMBER"}
