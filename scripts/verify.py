#!/usr/bin/env python3
"""Deterministic red-green verification runner.

Runs the full quality gate with terse, stable output so repeated runs are
cheap to read (token-frugal for humans and agents alike).

  python3 scripts/verify.py         expect GREEN -> exit 0 iff everything passes
  python3 scripts/verify.py --red   expect RED   -> exit 0 iff the suite FAILS
                                    (run before implementing, to prove the new
                                    tests actually test something)

Gate = byte-compile all sources + full pytest suite.
Determinism: fixed hash seed, no cache plugins, no bytecode writes.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAIL_LINES = 40  # max diagnostic lines shown on an unexpected outcome


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--red", action="store_true", help="expect the suite to fail")
    opts = ap.parse_args()

    comp = run([sys.executable, "-m", "compileall", "-q", "gsuite", "tests", "scripts"])
    if comp.returncode != 0 and not opts.red:
        print("COMPILE FAIL")
        print("\n".join((comp.stdout + comp.stderr).splitlines()[-TAIL_LINES:]))
        return 1

    # -q comes from addopts in pyproject.toml; adding it again would make
    # pytest -qq and suppress the one-line summary this script depends on.
    test = run([sys.executable, "-m", "pytest", "--tb=line", "tests"])
    out = (test.stdout + test.stderr).splitlines()
    summary = next(
        (l for l in reversed(out)
         if re.search(r"(passed|failed|error|no tests ran)", l)),
        "no summary",
    )
    failed = test.returncode != 0 or comp.returncode != 0

    if opts.red:
        if failed:
            print(f"RED OK: {summary.strip()}")
            return 0
        print(f"RED EXPECTED BUT SUITE IS GREEN: {summary.strip()}")
        return 1
    if failed:
        print(f"FAIL: {summary.strip()}")
        print("\n".join(out[-TAIL_LINES:]))
        return 1
    print(f"GREEN: {summary.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
