"""`gsuite searchconsole` — verified sites, search analytics, URL inspection."""
from __future__ import annotations

from gsuite.api import Client, quote_id
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.output import emit, emit_obj

BASE = "https://searchconsole.googleapis.com"


def _csv(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _keys(row: dict) -> str:
    return ",".join(row.get("keys", []))


def cmd_sites(args) -> int:
    # Not paged: the Search Console sites endpoint returns the full list.
    sites = Client.for_args(args).get(f"{BASE}/webmasters/v3/sites")
    emit(args, sites.get("siteEntry", []),
         [("SITE", "siteUrl"), ("PERMISSION", "permissionLevel")])
    return 0


def cmd_query(args) -> int:
    body = {
        "startDate": getattr(args, "from"),
        "endDate": args.to,
        "rowLimit": args.max,
    }
    dimensions = _csv(args.dimensions)
    if dimensions:
        body["dimensions"] = dimensions
    report = Client.for_args(args).post(
        f"{BASE}/webmasters/v3/sites/{quote_id(args.site)}/searchAnalytics/query",
        json_body=body)
    emit(args, report.get("rows", []),
         [("KEYS", _keys), ("CLICKS", "clicks"), ("IMPRESSIONS", "impressions"),
          ("CTR", "ctr"), ("POSITION", "position")])
    return 0


def cmd_inspect(args) -> int:
    result = Client.for_args(args).post(
        f"{BASE}/v1/urlInspection/index:inspect",
        json_body={"siteUrl": args.site, "inspectionUrl": args.url})
    status = result.get("inspectionResult", {}).get("indexStatusResult", {})
    emit_obj(args, {
        "verdict": status.get("verdict"),
        "coverage": status.get("coverageState"),
        "lastCrawl": status.get("lastCrawlTime"),
        "robots": status.get("robotsTxtState"),
    })
    return 0


def register(subparsers) -> None:
    register_service(subparsers, "searchconsole",
                     "Search Console: sites, search analytics, URL inspection", [
        Cmd("sites", cmd_sites, "list verified sites"),
        Cmd("query", cmd_query, "query search analytics for a site",
            (arg("site", help="e.g. https://example.com/ or sc-domain:example.com"),
             arg("--from", dest="from", metavar="DATE", required=True,
                 help="start date, YYYY-MM-DD"),
             arg("--to", metavar="DATE", required=True,
                 help="end date, YYYY-MM-DD"),
             arg("--dimensions",
                 help="comma-separated, e.g. query,page,country,device"),
             max_flag(25))),
        Cmd("inspect", cmd_inspect, "inspect a URL's index status",
            (arg("site", help="the verified site the URL belongs to"),
             arg("url", help="the full URL to inspect"))),
    ])
