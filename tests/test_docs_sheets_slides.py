import json

import pytest


@pytest.fixture
def gsvc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


# -- docs ---------------------------------------------------------------------

def test_docs_create(gsvc):
    ft, run = gsvc
    ft.add("POST", "docs.googleapis.com/v1/documents", {"documentId": "doc1",
                                                        "title": "My Doc"})
    out = run("docs", "create", "--title", "My Doc")
    assert "doc1" in out
    assert json.loads(ft.calls[0]["data"]) == {"title": "My Doc"}


def test_docs_cat_extracts_text(gsvc):
    ft, run = gsvc
    ft.add("GET", "documents/doc1", {
        "documentId": "doc1", "title": "T",
        "body": {"content": [
            {"paragraph": {"elements": [{"textRun": {"content": "line one\n"}}]}},
            {"sectionBreak": {}},
            {"paragraph": {"elements": [{"textRun": {"content": "line two\n"}}]}},
        ]},
    })
    out = run("docs", "cat", "doc1")
    assert "line one" in out and "line two" in out


def test_docs_append_inserts_at_end(gsvc):
    ft, run = gsvc
    ft.add("POST", "documents/doc1:batchUpdate", {})
    run("docs", "append", "doc1", "--text", "added")
    body = json.loads(ft.calls[0]["data"])
    insert = body["requests"][0]["insertText"]
    assert insert["text"] == "added"
    assert "endOfSegmentLocation" in insert


# -- sheets ---------------------------------------------------------------------

def test_sheets_create(gsvc):
    ft, run = gsvc
    ft.add("POST", "sheets.googleapis.com/v4/spreadsheets",
           {"spreadsheetId": "ss1"})
    out = run("sheets", "create", "--title", "Budget")
    assert "ss1" in out
    assert json.loads(ft.calls[0]["data"]) == {"properties": {"title": "Budget"}}


def test_sheets_read_prints_rows(gsvc):
    ft, run = gsvc
    ft.add("GET", "values/Sheet1%21A1%3AB2", {"values": [["h1", "h2"],
                                                         ["v1", "v2"]]})
    out = run("sheets", "read", "ss1", "Sheet1!A1:B2")
    assert "h1\th2" in out and "v1\tv2" in out


def test_sheets_append_parses_rows(gsvc):
    ft, run = gsvc
    ft.add("POST", ":append", {"updates": {"updatedRows": 2}})
    run("sheets", "append", "ss1", "A1", "--values", "a,b;c,d")
    assert "valueInputOption=USER_ENTERED" in ft.calls[0]["url"]
    assert json.loads(ft.calls[0]["data"])["values"] == [["a", "b"], ["c", "d"]]


def test_sheets_update(gsvc):
    ft, run = gsvc
    ft.add("PUT", "values/A1", {"updatedCells": 1})
    run("sheets", "update", "ss1", "A1", "--values", "x")
    assert json.loads(ft.calls[0]["data"])["values"] == [["x"]]


def test_sheets_clear(gsvc):
    ft, run = gsvc
    ft.add("POST", ":clear", {})
    run("sheets", "clear", "ss1", "A1:B2")


# -- slides ---------------------------------------------------------------------

def test_slides_create(gsvc):
    ft, run = gsvc
    ft.add("POST", "slides.googleapis.com/v1/presentations",
           {"presentationId": "pres1"})
    out = run("slides", "create", "--title", "Deck")
    assert "pres1" in out


def test_slides_info_counts_slides(gsvc):
    ft, run = gsvc
    ft.add("GET", "presentations/pres1", {
        "presentationId": "pres1", "title": "Deck",
        "slides": [{"objectId": "s1"}, {"objectId": "s2"}],
    })
    out = run("slides", "info", "pres1")
    assert "Deck" in out and "2" in out
