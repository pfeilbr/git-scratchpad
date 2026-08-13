import json

import pytest


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


def test_keep_rm_normalizes_bare_id(svc):
    ft, run = svc
    ft.add("DELETE", "keep.googleapis.com/v1/notes/n1", {})
    out = run("keep", "rm", "n1")
    assert "deleted notes/n1" in out
    assert ft.calls[0]["method"] == "DELETE"
    assert "keep.googleapis.com/v1/notes/n1" in ft.calls[0]["url"]


def test_keep_share_batch_create_body(svc):
    ft, run = svc
    ft.add("POST", "notes/n1/permissions:batchCreate", {})
    out = run("keep", "share", "n1", "bob@x.com")
    assert json.loads(ft.calls[0]["data"]) == {"requests": [
        {"parent": "notes/n1",
         "permission": {"role": "WRITER", "email": "bob@x.com"}}]}
    assert "shared notes/n1 with bob@x.com" in out


def test_keep_unshare_deletes_matching_permission(svc):
    ft, run = svc
    ft.add("GET", "keep.googleapis.com/v1/notes/n1", {
        "name": "notes/n1", "permissions": [
            {"name": "notes/n1/permissions/p1", "email": "owner@x.com",
             "role": "OWNER"},
            {"name": "notes/n1/permissions/p2", "email": "bob@x.com",
             "role": "WRITER"}]})
    ft.add("POST", "notes/n1/permissions:batchDelete", {})
    out = run("keep", "unshare", "notes/n1", "bob@x.com")
    assert json.loads(ft.calls[1]["data"]) == {
        "names": ["notes/n1/permissions/p2"]}
    assert "unshared bob@x.com from notes/n1" in out


def test_keep_unshare_unknown_email_fails_after_get_only(svc):
    ft, run = svc
    ft.add("GET", "keep.googleapis.com/v1/notes/n1", {
        "name": "notes/n1", "permissions": [
            {"name": "notes/n1/permissions/p1", "email": "owner@x.com",
             "role": "OWNER"}]})
    run("keep", "unshare", "n1", "nobody@x.com", expect=1)
    assert len(ft.calls) == 1
