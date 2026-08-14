import io
import json
import urllib.parse
from types import SimpleNamespace

import pytest

from gsuite.errors import CLIError
from gsuite.services.api import cmd_call


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


def _query(url: str) -> list[tuple[str, str]]:
    """The decoded query string of a recorded request, order preserved."""
    return urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query)


def test_api_call_get_with_params_and_shorthand_path(svc):
    ft, run = svc
    ft.add("GET", "www.googleapis.com/drive/v3/about", {"user": {"emailAddress":
                                                                 "a@x.com"}})
    out = run("api", "call", "GET", "drive/v3/about", "--param",
              "fields=user")
    assert "a@x.com" in out
    assert "fields=user" in ft.calls[0]["url"]


# -- repeated --param keys ---------------------------------------------------

def test_api_call_repeats_a_param_key(svc):
    """Several Google APIs take a parameter more than once (Gmail's
    metadataHeaders/labelIds, Calendar's eventTypes); every occurrence must
    reach the wire, not just the last one."""
    ft, run = svc
    ft.add("GET", "gmail/v1/users/me/messages/m1", {"id": "m1"})
    run("api", "call", "GET", "gmail/v1/users/me/messages/m1",
        "--param", "format=metadata",
        "--param", "metadataHeaders=From",
        "--param", "metadataHeaders=Subject")
    assert _query(ft.calls[0]["url"]) == [("format", "metadata"),
                                          ("metadataHeaders", "From"),
                                          ("metadataHeaders", "Subject")]


def test_api_call_single_param_url_is_byte_identical(svc):
    """Regression pin: one occurrence of a key must still produce exactly the
    URL it produced before repeated keys were supported."""
    ft, run = svc
    ft.add("GET", "drive/v3/about", {"user": {}})
    run("api", "call", "GET", "drive/v3/about", "--param", "fields=user")
    assert ft.calls[0]["url"] == (
        "https://www.googleapis.com/drive/v3/about?fields=user")


def test_api_call_param_value_may_contain_equals(svc):
    """Regression pin: only the first `=` separates key from value."""
    ft, run = svc
    ft.add("GET", "gmail/v1/users/me/messages", {"messages": []})
    run("api", "call", "GET", "gmail/v1/users/me/messages",
        "--param", "q=subject:a=b has:attachment")
    assert _query(ft.calls[0]["url"]) == [("q", "subject:a=b has:attachment")]


def test_api_call_param_without_equals_errors(svc):
    """Regression pin: a --param with no `=` stays a CLIError, exit 1."""
    ft, run = svc
    run("api", "call", "GET", "drive/v3/about", "--param", "fields", expect=1)
    assert ft.calls == []


# -- non-JSON responses ------------------------------------------------------

def test_api_call_prints_non_json_body_as_text(svc):
    """Drive `export`, `alt=media` and proxy error pages answer text, not
    JSON: print the body instead of crashing."""
    ft, run = svc
    ft.add("GET", "drive/v3/files/f1/export", b"Hello, plain text.")
    out = run("api", "call", "GET", "drive/v3/files/f1/export",
              "--param", "mimeType=text/plain")
    assert out == "Hello, plain text.\n"


def test_api_call_malformed_json_is_a_clean_error(svc):
    """A truncated body from a JSON endpoint is an error, never garbage on
    stdout and never a traceback."""
    ft, run = svc
    ft.add("GET", "drive/v3/about", b'{"user": {"emailAddress"')
    out = run("api", "call", "GET", "drive/v3/about", expect=1)
    assert out == ""

    ft.add("GET", "drive/v3/about", b'{"user": {"emailAddress"')
    args = SimpleNamespace(method="GET", path="drive/v3/about", param=None,
                           body=None, account=None, readonly=False)
    with pytest.raises(CLIError, match="not valid JSON"):
        cmd_call(args)


def test_api_call_json_output_is_unchanged(svc):
    """Regression pin: a JSON reply is still pretty-printed, sorted, exactly
    as before."""
    ft, run = svc
    payload = {"user": {"emailAddress": "a@x.com"}, "kind": "drive#about"}
    ft.add("GET", "drive/v3/about", payload)
    out = run("api", "call", "GET", "drive/v3/about")
    assert out == json.dumps(payload, indent=2, sort_keys=True) + "\n"


def test_api_call_full_url_and_body(svc):
    ft, run = svc
    ft.add("POST", "example.googleapis.com/v1/things", {"id": "t1"})
    run("api", "call", "POST", "https://example.googleapis.com/v1/things",
        "--body", '{"name": "thing"}')
    assert json.loads(ft.calls[0]["data"]) == {"name": "thing"}


def test_api_call_bad_body_json_errors(svc):
    ft, run = svc
    run("api", "call", "POST", "x/y", "--body", "{not json", expect=1)


def test_api_call_body_from_file(svc, tmp_path):
    ft, run = svc
    body_file = tmp_path / "body.json"
    body_file.write_text('{"name": "from-file"}')
    ft.add("POST", "example.googleapis.com/v1/things", {"id": "t1"})
    run("api", "call", "POST", "https://example.googleapis.com/v1/things",
        "--body", f"@{body_file}")
    assert json.loads(ft.calls[0]["data"]) == {"name": "from-file"}


def test_api_call_body_from_stdin(svc, monkeypatch):
    ft, run = svc
    monkeypatch.setattr("sys.stdin", io.StringIO('{"name": "from-stdin"}'))
    ft.add("POST", "example.googleapis.com/v1/things", {"id": "t1"})
    run("api", "call", "POST", "https://example.googleapis.com/v1/things",
        "--body", "-")
    assert json.loads(ft.calls[0]["data"]) == {"name": "from-stdin"}


def test_api_call_body_missing_file_errors(svc, tmp_path):
    ft, run = svc
    run("api", "call", "POST", "x/y", "--body", f"@{tmp_path}/missing.json",
        expect=1)


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
