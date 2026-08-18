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


# -- display width -----------------------------------------------------------

# The tests' own yardstick, deliberately independent of gsuite.output: the
# terminal cell count of every character used below, written out by hand, so
# the alignment assertions are about how the table renders rather than about
# how emit() happens to measure it.
TWO_CELLS = set("会議の事録日本語\uff21\U0001f35c")  # CJK, fullwidth A, emoji
NO_CELLS = {"\u0301", "\u200b"}  # combining acute, zero-width space


def cells(text):
    """Terminal cells `text` occupies, by hand-checked character."""
    return sum(0 if ch in NO_CELLS else 2 if ch in TWO_CELLS else 1
               for ch in text)


def owner_offsets(out, rows):
    """Display cells preceding the OWNER column, on the header and each row."""
    values = ["OWNER"] + [row["owner"] for row in rows]
    return {cells(line[:line.index(value)])
            for line, value in zip(out.splitlines(), values)}


WIDE_COLUMNS = [("NAME", "name"), ("OWNER", "owner")]
WIDE_ROWS = [{"name": "Quarterly report", "owner": "ann@x.com"},
             {"name": "会議の議事録", "owner": "kenji@x.com"},
             {"name": "日本語", "owner": "yui@x.com"}]
EMOJI_ROWS = [{"name": "Lunch \U0001f35c plans", "owner": "ann@x.com"},
              {"name": "Quarterly report", "owner": "bo@x.com"}]
# "Cafe" + U+0301: fourteen code points, but only thirteen terminal cells.
COMBINING_ROWS = [{"name": "Cafe\u0301 receipts", "owner": "ann@x.com"},
                  {"name": "Diner receipts", "owner": "bob@x.com"}]


def test_display_width_counts_terminal_cells_not_code_points():
    from gsuite.output import display_width

    assert display_width("") == 0
    assert display_width("abc") == 3
    assert display_width("会") == 2  # East Asian Wide
    assert display_width("\uff21") == 2  # fullwidth latin A
    assert display_width("e\u0301") == 1  # e + combining acute
    assert display_width("\U0001f35c") == 2  # emoji
    assert display_width("a\u200bb") == 2  # zero-width space


def test_cjk_rows_start_the_next_column_at_the_same_offset(capsys):
    emit(Args(), WIDE_ROWS, WIDE_COLUMNS)
    offsets = owner_offsets(capsys.readouterr().out, WIDE_ROWS)
    assert len(offsets) == 1, f"OWNER starts at cells {sorted(offsets)}"


def test_emoji_rows_start_the_next_column_at_the_same_offset(capsys):
    emit(Args(), EMOJI_ROWS, WIDE_COLUMNS)
    offsets = owner_offsets(capsys.readouterr().out, EMOJI_ROWS)
    assert len(offsets) == 1, f"OWNER starts at cells {sorted(offsets)}"


def test_a_combining_mark_row_is_not_padded_short(capsys):
    emit(Args(), COMBINING_ROWS, WIDE_COLUMNS)
    out = capsys.readouterr().out
    assert len(owner_offsets(out, COMBINING_ROWS)) == 1
    # The accented row holds one more code point than it draws cells, so
    # padding it by len() leaves it a cell shy of its plain-ASCII neighbour
    # (the two owners are the same width, so the whole lines must match).
    accented, plain = out.splitlines()[1:3]
    assert cells(accented) == cells(plain)


# -- regression pins ---------------------------------------------------------

WIDE_JSON = ('[\n'
             '  {\n'
             '    "name": "Quarterly report",\n'
             '    "owner": "ann@x.com"\n'
             '  },\n'
             '  {\n'
             '    "name": "\\u4f1a\\u8b70\\u306e\\u8b70\\u4e8b\\u9332",\n'
             '    "owner": "kenji@x.com"\n'
             '  },\n'
             '  {\n'
             '    "name": "\\u65e5\\u672c\\u8a9e",\n'
             '    "owner": "yui@x.com"\n'
             '  }\n'
             ']\n')


def test_wide_characters_leave_csv_and_json_bytes_untouched(capsys):
    """Padding is a table-only concern: the machine shapes never pad."""
    emit(Args(csv_mode=True), WIDE_ROWS, WIDE_COLUMNS)
    assert capsys.readouterr().out == (
        "NAME,OWNER\r\n"
        "Quarterly report,ann@x.com\r\n"
        "会議の議事録,kenji@x.com\r\n"
        "日本語,yui@x.com\r\n")
    emit(Args(json_mode=True), WIDE_ROWS, WIDE_COLUMNS)
    assert capsys.readouterr().out == WIDE_JSON


def test_pure_ascii_table_is_byte_identical(capsys):
    """A table of one-cell characters lays out exactly as it always has."""
    emit(Args(), ROWS, COLUMNS)
    assert capsys.readouterr().out == ("ID  NAME           TYPE\n"
                                       "1   alpha          system\n"
                                       "22  b, with comma  user\n")
