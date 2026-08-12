import json

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
