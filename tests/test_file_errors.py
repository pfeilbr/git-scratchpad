"""A bad path the user typed is an error message, not a traceback.

Four places take a filesystem path from the command line — `gmail send
--attach`, `gmail attachments -o`, `drive upload`, and `drive download`/
`export -o`. Each opened the file bare, so a typo, a missing directory or a
read-only target surfaced as a raw OSError past main()'s handler.
"""
import os

import pytest

from gsuite.errors import CLIError
from gsuite.services._common import read_file, write_file


def test_read_file_reports_a_missing_file(tmp_path):
    with pytest.raises(CLIError, match="cannot read"):
        read_file(str(tmp_path / "nope.pdf"))


def test_read_file_names_the_path(tmp_path):
    missing = str(tmp_path / "nope.pdf")
    with pytest.raises(CLIError) as exc:
        read_file(missing)
    assert missing in str(exc.value)


def test_read_file_returns_bytes(tmp_path):
    path = tmp_path / "ok.bin"
    path.write_bytes(b"hello")
    assert read_file(str(path)) == b"hello"


def test_write_file_reports_an_unwritable_destination(tmp_path):
    with pytest.raises(CLIError, match="cannot write"):
        write_file(str(tmp_path / "missing-dir" / "out.bin"), b"data")


def test_write_file_round_trips(tmp_path):
    path = tmp_path / "out.bin"
    write_file(str(path), b"data")
    assert path.read_bytes() == b"data"


# -- the four call sites, through the CLI ------------------------------------

def test_gmail_attach_missing_file_is_an_error(authed, fake_transport, run_cli):
    run_cli("gmail", "send", "--to", "a@x.com", "--subject", "s",
            "--body", "b", "--attach", "/nope/missing.pdf", expect=1)
    assert fake_transport.calls == []   # nothing sent


def test_drive_upload_missing_file_is_an_error(authed, fake_transport, run_cli):
    run_cli("drive", "upload", "/nope/missing.pdf", expect=1)
    assert fake_transport.calls == []


def test_drive_download_to_unwritable_path_is_an_error(authed, fake_transport,
                                                       run_cli, tmp_path):
    fake_transport.add("GET", "files/f1", b"filecontent")
    run_cli("drive", "download", "f1", "-o",
            str(tmp_path / "missing-dir" / "out.bin"), expect=1)


def test_gmail_attachment_download_to_unwritable_dir_is_an_error(
        authed, fake_transport, run_cli, tmp_path):
    fake_transport.add("GET", "messages/m1", {
        "id": "m1", "payload": {"parts": [
            {"filename": "a.bin", "mimeType": "application/octet-stream",
             "body": {"attachmentId": "att1", "size": 4}}]}})
    fake_transport.add("GET", "attachments/att1", {"data": "aGk"})
    target = tmp_path / "blocked"
    target.write_text("i am a file, not a directory")
    run_cli("gmail", "attachments", "m1", "-o", str(target / "sub"), expect=1)
