# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_installer_gui.py
# PROVES  : Installer GUI recovery-file routing stays aligned with the bundle
#           bootstrap contract and progress markers do not double-count.
#           InstallerApp class is importable (BUG-019 guard).
#           No bare tk.Label with bg= overrides (BUG-020 guard).
# RUN     : pytest tests/test_installer_gui.py -v
# WHEN    : After changes to scripts/ci/installer_gui.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gui_installer_artifact_paths_match_bootstrap_contract(tmp_path):
    gui_module = _load_module(ROOT / "scripts/ci/installer_gui.py", "installer_gui_module")
    bundle_module = _load_module(
        ROOT / "scripts/setup/bootstrap_release_bundle.py",
        "bootstrap_release_bundle_for_gui_test",
    )

    install_root = tmp_path / "stable" / "current"

    assert gui_module.build_install_artifact_paths(install_root) == bundle_module.build_install_artifact_paths(install_root)
    assert gui_module.render_failed_install_guidance(install_root) == [
        "Read these persisted installer files in order:",
        f"1. Summary file: {install_root / '.elefante-install-summary.txt'}",
        f"2. Status file: {install_root / '.elefante-install-status.txt'}",
        f"3. Log file: {install_root / '.elefante-install.log'}",
    ]


def test_process_stage_marker_ignores_repeated_markers():
    module = _load_module(ROOT / "scripts/ci/installer_gui.py", "installer_gui_stage_module")
    seen_markers: set[str] = set()

    advance, status = module.process_stage_marker("[Step 2] Creating virtual environment...", seen_markers)
    assert advance == 1
    assert status == "Installing: Creating virtual environment"

    advance, status = module.process_stage_marker("[Step 2] Creating virtual environment...", seen_markers)
    assert advance == 0
    assert status is None


def test_gui_labels_an_existing_product_as_repair(tmp_path):
    module = _load_module(ROOT / "scripts/ci/installer_gui.py", "installer_gui_copy_module")
    install_root = tmp_path / "current"

    assert module.installer_operation_copy(install_root)["title"] == "Install Elefante"

    install_root.mkdir()
    copy = module.installer_operation_copy(install_root)
    assert copy["title"] == "Repair Elefante"
    assert copy["ready"] == "Ready to repair"
    assert "agent connection, and Recall are ready" in copy["complete"]


def test_gui_reads_the_managed_backup_path_from_the_package_owner(tmp_path):
    module = _load_module(
        ROOT / "scripts/ci/installer_gui.py",
        "installer_gui_managed_backup_module",
    )
    installer_dir = tmp_path / "bundle"
    bootstrap = installer_dir / "scripts" / "setup" / "bootstrap_release_bundle.py"
    bootstrap.parent.mkdir(parents=True)
    bootstrap.write_text("", encoding="utf-8")
    install_root = tmp_path / "app" / "current"
    managed_backup = tmp_path / "custom-product" / "backups"

    def runner(command, **_kwargs):
        assert command[-1] == "--print-managed-backup-path"
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"{managed_backup}\n",
            stderr="",
        )

    assert module.read_managed_backup_path(
        installer_dir,
        install_root,
        runner=runner,
    ) == managed_backup


def test_gui_builds_unique_project_specs_without_duplicate_paths(tmp_path):
    module = _load_module(ROOT / "scripts/ci/installer_gui.py", "installer_gui_projects_module")
    first = tmp_path / "company-a" / "product"
    second = tmp_path / "company-b" / "product"
    first.mkdir(parents=True)
    second.mkdir(parents=True)

    specs = module.build_project_specs([first, first, second])

    assert specs == [f"product={first.resolve()}", f"product 2={second.resolve()}"]


def test_gui_uses_package_description_for_update_and_code_rollback(tmp_path):
    module = _load_module(ROOT / "scripts/ci/installer_gui.py", "installer_gui_update_copy_module")
    install_root = tmp_path / "current"
    install_root.mkdir()

    update = module.installer_operation_copy(
        install_root,
        {
            "operation": "update",
            "current_version": "2.13.0",
            "target_version": "2.14.0",
            "retained_rollback": {
                "available": True,
                "current_version": "2.13.0",
                "target_version": "2.12.3",
                "confirmation_token": "retained-token",
            },
        },
    )
    assert update["title"] == "Update Elefante"
    assert update["ready"] == "Ready to update"
    assert update["complete"].startswith("Update verified")
    assert update["retained_rollback_available"] == "true"
    assert update["retained_rollback_token"] == "retained-token"

    rollback = module.installer_operation_copy(
        install_root,
        {
            "operation": "rollback",
            "current_version": "2.14.0",
            "target_version": "2.13.0",
            "confirmation_token": "token-bound-to-both-builds",
        },
    )
    assert rollback["title"] == "Roll Back Elefante"
    assert rollback["confirmation_token"] == "token-bound-to-both-builds"
    assert rollback["complete"].startswith("Code rollback verified")


def test_gui_reads_operation_from_the_package_transaction_owner(tmp_path):
    module = _load_module(ROOT / "scripts/ci/installer_gui.py", "installer_gui_probe_module")
    installer_dir = tmp_path / "bundle"
    bootstrap = installer_dir / "scripts" / "setup" / "bootstrap_release_bundle.py"
    bootstrap.parent.mkdir(parents=True)
    bootstrap.write_text("", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "operation": "rollback",
        "current_version": "2.14.0",
        "target_version": "2.13.0",
        "confirmation_token": "bound-token",
    }
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload))

    result = module.read_package_operation(
        installer_dir,
        tmp_path / "stable" / "current",
        runner=runner,
    )

    assert result == payload
    assert "--describe-operation" in calls[0][0]
    assert calls[0][1]["timeout"] == 15


def test_gui_reads_exact_data_preserving_uninstall_from_package_owner(tmp_path):
    module = _load_module(ROOT / "scripts/ci/installer_gui.py", "installer_gui_uninstall_probe_module")
    installer_dir = tmp_path / "bundle"
    bootstrap = installer_dir / "scripts" / "setup" / "bootstrap_release_bundle.py"
    bootstrap.parent.mkdir(parents=True)
    bootstrap.write_text("", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "operation": "uninstall",
        "available": True,
        "confirmation_token": "state-bound-token",
        "data_effect": "preserved",
    }
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload))

    result = module.read_package_uninstall(
        installer_dir,
        tmp_path / "stable" / "current",
        runner=runner,
    )

    assert result == payload
    assert "--describe-uninstall" in calls[0][0]
    assert calls[0][1]["timeout"] == 15


def test_installer_app_class_is_importable():
    """Guard: InstallerApp must be syntactically constructable without crashing on import. (BUG-019)"""
    module = _load_module(ROOT / "scripts/ci/installer_gui.py", "installer_gui_class_module")
    assert hasattr(module, "InstallerApp")
    assert hasattr(module.InstallerApp, "_build_ui")
    assert hasattr(module.InstallerApp, "_configure_styles")


def test_installer_app_has_no_bg_overrides_on_ttk_labels():
    """Guard: bare bg= on tk.Label causes invisible text on macOS Aqua. (BUG-020)"""
    import ast
    src = (ROOT / "scripts/ci/installer_gui.py").read_text()
    tree = ast.parse(src)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            is_bare_tk_label = (
                isinstance(func, ast.Attribute) and func.attr == "Label"
                and isinstance(func.value, ast.Name) and func.value.id == "tk"
            )
            if is_bare_tk_label:
                for kw in node.keywords:
                    if kw.arg == "bg":
                        violations.append(f"line {node.lineno}: tk.Label with bg=")
    assert violations == [], f"BUG-020 risk: {violations}"


def test_native_installer_and_python_engine_share_host_ids():
    host_module = _load_module(
        ROOT / "scripts/setup/host_selection.py",
        "installer_host_selection_module",
    )
    swift_source = (ROOT / "scripts/ci/installer_app.swift").read_text(encoding="utf-8")

    for host in host_module.SUPPORTED_HOSTS:
        assert f'id: "{host}"' in swift_source
    assert 'let isCertified = host.id == "codex"' in swift_source
    assert 'button.isEnabled = host.detected && !isCertified' in swift_source
    assert 'processArguments.append(contentsOf: ["--host", host])' in swift_source
    assert "Codex is the first certified connection and is required" in swift_source
    assert "Optional host failures do not block the certified setup" in swift_source
    assert 'selectedHosts.contains("codex")' in swift_source
    assert "Backups:" in swift_source
    assert '"--print-managed-backup-path"' in swift_source
    assert '"--describe-operation"' in swift_source
    assert '"--confirm-code-rollback"' in swift_source
    assert '"--rollback-retained"' in swift_source
    assert '"--describe-uninstall"' in swift_source
    assert '"--uninstall"' in swift_source
    assert 'case "Update"' in swift_source
    assert 'case "Uninstall"' in swift_source
    assert "Your memories will not be restored or reversed" in swift_source
    assert "Your memories remain on this Mac for reinstall" in swift_source
    assert "Choose where Elefante may remember" in swift_source
    assert 'processArguments.append(contentsOf: ["--project", project])' in swift_source
    assert "disposable Recall and local backup included" in swift_source

    python_source = (ROOT / "scripts/ci/installer_gui.py").read_text(encoding="utf-8")
    assert "def default_backup_path()" in python_source
    assert "def read_managed_backup_path(" in python_source
    assert '"--print-managed-backup-path"' in python_source
    assert "Backups:" in python_source
    assert '"--rollback-retained"' in python_source
    assert "Roll Back Previous Version" in python_source
    assert '"--describe-uninstall"' in python_source
    assert '"--uninstall"' in python_source
    assert "Your memories remain on this computer for reinstall" in python_source
    assert "Choose where Elefante may remember" in python_source
    assert 'cmd.extend(["--project", project])' in python_source
