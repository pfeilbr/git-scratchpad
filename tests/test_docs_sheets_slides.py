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


# -- docs replace -------------------------------------------------------------

def test_docs_replace_builds_request_and_reports_occurrences(gsvc):
    ft, run = gsvc
    ft.add("POST", "documents/doc1:batchUpdate", {
        "replies": [{"replaceAllText": {"occurrencesChanged": 3}}]})
    out = run("docs", "replace", "doc1", "--find", "old", "--with", "new")
    rat = json.loads(ft.calls[0]["data"])["requests"][0]["replaceAllText"]
    assert rat["containsText"] == {"text": "old", "matchCase": False}
    assert rat["replaceText"] == "new"
    assert "3" in out and "occurrence" in out and "doc1" in out


def test_docs_replace_match_case_flag(gsvc):
    ft, run = gsvc
    ft.add("POST", "documents/doc1:batchUpdate", {"replies": [{}]})
    run("docs", "replace", "doc1", "--find", "Old", "--with", "New",
        "--match-case")
    rat = json.loads(ft.calls[0]["data"])["requests"][0]["replaceAllText"]
    assert rat["containsText"]["matchCase"] is True


# -- slides cat / add ---------------------------------------------------------

def test_slides_cat_prints_headers_and_text(gsvc):
    ft, run = gsvc
    ft.add("GET", "presentations/pres1", {
        "presentationId": "pres1",
        "slides": [
            {"pageElements": [
                {"shape": {"text": {"textElements": [
                    {"textRun": {"content": "Hello title\n"}},
                    {"paragraphMarker": {}},
                ]}}},
                {"line": {}},
            ]},
            {"pageElements": [
                {"shape": {"text": {"textElements": [
                    {"textRun": {"content": "Second slide body\n"}},
                ]}}},
            ]},
        ],
    })
    out = run("slides", "cat", "pres1")
    assert "-- slide 1 --" in out and "-- slide 2 --" in out
    assert (out.index("-- slide 1 --") < out.index("Hello title")
            < out.index("-- slide 2 --") < out.index("Second slide body"))


def test_slides_add_maps_placeholders_to_inserted_text(gsvc):
    ft, run = gsvc
    ft.add("POST", "presentations/pres1:batchUpdate", {})
    run("slides", "add", "pres1", "--title", "T", "--body", "B")
    reqs = json.loads(ft.calls[0]["data"])["requests"]
    create = reqs[0]["createSlide"]
    assert create["slideLayoutReference"] == {
        "predefinedLayout": "TITLE_AND_BODY"}
    ids = {m["layoutPlaceholder"]["type"]: m["objectId"]
           for m in create["placeholderIdMappings"]}
    assert set(ids) == {"TITLE", "BODY"} and ids["TITLE"] != ids["BODY"]
    inserts = {r["insertText"]["text"]: r["insertText"]["objectId"]
               for r in reqs[1:]}
    assert inserts == {"T": ids["TITLE"], "B": ids["BODY"]}


def test_slides_add_omits_body_insert_when_no_body(gsvc):
    ft, run = gsvc
    ft.add("POST", "presentations/pres1:batchUpdate", {})
    out = run("slides", "add", "pres1", "--title", "Only title")
    reqs = json.loads(ft.calls[0]["data"])["requests"]
    assert len(reqs) == 2
    assert reqs[1]["insertText"]["text"] == "Only title"
    assert "added slide to pres1" in out
