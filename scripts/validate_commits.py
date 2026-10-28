#!/usr/bin/env python3
"""Validate Conventional Commit headers used by this repository."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ALLOWED_TYPES = (
    "feat",
    "fix",
    "refactor",
    "perf",
    "style",
    "test",
    "docs",
    "build",
    "ops",
    "chore",
)
HEADER_PATTERN = re.compile(
    rf"^(?P<type>{'|'.join(ALLOWED_TYPES)})"
    r"(?:\((?P<scope>[a-z0-9][a-z0-9-]{0,19})\))?: "
    r"(?P<description>.+)$"
)
MERGE_PATTERN = re.compile(r"^Merge (?:branch|remote-tracking branch|pull request) ")
REVERT_PATTERN = re.compile(r'^Revert ".+"$')
MAX_HEADER_LENGTH = 100


def validate_header(header: str) -> list[str]:
    if not header:
        return ["Commit header is empty."]
    if len(header) > MAX_HEADER_LENGTH:
        return [f"Commit header must be at most {MAX_HEADER_LENGTH} characters."]
    if MERGE_PATTERN.match(header) or REVERT_PATTERN.match(header):
        return []

    match = HEADER_PATTERN.match(header)
    if match is None:
        return [
            "Commit header must match '<type>(<optional-scope>): <description>' "
            f"with one of: {', '.join(ALLOWED_TYPES)}."
        ]

    description = match.group("description")
    errors = []
    if len(description) > MAX_HEADER_LENGTH:
        errors.append("Commit description must be at most 100 characters.")
    if not description[0].islower() and not description[0].isdigit():
        errors.append("Commit description must start with a lowercase letter or digit.")
    if description.endswith("."):
        errors.append("Commit description must not end with a period.")
    return errors


def _git_log(range_spec: str) -> list[tuple[str, str]]:
    if "0000000" in range_spec:
        range_spec = "HEAD"
    result = subprocess.run(
        ["git", "log", "--format=%H%x1f%s%x1e", range_spec],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git log failed")
    commits = []
    for record in result.stdout.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        commit_hash, header = record.split("\x1f", 1)
        commits.append((commit_hash, header))
    return commits


def _validate_message_file(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0] if lines else ""
    errors = validate_header(header)
    if errors:
        for error in errors:
            print(f"commit-msg: {error}", file=sys.stderr)
        return 1
    return 0


def _validate_range(range_spec: str) -> int:
    commits = _git_log(range_spec)
    failures = 0
    for commit_hash, header in commits:
        errors = validate_header(header)
        if errors:
            failures += 1
            print(f"{commit_hash[:12]} {header}", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
    if failures:
        print(f"commit-msg: {failures} invalid commit header(s).", file=sys.stderr)
        return 1
    print(f"commit-msg: validated {len(commits)} commit header(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message-file", type=Path)
    parser.add_argument("--range", dest="range_spec", default="HEAD")
    args = parser.parse_args()

    if args.message_file is not None:
        return _validate_message_file(args.message_file)
    return _validate_range(args.range_spec)


if __name__ == "__main__":
    raise SystemExit(main())
