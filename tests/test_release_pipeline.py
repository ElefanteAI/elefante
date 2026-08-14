# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_release_pipeline.py
# PROVES  : GitHub release publication logic stays local-testable: release notes
#           render from CHANGELOG, oversize assets are filtered before publish,
#           and the workflow calls the maintained scripts instead of inline code.
# RUN     : pytest tests/test_release_pipeline.py -v
# WHEN    : After changes to .github/workflows/build-binaries.yml or scripts/ci/*
# ─────────────────────────────────────────────────────────────────────────────
"""Tests for release publication helpers and workflow guards."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

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
    assert "[User Documentation](docs/README.md)" in notes
    assert "workspace/" not in notes


def test_release_documentation_audit_passes_for_repo_history():
    module = _load_module(ROOT / "scripts/ci/render_release_notes.py", "render_release_notes")

    assert module.audit_changelog() == []


def test_published_release_can_render_public_notes():
    module = _load_module(ROOT / "scripts/ci/render_release_notes.py", "render_published_notes")

    assert "2.12.1" not in module.release_candidate_versions(
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    )
    module.validate_release_documentation("2.12.1")
    assert "## [2.12.1] - 2026-08-04" in module.render_release_notes("2.12.1")


def test_version_sync_tracks_release_identifiers_without_rewriting_history():
    module = _load_module(ROOT / "scripts/ci/bump_version.py", "bump_version")
    targets = {target[0] for target in module.TARGETS}

    assert {
        "src/__init__.py",
        "setup.py",
        "config.yaml",
        "src/dashboard/ui/package.json",
    }.issubset(targets)
    assert "README.md" not in targets
    assert "docs/README.md" not in targets
    assert "docs/explanation/vision.md" not in targets
    assert "workspace/ISSUES.md" not in targets
    assert "workspace/lessons.md" not in targets
    assert not any(path.startswith("workspace/postmortems/") for path in targets)
    assert module.GLOB_TARGETS == []

    source_version = re.search(
        r'__version__\s*=\s*"([^"]+)"',
        (ROOT / "src" / "__init__.py").read_text(encoding="utf-8"),
    ).group(1)
    assert f"v{source_version}" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_version_advisor_accepts_candidate_changelog_entries():
    module = _load_module(
        ROOT / "scripts/ci/advise_version_bump.py", "advise_version_candidate"
    )

    assert module.changelog_has_entry("2.12.2") is True


def test_build_workflow_uses_maintained_release_scripts():
    workflow = (ROOT / ".github/workflows/build-binaries.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert '"scripts/ci/build_release_client.py"' in workflow
    assert '"scripts/ci/resolve_release_publication.py"' in workflow
    assert '"scripts/ci/verify_release_client.py"' in workflow
    assert '"scripts/setup/**"' in workflow
    assert '"scripts/lifecycle/**"' in workflow
    assert '"src/**"' in workflow
    assert "python scripts/ci/build_release_client.py" in workflow
    assert "python scripts/ci/verify_release_client.py" in workflow
    assert "python scripts/ci/resolve_release_publication.py" in workflow
    assert '--ref-type "${GITHUB_REF_TYPE}"' in workflow
    assert '--ref-name "${GITHUB_REF_NAME}"' in workflow
    assert '--publication-status "${{ steps.publication.outputs.status }}"' in workflow
    assert (
        '--expected-publication-status "${{ steps.publication.outputs.status }}"'
        in workflow
    )
    assert "--publication-status release" not in workflow
    assert "requirements.client.lock" in workflow
    assert "python scripts/ci/generate_release_checksums.py" in workflow
    assert "python3 scripts/ci/render_release_notes.py" in workflow
    assert "python3 scripts/ci/select_release_assets.py" in workflow
    assert "python3 scripts/ci/generate_release_checksums.py" in workflow
    assert "body_path: release-notes.md" in workflow
    assert "${{ steps.select_release_assets.outputs.files }}" in workflow
    assert "SHA256SUMS" in workflow
    assert "name: elefante-${{ runner.os }}-installer" in workflow
    assert "name: Download releasable installer artifacts" in workflow
    assert "pattern: elefante-*-installer" in workflow
    assert "merge-multiple: false" in workflow
    assert "name: Download all artifacts" not in workflow
    assert 'ditto -x -k "$installer_archive"' in workflow
    assert '"${bundle_root}/Install Elefante.command"' in workflow
    assert "python3 - <<'PY'" not in workflow


def test_release_publication_requires_the_exact_source_version_tag(tmp_path):
    module = _load_module(
        ROOT / "scripts/ci/resolve_release_publication.py",
        "resolve_release_publication",
    )
    source_root = tmp_path / "source"
    (source_root / "src").mkdir(parents=True)
    (source_root / "src" / "__init__.py").write_text(
        '__version__ = "2.12.2"\n', encoding="utf-8"
    )

    version = module.source_version(source_root)
    assert version == "2.12.2"
    assert (
        module.publication_status(
            ref_type="branch", ref_name="main", version=version
        )
        == "candidate"
    )
    assert (
        module.publication_status(
            ref_type="tag", ref_name="v2.12.2", version=version
        )
        == "release"
    )
    with pytest.raises(ValueError, match="does not match source version"):
        module.publication_status(
            ref_type="tag", ref_name="v2.12.3", version=version
        )


def test_readme_uses_the_verified_macos_customer_launcher():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    release_section = readme.split("**Release bundle (preferred):**", 1)[1].split(
        "If `.venv` already exists", 1
    )[0]

    assert "Install Elefante.command" in release_section
    assert "Control-click" in release_section
    assert "Administrator access and Terminal commands are not required." in release_section
    assert "run the top-level `install.sh` or `install.bat`" not in release_section
    assert "https://github.com/ElefanteAI/elefante.git" in readme


def test_release_checksums_are_deterministic_and_detect_tampering(tmp_path):
    module = _load_module(
        ROOT / "scripts/ci/generate_release_checksums.py",
        "generate_release_checksums",
    )
    alpha = tmp_path / "alpha.zip"
    zeta = tmp_path / "zeta.zip"
    alpha.write_bytes(b"alpha release asset\n")
    zeta.write_bytes(b"zeta release asset\n")
    manifest = tmp_path / "SHA256SUMS"

    module.write_checksums([zeta, alpha], manifest)

    expected = (
        f"{hashlib.sha256(alpha.read_bytes()).hexdigest()}  alpha.zip\n"
        f"{hashlib.sha256(zeta.read_bytes()).hexdigest()}  zeta.zip\n"
    )
    assert manifest.read_bytes() == expected.encode("utf-8")
    assert module.verify_checksums(manifest, [zeta, alpha]) == ["alpha.zip", "zeta.zip"]

    alpha.write_bytes(b"tampered release asset\n")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        module.verify_checksums(manifest, [alpha, zeta])


def test_release_checksums_reject_ambiguous_asset_basenames(tmp_path):
    module = _load_module(
        ROOT / "scripts/ci/generate_release_checksums.py",
        "generate_release_checksums_duplicate_names",
    )
    first = tmp_path / "first" / "elefante.zip"
    second = tmp_path / "second" / "elefante.zip"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    with pytest.raises(ValueError, match="Duplicate release asset basename"):
        module.render_checksums([first, second])


def test_build_workflow_smokes_platform_archives_before_upload():
    workflow = (ROOT / ".github/workflows/build-binaries.yml").read_text(encoding="utf-8")

    unix_smoke = workflow.index("name: Smoke test platform archives (Unix)")
    windows_smoke = workflow.index("name: Smoke test platform archives (Windows)")
    upload = workflow.index("name: Upload Build Artifacts")

    assert unix_smoke < upload
    assert windows_smoke < upload
    assert 'test -x "${bundle_root}/install.sh"' in workflow
    assert 'test -x "${bundle_root}/Install Elefante.command"' in workflow
    assert "Windows launcher contains invalid control bytes" in workflow
    assert "Windows launcher contains a bare LF instead of CRLF" in workflow
    assert "--dry-run" in workflow
    assert "test ! -e \"$dry_run_root\"" in workflow
    assert "Installer bundle dry-run mutated the install path" in workflow
    assert "Developer dependency lock leaked into customer installer" in workflow
    assert "Release Profile: Client (runtime-only payload)" in workflow
    assert "--verify \"$checksum_file\"" in workflow
    assert "--verify $checksumFile" in workflow


def test_quality_workflow_enforces_release_candidate_gates():
    workflow = (ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")

    assert "python scripts/ci/bump_version.py --check" in workflow
    assert "from src import __version__" in workflow
    assert "scripts/ci/render_release_notes.py" in workflow
    assert "python -m pytest tests -m slow -q" in workflow
    assert "python -m ruff check" in workflow
    assert "npm audit --audit-level=high" in workflow
    assert "Production Dependency Audit" in workflow
    assert "pypa/gh-action-pip-audit@" in workflow
    assert "requirements.client.txt" in workflow
    assert "requirements.client.lock" in workflow
    assert "scripts/ci/build_release_client.py" in workflow
    assert "scripts/ci/verify_release_client.py" in workflow
    assert "requirements.client.lock" in workflow
    assert "pypa/gh-action-pip-audit@" in workflow


def test_release_client_candidate_workflow_is_validation_only():
    workflow = (ROOT / ".github/workflows/build-release-client.yml").read_text(
        encoding="utf-8"
    )

    assert '"release/**"' in workflow
    assert "macos-latest" in workflow
    assert "scripts/ci/build_release_client.py" in workflow
    assert "scripts/ci/verify_release_client.py" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "--require-clean-source" in workflow
    assert "--publication-status candidate" in workflow
    assert "--expected-publication-status candidate" in workflow
    assert "name: Prove a fresh macOS customer installation" in workflow
    assert 'ditto -x -k dist/elefante-v2.12.2-rc.1-macOS.zip' in workflow
    assert '"$bundle_root/Install Elefante.command" --venv-mode fresh --verbose' in workflow
    assert '"$install_root/scripts/lifecycle/doctor.py" --json' in workflow
    assert 'report["customer_ready"] is True' in workflow
    assert 'report["installation"]["version"] == "2.12.2"' in workflow
    assert 'report["installation"]["release_channel"] == "candidate"' in workflow
    assert 'report["installation"]["source_commit"] == os.environ["GITHUB_SHA"]' in workflow
    assert 'report["installation"]["source_clean"] is True' in workflow
    assert '"$install_root/scripts/lifecycle/uninstall_elefante.py" --apply' in workflow
    assert "if manifest_path.exists():" in workflow
    assert "softprops/action-gh-release" not in workflow
    assert "candidate-not-for-public-download" not in workflow


def test_release_workflow_publishes_verified_sha256sums():
    workflow = (ROOT / ".github/workflows/build-binaries.yml").read_text(encoding="utf-8")

    select = workflow.index("name: Select releasable assets")
    generate = workflow.index("name: Generate and verify SHA256SUMS")
    upload = workflow.index("name: Upload checksum manifest")
    release = workflow.index("name: Create Release")

    assert select < generate < upload < release
    assert "--output SHA256SUMS" in workflow
    assert "--verify SHA256SUMS" in workflow
    assert "name: elefante-${{ github.ref_name }}-checksums" in workflow
    assert "files: |\n            ${{ steps.select_release_assets.outputs.files }}\n            SHA256SUMS" in workflow


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
    assert "inputs: requirements.client.lock" in workflow
    assert "require-hashes: true" in workflow
    assert "internal-be-careful-extra-flags: --disable-pip" in workflow
    assert "no-deps: true" in workflow


def test_quality_lock_freshness_check_preserves_existing_transitive_pins():
    workflow = (ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")

    copy_requirements = 'cp requirements.txt "$RUNNER_TEMP/elefante-lock-check/requirements.txt"'
    copy_lock = 'cp requirements.lock "$RUNNER_TEMP/elefante-lock-check/requirements.lock"'
    compile_lock = "uv pip compile --universal --generate-hashes --python-version 3.11"
    compare_lock = 'cmp requirements.lock "$RUNNER_TEMP/elefante-lock-check/requirements.lock"'

    assert workflow.index(copy_requirements) < workflow.index(copy_lock)
    assert workflow.index(copy_lock) < workflow.index(compile_lock)
    assert workflow.index(compile_lock) < workflow.index(compare_lock)
