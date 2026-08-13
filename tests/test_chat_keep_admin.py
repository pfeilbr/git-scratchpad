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


def test_chat_create_space(svc):
    ft, run = svc
    ft.add("POST", "chat.googleapis.com/v1/spaces", {"name": "spaces/B"})
    out = run("chat", "create-space", "--name", "War room")
    assert json.loads(ft.calls[0]["data"]) == {
        "displayName": "War room", "spaceType": "SPACE"}
    assert "created spaces/B" in out
    ft.add("POST", "chat.googleapis.com/v1/spaces", {"name": "spaces/C"})
    run("chat", "create-space", "--name", "Chatter", "--type", "GROUP_CHAT")
    assert json.loads(ft.calls[-1]["data"]) == {
        "displayName": "Chatter", "spaceType": "GROUP_CHAT"}


def test_chat_members(svc):
    ft, run = svc
    ft.add("GET", "spaces/A/members", {"memberships": [
        {"name": "spaces/A/members/1",
         "member": {"name": "users/7", "type": "HUMAN"},
         "role": "ROLE_MEMBER"}]})
    out = run("chat", "members", "spaces/A")
    assert "NAME" in out and "MEMBER" in out and "TYPE" in out and "ROLE" in out
    assert "spaces/A/members/1" in out and "users/7" in out
    assert "HUMAN" in out and "ROLE_MEMBER" in out


def test_chat_add_member_normalizes_user(svc):
    ft, run = svc
    ft.add("POST", "spaces/A/members", {})
    out = run("chat", "add-member", "spaces/A", "u123")
    assert json.loads(ft.calls[0]["data"]) == {
        "member": {"name": "users/u123", "type": "HUMAN"}}
    assert "added users/u123 to spaces/A" in out
    ft.add("POST", "spaces/A/members", {})
    run("chat", "add-member", "spaces/A", "users/u123")
    assert json.loads(ft.calls[-1]["data"]) == {
        "member": {"name": "users/u123", "type": "HUMAN"}}


def test_chat_reply_threaded(svc):
    ft, run = svc
    ft.add("POST", "spaces/A/messages", {"name": "spaces/A/messages/9"})
    out = run("chat", "reply", "spaces/A",
              "--thread", "spaces/A/threads/T", "--text", "on it")
    assert "messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD" \
        in ft.calls[0]["url"]
    assert json.loads(ft.calls[0]["data"]) == {
        "text": "on it", "thread": {"name": "spaces/A/threads/T"}}
    assert "sent spaces/A/messages/9" in out


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


def test_admin_users_update_partial(svc):
    ft, run = svc
    ft.add("PATCH", "users/u%40corp.com", {})
    out = run("admin", "users", "update", "u@corp.com",
              "--first", "Jane", "--orgunit", "/Engineering")
    assert json.loads(ft.calls[0]["data"]) == {
        "name": {"givenName": "Jane"}, "orgUnitPath": "/Engineering"}
    assert "updated u@corp.com" in out
    ft.add("PATCH", "users/u%40corp.com", {})
    run("admin", "users", "update", "u@corp.com",
        "--last", "Doe", "--primary-email", "jane@corp.com")
    assert json.loads(ft.calls[-1]["data"]) == {
        "name": {"familyName": "Doe"}, "primaryEmail": "jane@corp.com"}


def test_admin_users_update_requires_a_flag(svc):
    ft, run = svc
    run("admin", "users", "update", "u@corp.com", expect=1)
    assert ft.calls == []


def test_admin_users_reset_password(svc):
    ft, run = svc
    ft.add("PATCH", "users/u%40corp.com", {})
    out = run("admin", "users", "reset-password", "u@corp.com",
              "--password", "s3cret", "--change-at-next-login")
    assert json.loads(ft.calls[0]["data"]) == {
        "password": "s3cret", "changePasswordAtNextLogin": True}
    assert "password reset for u@corp.com" in out
    ft.add("PATCH", "users/u%40corp.com", {})
    run("admin", "users", "reset-password", "u@corp.com",
        "--password", "s3cret")
    assert json.loads(ft.calls[-1]["data"]) == {
        "password": "s3cret", "changePasswordAtNextLogin": False}


def test_admin_groups_rm_member(svc):
    ft, run = svc
    ft.add("DELETE", "groups/eng%40corp.com/members/u%40corp.com", {})
    out = run("admin", "groups", "rm-member", "eng@corp.com", "u@corp.com")
    assert "removed u@corp.com from eng@corp.com" in out
    assert ft.calls[0]["method"] == "DELETE"
    assert "groups/eng%40corp.com/members/u%40corp.com" in ft.calls[0]["url"]


def test_admin_groups_delete(svc):
    ft, run = svc
    ft.add("DELETE", "groups/eng%40corp.com", {})
    out = run("admin", "groups", "delete", "eng@corp.com")
    assert "deleted eng@corp.com" in out
    assert ft.calls[0]["method"] == "DELETE"


def test_admin_orgunits(svc):
    ft, run = svc
    ft.add("GET", "customer/my_customer/orgunits", {"organizationUnits": [
        {"orgUnitPath": "/Engineering", "name": "Engineering",
         "parentOrgUnitPath": "/"},
        {"orgUnitPath": "/Engineering/Platform", "name": "Platform",
         "parentOrgUnitPath": "/Engineering"}]})
    out = run("admin", "orgunits")
    assert "PATH" in out and "NAME" in out and "PARENT" in out
    assert "/Engineering/Platform" in out and "Platform" in out
    assert "type=all" in ft.calls[0]["url"]
