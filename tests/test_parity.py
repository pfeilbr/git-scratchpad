"""Command-surface parity with the two upstream tools, as a checked fact.

The project's stated purpose is to combine the command surfaces of Google's
`gws` and steipete's `gog`. Until now that claim lived only in the README's
prose, where it could neither be audited nor kept honest: nothing failed when
the gap widened, and nobody could say how wide it was.

These pin the gate that measures it. The upstream lists are fetched, not
recalled — `scripts/parity.py --refresh` writes them with the source URL, the
fetch date and a digest, so a reader can re-derive every row.
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARITY = os.path.join(ROOT, "parity")
UPSTREAM = os.path.join(PARITY, "upstream.tsv")
MAPPING = os.path.join(PARITY, "mapping.tsv")
BASELINE = os.path.join(PARITY, "baseline.json")


def _run(*args):
    return subprocess.run([sys.executable, os.path.join(ROOT, "scripts",
                                                        "parity.py"), *args],
                          cwd=ROOT, capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": ROOT})


def _rows(path):
    with open(path) as fh:
        return [ln.rstrip("\n").split("\t") for ln in fh
                if ln.strip() and not ln.startswith("#")]


def _header(path):
    with open(path) as fh:
        return [ln for ln in fh if ln.startswith("#")]


# -- the data is evidence, not recollection ----------------------------------

def test_every_upstream_list_records_where_it_came_from():
    """A parity claim is worthless if its source cannot be re-derived.

    Without a URL, a date and a digest, the manifest is indistinguishable
    from a list somebody typed from memory — which would make the gate
    certify parity against an invented surface.
    """
    header = "".join(_header(UPSTREAM))
    tools = {row[0] for row in _rows(UPSTREAM)}
    assert tools, "no upstream commands recorded at all"
    for tool in tools:
        assert f"\t{tool}\t" in header, f"{tool} has no source line"
    assert "https://" in header
    assert "sha256:" in header


def test_upstream_lists_cover_both_tools():
    tools = {row[0] for row in _rows(UPSTREAM)}
    assert tools == {"gog", "gws"}, f"expected both upstream tools, got {tools}"


# -- our judgments have to be defensible -------------------------------------

def test_every_exclusion_states_a_reason():
    """A gate you can silence with a bare line is a gate that erodes."""
    for row in _rows(MAPPING):
        tool, command, status, value = row
        if status == "excluded":
            assert len(value.split()) >= 3, \
                f"{tool} {command}: exclusion needs a real reason, got {value!r}"


def test_every_alias_points_at_a_command_that_exists():
    """A stale alias silently inflates coverage."""
    import argparse

    from gsuite.cli import build_parser

    def leaves(parser, prefix=()):
        sub = next((a for a in parser._actions
                    if isinstance(a, argparse._SubParsersAction)), None)
        if sub is None:
            yield " ".join(prefix)
            return
        for name, child in sub.choices.items():
            yield from leaves(child, prefix + (name,))

    ours = set(leaves(build_parser()))
    for tool, command, status, value in _rows(MAPPING):
        if status == "alias":
            assert value in ours, \
                f"{tool} {command} is mapped to `gsuite {value}`, which does not exist"


def test_mapping_has_no_duplicate_rows():
    seen = [(r[0], r[1]) for r in _rows(MAPPING)]
    assert len(seen) == len(set(seen)), "an upstream command is mapped twice"


def test_every_mapped_command_is_actually_upstream():
    """Mapping a command the upstream tool does not have hides a typo."""
    upstream = {(r[0], r[1]) for r in _rows(UPSTREAM)}
    for tool, command, _status, _value in _rows(MAPPING):
        assert (tool, command) in upstream, \
            f"{tool} {command} is mapped but is not in upstream.tsv"


# -- the gate itself ---------------------------------------------------------

def test_the_gate_passes_on_the_current_tree():
    result = _run("--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PARITY OK" in result.stdout


def test_the_baseline_records_coverage_per_tool():
    baseline = json.load(open(BASELINE))
    assert set(baseline) == {"gog", "gws"}
    for tool, counts in baseline.items():
        assert counts["covered"] > 0, f"{tool} baseline claims zero coverage"


def test_the_ratchet_catches_a_command_going_missing(tmp_path):
    """Coverage must never silently regress.

    This is the property the whole gate rests on, so it is proved rather
    than assumed: drop the baseline's own numbers one command higher than
    the tree can satisfy, and `--check` has to fail.
    """
    baseline = json.load(open(BASELINE))
    inflated = {t: {**c, "covered": c["covered"] + 1} for t, c in baseline.items()}
    backup = open(BASELINE).read()
    try:
        with open(BASELINE, "w") as fh:
            json.dump(inflated, fh, indent=2)
        result = _run("--check")
        assert result.returncode == 1, \
            "the ratchet accepted coverage below the recorded baseline"
        assert "PARITY REGRESSED" in result.stdout
    finally:
        with open(BASELINE, "w") as fh:
            fh.write(backup)


def test_parity_is_wired_into_ci():
    workflow = open(os.path.join(ROOT, ".github", "workflows", "ci.yml")).read()
    assert "parity.py" in workflow


def test_refresh_is_not_run_by_ci():
    """CI must stay offline and deterministic; refreshing is a manual act."""
    workflow = open(os.path.join(ROOT, ".github", "workflows", "ci.yml")).read()
    assert "--refresh" not in workflow


# -- the number reaches the reader -------------------------------------------

def test_readme_states_the_measured_coverage():
    """The prose claim is replaced by a generated, checkable number."""
    readme = open(os.path.join(ROOT, "README.md")).read()
    assert "<!-- BEGIN GENERATED PARITY -->" in readme
    assert "<!-- END GENERATED PARITY -->" in readme
    result = _run("--check")
    assert "README is out of date" not in result.stdout


def test_an_alias_whose_target_is_gone_does_not_still_count_as_covered():
    """Deleting a command must move the number, even if an alias names it.

    `measure()` treated any row marked `alias` as covered without checking
    that the target still exists, so removing `drive mv` would leave
    `gog drive move` counted — the ratchet would sit green through exactly
    the regression it exists to catch. A test suite assertion is not enough:
    the gate itself has to be the thing that cannot be fooled, because CI
    runs the gate.
    """
    import scripts.parity as parity

    real = parity.our_commands

    def without_drive_mv():
        return real() - {"drive mv"}

    try:
        parity.our_commands = without_drive_mv
        report = parity.measure()
    finally:
        parity.our_commands = real

    assert "drive move" not in report["gog"]["covered"], \
        "a stale alias kept counting after its target was deleted"
    assert "drive move" in report["gog"]["broken"], \
        "a mapping pointing at a command that no longer exists must be reported"


def test_check_does_not_modify_the_working_tree():
    """A gate that edits the repo it is auditing is not a gate.

    `--check` shared its README-drift detection with the code that *writes*
    the README, so running it left the file rewritten. In CI that turns a
    read-only verification step into an uncommitted diff; locally it means
    checking twice gives two different answers, because the first run fixed
    what the second was meant to catch.
    """
    path = os.path.join(ROOT, "README.md")
    before = open(path).read()
    # Drift has to be present for this to test anything: with the block
    # already current, the writer short-circuits and any implementation
    # looks read-only.
    stale = before.replace("<!-- BEGIN GENERATED PARITY -->\n",
                           "<!-- BEGIN GENERATED PARITY -->\nstale row\n", 1)
    assert stale != before, "could not make the README stale"
    try:
        with open(path, "w") as fh:
            fh.write(stale)
        result = _run("--check")
        assert open(path).read() == stale, \
            "--check rewrote the file it was asked to inspect"
        assert result.returncode == 1
        assert "README is out of date" in result.stdout
    finally:
        with open(path, "w") as fh:
            fh.write(before)
