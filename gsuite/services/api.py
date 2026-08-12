"""`gsuite api` — raw authorized calls to any Google API + Discovery browsing.

The dynamic escape hatch (gws-style): every Google API method is reachable
even when gsuite has no hand-crafted command for it.
"""
from __future__ import annotations

import json

from gsuite.api import Client
from gsuite.errors import CLIError
from gsuite.output import emit

DISCOVERY = "https://www.googleapis.com/discovery/v1/apis"


def cmd_call(args) -> int:
    url = args.path
    if not url.startswith("http"):
        url = f"https://www.googleapis.com/{url.lstrip('/')}"
    params = {}
    for pair in args.param or []:
        if "=" not in pair:
            raise CLIError(f"bad --param (want key=value): {pair}")
        key, value = pair.split("=", 1)
        params[key] = value
    body = None
    if args.body is not None:
        try:
            body = json.loads(args.body)
        except ValueError as exc:
            raise CLIError(f"--body is not valid JSON: {exc}") from exc
    result = Client.for_args(args).request(args.method.upper(), url,
                                           params=params or None,
                                           json_body=body)
    print(json.dumps(result, indent=2, sort_keys=True))
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
    p = subparsers.add_parser("api", help="raw calls to any Google API")
    sub = p.add_subparsers(dest="subcommand", metavar="<command>")

    call = sub.add_parser("call", help="authorized request to any endpoint")
    call.add_argument("method", help="GET/POST/PATCH/PUT/DELETE")
    call.add_argument("path",
                      help="full URL or path under www.googleapis.com "
                           "(e.g. drive/v3/about)")
    call.add_argument("--param", action="append", metavar="KEY=VALUE")
    call.add_argument("--body", help="JSON request body")
    call.set_defaults(func=cmd_call)

    describe = sub.add_parser("describe", help="list an API's methods "
                                               "(Discovery service)")
    describe.add_argument("service", help="e.g. gmail, drive, tasks")
    describe.add_argument("--api-version", help="e.g. v1 (default: preferred)")
    describe.set_defaults(func=cmd_describe)

    sub.add_parser("list", help="list available Google APIs").set_defaults(
        func=cmd_list)
