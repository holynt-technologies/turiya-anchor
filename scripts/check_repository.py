#!/usr/bin/env python3
"""Check that this repository contains only what it should.

Patterns are read from the `FORBIDDEN_PATTERNS` environment variable, one regular expression
per line, so the set can be changed without a commit here. Without it the script scans for
nothing and exits 1 rather than reporting a pass, because a check that cannot see what it is
checking must not report success.

It runs on every push and every pull request, from `.github/workflows/checks.yml`, so the
result does not depend on anything running on a particular machine.

    FORBIDDEN_PATTERNS="..." python3 scripts/check_repository.py
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

#: Not scanned: git's internals and the workflow directory. The workflow names this file by
#: its full path, so scanning that directory would report the reference to this file.
SKIP_DIRS = {".git", ".github"}
SKIP_FILES = {"scripts/check_repository.py"}

TEXT_SUFFIXES = {".md", ".txt", ".json", ".py", ".yml", ".yaml", ".cff", ".pem", ""}

#: Lines matching these are skipped. Manifest entries record the receipt tree's own paths,
#: and those paths are already public.
ALLOW = [
    r'"path": "receipts/',
]

NAME = "check-repository"


def main() -> int:
    root = pathlib.Path(".").resolve()
    raw = os.environ.get("FORBIDDEN_PATTERNS", "").strip()

    if not raw:
        print(f"{NAME}: FORBIDDEN_PATTERNS is empty, so nothing was searched for.",
              file=sys.stderr)
        print("                 Refusing to report a pass on a check that checked nothing.",
              file=sys.stderr)
        return 1

    patterns = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append((line, re.compile(line)))
        except re.error as e:
            print(f"{NAME}: bad pattern {line!r}: {e}", file=sys.stderr)
            return 1

    if not patterns:
        print(f"{NAME}: no usable patterns. Not reporting a pass.", file=sys.stderr)
        return 1

    files = [
        p for p in sorted(root.rglob("*"))
        if p.is_file()
        and p.suffix in TEXT_SUFFIXES
        and not (SKIP_DIRS & set(p.parts))
        and str(p.relative_to(root)) not in SKIP_FILES
    ]

    allow = [re.compile(rx) for rx in ALLOW]
    findings = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"{NAME}: cannot read {f}: {e}", file=sys.stderr)
            return 1
        for n, line in enumerate(text.splitlines(), 1):
            if any(a.search(line) for a in allow):
                continue
            for label, rx in patterns:
                if rx.search(line):
                    findings.append((f.relative_to(root), n, line.strip()[:110]))
                    break

    if findings:
        print(f"{NAME}: {len(findings)} finding(s).\n", file=sys.stderr)
        for path, n, snippet in findings:
            print(f"  {path}:{n}\n      {snippet}", file=sys.stderr)
        return 1

    print(f"{NAME}: {len(files)} file(s) scanned against {len(patterns)} pattern(s), clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
