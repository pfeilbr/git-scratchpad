"""Shared idioms for service command handlers."""
from __future__ import annotations

import os
import urllib.parse

from gsuite.api import Client
from gsuite.errors import CLIError
from gsuite.output import emit

# Segments that would make the server (or an intermediary) resolve the path
# somewhere other than where the URL literally points.
_TRAVERSAL_SEGMENTS = {".", ".."}


def resource_path(value: str) -> str:
    """Percent-encode a Google *resource name* for use inside a URL path.

    Unlike `gsuite.api.quote_id`, which escapes a single opaque segment with
    ``safe=""``, this keeps ``/`` literal: the values it guards are genuinely
    multi-segment names — ``spaces/AAAA``, ``people/c123``, ``notes/n1``,
    ``contactGroups/abc``, ``properties/123``,
    ``conferenceRecords/c1/participants/p1``. Encoding their separators as
    ``%2F`` would send every one of those commands to a path that does not
    exist. Use `quote_id` instead whenever the value really is one segment.

    Keeping ``/`` means the traversal that encoding would have neutralized has
    to be rejected outright: an id of ``../../v1/other`` would otherwise walk
    out of the endpoint the command meant to call and into a different API
    path. Everything else a user can type — ``?``, ``#``, spaces, control
    characters — is percent-encoded, so it can no longer end the path and
    start a query string, a fragment, or a second request.
    """
    if "\\" in value:
        raise CLIError(f"invalid resource name {value!r}: "
                       "backslashes are not allowed")
    if value.startswith("/"):
        raise CLIError(f"invalid resource name {value!r}: "
                       "must not start with '/'")
    if any(segment in _TRAVERSAL_SEGMENTS for segment in value.split("/")):
        raise CLIError(f"invalid resource name {value!r}: "
                       "'.' and '..' path segments are not allowed")
    return urllib.parse.quote(value, safe="/")


def read_file(path: str) -> bytes:
    """Read a file the user named, as bytes.

    Paths come off the command line — `gmail send --attach`, `drive upload` —
    so a typo, a missing directory or a permission problem is ordinary user
    error, not a bug. Bare `open()` raised OSError straight past main()'s
    handler and printed a traceback; this reports it like every other
    operational failure.
    """
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        raise CLIError(f"cannot read {path}: {exc.strerror or exc}") from exc


def make_dir(path: str) -> None:
    """Create an output directory the user named, parents included."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        raise CLIError(
            f"cannot create directory {path}: {exc.strerror or exc}") from exc


def write_file(path: str, data: bytes) -> None:
    """Write bytes to a file the user named. See `read_file` for the why."""
    try:
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError as exc:
        raise CLIError(f"cannot write {path}: {exc.strerror or exc}") from exc


def emit_paged(args, url: str, columns: list[tuple], *, params: dict | None = None,
               key: str = "items", limit: int | None = None) -> None:
    """The list-command idiom: page through a collection and print it."""
    client = Client.for_args(args)
    emit(args, list(client.paged(url, params=params, key=key, limit=limit)),
         columns)
