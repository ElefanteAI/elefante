# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_installer_bundle.py
# VERSION : 2.9.2
# CHANGED : 2026-04-17
# PROVES  : Installer bundle bootstrap logic keeps Elefante payload placement
#           truthful, excludes local .venv backup directories, and bundle
#           packaging emits the expected bootstrap archive.
# RUN     : pytest tests/test_installer_bundle.py -v
# WHEN    : After changes to scripts/setup/bootstrap_release_bundle.py or
#           scripts/ci/build_installer_bundle.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_minimal_repo(root_dir: Path) -> None:
    required_files = {
        "README.md": "# Elefante\n\n**v9.9.9** — Test Bundle\n",
        "LICENSE": "test license\n",
        "requirements.txt": "pytest\n",
        "requirements.lock": "pytest==7.4.4 --hash=sha256:test\n",
        "config.yaml": "storage: local\n",
        ".github/copilot-instructions.md": "Use Elefante.\n",
        "scripts/setup/install.py": "print('install')\n",
        "scripts/setup/bootstrap_release_bundle.py": "print('bootstrap')\n",
        "scripts/verify/verify_health.py": "print('health')\n",
        "scripts/verify/verify_mcp_handshake.py": "print('handshake')\n",
        "scripts/pipeline/update_dashboard_data.py": "print('dashboard')\n",
        "src/main.py": "print('main')\n",
        "src/dashboard/ui/dist/index.html": "<html></html>\n",
    }
    for relative_path, content in required_files.items():
        file_path = root_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")


def test_default_install_root_prefers_localappdata_on_windows(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_module",
    )

    install_root = module.get_default_install_root(
        os_name="Windows",
        env={"LOCALAPPDATA": str(tmp_path / "LocalAppData")},
        home=tmp_path / "Home",
    )

    assert install_root == tmp_path / "LocalAppData" / "Elefante" / "app" / "current"


def test_place_payload_moves_existing_install_to_backup(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_place_module",
    )

    payload_root = tmp_path / "payload" / "elefante"
    payload_root.mkdir(parents=True, exist_ok=True)
    (payload_root / "README.md").write_text("new payload\n", encoding="utf-8")

    install_root = tmp_path / "stable" / "current"
    install_root.mkdir(parents=True, exist_ok=True)
    (install_root / "README.md").write_text("old payload\n", encoding="utf-8")

    backup_root = module.place_payload(payload_root, install_root)

    assert backup_root is not None
    assert (install_root / "README.md").read_text(encoding="utf-8") == "new payload\n"
    assert (backup_root / "README.md").read_text(encoding="utf-8") == "old payload\n"


def test_build_install_command_targets_installed_payload(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_command_module",
    )

    install_root = tmp_path / "stable" / "current"
    command = module.build_install_command(
        install_root,
        python_executable="/usr/bin/python3",
        venv_mode="reuse",
    )

    assert command[0] == "/usr/bin/python3"
    assert command[1] == str(install_root / "scripts/setup/install.py")
    assert str(install_root / ".elefante-install-status.txt") in command
    assert command[-1] == "reuse"


def test_render_failed_install_guidance_points_to_persisted_files(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_failure_routing_module",
    )

    install_root = tmp_path / "stable" / "current"
    lines = module.render_failed_install_guidance(install_root)

    assert lines[0] == "Delegated installer failed. Read these persisted files in order:"
    assert str(install_root / ".elefante-install-summary.txt") in lines[1]
    assert str(install_root / ".elefante-install-status.txt") in lines[2]
    assert str(install_root / ".elefante-install.log") in lines[3]


def test_build_installer_bundle_writes_manifest_wrappers_and_payload(tmp_path):
    module = _load_module(
        ROOT / "scripts/ci/build_installer_bundle.py",
        "build_installer_bundle_module",
    )

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    _create_minimal_repo(repo_root)

    output_path = tmp_path / "dist" / "elefante-installer-macOS.zip"
    module.build_installer_bundle(repo_root, platform_name="macOS", output_path=output_path)

    assert output_path.exists()

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())

    assert "elefante-installer-macOS/installer-manifest.json" in names
    assert "elefante-installer-macOS/install.sh" in names
    assert "elefante-installer-macOS/install.bat" in names
    assert "elefante-installer-macOS/scripts/setup/bootstrap_release_bundle.py" in names
    assert "elefante-installer-macOS/payload/elefante/scripts/setup/install.py" in names
    assert "elefante-installer-macOS/payload/elefante/requirements.lock" in names
    assert "elefante-installer-macOS/payload/elefante/src/dashboard/ui/dist/index.html" in names


def test_build_installer_bundle_skips_top_level_venv_backups(tmp_path):
    module = _load_module(
        ROOT / "scripts/ci/build_installer_bundle.py",
        "build_installer_bundle_venv_backup_module",
    )

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    _create_minimal_repo(repo_root)

    broken_backup = repo_root / ".venv.broken.20260417-132309" / "bin"
    broken_backup.mkdir(parents=True, exist_ok=True)
    broken_entry = broken_backup / "python3"
    try:
        broken_entry.symlink_to("/missing/python3")
    except OSError:
        broken_entry.write_text("local backup env should never ship\n", encoding="utf-8")

    output_path = tmp_path / "dist" / "elefante-installer-macOS.zip"
    module.build_installer_bundle(repo_root, platform_name="macOS", output_path=output_path)

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())

    assert not any(".venv.broken.20260417-132309" in name for name in names)
