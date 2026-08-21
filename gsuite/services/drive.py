"""`gsuite drive` — ls, search, upload/download, share, audit."""
from __future__ import annotations

import json
import mimetypes
import os
import sys

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, Group, arg, max_flag, register_service
from gsuite.errors import CLIError
from gsuite.output import confirm, emit, emit_obj
from gsuite.services._common import emit_paged, read_file, write_file

BASE = "https://www.googleapis.com/drive/v3"
UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
FILE_FIELDS = "files(id,name,mimeType,modifiedTime,size,webViewLink),nextPageToken"
INFO_FIELDS = ("id,name,mimeType,size,modifiedTime,parents,webViewLink,"
               "owners(emailAddress),trashed")
FILE_COLUMNS = [("ID", "id"), ("NAME", "name"), ("TYPE", "mimeType"),
                ("MODIFIED", "modifiedTime"), ("SIZE", "size")]
DRIVE_COLUMNS = [("ID", "id"), ("NAME", "name"), ("CREATED", "createdTime")]
OUTPUT_FLAG = arg("-o", "--output", help="output path (default: stdout)")
DRIVE_FLAG = arg("--drive", help="scope to one shared drive by id")
_BOUNDARY = "gsuite-multipart-boundary"


def _with_shared(params: dict | None = None) -> dict:
    """Params plus the flag that makes an API call see shared-drive items."""
    return {**(params or {}), "supportsAllDrives": "true"}


def _q_literal(value: str) -> str:
    """Quote a user-supplied value as a Drive query string literal.

    Drive's `q` syntax escapes `\\` and `'` inside a literal. Backslash goes
    first: escaping the quote first would leave a trailing `\\` free to escape
    the closing quote, letting the value run on into the rest of the query.
    """
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _emit_files(args, query: str, extra_columns: list | None = None) -> int:
    params = _with_shared({"q": query, "fields": FILE_FIELDS})
    params["includeItemsFromAllDrives"] = "true"
    if getattr(args, "drive", None):
        params.update(corpora="drive", driveId=args.drive)
    emit_paged(args, f"{BASE}/files", FILE_COLUMNS + (extra_columns or []),
               params=params, key="files", limit=getattr(args, "max", None))
    return 0


def cmd_drives(args) -> int:
    emit_paged(args, f"{BASE}/drives", DRIVE_COLUMNS,
               params={"pageSize": 100}, key="drives",
               limit=getattr(args, "max", None))
    return 0


def cmd_ls(args) -> int:
    return _emit_files(
        args, f"{_q_literal(args.folder)} in parents and trashed = false")


def cmd_search(args) -> int:
    query = args.query
    # A query containing `=` or ` contains ` is taken as a raw Drive query and
    # passed through untouched — it is deliberately written in `q` syntax, so
    # escaping it would break the operators the caller meant to use.
    if "=" not in query and " contains " not in query:
        query = f"name contains {_q_literal(query)} and trashed = false"
    return _emit_files(args, query)


def cmd_audit(args) -> int:
    query = ("(visibility = 'anyoneWithLink' or visibility = 'anyoneCanFind') "
             "and trashed = false")
    return _emit_files(args, query, extra_columns=[("LINK", "webViewLink")])


def cmd_info(args) -> int:
    meta = Client.for_args(args).get(f"{BASE}/files/{quote_id(args.id)}",
                                     params=_with_shared({"fields": INFO_FIELDS}))
    emit_obj(args, meta, [
        ("id", "id"), ("name", "name"), ("type", "mimeType"),
        ("size", "size"), ("modified", "modifiedTime"),
        ("parents", lambda m: ",".join(m.get("parents", []))),
        ("link", "webViewLink"),
        ("owner", lambda m: (m.get("owners") or [{}])[0].get("emailAddress")),
        ("trashed", "trashed"),
    ])
    return 0


def cmd_mv(args) -> int:
    if not args.parent and not args.name:
        raise CLIError("nothing to do: pass --parent and/or --name")
    client = Client.for_args(args)
    params = None
    if args.parent:
        current = client.get(f"{BASE}/files/{quote_id(args.id)}",
                             params={"fields": "parents"}).get("parents", [])
        params = {"addParents": args.parent,
                  "removeParents": ",".join(current)}
    body = {"name": args.name} if args.name else {}
    client.patch(f"{BASE}/files/{quote_id(args.id)}",
                 params=_with_shared(params), json_body=body)
    confirm("moved" if args.parent else "renamed", args.id)
    return 0


def cmd_trash(args) -> int:
    Client.for_args(args).patch(f"{BASE}/files/{quote_id(args.id)}",
                                params=_with_shared(),
                                json_body={"trashed": True})
    confirm("trashed", args.id)
    return 0


def cmd_restore(args) -> int:
    Client.for_args(args).patch(f"{BASE}/files/{quote_id(args.id)}",
                                params=_with_shared(),
                                json_body={"trashed": False})
    confirm("restored", args.id)
    return 0


def cmd_mkdir(args) -> int:
    body = {"name": args.name, "mimeType": FOLDER_MIME}
    if args.parent:
        body["parents"] = [args.parent]
    created = Client.for_args(args).post(f"{BASE}/files",
                                        params=_with_shared(), json_body=body)
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
    content = read_file(args.file)
    metadata: dict = {"name": name}
    if args.parent:
        metadata["parents"] = [args.parent]
    body, ctype = _multipart_related(metadata, content, mime)
    uploaded = Client.for_args(args).post(
        f"{UPLOAD_BASE}/files?uploadType=multipart",
        params=_with_shared(), data=body, headers={"Content-Type": ctype})
    confirm("uploaded", uploaded.get("id"), name)
    return 0


def _write_out(data: bytes, out_path: str | None) -> None:
    if out_path and out_path != "-":
        write_file(out_path, data)
        print(f"wrote {len(data)} bytes to {out_path}")
    else:
        sys.stdout.buffer.write(data)


def cmd_download(args) -> int:
    data = Client.for_args(args).get(f"{BASE}/files/{quote_id(args.id)}",
                                     params=_with_shared({"alt": "media"}),
                                     raw=True)
    _write_out(data, args.output)
    return 0


def cmd_export(args) -> int:
    data = Client.for_args(args).get(
        f"{BASE}/files/{quote_id(args.id)}/export",
        params=_with_shared({"mimeType": args.mime}), raw=True)
    _write_out(data, args.output)
    return 0


def cmd_share(args) -> int:
    grantee = getattr(args, "with")
    body = {"type": "anyone" if grantee == "anyone" else "user",
            "role": args.role}
    if grantee != "anyone":
        body["emailAddress"] = grantee
    Client.for_args(args).post(f"{BASE}/files/{quote_id(args.id)}/permissions",
                               params=_with_shared(), json_body=body)
    confirm("shared", args.id, "with", grantee, "as", args.role)
    return 0


def cmd_permissions(args) -> int:
    perms = Client.for_args(args).get(
        f"{BASE}/files/{quote_id(args.id)}/permissions",
        params=_with_shared(
            {"fields": "permissions(id,type,role,emailAddress)"}))
    emit(args, perms.get("permissions", []),
         [("ID", "id"), ("TYPE", "type"), ("ROLE", "role"),
          ("EMAIL", "emailAddress")])
    return 0


def cmd_rm(args) -> int:
    Client.for_args(args).delete(f"{BASE}/files/{quote_id(args.id)}",
                                 params=_with_shared())
    confirm("deleted", args.id)
    return 0


def cmd_copy(args) -> int:
    body = {"name": args.name} if args.name else {}
    copied = Client.for_args(args).post(
        f"{BASE}/files/{quote_id(args.id)}/copy",
        params=_with_shared(), json_body=body)
    confirm("copied to", copied.get("id"), copied.get("name"))
    return 0


# -- comments ---------------------------------------------------------------
#
# Two things set the comments collection apart from the files collection it
# hangs off, and both are easy to get wrong by copying the idioms above.
#
# It *requires* `fields`. Every comments and replies method answers "The
# 'fields' parameter is required for this method" when it is missing — there
# is no default projection — so each request below names what it wants.
#
# And it declares no `supportsAllDrives`, so `_with_shared` must stay away
# from here: Drive rejects a parameter a method does not declare, which would
# turn a call that looks more compatible into a 400.

COMMENT_FIELDS = ("id,createdTime,modifiedTime,resolved,deleted,content,"
                  "author(displayName),quotedFileContent(value),"
                  "replies(id,createdTime,content,action,author(displayName))")
COMMENT_LIST_FIELDS = f"comments({COMMENT_FIELDS}),nextPageToken"
REPLY_FIELDS = ("id,createdTime,modifiedTime,content,action,"
                "author(displayName)")


def _author(item: dict) -> str:
    """The display name on a comment or reply, or "" for a deleted author."""
    return (item.get("author") or {}).get("displayName", "")


def _oneline(text) -> str:
    """A comment body flattened for a table cell.

    Comment bodies routinely run to several lines. Printed as they arrive
    they escape their column and drag every row after them out of line, so
    the table shows them collapsed; `comments get` and `--json` still hand
    back the body exactly as Drive stores it.
    """
    return " ".join(str(text or "").split())


COMMENT_COLUMNS = [("ID", "id"), ("AUTHOR", _author),
                   ("CREATED", "createdTime"), ("RESOLVED", "resolved"),
                   ("REPLIES", lambda c: len(c.get("replies") or [])),
                   ("CONTENT", lambda c: _oneline(c.get("content")))]
COMMENT_OBJECT_FIELDS = [
    ("id", "id"), ("author", _author), ("created", "createdTime"),
    ("modified", "modifiedTime"), ("resolved", "resolved"),
    ("quoted", lambda c: (c.get("quotedFileContent") or {}).get("value")),
    ("content", "content"),
    ("replies", lambda c: len(c.get("replies") or [])),
]


def _comments_url(file_id: str) -> str:
    return f"{BASE}/files/{quote_id(file_id)}/comments"


def _comment_url(file_id: str, comment_id: str) -> str:
    return f"{_comments_url(file_id)}/{quote_id(comment_id)}"


def cmd_comments_list(args) -> int:
    params = {"fields": COMMENT_LIST_FIELDS, "pageSize": 100}
    if args.include_deleted:
        params["includeDeleted"] = "true"
    emit_paged(args, _comments_url(args.file), COMMENT_COLUMNS,
               params=params, key="comments", limit=args.max)
    return 0


def cmd_comments_get(args) -> int:
    comment = Client.for_args(args).get(
        _comment_url(args.file, args.comment),
        params={"fields": COMMENT_FIELDS})
    emit_obj(args, comment, COMMENT_OBJECT_FIELDS)
    return 0


def cmd_comments_create(args) -> int:
    body = {"content": args.content}
    if args.quote:
        # The passage the comment is about. Drive matches it against the file
        # to anchor the comment; without it the comment floats at the top.
        body["quotedFileContent"] = {"value": args.quote}
    created = Client.for_args(args).post(
        _comments_url(args.file), params={"fields": COMMENT_FIELDS},
        json_body=body)
    confirm("created comment", created.get("id"), "on", args.file)
    return 0


def cmd_comments_update(args) -> int:
    Client.for_args(args).patch(
        _comment_url(args.file, args.comment),
        params={"fields": COMMENT_FIELDS},
        json_body={"content": args.content})
    confirm("updated comment", args.comment)
    return 0


def cmd_comments_delete(args) -> int:
    # The one comments method with nothing to project: it returns an empty
    # body, so `fields` would have nothing to name.
    Client.for_args(args).delete(_comment_url(args.file, args.comment))
    confirm("deleted comment", args.comment, "from", args.file)
    return 0


def _post_reply(args, body: dict) -> dict:
    """Post one reply to a comment.

    Replies are projected exactly like comments, so `fields` is as mandatory
    here as it is on the collection they hang off.
    """
    return Client.for_args(args).post(
        f"{_comment_url(args.file, args.comment)}/replies",
        params={"fields": REPLY_FIELDS}, json_body=body)


def cmd_comments_reply(args) -> int:
    reply = _post_reply(args, {"content": args.content})
    confirm("replied", reply.get("id"), "to", args.comment)
    return 0


def _act_on_comment(args, action: str, past: str) -> int:
    """Resolve or reopen a comment.

    Drive exposes neither as a method: a comment's `resolved` flag is set by
    posting a reply that carries the action, so both verbs are the replies
    endpoint with a two-key body. `content` rides along only when the user
    gave one — sending an empty string would post a blank reply that everyone
    reading the file can see.
    """
    body = {"action": action}
    if args.content:
        body["content"] = args.content
    _post_reply(args, body)
    confirm(past, args.comment)
    return 0


def cmd_comments_resolve(args) -> int:
    return _act_on_comment(args, "resolve", "resolved")


def cmd_comments_reopen(args) -> int:
    return _act_on_comment(args, "reopen", "reopened")


# -- revisions --------------------------------------------------------------
#
# Like comments, the revisions collection declares no `supportsAllDrives` —
# see the note above for why sending it anyway would be a 400 rather than a
# courtesy. It does not demand `fields`, but naming them keeps the table's
# columns from depending on whatever Drive's default projection happens to
# include.

REVISION_FIELDS = ("id,modifiedTime,size,mimeType,keepForever,published,"
                   "originalFilename,lastModifyingUser(displayName)")


def _last_modifier(revision: dict) -> str:
    """Who saved this revision, or "" once that account is gone."""
    return (revision.get("lastModifyingUser") or {}).get("displayName", "")


REVISION_COLUMNS = [("ID", "id"), ("MODIFIED", "modifiedTime"),
                    ("SIZE", "size"), ("AUTHOR", _last_modifier),
                    ("KEEP", "keepForever")]


def _revisions_url(file_id: str) -> str:
    return f"{BASE}/files/{quote_id(file_id)}/revisions"


def cmd_revisions_list(args) -> int:
    emit_paged(args, _revisions_url(args.file), REVISION_COLUMNS,
               params={"fields": f"revisions({REVISION_FIELDS}),nextPageToken",
                       "pageSize": 100},
               key="revisions", limit=args.max)
    return 0


def cmd_revisions_get(args) -> int:
    revision = Client.for_args(args).get(
        f"{_revisions_url(args.file)}/{quote_id(args.revision)}",
        params={"fields": REVISION_FIELDS})
    emit_obj(args, revision, [
        ("id", "id"), ("modified", "modifiedTime"), ("size", "size"),
        ("type", "mimeType"), ("filename", "originalFilename"),
        ("author", _last_modifier),
        ("keepForever", "keepForever"), ("published", "published"),
    ])
    return 0


def cmd_rename(args) -> int:
    # `mv --name` renames too, but it also carries the machinery for changing
    # parents. Renaming is the common half, and asking for it by name means
    # never risking a typo in `--parent` moving the file as well.
    Client.for_args(args).patch(f"{BASE}/files/{quote_id(args.id)}",
                                params=_with_shared(),
                                json_body={"name": args.name})
    confirm("renamed", args.id, "to", args.name)
    return 0


def cmd_url(args) -> int:
    """Print each id's web URL. The one Drive command that stays offline.

    `open?id=` rather than the prettier `/file/d/<id>/view` because this makes
    no API call and so cannot know what it is looking at: the `/file/` form
    404s for folders and for native Docs/Sheets/Slides, while `open?id=`
    redirects to the right viewer for every one of them. The id is escaped as
    a query value, so an id containing `&` adds no second parameter.
    """
    rows = []
    for file_id in args.ids:
        if not file_id.strip():
            raise CLIError("file id must not be empty")
        rows.append({"id": file_id,
                     "url": f"https://drive.google.com/open?id="
                            f"{quote_id(file_id)}"})
    emit(args, rows, [("ID", "id"), ("URL", "url")])
    return 0


def _permission_id_for(client, file_id: str, grantee: str) -> str:
    """The id of the permission granting `grantee` access to `file_id`.

    `share` names a person or `anyone`, so `unshare` has to accept the same
    thing — but Drive deletes permissions by their own opaque id, which the
    user has no reason to know. This lookup is what makes the two commands
    inverses instead of near-neighbours.
    """
    perms = client.get(
        f"{BASE}/files/{quote_id(file_id)}/permissions",
        params=_with_shared({"fields": "permissions(id,type,emailAddress)"}))
    wanted = grantee.lower()
    for perm in perms.get("permissions", []):
        matched = (perm.get("type") == "anyone" if wanted == "anyone"
                   else (perm.get("emailAddress") or "").lower() == wanted)
        if matched and perm.get("id"):
            return perm["id"]
    raise CLIError(f"{file_id} is not shared with {grantee}")


def cmd_unshare(args) -> int:
    grantee = getattr(args, "with")
    if bool(grantee) == bool(args.permission):
        raise CLIError("pass exactly one of --with EMAIL|anyone "
                       "or --permission ID")
    client = Client.for_args(args)
    permission = (args.permission
                  or _permission_id_for(client, args.id, grantee))
    client.delete(
        f"{BASE}/files/{quote_id(args.id)}/permissions/{quote_id(permission)}",
        params=_with_shared())
    confirm("unshared", args.id, "from", grantee or permission)
    return 0


def cmd_shortcut(args) -> int:
    client = Client.for_args(args)
    name = args.name
    if not name:
        # An unnamed shortcut is filed as "Untitled", which is never what the
        # user meant. Borrowing the target's name mirrors how `upload`
        # defaults to the local basename.
        name = client.get(f"{BASE}/files/{quote_id(args.target)}",
                          params=_with_shared({"fields": "name"})).get("name")
    body = {"name": name, "mimeType": SHORTCUT_MIME,
            "shortcutDetails": {"targetId": args.target}}
    if args.parent:
        body["parents"] = [args.parent]
    created = client.post(f"{BASE}/files", params=_with_shared(),
                          json_body=body)
    confirm("created shortcut", created.get("id"), "to", args.target)
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "drive", "files: ls, search, upload, share", [
        Cmd("ls", cmd_ls, "list a folder (default: root)",
            (arg("folder", nargs="?", default="root"), DRIVE_FLAG,
             max_flag(100))),
        Cmd("search", cmd_search, "search by name or raw Drive query",
            (arg("query"), DRIVE_FLAG, max_flag(50))),
        Cmd("audit", cmd_audit, "find link-/publicly-shared files",
            (max_flag(100),)),
        Cmd("info", cmd_info, "show a file's metadata", (arg("id"),)),
        Cmd("mv", cmd_mv, "move and/or rename a file",
            (arg("id"), arg("--parent", help="new parent folder id"),
             arg("--name", help="new file name"))),
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
        Cmd("trash", cmd_trash, "move a file to the trash", (arg("id"),)),
        Cmd("restore", cmd_restore, "restore a file from the trash",
            (arg("id"),)),
        Cmd("rm", cmd_rm, "delete a file permanently", (arg("id"),)),
        Cmd("copy", cmd_copy, "copy a file", (arg("id"), arg("--name"))),
        Cmd("drives", cmd_drives, "list shared drives", (max_flag(50),)),
        Group("comments", "read and write comments on a file", (
            Cmd("list", cmd_comments_list, "list comments on a file",
                (arg("file"), arg("--include-deleted", action="store_true",
                                  help="include deleted comments"),
                 max_flag(50))),
            Cmd("get", cmd_comments_get,
                "show one comment (--json for the reply text)",
                (arg("file"), arg("comment"))),
            Cmd("create", cmd_comments_create, "comment on a file",
                (arg("file"), arg("--content", required=True),
                 arg("--quote", metavar="TEXT",
                     help="passage in the file the comment is about"))),
            Cmd("update", cmd_comments_update, "edit a comment's text",
                (arg("file"), arg("comment"),
                 arg("--content", required=True))),
            Cmd("delete", cmd_comments_delete, "delete a comment",
                (arg("file"), arg("comment"))),
            Cmd("reply", cmd_comments_reply, "reply to a comment",
                (arg("file"), arg("comment"),
                 arg("--content", required=True))),
            Cmd("resolve", cmd_comments_resolve, "mark a comment resolved",
                (arg("file"), arg("comment"),
                 arg("--content", help="text to reply with as you resolve"))),
            Cmd("reopen", cmd_comments_reopen, "reopen a resolved comment",
                (arg("file"), arg("comment"),
                 arg("--content", help="text to reply with as you reopen"))),
        )),
        Group("revisions", "a file's version history", (
            Cmd("list", cmd_revisions_list, "list a file's revisions",
                (arg("file"), max_flag(50))),
            Cmd("get", cmd_revisions_get, "show one revision",
                (arg("file"), arg("revision"))),
        )),
        Cmd("rename", cmd_rename, "rename a file or folder",
            (arg("id"), arg("name", help="the new name"))),
        Cmd("url", cmd_url, "print the web URL of one or more files "
                            "(no API call)",
            (arg("ids", nargs="+", metavar="ID"),)),
        Cmd("unshare", cmd_unshare, "revoke access to a file",
            (arg("id"), arg("--with", metavar="EMAIL|anyone",
                            help="the grantee whose access to revoke"),
             arg("--permission", metavar="ID",
                 help="the permission id, if you already know it"))),
        Cmd("shortcut", cmd_shortcut, "create a shortcut to a file",
            (arg("target", help="id of the file to point at"),
             arg("--name", help="shortcut name (default: the target's)"),
             arg("--parent", help="folder to create the shortcut in"))),
    ])
