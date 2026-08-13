import json

import pytest


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


REPORT = {
    "dimensionHeaders": [{"name": "country"}, {"name": "deviceCategory"}],
    "metricHeaders": [{"name": "activeUsers"}, {"name": "sessions"}],
    "rows": [
        {"dimensionValues": [{"value": "United States"}, {"value": "mobile"}],
         "metricValues": [{"value": "412"}, {"value": "530"}]},
        {"dimensionValues": [{"value": "Germany"}, {"value": "desktop"}],
         "metricValues": [{"value": "97"}, {"value": "118"}]},
    ],
}


def test_analytics_properties_flattens_summaries(svc):
    ft, run = svc
    ft.add("GET", "analyticsadmin.googleapis.com/v1beta/accountSummaries", {
        "accountSummaries": [
            {"account": "accounts/11", "propertySummaries": [
                {"property": "properties/1", "displayName": "Marketing site"},
                {"property": "properties/2", "displayName": "Blog"},
            ]},
            {"account": "accounts/22", "propertySummaries": [
                {"property": "properties/3", "displayName": "Docs"},
            ]},
        ]})
    out = run("analytics", "properties")
    assert ft.calls[0]["url"] == (
        "https://analyticsadmin.googleapis.com/v1beta/accountSummaries")
    header = out.splitlines()[0]
    assert "PROPERTY" in header and "NAME" in header and "ACCOUNT" in header
    assert len(out.splitlines()) == 4  # header + one row per property summary
    assert "properties/2  Blog" in out
    assert "properties/3" in out and "Docs" in out and "accounts/22" in out
    assert "accounts/11" in out


def test_analytics_report_normalizes_bare_property_id(svc):
    ft, run = svc
    ft.add("POST", "properties/123:runReport", REPORT)
    run("analytics", "report", "123", "--from", "2026-01-01",
        "--to", "2026-01-31")
    assert ft.calls[0]["url"] == (
        "https://analyticsdata.googleapis.com/v1beta/properties/123:runReport")
    assert json.loads(ft.calls[0]["data"]) == {
        "dateRanges": [{"startDate": "2026-01-01", "endDate": "2026-01-31"}],
        "metrics": [{"name": "activeUsers"}],
        "limit": 25,
    }
    # an already-qualified name is not double-prefixed
    ft.add("POST", "properties/123:runReport", REPORT)
    run("analytics", "report", "properties/123", "--from", "2026-01-01",
        "--to", "2026-01-31")
    assert ft.calls[1]["url"].endswith("/v1beta/properties/123:runReport")


def test_analytics_report_body_and_dynamic_columns(svc):
    ft, run = svc
    ft.add("POST", "properties/9:runReport", REPORT)
    out = run("analytics", "report", "properties/9",
              "--from", "2026-01-01", "--to", "2026-01-31",
              "--metrics", "activeUsers,sessions",
              "--dimensions", "country,deviceCategory", "--max", "10")
    assert json.loads(ft.calls[0]["data"]) == {
        "dateRanges": [{"startDate": "2026-01-01", "endDate": "2026-01-31"}],
        "metrics": [{"name": "activeUsers"}, {"name": "sessions"}],
        "dimensions": [{"name": "country"}, {"name": "deviceCategory"}],
        "limit": 10,
    }
    # columns come from the response headers, in dimension-then-metric order
    header = out.splitlines()[0].split()
    assert header == ["COUNTRY", "DEVICECATEGORY", "ACTIVEUSERS", "SESSIONS"]
    assert "United States  mobile" in out
    assert "412" in out and "530" in out
    assert out.splitlines()[2].split()[0] == "Germany"
    assert "97" in out and "118" in out


def test_analytics_report_columns_track_requested_metrics(svc):
    ft, run = svc
    ft.add("POST", "properties/9:runReport", {
        "dimensionHeaders": [],
        "metricHeaders": [{"name": "screenPageViews"}],
        "rows": [{"metricValues": [{"value": "7788"}]}],
    })
    out = run("analytics", "report", "9", "--from", "2026-03-01",
              "--to", "2026-03-31", "--metrics", "screenPageViews")
    assert json.loads(ft.calls[0]["data"])["metrics"] == [
        {"name": "screenPageViews"}]
    assert out.splitlines()[0].split() == ["SCREENPAGEVIEWS"]
    assert "COUNTRY" not in out
    assert "7788" in out


def test_analytics_realtime_omits_date_ranges(svc):
    ft, run = svc
    ft.add("POST", "properties/9:runRealtimeReport", {
        "dimensionHeaders": [{"name": "country"}],
        "metricHeaders": [{"name": "activeUsers"}],
        "rows": [{"dimensionValues": [{"value": "Japan"}],
                  "metricValues": [{"value": "5"}]}],
    })
    out = run("analytics", "realtime", "9", "--dimensions", "country",
              "--max", "3")
    assert ft.calls[0]["url"] == (
        "https://analyticsdata.googleapis.com/v1beta/"
        "properties/9:runRealtimeReport")
    assert json.loads(ft.calls[0]["data"]) == {
        "metrics": [{"name": "activeUsers"}],
        "dimensions": [{"name": "country"}],
        "limit": 3,
    }
    assert out.splitlines()[0].split() == ["COUNTRY", "ACTIVEUSERS"]
    assert "Japan" in out and "5" in out


def test_analytics_scopes_registered():
    from gsuite.oauth import SERVICE_SCOPES

    assert SERVICE_SCOPES["analytics"] == [
        "https://www.googleapis.com/auth/analytics.readonly",
    ]
