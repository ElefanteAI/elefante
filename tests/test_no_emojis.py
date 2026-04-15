# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_no_emojis.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PROVES  : No-emoji policy enforcement across strict source/docs surfaces.
#           Mirrors the logic of verify_emoji_policy.py but as a pytest test.
# RUN     : pytest tests/test_no_emojis.py -v
# WHEN    : After adding LLM-generated content (high emoji-injection risk) or
#           new files in docs/ or src/. Part of standard pre-commit suite.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from pathlib import Path
import unicodedata

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
    "archive",  # historical docs, not production
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


def _is_excluded_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def _iter_repo_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_excluded_path(path):
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        paths.append(path)
    return paths


def _read_text_utf8(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def test_repo_contains_no_emojis() -> None:
    root = Path(__file__).resolve().parents[1]
    violations: list[str] = []

    for path in _iter_repo_files(root):
        text = _read_text_utf8(path)
        if text is None:
            continue

        for match in VIOLATION_RE.finditer(text):
            ch = match.group(0)
            idx = match.start()
            line = text.count("\n", 0, idx) + 1
            rel = path.relative_to(root)
            codepoint = f"U+{ord(ch):04X}"
            name = unicodedata.name(ch, "UNKNOWN")
            violations.append(f"{rel}:{line} {codepoint} {name}")
            if len(violations) >= 50:
                break
        if len(violations) >= 50:
            break

    assert not violations, (
        "Emoji violations found (first 50 shown; output omits emoji characters):\n"
        + "\n".join(violations)
    )
