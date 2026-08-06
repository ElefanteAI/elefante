# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_install_setup.py
# PROVES  : Installer lifecycle contracts: state tracking, daemon service,
#           host registration ownership/refresh/rollback, safe uninstall,
#           dependency bootstrap, and seed-memory guard behavior.
# RUN     : pytest tests/test_install_setup.py -v
# WHEN    : After changes to scripts/setup/, scripts/lifecycle/, or installer
#           ownership logic.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import zipfile

import pytest
from packaging.requirements import Requirement


ROOT = Path(__file__).resolve().parents[1]


def test_installer_entrypoint_starts_without_product_dependencies():
    """A clean machine must reach installer setup before dependencies exist."""
    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "scripts/setup/install.py"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--release-profile" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr


def test_client_health_checks_customer_baseline_without_developer_sdd(monkeypatch):
    from scripts.verify import verify_health
    from src.core.directive_store import CLIENT_SYSTEM_DIRECTIVE_DEFINITIONS

    class Orchestrator:
        async def ensure_system_baseline(self):
            return {"success": True}

    class DirectiveStore:
        def list_all(self):
            return [
                {"id": directive_id, "content": content}
                for directive_id, content in CLIENT_SYSTEM_DIRECTIVE_DEFINITIONS
            ]

    monkeypatch.setattr(verify_health, "get_orchestrator", Orchestrator)
    monkeypatch.setattr(verify_health, "get_directive_store", DirectiveStore)
    monkeypatch.setattr(verify_health, "is_client_runtime", lambda: True)

    result = asyncio.run(verify_health.check_system_baseline())

    assert result["status"] == "healthy"
    assert result["profile"] == "client"
    assert result["missing_directives"] == []
    assert result["developer_directives"] == []
    assert result["specifications"] == "not-applicable"


def test_requirements_pin_every_declared_direct_dependency():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    declared = [line.strip() for line in requirements if line.strip() and not line.lstrip().startswith("#")]
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")

    assert declared
    assert all("==" in dependency for dependency in declared), declared
    assert all(
        ">" not in dependency and "<" not in dependency and "~" not in dependency
        for dependency in declared
    ), declared
    assert "uv pip compile --universal --generate-hashes" in lock
    assert "--hash=sha256:" in lock
    assert all(dependency in lock for dependency in declared), declared


def _runtime_requirements() -> list[str]:
    values: list[str] = []
    active = "runtime"
    for raw_line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("# Development Dependencies"):
            active = "development"
            continue
        if active == "runtime" and line and not line.startswith("#"):
            values.append(line)
    return values


def test_client_runtime_requirements_match_the_product_runtime_contract():
    client_requirements = [
        line.strip()
        for line in (ROOT / "requirements.client.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert set(client_requirements) == set(_runtime_requirements())
    assert not {
        "black==26.3.1",
        "mypy==1.20.2",
        "pytest==9.0.3",
        "pytest-asyncio==1.4.0",
        "ruff==0.1.15",
    } & set(client_requirements)


def test_isolated_package_wheel_preserves_src_runtime_contract(tmp_path):
    """The installable wheel must match the checkout's `python -m src...` contract."""
    package_root = tmp_path / "package"
    package_root.mkdir()
    for filename in ("setup.py", "README.md", "requirements.txt"):
        shutil.copy2(ROOT / filename, package_root / filename)
    shutil.copytree(ROOT / "src", package_root / "src")
    wheel_dir = tmp_path / "wheels"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            ".",
        ],
        cwd=package_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    wheel = next(wheel_dir.glob("elefante-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_path = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_path).decode("utf-8")

    assert {"src/__init__.py", "src/mcp/server.py", "src/core/sqlite_vector_store.py"} <= names
    metadata_requirements = [
        Requirement(line.removeprefix("Requires-Dist: "))
        for line in metadata.splitlines()
        if line.startswith("Requires-Dist: ") and "; extra ==" not in line
    ]
    actual = {requirement.name.lower(): str(requirement.specifier) for requirement in metadata_requirements}
    expected = {
        requirement.name.lower(): str(requirement.specifier)
        for requirement in map(Requirement, _runtime_requirements())
    }
    assert actual == expected

    installed = tmp_path / "installed"
    installed_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(installed),
            str(wheel),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert installed_result.returncode == 0, installed_result.stderr
    import_result = subprocess.run(
        [sys.executable, "-c", "from src.mcp import stdio_bridge; print(stdio_bridge.DEFAULT_DAEMON_URL)"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(installed)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert import_result.returncode == 0, import_result.stderr
    assert import_result.stdout.strip() == "http://127.0.0.1:8765/mcp/"


def test_readme_and_install_guide_match_current_runtime_and_host_contract():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install_guide = (ROOT / "docs/how-to/install.md").read_text(encoding="utf-8")
    run_guide = (ROOT / "docs/how-to/run-mcp-server.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    scripts_index = (ROOT / "scripts/README.md").read_text(encoding="utf-8")

    assert "mcp==1.28.1" in _runtime_requirements()
    assert "MCP 1.28.1" in readme
    assert "SQLite vectors" in readme
    for document in (readme, install_guide, run_guide):
        assert "1.23.1" not in document
    for host in ("Gemini CLI", "Claude Code", "Codex", "OpenClaw"):
        assert host in install_guide
        assert host in docs_index
    for adapter in (
        "configure_vscode_bob.py",
        "configure_cursor_kiro.py",
        "configure_antigravity.py",
        "configure_cli_agents.py",
    ):
        assert adapter in install_guide
    assert "transport-only" in run_guide
    assert "one durable store owner" in run_guide
    assert "configured embedded vector store" in scripts_index
    assert "SQLite snapshot support remains" not in scripts_index
    assert "configured embedded vector store" in install_guide
    assert "explicitly configured in `config.yaml`" in install_guide
    assert "would contain its own recovery directory" in scripts_index


def test_python_runtime_range_matches_installer_and_package_metadata():
    from src.utils.version import get_supported_python_message, is_supported_python

    installer = (ROOT / "scripts/setup/install.py").read_text(encoding="utf-8")
    setup_metadata = (ROOT / "setup.py").read_text(encoding="utf-8")

    assert not is_supported_python((3, 10))
    assert is_supported_python((3, 11))
    assert is_supported_python((3, 12))
    assert is_supported_python((3, 13))
    assert not is_supported_python((3, 14))
    assert "3.11, 3.12, or 3.13" in get_supported_python_message((3, 14))
    assert "Python 3.11, 3.12, or 3.13" in installer
    for version in ("3.11", "3.12", "3.13"):
        assert f"Programming Language :: Python :: {version}" in setup_metadata


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_dashboard_ui_prefers_bundled_assets(tmp_path):
    module = _load_module(ROOT / "scripts/setup/install.py", "install_setup_module")
    module.logger = module.Logger(spinner_enabled=False)

    bundled_index = tmp_path / "src" / "dashboard" / "ui" / "dist" / "index.html"
    bundled_index.parent.mkdir(parents=True, exist_ok=True)
    bundled_index.write_text("<html></html>", encoding="utf-8")

    assert module.build_dashboard_ui(tmp_path) == "bundled"


def test_install_state_tracker_writes_status_and_summary(tmp_path):
    module = _load_module(ROOT / "scripts/setup/install.py", "install_state_tracker_module")
    logger = module.Logger(spinner_enabled=False)
    status_file = tmp_path / "status.txt"
    summary_file = tmp_path / "summary.txt"
    log_file = tmp_path / "install.log"

    tracker = module.InstallStateTracker(
        root_dir=tmp_path,
        logger=logger,
        status_file=status_file,
        summary_file=summary_file,
        log_file=log_file,
    )

    tracker.start_stage("1", "Environment Setup", "Preparing repository virtual environment")
    tracker.complete_stage("1", "Environment Setup", "Using repository Python")
    tracker.finish(True, next_action="restart your IDE")

    status_contents = status_file.read_text(encoding="utf-8")
    summary_contents = summary_file.read_text(encoding="utf-8")

    assert "installer_state=completed" in status_contents
    assert "final_note=restart your IDE" in status_contents
    assert "1|Environment Setup|COMPLETE|Using repository Python" in summary_contents


def test_install_state_tracker_renders_persisted_file_routing(tmp_path):
    module = _load_module(ROOT / "scripts/setup/install.py", "install_state_tracker_routing_module")
    logger = module.Logger(spinner_enabled=False)
    status_file = tmp_path / "status.txt"
    summary_file = tmp_path / "summary.txt"
    log_file = tmp_path / "install.log"

    tracker = module.InstallStateTracker(
        root_dir=tmp_path,
        logger=logger,
        status_file=status_file,
        summary_file=summary_file,
        log_file=log_file,
    )

    lines = tracker.render_persisted_file_routing()

    assert lines[0] == "Read these persisted installer files in order:"
    assert str(summary_file) in lines[1]
    assert str(status_file) in lines[2]
    assert str(log_file) in lines[3]


def test_install_dependencies_bootstraps_pip_when_missing(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/setup/install.py", "install_setup_pip_bootstrap_module")
    module.logger = module.Logger(spinner_enabled=False)

    calls: list[list[str]] = []
    pip_version_checks = 0

    def fake_run_command(cmd, cwd=None, shell=False, env=None):
        nonlocal pip_version_checks
        del cwd, shell, env
        calls.append(cmd)

        if cmd[2:] == ["pip", "--version"]:
            pip_version_checks += 1
            return pip_version_checks > 1

        if cmd[2:] == ["ensurepip", "--upgrade"]:
            return True

        if cmd[2:] == ["pip", "install", "--upgrade", "pip"]:
            return True

        if cmd[2:] == ["pip", "install", "--require-hashes", "-r", "requirements.lock"]:
            return True

        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(module, "run_command", fake_run_command)

    (tmp_path / "requirements.lock").write_text("example==1.0 --hash=sha256:example", encoding="utf-8")
    result = module.install_dependencies(tmp_path, "/tmp/venv/bin/python")

    assert result is True
    assert calls == [
        ["/tmp/venv/bin/python", "-m", "pip", "--version"],
        ["/tmp/venv/bin/python", "-m", "ensurepip", "--upgrade"],
        ["/tmp/venv/bin/python", "-m", "pip", "--version"],
        ["/tmp/venv/bin/python", "-m", "pip", "install", "--upgrade", "pip"],
        ["/tmp/venv/bin/python", "-m", "pip", "install", "--require-hashes", "-r", "requirements.lock"],
    ]


def test_install_dependencies_refuses_to_resolve_without_the_checked_in_lock(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/setup/install.py", "install_setup_missing_lock_module")
    module.logger = module.Logger(spinner_enabled=False)
    calls: list[list[str]] = []
    monkeypatch.setattr(module, "run_command", lambda command, **_: calls.append(command) or True)

    assert module.install_dependencies(tmp_path, "/tmp/venv/bin/python") is False
    assert calls == []


def test_client_install_dependencies_use_the_runtime_only_lock(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/setup/install.py", "install_setup_client_lock_module")
    module.logger = module.Logger(spinner_enabled=False)
    calls: list[list[str]] = []
    monkeypatch.setattr(module, "run_command", lambda command, **_: calls.append(command) or True)
    (tmp_path / "requirements.client.lock").write_text(
        "example==1.0 --hash=sha256:example", encoding="utf-8"
    )

    assert module.install_dependencies(tmp_path, "/tmp/venv/bin/python", "client") is True
    assert calls[-1] == [
        "/tmp/venv/bin/python",
        "-m",
        "pip",
        "install",
        "--require-hashes",
        "-r",
        "requirements.client.lock",
    ]


def test_daemon_service_renders_user_scope_macos_and_linux_units(tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/daemon_service.py", "daemon_service_module")
    mac_path = module.service_path(tmp_path, "Darwin")
    linux_path = module.service_path(tmp_path, "Linux")

    assert mac_path == tmp_path / "Library/LaunchAgents/ai.elefante.daemon.plist"
    assert linux_path == tmp_path / ".config/systemd/user/ai.elefante.daemon.service"
    assert "src.mcp.daemon" in module.render_service(tmp_path, "Darwin")
    assert "KeepAlive" in module.render_service(tmp_path, "Darwin")
    assert "src.mcp.daemon" in module.render_service(tmp_path, "Linux")
    assert "Restart=on-failure" in module.render_service(tmp_path, "Linux")

    windows_path = module.service_path(tmp_path, "Windows")
    windows_service = module.render_service(tmp_path, "Windows")
    assert windows_path == tmp_path / ".elefante/services/ai.elefante.daemon.xml"
    assert "LogonTrigger" in windows_service
    assert "RestartOnFailure" in windows_service
    assert "src.mcp.daemon" in windows_service


def test_daemon_service_status_reports_ownership_runtime_and_health(tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/daemon_service.py", "daemon_service_status_module")
    service = module.service_path(tmp_path, "Linux")
    service.parent.mkdir(parents=True)
    service.write_text(module.render_service(tmp_path, "Linux"), encoding="utf-8")
    module.record_emitted_file(service, "daemon-service", tmp_path)

    def runner(command, **_):
        assert command == ["systemctl", "--user", "is-active", "ai.elefante.daemon"]
        return subprocess.CompletedProcess(command, 0, stdout="active\n")

    status = module.service_status(
        tmp_path, "Linux", runner=runner, health_check=lambda: True
    )

    assert status == {
        "platform": "Linux",
        "service_file": str(service),
        "service_file_exists": True,
        "service_file_ownership": "owned",
        "service_runtime": "active",
        "daemon_health": True,
    }


def test_daemon_service_status_preserves_the_distinction_between_missing_and_modified(tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/daemon_service.py", "daemon_service_unowned_status_module")
    service = module.service_path(tmp_path, "Linux")
    status = module.service_status(
        tmp_path,
        "Linux",
        runner=lambda command, **_: subprocess.CompletedProcess(command, 3, stdout="inactive\n"),
        health_check=lambda: False,
    )
    assert status["service_file"] == str(service)
    assert status["service_file_ownership"] == "absent"
    assert status["service_runtime"] == "inactive"
    assert status["daemon_health"] is False

    service.parent.mkdir(parents=True)
    service.write_text("user managed", encoding="utf-8")
    modified = module.service_status(
        tmp_path,
        "Linux",
        runner=lambda command, **_: subprocess.CompletedProcess(command, 3, stdout="inactive\n"),
        health_check=lambda: False,
    )
    assert modified["service_file_ownership"] == "modified_or_untracked"


def test_daemon_install_preserves_an_untracked_or_modified_service(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/daemon_service.py", "daemon_install_preserve_module")
    home = tmp_path / "home"
    path = module.service_path(home, "Linux")
    path.parent.mkdir(parents=True)
    path.write_text("user managed service", encoding="utf-8")
    commands = []
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(module, "_run", lambda command, apply: commands.append((command, apply)))

    assert module.install(home, apply=True) == path
    assert path.read_text(encoding="utf-8") == "user managed service"
    assert commands == []


def test_daemon_service_cli_returns_nonzero_when_it_preserves_a_user_service(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/daemon_service.py", "daemon_install_conflict_cli_module")
    home = tmp_path / "home"
    path = module.service_path(home, "Linux")
    path.parent.mkdir(parents=True)
    path.write_text("user managed service", encoding="utf-8")
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(module.sys, "argv", ["daemon_service.py", "install"])

    with pytest.raises(SystemExit) as exited:
        module.main()

    assert exited.value.code == 2
    assert path.read_text(encoding="utf-8") == "user managed service"


def test_daemon_install_refreshes_only_a_manifest_owned_linux_service(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/daemon_service.py", "daemon_install_refresh_module")
    home = tmp_path / "home"
    path = module.service_path(home, "Linux")
    path.parent.mkdir(parents=True)
    path.write_text(module.render_service(home, "Linux"), encoding="utf-8")
    module.record_emitted_file(path, "daemon-service", home)
    commands = []
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(module, "_run", lambda command, apply: commands.append((command, apply)))

    assert module.install(home, apply=True) == path
    assert commands == [
        (["systemctl", "--user", "daemon-reload"], True),
        (["systemctl", "--user", "enable", "--now", "ai.elefante.daemon"], True),
        (["systemctl", "--user", "try-restart", "ai.elefante.daemon"], True),
    ]
    assert module.is_unchanged_emitted_file(path, home)


def test_daemon_install_refreshes_launchd_without_failing_on_an_absent_job(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/daemon_service.py", "daemon_install_launchd_refresh_module")
    home = tmp_path / "home"
    path = module.service_path(home, "Darwin")
    path.parent.mkdir(parents=True)
    path.write_text(module.render_service(home, "Darwin"), encoding="utf-8")
    module.record_emitted_file(path, "daemon-service", home)
    commands = []
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(module, "_run_optional", lambda command, apply: commands.append(("optional", command, apply)))
    monkeypatch.setattr(module, "_run", lambda command, apply: commands.append(("required", command, apply)))

    module.install(home, apply=False)

    assert commands == [
        ("optional", ["launchctl", "bootout", f"gui/{module.os.getuid()}", str(path)], False),
        ("required", ["launchctl", "bootstrap", f"gui/{module.os.getuid()}", str(path)], False),
    ]


def test_doctor_reports_ready_only_when_runtime_and_daemon_are_healthy(tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/doctor.py", "doctor_report_module")
    repo = tmp_path / "repo"
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    (repo / "config.yaml").write_text("app_name: elefante\n", encoding="utf-8")
    matrix = repo / "agents" / "manifests"
    matrix.mkdir(parents=True)
    (matrix / "ide-integration.yaml").write_text(
        "surfaces:\n  - id: codex\n    status: compatible\n  - id: preview-host\n    status: planned-v2.12\n  - id: openclaw\n    status: community\n",
        encoding="utf-8",
    )

    home = tmp_path / "home"
    manifest = home / ".elefante" / "install-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "files": {},
                "commands": {},
                "runtime": {
                    "app_root": str(repo),
                    "data_root": str(home / ".elefante" / "data"),
                    "scope": "customer",
                    "version": "9.9.9",
                },
            }
        ),
        encoding="utf-8",
    )

    report = module.build_report(
        repo_root=repo,
        home=home,
        service_inspector=lambda _: {
            "daemon_health": True,
            "service_runtime": "active",
            "service_file_ownership": "owned",
        },
        host_detector=lambda **_: set(),
        surface_inspector=lambda _: set(),
    )

    assert report["ready"] is True
    assert report["customer_ready"] is True
    assert report["diagnostics"] == []
    assert report["integrations"] == {
        "compatible": ["codex"],
        "preview": ["preview-host"],
        "community": ["generic-mcp-client", "openclaw"],
    }


def test_client_doctor_uses_runtime_host_contract_without_developer_manifest(tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/doctor.py", "doctor_client_report_module")
    repo = tmp_path / "repo"
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    (repo / "config.yaml").write_text("app_name: elefante\n", encoding="utf-8")
    home = tmp_path / "home"
    manifest = home / ".elefante" / "install-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "files": {},
                "commands": {},
                "runtime": {
                    "app_root": str(repo),
                    "data_root": str(home / ".elefante" / "data"),
                    "scope": "customer",
                    "version": "2.12.2",
                },
            }
        ),
        encoding="utf-8",
    )

    report = module.build_report(
        repo_root=repo,
        home=home,
        service_inspector=lambda _: {
            "daemon_health": True,
            "service_runtime": "active",
            "service_file_ownership": "owned",
        },
        host_detector=lambda **_: set(),
        surface_inspector=lambda _: set(),
    )

    assert report["ready"] is True
    assert report["customer_ready"] is True
    assert report["diagnostics"] == []
    assert report["integrations"]["compatible"] == sorted(module.SUPPORTED_HOSTS)


def test_doctor_reports_missing_runtime_and_invalid_manifest_without_mutating_it(tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/doctor.py", "doctor_diagnostics_module")
    repo = tmp_path / "repo"
    (repo / "agents" / "manifests").mkdir(parents=True)
    (repo / "agents" / "manifests" / "ide-integration.yaml").write_text("surfaces: []\n", encoding="utf-8")
    home = tmp_path / "home"
    manifest = home / ".elefante" / "install-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("not json", encoding="utf-8")

    report = module.build_report(
        repo_root=repo,
        home=home,
        service_inspector=lambda _: {"daemon_health": False, "service_runtime": "inactive"},
        host_detector=lambda **_: set(),
        surface_inspector=lambda _: set(),
    )

    assert report["ready"] is False
    assert set(report["diagnostics"]) == {
        "install_manifest_invalid",
        "repository_venv_missing",
        "repository_config_missing",
        "daemon_unreachable",
    }
    assert manifest.read_text(encoding="utf-8") == "not json"


def test_doctor_reports_owned_surfaces_without_exposing_host_commands(tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/doctor.py", "doctor_owned_surfaces_module")
    repo = tmp_path / "repo"
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    (repo / "config.yaml").write_text("app_name: elefante\n", encoding="utf-8")
    matrix = repo / "agents" / "manifests"
    matrix.mkdir(parents=True)
    (matrix / "ide-integration.yaml").write_text("surfaces: []\n", encoding="utf-8")
    home = tmp_path / "home"
    manifest = home / ".elefante" / "install-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"files":{"/private/config":{"surface":"gemini"}},'
        '"commands":{"openclaw:elefante":{"surface":"openclaw",'
        '"add":["secret-command"]}}}',
        encoding="utf-8",
    )

    report = module.build_report(
        repo_root=repo,
        home=home,
        service_inspector=lambda _: {"daemon_health": True, "service_runtime": "active"},
        host_detector=lambda **_: set(),
        surface_inspector=lambda _: set(),
    )
    rendered = module._render_text(report)

    assert report["installer_ownership"]["configured_surfaces"] == ["gemini", "openclaw"]
    assert "configured_surfaces=gemini,openclaw" in rendered
    assert "secret-command" not in rendered
    assert "/private/config" not in rendered


def test_doctor_cli_uses_readiness_for_its_exit_code_and_json_output(monkeypatch, capsys):
    module = _load_module(ROOT / "scripts/lifecycle/doctor.py", "doctor_cli_module")
    report = {
        "ready": False,
        "customer_ready": False,
        "repository": "/repo",
        "runtime": {"venv_python_exists": True, "config_exists": True},
        "daemon": {"daemon_health": False, "service_runtime": "inactive"},
        "installer_ownership": {"files": 0, "host_registrations": 0, "configured_surfaces": []},
        "host_coverage": {"detected": [], "verified": [], "uncovered": []},
        "integrations": {"compatible": [], "preview": [], "community": []},
        "diagnostics": ["daemon_unreachable"],
        "customer_diagnostics": ["runtime_installation_unrecorded"],
    }
    monkeypatch.setattr(module, "build_report", lambda: report)

    assert module.main(["--json"]) == 1
    assert __import__("json").loads(capsys.readouterr().out)["diagnostics"] == ["daemon_unreachable"]


def test_doctor_reports_detected_but_unconfigured_customer_hosts(tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/doctor.py", "doctor_host_coverage_module")
    repo = tmp_path / "repo"
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    (repo / "config.yaml").write_text("app_name: elefante\n", encoding="utf-8")
    matrix = repo / "agents" / "manifests"
    matrix.mkdir(parents=True)
    (matrix / "ide-integration.yaml").write_text("surfaces: []\n", encoding="utf-8")
    home = tmp_path / "home"
    manifest = home / ".elefante" / "install-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "files": {},
                "commands": {},
                "runtime": {
                    "app_root": str(repo),
                    "data_root": str(home / ".elefante" / "data"),
                    "scope": "customer",
                    "version": "9.9.9",
                },
            }
        ),
        encoding="utf-8",
    )

    report = module.build_report(
        repo_root=repo,
        home=home,
        service_inspector=lambda _: {
            "daemon_health": True,
            "service_runtime": "active",
            "service_file_ownership": "owned",
        },
        host_detector=lambda **_: {"codex", "cursor"},
        surface_inspector=lambda _: {"codex"},
    )

    assert report["ready"] is True
    assert report["customer_ready"] is False
    assert report["host_coverage"] == {
        "detected": ["codex", "cursor"],
        "verified": ["codex"],
        "uncovered": ["cursor"],
    }
    assert report["customer_diagnostics"] == ["detected_hosts_unconfigured"]


def test_vscode_adapter_uses_transport_only_bridge(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_vscode_bob.py", "vscode_bridge_module")
    target = tmp_path / "mcp.json"

    assert module.configure_vscode_mcp_json(
        target, tmp_path, "/tmp/python", manifest_home=tmp_path / "home"
    )
    server = __import__("json").loads(target.read_text(encoding="utf-8"))["servers"]["elefante"]
    assert server["args"] == ["-m", "src.mcp.stdio_bridge"]
    assert server["env"]["ELEFANTE_DAEMON_URL"] == "http://127.0.0.1:8765/mcp/"


def test_vscode_adapter_requires_explicit_manifest_home(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_vscode_bob.py", "vscode_manifest_scope_module")

    with pytest.raises(TypeError, match="manifest_home"):
        module.configure_vscode_mcp_json(tmp_path / "mcp.json", tmp_path, "/tmp/python")

    assert not (tmp_path / "mcp.json").exists()


def test_vscode_adapter_preserves_a_user_owned_elefante_entry(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_vscode_bob.py", "vscode_ownership_module")
    target = tmp_path / "mcp.json"
    home = tmp_path / "home"
    original = {"servers": {"elefante": {"command": "user"}}}
    target.write_text(__import__("json").dumps(original), encoding="utf-8")

    assert not module.configure_vscode_mcp_json(target, tmp_path, "/tmp/python", manifest_home=home)
    assert __import__("json").loads(target.read_text(encoding="utf-8")) == original
    assert not (home / ".elefante" / "install-manifest.json").exists()


def test_customer_vscode_adapter_adopts_a_legacy_elefante_runtime(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_vscode_bob.py", "vscode_legacy_module")
    target = tmp_path / "mcp.json"
    home = tmp_path / "home"
    target.write_text(
        '{"servers":{"elefante":{"command":"/old/python","args":["-m","src.mcp.server"]}}}',
        encoding="utf-8",
    )

    assert module.configure_vscode_mcp_json(
        target,
        tmp_path / "stable",
        "/stable/python",
        manifest_home=home,
        adopt_legacy=True,
    )
    entry = __import__("json").loads(target.read_text(encoding="utf-8"))["servers"]["elefante"]
    assert entry["command"] == "/stable/python"
    assert entry["args"] == ["-m", "src.mcp.stdio_bridge"]


def test_customer_vscode_adapter_does_not_adopt_a_foreign_named_server(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_vscode_bob.py", "vscode_foreign_module")
    target = tmp_path / "mcp.json"
    original = {"servers": {"elefante": {"command": "user", "args": ["serve"]}}}
    target.write_text(__import__("json").dumps(original), encoding="utf-8")

    assert not module.configure_vscode_mcp_json(
        target,
        tmp_path / "stable",
        "/stable/python",
        manifest_home=tmp_path / "home",
        adopt_legacy=True,
    )
    assert __import__("json").loads(target.read_text(encoding="utf-8")) == original


def test_host_selection_keeps_adapter_families_isolated():
    module = _load_module(ROOT / "scripts/setup/host_selection.py", "host_selection_module")

    selected = module.normalize_selected_hosts(["cursor", "codex"])

    assert module.select_family(selected, module.JSON_HOSTS) == {"cursor"}
    assert module.select_family(selected, module.CLI_HOSTS) == {"codex"}
    assert module.select_family(selected, module.VSCODE_FAMILY) == set()
    assert module.select_family(None, module.JSON_HOSTS) is None


def test_vscode_adapter_filters_paths_to_selected_host(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_vscode_bob.py", "vscode_selection_module")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(module.os, "name", "posix")
    monkeypatch.setattr(module.os, "uname", lambda: type("Uname", (), {"sysname": "Darwin"})())

    vscode_paths = module.get_settings_paths({"vscode-copilot"})
    bob_paths = module.get_settings_paths({"bob"})

    assert vscode_paths
    assert all(module._host_for_path(path) == "vscode-copilot" for path in vscode_paths)
    assert bob_paths
    assert all(module._host_for_path(path) == "bob" for path in bob_paths)


def test_antigravity_adapter_preserves_a_user_owned_elefante_entry(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_antigravity.py", "antigravity_ownership_module")
    target = tmp_path / "mcp_config.json"
    original = {"mcpServers": {"elefante": {"command": "user"}}}
    target.write_text(__import__("json").dumps(original), encoding="utf-8")
    monkeypatch.setattr(module, "get_antigravity_config_path", lambda: target)

    assert not module.configure_mcp([])
    assert __import__("json").loads(target.read_text(encoding="utf-8")) == original


def test_antigravity_adapter_writes_atomically_without_an_untracked_backup(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_antigravity.py", "antigravity_clean_write_module")
    home = tmp_path / "home"
    target = home / ".gemini" / "antigravity" / "mcp_config.json"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(module, "get_antigravity_config_path", lambda: target)

    assert module.configure_mcp([])
    assert target.is_file()
    assert not target.with_suffix(".json.bak").exists()


def test_bob_adapter_preserves_a_user_owned_elefante_entry(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_vscode_bob.py", "bob_ownership_module")
    target = tmp_path / "mcp_settings.json"
    original = {"mcpServers": {"elefante": {"command": "user"}}}
    target.write_text(__import__("json").dumps(original), encoding="utf-8")
    monkeypatch.setattr(module, "get_mcp_json_paths", lambda *_: [])
    monkeypatch.setattr(module, "get_settings_paths", lambda *_: [target])

    assert module.configure_mcp(["--vscode", "chat-settings"])
    assert __import__("json").loads(target.read_text(encoding="utf-8")) == original


def test_bob_adapter_creates_the_user_global_registry_for_a_detected_host(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_vscode_bob.py", "bob_global_module")
    home = tmp_path / "home"
    (home / ".bob").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    assert module.configure_mcp(["--host", "bob"])

    target = home / ".bob" / "settings" / "mcp_settings.json"
    entry = json.loads(target.read_text(encoding="utf-8"))["mcpServers"]["elefante"]
    assert entry["env"]["ELEFANTE_CLIENT_TOOL"] == "ibm-bob"
    manifest = _load_module(ROOT / "scripts/setup/install_manifest.py", "bob_global_manifest")
    assert manifest.configured_surfaces(home) == {"ibm-bob"}


def test_cursor_kiro_and_gemini_adapters_preserve_other_servers_and_emit_provenance(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cursor_kiro.py", "cursor_kiro_bridge_module")
    home = tmp_path / "home"
    cursor = home / ".cursor" / "mcp.json"
    kiro = home / ".kiro" / "settings" / "mcp.json"
    gemini = home / ".gemini" / "settings.json"
    cursor.parent.mkdir(parents=True)
    (home / ".kiro").mkdir(parents=True)
    (home / ".gemini").mkdir(parents=True)
    for config in (cursor, kiro, gemini):
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text('{"mcpServers":{"other":{"command":"other"}}}', encoding="utf-8")

    result = module.configure_detected_hosts(
        tmp_path,
        "/tmp/python",
        home=home,
        which=lambda binary: "/tmp/gemini" if binary == "gemini" else None,
    )

    assert result == {"cursor": True, "kiro": True, "gemini": True}
    for config, tool in ((cursor, "cursor"), (kiro, "kiro"), (gemini, "gemini")):
        servers = __import__("json").loads(config.read_text(encoding="utf-8"))["mcpServers"]
        assert servers["other"] == {"command": "other"}
        assert servers["elefante"]["args"] == ["-m", "src.mcp.stdio_bridge"]
        assert servers["elefante"]["env"]["ELEFANTE_CLIENT_TOOL"] == tool
        if tool == "gemini":
            assert "disabled" not in servers["elefante"]

    manifest = _load_module(ROOT / "scripts/setup/install_manifest.py", "cursor_kiro_manifest_module")
    removed, preserved = manifest.remove_unchanged_files(home=home, apply=True)
    assert set(removed) == {cursor, kiro, gemini}
    assert preserved == []
    for config in (cursor, kiro, gemini):
        assert __import__("json").loads(config.read_text(encoding="utf-8")) == {
            "mcpServers": {"other": {"command": "other"}}
        }


def test_json_host_adapter_never_replaces_a_user_owned_elefante_entry(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cursor_kiro.py", "json_host_ownership_module")
    config = tmp_path / "mcp.json"
    home = tmp_path / "home"
    original = {"mcpServers": {"other": {"command": "other"}, "elefante": {"command": "user"}}}
    config.write_text(__import__("json").dumps(original), encoding="utf-8")

    assert not module.configure_json_mcp(config, tmp_path, "/tmp/python", "cursor", manifest_home=home)
    assert __import__("json").loads(config.read_text(encoding="utf-8")) == original
    assert not (home / ".elefante" / "install-manifest.json").exists()


def test_customer_json_host_adapter_adopts_a_legacy_elefante_runtime(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cursor_kiro.py", "json_host_legacy_module")
    config = tmp_path / "mcp.json"
    home = tmp_path / "home"
    config.write_text(
        '{"mcpServers":{"elefante":{"command":"/old/python","args":["-m","src.mcp.server"]}}}',
        encoding="utf-8",
    )

    assert module.configure_json_mcp(
        config,
        tmp_path / "stable",
        "/stable/python",
        "cursor",
        manifest_home=home,
        adopt_legacy=True,
    )
    entry = __import__("json").loads(config.read_text(encoding="utf-8"))["mcpServers"]["elefante"]
    assert entry["command"] == "/stable/python"
    assert entry["args"] == ["-m", "src.mcp.stdio_bridge"]


def test_json_host_adapter_refreshes_only_its_unchanged_entry(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cursor_kiro.py", "json_host_refresh_module")
    config = tmp_path / "mcp.json"
    home = tmp_path / "home"
    config.write_text('{"mcpServers":{"other":{"command":"other"}}}', encoding="utf-8")

    assert module.configure_json_mcp(config, tmp_path, "/tmp/python-one", "cursor", manifest_home=home)
    assert module.configure_json_mcp(config, tmp_path, "/tmp/python-two", "cursor", manifest_home=home)
    servers = __import__("json").loads(config.read_text(encoding="utf-8"))["mcpServers"]
    assert servers["other"] == {"command": "other"}
    assert servers["elefante"]["command"] == "/tmp/python-two"

    servers["other"]["command"] = "user-edited"
    config.write_text(__import__("json").dumps({"mcpServers": servers}), encoding="utf-8")
    before = config.read_text(encoding="utf-8")
    assert not module.configure_json_mcp(config, tmp_path, "/tmp/python-three", "cursor", manifest_home=home)
    assert config.read_text(encoding="utf-8") == before


def test_gemini_adapter_does_not_treat_an_antigravity_directory_as_gemini_cli(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cursor_kiro.py", "gemini_detection_module")
    home = tmp_path / "home"
    (home / ".gemini" / "antigravity").mkdir(parents=True)

    result = module.configure_detected_hosts(
        tmp_path, "/tmp/python", home=home, selected={"gemini"}, which=lambda _: None
    )

    assert result == {}
    assert not (home / ".gemini" / "settings.json").exists()


def test_cli_agent_registration_and_uninstall_require_matching_host_configuration(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cli_agents.py", "cli_agents_module")
    manifest = _load_module(ROOT / "scripts/setup/install_manifest.py", "cli_agents_manifest_module")
    configured = False
    calls = []

    def runner(command, **_):
        nonlocal configured
        calls.append(command)
        if command[2:4] == ["get", "elefante"]:
            return __import__("subprocess").CompletedProcess(
                command, 0 if configured else 1, stdout="registered-elefante\n" if configured else ""
            )
        if command[2] == "add":
            configured = True
            return __import__("subprocess").CompletedProcess(command, 0, stdout="")
        if command[2:4] == ["remove", "elefante"]:
            configured = False
            return __import__("subprocess").CompletedProcess(command, 0, stdout="")
        raise AssertionError(command)

    result = module.configure_cli_host(
        "codex", "codex", tmp_path, "/tmp/python", home=tmp_path / "home", runner=runner
    )

    assert result == "configured"
    add = next(command for command in calls if command[2] == "add")
    assert "ELEFANTE_CLIENT_TOOL=codex" in add
    assert add[-3:] == ["/tmp/python", "-m", "src.mcp.stdio_bridge"]
    removed, preserved = manifest.remove_unchanged_host_commands(
        home=tmp_path / "home", apply=True, runner=runner
    )
    assert removed == ["codex:elefante"]
    assert preserved == []
    assert configured is False


def test_openclaw_adapter_uses_native_registry_and_safe_manifest_ownership(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cli_agents.py", "openclaw_cli_agents_module")
    manifest = _load_module(ROOT / "scripts/setup/install_manifest.py", "openclaw_manifest_module")
    configured = False
    calls = []

    def runner(command, **_):
        nonlocal configured
        calls.append(command)
        if command[2:4] == ["show", "elefante"]:
            return __import__("subprocess").CompletedProcess(
                command, 0 if configured else 1, stdout='{"name":"elefante"}' if configured else ""
            )
        if command[2] == "add":
            configured = True
            return __import__("subprocess").CompletedProcess(command, 0, stdout="")
        if command[2:4] == ["unset", "elefante"]:
            configured = False
            return __import__("subprocess").CompletedProcess(command, 0, stdout="")
        raise AssertionError(command)

    home = tmp_path / "home"
    assert module.configure_cli_host("openclaw", "openclaw", tmp_path, "/tmp/python", home=home, runner=runner) == "configured"
    add = next(command for command in calls if command[2] == "add")
    assert add[:5] == ["openclaw", "mcp", "add", "elefante", "--command"]
    assert "ELEFANTE_CLIENT_TOOL=openclaw" in add
    removed, preserved = manifest.remove_unchanged_host_commands(home=home, apply=True, runner=runner)
    assert removed == ["openclaw:elefante"]
    assert preserved == []
    assert configured is False


def test_host_configuration_hash_canonicalizes_json_but_not_plain_text():
    manifest = _load_module(ROOT / "scripts/setup/install_manifest.py", "host_configuration_hash_module")
    first = '{"transport":{"env":{"B":"2","A":"1"}},"name":"elefante"}'
    reordered = '{"name":"elefante","transport":{"env":{"A":"1","B":"2"}}}'
    assert manifest.configuration_hash(first) == manifest.configuration_hash(reordered)
    assert manifest.configuration_hash("plain\n") != manifest.configuration_hash("plain")


def test_host_configuration_match_treats_a_malformed_command_manifest_as_unowned(tmp_path):
    manifest = _load_module(ROOT / "scripts/setup/install_manifest.py", "malformed_host_manifest_module")
    target = manifest.manifest_path(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_text('{"files": {}, "commands": []}', encoding="utf-8")

    assert manifest.matching_host_add_command("codex:elefante", "configuration", tmp_path) is None


def test_cli_agent_does_not_replace_an_existing_user_registration(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cli_agents.py", "cli_agents_existing_module")
    calls = []

    def runner(command, **_):
        calls.append(command)
        return __import__("subprocess").CompletedProcess(command, 0, stdout="user-managed\n")

    result = module.configure_cli_host(
        "claude-code", "claude", tmp_path, "/tmp/python", home=tmp_path / "home", runner=runner
    )

    assert result == "already-present"
    assert calls == [["claude", "mcp", "get", "elefante"]]


def test_customer_codex_adapter_adopts_a_legacy_elefante_runtime(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cli_agents.py", "cli_agents_legacy_module")
    state = {
        "name": "elefante",
        "transport": {
            "command": "/old/python",
            "args": ["-m", "src.mcp.server"],
            "env": {"PYTHONPATH": "/old/elefante"},
        },
    }
    calls = []

    def runner(command, **_):
        nonlocal state
        calls.append(command)
        if command[2:4] == ["get", "elefante"]:
            return subprocess.CompletedProcess(command, 0 if state else 1, stdout=json.dumps(state) if state else "")
        if command[2:4] == ["remove", "elefante"]:
            state = {}
            return subprocess.CompletedProcess(command, 0, stdout="")
        if command[2] == "add":
            state = {
                "name": "elefante",
                "transport": {
                    "command": command[-3],
                    "args": command[-2:],
                    "env": module.bridge_environment(tmp_path / "stable", "codex"),
                },
            }
            return subprocess.CompletedProcess(command, 0, stdout="")
        raise AssertionError(command)

    result = module.configure_cli_host(
        "codex",
        "codex",
        tmp_path / "stable",
        "/stable/python",
        home=tmp_path / "home",
        runner=runner,
        adopt_legacy=True,
    )

    assert result == "updated"
    assert state["transport"]["command"] == "/stable/python"
    assert any(command[2:4] == ["remove", "elefante"] for command in calls)


def test_cli_agent_refreshes_only_an_unchanged_installer_owned_registration(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cli_agents.py", "cli_agents_upgrade_module")
    state = "missing"
    calls = []

    def runner(command, **_):
        nonlocal state
        calls.append(command)
        if command[2:4] == ["get", "elefante"]:
            return subprocess.CompletedProcess(command, 0 if state != "missing" else 1, stdout=f"{state}\n")
        if command[2:4] == ["remove", "elefante"]:
            state = "missing"
            return subprocess.CompletedProcess(command, 0, stdout="")
        if command[2] == "add":
            state = "new" if any("/new-location" in part for part in command) else "old"
            return subprocess.CompletedProcess(command, 0, stdout="")
        raise AssertionError(command)

    home = tmp_path / "home"
    assert module.configure_cli_host(
        "codex", "codex", tmp_path / "old-location", "/tmp/python", home=home, runner=runner
    ) == "configured"
    assert module.configure_cli_host(
        "codex", "codex", tmp_path / "new-location", "/tmp/python", home=home, runner=runner
    ) == "updated"
    assert state == "new"
    assert any(command[2:4] == ["remove", "elefante"] for command in calls)


def test_cli_agent_restores_owned_registration_when_refresh_fails(tmp_path):
    module = _load_module(ROOT / "scripts/setup/configure_cli_agents.py", "cli_agents_rollback_module")
    state = "missing"

    def runner(command, **_):
        nonlocal state
        if command[2:4] == ["get", "elefante"]:
            return subprocess.CompletedProcess(command, 0 if state != "missing" else 1, stdout=f"{state}\n")
        if command[2:4] == ["remove", "elefante"]:
            state = "missing"
            return subprocess.CompletedProcess(command, 0, stdout="")
        if command[2] == "add":
            if any("/new-location" in part for part in command):
                return subprocess.CompletedProcess(command, 1, stdout="")
            state = "old"
            return subprocess.CompletedProcess(command, 0, stdout="")
        raise AssertionError(command)

    home = tmp_path / "home"
    assert module.configure_cli_host(
        "codex", "codex", tmp_path / "old-location", "/tmp/python", home=home, runner=runner
    ) == "configured"
    assert module.configure_cli_host(
        "codex", "codex", tmp_path / "new-location", "/tmp/python", home=home, runner=runner
    ) == "failed"
    assert state == "old"


@pytest.mark.integration
def test_codex_cli_registration_round_trip_uses_an_isolated_config_home():
    codex = shutil.which("codex")
    if not codex:
        pytest.skip("Codex CLI is not installed")
    module = _load_module(ROOT / "scripts/setup/configure_cli_agents.py", "codex_cli_roundtrip_module")
    manifest = _load_module(ROOT / "scripts/setup/install_manifest.py", "codex_cli_roundtrip_manifest_module")
    with tempfile.TemporaryDirectory(prefix="elefante-codex-") as temp_dir:
        temp_root = Path(temp_dir)
        codex_home = temp_root / "codex"
        codex_home.mkdir()
        environment = {**os.environ, "CODEX_HOME": str(codex_home)}

        def runner(command, **kwargs):
            return subprocess.run(command, env=environment, **kwargs)

        result = module.configure_cli_host(
            "codex",
            codex,
            ROOT,
            sys.executable,
            home=temp_root / "elefante-home",
            runner=runner,
        )
        assert result == "configured"
        current = runner([codex, "mcp", "get", "elefante", "--json"], capture_output=True, text=True, check=False)
        assert current.returncode == 0
        registration = json.loads(current.stdout)
        assert registration["transport"] == {
            "type": "stdio",
            "command": sys.executable,
            "args": ["-m", "src.mcp.stdio_bridge"],
            "env": module.bridge_environment(ROOT, "codex"),
            "env_vars": [],
            "cwd": None,
        }

        relocated = temp_root / "relocated-elefante"
        assert module.configure_cli_host(
            "codex",
            codex,
            relocated,
            sys.executable,
            home=temp_root / "elefante-home",
            runner=runner,
        ) == "updated"
        refreshed = runner([codex, "mcp", "get", "elefante", "--json"], capture_output=True, text=True, check=False)
        assert refreshed.returncode == 0
        assert json.loads(refreshed.stdout)["transport"]["env"] == module.bridge_environment(relocated, "codex")

        # A later user-owned replacement must never be removed by Elefante's
        # manifest-driven uninstall, even though it has the same server name.
        assert runner([codex, "mcp", "remove", "elefante"], capture_output=True, text=True, check=False).returncode == 0
        user_add = [
            codex,
            "mcp",
            "add",
            "elefante",
            "--",
            sys.executable,
            "-m",
            "src.mcp.stdio_bridge",
        ]
        assert runner(user_add, capture_output=True, text=True, check=False).returncode == 0

        removed, preserved = manifest.remove_unchanged_host_commands(
            home=temp_root / "elefante-home", apply=True, runner=runner
        )
        assert removed == []
        assert preserved == ["codex:elefante"]
        assert runner([codex, "mcp", "get", "elefante"], capture_output=True, text=True, check=False).returncode == 0

        # Restore the installer-owned registration, then prove normal removal.
        assert runner([codex, "mcp", "remove", "elefante"], capture_output=True, text=True, check=False).returncode == 0
        assert module.configure_cli_host(
            "codex",
            codex,
            relocated,
            sys.executable,
            home=temp_root / "elefante-home",
            runner=runner,
        ) == "configured"

        removed, preserved = manifest.remove_unchanged_host_commands(
            home=temp_root / "elefante-home", apply=True, runner=runner
        )
        assert removed == ["codex:elefante"]
        assert preserved == []
        assert runner([codex, "mcp", "get", "elefante"], capture_output=True, text=True, check=False).returncode != 0


def test_install_daemon_service_uses_explicit_apply_and_requires_health(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/setup/install.py", "install_daemon_service_module")
    calls = []
    monkeypatch.setattr(module, "run_command", lambda command, **_: calls.append(command) or True)

    assert module.install_daemon_service(tmp_path, "/tmp/python", health_waiter=lambda: True) is True
    assert calls == [["/tmp/python", str(tmp_path / "scripts/lifecycle/daemon_service.py"), "install", "--apply"]]


def test_install_daemon_service_fails_closed_when_service_never_becomes_healthy(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/setup/install.py", "install_daemon_service_health_failure_module")
    module.logger = module.Logger(spinner_enabled=False)
    monkeypatch.setattr(module, "run_command", lambda *_args, **_kwargs: True)

    assert module.install_daemon_service(tmp_path, "/tmp/python", health_waiter=lambda: False) is False


def test_daemon_health_check_requires_the_expected_loopback_payload():
    module = _load_module(ROOT / "scripts/setup/install.py", "daemon_health_check_module")

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return __import__("json").dumps(self.payload).encode("utf-8")

    expected = {
        "status": "ok",
        "service": "elefante-daemon",
        "transport": "streamable-http",
    }
    assert module.daemon_health_check(lambda *_args, **_kwargs: Response(expected)) is True
    assert module.daemon_health_check(lambda *_args, **_kwargs: Response({"status": "ok"})) is False


def test_wait_for_daemon_health_is_bounded_and_retries_until_ready():
    module = _load_module(ROOT / "scripts/setup/install.py", "wait_for_daemon_health_module")
    attempts = []

    def health_check():
        attempts.append(None)
        return len(attempts) == 3

    assert module.wait_for_daemon_health(
        health_check=health_check, clock=lambda: 0, sleeper=lambda _: None
    ) is True
    assert len(attempts) == 3

    ticks = iter((0, 0, 1))
    assert module.wait_for_daemon_health(
        timeout_seconds=0.5,
        health_check=lambda: False,
        clock=lambda: next(ticks),
        sleeper=lambda _: None,
    ) is False


def test_install_manifest_records_only_emitted_files(tmp_path):
    module = _load_module(ROOT / "scripts/setup/install_manifest.py", "install_manifest_module")
    emitted = tmp_path / "user-config" / "mcp.json"
    emitted.parent.mkdir()
    emitted.write_text("{}", encoding="utf-8")

    manifest = module.record_emitted_file(emitted, "vscode-copilot", home=tmp_path / "home")
    payload = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    assert payload["files"][str(emitted.resolve())]["surface"] == "vscode-copilot"
    assert payload["files"][str(emitted.resolve())]["sha256"] == module.file_hash(emitted)

    removed, preserved = module.remove_unchanged_files(home=tmp_path / "home", apply=True)
    assert removed == [emitted]
    assert preserved == []

    emitted.write_text("user edit", encoding="utf-8")
    module.record_emitted_file(emitted, "vscode-copilot", home=tmp_path / "home")
    emitted.write_text("user edit after install", encoding="utf-8")
    removed, preserved = module.remove_unchanged_files(home=tmp_path / "home", apply=True)
    assert removed == []
    assert preserved == [emitted]


def test_install_manifest_records_customer_runtime_without_losing_owned_surfaces(tmp_path):
    module = _load_module(ROOT / "scripts/setup/install_manifest.py", "runtime_manifest_module")
    home = tmp_path / "home"
    emitted = tmp_path / "mcp.json"
    emitted.write_text("{}", encoding="utf-8")
    module.record_emitted_file(emitted, "vscode-copilot", home=home)

    target = module.record_runtime_installation(
        app_root=tmp_path / "app" / "current",
        data_root=home / ".elefante" / "data",
        version="9.9.9",
        scope="customer",
        home=home,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 2
    assert payload["runtime"]["scope"] == "customer"
    assert module.read_runtime_installation(home)["version"] == "9.9.9"
    assert module.configured_surfaces(home) == {"vscode-copilot"}


def test_json_surface_verification_ignores_unrelated_user_settings(tmp_path):
    module = _load_module(ROOT / "scripts/setup/install_manifest.py", "surface_verification_module")
    home = tmp_path / "home"
    config = tmp_path / "mcp.json"
    config.write_text('{"servers":{"elefante":{"command":"bridge"}}}', encoding="utf-8")
    module.record_emitted_json_entry(
        config,
        "vscode-copilot",
        ("servers", "elefante"),
        created=True,
        home=home,
    )

    config.write_text(
        '{"servers":{"elefante":{"command":"bridge"},"other":{"command":"other"}}}',
        encoding="utf-8",
    )

    assert module.configured_surfaces(home) == {"vscode-copilot"}
    removed, preserved = module.remove_unchanged_files(home=home, apply=True)
    assert removed == []
    assert preserved == [config]


def test_host_detection_and_customer_runtime_conflict_are_explicit(tmp_path):
    hosts = _load_module(ROOT / "scripts/setup/host_selection.py", "host_detection_module")
    install = _load_module(ROOT / "scripts/setup/install.py", "install_scope_module")
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    (home / ".gemini" / "antigravity").mkdir(parents=True)
    (home / "Library" / "Application Support" / "Code" / "User").mkdir(parents=True)
    binaries = {"codex": "/usr/local/bin/codex"}

    detected = hosts.detect_supported_hosts(
        home=home,
        system="Darwin",
        which=lambda command: binaries.get(command),
    )

    assert detected == {"antigravity", "codex", "cursor", "vscode-copilot"}
    selected, required = install.installation_host_plan(
        installation_scope="customer",
        requested_hosts={"codex"},
        detected_hosts=detected,
    )
    assert selected is None
    assert required == detected
    selected, required = install.installation_host_plan(
        installation_scope="developer",
        requested_hosts={"codex"},
        detected_hosts=detected,
    )
    assert selected == {"codex"}
    assert required == {"codex"}
    assert install.uncovered_required_hosts(detected, {"antigravity", "codex", "vscode-copilot"}) == [
        "cursor"
    ]
    assert install.developer_runtime_conflicts_with_customer(
        installation_scope="developer",
        root_dir=tmp_path / "developer-checkout",
        existing_runtime={
            "app_root": str(tmp_path / "app" / "current"),
            "data_root": str(home / ".elefante" / "data"),
            "scope": "customer",
            "version": "9.9.9",
        },
    )


def test_uninstall_removes_only_owned_json_entry_from_shared_config(tmp_path):
    module = _load_module(ROOT / "scripts/setup/install_manifest.py", "install_manifest_json_entry_module")
    config = tmp_path / "mcp.json"
    config.write_text(
        '{"servers":{"other":{"command":"other"},"elefante":{"command":"elefante"}}}',
        encoding="utf-8",
    )
    home = tmp_path / "home"
    module.record_emitted_json_entry(
        config, "vscode-copilot", ("servers", "elefante"), created=False, home=home
    )

    removed, preserved = module.remove_unchanged_files(home=home, apply=True)

    assert removed == [config]
    assert preserved == []
    assert __import__("json").loads(config.read_text(encoding="utf-8")) == {
        "servers": {"other": {"command": "other"}}
    }


def test_uninstall_deletes_empty_installer_created_json_config(tmp_path):
    module = _load_module(ROOT / "scripts/setup/install_manifest.py", "install_manifest_created_json_module")
    config = tmp_path / "mcp.json"
    config.write_text('{"servers":{"elefante":{"command":"elefante"}}}', encoding="utf-8")
    home = tmp_path / "home"
    module.record_emitted_json_entry(
        config, "vscode-copilot", ("servers", "elefante"), created=True, home=home
    )

    removed, preserved = module.remove_unchanged_files(home=home, apply=True)

    assert removed == [config]
    assert preserved == []
    assert not config.exists()


def test_complete_uninstall_can_clear_customer_runtime_identity(tmp_path):
    module = _load_module(ROOT / "scripts/setup/install_manifest.py", "clear_runtime_module")
    home = tmp_path / "home"
    module.record_runtime_installation(
        app_root=tmp_path / "app" / "current",
        data_root=home / ".elefante" / "data",
        version="9.9.9",
        scope="customer",
        home=home,
    )

    module.clear_runtime_installation(home)

    assert module.read_runtime_installation(home) is None
    assert not module.manifest_path(home).exists()


def test_daemon_uninstall_preserves_modified_service_without_stopping_it(monkeypatch, tmp_path):
    module = _load_module(ROOT / "scripts/lifecycle/daemon_service.py", "daemon_uninstall_safety_module")
    home = tmp_path / "home"
    path = module.service_path(home, "Linux")
    path.parent.mkdir(parents=True)
    path.write_text(module.render_service(home, "Linux"), encoding="utf-8")
    module.record_emitted_file(path, "daemon-service", home)
    path.write_text("user-managed service", encoding="utf-8")
    commands = []
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(module, "_run", lambda command, apply: commands.append((command, apply)))

    module.uninstall(home, apply=True)

    assert commands == []
    assert path.read_text(encoding="utf-8") == "user-managed service"


@pytest.mark.asyncio
async def test_inject_seed_memory_returns_false_when_guard_blocks(monkeypatch):
    module = _load_module(ROOT / "scripts/setup/init_databases.py", "init_databases_test_module")

    class FakeOrchestrator:
        _last_rejection_reason = "Test-memory guard blocked this submission"

        async def search_memories(self, query):
            assert query == "Indigo-Echo"
            return []

        async def add_memory(self, **kwargs):
            assert kwargs["metadata"]["category"] == "system-test"
            return None

    import src.core.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module, "get_orchestrator", lambda: FakeOrchestrator())

    result = await module.inject_seed_memory()

    assert result is False


@pytest.mark.asyncio
async def test_database_verification_uses_configured_storage_paths(monkeypatch, tmp_path):
    """BUG-039: fresh SQLite installs must not report a retired Chroma path."""
    module = _load_module(ROOT / "scripts/setup/init_databases.py", "init_databases_paths_module")
    data_dir = tmp_path / "data"
    vector_dir = data_dir / "vector"
    graph_dir = data_dir / "kuzu_db"

    config = SimpleNamespace(
        elefante=SimpleNamespace(
            data_dir=str(data_dir),
            vector_store=SimpleNamespace(type="sqlite", persist_directory=str(vector_dir)),
            graph_store=SimpleNamespace(database_path=str(graph_dir)),
        )
    )

    events = []
    monkeypatch.setattr(module, "get_config", lambda: config)
    monkeypatch.setattr(module.logger, "info", lambda event, **values: events.append((event, values)))

    assert await module.verify_setup() is True
    paths_event = next(values for event, values in events if event == "Data directories")
    assert paths_event["vector_dir"] == str(vector_dir)
    assert paths_event["graph_dir"] == str(graph_dir)
    assert "chroma" not in paths_event["vector_dir"].lower()


@pytest.mark.asyncio
async def test_inject_seed_memory_payload_does_not_trip_test_memory_guard(monkeypatch):
    """BUG-021 regression: the installer's own seed injection must not match
    the test-memory guard. The guard exists to block E2E/persistence test
    artifacts from polluting the production graph. If the installer's seed
    tags or category match the guard, every fresh install fails at stage 3
    (Database Initialization) — which is exactly what shipped before v2.9.1.
    """
    module = _load_module(ROOT / "scripts/setup/init_databases.py", "init_databases_seed_payload_module")

    captured: dict = {}

    class CapturingOrchestrator:
        _last_rejection_reason = None

        async def search_memories(self, query):
            return []

        async def add_memory(self, **kwargs):
            captured.update(kwargs)

            class _StubMemory:
                id = "stub-seed-id"

            return _StubMemory()

    import src.core.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module, "get_orchestrator", lambda: CapturingOrchestrator())

    result = await module.inject_seed_memory()
    assert result is True, "Seed injection must succeed when the orchestrator accepts the payload"

    tags = {t.strip().lower() for t in captured.get("tags", []) if isinstance(t, str) and t.strip()}
    metadata = captured.get("metadata") or {}
    category = str(metadata.get("category") or "").strip().lower()
    namespace = str(metadata.get("namespace") or "").strip().lower()
    content = (captured.get("content") or "").strip().lower()

    blocking_tags = tags & {"test", "e2e"}
    assert not blocking_tags, (
        f"Seed tags must not include guard-blocked tags; found {sorted(blocking_tags)}. "
        f"Rename or remove these before shipping."
    )
    assert not any(t.startswith("hybrid_test_") for t in tags), "Seed tags must not start with 'hybrid_test_'"
    assert namespace != "test", "Seed metadata.namespace must not equal 'test'"
    assert category != "test", "Seed metadata.category must not equal 'test'"
    assert not category.startswith("hybrid_test_"), "Seed metadata.category must not start with 'hybrid_test_'"
    assert not content.startswith("elefante e2e test memory"), "Seed content must not open with 'elefante e2e test memory'"
    assert not content.startswith("hybrid search test memory"), "Seed content must not open with 'hybrid search test memory'"
    assert " test memory" not in content, "Seed content must not contain ' test memory'"
