"""Shared idioms for service command handlers."""
from __future__ import annotations

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


def emit_paged(args, url: str, columns: list[tuple], *, params: dict | None = None,
               key: str = "items", limit: int | None = None) -> None:
    """The list-command idiom: page through a collection and print it."""
    client = Client.for_args(args)
    emit(args, list(client.paged(url, params=params, key=key, limit=limit)),
         columns)
