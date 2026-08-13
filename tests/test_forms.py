import json

import pytest


@pytest.fixture
def svc(authed, fake_transport, run_cli):
    return fake_transport, run_cli


FORM = {
    "formId": "f1",
    "info": {"title": "Team survey", "description": "Quarterly pulse"},
    "responderUri": "https://docs.google.com/forms/d/e/abc/viewform",
    "items": [
        {"itemId": "i1", "title": "Your name",
         "questionItem": {"question": {"textQuestion": {}}}},
        {"itemId": "i2", "title": "Rate us",
         "questionItem": {"question": {"scaleQuestion": {"low": 1, "high": 5}}}},
        {"itemId": "i3", "title": "Section header"},
    ],
}


def test_forms_create(svc):
    ft, run = svc
    ft.add("POST", "forms.googleapis.com/v1/forms",
           {"formId": "f1", "info": {"title": "Team survey"}})
    out = run("forms", "create", "--title", "Team survey")
    assert "created f1 Team survey" in out
    call = ft.calls[0]
    assert call["url"].startswith("https://forms.googleapis.com/v1/forms")
    assert json.loads(call["data"]) == {"info": {"title": "Team survey"}}


def test_forms_get(svc):
    ft, run = svc
    ft.add("GET", "v1/forms/f1", FORM)
    out = run("forms", "get", "f1")
    assert "https://forms.googleapis.com/v1/forms/f1" in ft.calls[0]["url"]
    assert "id: f1" in out
    assert "title: Team survey" in out
    assert "description: Quarterly pulse" in out
    assert "url: https://docs.google.com/forms/d/e/abc/viewform" in out
    assert "items: 3" in out


def test_forms_questions(svc):
    ft, run = svc
    ft.add("GET", "v1/forms/f1", FORM)
    out = run("forms", "questions", "f1")
    assert "https://forms.googleapis.com/v1/forms/f1" in ft.calls[0]["url"]
    assert "i1" in out and "Your name" in out and "textQuestion" in out
    assert "i2" in out and "scaleQuestion" in out
    # non-question items show "-" for TYPE
    row = next(l for l in out.splitlines() if l.startswith("i3"))
    assert "-" in row


def test_forms_responses(svc):
    ft, run = svc
    ft.add("GET", "v1/forms/f1/responses", {"responses": [
        {"responseId": "r1", "lastSubmittedTime": "2026-01-05T10:00:00Z"},
        {"responseId": "r2", "lastSubmittedTime": "2026-01-06T11:30:00Z"},
    ]})
    out = run("forms", "responses", "f1")
    assert "https://forms.googleapis.com/v1/forms/f1/responses" in ft.calls[0]["url"]
    assert "r1" in out and "2026-01-05T10:00:00Z" in out
    assert "r2" in out and "2026-01-06T11:30:00Z" in out


def test_forms_responses_max_limits_items(svc):
    ft, run = svc
    ft.add("GET", "v1/forms/f1/responses", {"responses": [
        {"responseId": "r1", "lastSubmittedTime": "2026-01-05T10:00:00Z"},
        {"responseId": "r2", "lastSubmittedTime": "2026-01-06T11:30:00Z"},
    ], "nextPageToken": "npt"})
    out = run("forms", "responses", "f1", "--max", "2")
    # limit reached on the first page: no second request follows the token
    assert len(ft.calls) == 1
    assert "r1" in out and "r2" in out


def test_forms_scopes_registered():
    from gsuite.oauth import SERVICE_SCOPES

    assert SERVICE_SCOPES["forms"] == [
        "https://www.googleapis.com/auth/forms.body",
        "https://www.googleapis.com/auth/forms.responses.readonly",
    ]
