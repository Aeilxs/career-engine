#!/usr/bin/env python3
"""Validate a Conventional Commit subject or PR title with stdlib only."""

import argparse
import re
from pathlib import Path

TYPES = "feat|fix|docs|test|refactor|perf|build|ci|chore|style|revert"
PATTERN = re.compile(rf"^({TYPES})(\([a-z0-9][a-z0-9._/-]*\))?!?: [a-zA-Z0-9].+\S$")


def valid(subject: str) -> bool:
    return bool(PATTERN.fullmatch(subject)) and len(subject) <= 100


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?", help="commit message file")
    parser.add_argument("--text", help="PR title / message subject")
    args = parser.parse_args()
    if args.text is None and args.path is None:
        parser.error("provide --text or commit message path")
    subject = args.text if args.text is not None else args.path.read_text().splitlines()[0]
    if valid(subject):
        print(f"Valid Conventional Commit: {subject}")
        return 0
    print(f"Invalid Conventional Commit: {subject}\nExpected e.g. feat(offers): normalize imports")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
