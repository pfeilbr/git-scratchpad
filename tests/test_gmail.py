import base64
import email
import json

import pytest


def b64u(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def sent_mime(ft, call_index=-1):
    """Decode the MIME message from a messages/send or drafts POST."""
    payload = json.loads(ft.calls[call_index]["data"])
    raw = payload.get("raw") or payload["message"]["raw"]
    padded = raw + "=" * (-len(raw) % 4)
    return payload, email.message_from_bytes(base64.urlsafe_b64decode(padded))


def meta(msg_id, headers, thread="t1", snippet=""):
    return {
        "id": msg_id,
        "threadId": thread,
        "snippet": snippet,
        "payload": {"headers": [{"name": k, "value": v} for k, v in headers.items()]},
    }


@pytest.fixture
def gmail(authed, fake_transport, run_cli):
    return fake_transport, run_cli


def test_search_lists_messages_with_headers(gmail):
    ft, run = gmail
    ft.add("GET", "messages?", {"messages": [{"id": "m1"}, {"id": "m2"}]})
    ft.add("GET", "messages/m1", meta("m1", {"From": "alice@x.com",
                                             "Subject": "Hello",
                                             "Date": "Mon, 1 Jan 2026 10:00:00 +0000"}))
    ft.add("GET", "messages/m2", meta("m2", {"From": "bob@x.com",
                                             "Subject": "Ping",
                                             "Date": "Tue, 2 Jan 2026 10:00:00 +0000"}))
    out = run("gmail", "search", "is:unread", "--max", "2")
    assert "alice@x.com" in out and "Ping" in out and "m1" in out
    assert "q=is%3Aunread" in ft.calls[0]["url"]


def test_get_decodes_plain_text_body(gmail):
    ft, run = gmail
    ft.add("GET", "messages/m1", {
        "id": "m1", "threadId": "t1",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [{"name": "From", "value": "alice@x.com"},
                        {"name": "Subject", "value": "Hello"}],
            "parts": [
                {"mimeType": "text/html", "body": {"data": b64u("<b>nope</b>")}},
                {"mimeType": "text/plain", "body": {"data": b64u("plain wins")}},
            ],
        },
    })
    out = run("gmail", "get", "m1")
    assert "plain wins" in out and "alice@x.com" in out
    assert "nope" not in out


def test_send_builds_rfc822(gmail):
    ft, run = gmail
    ft.add("POST", "messages/send", {"id": "sent1"})
    out = run("gmail", "send", "--to", "dst@x.com", "--subject", "Hi there",
              "--body", "the body", "--cc", "cc@x.com")
    _, mime = sent_mime(ft)
    assert mime["To"] == "dst@x.com"
    assert mime["Cc"] == "cc@x.com"
    assert mime["Subject"] == "Hi there"
    assert "the body" in mime.get_payload()
    assert "sent1" in out


def test_reply_threads_onto_original(gmail):
    ft, run = gmail
    ft.add("GET", "messages/m1", meta("m1", {"From": "alice@x.com",
                                             "Subject": "Question",
                                             "Message-ID": "<orig@x>"}))
    ft.add("POST", "messages/send", {"id": "sent2"})
    run("gmail", "reply", "m1", "--body", "answer")
    payload, mime = sent_mime(ft)
    assert payload["threadId"] == "t1"
    assert mime["To"] == "alice@x.com"
    assert mime["Subject"] == "Re: Question"
    assert mime["In-Reply-To"] == "<orig@x>"


def test_forward_prefixes_subject_and_quotes(gmail):
    ft, run = gmail
    ft.add("GET", "messages/m1", {
        "id": "m1", "threadId": "t1",
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": "From", "value": "alice@x.com"},
                        {"name": "Subject", "value": "News"}],
            "body": {"data": b64u("original text")},
        },
    })
    ft.add("POST", "messages/send", {"id": "sent3"})
    run("gmail", "forward", "m1", "--to", "third@x.com")
    _, mime = sent_mime(ft)
    assert mime["To"] == "third@x.com"
    assert mime["Subject"] == "Fwd: News"
    assert "original text" in mime.get_payload()


def test_labels_list_and_create(gmail):
    ft, run = gmail
    ft.add("GET", "labels", {"labels": [{"id": "L1", "name": "INBOX",
                                         "type": "system"}]})
    assert "INBOX" in run("gmail", "labels", "list")
    ft.add("POST", "labels", {"id": "L2", "name": "todo"})
    run("gmail", "labels", "create", "todo")
    assert json.loads(ft.calls[-1]["data"])["name"] == "todo"


def test_labels_apply_resolves_name_to_id(gmail):
    ft, run = gmail
    ft.add("GET", "labels", {"labels": [{"id": "L9", "name": "todo"}]})
    ft.add("POST", "messages/m1/modify", {"id": "m1"})
    run("gmail", "labels", "apply", "m1", "todo")
    assert json.loads(ft.calls[-1]["data"]) == {"addLabelIds": ["L9"]}


def test_labels_apply_unknown_name_errors(gmail):
    ft, run = gmail
    ft.add("GET", "labels", {"labels": []})
    run("gmail", "labels", "apply", "m1", "ghost", expect=1)


def test_trash(gmail):
    ft, run = gmail
    ft.add("POST", "messages/m1/trash", {"id": "m1"})
    run("gmail", "trash", "m1")


def test_drafts_list_and_create(gmail):
    ft, run = gmail
    ft.add("GET", "drafts", {"drafts": [{"id": "d1", "message": {"id": "m1"}}]})
    assert "d1" in run("gmail", "drafts", "list")
    ft.add("POST", "drafts", {"id": "d2"})
    run("gmail", "drafts", "create", "--to", "x@x.com", "--subject", "s",
        "--body", "b")
    payload, mime = sent_mime(ft)
    assert mime["To"] == "x@x.com"
