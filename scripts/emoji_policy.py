#!/usr/bin/env python3
"""Repo-wide emoji policy enforcement.

Policy:
- No emojis anywhere in repository text files.
- We detect emojis via Unicode properties (Extended_Pictographic + Regional_Indicator)
  and also forbid emoji joiners/variation selectors (ZWJ, VS15, VS16).

This script avoids printing emoji characters in its output.

Usage:
  python scripts/emoji_policy.py check
  python scripts/emoji_policy.py apply

Exit codes:
  0: clean
  2: violations found (check mode)
  1: unexpected error
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import regex


VIOLATION_RE = regex.compile(r"[\p{Extended_Pictographic}\p{Regional_Indicator}\u200d\ufe0e\ufe0f]")


EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    ".venv_clean",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}


ALLOWED_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".sh",
    ".bat",
    ".csv",
}


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    col: int
    char: str

    @property
    def codepoint(self) -> str:
        return f"U+{ord(self.char):04X}"

    @property
    def name(self) -> str:
        return unicodedata.name(self.char, "UNKNOWN")


def is_excluded_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def is_candidate_file(path: Path) -> bool:
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return False
    if is_excluded_path(path):
        return False
    return True


def iter_repo_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if not is_candidate_file(path):
            continue
        paths.append(path)
    return paths


def find_violations_in_text(text: str, path: Path) -> list[Violation]:
    violations: list[Violation] = []
    for match in VIOLATION_RE.finditer(text):
        idx = match.start()
        line = text.count("\n", 0, idx) + 1
        last_newline = text.rfind("\n", 0, idx)
        col = idx + 1 if last_newline == -1 else (idx - last_newline)
        violations.append(Violation(path=path, line=line, col=col, char=match.group(0)))
    return violations


def read_text_utf8(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def write_text_utf8(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def strip_violations(text: str) -> str:
    return VIOLATION_RE.sub("", text)


def cmd_check(root: Path, max_report: int) -> int:
    all_violations: list[Violation] = []

    for path in iter_repo_files(root):
        text = read_text_utf8(path)
        if text is None:
            continue
        all_violations.extend(find_violations_in_text(text, path))

    if not all_violations:
        print("OK: no emoji violations found")
        return 0

    print(f"FAIL: found {len(all_violations)} emoji violations")
    for v in all_violations[:max_report]:
        rel = v.path.relative_to(root)
        print(f"  {rel}:{v.line}:{v.col} {v.codepoint} {v.name}")

    if len(all_violations) > max_report:
        print(f"  ... and {len(all_violations) - max_report} more")

    return 2


def cmd_apply(root: Path) -> int:
    changed_files = 0
    removed_chars_total = 0

    for path in iter_repo_files(root):
        text = read_text_utf8(path)
        if text is None:
            continue

        matches = list(VIOLATION_RE.finditer(text))
        if not matches:
            continue

        cleaned = strip_violations(text)
        if cleaned == text:
            continue

        removed_chars_total += (len(text) - len(cleaned))
        write_text_utf8(path, cleaned)
        changed_files += 1

    print(f"APPLIED: updated {changed_files} files; removed {removed_chars_total} characters")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enforce repo no-emoji policy")
    parser.add_argument("mode", choices={"check", "apply"})
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root directory (default: repo root)",
    )
    parser.add_argument(
        "--max-report",
        type=int,
        default=50,
        help="Max violations to print (check mode)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()

    if args.mode == "check":
        return cmd_check(root=root, max_report=args.max_report)

    if args.mode == "apply":
        return cmd_apply(root=root)

    raise AssertionError(f"Unhandled mode: {args.mode}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
