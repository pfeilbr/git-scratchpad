import os

import pytest

from gsuite.cli import SERVICE_MODULES, main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED_SERVICES = ["auth", "gmail", "calendar", "drive", "docs", "sheets",
                     "slides", "contacts", "tasks", "chat", "keep", "admin",
                     "api"]


def test_all_expected_services_registered():
    assert SERVICE_MODULES == EXPECTED_SERVICES


def test_root_help_lists_every_service(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    for service in EXPECTED_SERVICES:
        assert service in out


@pytest.mark.parametrize("service", EXPECTED_SERVICES)
def test_service_help_renders(service, capsys):
    with pytest.raises(SystemExit) as exc:
        main([service, "--help"])
    assert exc.value.code == 0


@pytest.mark.parametrize("service", EXPECTED_SERVICES)
def test_bare_service_prints_usage(service, capsys):
    assert main([service]) == 2


def test_readme_documents_every_service():
    readme = open(os.path.join(ROOT, "README.md")).read()
    assert "gsuite" in readme
    assert "## Commands" in readme
    for service in EXPECTED_SERVICES:
        assert f"gsuite {service}" in readme, f"README missing: gsuite {service}"
    assert "verify.py" in readme  # the red-green workflow is documented
