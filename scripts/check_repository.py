#!/usr/bin/env python3
"""Check that this repository contains only what it should.

Patterns are read from two places, one regular expression per line:

* the committed `scripts/forbidden_patterns.txt`, which is reviewable and testable;
* the `FORBIDDEN_PATTERNS` environment variable, for patterns that must not be published.

The sets are unioned. With neither source the script scans for nothing and exits 1
rather than reporting a pass, because a check that cannot see what it is checking must
not report success.

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
SKIP_FILES = {"scripts/check_repository.py", "scripts/forbidden_patterns.txt"}

#: The committed, auditable pattern list. The environment variable remains for the
#: patterns that must stay private.
PATTERN_FILE = pathlib.Path(__file__).resolve().parent / "forbidden_patterns.txt"

TEXT_SUFFIXES = {".md", ".txt", ".json", ".py", ".yml", ".yaml", ".cff", ".pem", ""}

#: Lines matching these are skipped. Manifest entries record the receipt tree's own paths,
#: and those paths are already public.
ALLOW = [
    r'"path": "receipts/',
]

NAME = "check-repository"


def _patterns_from(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def main() -> int:
    root = pathlib.Path(".").resolve()

    sources = _patterns_from(os.environ.get("FORBIDDEN_PATTERNS", ""))
    try:
        sources += _patterns_from(PATTERN_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"{NAME}: cannot read {PATTERN_FILE}: {e}", file=sys.stderr)
        return 1

    seen = set()
    raw_patterns = []
    for p in sources:
        if p not in seen:
            seen.add(p)
            raw_patterns.append(p)

    if not raw_patterns:
        print(f"{NAME}: no patterns from FORBIDDEN_PATTERNS or {PATTERN_FILE.name},",
              file=sys.stderr)
        print("                 so nothing was searched for. Refusing to report a pass.",
              file=sys.stderr)
        return 1

    patterns = []
    for line in raw_patterns:
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
