#!/usr/bin/env python3
"""End-to-end smoke test of the real installed artifact.

scripts/verify.py drives main() in-process against a fake transport — fast,
offline, and blind to everything that only breaks in a real process: broken
packaging, a missing entry point, an unimportable service module, a
traceback where an error message belongs.

This script installs the project into a throwaway virtualenv and drives the
`gsuite` console script itself. It makes NO network calls: every command it
runs either prints help, emits a completion script, or fails on missing
credentials.

  python3 scripts/smoke.py            build a venv, run the checks
  python3 scripts/smoke.py --keep     leave the venv behind for poking at

Terse and deterministic, like verify.py: one line per failure, a summary,
exit 0 only if every check passed.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAIL = 20  # diagnostic lines shown for a failing check


class Smoke:
    def __init__(self, binary: str, home: str):
        self.binary = binary
        self.failures: list[str] = []
        self.checks = 0
        # Point config and HOME at the sandbox so a developer's real
        # ~/.config/gsuite and ADC file can never influence the result.
        self.env = {
            **os.environ,
            "HOME": home,
            "GSUITE_CONFIG_DIR": os.path.join(home, "config"),
            "GOOGLE_APPLICATION_CREDENTIALS": os.path.join(home, "no-adc.json"),
        }
        self.env.pop("GSUITE_ACCESS_TOKEN", None)

    def run(self, args: str, shell: bool = False):
        cmd = f"{self.binary} {args}" if shell else [self.binary, *args.split()]
        return subprocess.run(cmd, shell=shell, capture_output=True, text=True,
                              env=self.env)

    def check(self, label: str, ok: bool, detail: str = "") -> bool:
        self.checks += 1
        if not ok:
            self.failures.append(label)
            print(f"FAIL {label}")
            if detail:
                print("\n".join(f"     {l}"
                                for l in detail.strip().splitlines()[-TAIL:]))
        return ok

    def expect_clean(self, label: str, args: str, code: int | None = 0,
                     expect_in_output: str = "", shell: bool = False):
        """Run a command; require the exit code and no traceback anywhere."""
        result = self.run(args, shell=shell)
        blob = result.stdout + result.stderr
        ok = "Traceback" not in blob and "BrokenPipeError" not in blob
        if code is not None:
            ok = ok and result.returncode == code
        if expect_in_output:
            ok = ok and expect_in_output in blob
        return self.check(label, ok,
                          f"exit={result.returncode}\n{blob}" if not ok else "")


def build_venv(workdir: str) -> str:
    venv = os.path.join(workdir, "venv")
    subprocess.run([sys.executable, "-m", "venv", venv], check=True,
                   capture_output=True)
    pip = os.path.join(venv, "bin", "pip")
    install = subprocess.run([pip, "install", "--quiet", ROOT],
                             capture_output=True, text=True)
    if install.returncode != 0:
        print("FAIL pip install .")
        print(install.stdout + install.stderr)
        raise SystemExit(1)
    return os.path.join(venv, "bin", "gsuite")


def services(binary: str, env: dict) -> list[str]:
    """Ask the installed CLI itself which services it registers."""
    code = "import gsuite.cli as c; print(' '.join(c.SERVICE_MODULES))"
    python = os.path.join(os.path.dirname(binary), "python")
    out = subprocess.run([python, "-c", code], capture_output=True, text=True,
                         env=env)
    return out.stdout.split()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", action="store_true",
                    help="keep the throwaway virtualenv")
    opts = ap.parse_args()

    workdir = tempfile.mkdtemp(prefix="gsuite-smoke-")
    home = os.path.join(workdir, "home")
    os.makedirs(home, exist_ok=True)
    try:
        binary = build_venv(workdir)
        s = Smoke(binary, home)

        # The entry point exists and reports the packaged version.
        s.expect_clean("entry point runs (--version)", "--version",
                       expect_in_output="gsuite ")
        s.expect_clean("root help", "--help", expect_in_output="<service>")

        # Every registered service imports and renders help for real.
        names = services(binary, s.env)
        s.check("service list is non-empty", bool(names))
        for name in names:
            s.expect_clean(f"{name} --help", f"{name} --help")

        # A bare service prints usage and exits 2 (argparse convention).
        if names:
            s.expect_clean("bare service exits 2", names[-1], code=2)

        # Missing credentials must be a message, never a traceback.
        s.expect_clean("no credentials -> error, not traceback",
                       "gmail search is:unread", code=1,
                       expect_in_output="auth login")
        s.expect_clean("auth doctor reports problems", "auth doctor", code=1,
                       expect_in_output="FAIL")

        # Behaves like a UNIX filter when a reader closes the pipe. `zsh`
        # emits its payload in one large write, so it faults during the
        # write rather than at exit-flush — the case that actually broke.
        for piped in ("completion zsh | head -1", "completion bash | head -1",
                      "--help | head -2"):
            s.expect_clean(f"{piped}", piped, code=None, shell=True)

        # The emitted completion script is valid shell.
        if shutil.which("bash"):
            script = s.run("completion bash").stdout
            syntax = subprocess.run(["bash", "-n"], input=script, text=True,
                                    capture_output=True)
            s.check("completion bash passes `bash -n`", syntax.returncode == 0,
                    syntax.stderr)

        if s.failures:
            print(f"SMOKE FAIL: {len(s.failures)}/{s.checks} checks failed")
            return 1
        print(f"SMOKE OK: {s.checks} checks passed")
        return 0
    finally:
        if opts.keep:
            print(f"venv kept at {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
