# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_install_setup.py
# VERSION : 2.7.2
# CHANGED : 2026-04-17
# PROVES  : Installer instrumentation stays truthful: bundled dashboard assets
#           are preferred, stage status files are written, dependency setup
#           bootstraps pip when missing, and seed-memory injection fails
#           when the memory guard blocks the write.
# RUN     : pytest tests/test_install_setup.py -v
# WHEN    : After changes to scripts/setup/install.py or init_databases.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import importlib.util
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

        if cmd[2:] == ["pip", "install", "-r", "requirements.txt"]:
            return True

        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(module, "run_command", fake_run_command)

    result = module.install_dependencies(tmp_path, "/tmp/venv/bin/python")

    assert result is True
    assert calls == [
        ["/tmp/venv/bin/python", "-m", "pip", "--version"],
        ["/tmp/venv/bin/python", "-m", "ensurepip", "--upgrade"],
        ["/tmp/venv/bin/python", "-m", "pip", "--version"],
        ["/tmp/venv/bin/python", "-m", "pip", "install", "--upgrade", "pip"],
        ["/tmp/venv/bin/python", "-m", "pip", "install", "-r", "requirements.txt"],
    ]


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