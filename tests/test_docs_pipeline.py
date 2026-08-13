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


# -- the hand-written docs must not drift either -----------------------------

README_BEGIN = "<!-- BEGIN GENERATED COMMAND SUMMARY -->"
README_END = "<!-- END GENERATED COMMAND SUMMARY -->"


def _readme_generated_block():
    readme = _read("README.md")
    assert README_BEGIN in readme and README_END in readme, \
        "README command summary is not a generated block"
    return readme.split(README_BEGIN)[1].split(README_END)[0]


def _command_paths():
    """Every leaf command as (service, path-words) from the live parser."""
    import argparse

    from gsuite.cli import build_parser

    def sub(parser):
        return next((a for a in parser._actions
                     if isinstance(a, argparse._SubParsersAction)), None)

    paths = []
    root = sub(build_parser())
    for service, sp in root.choices.items():
        level = sub(sp)
        for name, cp in level.choices.items():
            nested = sub(cp)
            if nested is None:
                paths.append((service, [name]))
            else:
                for leaf in nested.choices:
                    paths.append((service, [name, leaf]))
    return paths


def test_readme_summary_lists_every_service_and_command():
    block = _readme_generated_block()
    for service, path in _command_paths():
        assert f"`gsuite {service}`" in block or f"gsuite {service}" in block, \
            f"README summary missing service: {service}"
        for word in path:
            assert word in block, \
                f"README summary missing: gsuite {service} {' '.join(path)}"


def test_readme_summary_matches_the_generator():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import gen_docs

    assert gen_docs.render_readme_summary() == _readme_generated_block()


def test_architecture_diagram_covers_every_service():
    page = _read("docs/architecture.md")
    for service in SERVICE_MODULES:
        assert service in page, f"architecture page never mentions: {service}"


def test_index_page_mentions_every_service():
    page = _read("docs/index.md")
    for service in SERVICE_MODULES:
        assert service in page, f"docs/index.md never mentions: {service}"


def test_reference_pages_list_every_global_flag():
    """The generated pages must name the real root flags, not a stale subset."""
    import argparse

    from gsuite.cli import build_parser

    page = _read("docs/reference/gmail.md")
    for action in build_parser()._actions:
        if isinstance(action, (argparse._HelpAction,
                               argparse._VersionAction,
                               argparse._SubParsersAction)):
            continue
        flag = action.option_strings[-1]
        assert flag in page, f"reference pages never mention global flag {flag}"
