# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_installer_gui.py
# VERSION : 2.9.1
# CHANGED : 2026-04-16
# PROVES  : Installer GUI recovery-file routing stays aligned with the bundle
#           bootstrap contract and progress markers do not double-count.
#           InstallerApp class is importable (BUG-019 guard).
#           No bare tk.Label with bg= overrides (BUG-020 guard).
# RUN     : pytest tests/test_installer_gui.py -v
# WHEN    : After changes to scripts/ci/installer_gui.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import importlib.util
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
    assert 'button.isEnabled = false' in swift_source
    assert 'processArguments.append(contentsOf: ["--host", host])' not in swift_source
