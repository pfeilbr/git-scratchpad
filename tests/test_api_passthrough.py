import json

import pytest


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


def test_api_call_get_with_params_and_shorthand_path(svc):
    ft, run = svc
    ft.add("GET", "www.googleapis.com/drive/v3/about", {"user": {"emailAddress":
                                                                 "a@x.com"}})
    out = run("api", "call", "GET", "drive/v3/about", "--param",
              "fields=user")
    assert "a@x.com" in out
    assert "fields=user" in ft.calls[0]["url"]


def test_api_call_full_url_and_body(svc):
    ft, run = svc
    ft.add("POST", "example.googleapis.com/v1/things", {"id": "t1"})
    run("api", "call", "POST", "https://example.googleapis.com/v1/things",
        "--body", '{"name": "thing"}')
    assert json.loads(ft.calls[0]["data"]) == {"name": "thing"}


def test_api_call_bad_body_json_errors(svc):
    ft, run = svc
    run("api", "call", "POST", "x/y", "--body", "{not json", expect=1)


def test_api_describe_flattens_methods(svc):
    ft, run = svc
    ft.add("GET", "discovery/v1/apis/tasks/v1/rest", {
        "name": "tasks", "version": "v1",
        "resources": {
            "tasklists": {"methods": {
                "list": {"id": "tasks.tasklists.list", "httpMethod": "GET",
                         "path": "users/@me/lists",
                         "description": "Lists task lists."}}},
            "tasks": {"resources": {"sub": {"methods": {
                "get": {"id": "tasks.sub.get", "httpMethod": "GET",
                        "path": "x/y", "description": "d"}}}}},
        },
    })
    out = run("api", "describe", "tasks", "--api-version", "v1")
    assert "tasks.tasklists.list" in out
    assert "tasks.sub.get" in out
    assert "users/@me/lists" in out


def test_api_list_directory(svc):
    ft, run = svc
    ft.add("GET", "discovery/v1/apis?preferred=true", {"items": [
        {"name": "gmail", "version": "v1", "title": "Gmail API"}]})
    out = run("api", "list")
    assert "gmail" in out and "Gmail API" in out
