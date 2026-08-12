import argparse

import pytest

from gsuite.api import quote_id
from gsuite.cmdreg import Cmd, Group, arg, max_flag, register_service
from gsuite.output import confirm
from gsuite.services._common import emit_paged


def _root(entries):
    root = argparse.ArgumentParser(prog="gsuite")
    sub = root.add_subparsers(dest="command")
    register_service(sub, "svc", "a test service", entries)
    return root


def _noop(args):
    return 0


def test_cmdreg_registers_command_and_dispatch_func():
    def handler(args):
        return 0

    root = _root([Cmd("do", handler, "do it", (arg("target"),))])
    args = root.parse_args(["svc", "do", "thing"])
    assert args.func is handler
    assert args.target == "thing"


def test_cmdreg_flag_kwargs_and_max_factory():
    root = _root([Cmd("list", _noop, args=(max_flag(42),
                                           arg("--all", action="store_true")))])
    args = root.parse_args(["svc", "list"])
    assert args.max == 42
    assert args.all is False


def test_cmdreg_nested_group():
    root = _root([Group("labels", "manage labels",
                        (Cmd("list", _noop), Cmd("create", _noop,
                                                 args=(arg("name"),))))])
    args = root.parse_args(["svc", "labels", "create", "todo"])
    assert args.func is _noop
    assert args.name == "todo"


def test_cmdreg_bare_service_has_no_func():
    root = _root([Cmd("do", _noop)])
    args = root.parse_args(["svc"])
    assert getattr(args, "func", None) is None


def test_confirm_joins_and_skips_empty(capsys):
    confirm("created", "", "id1", None, "title")
    assert capsys.readouterr().out == "created id1 title\n"


def test_quote_id_escapes_reserved_chars():
    assert quote_id("a@b/c") == "a%40b%2Fc"


def test_emit_paged_lists_and_prints(authed, fake_transport, capsys):
    fake_transport.add("GET", "/v1/items", {"items": [{"id": "1"}],
                                            "nextPageToken": "p2"})
    fake_transport.add("GET", "pageToken=p2", {"items": [{"id": "2"}]})
    ns = argparse.Namespace(account=None, json=False)
    emit_paged(ns, "https://e.googleapis.com/v1/items", [("ID", "id")])
    out = capsys.readouterr().out
    assert "1" in out and "2" in out
