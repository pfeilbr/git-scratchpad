"""`gsuite completion` — shell completion scripts generated from the parser tree."""
import pytest


@pytest.fixture
def bash_script(run_cli):
    return run_cli("completion", "bash")


def _lookup_line(script: str, path: str) -> str:
    """The single line holding the completion words for a command path.

    Works for either a case-statement or associative-array lookup: the line
    is the one containing the exact quoted path (both quotes included, so
    "gsuite gmail" does not match the "gsuite gmail labels" entry).
    """
    lines = [l for l in script.splitlines() if f'"{path}"' in l]
    assert lines, f"no completion entry for path {path!r}"
    assert len(lines) == 1, f"ambiguous entries for {path!r}: {lines}"
    return lines[0]


def _tokens(line: str) -> set[str]:
    return set(line.replace('"', " ").replace(")", " ").split())


def test_bash_ends_with_complete_registration(bash_script):
    lines = [l for l in bash_script.splitlines() if l.strip()]
    assert lines[-1] == "complete -F _gsuite gsuite"
    assert "_gsuite()" in bash_script


def test_bash_offers_top_level_services(bash_script):
    tokens = _tokens(_lookup_line(bash_script, "gsuite"))
    for service in ("gmail", "calendar", "api", "completion"):
        assert service in tokens, f"root level missing service {service!r}"


def test_bash_offers_nested_subcommands(bash_script):
    gmail = _tokens(_lookup_line(bash_script, "gsuite gmail"))
    for word in ("search", "labels", "drafts"):
        assert word in gmail, f"'gsuite gmail' level missing {word!r}"
    labels = _tokens(_lookup_line(bash_script, "gsuite gmail labels"))
    for word in ("apply", "remove"):
        assert word in labels, f"'gsuite gmail labels' level missing {word!r}"


def test_bash_offers_root_option_strings(bash_script):
    tokens = _tokens(_lookup_line(bash_script, "gsuite"))
    assert "--account" in tokens
    assert "--json" in tokens


def test_bash_output_is_deterministic(run_cli):
    assert run_cli("completion", "bash") == run_cli("completion", "bash")


def test_zsh_is_bash_payload_behind_bashcompinit_shim(run_cli, bash_script):
    zsh = run_cli("completion", "zsh")
    assert zsh.startswith("autoload -U +X bashcompinit && bashcompinit\n")
    assert bash_script in zsh
    assert "complete -F _gsuite gsuite" in zsh
