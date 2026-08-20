import json

import pytest

from gsuite.api import Client
from gsuite.errors import APIError, CLIError
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


def test_list_param_repeats_the_key(client):
    """doseq expansion: a list value becomes one occurrence per item — what
    `gmail._fetch_meta` and `api call --param k=a --param k=b` both rely on."""
    c, ft = client
    ft.add("GET", "metadataHeaders=From&metadataHeaders=Subject", {"ok": True})
    c.get("https://gmail.googleapis.com/v1/m",
          params={"format": "metadata",
                  "metadataHeaders": ["From", "Subject"]})


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


def test_raw_returns_non_json_bytes_untouched(client):
    """Regression pin: raw=True never parses, so `drive export`/`download`
    keep receiving exactly the bytes Google sent, JSON or not."""
    c, ft = client
    ft.add("GET", "/export", b"col1,col2\n1,2\n")
    assert c.get("https://www.googleapis.com/drive/v3/files/f1/export",
                 raw=True) == b"col1,col2\n1,2\n"


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


# -- retry / backoff ---------------------------------------------------------

@pytest.fixture
def sleeps(monkeypatch):
    """Record delays passed to gsuite.api._sleep instead of really sleeping."""
    recorded = []
    monkeypatch.setattr("gsuite.api._sleep", recorded.append, raising=False)
    return recorded


def test_429_retries_then_succeeds(client, sleeps):
    c, ft = client
    ft.add("GET", "/v1/x", {"error": {"message": "rate limited"}}, status=429)
    ft.add("GET", "/v1/x", {"ok": True})
    assert c.get("https://example.googleapis.com/v1/x") == {"ok": True}
    assert sleeps == [1]


def test_persistent_503_backs_off_then_raises(client, sleeps):
    c, ft = client
    for _ in range(4):
        ft.add("GET", "/v1/x", {"error": {"message": "backend error"}}, status=503)
    with pytest.raises(APIError, match="backend error") as exc:
        c.get("https://example.googleapis.com/v1/x")
    assert exc.value.status == 503
    assert sleeps == [1, 2, 4]
    assert len(ft.calls) == 4


def test_retry_after_header_overrides_backoff(client, sleeps):
    c, ft = client
    ft.add("GET", "/v1/x", {"error": {"message": "rate limited"}}, status=429,
           headers={"Retry-After": "7"})
    ft.add("GET", "/v1/x", {"ok": True})
    assert c.get("https://example.googleapis.com/v1/x") == {"ok": True}
    assert sleeps == [7]


def test_400_is_not_retried(client, sleeps):
    c, ft = client
    ft.add("GET", "/v1/x", {"error": {"message": "bad request"}}, status=400)
    with pytest.raises(APIError) as exc:
        c.get("https://example.googleapis.com/v1/x")
    assert exc.value.status == 400
    assert len(ft.calls) == 1
    assert sleeps == []


def test_401_refresh_flow_does_not_sleep(client, sleeps):
    c, ft = client
    ft.add("GET", "/v1/x", {"error": {"message": "unauthorized"}}, status=401)
    ft.add("POST", "oauth2.googleapis.com/token",
           {"access_token": "tok2", "expires_in": 3600})
    ft.add("GET", "/v1/x", {"ok": True})
    assert c.get("https://example.googleapis.com/v1/x") == {"ok": True}
    assert ft.calls[-1]["headers"]["Authorization"] == "Bearer tok2"
    assert sleeps == []


# -- idempotency: a 5xx must never replay a write ----------------------------

# Idempotent by definition — repeating one has the same effect as sending it
# once, so a lost reply costs nothing but a second round trip.
IDEMPOTENT = ["GET", "PUT", "DELETE"]
# Not idempotent — each delivery is another sent mail, another created event,
# another group member.
NON_IDEMPOTENT = ["POST", "PATCH"]


@pytest.mark.parametrize("status", [500, 502, 503, 504])
@pytest.mark.parametrize("method", NON_IDEMPOTENT)
def test_5xx_never_replays_a_non_idempotent_request(client, sleeps, method,
                                                    status):
    """A 5xx often means the request WAS applied and only the reply was lost,
    so resending it could send the same mail or create the same event twice.
    One attempt, then fail."""
    c, ft = client
    for _ in range(4):  # four replies queued: the client must want only one
        ft.add(method, "/v1/x", {"error": {"message": "backend error"}},
               status=status)
    with pytest.raises(APIError, match="backend error") as exc:
        c.request(method, "https://example.googleapis.com/v1/x",
                  json_body={"n": 1})
    assert exc.value.status == status
    assert len(ft.calls) == 1
    assert sleeps == []


@pytest.mark.parametrize("method", IDEMPOTENT)
def test_5xx_still_retries_an_idempotent_request(client, sleeps, method):
    """Regression pin: replaying these cannot duplicate anything, so they keep
    the full backoff budget."""
    c, ft = client
    for _ in range(4):
        ft.add(method, "/v1/x", {"error": {"message": "backend error"}},
               status=503)
    with pytest.raises(APIError, match="backend error"):
        c.request(method, "https://example.googleapis.com/v1/x")
    assert len(ft.calls) == 4
    assert sleeps == [1, 2, 4]


@pytest.mark.parametrize("method", NON_IDEMPOTENT + IDEMPOTENT)
def test_429_still_retries_every_method(client, sleeps, method):
    """Regression pin: a 429 is a rejection — nothing ran — so replaying it is
    safe for writes too, and backing off is what Google's guidance asks for."""
    c, ft = client
    ft.add(method, "/v1/x", {"error": {"message": "rate limited"}}, status=429)
    ft.add(method, "/v1/x", {"ok": True})
    assert c.request(method,
                     "https://example.googleapis.com/v1/x") == {"ok": True}
    assert len(ft.calls) == 2
    assert sleeps == [1]


def test_401_refresh_still_retries_a_post_once(client, sleeps):
    """Regression pin: a 401 is rejected for authentication before the handler
    ever runs, so refresh-and-retry-once stays intact for writes."""
    c, ft = client
    ft.add("POST", "/v1/x", {"error": {"message": "unauthorized"}}, status=401)
    ft.add("POST", "oauth2.googleapis.com/token",
           {"access_token": "tok2", "expires_in": 3600})
    ft.add("POST", "/v1/x", {"ok": True})
    assert c.post("https://example.googleapis.com/v1/x",
                  json_body={"n": 1}) == {"ok": True}
    assert ft.calls[-1]["headers"]["Authorization"] == "Bearer tok2"
    assert sleeps == []


def test_5xx_on_a_write_explains_why_it_was_not_retried(client, sleeps):
    """The user has to decide whether to re-run it by hand, so the error says
    it was not replayed and may or may not have taken effect."""
    c, ft = client
    ft.add("POST", "/messages/send", {"error": {"message": "Backend Error"}},
           status=503)
    with pytest.raises(APIError) as exc:
        c.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
               json_body={"raw": "..."})
    msg = str(exc.value)
    assert "Backend Error" in msg  # Google's own text still leads
    assert "not retried" in msg
    assert "duplicate" in msg
    assert "may or may not have been applied" in msg


# -- actionable error hints --------------------------------------------------

# Real shapes of Google's 403 bodies: the human message, and the machine
# reason that carries the same news when the message is less specific.
SCOPE_403 = {"error": {
    "code": 403, "status": "PERMISSION_DENIED",
    "message": "Request had insufficient authentication scopes.",
    "errors": [{"message": "Insufficient Permission", "reason": "insufficientPermissions"}],
}}
SCOPE_403_BY_REASON = {"error": {
    "code": 403, "status": "PERMISSION_DENIED", "message": "Permission denied.",
    "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
                 "reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}],
}}
NOT_ENABLED_403 = {"error": {
    "code": 403, "status": "PERMISSION_DENIED",
    "message": ("Google Sheets API has not been used in project 42 before or "
                "it is disabled."),
    "errors": [{"reason": "accessNotConfigured"}],
}}


def test_scope_403_names_the_service_and_account(client):
    c, ft = client
    ft.add("GET", "gmail.googleapis.com", SCOPE_403, status=403)
    with pytest.raises(APIError) as exc:
        c.get("https://gmail.googleapis.com/gmail/v1/users/me/messages")
    msg = str(exc.value)
    assert "Request had insufficient authentication scopes." in msg  # Google's own text
    assert "`gsuite auth login a@x.com --services gmail`" in msg


def test_scope_403_on_unknown_host_omits_services(client):
    c, ft = client
    ft.add("GET", "example.googleapis.com", SCOPE_403, status=403)
    with pytest.raises(APIError) as exc:
        c.get("https://example.googleapis.com/v1/x")
    msg = str(exc.value)
    assert "`gsuite auth login a@x.com`" in msg
    assert "--services" not in msg  # better silent than guessing the wrong one


def test_scope_403_tells_drive_and_calendar_apart(client):
    c, ft = client
    ft.add("GET", "/drive/v3/files", SCOPE_403_BY_REASON, status=403)
    ft.add("GET", "/calendar/v3/calendars", SCOPE_403_BY_REASON, status=403)
    with pytest.raises(APIError) as exc:
        c.get("https://www.googleapis.com/drive/v3/files")
    assert "--services drive" in str(exc.value)
    with pytest.raises(APIError) as exc:
        c.get("https://www.googleapis.com/calendar/v3/calendars/primary/events")
    assert "--services calendar" in str(exc.value)


def test_scope_403_without_an_account_suggests_bare_login(authed, fake_transport,
                                                          monkeypatch):
    monkeypatch.setenv("GSUITE_ACCESS_TOKEN", "env-tok")
    c = Client(authed, "")  # with $GSUITE_ACCESS_TOKEN there is no account to name
    fake_transport.add("GET", "sheets.googleapis.com", SCOPE_403, status=403)
    with pytest.raises(APIError) as exc:
        c.get("https://sheets.googleapis.com/v4/spreadsheets/s1")
    assert "`gsuite auth login --services sheets`" in str(exc.value)


def test_403_api_not_enabled_suggests_enabling_it(client):
    c, ft = client
    ft.add("GET", "sheets.googleapis.com", NOT_ENABLED_403, status=403)
    with pytest.raises(APIError) as exc:
        c.get("https://sheets.googleapis.com/v4/spreadsheets/s1")
    msg = str(exc.value)
    assert "has not been used in project 42" in msg  # Google's own text
    assert "Google Cloud console" in msg
    assert "auth login" not in msg  # re-authorizing would not help here


def test_429_after_retries_mentions_quota(client, sleeps):
    c, ft = client
    for _ in range(4):
        ft.add("GET", "/v1/x", {"error": {"message": "Quota exceeded."}}, status=429)
    with pytest.raises(APIError) as exc:
        c.get("https://example.googleapis.com/v1/x")
    msg = str(exc.value)
    assert "quota" in msg.lower()
    assert "retried" in msg  # tells the user backoff was already tried
    assert sleeps == [1, 2, 4]


def test_401_suggests_logging_in_again(client):
    c, ft = client
    ft.add("GET", "/v1/x", {"error": {"message": "Invalid Credentials"}}, status=401)
    ft.add("POST", "oauth2.googleapis.com/token",
           {"access_token": "tok2", "expires_in": 3600})
    ft.add("GET", "/v1/x", {"error": {"message": "Invalid Credentials"}}, status=401)
    with pytest.raises(APIError) as exc:
        c.get("https://example.googleapis.com/v1/x")
    assert "`gsuite auth login a@x.com`" in str(exc.value)


def test_unremarkable_error_message_is_unchanged(client):
    c, ft = client
    ft.add("GET", "/v1/x", {"error": {"message": "not found", "code": 404}},
           status=404)
    with pytest.raises(APIError) as exc:
        c.get("https://gmail.googleapis.com/v1/x")
    assert str(exc.value) == "HTTP 404: not found"


# -- readonly mode -----------------------------------------------------------

@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_readonly_refuses_writes_before_any_io(authed, fake_transport, method):
    c = Client(authed, "a@x.com", readonly=True)
    # Expire the token: any token refresh attempt would hit the transport,
    # so ft.calls == [] proves the guard runs before token work too.
    token = authed.load_token("a@x.com")
    token["expiry"] = 0
    authed.save_token("a@x.com", token)
    with pytest.raises(CLIError, match="readonly mode"):
        c.request(method, "https://example.googleapis.com/v1/x")
    assert fake_transport.calls == []


def test_readonly_get_still_works(authed, fake_transport):
    c = Client(authed, "a@x.com", readonly=True)
    fake_transport.add("GET", "/v1/things", {"kind": "thing"})
    assert c.get("https://example.googleapis.com/v1/things") == {"kind": "thing"}


def test_cli_readonly_blocks_gmail_trash(authed, fake_transport, run_cli):
    run_cli("--readonly", "gmail", "trash", "m1", expect=1)
    assert fake_transport.calls == []


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


# -- a 2xx whose body is not JSON --------------------------------------------

def test_non_json_success_body_is_an_error_not_a_traceback(client):
    """A 200 carrying HTML is a captive portal or a proxy, not a bug.

    `request()` ended with `json.loads(body)`, so anything that answered a
    Google URL with non-JSON — a hotel wifi splash page, a corporate proxy's
    block notice, a load balancer's plain-text "ok" — surfaced as an uncaught
    JSONDecodeError with a traceback. `api call` already handled this by
    asking for `raw=True`; every one of the other 147 commands did not.
    """
    c, ft = client
    ft.add("GET", "/v1/things", b"<html>Sign in to continue</html>")
    with pytest.raises(CLIError) as exc:
        c.get("https://example.googleapis.com/v1/things")
    message = str(exc.value)
    assert "200" in message, "the status is the first thing to check"
    assert "JSON" in message
    # The body is the evidence; without it the user cannot tell a proxy page
    # from a Google outage.
    assert "Sign in to continue" in message


def test_non_json_error_body_still_reports_googles_own_text(client, sleeps):
    """The non-JSON guard must not shadow the existing 4xx/5xx path.

    A proxy's 502 is the case that carries both properties at once: an error
    status *and* an unparseable body. It must stay an APIError quoting the
    gateway's own words, not become the generic "not JSON" message.
    """
    c, ft = client
    for _ in range(4):  # a 502 on a GET is retried; every attempt needs a route
        ft.add("GET", "/v1/things", b"upstream connect error", status=502)
    with pytest.raises(APIError) as exc:
        c.get("https://example.googleapis.com/v1/things")
    assert "upstream connect error" in str(exc.value)


def test_raw_requests_still_get_the_bytes_unparsed(client):
    """`drive download` and `api call` depend on bypassing the guard."""
    c, ft = client
    ft.add("GET", "/v1/things", b"\x89PNG\r\n\x1a\n not json")
    assert c.get("https://example.googleapis.com/v1/things",
                 raw=True) == b"\x89PNG\r\n\x1a\n not json"


def test_an_empty_body_is_still_an_empty_dict(client):
    """A 204-shaped reply from delete/patch has nothing to parse."""
    c, ft = client
    ft.add("DELETE", "/v1/things/1", b"")
    assert c.delete("https://example.googleapis.com/v1/things/1") == {}
