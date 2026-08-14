"""`gsuite api` — raw authorized calls to any Google API + Discovery browsing.

The dynamic escape hatch (gws-style): every Google API method is reachable
even when gsuite has no hand-crafted command for it.
"""
from __future__ import annotations

import json
import sys

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, register_service
from gsuite.errors import CLIError
from gsuite.output import emit

DISCOVERY = "https://www.googleapis.com/discovery/v1/apis"


def _print_response(body: bytes) -> None:
    """Pretty-print a JSON reply; print any other body as text.

    `api call` can reach endpoints that answer text, HTML or CSV (Drive's
    `export`, `alt=media`, a proxy's error page), so it takes the bytes raw
    and decides here — `Client.request` keeps parsing JSON for every typed
    caller. A body that opens like JSON but does not parse is a real error
    (a truncated reply), so it is reported rather than dumped on stdout.
    """
    if not body:
        print("{}")  # 204/empty: unchanged from when request() parsed for us
        return
    try:
        parsed = json.loads(body)
    except ValueError as exc:
        text = body.decode("utf-8", errors="replace")
        if text.lstrip()[:1] in ("{", "["):
            raise CLIError(f"response was not valid JSON: {exc}") from exc
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        return
    print(json.dumps(parsed, indent=2, sort_keys=True))


def cmd_call(args) -> int:
    url = args.path
    if not url.startswith("http"):
        url = f"https://www.googleapis.com/{url.lstrip('/')}"
    params: dict[str, list[str]] = {}
    for pair in args.param or []:
        if "=" not in pair:
            raise CLIError(f"bad --param (want key=value): {pair}")
        key, value = pair.split("=", 1)
        # Repeated keys accumulate instead of overwriting: several APIs take a
        # parameter more than once (Gmail's metadataHeaders and labelIds,
        # Calendar's eventTypes), and request()'s urlencode(doseq=True)
        # expands each list back into one occurrence per value.
        params.setdefault(key, []).append(value)
    body = None
    if args.body is not None:
        text = args.body
        if text == "-":
            text = sys.stdin.read()
        elif text.startswith("@"):
            try:
                with open(text[1:], encoding="utf-8") as fh:
                    text = fh.read()
            except OSError as exc:
                raise CLIError(f"cannot read --body file: {exc}") from exc
        try:
            body = json.loads(text)
        except ValueError as exc:
            raise CLIError(f"--body is not valid JSON: {exc}") from exc
    _print_response(Client.for_args(args).request(args.method.upper(), url,
                                                  params=params or None,
                                                  json_body=body, raw=True))
    return 0


def _flatten_methods(node: dict, out: list[dict]) -> None:
    for method in node.get("methods", {}).values():
        out.append({"id": method.get("id", ""),
                    "http": method.get("httpMethod", ""),
                    "path": method.get("path", ""),
                    "description": method.get("description", "")})
    for resource in node.get("resources", {}).values():
        _flatten_methods(resource, out)


def cmd_describe(args) -> int:
    version = args.api_version
    client = Client.for_args(args)
    if not version:
        directory = client.get(DISCOVERY, params={"name": args.service,
                                                  "preferred": "true"})
        items = directory.get("items", [])
        if not items:
            raise CLIError(f"no API named {args.service} in the Discovery directory")
        version = items[0]["version"]
    doc = client.get(f"{DISCOVERY}/{args.service}/{version}/rest")
    methods: list[dict] = []
    _flatten_methods(doc, methods)
    emit(args, sorted(methods, key=lambda m: m["id"]),
         [("METHOD", "id"), ("HTTP", "http"), ("PATH", "path"),
          ("DESCRIPTION", "description")])
    return 0


def cmd_list(args) -> int:
    directory = Client.for_args(args).get(DISCOVERY,
                                          params={"preferred": "true"})
    emit(args, directory.get("items", []),
         [("NAME", "name"), ("VERSION", "version"), ("TITLE", "title")])
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "api", "raw calls to any Google API", [
        Cmd("call", cmd_call, "authorized request to any endpoint",
            (arg("method", help="GET/POST/PATCH/PUT/DELETE"),
             arg("path", help="full URL or path under www.googleapis.com "
                              "(e.g. drive/v3/about)"),
             arg("--param", action="append", metavar="KEY=VALUE",
                 help="query parameter; repeat for more than one, and "
                      "repeat the same key to send it more than once"),
             arg("--body", help="JSON request body (@file reads from a "
                                "file, - reads from stdin)"))),
        Cmd("describe", cmd_describe,
            "list an API's methods (Discovery service)",
            (arg("service", help="e.g. gmail, drive, tasks"),
             arg("--api-version", help="e.g. v1 (default: preferred)"))),
        Cmd("list", cmd_list, "list available Google APIs"),
    ])
