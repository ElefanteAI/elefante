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
import tarfile
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
    assert "[Installation Guide](docs/how-to/install.md)" in notes


def test_release_documentation_audit_passes_for_repo_history():
    module = _load_module(ROOT / "scripts/ci/render_release_notes.py", "render_release_notes")

    assert module.audit_changelog() == []


def test_version_sync_tracks_release_identifiers_without_rewriting_history():
    module = _load_module(ROOT / "scripts/ci/bump_version.py", "bump_version")
    targets = {target[0] for target in module.TARGETS}

    assert {
        "src/__init__.py",
        "setup.py",
        "config.yaml",
        "src/dashboard/ui/package.json",
        "README.md",
        "docs/README.md",
        "docs/explanation/vision.md",
    }.issubset(targets)
    assert "workspace/ISSUES.md" not in targets
    assert "workspace/lessons.md" not in targets
    assert not any(path.startswith("workspace/postmortems/") for path in targets)
    assert module.GLOB_TARGETS == []


def test_build_workflow_uses_maintained_release_scripts():
    workflow = (ROOT / ".github/workflows/build-binaries.yml").read_text(encoding="utf-8")

    assert "python scripts/ci/build_installer_bundle.py" in workflow
    assert "python3 scripts/ci/render_release_notes.py" in workflow
    assert "python3 scripts/ci/select_release_assets.py" in workflow
    assert "body_path: release-notes.md" in workflow
    assert "files: ${{ steps.select_release_assets.outputs.files }}" in workflow
    assert "name: elefante-${{ runner.os }}-installer" in workflow
    assert "python3 - <<'PY'" not in workflow


def test_docker_bundle_uses_live_docs_and_hash_locked_dependencies(tmp_path):
    output_dir = tmp_path / "bundle-output"
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/ci/bundle_docker_package.sh")],
        cwd=ROOT,
        env={**os.environ, "ELEFANTE_BUNDLE_OUTPUT_DIR": str(output_dir)},
        capture_output=True,
        text=True,
        check=False,
    )

    archive_path = output_dir / "elefante-docker-bundle.tar.gz"
    assert result.returncode == 0, result.stderr
    assert archive_path.is_file()
    with tarfile.open(archive_path, "r:gz") as archive:
        names = set(archive.getnames())
    assert {"requirements.txt", "requirements.lock"}.issubset(names)
    assert "docs/how-to/agent-handoff.md" in names
    assert "docs/how-to/docker.md" in names
    assert not any(name.startswith("docs/technical/") for name in names)


def test_tagged_release_cannot_bypass_the_hash_locked_dependency_audit():
    workflow = (ROOT / ".github/workflows/build-binaries.yml").read_text(encoding="utf-8")

    assert "dependency-audit:" in workflow
    assert "needs: [build, dependency-audit]" in workflow
    assert "pypa/gh-action-pip-audit@1220774d901786e6f652ae159f7b6bc8fea6d266" in workflow
    assert "inputs: requirements.lock" in workflow
    assert "require-hashes: true" in workflow
    assert "disable-pip: true" in workflow
    assert "no-deps: true" in workflow
