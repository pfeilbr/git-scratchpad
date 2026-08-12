"""The documentation set is generated and gated: stale docs fail the build."""
import os
import subprocess
import sys

import pytest

from gsuite.cli import SERVICE_MODULES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAND_WRITTEN = ["docs/index.md", "docs/architecture.md", "docs/development.md",
                "docs/guides/authentication.md", "docs/guides/scripting.md"]


def _read(rel):
    with open(os.path.join(ROOT, rel)) as fh:
        return fh.read()


def test_reference_docs_are_in_sync_with_parsers():
    result = subprocess.run(
        [sys.executable, "scripts/gen_docs.py", "--check"],
        cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_service_has_reference_page_with_usage_and_examples():
    for service in SERVICE_MODULES:
        page = _read(f"docs/reference/{service}.md")
        assert f"# gsuite {service}" in page
        assert "usage:" in page
        assert "## Examples" in page, f"{service} reference page has no examples"


def test_reference_index_links_every_service():
    index = _read("docs/reference/index.md")
    for service in SERVICE_MODULES:
        assert f"{service}.md" in index


def test_mkdocs_nav_covers_all_pages():
    nav = _read("mkdocs.yml")
    for service in SERVICE_MODULES:
        assert f"reference/{service}.md" in nav
    for page in HAND_WRITTEN:
        assert page.removeprefix("docs/") in nav


def test_hand_written_pages_exist():
    for page in HAND_WRITTEN:
        assert os.path.exists(os.path.join(ROOT, page)), f"missing {page}"


def test_architecture_page_has_mermaid_visuals():
    page = _read("docs/architecture.md")
    assert page.count("```mermaid") >= 3
    assert "flowchart" in page
    assert "sequenceDiagram" in page


def test_verify_gate_includes_docs_sync():
    assert "gen_docs" in _read("scripts/verify.py")


def test_readme_links_documentation():
    assert "docs/" in _read("README.md")
