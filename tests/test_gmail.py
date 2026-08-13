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


def full_msg(msg_id, headers, body_text):
    return {"id": msg_id, "threadId": "t1",
            "payload": {"mimeType": "text/plain",
                        "headers": [{"name": k, "value": v}
                                    for k, v in headers.items()],
                        "body": {"data": b64u(body_text)}}}


ATTACHMENT_MESSAGE = {
    "id": "m1", "threadId": "t1",
    "payload": {"mimeType": "multipart/mixed", "parts": [
        {"mimeType": "text/plain", "filename": "", "body": {"data": "aGk"}},
        {"mimeType": "image/png", "filename": "pic.png",
         "body": {"attachmentId": "att1", "size": 6}},
        {"mimeType": "multipart/alternative", "parts": [
            {"mimeType": "application/pdf", "filename": "doc.pdf",
             "body": {"attachmentId": "att2", "size": 8}},
        ]},
    ]},
}


def test_thread_renders_each_message_block(gmail):
    ft, run = gmail
    ft.add("GET", "threads/t1", {"id": "t1", "messages": [
        full_msg("m1", {"From": "alice@x.com", "Subject": "Hello",
                        "Date": "Mon, 1 Jan 2026 10:00:00 +0000"},
                 "first message body"),
        full_msg("m2", {"From": "bob@x.com", "Subject": "Re: Hello",
                        "Date": "Tue, 2 Jan 2026 10:00:00 +0000"},
                 "second message body"),
    ]})
    out = run("gmail", "thread", "t1")
    assert "/threads/t1" in ft.calls[0]["url"]
    assert "format=full" in ft.calls[0]["url"]
    assert "from: alice@x.com" in out
    assert "date: Mon, 1 Jan 2026 10:00:00 +0000" in out
    assert "subject: Hello" in out
    # blank line separates one message's body from the next message's headers
    assert "first message body\n\nfrom: bob@x.com" in out
    assert "second message body" in out


def test_thread_json_prints_raw_thread(gmail):
    ft, run = gmail
    thread = {"id": "t1", "messages": [
        full_msg("m1", {"From": "alice@x.com", "Subject": "Hello"}, "body one"),
    ]}
    ft.add("GET", "threads/t1", thread)
    out = run("--json", "gmail", "thread", "t1")
    assert json.loads(out) == thread


def test_attachments_lists_filename_mime_size(gmail):
    ft, run = gmail
    ft.add("GET", "messages/m1", ATTACHMENT_MESSAGE)
    out = run("gmail", "attachments", "m1")
    assert "format=full" in ft.calls[0]["url"]
    assert "FILENAME" in out and "MIME" in out and "SIZE" in out
    assert "pic.png" in out and "image/png" in out and "6" in out
    assert "doc.pdf" in out and "application/pdf" in out  # nested part found
    assert "hi" not in out  # body part without attachmentId is not listed


def test_attachments_download_writes_files(gmail, tmp_path):
    ft, run = gmail
    png = b"\x89PNG\r\n"
    pdf = b"%PDF-1.4"
    ft.add("GET", "messages/m1", ATTACHMENT_MESSAGE)
    ft.add("GET", "attachments/att1",
           {"data": base64.urlsafe_b64encode(png).decode().rstrip("="),
            "size": len(png)})
    ft.add("GET", "attachments/att2",
           {"data": base64.urlsafe_b64encode(pdf).decode().rstrip("="),
            "size": len(pdf)})
    dest = tmp_path / "atts"
    out = run("gmail", "attachments", "m1", "-o", str(dest))
    assert "messages/m1/attachments/att1" in ft.calls[1]["url"]
    assert (dest / "pic.png").read_bytes() == png
    assert (dest / "doc.pdf").read_bytes() == pdf
    assert f"wrote {len(png)} bytes to {dest / 'pic.png'}" in out
    assert f"wrote {len(pdf)} bytes to {dest / 'doc.pdf'}" in out


def test_send_with_attachments(gmail, tmp_path):
    ft, run = gmail
    report = tmp_path / "report.txt"
    report.write_text("quarterly numbers")
    blob = tmp_path / "data.bin"
    blob.write_bytes(b"\x00\x01\x02")
    ft.add("POST", "messages/send", {"id": "sent9"})
    run("gmail", "send", "--to", "dst@x.com", "--subject", "files",
        "--body", "see attached", "--attach", str(report),
        "--attach", str(blob))
    _, mime = sent_mime(ft)
    assert mime.is_multipart()
    body_part = next(p for p in mime.walk()
                     if p.get_content_type() == "text/plain"
                     and not p.get_filename())
    assert "see attached" in body_part.get_payload()
    atts = {p.get_filename(): p for p in mime.walk() if p.get_filename()}
    assert atts["report.txt"].get_payload(decode=True) == b"quarterly numbers"
    assert atts["report.txt"].get_content_type() == "text/plain"
    assert atts["data.bin"].get_payload(decode=True) == b"\x00\x01\x02"
    assert atts["data.bin"].get_content_type() == "application/octet-stream"


def test_drafts_create_with_attachment(gmail, tmp_path):
    ft, run = gmail
    notes = tmp_path / "notes.txt"
    notes.write_text("draft attachment")
    ft.add("POST", "drafts", {"id": "d9"})
    run("gmail", "drafts", "create", "--to", "x@x.com", "--subject", "s",
        "--body", "b", "--attach", str(notes))
    _, mime = sent_mime(ft)
    names = [p.get_filename() for p in mime.walk() if p.get_filename()]
    assert names == ["notes.txt"]
    atts = {p.get_filename(): p for p in mime.walk() if p.get_filename()}
    assert atts["notes.txt"].get_payload(decode=True) == b"draft attachment"
