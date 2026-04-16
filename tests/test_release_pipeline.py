# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_release_pipeline.py
# VERSION : 2.7.1
# CHANGED : 2026-04-15
# PROVES  : GitHub release publication logic stays local-testable: release notes
#           render from CHANGELOG, oversize assets are filtered before publish,
#           and the workflow calls the maintained scripts instead of inline code.
# RUN     : pytest tests/test_release_pipeline.py -v
# WHEN    : After changes to .github/workflows/build-binaries.yml or scripts/ci/*
# ─────────────────────────────────────────────────────────────────────────────
"""Tests for release publication helpers and workflow guards."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_select_release_assets_filters_oversized_and_missing(tmp_path):
    module = _load_module(ROOT / "scripts/ci/select_release_assets.py", "select_release_assets")

    small = tmp_path / "elefante-macOS.zip"
    large = tmp_path / "elefante-Linux.zip"
    missing = tmp_path / "elefante-Windows.zip"
    small.write_bytes(b"ok")
    large.write_bytes(b"0123456789")

    release_files, skipped = module.select_release_assets(
        [small, large, missing],
        max_release_bytes=5,
    )

    assert release_files == [str(small)]
    assert any(item == f"MISSING {missing}" for item in skipped)
    assert any("exceeds GitHub release asset limit" in item and str(large) in item for item in skipped)


def test_select_release_assets_cli_writes_outputs(tmp_path):
    small = tmp_path / "elefante-macOS.zip"
    large = tmp_path / "elefante-Linux.zip"
    small.write_bytes(b"ok")
    large.write_bytes(b"0123456789")

    github_output = tmp_path / "github_output.txt"
    step_summary = tmp_path / "step_summary.md"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/ci/select_release_assets.py"),
            "--candidate",
            str(small),
            "--candidate",
            str(large),
            "--max-bytes",
            "5",
        ],
        cwd=str(ROOT),
        env={
            **os.environ,
            "GITHUB_OUTPUT": str(github_output),
            "GITHUB_STEP_SUMMARY": str(step_summary),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "UPLOAD" in result.stdout
    assert "SKIP" in result.stdout
    assert str(small) in github_output.read_text(encoding="utf-8")
    summary = step_summary.read_text(encoding="utf-8")
    assert "## Release asset selection" in summary
    assert str(small) in summary
    assert str(large) in summary


def test_select_release_assets_defaults_include_installer_bundles():
    module = _load_module(ROOT / "scripts/ci/select_release_assets.py", "select_release_assets_defaults")

    defaults = {str(path) for path in module.DEFAULT_CANDIDATES}

    assert "artifacts/elefante-Linux-installer/elefante-installer-Linux.zip" in defaults
    assert "artifacts/elefante-macOS-installer/elefante-installer-macOS.zip" in defaults
    assert "artifacts/elefante-Windows-installer/elefante-installer-Windows.zip" in defaults


def test_render_release_notes_uses_matching_changelog_entry():
    module = _load_module(ROOT / "scripts/ci/render_release_notes.py", "render_release_notes")

    notes = module.render_release_notes("2.7.1")

    assert notes.startswith("# Elefante v2.7.1")
    assert "## [2.7.1] - 2026-04-15" in notes
    assert "BUG-015" in notes
    assert "[Installation Guide](docs/technical/ops-installation.md)" in notes


def test_release_documentation_audit_passes_for_repo_history():
    module = _load_module(ROOT / "scripts/ci/render_release_notes.py", "render_release_notes")

    assert module.audit_changelog() == []


def test_build_workflow_uses_maintained_release_scripts():
    workflow = (ROOT / ".github/workflows/build-binaries.yml").read_text(encoding="utf-8")

    assert "python scripts/ci/build_installer_bundle.py" in workflow
    assert "python3 scripts/ci/render_release_notes.py" in workflow
    assert "python3 scripts/ci/select_release_assets.py" in workflow
    assert "body_path: release-notes.md" in workflow
    assert "files: ${{ steps.select_release_assets.outputs.files }}" in workflow
    assert "name: elefante-${{ runner.os }}-installer" in workflow
    assert "python3 - <<'PY'" not in workflow