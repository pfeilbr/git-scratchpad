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


def test_vacation_show(gmail):
    ft, run = gmail
    ft.add("GET", "settings/vacation", {"enableAutoReply": True,
                                        "responseSubject": "OOO",
                                        "responseBodyPlainText": "back soon"})
    out = run("gmail", "vacation", "show")
    assert "settings/vacation" in ft.calls[0]["url"]
    assert "enabled: True" in out
    assert "subject: OOO" in out
    assert "body: back soon" in out


def test_vacation_set_and_off(gmail):
    ft, run = gmail
    ft.add("PUT", "settings/vacation", {"enableAutoReply": True})
    out = run("gmail", "vacation", "set", "--subject", "OOO",
              "--body", "back soon")
    assert ft.calls[-1]["method"] == "PUT"
    assert json.loads(ft.calls[-1]["data"]) == {
        "enableAutoReply": True,
        "responseSubject": "OOO",
        "responseBodyPlainText": "back soon",
    }
    assert "vacation responder enabled" in out
    ft.add("PUT", "settings/vacation", {"enableAutoReply": False})
    out = run("gmail", "vacation", "off")
    assert json.loads(ft.calls[-1]["data"]) == {"enableAutoReply": False}
    assert "vacation responder disabled" in out


SEND_AS = {"sendAs": [
    {"sendAsEmail": "alias@x.com", "signature": "alias sig"},
    {"sendAsEmail": "a@x.com", "isPrimary": True, "signature": "primary sig"},
]}


def test_signature_show_falls_back_to_primary(gmail):
    ft, run = gmail
    ft.add("GET", "settings/sendAs", SEND_AS)
    out = run("gmail", "signature", "show")
    assert "primary sig" in out
    assert "alias sig" not in out
    ft.add("GET", "settings/sendAs", SEND_AS)
    out = run("gmail", "signature", "show", "--send-as", "alias@x.com")
    assert "alias sig" in out


def test_signature_set_patches_send_as(gmail):
    ft, run = gmail
    ft.add("GET", "settings/sendAs", SEND_AS)
    ft.add("PATCH", "settings/sendAs/", {})
    out = run("gmail", "signature", "set", "--html", "<b>sig</b>",
              "--send-as", "alias@x.com")
    assert ft.calls[-1]["method"] == "PATCH"
    assert "settings/sendAs/alias%40x.com" in ft.calls[-1]["url"]
    assert json.loads(ft.calls[-1]["data"]) == {"signature": "<b>sig</b>"}
    assert "signature updated for alias@x.com" in out


def test_filters_list_and_rm(gmail):
    ft, run = gmail
    ft.add("GET", "settings/filters", {"filter": [
        {"id": "f1",
         "criteria": {"from": "spam@x.com", "query": "unsubscribe"},
         "action": {"addLabelIds": ["L1", "L2"], "removeLabelIds": ["INBOX"]}},
    ]})
    out = run("gmail", "filters", "list")
    assert "ID" in out and "FROM" in out and "QUERY" in out
    assert "ADD" in out and "REMOVE" in out
    assert "f1" in out and "spam@x.com" in out and "unsubscribe" in out
    assert "L1,L2" in out and "INBOX" in out
    ft.add("DELETE", "settings/filters/f1", {})
    out = run("gmail", "filters", "rm", "f1")
    assert "settings/filters/f1" in ft.calls[-1]["url"]
    assert "deleted f1" in out


def test_filters_create_resolves_label(gmail):
    ft, run = gmail
    ft.add("GET", "labels", {"labels": [{"id": "L9", "name": "todo"}]})
    ft.add("POST", "settings/filters", {"id": "f2"})
    out = run("gmail", "filters", "create", "--from", "spam@x.com",
              "--add-label", "todo")
    assert json.loads(ft.calls[-1]["data"]) == {
        "criteria": {"from": "spam@x.com"},
        "action": {"addLabelIds": ["L9"]},
    }
    assert "created f2" in out
    ft.add("POST", "settings/filters", {"id": "f3"})
    run("gmail", "filters", "create", "--query", "unsubscribe", "--delete")
    assert json.loads(ft.calls[-1]["data"]) == {
        "criteria": {"query": "unsubscribe"},
        "action": {"addLabelIds": ["TRASH"]},
    }


def test_filters_create_requires_criteria_and_action(gmail):
    ft, run = gmail
    run("gmail", "filters", "create", "--add-label", "todo", expect=1)
    run("gmail", "filters", "create", "--from", "spam@x.com", expect=1)
    assert ft.calls == []  # both rejected before any HTTP


def test_batch_modify_pages_and_posts_ids(gmail):
    ft, run = gmail
    ft.add("GET", "messages?", {"messages": [{"id": "m1"}, {"id": "m2"}],
                                "nextPageToken": "tok"})
    ft.add("GET", "pageToken=tok", {"messages": [{"id": "m3"}]})
    ft.add("GET", "labels", {"labels": [{"id": "L9", "name": "todo"}]})
    ft.add("POST", "messages/batchModify", {})
    out = run("gmail", "batch-modify", "--query", "from:spam",
              "--add-label", "todo")
    assert "q=from%3Aspam" in ft.calls[0]["url"]
    assert json.loads(ft.calls[-1]["data"]) == {"ids": ["m1", "m2", "m3"],
                                                "addLabelIds": ["L9"]}
    assert "modified 3 message(s)" in out


def test_batch_modify_requires_label_flag(gmail):
    ft, run = gmail
    run("gmail", "batch-modify", "--query", "from:spam", expect=1)
    assert ft.calls == []


@pytest.mark.parametrize("command, body, expected", [
    ("archive", {"removeLabelIds": ["INBOX"]}, "archived m1"),
    ("unarchive", {"addLabelIds": ["INBOX"]}, "moved to inbox m1"),
])
def test_archive_and_unarchive(gmail, command, body, expected):
    ft, run = gmail
    ft.add("POST", "messages/m1/modify", {"id": "m1"})
    out = run("gmail", command, "m1")
    assert json.loads(ft.calls[-1]["data"]) == body
    assert expected in out


@pytest.mark.parametrize("command, body, expected", [
    ("mark-read", {"removeLabelIds": ["UNREAD"]}, "marked read m1"),
    ("mark-unread", {"addLabelIds": ["UNREAD"]}, "marked unread m1"),
])
def test_mark_read_and_unread(gmail, command, body, expected):
    ft, run = gmail
    ft.add("POST", "messages/m1/modify", {"id": "m1"})
    out = run("gmail", command, "m1")
    assert json.loads(ft.calls[-1]["data"]) == body
    assert expected in out


@pytest.mark.parametrize("command, body, expected", [
    ("spam", {"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]},
     "marked spam m1"),
    ("unspam", {"addLabelIds": ["INBOX"], "removeLabelIds": ["SPAM"]},
     "unmarked spam m1"),
])
def test_spam_and_unspam_swap_inbox_and_spam(gmail, command, body, expected):
    ft, run = gmail
    ft.add("POST", "messages/m1/modify", {"id": "m1"})
    out = run("gmail", command, "m1")
    assert json.loads(ft.calls[-1]["data"]) == body
    assert expected in out


def test_untrash_posts_to_untrash_endpoint_without_body(gmail):
    ft, run = gmail
    ft.add("POST", "messages/m1/untrash", {"id": "m1"})
    out = run("gmail", "untrash", "m1")
    assert ft.calls[-1]["url"].endswith("/messages/m1/untrash")
    assert not ft.calls[-1]["data"]
    assert "untrashed m1" in out


def test_archive_uses_literal_label_without_lookup(gmail):
    """System label ids are literal, so there is no GET /labels round-trip."""
    ft, run = gmail
    ft.add("POST", "messages/m1/modify", {"id": "m1"})
    run("gmail", "archive", "m1")
    assert len(ft.calls) == 1


# --- header injection (CR/LF in header values) -------------------------------

# Shapes an attacker (or a fat-fingered script) can put in a header value.
# The first three smuggle a whole extra header; the last two are the trailing
# CR/LF that Python's own `len(value.splitlines()) > 1` guard lets through.
INJECTION_SHAPES = [
    "dst@x.com\nBcc: evil@example.com",
    "dst@x.com\r\nBcc: evil@example.com",
    "dst@x.com\rBcc: evil@example.com",
    "dst@x.com\n",
    "dst@x.com\r",
]


@pytest.mark.parametrize("hostile", INJECTION_SHAPES)
def test_send_refuses_crlf_in_to_and_sends_nothing(gmail, hostile):
    ft, run = gmail
    # No routes registered: any HTTP at all would blow up the fake transport,
    # so the clean exit 1 proves the value is rejected before the network.
    run("gmail", "send", "--to", hostile, "--subject", "hi", "--body", "b",
        expect=1)
    assert ft.calls == []


def test_send_refuses_crlf_in_subject_cc_and_bcc(gmail):
    ft, run = gmail
    run("gmail", "send", "--to", "dst@x.com",
        "--subject", "hi\r\nBcc: evil@example.com", "--body", "b", expect=1)
    run("gmail", "send", "--to", "dst@x.com", "--subject", "hi", "--body", "b",
        "--cc", "cc@x.com\nBcc: evil@example.com", expect=1)
    run("gmail", "send", "--to", "dst@x.com", "--subject", "hi", "--body", "b",
        "--bcc", "bcc@x.com\nX-Evil: 1", expect=1)
    assert ft.calls == []


def test_header_error_names_the_offending_flag_or_header():
    from gsuite.errors import CLIError
    from gsuite.services.gmail import _build_mime

    with pytest.raises(CLIError, match="--to"):
        _build_mime("a@x.com\nBcc: evil@example.com", "s", "b")
    with pytest.raises(CLIError, match="--subject"):
        _build_mime("a@x.com", "s\r\nBcc: evil@example.com", "b")
    with pytest.raises(CLIError, match="--cc"):
        _build_mime("a@x.com", "s", "b", cc="c@x.com\nX: 1")
    with pytest.raises(CLIError, match="--bcc"):
        _build_mime("a@x.com", "s", "b", bcc="c@x.com\nX: 1")
    with pytest.raises(CLIError, match="In-Reply-To"):
        _build_mime("a@x.com", "s", "b",
                    extra_headers={"In-Reply-To": "<o@x>\nBcc: evil@x.com"})


def test_reply_refuses_hostile_message_id_from_fetched_message(gmail):
    """A Message-ID on *received* mail is untrusted input, not our own value."""
    ft, run = gmail
    ft.add("GET", "messages/m1", meta("m1", {
        "From": "alice@x.com",
        "Subject": "Question",
        "Message-ID": "<orig@x>\r\nBcc: evil@example.com",
    }))
    ft.add("POST", "messages/send", {"id": "nope"})
    run("gmail", "reply", "m1", "--body", "answer", expect=1)
    # The fetch happens first and is fine; nothing may be sent afterwards.
    assert [c["method"] for c in ft.calls] == ["GET"]


def test_send_keeps_multiline_body_intact(gmail):
    """Newlines are normal in a body and must not be restricted."""
    ft, run = gmail
    ft.add("POST", "messages/send", {"id": "sentb"})
    body = "first line\nsecond line\n\nafter a blank line"
    run("gmail", "send", "--to", "dst@x.com", "--subject", "hi", "--body", body)
    _, mime = sent_mime(ft)
    assert mime.get_payload() == body + "\n"
    assert mime["To"] == "dst@x.com"


def test_send_ordinary_values_are_byte_identical(gmail):
    """Regression pin: the exact wire bytes for a normal send do not change."""
    ft, run = gmail
    ft.add("POST", "messages/send", {"id": "sentp"})
    run("gmail", "send", "--to", "dst@x.com", "--subject", "Hi there",
        "--body", "the body", "--cc", "cc@x.com")
    assert json.loads(ft.calls[-1]["data"])["raw"] == (
        "VG86IGRzdEB4LmNvbQpDYzogY2NAeC5jb20KU3ViamVjdDogSGkgdGhlcmUKQ29udGVu"
        "dC1UeXBlOiB0ZXh0L3BsYWluOyBjaGFyc2V0PSJ1dGYtOCIKQ29udGVudC1UcmFuc2Zl"
        "ci1FbmNvZGluZzogN2JpdApNSU1FLVZlcnNpb246IDEuMAoKdGhlIGJvZHkK"
    )


def test_send_allows_long_subject_that_the_library_folds(gmail):
    """Folding inserts newlines at serialization time, not into the value."""
    ft, run = gmail
    ft.add("POST", "messages/send", {"id": "sentf"})
    subject = ("Quarterly planning review for the distributed systems team "
               "covering roadmap milestones and staffing")
    run("gmail", "send", "--to", "dst@x.com", "--subject", subject,
        "--body", "b")
    raw = json.loads(ft.calls[-1]["data"])["raw"]
    wire = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
    assert "\n roadmap milestones and staffing" in wire  # really folded
    _, mime = sent_mime(ft)
    # Unfolding (dropping the inserted newline, keeping the fold whitespace)
    # gets the original subject back, so the fold is cosmetic.
    assert mime["Subject"].replace("\n", "") == subject


@pytest.mark.parametrize("separator, name", [
    ("\x0b", "vertical tab"),
    ("\x0c", "form feed"),
    (" ", "unicode line separator"),
    (" ", "unicode paragraph separator"),
    ("\x85", "next line"),
])
def test_unusual_line_separators_are_errors_not_tracebacks(separator, name):
    """`email` splits on more than CR/LF, and refuses all of them.

    Rejecting only CR/LF left the rest raising a bare ValueError straight
    past main()'s handler — a traceback where an error message belongs.
    """
    from gsuite.errors import CLIError
    from gsuite.services.gmail import _build_mime

    with pytest.raises(CLIError, match="--to"):
        _build_mime(f"a@x.com{separator}Bcc: evil@example.com", "s", "b")
    with pytest.raises(CLIError, match="--subject"):
        _build_mime("a@x.com", f"subject{separator}injected", "b")


def test_empty_header_values_are_still_allowed():
    """An empty subject is ordinary; only line breaks are refused."""
    from gsuite.services.gmail import _build_mime

    assert _build_mime("a@x.com", "", "body")  # must not raise


# -- message ids are one URL segment, not a path ----------------------------

@pytest.mark.parametrize("argv, route", [
    (("gmail", "trash", "../../oauth2/v1/tokeninfo"), "messages/"),
    (("gmail", "untrash", "../../oauth2/v1/tokeninfo"), "messages/"),
    (("gmail", "archive", "../../oauth2/v1/tokeninfo"), "messages/"),
    (("gmail", "get", "a?b#c"), "messages/"),
    (("gmail", "thread", "a?b#c"), "threads/"),
])
def test_ids_cannot_escape_their_url_segment(gmail, argv, route):
    """A message id is opaque: it must never add segments or a query string."""
    ft, run = gmail
    ft.add("GET", route, {"id": "m", "threadId": "t", "payload": {}})
    ft.add("POST", route, {"id": "m"})
    run(*argv)
    url = ft.calls[0]["url"]
    assert "/messages/../" not in url and "/threads/../" not in url
    assert "?b" not in url and "#c" not in url
    # The hostile text survives, but percent-encoded into a single segment.
    assert "%2F" in url or "%3F" in url or "%23" in url


def test_filter_ids_are_encoded_too(gmail):
    ft, run = gmail
    ft.add("DELETE", "settings/filters/", {})
    run("gmail", "filters", "rm", "../../../v1/other")
    assert "/filters/../" not in ft.calls[0]["url"]


def test_ordinary_message_ids_are_unchanged(gmail):
    """Regression pin: a normal id must produce exactly today's URL."""
    ft, run = gmail
    ft.add("POST", "messages/19ab3f/trash", {"id": "19ab3f"})
    run("gmail", "trash", "19ab3f")
    assert ft.calls[0]["url"].endswith("/users/me/messages/19ab3f/trash")


# -- triage and reply-all (gws's `+triage` / `+reply-all`) -------------------

def test_triage_lists_unread_inbox_mail(gmail):
    ft, run = gmail
    ft.add("GET", "messages?", {"messages": [{"id": "m1"}, {"id": "m2"}]})
    ft.add("GET", "messages/m1",
           meta("m1", {"From": "alice@x.com", "Subject": "Q1 roadmap",
                       "Date": "Mon, 5 Jan 2026 09:14:00 +0000"}))
    ft.add("GET", "messages/m2",
           meta("m2", {"From": "bob@x.com", "Subject": "Ping",
                       "Date": "Tue, 6 Jan 2026 09:14:00 +0000"}))
    out = run("gmail", "triage")
    assert "q=is%3Aunread+in%3Ainbox" in ft.calls[0]["url"]
    assert "FROM" in out and "SUBJECT" in out and "DATE" in out
    assert "alice@x.com" in out and "Q1 roadmap" in out
    assert "bob@x.com" in out and "Ping" in out
    # The id leads: triage exists to hand the next command something to act on.
    assert "m1" in out and "m2" in out


def test_triage_is_a_listing_that_honours_max_and_json(gmail):
    ft, run = gmail
    ft.add("GET", "messages?", {"messages": [{"id": "m1"}, {"id": "m2"}]})
    ft.add("GET", "messages/m1",
           meta("m1", {"From": "alice@x.com", "Subject": "Q1 roadmap",
                       "Date": "Mon, 5 Jan 2026 09:14:00 +0000"}))
    out = run("--json", "gmail", "triage", "--max", "1")
    # --max stops the walk: the second id is never fetched.
    assert [c["url"].rsplit("/", 1)[-1] for c in ft.calls[1:]] == [
        "m1?format=metadata&metadataHeaders=From&metadataHeaders=To"
        "&metadataHeaders=Cc&metadataHeaders=Reply-To"
        "&metadataHeaders=Subject&metadataHeaders=Date"
        "&metadataHeaders=Message-ID"]
    assert json.loads(out) == [{"id": "m1", "from": "alice@x.com",
                                "subject": "Q1 roadmap",
                                "date": "Mon, 5 Jan 2026 09:14:00 +0000",
                                "snippet": ""}]


def test_reply_all_answers_every_participant_except_me(gmail):
    ft, run = gmail
    ft.add("GET", "messages/m1", meta("m1", {
        "From": "Alice <alice@x.com>",
        "To": "a@x.com, Bob <bob@x.com>",
        "Cc": "carol@x.com, A@X.com",
        "Subject": "Q",
        "Message-ID": "<orig@x>",
    }))
    ft.add("POST", "messages/send", {"id": "sentall"})
    out = run("gmail", "reply-all", "m1", "--body", "answer")
    payload, mime = sent_mime(ft)
    assert payload["threadId"] == "t1"
    # Sender first, then the other To recipients; display names survive.
    assert mime["To"] == "Alice <alice@x.com>, Bob <bob@x.com>"
    # The acting account drops out of both lists, whatever its case.
    assert mime["Cc"] == "carol@x.com"
    assert mime["Subject"] == "Re: Q"
    assert mime["In-Reply-To"] == "<orig@x>"
    assert "answer" in mime.get_payload()
    assert "sentall" in out


def test_reply_all_does_not_send_anyone_two_copies(gmail):
    """The sender is usually on the To line too; they get one copy, not two."""
    ft, run = gmail
    ft.add("GET", "messages/m1", meta("m1", {"From": "alice@x.com",
                                             "To": "alice@x.com, bob@x.com",
                                             "Cc": "bob@x.com",
                                             "Subject": "Q"}))
    ft.add("POST", "messages/send", {"id": "sentd"})
    run("gmail", "reply-all", "m1", "--body", "answer")
    _, mime = sent_mime(ft)
    assert mime["To"] == "alice@x.com, bob@x.com"
    assert mime["Cc"] is None


def test_reply_all_prefers_reply_to_over_the_sender(gmail):
    ft, run = gmail
    ft.add("GET", "messages/m1", meta("m1", {"From": "alice@x.com",
                                             "Reply-To": "list@x.com",
                                             "To": "bob@x.com",
                                             "Subject": "Q"}))
    ft.add("POST", "messages/send", {"id": "sentr"})
    run("gmail", "reply-all", "m1", "--body", "answer")
    _, mime = sent_mime(ft)
    assert mime["To"] == "list@x.com, bob@x.com"


def test_reply_all_errors_when_every_participant_is_me(gmail):
    ft, run = gmail
    ft.add("GET", "messages/m1", meta("m1", {"From": "a@x.com",
                                             "To": "a@x.com",
                                             "Subject": "note to self"}))
    run("gmail", "reply-all", "m1", "--body", "answer", expect=1)
    assert [c["method"] for c in ft.calls] == ["GET"]  # nothing sent


@pytest.mark.parametrize("header", ["To", "Cc", "From"])
def test_reply_all_refuses_a_line_break_in_a_fetched_recipient_header(gmail,
                                                                      header):
    """Recipient headers come off received mail, so they are hostile input.

    `getaddresses` cannot be the guard: depending on the Python patch level
    it either hands the smuggled header back as one more address or drops
    every recipient silently, and neither is an answer a user can act on.
    """
    ft, run = gmail
    headers = {"From": "alice@x.com", "To": "bob@x.com", "Subject": "Q"}
    headers[header] = "victim@x.com\r\nBcc: evil@example.com"
    ft.add("GET", "messages/m1", meta("m1", headers))
    ft.add("POST", "messages/send", {"id": "nope"})
    run("gmail", "reply-all", "m1", "--body", "answer", expect=1)
    assert [c["method"] for c in ft.calls] == ["GET"]


def test_reply_requests_the_headers_it_reads(gmail):
    """Regression: `reply` preferred Reply-To but never asked Gmail for it.

    `format=metadata` returns *only* the headers named in metadataHeaders, so
    one left off that list reads as absent on every real message — which is
    how the Reply-To branch came to be dead code against the live API.
    """
    ft, run = gmail
    ft.add("GET", "messages/m1", meta("m1", {"From": "alice@x.com",
                                             "Reply-To": "list@x.com",
                                             "Subject": "Q"}))
    ft.add("POST", "messages/send", {"id": "sentrt"})
    run("gmail", "reply", "m1", "--body", "answer")
    url = ft.calls[0]["url"]
    assert "metadataHeaders=Reply-To" in url and "metadataHeaders=Cc" in url
    _, mime = sent_mime(ft)
    assert mime["To"] == "list@x.com"


# -- settings: send-as addresses (gog's `gmail settings sendas *`) -----------

SENDAS_ENTRIES = {"sendAs": [
    {"sendAsEmail": "a@x.com", "displayName": "Ada", "isPrimary": True,
     "isDefault": True, "signature": "primary sig"},
    {"sendAsEmail": "alias@x.com", "displayName": "Alias",
     "replyToAddress": "list@x.com", "signature": "<b>alias sig</b>",
     "verificationStatus": "pending", "treatAsAlias": True},
]}


def test_settings_sendas_list(gmail):
    ft, run = gmail
    ft.add("GET", "settings/sendAs", SENDAS_ENTRIES)
    out = run("gmail", "settings", "sendas", "list")
    assert ft.calls[0]["url"].endswith("/settings/sendAs")
    for header in ("EMAIL", "NAME", "PRIMARY", "DEFAULT", "VERIFIED"):
        assert header in out
    assert "a@x.com" in out and "Ada" in out and "yes" in out
    assert "alias@x.com" in out and "pending" in out


def test_settings_sendas_get(gmail):
    ft, run = gmail
    ft.add("GET", "settings/sendAs/alias%40x.com", SENDAS_ENTRIES["sendAs"][1])
    out = run("gmail", "settings", "sendas", "get", "alias@x.com")
    assert "settings/sendAs/alias%40x.com" in ft.calls[0]["url"]
    assert "email: alias@x.com" in out
    assert "name: Alias" in out
    assert "reply-to: list@x.com" in out
    assert "verified: pending" in out
    assert "signature: <b>alias sig</b>" in out


def test_settings_sendas_create(gmail):
    ft, run = gmail
    ft.add("POST", "settings/sendAs", {"sendAsEmail": "new@x.com",
                                       "verificationStatus": "pending"})
    out = run("gmail", "settings", "sendas", "create", "new@x.com",
              "--name", "New", "--reply-to", "list@x.com", "--treat-as-alias")
    assert ft.calls[-1]["method"] == "POST"
    assert json.loads(ft.calls[-1]["data"]) == {"sendAsEmail": "new@x.com",
                                                "displayName": "New",
                                                "replyToAddress": "list@x.com",
                                                "treatAsAlias": True}
    # Google mails a confirmation link, so the status is worth saying out loud.
    assert "created new@x.com pending" in out


def test_settings_sendas_create_sends_only_what_was_asked_for(gmail):
    ft, run = gmail
    ft.add("POST", "settings/sendAs", {"sendAsEmail": "new@x.com"})
    run("gmail", "settings", "sendas", "create", "new@x.com")
    assert json.loads(ft.calls[-1]["data"]) == {"sendAsEmail": "new@x.com"}


def test_settings_sendas_update_patches_only_the_named_fields(gmail):
    ft, run = gmail
    ft.add("PATCH", "settings/sendAs/alias%40x.com",
           {"sendAsEmail": "alias@x.com"})
    out = run("gmail", "settings", "sendas", "update", "alias@x.com",
              "--name", "Renamed", "--default")
    assert ft.calls[-1]["method"] == "PATCH"
    assert json.loads(ft.calls[-1]["data"]) == {"displayName": "Renamed",
                                                "isDefault": True}
    assert "updated alias@x.com" in out


def test_settings_sendas_update_can_clear_a_field(gmail):
    """An empty --name is a request to clear the display name, not a no-op."""
    ft, run = gmail
    ft.add("PATCH", "settings/sendAs/alias%40x.com",
           {"sendAsEmail": "alias@x.com"})
    run("gmail", "settings", "sendas", "update", "alias@x.com", "--name", "")
    assert json.loads(ft.calls[-1]["data"]) == {"displayName": ""}


def test_settings_sendas_update_requires_a_field(gmail):
    ft, run = gmail
    run("gmail", "settings", "sendas", "update", "alias@x.com", expect=1)
    assert ft.calls == []  # rejected before any HTTP


def test_settings_sendas_delete_and_verify(gmail):
    ft, run = gmail
    ft.add("DELETE", "settings/sendAs/alias%40x.com", {})
    out = run("gmail", "settings", "sendas", "delete", "alias@x.com")
    assert ft.calls[-1]["method"] == "DELETE"
    assert "deleted send-as alias@x.com" in out
    ft.add("POST", "settings/sendAs/alias%40x.com/verify", {})
    out = run("gmail", "settings", "sendas", "verify", "alias@x.com")
    assert ft.calls[-1]["url"].endswith("/sendAs/alias%40x.com/verify")
    assert "verification email sent to alias@x.com" in out


def test_settings_sendas_addresses_cannot_escape_their_url_segment(gmail):
    """An address is one opaque segment, even when it is not an address."""
    ft, run = gmail
    ft.add("DELETE", "settings/sendAs/", {})
    run("gmail", "settings", "sendas", "delete", "../../../v1/other")
    url = ft.calls[0]["url"]
    assert "/sendAs/../" not in url and "%2F" in url


def test_settings_sendas_does_not_take_over_signature_editing(gmail):
    """`gmail signature set` owns signatures; sendas neither duplicates it…

    Two commands writing the same field is how they drift apart, so the
    overlap is refused at the parser rather than resolved at runtime.
    """
    ft, run = gmail
    with pytest.raises(SystemExit):  # argparse: unrecognized argument
        run("gmail", "settings", "sendas", "update", "alias@x.com",
            "--signature", "<b>x</b>")
    assert ft.calls == []
    # …nor hides them: `get` still shows what the signature is.
    ft.add("GET", "settings/sendAs/alias%40x.com", SENDAS_ENTRIES["sendAs"][1])
    assert "<b>alias sig</b>" in run("gmail", "settings", "sendas", "get",
                                     "alias@x.com")


# -- settings: delegates (gog's `gmail settings delegates *`) ----------------

def test_settings_delegates_list(gmail):
    ft, run = gmail
    ft.add("GET", "settings/delegates", {"delegates": [
        {"delegateEmail": "assistant@x.com", "verificationStatus": "accepted"},
        {"delegateEmail": "temp@x.com", "verificationStatus": "pending"},
    ]})
    out = run("gmail", "settings", "delegates", "list")
    assert ft.calls[0]["url"].endswith("/settings/delegates")
    assert "EMAIL" in out and "STATUS" in out
    assert "assistant@x.com" in out and "accepted" in out
    assert "temp@x.com" in out and "pending" in out


def test_settings_delegates_get(gmail):
    ft, run = gmail
    ft.add("GET", "settings/delegates/assistant%40x.com",
           {"delegateEmail": "assistant@x.com",
            "verificationStatus": "accepted"})
    out = run("gmail", "settings", "delegates", "get", "assistant@x.com")
    assert "settings/delegates/assistant%40x.com" in ft.calls[0]["url"]
    assert "email: assistant@x.com" in out
    assert "status: accepted" in out


def test_settings_delegates_add_and_remove(gmail):
    ft, run = gmail
    ft.add("POST", "settings/delegates",
           {"delegateEmail": "assistant@x.com",
            "verificationStatus": "pending"})
    out = run("gmail", "settings", "delegates", "add", "assistant@x.com")
    assert json.loads(ft.calls[-1]["data"]) == {
        "delegateEmail": "assistant@x.com"}
    assert "added delegate assistant@x.com pending" in out
    ft.add("DELETE", "settings/delegates/assistant%40x.com", {})
    out = run("gmail", "settings", "delegates", "remove", "assistant@x.com")
    assert ft.calls[-1]["method"] == "DELETE"
    assert "removed delegate assistant@x.com" in out


# -- settings: forwarding addresses and auto-forwarding ----------------------

def test_settings_forwarding_list_and_get(gmail):
    ft, run = gmail
    ft.add("GET", "settings/forwardingAddresses", {"forwardingAddresses": [
        {"forwardingEmail": "ops@x.com", "verificationStatus": "accepted"},
    ]})
    out = run("gmail", "settings", "forwarding", "list")
    assert ft.calls[0]["url"].endswith("/settings/forwardingAddresses")
    assert "EMAIL" in out and "STATUS" in out
    assert "ops@x.com" in out and "accepted" in out
    ft.add("GET", "settings/forwardingAddresses/ops%40x.com",
           {"forwardingEmail": "ops@x.com", "verificationStatus": "accepted"})
    out = run("gmail", "settings", "forwarding", "get", "ops@x.com")
    assert "email: ops@x.com" in out and "status: accepted" in out


def test_settings_forwarding_create_and_delete(gmail):
    ft, run = gmail
    ft.add("POST", "settings/forwardingAddresses",
           {"forwardingEmail": "ops@x.com", "verificationStatus": "pending"})
    out = run("gmail", "settings", "forwarding", "create", "ops@x.com")
    assert json.loads(ft.calls[-1]["data"]) == {"forwardingEmail": "ops@x.com"}
    assert "created ops@x.com pending" in out
    ft.add("DELETE", "settings/forwardingAddresses/ops%40x.com", {})
    out = run("gmail", "settings", "forwarding", "delete", "ops@x.com")
    assert ft.calls[-1]["method"] == "DELETE"
    assert "deleted forwarding address ops@x.com" in out


def test_settings_autoforward_get(gmail):
    ft, run = gmail
    ft.add("GET", "settings/autoForwarding", {"enabled": True,
                                              "emailAddress": "ops@x.com",
                                              "disposition": "archive"})
    out = run("gmail", "settings", "autoforward", "get")
    assert ft.calls[0]["url"].endswith("/settings/autoForwarding")
    assert "enabled: True" in out
    assert "to: ops@x.com" in out
    assert "disposition: archive" in out


def test_settings_autoforward_update_turns_it_on(gmail):
    ft, run = gmail
    ft.add("PUT", "settings/autoForwarding", {"enabled": True})
    out = run("gmail", "settings", "autoforward", "update",
              "--to", "ops@x.com", "--disposition", "archive")
    assert ft.calls[-1]["method"] == "PUT"
    assert json.loads(ft.calls[-1]["data"]) == {"enabled": True,
                                                "emailAddress": "ops@x.com",
                                                "disposition": "archive"}
    assert "auto-forwarding to ops@x.com (archive)" in out


def test_settings_autoforward_update_keeps_a_copy_by_default(gmail):
    """The safe disposition is the default: forwarding never loses the mail."""
    ft, run = gmail
    ft.add("PUT", "settings/autoForwarding", {"enabled": True})
    run("gmail", "settings", "autoforward", "update", "--to", "ops@x.com")
    assert json.loads(ft.calls[-1]["data"])["disposition"] == "leaveInInbox"


def test_settings_autoforward_update_turns_it_off(gmail):
    ft, run = gmail
    ft.add("PUT", "settings/autoForwarding", {"enabled": False})
    out = run("gmail", "settings", "autoforward", "update", "--off")
    assert json.loads(ft.calls[-1]["data"]) == {"enabled": False}
    assert "auto-forwarding disabled" in out


def test_settings_autoforward_update_needs_to_know_which_way(gmail):
    """Neither flag is a no-op, and both together contradict each other."""
    ft, run = gmail
    run("gmail", "settings", "autoforward", "update", expect=1)
    run("gmail", "settings", "autoforward", "update", "--off",
        "--to", "ops@x.com", expect=1)
    assert ft.calls == []  # both rejected before any HTTP


@pytest.mark.parametrize("group, command, method, route", [
    ("delegates", "remove", "DELETE", "settings/delegates/"),
    ("forwarding", "delete", "DELETE", "settings/forwardingAddresses/"),
])
def test_settings_addresses_cannot_escape_their_url_segment(gmail, group,
                                                            command, method,
                                                            route):
    ft, run = gmail
    ft.add(method, route, {})
    run("gmail", "settings", group, command, "../../../v1/other")
    url = ft.calls[0]["url"]
    assert "/../" not in url and "%2F" in url
