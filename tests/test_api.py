import json

import pytest

from gsuite.api import Client
from gsuite.errors import APIError
from gsuite.output import emit


@pytest.fixture
def client(authed, fake_transport):
    return Client(authed, "a@x.com"), fake_transport


def test_get_sends_bearer_and_parses_json(client):
    c, ft = client
    ft.add("GET", "example.googleapis.com/v1/things", {"kind": "thing"})
    assert c.get("https://example.googleapis.com/v1/things") == {"kind": "thing"}
    assert ft.calls[0]["headers"]["Authorization"] == "Bearer tok"


def test_params_are_urlencoded(client):
    c, ft = client
    ft.add("GET", "q=hello+world", {"ok": True})
    c.get("https://example.googleapis.com/v1/x", params={"q": "hello world"})


def test_post_sends_json_body(client):
    c, ft = client
    ft.add("POST", "/v1/x", {"id": "1"})
    c.post("https://example.googleapis.com/v1/x", json_body={"name": "n"})
    call = ft.calls[0]
    assert json.loads(call["data"]) == {"name": "n"}
    assert call["headers"]["Content-Type"] == "application/json"


def test_api_error_extracts_message(client):
    c, ft = client
    ft.add("GET", "/v1/x", {"error": {"message": "not found", "code": 404}},
           status=404)
    with pytest.raises(APIError, match="not found") as exc:
        c.get("https://example.googleapis.com/v1/x")
    assert exc.value.status == 404


def test_401_refreshes_and_retries_once(client):
    c, ft = client
    ft.add("GET", "/v1/x", {"error": {"message": "unauthorized"}}, status=401)
    ft.add("POST", "oauth2.googleapis.com/token",
           {"access_token": "tok2", "expires_in": 3600})
    ft.add("GET", "/v1/x", {"ok": True})
    assert c.get("https://example.googleapis.com/v1/x") == {"ok": True}
    assert ft.calls[-1]["headers"]["Authorization"] == "Bearer tok2"


def test_raw_returns_bytes(client):
    c, ft = client
    ft.add("GET", "alt=media", b"raw-bytes")
    assert c.get("https://example.googleapis.com/f?alt=media", raw=True) == b"raw-bytes"


def test_paged_follows_next_page_token(client):
    c, ft = client
    ft.add("GET", "/v1/items", {"items": [{"n": 1}], "nextPageToken": "p2"})
    ft.add("GET", "pageToken=p2", {"items": [{"n": 2}]})
    items = list(c.paged("https://example.googleapis.com/v1/items", key="items"))
    assert [i["n"] for i in items] == [1, 2]


def test_paged_respects_limit(client):
    c, ft = client
    ft.add("GET", "/v1/items", {"items": [{"n": 1}, {"n": 2}], "nextPageToken": "p2"})
    items = list(c.paged("https://example.googleapis.com/v1/items", key="items",
                         limit=2))
    assert len(items) == 2  # second page never requested


# -- output ------------------------------------------------------------------

class FakeArgs:
    def __init__(self, json_mode=False):
        self.json = json_mode


def test_emit_table_aligns_columns(capsys):
    emit(FakeArgs(), [{"id": "1", "name": "alpha"}, {"id": "22", "name": "b"}],
         [("ID", "id"), ("NAME", "name")])
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("ID")
    assert "NAME" in out[0]
    assert out[1].index("alpha") == out[2].index("b")


def test_emit_json_mode(capsys):
    rows = [{"id": "1", "name": "alpha"}]
    emit(FakeArgs(json_mode=True), rows, [("ID", "id")])
    assert json.loads(capsys.readouterr().out) == rows


def test_emit_callable_getter(capsys):
    emit(FakeArgs(), [{"a": {"b": "deep"}}], [("X", lambda r: r["a"]["b"])])
    assert "deep" in capsys.readouterr().out
