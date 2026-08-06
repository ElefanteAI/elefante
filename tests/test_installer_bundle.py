# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_installer_bundle.py
# PROVES  : Installer bundle bootstrap logic keeps Elefante payload placement
#           truthful, excludes local .venv backup directories, and emits clean,
#           platform-specific launchers with executable metadata.
# RUN     : pytest tests/test_installer_bundle.py -v
# WHEN    : After changes to scripts/setup/bootstrap_release_bundle.py or
#           scripts/ci/build_installer_bundle.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import importlib.util
import stat
import sys
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
        hosts=["cursor", "codex"],
    )

    assert command[0] == "/usr/bin/python3"
    assert command[1] == str(install_root / "scripts/setup/install.py")
    assert str(install_root / ".elefante-install-status.txt") in command
    assert command[command.index("--installation-scope") + 1] == "customer"
    assert "--host" not in command


def test_client_bundle_command_selects_the_client_runtime_profile(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_client_profile_module",
    )

    command = module.build_install_command(
        tmp_path / "current",
        python_executable="/usr/bin/python3",
        venv_mode="reuse",
        release_profile="client",
    )

    assert command[-2:] == ["--release-profile", "client"]


def test_client_bundle_layout_requires_the_client_lock(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_client_layout_module",
    )
    bundle_root = tmp_path / "bundle"
    payload_root = bundle_root / "payload" / "elefante"
    (payload_root / "scripts" / "setup").mkdir(parents=True)
    (bundle_root / "scripts" / "setup").mkdir(parents=True)
    (payload_root / "scripts" / "setup" / "install.py").write_text("", encoding="utf-8")
    (payload_root / "requirements.client.txt").write_text("", encoding="utf-8")
    (payload_root / "requirements.client.lock").write_text("", encoding="utf-8")
    (bundle_root / "scripts" / "setup" / "bootstrap_release_bundle.py").write_text(
        "", encoding="utf-8"
    )

    assert module.ensure_bundle_layout(bundle_root, release_profile="client") == payload_root


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


def test_bundle_dry_run_never_places_payload(monkeypatch, tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_dry_run_module",
    )
    bundle_root = tmp_path / "bundle"
    payload_root = bundle_root / "payload" / "elefante"
    (payload_root / "scripts" / "setup").mkdir(parents=True)
    (bundle_root / "scripts" / "setup").mkdir(parents=True)
    (payload_root / "scripts" / "setup" / "install.py").write_text("", encoding="utf-8")
    (payload_root / "requirements.txt").write_text("", encoding="utf-8")
    (payload_root / "requirements.lock").write_text("", encoding="utf-8")
    (bundle_root / "scripts" / "setup" / "bootstrap_release_bundle.py").write_text(
        "",
        encoding="utf-8",
    )
    install_root = tmp_path / "live-install"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bootstrap_release_bundle.py",
            "--bundle-root",
            str(bundle_root),
            "--install-root",
            str(install_root),
            "--dry-run",
        ],
    )
    monkeypatch.setattr(module, "resolve_install_python", lambda _: sys.executable)
    monkeypatch.setattr(
        module,
        "place_payload",
        lambda *_: (_ for _ in ()).throw(AssertionError("dry run placed payload")),
    )

    module.main()

    assert not install_root.exists()


def test_build_installer_bundle_writes_macos_launchers_and_payload(tmp_path):
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
        manifest = archive.read(
            "elefante-installer-macOS/installer-manifest.json"
        ).decode("utf-8")
        start_here = archive.read("elefante-installer-macOS/START HERE.txt").decode(
            "utf-8"
        )
        command_info = archive.getinfo(
            "elefante-installer-macOS/Install Elefante.command"
        )
        shell_info = archive.getinfo("elefante-installer-macOS/install.sh")

    assert "elefante-installer-macOS/installer-manifest.json" in names
    assert "elefante-installer-macOS/START HERE.txt" in names
    assert "elefante-installer-macOS/Install Elefante.command" in names
    assert "elefante-installer-macOS/install.sh" in names
    assert "elefante-installer-macOS/Install Elefante.bat" not in names
    assert "elefante-installer-macOS/scripts/setup/bootstrap_release_bundle.py" in names
    assert "elefante-installer-macOS/payload/elefante/scripts/setup/install.py" in names
    assert "elefante-installer-macOS/payload/elefante/requirements.lock" in names
    assert "elefante-installer-macOS/payload/elefante/src/dashboard/ui/dist/index.html" in names
    assert '"entrypoints": [\n    "Install Elefante.command",\n    "install.sh"\n  ]' in manifest
    assert 'Double-click "Install Elefante.command"' in start_here
    assert "Administrator access and Terminal commands are not required." in start_here
    assert "chmod +x" not in start_here

    command_mode = command_info.external_attr >> 16
    shell_mode = shell_info.external_attr >> 16
    assert stat.S_ISREG(command_mode)
    assert stat.S_IMODE(command_mode) == 0o755
    assert stat.S_ISREG(shell_mode)
    assert stat.S_IMODE(shell_mode) == 0o755
    assert command_info.date_time[0] >= 2026


def test_build_installer_bundle_writes_clean_windows_launcher(tmp_path):
    module = _load_module(
        ROOT / "scripts/ci/build_installer_bundle.py",
        "build_installer_bundle_windows_module",
    )

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    _create_minimal_repo(repo_root)

    output_path = tmp_path / "dist" / "elefante-installer-Windows.zip"
    module.build_installer_bundle(repo_root, platform_name="Windows", output_path=output_path)

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        launcher = archive.read("elefante-installer-Windows/Install Elefante.bat")
        manifest = archive.read(
            "elefante-installer-Windows/installer-manifest.json"
        ).decode("utf-8")

    assert "elefante-installer-Windows/START HERE.txt" in names
    assert "elefante-installer-Windows/Install Elefante.bat" in names
    assert "elefante-installer-Windows/install.sh" not in names
    assert b"scripts\\setup\\bootstrap_release_bundle.py" in launcher
    assert not [
        byte
        for byte in launcher
        if byte < 32 and byte not in (9, 10, 13)
    ]
    assert b"\r\n" in launcher
    assert '"entrypoints": [\n    "Install Elefante.bat"\n  ]' in manifest


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
