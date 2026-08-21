import json
from urllib.parse import parse_qs, urlsplit

import pytest


@pytest.fixture
def drive(authed, fake_transport, run_cli):
    return fake_transport, run_cli


FILE_ROW = {"id": "f1", "name": "notes.txt", "mimeType": "text/plain",
            "modifiedTime": "2026-01-05T00:00:00Z", "size": "12"}


def test_ls_lists_root_children(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": [FILE_ROW]})
    out = run("drive", "ls")
    assert "notes.txt" in out
    assert "%27root%27+in+parents" in ft.calls[0]["url"]


def test_ls_folder_arg(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": []})
    run("drive", "ls", "folder123")
    assert "%27folder123%27+in+parents" in ft.calls[0]["url"]


def test_search_by_name(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": [FILE_ROW]})
    out = run("drive", "search", "notes")
    assert "notes.txt" in out
    assert "name+contains" in ft.calls[0]["url"]


def test_mkdir(drive):
    ft, run = drive
    ft.add("POST", "drive/v3/files", {"id": "d1", "name": "new"})
    run("drive", "mkdir", "new")
    body = json.loads(ft.calls[0]["data"])
    assert body["mimeType"] == "application/vnd.google-apps.folder"
    assert body["name"] == "new"


def test_upload_multipart(drive, tmp_path):
    ft, run = drive
    src = tmp_path / "hello.txt"
    src.write_text("file-content-here")
    ft.add("POST", "upload/drive/v3/files?uploadType=multipart", {"id": "u1"})
    out = run("drive", "upload", str(src), "--parent", "folder123")
    call = ft.calls[0]
    assert call["headers"]["Content-Type"].startswith("multipart/related")
    assert b"file-content-here" in call["data"]
    assert b'"hello.txt"' in call["data"]
    assert b"folder123" in call["data"]
    assert "u1" in out


def test_download_writes_file(drive, tmp_path):
    ft, run = drive
    ft.add("GET", "files/f1?alt=media", b"binary-bytes")
    dest = tmp_path / "out.bin"
    run("drive", "download", "f1", "-o", str(dest))
    assert dest.read_bytes() == b"binary-bytes"


def test_export_google_doc(drive, tmp_path):
    ft, run = drive
    ft.add("GET", "files/f1/export?mimeType=application%2Fpdf", b"%PDF-fake")
    dest = tmp_path / "doc.pdf"
    run("drive", "export", "f1", "--mime", "application/pdf", "-o", str(dest))
    assert dest.read_bytes() == b"%PDF-fake"


def test_share_grants_role(drive):
    ft, run = drive
    ft.add("POST", "files/f1/permissions", {"id": "p1"})
    run("drive", "share", "f1", "--with", "bob@x.com", "--role", "writer")
    body = json.loads(ft.calls[0]["data"])
    assert body == {"type": "user", "role": "writer", "emailAddress": "bob@x.com"}


def test_permissions_list(drive):
    ft, run = drive
    ft.add("GET", "files/f1/permissions", {"permissions": [
        {"id": "p1", "type": "user", "role": "owner",
         "emailAddress": "me@x.com"}]})
    assert "me@x.com" in run("drive", "permissions", "f1")


def test_rm_and_copy(drive):
    ft, run = drive
    ft.add("DELETE", "files/f1", {})
    run("drive", "rm", "f1")
    ft.add("POST", "files/f1/copy", {"id": "f2", "name": "copy"})
    run("drive", "copy", "f1", "--name", "copy")
    assert json.loads(ft.calls[-1]["data"]) == {"name": "copy"}


def test_audit_finds_link_shared_files(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": [dict(FILE_ROW,
                                                    webViewLink="http://l")]})
    out = run("drive", "audit")
    assert "notes.txt" in out
    assert "visibility" in ft.calls[0]["url"]


INFO_BODY = {"id": "f1", "name": "notes.txt", "mimeType": "text/plain",
             "size": "12", "modifiedTime": "2026-01-05T00:00:00Z",
             "parents": ["p1", "p2"], "webViewLink": "http://link",
             "owners": [{"emailAddress": "me@x.com"}], "trashed": False}


def test_info_shows_metadata(drive):
    ft, run = drive
    ft.add("GET", "files/f1?fields=", INFO_BODY)
    out = run("drive", "info", "f1")
    assert "owners%28emailAddress%29" in ft.calls[0]["url"]
    assert "name: notes.txt" in out
    assert "type: text/plain" in out
    assert "parents: p1,p2" in out
    assert "owner: me@x.com" in out
    assert "link: http://link" in out
    assert "trashed: False" in out


def test_mv_to_new_parent(drive):
    ft, run = drive
    ft.add("GET", "files/f1?fields=parents", {"parents": ["old1", "old2"]})
    ft.add("PATCH", "files/f1", {"id": "f1"})
    out = run("drive", "mv", "f1", "--parent", "newp")
    patch = ft.calls[1]
    assert patch["method"] == "PATCH"
    assert "addParents=newp" in patch["url"]
    assert "removeParents=old1%2Cold2" in patch["url"]
    assert "moved f1" in out


def test_mv_rename_only(drive):
    ft, run = drive
    ft.add("PATCH", "files/f1", {"id": "f1"})
    out = run("drive", "mv", "f1", "--name", "renamed.txt")
    assert len(ft.calls) == 1  # no parents lookup when only renaming
    assert json.loads(ft.calls[0]["data"]) == {"name": "renamed.txt"}
    assert "addParents" not in ft.calls[0]["url"]
    assert "renamed f1" in out


def test_mv_requires_parent_or_name(drive):
    ft, run = drive
    run("drive", "mv", "f1", expect=1)
    assert ft.calls == []


def test_trash_and_restore(drive):
    ft, run = drive
    ft.add("PATCH", "files/f1", {"id": "f1"})
    out = run("drive", "trash", "f1")
    assert json.loads(ft.calls[0]["data"]) == {"trashed": True}
    assert "trashed f1" in out
    ft.add("PATCH", "files/f1", {"id": "f1"})
    out = run("drive", "restore", "f1")
    assert json.loads(ft.calls[-1]["data"]) == {"trashed": False}
    assert "restored f1" in out


# -- shared drives ---------------------------------------------------------

DRIVE_ROW = {"id": "d1", "name": "Team Drive",
             "createdTime": "2026-02-01T00:00:00Z"}


def test_drives_lists_shared_drives(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/drives", {"drives": [DRIVE_ROW]})
    out = run("drive", "drives")
    assert "d1" in out
    assert "Team Drive" in out
    assert "2026-02-01T00:00:00Z" in out
    assert "CREATED" in out
    assert "pageSize=100" in ft.calls[0]["url"]


def test_ls_sends_shared_drive_params(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": [FILE_ROW]})
    run("drive", "ls")
    url = ft.calls[0]["url"]
    assert "supportsAllDrives=true" in url
    assert "includeItemsFromAllDrives=true" in url
    # existing behavior must survive
    assert "%27root%27+in+parents" in url
    assert "fields=files" in url
    assert "corpora" not in url


def test_ls_drive_flag_scopes_to_one_shared_drive(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": []})
    run("drive", "ls", "--drive", "D1")
    url = ft.calls[0]["url"]
    assert "corpora=drive" in url
    assert "driveId=D1" in url
    assert "supportsAllDrives=true" in url
    assert "includeItemsFromAllDrives=true" in url


def test_search_drive_flag_scopes_to_one_shared_drive(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": [FILE_ROW]})
    run("drive", "search", "notes", "--drive", "D2")
    url = ft.calls[0]["url"]
    assert "corpora=drive" in url
    assert "driveId=D2" in url
    assert "name+contains" in url


def test_audit_sees_all_drives(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": []})
    run("drive", "audit")
    url = ft.calls[0]["url"]
    assert "supportsAllDrives=true" in url
    assert "includeItemsFromAllDrives=true" in url


def test_mutations_support_all_drives(drive):
    ft, run = drive
    ft.add("PATCH", "files/f1", {"id": "f1"})
    run("drive", "trash", "f1")
    assert "supportsAllDrives=true" in ft.calls[0]["url"]
    assert json.loads(ft.calls[0]["data"]) == {"trashed": True}
    ft.add("GET", "files/f1?fields=parents", {"parents": ["old1"]})
    ft.add("PATCH", "files/f1", {"id": "f1"})
    run("drive", "mv", "f1", "--parent", "newp")
    patch = ft.calls[-1]
    assert "supportsAllDrives=true" in patch["url"]
    assert "addParents=newp" in patch["url"]
    assert "removeParents=old1" in patch["url"]
    ft.add("DELETE", "files/f1", {})
    run("drive", "rm", "f1")
    assert "supportsAllDrives=true" in ft.calls[-1]["url"]


def test_download_and_export_keep_params_and_support_all_drives(drive, tmp_path):
    ft, run = drive
    ft.add("GET", "files/f1?alt=media", b"binary-bytes")
    dest = tmp_path / "out.bin"
    run("drive", "download", "f1", "-o", str(dest))
    url = ft.calls[0]["url"]
    assert "alt=media" in url
    assert "supportsAllDrives=true" in url
    assert dest.read_bytes() == b"binary-bytes"
    ft.add("GET", "files/f1/export", b"%PDF-fake")
    doc = tmp_path / "doc.pdf"
    run("drive", "export", "f1", "--mime", "application/pdf", "-o", str(doc))
    url = ft.calls[-1]["url"]
    assert "mimeType=application%2Fpdf" in url
    assert "supportsAllDrives=true" in url
    assert doc.read_bytes() == b"%PDF-fake"


# -- query-string safety ---------------------------------------------------
#
# Inside a Drive `q` string literal both `\` and `'` must be escaped, backslash
# first. A value that escapes neither can close the literal early and change
# what the query means, so these tests pin the wire format down: pull `q` back
# out of the request URL and assert on the query the API would actually see.


def _q(call) -> str:
    """The decoded Drive `q` parameter of a recorded request."""
    return parse_qs(urlsplit(call["url"]).query)["q"][0]


def test_ls_escapes_quote_in_folder_id(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": []})
    run("drive", "ls", "fol'der")
    q = _q(ft.calls[0])
    assert q == r"'fol\'der' in parents and trashed = false"
    # the quote is escaped, so it cannot terminate the literal early and the
    # trailing clauses stay outside of it
    assert r"\'" in q
    assert q.endswith("in parents and trashed = false")


def test_search_escapes_quote_in_term(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": []})
    run("drive", "search", "it's")
    assert _q(ft.calls[0]) == r"name contains 'it\'s' and trashed = false"


def test_search_trailing_backslash_does_not_escape_closing_quote(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": []})
    run("drive", "search", "back\\")
    q = _q(ft.calls[0])
    # the backslash is doubled, so the closing quote stays a closing quote
    assert q == r"name contains 'back\\' and trashed = false"
    assert q.endswith("and trashed = false")


def test_search_escapes_backslash_before_quote(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": []})
    run("drive", "search", "it's\\")
    assert _q(ft.calls[0]) == r"name contains 'it\'s\\' and trashed = false"


def test_search_plain_term_query_is_unchanged(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": []})
    run("drive", "search", "notes")
    assert _q(ft.calls[0]) == "name contains 'notes' and trashed = false"


def test_search_raw_query_passes_through_unescaped(drive):
    ft, run = drive
    ft.add("GET", "drive/v3/files", {"files": []})
    raw = r"name contains 'it\'s' and mimeType = 'text/plain'"
    run("drive", "search", raw)
    # a deliberate raw Drive query is forwarded verbatim, never re-escaped
    assert _q(ft.calls[0]) == raw


# -- comments --------------------------------------------------------------
#
# Drive's comments collection is the one part of the API that refuses a
# request carrying no `fields`: every method answers "The 'fields' parameter
# is required for this method" and returns no comment at all. So the
# parameter is pinned onto the wire here rather than left to review — a
# refactor that drops it breaks every comment command at once, and only
# against the real API, where no unit test would be watching.

COMMENT = {"id": "c1", "content": "looks good",
           "author": {"displayName": "Ada"},
           "createdTime": "2026-03-01T00:00:00Z",
           "modifiedTime": "2026-03-01T00:00:00Z",
           "resolved": False,
           "quotedFileContent": {"value": "the third paragraph"},
           "replies": [{"id": "r1", "content": "thanks",
                        "author": {"displayName": "Bob"},
                        "createdTime": "2026-03-02T00:00:00Z"}]}


def test_comments_list_shows_author_and_content(drive):
    ft, run = drive
    ft.add("GET", "files/f1/comments", {"comments": [COMMENT]})
    out = run("drive", "comments", "list", "f1")
    assert "c1" in out
    assert "Ada" in out
    assert "looks good" in out
    assert "2026-03-01T00:00:00Z" in out
    url = ft.calls[0]["url"]
    assert "/files/f1/comments?" in url
    assert "fields=comments" in url


def test_comments_list_counts_replies(drive):
    ft, run = drive
    ft.add("GET", "files/f1/comments", {"comments": [COMMENT]})
    out = run("--fields", "id,replies", "drive", "comments", "list", "f1")
    assert "REPLIES" in out
    assert out.splitlines()[-1].split() == ["c1", "1"]


def test_comments_list_include_deleted_is_opt_in(drive):
    ft, run = drive
    ft.add("GET", "files/f1/comments", {"comments": []})
    run("drive", "comments", "list", "f1")
    assert "includeDeleted" not in ft.calls[0]["url"]
    ft.add("GET", "files/f1/comments", {"comments": []})
    run("drive", "comments", "list", "f1", "--include-deleted")
    assert "includeDeleted=true" in ft.calls[-1]["url"]


def test_comments_get_shows_one_comment(drive):
    ft, run = drive
    ft.add("GET", "files/f1/comments/c1", COMMENT)
    out = run("drive", "comments", "get", "f1", "c1")
    assert "id: c1" in out
    assert "author: Ada" in out
    assert "content: looks good" in out
    assert "quoted: the third paragraph" in out
    assert "replies: 1" in out
    assert "fields=" in ft.calls[0]["url"]


def test_comments_create_posts_content(drive):
    ft, run = drive
    ft.add("POST", "files/f1/comments", {"id": "c9"})
    out = run("drive", "comments", "create", "f1", "--content", "please fix")
    assert json.loads(ft.calls[0]["data"]) == {"content": "please fix"}
    assert "fields=" in ft.calls[0]["url"]
    assert "c9" in out


def test_comments_create_can_quote_the_text_it_is_about(drive):
    ft, run = drive
    ft.add("POST", "files/f1/comments", {"id": "c9"})
    run("drive", "comments", "create", "f1", "--content", "typo",
        "--quote", "teh")
    assert json.loads(ft.calls[0]["data"]) == {
        "content": "typo", "quotedFileContent": {"value": "teh"}}


def test_comments_update_patches_content(drive):
    ft, run = drive
    ft.add("PATCH", "files/f1/comments/c1", {"id": "c1"})
    out = run("drive", "comments", "update", "f1", "c1",
              "--content", "revised")
    assert ft.calls[0]["method"] == "PATCH"
    assert json.loads(ft.calls[0]["data"]) == {"content": "revised"}
    assert "fields=" in ft.calls[0]["url"]
    assert "updated comment c1" in out


def test_comments_delete(drive):
    ft, run = drive
    ft.add("DELETE", "files/f1/comments/c1", {})
    out = run("drive", "comments", "delete", "f1", "c1")
    assert ft.calls[0]["method"] == "DELETE"
    assert "/files/f1/comments/c1" in ft.calls[0]["url"]
    assert "deleted comment c1" in out


def test_every_comments_method_asks_for_fields(drive):
    """Without `fields` the API answers with an error, never a comment."""
    ft, run = drive
    ft.add("GET", "files/f1/comments", {"comments": []})
    ft.add("GET", "files/f1/comments/c1", COMMENT)
    ft.add("POST", "files/f1/comments", {"id": "c9"})
    ft.add("PATCH", "files/f1/comments/c1", {"id": "c1"})
    run("drive", "comments", "list", "f1")
    run("drive", "comments", "get", "f1", "c1")
    run("drive", "comments", "create", "f1", "--content", "x")
    run("drive", "comments", "update", "f1", "c1", "--content", "y")
    for call in ft.calls:
        assert "fields=" in call["url"], call["url"]


def test_comments_escape_both_ids_into_one_path_segment_each(drive):
    ft, run = drive
    ft.add("GET", "files/f%201/comments/..%2F..%2Fdrives", COMMENT)
    run("drive", "comments", "get", "f 1", "../../drives")
    url = ft.calls[0]["url"]
    assert "/files/f%201/comments/..%2F..%2Fdrives?" in url
    assert "../../drives" not in url


def test_comments_do_not_send_shared_drive_params(drive):
    """`supportsAllDrives` is not a parameter of the comments collection.

    Drive rejects query parameters a method does not declare, so copying the
    files-collection idiom over here would turn every comment command into a
    400 — the opposite of the compatibility it looks like it is buying.
    """
    ft, run = drive
    ft.add("GET", "files/f1/comments", {"comments": []})
    run("drive", "comments", "list", "f1")
    assert "supportsAllDrives" not in ft.calls[0]["url"]


# -- replies ---------------------------------------------------------------
#
# Drive has no "resolve a comment" endpoint. Resolving and reopening are
# replies that carry an `action`, posted to the same replies collection as an
# ordinary reply — so all three commands below are one request shape with a
# different body, and these tests pin which body each one sends.

REPLY = {"id": "r9", "content": "done", "action": "resolve",
         "author": {"displayName": "Ada"},
         "createdTime": "2026-03-03T00:00:00Z"}


def test_comments_reply_posts_to_the_replies_collection(drive):
    ft, run = drive
    ft.add("POST", "files/f1/comments/c1/replies", REPLY)
    out = run("drive", "comments", "reply", "f1", "c1", "--content", "on it")
    call = ft.calls[0]
    assert call["method"] == "POST"
    assert "/files/f1/comments/c1/replies?" in call["url"]
    assert json.loads(call["data"]) == {"content": "on it"}
    assert "fields=" in call["url"]
    assert "replied r9" in out


def test_comments_resolve_sends_the_resolve_action(drive):
    ft, run = drive
    ft.add("POST", "files/f1/comments/c1/replies", REPLY)
    out = run("drive", "comments", "resolve", "f1", "c1")
    assert json.loads(ft.calls[0]["data"]) == {"action": "resolve"}
    assert "/files/f1/comments/c1/replies?" in ft.calls[0]["url"]
    assert "resolved c1" in out


def test_comments_reopen_sends_the_reopen_action(drive):
    ft, run = drive
    ft.add("POST", "files/f1/comments/c1/replies", REPLY)
    out = run("drive", "comments", "reopen", "f1", "c1")
    assert json.loads(ft.calls[0]["data"]) == {"action": "reopen"}
    assert "reopened c1" in out


def test_comments_resolve_can_carry_a_note(drive):
    """`content` is optional on an action reply, and omitted when unset.

    Sending `content: ""` alongside the action would post an empty reply into
    the thread, which is visible to everyone who reads the file.
    """
    ft, run = drive
    ft.add("POST", "files/f1/comments/c1/replies", REPLY)
    run("drive", "comments", "resolve", "f1", "c1", "--content", "fixed in v2")
    assert json.loads(ft.calls[0]["data"]) == {
        "action": "resolve", "content": "fixed in v2"}


def test_reply_actions_ask_for_fields_too(drive):
    ft, run = drive
    ft.add("POST", "files/f1/comments/c1/replies", REPLY)
    ft.add("POST", "files/f1/comments/c1/replies", REPLY)
    run("drive", "comments", "resolve", "f1", "c1")
    run("drive", "comments", "reopen", "f1", "c1")
    for call in ft.calls:
        assert "fields=" in call["url"], call["url"]


def test_replies_escape_both_ids(drive):
    ft, run = drive
    ft.add("POST", "files/f%201/comments/c%2F1/replies", REPLY)
    run("drive", "comments", "reply", "f 1", "c/1", "--content", "x")
    url = ft.calls[0]["url"]
    assert "/files/f%201/comments/c%2F1/replies?" in url
    assert "c/1/replies" not in url


# -- revisions -------------------------------------------------------------

REVISION = {"id": "rev1", "modifiedTime": "2026-04-01T00:00:00Z",
            "size": "2048", "keepForever": False, "mimeType": "text/plain",
            "originalFilename": "notes.txt",
            "lastModifyingUser": {"displayName": "Ada"}}


def test_revisions_list_shows_the_history(drive):
    ft, run = drive
    ft.add("GET", "files/f1/revisions", {"revisions": [REVISION]})
    out = run("drive", "revisions", "list", "f1")
    assert "rev1" in out
    assert "2026-04-01T00:00:00Z" in out
    assert "2048" in out
    assert "Ada" in out
    url = ft.calls[0]["url"]
    assert "/files/f1/revisions?" in url
    assert "fields=revisions" in url


def test_revisions_get_shows_one_revision(drive):
    ft, run = drive
    ft.add("GET", "files/f1/revisions/rev1", REVISION)
    out = run("drive", "revisions", "get", "f1", "rev1")
    assert "id: rev1" in out
    assert "modified: 2026-04-01T00:00:00Z" in out
    assert "size: 2048" in out
    assert "author: Ada" in out
    assert "keepForever: False" in out
    assert "/files/f1/revisions/rev1?" in ft.calls[0]["url"]


def test_revisions_do_not_send_shared_drive_params(drive):
    """`supportsAllDrives` is not a parameter of the revisions collection.

    Same trap as the comments collection: Drive rejects a parameter a method
    does not declare, so borrowing the files-collection idiom here would make
    every revision command a 400.
    """
    ft, run = drive
    ft.add("GET", "files/f1/revisions", {"revisions": []})
    ft.add("GET", "files/f1/revisions/rev1", REVISION)
    run("drive", "revisions", "list", "f1")
    run("drive", "revisions", "get", "f1", "rev1")
    for call in ft.calls:
        assert "supportsAllDrives" not in call["url"], call["url"]


def test_revisions_escape_both_ids(drive):
    ft, run = drive
    ft.add("GET", "files/f%201/revisions/..%2F..%2Fdrives", REVISION)
    run("drive", "revisions", "get", "f 1", "../../drives")
    url = ft.calls[0]["url"]
    assert "/files/f%201/revisions/..%2F..%2Fdrives?" in url
    assert "../../drives" not in url


# -- rename ----------------------------------------------------------------


def test_rename_patches_only_the_name(drive):
    ft, run = drive
    ft.add("PATCH", "files/f1", {"id": "f1", "name": "final.txt"})
    out = run("drive", "rename", "f1", "final.txt")
    call = ft.calls[0]
    assert call["method"] == "PATCH"
    assert json.loads(call["data"]) == {"name": "final.txt"}
    # renaming must never move the file, however `mv` chooses to do it
    assert "addParents" not in call["url"]
    assert "removeParents" not in call["url"]
    assert len(ft.calls) == 1  # and needs no parents lookup to do it
    assert "renamed f1 to final.txt" in out


def test_rename_supports_shared_drives(drive):
    ft, run = drive
    ft.add("PATCH", "files/f1", {"id": "f1"})
    run("drive", "rename", "f1", "final.txt")
    assert "supportsAllDrives=true" in ft.calls[0]["url"]


def test_rename_escapes_the_file_id(drive):
    ft, run = drive
    ft.add("PATCH", "files/..%2F..%2Fdrives", {"id": "x"})
    run("drive", "rename", "../../drives", "n")
    url = ft.calls[0]["url"]
    assert "/files/..%2F..%2Fdrives?" in url
    assert "../../drives" not in url


# -- url (offline) ---------------------------------------------------------
#
# The one Drive command that never talks to Google: a file's web URL is a
# function of its id, so asking the API for it would spend a round trip — and
# an access token — on something already known. `ft.calls == []` is the
# assertion that keeps it that way.


def test_url_is_built_offline_from_the_id(drive):
    ft, run = drive
    out = run("drive", "url", "f1")
    assert "https://drive.google.com/open?id=f1" in out
    assert ft.calls == [], "building a URL must not call the API"


def test_url_accepts_several_ids(drive):
    ft, run = drive
    out = run("drive", "url", "f1", "f2")
    assert "id=f1" in out
    assert "id=f2" in out
    assert ft.calls == []


def test_url_escapes_an_id_so_it_cannot_add_query_parameters(drive):
    ft, run = drive
    out = run("--fields", "url", "drive", "url", "a&role=owner")
    # `&` encoded, so the id stays one parameter instead of smuggling a second
    assert out.splitlines()[-1].strip() == (
        "https://drive.google.com/open?id=a%26role%3Downer")
    assert ft.calls == []


def test_url_rejects_a_blank_id(drive):
    ft, run = drive
    run("drive", "url", "", expect=1)
    assert ft.calls == []


# -- unshare ---------------------------------------------------------------


def test_unshare_deletes_a_named_permission(drive):
    ft, run = drive
    ft.add("DELETE", "files/f1/permissions/p1", {})
    out = run("drive", "unshare", "f1", "--permission", "p1")
    assert ft.calls[0]["method"] == "DELETE"
    assert "/files/f1/permissions/p1?" in ft.calls[0]["url"]
    assert "supportsAllDrives=true" in ft.calls[0]["url"]
    assert len(ft.calls) == 1  # a known permission id needs no lookup
    assert "unshared f1" in out


def test_unshare_looks_up_the_permission_for_an_email(drive):
    """`share --with` names a person, so `unshare --with` has to as well.

    Drive deletes permissions by their own opaque id, which nobody has to
    hand; the lookup is what makes the two commands inverses of each other.
    """
    ft, run = drive
    ft.add("GET", "files/f1/permissions", {"permissions": [
        {"id": "p1", "type": "user", "emailAddress": "me@x.com"},
        {"id": "p2", "type": "user", "emailAddress": "bob@x.com"}]})
    ft.add("DELETE", "files/f1/permissions/p2", {})
    out = run("drive", "unshare", "f1", "--with", "BOB@x.com")
    assert ft.calls[1]["method"] == "DELETE"
    assert "/files/f1/permissions/p2?" in ft.calls[1]["url"]
    assert "unshared f1 from BOB@x.com" in out


def test_unshare_anyone_removes_the_link_grant(drive):
    ft, run = drive
    ft.add("GET", "files/f1/permissions", {"permissions": [
        {"id": "p1", "type": "user", "emailAddress": "me@x.com"},
        {"id": "anyoneWithLink", "type": "anyone"}]})
    ft.add("DELETE", "files/f1/permissions/anyoneWithLink", {})
    run("drive", "unshare", "f1", "--with", "anyone")
    assert "/files/f1/permissions/anyoneWithLink?" in ft.calls[1]["url"]


def test_unshare_reports_a_grantee_who_has_no_permission(drive):
    ft, run = drive
    ft.add("GET", "files/f1/permissions", {"permissions": [
        {"id": "p1", "type": "user", "emailAddress": "me@x.com"}]})
    run("drive", "unshare", "f1", "--with", "nobody@x.com", expect=1)
    assert len(ft.calls) == 1, "nothing may be deleted when nothing matched"


def test_unshare_wants_exactly_one_way_to_name_the_permission(drive):
    ft, run = drive
    run("drive", "unshare", "f1", expect=1)
    run("drive", "unshare", "f1", "--with", "b@x.com", "--permission", "p1",
        expect=1)
    assert ft.calls == []


def test_unshare_escapes_both_ids(drive):
    ft, run = drive
    ft.add("DELETE", "files/f%201/permissions/..%2F..%2Fdrives", {})
    run("drive", "unshare", "f 1", "--permission", "../../drives")
    url = ft.calls[0]["url"]
    assert "/files/f%201/permissions/..%2F..%2Fdrives?" in url
    assert "../../drives" not in url


# -- shortcut --------------------------------------------------------------

SHORTCUT_MIME = "application/vnd.google-apps.shortcut"


def test_shortcut_points_at_the_target(drive):
    ft, run = drive
    ft.add("POST", "drive/v3/files", {"id": "s1", "name": "link"})
    out = run("drive", "shortcut", "f1", "--name", "link")
    body = json.loads(ft.calls[0]["data"])
    assert body == {"name": "link", "mimeType": SHORTCUT_MIME,
                    "shortcutDetails": {"targetId": "f1"}}
    assert "supportsAllDrives=true" in ft.calls[0]["url"]
    assert "created shortcut s1 to f1" in out


def test_shortcut_defaults_its_name_to_the_targets(drive):
    """An unnamed shortcut shows up as "Untitled", which nobody wants."""
    ft, run = drive
    ft.add("GET", "files/f1?fields=name", {"name": "notes.txt"})
    ft.add("POST", "drive/v3/files", {"id": "s1"})
    run("drive", "shortcut", "f1")
    assert json.loads(ft.calls[1]["data"])["name"] == "notes.txt"


def test_shortcut_can_be_placed_in_a_folder(drive):
    ft, run = drive
    ft.add("POST", "drive/v3/files", {"id": "s1"})
    run("drive", "shortcut", "f1", "--name", "link", "--parent", "folder123")
    assert json.loads(ft.calls[0]["data"])["parents"] == ["folder123"]


def test_shortcut_escapes_the_target_id_on_the_lookup(drive):
    ft, run = drive
    ft.add("GET", "files/..%2F..%2Fdrives", {"name": "n"})
    ft.add("POST", "drive/v3/files", {"id": "s1"})
    run("drive", "shortcut", "../../drives")
    assert "/files/..%2F..%2Fdrives?" in ft.calls[0]["url"]
