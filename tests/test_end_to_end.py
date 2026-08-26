#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_end_to_end.py
# PROVES  : Convenience entrypoint that delegates to verify_e2e_tests.py for
#           backward compatibility with docs that referenced this original path.
# RUN     : pytest tests/test_end_to_end.py -v  OR  python tests/test_end_to_end.py
# WHEN    : Use verify_e2e_tests.py directly for new invocations. This file exists
#           only for compatibility; do not add new logic here.
# ─────────────────────────────────────────────────────────────────────────────
"""Convenience entrypoint for the manual end-to-end test.

Docs and deploy scripts historically referenced `scripts/test_end_to_end.py`.
The canonical script currently lives at `tests/manual/test_end_to_end.py`.

Usage:
  python scripts/test_end_to_end.py
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    target = repo_root / "tests" / "manual" / "test_end_to_end.py"
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
