"""`gsuite drive` — ls, search, upload/download, share, audit."""
from __future__ import annotations

import json
import mimetypes
import os
import sys

from gsuite.api import Client
from gsuite.output import emit

BASE = "https://www.googleapis.com/drive/v3"
UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"
FILE_FIELDS = "files(id,name,mimeType,modifiedTime,size,webViewLink),nextPageToken"
FILE_COLUMNS = [("ID", "id"), ("NAME", "name"), ("TYPE", "mimeType"),
                ("MODIFIED", "modifiedTime"), ("SIZE", "size")]
_BOUNDARY = "gsuite-multipart-boundary"


def _list_files(args, query: str, extra_columns: list | None = None) -> int:
    files = Client.for_args(args).paged(
        f"{BASE}/files", params={"q": query, "fields": FILE_FIELDS},
        key="files", limit=getattr(args, "max", None))
    emit(args, list(files), FILE_COLUMNS + (extra_columns or []))
    return 0


def cmd_ls(args) -> int:
    return _list_files(args, f"'{args.folder}' in parents and trashed = false")


def cmd_search(args) -> int:
    query = args.query
    if "=" not in query and " contains " not in query:
        escaped = query.replace("'", "\\'")
        query = f"name contains '{escaped}' and trashed = false"
    return _list_files(args, query)


def cmd_audit(args) -> int:
    query = ("(visibility = 'anyoneWithLink' or visibility = 'anyoneCanFind') "
             "and trashed = false")
    return _list_files(args, query, extra_columns=[("LINK", "webViewLink")])


def cmd_mkdir(args) -> int:
    body = {"name": args.name, "mimeType": FOLDER_MIME}
    if args.parent:
        body["parents"] = [args.parent]
    created = Client.for_args(args).post(f"{BASE}/files", json_body=body)
    print(f"created {created.get('id', '')} {created.get('name', '')}".strip())
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
    print(f"uploaded {uploaded.get('id', '')} {name}".strip())
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
    print(f"shared {args.id} with {grantee} as {args.role}")
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
    print(f"deleted {args.id}")
    return 0


def cmd_copy(args) -> int:
    body = {"name": args.name} if args.name else {}
    copied = Client.for_args(args).post(f"{BASE}/files/{args.id}/copy",
                                        json_body=body)
    print(f"copied to {copied.get('id', '')} {copied.get('name', '')}".strip())
    return 0


def register(subparsers) -> None:
    p = subparsers.add_parser("drive", help="files: ls, search, upload, share")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    ls = sub.add_parser("ls", help="list a folder (default: root)")
    ls.add_argument("folder", nargs="?", default="root")
    ls.add_argument("--max", type=int, default=100)
    ls.set_defaults(func=cmd_ls)

    search = sub.add_parser("search", help="search by name or raw Drive query")
    search.add_argument("query")
    search.add_argument("--max", type=int, default=50)
    search.set_defaults(func=cmd_search)

    audit = sub.add_parser("audit", help="find link-/publicly-shared files")
    audit.add_argument("--max", type=int, default=100)
    audit.set_defaults(func=cmd_audit)

    mkdir = sub.add_parser("mkdir", help="create a folder")
    mkdir.add_argument("name")
    mkdir.add_argument("--parent")
    mkdir.set_defaults(func=cmd_mkdir)

    upload = sub.add_parser("upload", help="upload a local file")
    upload.add_argument("file")
    upload.add_argument("--parent")
    upload.add_argument("--name", help="name in Drive (default: local basename)")
    upload.add_argument("--mime")
    upload.set_defaults(func=cmd_upload)

    download = sub.add_parser("download", help="download file content")
    download.add_argument("id")
    download.add_argument("-o", "--output", help="output path (default: stdout)")
    download.set_defaults(func=cmd_download)

    export = sub.add_parser("export", help="export a Google Doc/Sheet/Slides file")
    export.add_argument("id")
    export.add_argument("--mime", required=True,
                        help="target MIME type, e.g. application/pdf")
    export.add_argument("-o", "--output")
    export.set_defaults(func=cmd_export)

    share = sub.add_parser("share", help="grant access to a file")
    share.add_argument("id")
    share.add_argument("--with", required=True, metavar="EMAIL|anyone")
    share.add_argument("--role", default="reader",
                       choices=["reader", "commenter", "writer", "organizer",
                                "fileOrganizer", "owner"])
    share.set_defaults(func=cmd_share)

    perms = sub.add_parser("permissions", help="list a file's permissions")
    perms.add_argument("id")
    perms.set_defaults(func=cmd_permissions)

    rm = sub.add_parser("rm", help="delete a file permanently")
    rm.add_argument("id")
    rm.set_defaults(func=cmd_rm)

    copy = sub.add_parser("copy", help="copy a file")
    copy.add_argument("id")
    copy.add_argument("--name")
    copy.set_defaults(func=cmd_copy)
