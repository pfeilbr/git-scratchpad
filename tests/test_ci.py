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
