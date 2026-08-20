"""CI must run the exact same deterministic gate as local development."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "ci.yml")


def test_ci_workflow_exists():
    assert os.path.exists(WORKFLOW)


def test_ci_runs_the_verify_gate_on_push():
    text = open(WORKFLOW).read()
    assert "scripts/verify.py" in text  # same gate, not a parallel test config
    assert "push" in text
    assert "actions/setup-python" in text
    assert "pytest" in text  # the only dev dependency gets installed


def test_ci_runs_the_traceback_fuzzer():
    """The gate that generalises six hand-found bugs must not fall out of CI.

    `verify.py` proves the behaviours someone thought to write a test for;
    the fuzzer proves the one property that holds for *every* command — no
    input yields a traceback. It only pays for itself if it runs on push.
    """
    assert os.path.exists(os.path.join(ROOT, "scripts", "fuzz_cli.py"))
    assert "fuzz_cli.py" in open(WORKFLOW).read()
