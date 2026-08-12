"""Shared idioms for service command handlers."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.output import emit


def emit_paged(args, url: str, columns: list[tuple], *, params: dict | None = None,
               key: str = "items", limit: int | None = None) -> None:
    """The list-command idiom: page through a collection and print it."""
    client = Client.for_args(args)
    emit(args, list(client.paged(url, params=params, key=key, limit=limit)),
         columns)
