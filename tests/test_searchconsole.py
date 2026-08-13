import json

import pytest


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


def test_searchconsole_sites(svc):
    ft, run = svc
    ft.add("GET", "webmasters/v3/sites", {"siteEntry": [
        {"siteUrl": "https://example.com/", "permissionLevel": "siteOwner"},
        {"siteUrl": "sc-domain:example.org", "permissionLevel": "siteFullUser"},
    ]})
    out = run("searchconsole", "sites")
    assert ft.calls[0]["url"] == (
        "https://searchconsole.googleapis.com/webmasters/v3/sites")
    assert ft.calls[0]["method"] == "GET"
    # plain GET: this endpoint has no pageToken, so exactly one request
    assert len(ft.calls) == 1
    header = out.splitlines()[0]
    assert "SITE" in header and "PERMISSION" in header
    assert "https://example.com/" in out and "siteOwner" in out
    assert "sc-domain:example.org" in out and "siteFullUser" in out


def test_searchconsole_query_with_dimensions(svc):
    ft, run = svc
    ft.add("POST", "searchAnalytics/query", {"rows": [
        {"keys": ["query-a", "USA"], "clicks": 12, "impressions": 340,
         "ctr": 0.035, "position": 4.2},
    ]})
    out = run("searchconsole", "query", "https://example.com/",
              "--from", "2026-01-01", "--to", "2026-01-31",
              "--dimensions", "query,country", "--max", "5")
    assert ft.calls[0]["url"] == (
        "https://searchconsole.googleapis.com/webmasters/v3/sites/"
        "https%3A%2F%2Fexample.com%2F/searchAnalytics/query")
    assert json.loads(ft.calls[0]["data"]) == {
        "startDate": "2026-01-01", "endDate": "2026-01-31", "rowLimit": 5,
        "dimensions": ["query", "country"],
    }
    header = out.splitlines()[0]
    for col in ("KEYS", "CLICKS", "IMPRESSIONS", "CTR", "POSITION"):
        assert col in header
    assert "query-a,USA" in out
    assert "12" in out and "340" in out and "0.035" in out and "4.2" in out


def test_searchconsole_query_defaults_omit_dimensions(svc):
    ft, run = svc
    ft.add("POST", "searchAnalytics/query", {"rows": [
        {"clicks": 3, "impressions": 90, "ctr": 0.033, "position": 9.1},
    ]})
    out = run("searchconsole", "query", "https://example.com/",
              "--from", "2026-02-01", "--to", "2026-02-02")
    body = json.loads(ft.calls[0]["data"])
    assert "dimensions" not in body
    assert body["rowLimit"] == 25  # --max default
    # no keys in the row -> empty KEYS cell, remaining columns still render
    row = out.splitlines()[1]
    assert row.split()[0] == "3"
    assert "90" in row and "9.1" in row


def test_searchconsole_inspect(svc):
    ft, run = svc
    ft.add("POST", "v1/urlInspection/index:inspect", {"inspectionResult": {
        "indexStatusResult": {
            "verdict": "PASS",
            "coverageState": "Submitted and indexed",
            "lastCrawlTime": "2026-01-05T10:00:00Z",
            "robotsTxtState": "ALLOWED",
        }}})
    out = run("searchconsole", "inspect", "https://example.com/",
              "https://example.com/page")
    assert ft.calls[0]["url"] == (
        "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect")
    assert json.loads(ft.calls[0]["data"]) == {
        "siteUrl": "https://example.com/",
        "inspectionUrl": "https://example.com/page",
    }
    assert "verdict: PASS" in out
    assert "coverage: Submitted and indexed" in out
    assert "lastCrawl: 2026-01-05T10:00:00Z" in out
    assert "robots: ALLOWED" in out


def test_searchconsole_scopes_registered():
    from gsuite.oauth import SERVICE_SCOPES

    assert SERVICE_SCOPES["searchconsole"] == [
        "https://www.googleapis.com/auth/webmasters.readonly",
    ]
