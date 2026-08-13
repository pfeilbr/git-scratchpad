"""The real artifact, not the faked one.

Every other test drives main() in-process with a fake transport. These pin
the things only a real process can prove: that the CLI behaves like a UNIX
filter, that the package metadata installs a working entry point, and that
the end-to-end smoke script is wired into CI.
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel)) as fh:
        return fh.read()


def _run(shell_cmd, env=None):
    return subprocess.run(shell_cmd, shell=True, cwd=ROOT, capture_output=True,
                          text=True,
                          env={**os.environ, "PYTHONPATH": ROOT, **(env or {})})


@pytest.mark.parametrize("command", [
    # `completion zsh` writes its whole payload in one large print, so the
    # write itself faults when the reader goes away — the case that actually
    # raised BrokenPipeError. `bash` and `--help` write less than the 64KB
    # pipe buffer, so they only fault at exit-flush; keep them as guards
    # against a regression in either path.
    "completion zsh | head -1",
    "completion bash | head -1",
    "--help | head -2",
])
def test_closed_pipe_does_not_traceback(command):
    """`gsuite … | head` must exit quietly, like every other UNIX tool."""
    result = _run(f"{sys.executable} -m gsuite.cli {command}")
    assert "BrokenPipeError" not in result.stderr, result.stderr
    assert "Traceback" not in result.stderr, result.stderr


def test_missing_credentials_is_an_error_not_a_traceback(tmp_path):
    env_cfg = tmp_path / "empty-config"
    result = _run(f"{sys.executable} -m gsuite.cli gmail search is:unread",
                  env={"GSUITE_CONFIG_DIR": str(env_cfg),
                       "GSUITE_ACCESS_TOKEN": "", "HOME": str(tmp_path)})
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "auth login" in result.stderr


def test_packaging_declares_the_entry_point_and_subpackages():
    pyproject = _read("pyproject.toml")
    assert 'gsuite = "gsuite.cli:entrypoint"' in pyproject
    assert 'include = ["gsuite*"]' in pyproject  # picks up gsuite.services


def test_smoke_script_exists_and_is_wired_into_ci():
    assert os.path.exists(os.path.join(ROOT, "scripts", "smoke.py"))
    assert "smoke.py" in _read(".github/workflows/ci.yml")
