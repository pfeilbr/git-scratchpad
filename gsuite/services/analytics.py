"""`gsuite analytics` — GA4 properties and (realtime) reports."""
from __future__ import annotations

from gsuite.api import Client
from gsuite.cmdreg import Cmd, arg, max_flag, register_service
from gsuite.output import emit
from gsuite.services._common import resource_path

DATA = "https://analyticsdata.googleapis.com/v1beta"
ADMIN = "https://analyticsadmin.googleapis.com/v1beta"


def _csv(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _property(value: str) -> str:
    """Accept `properties/123` or a bare `123`; return the raw name."""
    return (value if value.startswith("properties/")
            else f"properties/{value}")


def _report_body(args, *, dates: bool) -> dict:
    body: dict = {}
    if dates:
        body["dateRanges"] = [{"startDate": getattr(args, "from"),
                               "endDate": args.to}]
    body["metrics"] = [{"name": m} for m in _csv(args.metrics)]
    dimensions = _csv(args.dimensions)
    if dimensions:
        body["dimensions"] = [{"name": d} for d in dimensions]
    body["limit"] = args.max
    return body


def _emit_report(args, report: dict) -> None:
    """Columns follow the response headers, so the table matches the request."""
    names = ([h.get("name", "") for h in report.get("dimensionHeaders", [])]
             + [h.get("name", "") for h in report.get("metricHeaders", [])])
    rows = []
    for row in report.get("rows", []):
        values = [cell.get("value", "")
                  for cell in (row.get("dimensionValues", [])
                               + row.get("metricValues", []))]
        rows.append(dict(zip(names, values)))
    emit(args, rows, [(name.upper(), name) for name in names])


def cmd_properties(args) -> int:
    summaries = Client.for_args(args).get(f"{ADMIN}/accountSummaries")
    rows = [dict(prop, account=summary.get("account", ""))
            for summary in summaries.get("accountSummaries", [])
            for prop in summary.get("propertySummaries", [])]
    emit(args, rows, [("PROPERTY", "property"), ("NAME", "displayName"),
                      ("ACCOUNT", "account")])
    return 0


def cmd_report(args) -> int:
    report = Client.for_args(args).post(
        f"{DATA}/{resource_path(_property(args.property))}:runReport",
        json_body=_report_body(args, dates=True))
    _emit_report(args, report)
    return 0


def cmd_realtime(args) -> int:
    report = Client.for_args(args).post(
        f"{DATA}/{resource_path(_property(args.property))}:runRealtimeReport",
        json_body=_report_body(args, dates=False))
    _emit_report(args, report)
    return 0


PROPERTY_ARG = arg("property", help="e.g. properties/123 or 123")
METRICS_FLAG = arg("--metrics", default="activeUsers",
                   help="comma-separated GA4 metric names")
DIMENSIONS_FLAG = arg("--dimensions",
                      help="comma-separated GA4 dimension names")


def register(subparsers) -> None:
    register_service(subparsers, "analytics",
                     "Google Analytics 4: properties and reports", [
        Cmd("properties", cmd_properties, "list GA4 properties"),
        Cmd("report", cmd_report, "run a GA4 report over a date range",
            (PROPERTY_ARG,
             arg("--from", dest="from", metavar="DATE", required=True,
                 help="start date, YYYY-MM-DD (or e.g. 28daysAgo)"),
             arg("--to", metavar="DATE", required=True,
                 help="end date, YYYY-MM-DD (or e.g. today)"),
             METRICS_FLAG, DIMENSIONS_FLAG, max_flag(25))),
        Cmd("realtime", cmd_realtime, "run a GA4 realtime report",
            (PROPERTY_ARG, METRICS_FLAG, DIMENSIONS_FLAG, max_flag(25))),
    ])
