"""Output-shaping root flags: --fields and --csv."""
import json

import pytest

from gsuite.errors import CLIError
from gsuite.output import emit, emit_obj

ROWS = [{"id": "1", "name": "alpha", "type": "system"},
        {"id": "22", "name": "b, with comma", "type": "user"}]
COLUMNS = [("ID", "id"), ("NAME", "name"), ("TYPE", "type")]


class Args:
    """Stand-in for the parsed root namespace."""

    def __init__(self, json_mode=False, csv_mode=False, fields=None):
        self.json = json_mode
        self.csv = csv_mode
        self.fields = fields


# -- --fields ----------------------------------------------------------------

def test_fields_keeps_only_named_columns_in_requested_order(capsys):
    emit(Args(fields="name,id"), ROWS, COLUMNS)
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0].split() == ["NAME", "ID"]
    assert "system" not in out
    assert lines[1].startswith("alpha")
    assert lines[1].rstrip().endswith("1")


def test_fields_matching_is_case_insensitive(capsys):
    emit(Args(fields="ID"), ROWS, COLUMNS)
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].strip() == "ID"
    assert lines[1].strip() == "1"


def test_unknown_field_raises_and_lists_valid_headers():
    with pytest.raises(CLIError) as exc:
        emit(Args(fields="id,nope"), ROWS, COLUMNS)
    message = str(exc.value)
    assert "nope" in message
    for header in ("ID", "NAME", "TYPE"):
        assert header in message


def test_fields_with_json_restricts_dicts_by_lowercased_header(capsys):
    emit(Args(json_mode=True, fields="name,id"), ROWS, COLUMNS)
    out = json.loads(capsys.readouterr().out)
    assert out == [{"name": "alpha", "id": "1"},
                   {"name": "b, with comma", "id": "22"}]


def test_fields_json_uses_callable_getters(capsys):
    emit(Args(json_mode=True, fields="deep"),
         [{"a": {"b": "value"}}], [("DEEP", lambda r: r["a"]["b"])])
    assert json.loads(capsys.readouterr().out) == [{"deep": "value"}]


def test_emit_obj_honors_fields(capsys):
    emit_obj(Args(fields="name"), {"id": "1", "name": "alpha"},
             [("ID", "id"), ("NAME", "name")])
    assert capsys.readouterr().out == "NAME: alpha\n"


# -- --csv -------------------------------------------------------------------

def test_csv_writes_header_row_and_quotes_commas(capsys):
    emit(Args(csv_mode=True), ROWS, COLUMNS)
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == "ID,NAME,TYPE"
    assert lines[2] == '22,"b, with comma",user'
    assert out.startswith("ID,NAME,TYPE\r\n")  # RFC 4180 line endings


def test_csv_composes_with_fields(capsys):
    emit(Args(csv_mode=True, fields="type,id"), ROWS, COLUMNS)
    assert capsys.readouterr().out.splitlines() == ["TYPE,ID", "system,1",
                                                    "user,22"]


# -- CLI wiring --------------------------------------------------------------

@pytest.fixture
def gmail_labels(authed, fake_transport, run_cli):
    fake_transport.add("GET", "labels", {"labels": [
        {"id": "L1", "name": "INBOX", "type": "system"},
        {"id": "L2", "name": "todo", "type": "user"}]})
    return run_cli


def test_cli_fields_journey_through_a_real_command(gmail_labels):
    out = gmail_labels("--fields", "name,id", "gmail", "labels", "list")
    lines = out.splitlines()
    assert lines[0].split() == ["NAME", "ID"]
    assert "system" not in out
    assert "INBOX" in out and "L1" in out


def test_cli_csv_journey_through_a_real_command(gmail_labels):
    out = gmail_labels("--csv", "gmail", "labels", "list")
    assert out.splitlines()[0] == "ID,NAME,TYPE"


def test_cli_unknown_field_exits_1(gmail_labels, capsys):
    gmail_labels("--fields", "nope", "gmail", "labels", "list", expect=1)


def test_cli_json_and_csv_are_mutually_exclusive(authed, fake_transport,
                                                 run_cli):
    # fake_transport has no routes: reaching the network would blow up, so
    # the clean exit 1 also proves the check runs before any request.
    run_cli("--json", "--csv", "gmail", "labels", "list", expect=1)
    assert fake_transport.calls == []


def test_root_flags_are_global(capsys):
    from gsuite.cli import build_parser

    args = build_parser().parse_args(["--fields", "a,b", "--csv", "--debug",
                                      "gmail", "labels", "list"])
    assert args.fields == "a,b"
    assert args.csv is True
    assert args.debug is True
