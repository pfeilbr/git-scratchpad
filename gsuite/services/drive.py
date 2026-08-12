"""`gsuite drive` — ls, search, upload/download, share, audit."""
from __future__ import annotations

import json
import mimetypes
import os
import sys

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.output import confirm, emit
from gsuite.services._common import emit_paged

BASE = "https://www.googleapis.com/drive/v3"
UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"
FILE_FIELDS = "files(id,name,mimeType,modifiedTime,size,webViewLink),nextPageToken"
FILE_COLUMNS = [("ID", "id"), ("NAME", "name"), ("TYPE", "mimeType"),
                ("MODIFIED", "modifiedTime"), ("SIZE", "size")]
OUTPUT_FLAG = arg("-o", "--output", help="output path (default: stdout)")
_BOUNDARY = "gsuite-multipart-boundary"


def _emit_files(args, query: str, extra_columns: list | None = None) -> int:
    emit_paged(args, f"{BASE}/files", FILE_COLUMNS + (extra_columns or []),
               params={"q": query, "fields": FILE_FIELDS}, key="files",
               limit=getattr(args, "max", None))
    return 0


def cmd_ls(args) -> int:
    return _emit_files(args, f"'{args.folder}' in parents and trashed = false")


def cmd_search(args) -> int:
    query = args.query
    if "=" not in query and " contains " not in query:
        escaped = query.replace("'", "\\'")
        query = f"name contains '{escaped}' and trashed = false"
    return _emit_files(args, query)


def cmd_audit(args) -> int:
    query = ("(visibility = 'anyoneWithLink' or visibility = 'anyoneCanFind') "
             "and trashed = false")
    return _emit_files(args, query, extra_columns=[("LINK", "webViewLink")])


def cmd_mkdir(args) -> int:
    body = {"name": args.name, "mimeType": FOLDER_MIME}
    if args.parent:
        body["parents"] = [args.parent]
    created = Client.for_args(args).post(f"{BASE}/files", json_body=body)
    confirm("created", created.get("id"), created.get("name"))
    return 0


def _multipart_related(metadata: dict, content: bytes, mime: str) -> tuple[bytes, str]:
    head = (f"--{_BOUNDARY}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{_BOUNDARY}\r\n"
            f"Content-Type: {mime}\r\n\r\n").encode()
    tail = f"\r\n--{_BOUNDARY}--\r\n".encode()
    ctype = f"multipart/related; boundary={_BOUNDARY}"
    return head + content + tail, ctype


def cmd_upload(args) -> int:
    name = args.name or os.path.basename(args.file)
    mime = args.mime or mimetypes.guess_type(name)[0] or "application/octet-stream"
    with open(args.file, "rb") as fh:
        content = fh.read()
    metadata: dict = {"name": name}
    if args.parent:
        metadata["parents"] = [args.parent]
    body, ctype = _multipart_related(metadata, content, mime)
    uploaded = Client.for_args(args).post(
        f"{UPLOAD_BASE}/files?uploadType=multipart",
        data=body, headers={"Content-Type": ctype})
    confirm("uploaded", uploaded.get("id"), name)
    return 0


def _write_out(data: bytes, out_path: str | None) -> None:
    if out_path and out_path != "-":
        with open(out_path, "wb") as fh:
            fh.write(data)
        print(f"wrote {len(data)} bytes to {out_path}")
    else:
        sys.stdout.buffer.write(data)


def cmd_download(args) -> int:
    data = Client.for_args(args).get(f"{BASE}/files/{args.id}",
                                     params={"alt": "media"}, raw=True)
    _write_out(data, args.output)
    return 0


def cmd_export(args) -> int:
    data = Client.for_args(args).get(f"{BASE}/files/{args.id}/export",
                                     params={"mimeType": args.mime}, raw=True)
    _write_out(data, args.output)
    return 0


def cmd_share(args) -> int:
    grantee = getattr(args, "with")
    body = {"type": "anyone" if grantee == "anyone" else "user",
            "role": args.role}
    if grantee != "anyone":
        body["emailAddress"] = grantee
    Client.for_args(args).post(f"{BASE}/files/{args.id}/permissions",
                               json_body=body)
    confirm("shared", args.id, "with", grantee, "as", args.role)
    return 0


def cmd_permissions(args) -> int:
    perms = Client.for_args(args).get(
        f"{BASE}/files/{args.id}/permissions",
        params={"fields": "permissions(id,type,role,emailAddress)"})
    emit(args, perms.get("permissions", []),
         [("ID", "id"), ("TYPE", "type"), ("ROLE", "role"),
          ("EMAIL", "emailAddress")])
    return 0


def cmd_rm(args) -> int:
    Client.for_args(args).delete(f"{BASE}/files/{args.id}")
    confirm("deleted", args.id)
    return 0


def cmd_copy(args) -> int:
    body = {"name": args.name} if args.name else {}
    copied = Client.for_args(args).post(f"{BASE}/files/{args.id}/copy",
                                        json_body=body)
    confirm("copied to", copied.get("id"), copied.get("name"))
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "drive", "files: ls, search, upload, share", [
        Cmd("ls", cmd_ls, "list a folder (default: root)",
            (arg("folder", nargs="?", default="root"), max_flag(100))),
        Cmd("search", cmd_search, "search by name or raw Drive query",
            (arg("query"), max_flag(50))),
        Cmd("audit", cmd_audit, "find link-/publicly-shared files",
            (max_flag(100),)),
        Cmd("mkdir", cmd_mkdir, "create a folder",
            (arg("name"), arg("--parent"))),
        Cmd("upload", cmd_upload, "upload a local file",
            (arg("file"), arg("--parent"),
             arg("--name", help="name in Drive (default: local basename)"),
             arg("--mime"))),
        Cmd("download", cmd_download, "download file content",
            (arg("id"), OUTPUT_FLAG)),
        Cmd("export", cmd_export, "export a Google Doc/Sheet/Slides file",
            (arg("id"), arg("--mime", required=True,
                            help="target MIME type, e.g. application/pdf"),
             OUTPUT_FLAG)),
        Cmd("share", cmd_share, "grant access to a file",
            (arg("id"), arg("--with", required=True, metavar="EMAIL|anyone"),
             arg("--role", default="reader",
                 choices=["reader", "commenter", "writer", "organizer",
                          "fileOrganizer", "owner"]))),
        Cmd("permissions", cmd_permissions, "list a file's permissions",
            (arg("id"),)),
        Cmd("rm", cmd_rm, "delete a file permanently", (arg("id"),)),
        Cmd("copy", cmd_copy, "copy a file", (arg("id"), arg("--name"))),
    ])
