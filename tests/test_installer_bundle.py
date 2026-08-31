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
import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TEST_COMMIT = "a" * 40


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
        "scripts/lifecycle/daemon_service.py": "print('service')\n",
        "scripts/lifecycle/backup_elefante_data.py": "print('backup')\n",
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


def _create_bootstrap_bundle(
    bundle_root: Path,
    *,
    version: str,
    source_commit: str,
) -> Path:
    payload_root = bundle_root / "payload" / "elefante"
    (payload_root / "scripts" / "setup").mkdir(parents=True)
    (bundle_root / "scripts" / "setup").mkdir(parents=True)
    (payload_root / "scripts" / "setup" / "install.py").write_text(
        "print('install')\n",
        encoding="utf-8",
    )
    (payload_root / "requirements.txt").write_text("", encoding="utf-8")
    (payload_root / "requirements.lock").write_text("", encoding="utf-8")
    identity = {
        "schema_version": 1,
        "version": version,
        "source_commit": source_commit,
        "source_clean": True,
        "release_channel": "development",
    }
    (payload_root / "elefante-build.json").write_text(
        json.dumps(identity),
        encoding="utf-8",
    )
    (bundle_root / "installer-manifest.json").write_text(
        json.dumps(
            {
                "version": version,
                "release_profile": "developer",
                "release_channel": "development",
                "source": {"commit": source_commit, "clean": True},
            }
        ),
        encoding="utf-8",
    )
    (bundle_root / "scripts" / "setup" / "bootstrap_release_bundle.py").write_text(
        "",
        encoding="utf-8",
    )
    return payload_root


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


def test_managed_data_root_comes_from_the_matching_strict_install_manifest(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_data_root_module",
    )
    home = tmp_path / "home"
    install_root = tmp_path / "stable" / "current"
    custom_data = tmp_path / "customer-data" / "elefante"
    manifest = home / ".elefante" / module.INSTALL_MANIFEST_FILE_NAME
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "runtime": {
                    "app_root": str(install_root),
                    "data_root": str(custom_data),
                }
            }
        ),
        encoding="utf-8",
    )

    assert module.resolve_managed_data_dir(install_root, home=home) == custom_data

    manifest.write_text(
        '{"runtime":{"app_root":"one","app_root":"two","data_root":"/data"}}',
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="manifest is invalid"):
        module.resolve_managed_data_dir(install_root, home=home)


def test_managed_backup_directory_follows_the_effective_data_layout(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_managed_backup_module",
    )
    custom_data = tmp_path / "managed-product" / "data"

    assert module.managed_backup_dir(custom_data) == (
        tmp_path / "managed-product" / "backups"
    )


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


def test_place_payload_restores_previous_install_when_switch_is_interrupted(
    monkeypatch,
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_interrupt_module",
    )
    payload_root = tmp_path / "payload" / "elefante"
    payload_root.mkdir(parents=True)
    (payload_root / "README.md").write_text("new payload\n", encoding="utf-8")
    install_root = tmp_path / "stable" / "current"
    install_root.mkdir(parents=True)
    (install_root / "README.md").write_text("old payload\n", encoding="utf-8")
    real_move = module.shutil.move
    moves = 0

    def interrupt_candidate_switch(source, destination):
        nonlocal moves
        moves += 1
        if moves == 2:
            raise KeyboardInterrupt
        return real_move(source, destination)

    monkeypatch.setattr(module.shutil, "move", interrupt_candidate_switch)

    with pytest.raises(KeyboardInterrupt):
        module.place_payload(payload_root, install_root)

    assert (install_root / "README.md").read_text(encoding="utf-8") == "old payload\n"
    assert list(install_root.parent.glob("current.backup.*")) == []


def test_restore_previous_payload_quarantines_failed_candidate_and_restores_exact_prior(
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_restore_module",
    )
    install_root = tmp_path / "stable" / "current"
    install_root.mkdir(parents=True)
    (install_root / "candidate.txt").write_text("failed candidate\n", encoding="utf-8")
    backup_root = tmp_path / "stable" / "current.backup.20260829_120000"
    backup_root.mkdir()
    (backup_root / "previous.txt").write_text("known good\n", encoding="utf-8")

    failed_root = module.restore_previous_payload(install_root, backup_root)

    assert (install_root / "previous.txt").read_text(encoding="utf-8") == "known good\n"
    assert (failed_root / "candidate.txt").read_text(encoding="utf-8") == "failed candidate\n"
    assert not backup_root.exists()


def test_restore_previous_payload_rejects_unrelated_directory(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_restore_safety_module",
    )
    install_root = tmp_path / "stable" / "current"
    install_root.mkdir(parents=True)
    unrelated = tmp_path / "stable" / "user-files"
    unrelated.mkdir()

    with pytest.raises(ValueError, match="missing or unsafe"):
        module.restore_previous_payload(install_root, unrelated)

    assert install_root.is_dir()
    assert unrelated.is_dir()


def test_retained_code_switch_is_exact_and_reversible(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_retained_switch_module",
    )
    install_root = tmp_path / "app" / "current"
    target_root = tmp_path / "app" / "current.backup.20260830_120000"
    install_root.mkdir(parents=True)
    target_root.mkdir()
    (install_root / "version.txt").write_text("current\n", encoding="utf-8")
    (target_root / "version.txt").write_text("previous\n", encoding="utf-8")

    displaced_root = module.switch_to_retained_payload(install_root, target_root)

    assert (install_root / "version.txt").read_text(encoding="utf-8") == "previous\n"
    assert (displaced_root / "version.txt").read_text(encoding="utf-8") == "current\n"
    assert not target_root.exists()

    module.restore_displaced_payload(install_root, displaced_root, target_root)

    assert (install_root / "version.txt").read_text(encoding="utf-8") == "current\n"
    assert (target_root / "version.txt").read_text(encoding="utf-8") == "previous\n"
    assert not displaced_root.exists()


def test_retained_code_switch_interruption_restores_current_before_returning(
    monkeypatch,
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_retained_interrupt_module",
    )
    install_root = tmp_path / "app" / "current"
    target_root = tmp_path / "app" / "current.backup.20260830_120000"
    install_root.mkdir(parents=True)
    target_root.mkdir()
    (install_root / "current.txt").write_text("current\n", encoding="utf-8")
    (target_root / "target.txt").write_text("target\n", encoding="utf-8")
    real_move = module.shutil.move
    moves = 0

    def interrupt_target(source, destination):
        nonlocal moves
        moves += 1
        if moves == 2:
            raise KeyboardInterrupt
        return real_move(source, destination)

    monkeypatch.setattr(module.shutil, "move", interrupt_target)

    with pytest.raises(KeyboardInterrupt):
        module.switch_to_retained_payload(install_root, target_root)

    assert (install_root / "current.txt").read_text(encoding="utf-8") == "current\n"
    assert (target_root / "target.txt").read_text(encoding="utf-8") == "target\n"
    assert list(install_root.parent.glob("current.backup.*")) == [target_root]


def test_runtime_manifest_identity_switch_preserves_ownership_and_exact_rollback(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_manifest_switch_module",
    )
    install_root = tmp_path / "app" / "current"
    data_dir = tmp_path / "data"
    manifest_path = tmp_path / "home" / ".elefante" / module.INSTALL_MANIFEST_FILE_NAME
    manifest_path.parent.mkdir(parents=True)
    original_payload = {
        "schema_version": 3,
        "files": {"owned": {"sha256": "digest"}},
        "runtime": {
            "app_root": str(install_root),
            "data_root": str(data_dir),
            "scope": "customer",
            "version": "2.14.0",
            "source_commit": "b" * 40,
            "source_clean": True,
            "release_channel": "release",
        },
    }
    manifest_path.write_text(
        json.dumps(original_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_path.chmod(0o600)
    original_bytes = manifest_path.read_bytes()
    target_identity = {
        "version": "2.13.0",
        "source_commit": "a" * 40,
        "source_clean": True,
        "release_channel": "release",
    }

    snapshot, mode = module.update_runtime_manifest_identity(
        manifest_path,
        install_root=install_root,
        data_dir=data_dir,
        identity=target_identity,
        operation_id="rollback-operation",
    )

    activated = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert activated["runtime"]["version"] == "2.13.0"
    assert activated["files"] == original_payload["files"]
    assert manifest_path.stat().st_mode & 0o777 == 0o600
    assert snapshot == original_bytes

    module.restore_runtime_manifest_snapshot(
        manifest_path,
        snapshot,
        mode,
        operation_id="rollback-operation",
    )
    assert manifest_path.read_bytes() == original_bytes
    assert manifest_path.stat().st_mode & 0o777 == 0o600


def _write_customer_identity(root: Path, identity: dict[str, object]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "elefante-build.json").write_text(
        json.dumps({"schema_version": 1, **identity}),
        encoding="utf-8",
    )


def _write_customer_manifest(
    home: Path,
    *,
    install_root: Path,
    data_dir: Path,
    identity: dict[str, object],
) -> Path:
    manifest_path = home / ".elefante" / "install-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "files": {"owned": {"sha256": "digest"}},
                "runtime": {
                    "app_root": str(install_root),
                    "data_root": str(data_dir),
                    "scope": "customer",
                    **identity,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path.chmod(0o600)
    return manifest_path


def _uninstall_fixture(module, tmp_path):
    home = tmp_path / "home"
    install_root = tmp_path / "app" / "current"
    payload_root = tmp_path / "official-package" / "payload" / "elefante"
    data_dir = tmp_path / "custom-elefante-data"
    identity = {
        "version": "2.13.0",
        "source_commit": "a" * 40,
        "source_clean": True,
        "release_channel": "release",
    }
    _write_customer_identity(install_root, identity)
    (install_root / "product.txt").write_text("installed product\n", encoding="utf-8")
    payload_root.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    (data_dir / "memory.sqlite3").write_bytes(b"private-memory-bytes")
    _write_customer_manifest(
        home,
        install_root=install_root,
        data_dir=data_dir,
        identity=identity,
    )
    return {
        "home": home,
        "install_root": install_root,
        "payload_root": payload_root,
        "data_dir": data_dir,
        "identity": identity,
        "build_identity": {"schema_version": 1, **identity},
    }


def test_package_uninstall_plan_is_exact_private_and_stale_on_data_change(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_uninstall_plan_module",
    )
    fixture = _uninstall_fixture(module, tmp_path)

    plan = module.describe_package_uninstall(
        fixture["install_root"],
        fixture["build_identity"],
        release_profile="client",
        home=fixture["home"],
    )

    assert plan["available"] is True
    assert plan["data_effect"] == "preserved"
    assert plan["verified_backup_required"] is True
    assert plan["data_file_count"] == 1
    assert len(plan["confirmation_token"]) == 64
    rendered = json.dumps(plan, sort_keys=True)
    assert "private-memory-bytes" not in rendered
    assert "memory.sqlite3" not in rendered
    assert str(fixture["data_dir"]) not in rendered

    (fixture["data_dir"] / "memory.sqlite3").write_bytes(b"changed-after-preview")
    changed = module.describe_package_uninstall(
        fixture["install_root"],
        fixture["build_identity"],
        release_profile="client",
        home=fixture["home"],
    )
    assert changed["confirmation_token"] != plan["confirmation_token"]

    mismatched = module.describe_package_uninstall(
        fixture["install_root"],
        {**fixture["build_identity"], "source_commit": "b" * 40},
        release_profile="client",
        home=fixture["home"],
    )
    assert mismatched["available"] is False
    assert mismatched["reason_code"] == "MATCHING_OFFICIAL_PACKAGE_REQUIRED"


def test_package_uninstall_preserves_data_removes_app_and_enables_reinstall(
    monkeypatch,
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_uninstall_success_module",
    )
    fixture = _uninstall_fixture(module, tmp_path)
    backup_path = fixture["home"] / ".elefante" / "backups" / "verified.zip"
    backup_path.parent.mkdir(parents=True)
    backup_path.write_bytes(b"verified-backup")
    monkeypatch.setattr(module, "_run_payload_lifecycle", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module,
        "_create_uninstall_safety_backup",
        lambda **_kwargs: backup_path,
    )
    monkeypatch.setattr(
        module,
        "_detach_owned_surfaces_for_uninstall",
        lambda **_kwargs: {
            "removed_command_count": 2,
            "preserved_command_count": 1,
            "removed_file_count": 3,
            "preserved_file_count": 1,
        },
    )
    plan = module.describe_package_uninstall(
        fixture["install_root"],
        fixture["build_identity"],
        release_profile="client",
        home=fixture["home"],
    )

    result = module.execute_package_uninstall(
        payload_root=fixture["payload_root"],
        install_root=fixture["install_root"],
        build_identity=fixture["build_identity"],
        release_profile="client",
        confirmation_token=plan["confirmation_token"],
        python_executable=sys.executable,
        home=fixture["home"],
    )

    assert result["status"] == "VERIFIED_COMPLETE"
    assert result["app_removed"] is True
    assert result["preserved_command_count"] == 1
    assert not fixture["install_root"].exists()
    assert (fixture["data_dir"] / "memory.sqlite3").read_bytes() == b"private-memory-bytes"
    manifest = json.loads(
        (fixture["home"] / ".elefante" / "install-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert "runtime" not in manifest
    pointer_path = module.data_preservation_path(fixture["home"])
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    assert pointer["status"] == "VERIFIED_COMPLETE"
    assert pointer["data_state"]["file_count"] == 1
    assert pointer_path.stat().st_mode & 0o777 == 0o600
    assert pointer_path.parent.stat().st_mode & 0o777 == 0o700
    assert Path(result["receipt"]).parent.stat().st_mode & 0o777 == 0o700
    assert module.resolve_managed_data_dir(
        fixture["install_root"],
        home=fixture["home"],
    ) == fixture["data_dir"].resolve()
    receipt_text = Path(result["receipt"]).read_text(encoding="utf-8")
    assert "private-memory-bytes" not in receipt_text
    assert str(fixture["data_dir"]) not in receipt_text

    assert module.consume_data_preservation_receipt(
        home=fixture["home"],
        install_root=fixture["install_root"],
        data_root=fixture["data_dir"],
    ) is True
    assert not pointer_path.exists()


def test_package_uninstall_rejects_stale_confirmation_without_mutation(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_uninstall_stale_module",
    )
    fixture = _uninstall_fixture(module, tmp_path)
    plan = module.describe_package_uninstall(
        fixture["install_root"],
        fixture["build_identity"],
        release_profile="client",
        home=fixture["home"],
    )
    (fixture["data_dir"] / "memory.sqlite3").write_bytes(b"new-memory-state")

    result = module.execute_package_uninstall(
        payload_root=fixture["payload_root"],
        install_root=fixture["install_root"],
        build_identity=fixture["build_identity"],
        release_profile="client",
        confirmation_token=plan["confirmation_token"],
        python_executable=sys.executable,
        home=fixture["home"],
    )

    assert result["status"] == "FAILED_NO_CHANGE"
    assert result["reason_code"] == "CONFIRMATION_MISMATCH"
    assert fixture["install_root"].is_dir()
    assert (fixture["data_dir"] / "memory.sqlite3").read_bytes() == b"new-memory-state"
    assert not module.data_preservation_path(fixture["home"]).exists()


def test_package_uninstall_fails_closed_when_install_identity_changes_after_preview(
    monkeypatch,
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_uninstall_identity_race_module",
    )
    fixture = _uninstall_fixture(module, tmp_path)
    plan = module.describe_package_uninstall(
        fixture["install_root"],
        fixture["build_identity"],
        release_profile="client",
        home=fixture["home"],
    )
    identity_reads = iter([fixture["identity"], None])
    monkeypatch.setattr(
        module,
        "_read_customer_build_identity",
        lambda _root: next(identity_reads),
    )

    result = module.execute_package_uninstall(
        payload_root=fixture["payload_root"],
        install_root=fixture["install_root"],
        build_identity=fixture["build_identity"],
        release_profile="client",
        confirmation_token=plan["confirmation_token"],
        python_executable=sys.executable,
        home=fixture["home"],
    )

    assert result["status"] == "FAILED_NO_CHANGE"
    assert result["reason_code"] == "INSTALLATION_STATE_CHANGED"
    assert fixture["install_root"].is_dir()
    assert (fixture["data_dir"] / "memory.sqlite3").read_bytes() == b"private-memory-bytes"


def test_package_uninstall_restores_app_when_code_removal_cannot_verify(
    monkeypatch,
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_uninstall_rollback_module",
    )
    fixture = _uninstall_fixture(module, tmp_path)
    backup_path = fixture["home"] / ".elefante" / "backups" / "verified.zip"
    backup_path.parent.mkdir(parents=True)
    backup_path.write_bytes(b"verified-backup")
    monkeypatch.setattr(module, "_run_payload_lifecycle", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module,
        "_create_uninstall_safety_backup",
        lambda **_kwargs: backup_path,
    )
    monkeypatch.setattr(
        module,
        "_detach_owned_surfaces_for_uninstall",
        lambda **_kwargs: {
            "removed_command_count": 0,
            "preserved_command_count": 0,
            "removed_file_count": 0,
            "preserved_file_count": 0,
        },
    )
    monkeypatch.setattr(
        module,
        "_clear_runtime_manifest_for_uninstall",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("forced manifest failure")),
    )
    monkeypatch.setattr(module, "reactivate_previous_install", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "verify_installed_product", lambda *_args, **_kwargs: True)
    plan = module.describe_package_uninstall(
        fixture["install_root"],
        fixture["build_identity"],
        release_profile="client",
        home=fixture["home"],
    )

    result = module.execute_package_uninstall(
        payload_root=fixture["payload_root"],
        install_root=fixture["install_root"],
        build_identity=fixture["build_identity"],
        release_profile="client",
        confirmation_token=plan["confirmation_token"],
        python_executable=sys.executable,
        home=fixture["home"],
    )

    assert result["status"] == "FAILED_ROLLED_BACK"
    assert fixture["install_root"].is_dir()
    assert (fixture["install_root"] / "product.txt").is_file()
    assert (fixture["data_dir"] / "memory.sqlite3").read_bytes() == b"private-memory-bytes"
    pointer = json.loads(
        module.data_preservation_path(fixture["home"]).read_text(encoding="utf-8")
    )
    assert pointer["status"] == "FAILED_ROLLED_BACK"


def test_package_uninstall_never_overstates_rollback_after_owned_surface_removal(
    monkeypatch,
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_uninstall_partial_detach_module",
    )
    fixture = _uninstall_fixture(module, tmp_path)
    backup_path = fixture["home"] / ".elefante" / "backups" / "verified.zip"
    backup_path.parent.mkdir(parents=True)
    backup_path.write_bytes(b"verified-backup")
    monkeypatch.setattr(module, "_run_payload_lifecycle", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module,
        "_create_uninstall_safety_backup",
        lambda **_kwargs: backup_path,
    )
    monkeypatch.setattr(
        module,
        "_detach_owned_surfaces_for_uninstall",
        lambda **_kwargs: {
            "removed_command_count": 1,
            "preserved_command_count": 0,
            "removed_file_count": 0,
            "preserved_file_count": 0,
        },
    )
    monkeypatch.setattr(
        module,
        "_clear_runtime_manifest_for_uninstall",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("forced manifest failure")),
    )
    monkeypatch.setattr(module, "reactivate_previous_install", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "verify_installed_product", lambda *_args, **_kwargs: True)
    plan = module.describe_package_uninstall(
        fixture["install_root"],
        fixture["build_identity"],
        release_profile="client",
        home=fixture["home"],
    )

    result = module.execute_package_uninstall(
        payload_root=fixture["payload_root"],
        install_root=fixture["install_root"],
        build_identity=fixture["build_identity"],
        release_profile="client",
        confirmation_token=plan["confirmation_token"],
        python_executable=sys.executable,
        home=fixture["home"],
    )

    assert result["status"] == "NEEDS_HUMAN"
    assert result["next_action"] == "create_support_report"
    assert fixture["install_root"].is_dir()


@pytest.mark.parametrize("target_verifies", [True, False])
def test_retained_code_rollback_verifies_target_or_restores_exact_current(
    monkeypatch,
    tmp_path,
    target_verifies,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        f"bootstrap_release_bundle_retained_execute_{target_verifies}_module",
    )
    home = tmp_path / "home"
    install_root = tmp_path / "app" / "current"
    target_root = tmp_path / "app" / "current.backup.20260830_120000"
    data_dir = tmp_path / "managed-data"
    current_identity = {
        "version": "2.14.0",
        "source_commit": "b" * 40,
        "source_clean": True,
        "release_channel": "release",
    }
    target_identity = {
        "version": "2.13.0",
        "source_commit": "a" * 40,
        "source_clean": True,
        "release_channel": "release",
    }
    _write_customer_identity(install_root, current_identity)
    _write_customer_identity(target_root, target_identity)
    (install_root / "current.txt").write_text("current product\n", encoding="utf-8")
    (target_root / "target.txt").write_text("retained product\n", encoding="utf-8")
    module.write_retained_code_receipt(
        target_root,
        operation_id="source-update",
        retained_identity=target_identity,
        replacement_identity=current_identity,
    )
    manifest_path = _write_customer_manifest(
        home,
        install_root=install_root,
        data_dir=data_dir,
        identity=current_identity,
    )
    original_manifest = manifest_path.read_bytes()
    description = module.describe_retained_code_rollback(install_root)
    monkeypatch.setattr(module, "prepare_existing_install", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "reactivate_previous_install", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "_run_payload_lifecycle", lambda *_args, **_kwargs: True)

    def verifier(root, **_kwargs):
        version = module._read_customer_build_identity(root)["version"]
        return version == "2.14.0" or target_verifies

    monkeypatch.setattr(module, "verify_installed_product", verifier)

    result = module.execute_retained_code_rollback(
        payload_root=tmp_path / "official-package" / "payload" / "elefante",
        install_root=install_root,
        package_identity=current_identity,
        confirmation_token=description["confirmation_token"],
        python_executable=sys.executable,
        home=home,
    )

    if target_verifies:
        assert result == 0
        assert module._read_customer_build_identity(install_root) == target_identity
        assert (install_root / "target.txt").is_file()
        activated = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert activated["runtime"]["version"] == "2.13.0"
        receipt = json.loads(
            (install_root / module.PACKAGE_RECEIPT_FILE_NAME).read_text(encoding="utf-8")
        )
        assert receipt["status"] == "VERIFIED_COMPLETE"
        assert receipt["operation"] == "rollback"
        retained_newer = module.describe_retained_code_rollback(install_root)
        assert retained_newer["available"] is True
        assert retained_newer["target_version"] == "2.14.0"
    else:
        assert result == 1
        assert module._read_customer_build_identity(install_root) == current_identity
        assert (install_root / "current.txt").is_file()
        assert target_root.is_dir()
        assert manifest_path.read_bytes() == original_manifest
        receipt = json.loads(
            (target_root / module.PACKAGE_RECEIPT_FILE_NAME).read_text(encoding="utf-8")
        )
        assert receipt["status"] == "FAILED_ROLLED_BACK"
        assert receipt["rollback"] == "previous_product_restored"


def test_reactivate_previous_install_uses_restored_lifecycle_owner(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_reactivate_module",
    )
    install_root = tmp_path / "stable" / "current"
    service_script = install_root / "scripts" / "lifecycle" / "daemon_service.py"
    service_script.parent.mkdir(parents=True)
    service_script.write_text("", encoding="utf-8")
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    assert module.reactivate_previous_install(
        install_root,
        python_executable="/usr/bin/python3",
        runner=runner,
        health_check=lambda: True,
    )
    assert calls == [
        (
            ["/usr/bin/python3", str(service_script), "install", "--apply"],
            {"cwd": install_root, "check": False},
        )
    ]


def test_reactivate_previous_install_requires_live_health_after_service_command(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_reactivate_health_module",
    )
    install_root = tmp_path / "current"
    service_script = install_root / module.DAEMON_SERVICE_RELATIVE_PATH
    service_script.parent.mkdir(parents=True)
    service_script.write_text("", encoding="utf-8")

    assert not module.reactivate_previous_install(
        install_root,
        python_executable="/usr/bin/python3",
        runner=lambda command, **_: subprocess.CompletedProcess(command, 0),
        health_check=lambda: False,
        timeout_seconds=0,
    )


def test_prepare_existing_install_stops_service_then_creates_verified_backup(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_prepare_module",
    )
    payload_root = tmp_path / "payload"
    for relative in (
        module.DAEMON_SERVICE_RELATIVE_PATH,
        module.BACKUP_SCRIPT_RELATIVE_PATH,
    ):
        script = payload_root / relative
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("", encoding="utf-8")
    install_root = tmp_path / "stable" / "current"
    install_root.mkdir(parents=True)
    home = tmp_path / "home"
    data_root = tmp_path / "custom-product" / "data"
    data_file = data_root / "vector" / "memories.sqlite3"
    data_file.parent.mkdir(parents=True)
    data_file.write_text("memory", encoding="utf-8")
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    assert module.prepare_existing_install(
        payload_root,
        install_root,
        python_executable="/usr/bin/python3",
        home=home,
        data_dir=data_root,
        runner=runner,
    )
    assert calls == [
        (
            [
                "/usr/bin/python3",
                str(payload_root / module.DAEMON_SERVICE_RELATIVE_PATH),
                "stop",
                "--apply",
            ],
            {"cwd": payload_root, "check": False},
        ),
        (
            [
                "/usr/bin/python3",
                str(payload_root / module.BACKUP_SCRIPT_RELATIVE_PATH),
                "--elefante-home",
                str(home / ".elefante"),
                "--data-dir",
                str(data_root),
                "--out-dir",
                str(data_root.parent / "backups"),
            ],
            {"cwd": payload_root, "check": False},
        ),
    ]


def test_prepare_existing_install_restarts_unchanged_service_when_backup_fails(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_prepare_failure_module",
    )
    payload_root = tmp_path / "payload"
    for relative in (
        module.DAEMON_SERVICE_RELATIVE_PATH,
        module.BACKUP_SCRIPT_RELATIVE_PATH,
    ):
        script = payload_root / relative
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("", encoding="utf-8")
    install_root = tmp_path / "stable" / "current"
    install_root.mkdir(parents=True)
    home = tmp_path / "home"
    data_dir = home / ".elefante" / "data"
    data_dir.mkdir(parents=True)
    actions = []

    def runner(command, **_):
        action = command[2] if command[1].endswith("daemon_service.py") else "backup"
        actions.append(action)
        return subprocess.CompletedProcess(command, 1 if action == "backup" else 0)

    def reactivate(*_args, **_kwargs):
        actions.append("reactivate")
        return True

    with pytest.raises(RuntimeError, match="left unchanged"):
        module.prepare_existing_install(
            payload_root,
            install_root,
            python_executable="/usr/bin/python3",
            home=home,
            runner=runner,
            reactivator=reactivate,
            product_verifier=lambda *_args, **_kwargs: True,
        )

    assert actions == ["stop", "backup", "reactivate"]


def test_verify_installed_product_requires_customer_ready_and_live_recall(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_verify_module",
    )
    install_root = tmp_path / "current"
    python_path = install_root / ".venv" / (
        "Scripts/python.exe" if module.os.name == "nt" else "bin/python"
    )
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    doctor_path = install_root / module.DOCTOR_SCRIPT_RELATIVE_PATH
    doctor_path.parent.mkdir(parents=True)
    doctor_path.write_text("", encoding="utf-8")

    def report(payload, returncode=0):
        return lambda command, **_: subprocess.CompletedProcess(
            command,
            returncode,
            stdout=json.dumps(payload),
        )

    assert module.verify_installed_product(
        install_root,
        runner=report(
            {
                "ready": True,
                "customer_ready": True,
                "recall": {"required": True, "ready": True},
            }
        ),
    )
    assert not module.verify_installed_product(
        install_root,
        runner=report(
            {
                "ready": True,
                "customer_ready": True,
                "recall": {"required": True, "ready": False},
            }
        ),
    )
    assert not module.verify_installed_product(
        install_root,
        runner=report(
            {
                "ready": True,
                "customer_ready": False,
                "recall": {"required": False, "ready": None},
            },
            returncode=1,
        ),
    )


def test_package_receipt_is_content_free_private_and_customer_readable(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_receipt_module",
    )
    root = tmp_path / "current"

    target = module.write_package_receipt(
        root,
        operation_id="operation-123",
        operation="repair",
        status="VERIFIED_COMPLETE",
        started_at="2026-08-29T12:00:00+00:00",
        previous_version="2.13.0",
        target_version="2.13.0",
        safety_backup="VERIFIED",
        product_verification=True,
        rollback="previous_product_available",
        recoverable=True,
        next_action="reopen_home_check_health",
    )

    receipt = json.loads(target.read_text(encoding="utf-8"))
    assert receipt["operation"] == "repair"
    assert receipt["status"] == "VERIFIED_COMPLETE"
    assert receipt["failed_stage"] is None
    assert [check["name"] for check in receipt["checks"]] == [
        "safety_backup",
        "product_readiness",
        "first_run_acceptance",
    ]
    assert receipt["checks"][2]["code"] == "FIRST_RUN_ACCEPTANCE_NOT_REQUIRED"
    assert "content" not in json.dumps(receipt).lower()
    assert target.stat().st_mode & 0o777 == 0o600
    summary = (root / module.INSTALL_SUMMARY_FILE_NAME).read_text(encoding="utf-8")
    assert "Operation: Repair" in summary
    assert "Runtime, agent connection, and Recall: VERIFIED" in summary


def test_failed_package_receipt_records_only_an_allowlisted_installer_stage(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_failed_stage_module",
    )
    root = tmp_path / "current"
    target = module.write_package_receipt(
        root,
        operation_id="55555555-5555-4555-8555-555555555555",
        operation="repair",
        status="FAILED_ROLLED_BACK",
        started_at="2026-08-30T12:00:00+00:00",
        previous_version="2.13.0",
        target_version="2.13.0",
        safety_backup="VERIFIED",
        product_verification=True,
        rollback="previous_product_restored",
        recoverable=True,
        next_action="create_support_report",
        failed_stage="4",
    )
    receipt = json.loads(target.read_text(encoding="utf-8"))
    assert receipt["failed_stage"] == "4"
    assert "Failed stage: 4" in (root / module.INSTALL_SUMMARY_FILE_NAME).read_text()

    with pytest.raises(ValueError, match="failed stage"):
        module.write_package_receipt(
            root,
            operation_id="66666666-6666-4666-8666-666666666666",
            operation="repair",
            status="FAILED_ROLLED_BACK",
            started_at="2026-08-30T12:00:00+00:00",
            previous_version="2.13.0",
            target_version="2.13.0",
            safety_backup="VERIFIED",
            product_verification=True,
            rollback="previous_product_restored",
            recoverable=True,
            next_action="create_support_report",
            failed_stage="/Users/customer/private",
        )


def test_failed_installer_stage_is_read_from_bounded_summary(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_failed_stage_reader_module",
    )
    root = tmp_path / "current"
    root.mkdir()
    summary = root / module.INSTALL_SUMMARY_FILE_NAME
    summary.write_text(
        "1|Dependencies|COMPLETED|ok\n4|IDE Configuration|FAILED|private detail\n",
        encoding="utf-8",
    )
    assert module.read_failed_installer_stage(root) == "4"

    summary.write_text(
        "customer/private/path|Unknown|FAILED|private detail\n",
        encoding="utf-8",
    )
    assert module.read_failed_installer_stage(root) == "unknown"


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
    assert command[command.index("--installation-scope") + 1] == "developer"
    assert command.count("--host") == 2
    assert command[command.index("--host") + 1] == "cursor"
    second_host = command.index("--host", command.index("--host") + 1)
    assert command[second_host + 1] == "codex"


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
        build_identity={
            "schema_version": 1,
            "version": "9.9.9",
            "source_commit": TEST_COMMIT,
            "source_clean": True,
            "release_channel": "candidate",
        },
    )

    assert command[-2:] == ["--release-profile", "client"]
    assert command[command.index("--installation-scope") + 1] == "customer"
    assert command[command.index("--source-commit") + 1] == TEST_COMMIT
    assert command[command.index("--release-channel") + 1] == "candidate"
    assert "--source-clean" in command


def test_client_bundle_command_forwards_fresh_project_selections(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_project_command_module",
    )
    project_root = tmp_path / "company" / "alpha"
    project_root.mkdir(parents=True)
    project = f"Alpha={project_root}"

    command = module.build_install_command(
        tmp_path / "current",
        python_executable="/usr/bin/python3",
        venv_mode="fresh",
        release_profile="client",
        build_identity={
            "schema_version": 1,
            "version": "9.9.9",
            "source_commit": TEST_COMMIT,
            "source_clean": True,
            "release_channel": "candidate",
        },
        projects=[project],
    )

    assert command[command.index("--project") + 1] == project


def test_bootstrap_independently_verifies_content_free_first_run_receipt(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_first_run_receipt_module",
    )
    target = tmp_path / module.FIRST_RUN_RECEIPT_FILE_NAME
    receipt = {
        "schema_version": 1,
        "operation": "first_run_acceptance",
        "status": "VERIFIED_COMPLETE",
        "finished_at": "2026-08-30T14:00:00+00:00",
        "checks": [
            {"name": name, "passed": True, "code": f"{name.upper()}_VERIFIED"}
            for name in (
                "project_isolation",
                "disposable_recall",
                "acceptance_cleanup",
                "initial_backup",
            )
        ],
        "acceptance_operation_id": "11111111-1111-4111-8111-111111111111",
        "backup_operation_id": "22222222-2222-4222-8222-222222222222",
        "initial_backup": {
            "archive_name": "elefante_data_backup_20260830.zip",
            "archive_sha256": "a" * 64,
        },
        "memory_content_included": False,
        "project_path_included": False,
        "next_action": "open_elefante_home",
    }
    target.write_text(json.dumps(receipt), encoding="utf-8")
    os.chmod(target, 0o600)

    assert module.verify_first_run_acceptance(tmp_path) is True

    receipt["project_path"] = "/private/tmp/customer-project"
    target.write_text(json.dumps(receipt), encoding="utf-8")
    os.chmod(target, 0o600)
    assert module.verify_first_run_acceptance(tmp_path) is False


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
    (payload_root / "scripts" / "lifecycle").mkdir(parents=True)
    (payload_root / "scripts" / "lifecycle" / "daemon_service.py").write_text(
        "", encoding="utf-8"
    )
    (payload_root / "scripts" / "lifecycle" / "backup_elefante_data.py").write_text(
        "", encoding="utf-8"
    )
    (payload_root / "scripts" / "lifecycle" / "restore_elefante_data.py").write_text(
        "", encoding="utf-8"
    )
    (payload_root / "scripts" / "lifecycle" / "uninstall_elefante.py").write_text(
        "", encoding="utf-8"
    )
    (payload_root / "scripts" / "lifecycle" / "doctor.py").write_text(
        "", encoding="utf-8"
    )
    (payload_root / "requirements.client.txt").write_text("", encoding="utf-8")
    (payload_root / "requirements.client.lock").write_text("", encoding="utf-8")
    (payload_root / "elefante-build.json").write_text("{}", encoding="utf-8")
    (bundle_root / "scripts" / "setup" / "bootstrap_release_bundle.py").write_text(
        "", encoding="utf-8"
    )

    assert module.ensure_bundle_layout(bundle_root, release_profile="client") == payload_root


def test_bootstrap_rejects_archive_payload_identity_mismatch(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_identity_module",
    )
    bundle_root = tmp_path / "bundle"
    payload_root = bundle_root / "payload" / "elefante"
    payload_root.mkdir(parents=True)
    manifest = {
        "version": "9.9.9",
        "release_profile": "client",
        "publication_status": "candidate",
        "source": {"commit": TEST_COMMIT, "clean": True},
    }
    identity = {
        "schema_version": 1,
        "version": "9.9.9",
        "source_commit": TEST_COMMIT,
        "source_clean": True,
        "release_channel": "candidate",
    }
    (payload_root / "elefante-build.json").write_text(
        json.dumps(identity),
        encoding="utf-8",
    )

    assert module.load_build_identity(
        bundle_root,
        manifest,
        release_profile="client",
    ) == identity

    identity["source_commit"] = "b" * 40
    (payload_root / "elefante-build.json").write_text(
        json.dumps(identity),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="do not match"):
        module.load_build_identity(
            bundle_root,
            manifest,
            release_profile="client",
        )


def test_package_operation_distinguishes_install_repair_update_and_blocks_downgrade(
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_operation_module",
    )
    install_root = tmp_path / "current"
    candidate = {
        "version": "2.13.0",
        "source_commit": "b" * 40,
    }

    assert module.classify_package_operation(install_root, candidate) == "install"

    install_root.mkdir()
    assert module.classify_package_operation(install_root, candidate) == "repair"

    (install_root / module.BUILD_IDENTITY_FILE_NAME).write_text(
        json.dumps(candidate), encoding="utf-8"
    )
    assert module.classify_package_operation(install_root, candidate) == "repair"

    newer = {"version": "2.14.0", "source_commit": "c" * 40}
    assert module.classify_package_operation(install_root, newer) == "update"

    older = {"version": "2.12.3", "source_commit": "a" * 40}
    assert module.classify_package_operation(install_root, older) == "rollback"


def test_failed_fresh_install_reopens_as_install_for_safe_project_selection(
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_retry_fresh_install_module",
    )
    install_root = tmp_path / "home" / ".elefante" / "app" / "current"
    install_root.mkdir(parents=True)
    identity = {
        "schema_version": 1,
        "version": "2.14.0",
        "source_commit": "a" * 40,
        "source_clean": True,
        "release_channel": "candidate",
    }
    (install_root / module.BUILD_IDENTITY_FILE_NAME).write_text(
        json.dumps(identity),
        encoding="utf-8",
    )
    module.write_package_receipt(
        install_root,
        operation_id="44444444-4444-4444-8444-444444444444",
        operation="install",
        status="NEEDS_HUMAN",
        started_at="2026-08-30T12:00:00+00:00",
        previous_version=None,
        target_version="2.14.0",
        safety_backup="NOT_REQUIRED",
        product_verification=False,
        rollback="manual_recovery_required",
        recoverable=False,
        next_action="create_support_report",
        first_run_verification=False,
    )

    assert module.classify_package_operation(install_root, identity) == "install"

    receipt = json.loads(
        (install_root / module.PACKAGE_RECEIPT_FILE_NAME).read_text(encoding="utf-8")
    )
    receipt["status"] = "VERIFIED_COMPLETE"
    (install_root / module.PACKAGE_RECEIPT_FILE_NAME).write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )
    assert module.classify_package_operation(install_root, identity) == "repair"


def test_package_operation_description_binds_explicit_code_rollback_to_both_builds(
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_description_module",
    )
    install_root = tmp_path / "current"
    install_root.mkdir()
    installed = {"version": "2.14.0", "source_commit": "b" * 40}
    target = {"version": "2.13.0", "source_commit": "a" * 40}
    (install_root / module.BUILD_IDENTITY_FILE_NAME).write_text(
        json.dumps(installed),
        encoding="utf-8",
    )

    description = module.describe_package_operation(install_root, target)

    assert description == {
        "schema_version": 1,
        "operation": "rollback",
        "title": "Roll Back Elefante",
        "current_version": "2.14.0",
        "target_version": "2.13.0",
        "requires_confirmation": True,
        "confirmation_token": module.build_code_rollback_confirmation(installed, target),
        "data_effect": "preserved_not_restored",
        "completion": (
            "Code rollback verified — Elefante, agent connection, and Recall are ready."
        ),
        "retained_rollback": {"available": False},
    }
    assert str(tmp_path) not in json.dumps(description)


def test_retained_code_receipt_exposes_only_the_exact_verified_previous_product(tmp_path):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_retained_code_module",
    )
    install_root = tmp_path / "app" / "current"
    backup_root = tmp_path / "app" / "current.backup.20260830_120000"
    install_root.mkdir(parents=True)
    backup_root.mkdir()
    current_identity = {
        "version": "2.14.0",
        "source_commit": "b" * 40,
        "source_clean": True,
        "release_channel": "release",
    }
    retained_identity = {
        "version": "2.13.0",
        "source_commit": "a" * 40,
        "source_clean": True,
        "release_channel": "release",
    }
    for root, identity in (
        (install_root, current_identity),
        (backup_root, retained_identity),
    ):
        (root / module.BUILD_IDENTITY_FILE_NAME).write_text(
            json.dumps({"schema_version": 1, **identity}),
            encoding="utf-8",
        )
    retained_file = backup_root / "src" / "retained.py"
    retained_file.parent.mkdir()
    retained_file.write_text("stable payload\n", encoding="utf-8")

    receipt_path = module.write_retained_code_receipt(
        backup_root,
        operation_id="update-operation",
        retained_identity=retained_identity,
        replacement_identity=current_identity,
    )
    description = module.describe_retained_code_rollback(install_root)

    assert receipt_path.stat().st_mode & 0o777 == 0o600
    assert description["available"] is True
    assert description["backup_name"] == backup_root.name
    assert description["current_version"] == "2.14.0"
    assert description["target_version"] == "2.13.0"
    assert len(description["confirmation_token"]) == 64
    assert str(tmp_path) not in json.dumps(description)
    assert "content" not in receipt_path.read_text(encoding="utf-8")

    retained_file.write_text("tampered payload\n", encoding="utf-8")
    assert module._read_retained_code_receipt(backup_root) is not None
    assert module.verify_retained_code_receipt(backup_root) is None
    retained_file.write_text("stable payload\n", encoding="utf-8")
    assert module.verify_retained_code_receipt(backup_root) is not None

    (backup_root / module.BUILD_IDENTITY_FILE_NAME).write_text(
        json.dumps({"schema_version": 1, **retained_identity, "source_commit": "c" * 40}),
        encoding="utf-8",
    )
    assert module.describe_retained_code_rollback(install_root) == {"available": False}


def test_bootstrap_routes_retained_rollback_through_the_matching_official_package(
    monkeypatch,
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_retained_route_module",
    )
    bundle_root = tmp_path / "bundle"
    payload_root = bundle_root / "payload" / "elefante"
    install_root = tmp_path / "app" / "current"
    identity = {
        "version": "2.14.0",
        "source_commit": "b" * 40,
        "source_clean": True,
        "release_channel": "release",
    }
    _write_customer_identity(install_root, identity)
    calls = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bootstrap_release_bundle.py",
            "--bundle-root",
            str(bundle_root),
            "--install-root",
            str(install_root),
            "--rollback-retained",
            "bound-token",
        ],
    )
    monkeypatch.setattr(module, "get_release_profile", lambda _manifest: "client")
    monkeypatch.setattr(
        module,
        "ensure_bundle_layout",
        lambda *_args, **_kwargs: payload_root,
    )
    monkeypatch.setattr(
        module,
        "load_build_identity",
        lambda *_args, **_kwargs: {"schema_version": 1, **identity},
    )
    monkeypatch.setattr(module, "resolve_install_python", lambda _value: sys.executable)
    monkeypatch.setattr(
        module,
        "resolve_managed_data_dir",
        lambda *_args, **_kwargs: tmp_path / "managed-data",
    )

    def execute(**kwargs):
        calls.append(kwargs)
        return 0

    monkeypatch.setattr(module, "execute_retained_code_rollback", execute)

    with pytest.raises(SystemExit) as exited:
        module.main()

    assert exited.value.code == 0
    assert calls[0]["payload_root"] == payload_root
    assert calls[0]["install_root"] == install_root
    assert calls[0]["confirmation_token"] == "bound-token"


def test_older_package_requires_exact_code_rollback_confirmation_before_mutation(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_rollback_guard_module",
    )
    bundle_root = tmp_path / "bundle"
    _create_bootstrap_bundle(
        bundle_root,
        version="2.13.0",
        source_commit="a" * 40,
    )
    install_root = tmp_path / "stable" / "current"
    install_root.mkdir(parents=True)
    installed = {"version": "2.14.0", "source_commit": "b" * 40}
    (install_root / module.BUILD_IDENTITY_FILE_NAME).write_text(
        json.dumps(installed),
        encoding="utf-8",
    )
    (install_root / "previous.txt").write_text("unchanged\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bootstrap_release_bundle.py",
            "--bundle-root",
            str(bundle_root),
            "--install-root",
            str(install_root),
        ],
    )
    monkeypatch.setattr(module, "resolve_install_python", lambda _: sys.executable)
    monkeypatch.setattr(
        module,
        "resolve_managed_data_dir",
        lambda *_args, **_kwargs: tmp_path / "managed-data",
    )
    monkeypatch.setattr(
        module,
        "place_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unconfirmed rollback changed product files")
        ),
    )

    with pytest.raises(SystemExit) as exited:
        module.main()

    assert exited.value.code == 1
    assert (install_root / "previous.txt").read_text(encoding="utf-8") == "unchanged\n"
    output = capsys.readouterr().out
    target = {"version": "2.13.0", "source_commit": "a" * 40}
    token = module.build_code_rollback_confirmation(installed, target)
    assert f"--confirm-code-rollback {token}" in output
    assert "does not restore or reverse memory data" in output


@pytest.mark.parametrize(
    ("current_version", "target_version", "operation"),
    [
        ("2.13.0", "2.14.0", "update"),
        ("2.14.0", "2.13.0", "rollback"),
    ],
)
def test_update_and_confirmed_code_rollback_share_verified_package_transaction(
    monkeypatch,
    tmp_path,
    current_version,
    target_version,
    operation,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        f"bootstrap_release_bundle_{operation}_success_module",
    )
    bundle_root = tmp_path / "bundle"
    target_commit = "a" * 40
    _create_bootstrap_bundle(
        bundle_root,
        version=target_version,
        source_commit=target_commit,
    )
    install_root = tmp_path / "stable" / "current"
    install_root.mkdir(parents=True)
    installed = {"version": current_version, "source_commit": "b" * 40}
    (install_root / module.BUILD_IDENTITY_FILE_NAME).write_text(
        json.dumps(installed),
        encoding="utf-8",
    )
    (install_root / "previous.txt").write_text("known product\n", encoding="utf-8")
    arguments = [
        "bootstrap_release_bundle.py",
        "--bundle-root",
        str(bundle_root),
        "--install-root",
        str(install_root),
    ]
    if operation == "rollback":
        target = {"version": target_version, "source_commit": target_commit}
        arguments.extend(
            [
                "--confirm-code-rollback",
                module.build_code_rollback_confirmation(installed, target),
            ]
        )
    monkeypatch.setattr(sys, "argv", arguments)
    monkeypatch.setattr(module, "resolve_install_python", lambda _: sys.executable)
    monkeypatch.setattr(
        module,
        "resolve_managed_data_dir",
        lambda *_args, **_kwargs: tmp_path / "managed-data",
    )
    monkeypatch.setattr(module, "prepare_existing_install", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "verify_installed_product", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **_: subprocess.CompletedProcess(command, 0),
    )

    with pytest.raises(SystemExit) as exited:
        module.main()

    assert exited.value.code == 0
    receipt = json.loads(
        (install_root / module.PACKAGE_RECEIPT_FILE_NAME).read_text(encoding="utf-8")
    )
    assert receipt["operation"] == operation
    assert receipt["status"] == "VERIFIED_COMPLETE"
    assert receipt["previous_version"] == current_version
    assert receipt["target_version"] == target_version
    assert receipt["checks"][1]["code"] == "RUNTIME_AGENT_RECALL_VERIFIED"
    backups = list(install_root.parent.glob("current.backup.*"))
    assert len(backups) == 1
    assert (backups[0] / "previous.txt").read_text(encoding="utf-8") == "known product\n"


def test_successful_customer_update_retains_the_exact_verified_previous_product(
    monkeypatch,
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_customer_update_retention_module",
    )
    bundle_root = tmp_path / "bundle"
    payload_root = bundle_root / "payload" / "elefante"
    install_root = tmp_path / "app" / "current"
    previous_identity = {
        "version": "2.13.0",
        "source_commit": "a" * 40,
        "source_clean": True,
        "release_channel": "release",
    }
    target_identity = {
        "version": "2.14.0",
        "source_commit": "b" * 40,
        "source_clean": True,
        "release_channel": "release",
    }
    _write_customer_identity(install_root, previous_identity)
    _write_customer_identity(payload_root, target_identity)
    (install_root / "previous.txt").write_text("verified previous\n", encoding="utf-8")
    (payload_root / "target.txt").write_text("new product\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bootstrap_release_bundle.py",
            "--bundle-root",
            str(bundle_root),
            "--install-root",
            str(install_root),
        ],
    )
    monkeypatch.setattr(module, "get_release_profile", lambda _manifest: "client")
    monkeypatch.setattr(
        module,
        "ensure_bundle_layout",
        lambda *_args, **_kwargs: payload_root,
    )
    monkeypatch.setattr(
        module,
        "load_build_identity",
        lambda *_args, **_kwargs: {"schema_version": 1, **target_identity},
    )
    monkeypatch.setattr(module, "resolve_install_python", lambda _value: sys.executable)
    monkeypatch.setattr(
        module,
        "resolve_managed_data_dir",
        lambda *_args, **_kwargs: tmp_path / "managed-data",
    )
    monkeypatch.setattr(module, "prepare_existing_install", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "verify_installed_product", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **_: subprocess.CompletedProcess(command, 0),
    )

    with pytest.raises(SystemExit) as exited:
        module.main()

    assert exited.value.code == 0
    assert module._read_customer_build_identity(install_root) == target_identity
    retained = module.describe_retained_code_rollback(install_root)
    assert retained["available"] is True
    assert retained["target_version"] == "2.13.0"
    backup_root = install_root.parent / retained["backup_name"]
    assert (backup_root / "previous.txt").read_text(encoding="utf-8") == "verified previous\n"
    receipt = json.loads(
        (install_root / module.PACKAGE_RECEIPT_FILE_NAME).read_text(encoding="utf-8")
    )
    assert receipt["rollback"] == "verified_previous_product_available"
    assert receipt["recoverable"] is True


def test_failed_update_verification_restores_and_fully_verifies_previous_product(
    monkeypatch,
    tmp_path,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_update_rollback_module",
    )
    bundle_root = tmp_path / "bundle"
    _create_bootstrap_bundle(
        bundle_root,
        version="2.14.0",
        source_commit="b" * 40,
    )
    install_root = tmp_path / "stable" / "current"
    install_root.mkdir(parents=True)
    previous_identity = {"version": "2.13.0", "source_commit": "a" * 40}
    (install_root / module.BUILD_IDENTITY_FILE_NAME).write_text(
        json.dumps(previous_identity),
        encoding="utf-8",
    )
    (install_root / "previous.txt").write_text("known good\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bootstrap_release_bundle.py",
            "--bundle-root",
            str(bundle_root),
            "--install-root",
            str(install_root),
        ],
    )
    monkeypatch.setattr(module, "resolve_install_python", lambda _: sys.executable)
    monkeypatch.setattr(
        module,
        "resolve_managed_data_dir",
        lambda *_args, **_kwargs: tmp_path / "managed-data",
    )
    monkeypatch.setattr(module, "prepare_existing_install", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "reactivate_previous_install", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module,
        "verify_installed_product",
        lambda root, **_kwargs: json.loads(
            (Path(root) / module.BUILD_IDENTITY_FILE_NAME).read_text(encoding="utf-8")
        )["version"]
        == "2.13.0",
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **_: subprocess.CompletedProcess(command, 0),
    )

    with pytest.raises(SystemExit) as exited:
        module.main()

    assert exited.value.code == 1
    assert (install_root / "previous.txt").read_text(encoding="utf-8") == "known good\n"
    assert json.loads(
        (install_root / module.BUILD_IDENTITY_FILE_NAME).read_text(encoding="utf-8")
    )["version"] == "2.13.0"
    failed_roots = list(install_root.parent.glob("current.failed.*"))
    assert len(failed_roots) == 1
    receipt = json.loads(
        (failed_roots[0] / module.PACKAGE_RECEIPT_FILE_NAME).read_text(encoding="utf-8")
    )
    assert receipt["operation"] == "update"
    assert receipt["status"] == "FAILED_ROLLED_BACK"
    assert receipt["rollback"] == "previous_product_restored"
    active_receipt = json.loads(
        (install_root / module.PACKAGE_RECEIPT_FILE_NAME).read_text(encoding="utf-8")
    )
    active_checks = {check["name"]: check for check in active_receipt["checks"]}
    assert active_receipt["status"] == "FAILED_ROLLED_BACK"
    assert active_receipt["rollback"] == "previous_product_restored"
    assert active_receipt["next_action"] == "create_support_report"
    assert active_receipt["failed_candidate_name"] is None
    assert active_checks["product_readiness"]["passed"] is True


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
    identity = {
        "schema_version": 1,
        "version": "9.9.9",
        "source_commit": "unavailable",
        "source_clean": False,
        "release_channel": "development",
    }
    (payload_root / "elefante-build.json").write_text(
        json.dumps(identity),
        encoding="utf-8",
    )
    (bundle_root / "installer-manifest.json").write_text(
        json.dumps(
            {
                "version": "9.9.9",
                "release_profile": "developer",
                "release_channel": "development",
                "source": {"commit": "unavailable", "clean": False},
            }
        ),
        encoding="utf-8",
    )
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


@pytest.mark.parametrize(
    ("rollback_product_ready", "expected_status"),
    [(True, "FAILED_ROLLED_BACK"), (False, "NEEDS_HUMAN")],
)
def test_failed_delegated_install_restores_previous_payload_and_preserves_diagnostics(
    monkeypatch,
    tmp_path,
    capsys,
    rollback_product_ready,
    expected_status,
):
    module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_failed_install_module",
    )
    bundle_root = tmp_path / "bundle"
    payload_root = bundle_root / "payload" / "elefante"
    (payload_root / "scripts" / "setup").mkdir(parents=True)
    (bundle_root / "scripts" / "setup").mkdir(parents=True)
    (payload_root / "scripts" / "setup" / "install.py").write_text(
        "", encoding="utf-8"
    )
    (payload_root / "requirements.txt").write_text("", encoding="utf-8")
    (payload_root / "requirements.lock").write_text("", encoding="utf-8")
    (payload_root / "candidate.txt").write_text("failed candidate\n", encoding="utf-8")
    (bundle_root / "scripts" / "setup" / "bootstrap_release_bundle.py").write_text(
        "", encoding="utf-8"
    )
    (bundle_root / "installer-manifest.json").write_text(
        json.dumps(
            {
                "version": "9.9.9",
                "release_profile": "developer",
                "release_channel": "development",
                "source": {"commit": "unavailable", "clean": False},
            }
        ),
        encoding="utf-8",
    )
    install_root = tmp_path / "stable" / "current"
    install_root.mkdir(parents=True)
    (install_root / "previous.txt").write_text("known good\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bootstrap_release_bundle.py",
            "--bundle-root",
            str(bundle_root),
            "--install-root",
            str(install_root),
        ],
    )
    monkeypatch.setattr(module, "resolve_install_python", lambda _: sys.executable)
    monkeypatch.setattr(
        module,
        "resolve_managed_data_dir",
        lambda *_args, **_kwargs: tmp_path / "managed-data",
    )
    monkeypatch.setattr(module, "prepare_existing_install", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "reactivate_previous_install", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module,
        "verify_installed_product",
        lambda *_args, **_kwargs: rollback_product_ready,
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **_: subprocess.CompletedProcess(command, 7),
    )

    with pytest.raises(SystemExit) as exited:
        module.main()

    assert exited.value.code == 7
    assert (install_root / "previous.txt").read_text(encoding="utf-8") == "known good\n"
    failed_roots = list(install_root.parent.glob("current.failed.*"))
    assert len(failed_roots) == 1
    assert (failed_roots[0] / "candidate.txt").read_text(encoding="utf-8") == "failed candidate\n"
    output = capsys.readouterr().out
    assert f"Failed candidate preserved at: {failed_roots[0]}" in output
    assert f"Summary file: {failed_roots[0] / module.INSTALL_SUMMARY_FILE_NAME}" in output
    receipt = json.loads(
        (failed_roots[0] / module.PACKAGE_RECEIPT_FILE_NAME).read_text(encoding="utf-8")
    )
    assert receipt["status"] == expected_status
    if rollback_product_ready:
        assert "Previous Elefante product restored and verified." in output
        active_receipt = json.loads(
            (install_root / module.PACKAGE_RECEIPT_FILE_NAME).read_text(
                encoding="utf-8"
            )
        )
        assert active_receipt["status"] == "FAILED_ROLLED_BACK"
        assert active_receipt["next_action"] == "create_support_report"
        assert active_receipt["failed_candidate_name"] is None
    else:
        assert "full product verification failed" in output


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
    assert "elefante-installer-macOS/payload/elefante/elefante-build.json" in names
    assert "elefante-installer-macOS/payload/elefante/requirements.lock" in names
    assert "elefante-installer-macOS/payload/elefante/src/dashboard/ui/dist/index.html" in names
    assert '"entrypoints": [\n    "Install Elefante.command",\n    "install.sh"\n  ]' in manifest
    assert '"release_profile": "developer"' in manifest
    assert '"release_channel": "development"' in manifest
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
