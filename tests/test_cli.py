import pytest

from gsuite import __version__
from gsuite.cli import main


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_args_prints_help_and_exits_2(capsys):
    assert main([]) == 2
    assert "usage: gsuite" in capsys.readouterr().err


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "gsuite" in capsys.readouterr().out


def test_unknown_command_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["not-a-service"])
    assert exc.value.code == 2
