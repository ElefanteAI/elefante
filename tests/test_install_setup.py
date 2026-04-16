# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_install_setup.py
# VERSION : 2.7.2
# CHANGED : 2026-04-16
# PROVES  : Installer instrumentation stays truthful: bundled dashboard assets
#           are preferred, stage status files are written, and seed-memory
#           injection fails when the memory guard blocks the write.
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