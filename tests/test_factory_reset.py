# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_factory_reset.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PROVES  : reset_factory.py safety gates: dry-run behavior, backup creation,
#           confirmation gate, and correct data removal on apply.
# RUN     : pytest tests/test_factory_reset.py -v
# WHEN    : After any change to scripts/lifecycle/reset_factory.py.
# ─────────────────────────────────────────────────────────────────────────────
"""
Factory Reset Safety Tests
==========================
Validates scripts/lifecycle/reset_factory.py:
  - Dry-run does NOT touch data
  - Safety gates reject without ELEFANTE_PRIVILEGED + --confirm DELETE
  - Live reset moves databases to backup (never deletes)
  - Backup directory structure is correct
  - Clean state after reset (databases gone, backups present)

All tests run against an isolated temporary HOME directory.
Real user data is never touched.
"""

import os
import shutil
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the factory reset module under test
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.lifecycle.reset_factory import factory_reset, _targets, _backup_dir


@pytest.fixture()
def isolated_home(tmp_path):
    """Create a fake ~/.elefante/data with dummy databases."""
    fake_home = tmp_path / "fakehome"
    data_dir = fake_home / ".elefante" / "data"
    chroma_dir = data_dir / "chroma"
    kuzu_path = data_dir / "kuzu_db"

    # Seed fake database content
    chroma_dir.mkdir(parents=True)
    (chroma_dir / "chroma.sqlite3").write_text("fake-chroma-data")
    (chroma_dir / "collections").mkdir()

    data_dir.mkdir(parents=True, exist_ok=True)
    kuzu_path.write_text("fake-kuzu-data")

    # Patch Path.home() to return our fake home
    with patch("scripts.lifecycle.reset_factory.Path.home", return_value=fake_home):
        yield fake_home, chroma_dir, kuzu_path


class TestDryRun:
    """Dry-run must never modify anything."""

    def test_dry_run_leaves_databases_intact(self, isolated_home):
        fake_home, chroma_dir, kuzu_path = isolated_home

        result = factory_reset(apply=False, confirm="")
        assert result is True
        assert chroma_dir.exists(), "Dry-run must not touch ChromaDB"
        assert kuzu_path.exists(), "Dry-run must not touch KuzuDB"

    def test_dry_run_creates_no_backup(self, isolated_home):
        fake_home, chroma_dir, kuzu_path = isolated_home
        backup_root = fake_home / ".elefante" / "data" / "backups" / "factory_reset"

        factory_reset(apply=False, confirm="")
        assert not backup_root.exists(), "Dry-run must not create backup directory"


class TestSafetyGates:
    """All three safety gates must reject independently."""

    def test_rejects_without_privileged_env(self, isolated_home):
        """Missing ELEFANTE_PRIVILEGED=1 -> refuse."""
        with patch.dict(os.environ, {"ELEFANTE_PRIVILEGED": ""}, clear=False):
            result = factory_reset(apply=True, confirm="DELETE")
        assert result is False

    def test_rejects_with_wrong_confirm(self, isolated_home):
        """Wrong --confirm value -> refuse."""
        with patch.dict(os.environ, {"ELEFANTE_PRIVILEGED": "1"}, clear=False):
            result = factory_reset(apply=True, confirm="yes")
        assert result is False

    def test_rejects_empty_confirm(self, isolated_home):
        """Empty --confirm -> refuse."""
        with patch.dict(os.environ, {"ELEFANTE_PRIVILEGED": "1"}, clear=False):
            result = factory_reset(apply=True, confirm="")
        assert result is False

    def test_databases_survive_rejected_reset(self, isolated_home):
        """After any rejection, databases must still exist."""
        fake_home, chroma_dir, kuzu_path = isolated_home

        # Try all rejection paths
        with patch.dict(os.environ, {"ELEFANTE_PRIVILEGED": ""}, clear=False):
            factory_reset(apply=True, confirm="DELETE")
        with patch.dict(os.environ, {"ELEFANTE_PRIVILEGED": "1"}, clear=False):
            factory_reset(apply=True, confirm="wrong")

        assert chroma_dir.exists(), "Rejected reset must not touch ChromaDB"
        assert kuzu_path.exists(), "Rejected reset must not touch KuzuDB"


class TestLiveReset:
    """Actual reset with all gates satisfied."""

    def test_reset_moves_databases_to_backup(self, isolated_home):
        fake_home, chroma_dir, kuzu_path = isolated_home
        backup_root = fake_home / ".elefante" / "data" / "backups" / "factory_reset"

        with patch.dict(os.environ, {"ELEFANTE_PRIVILEGED": "1"}, clear=False):
            result = factory_reset(apply=True, confirm="DELETE")

        assert result is True
        assert not chroma_dir.exists(), "ChromaDB must be moved away"
        assert not kuzu_path.exists(), "KuzuDB must be moved away"
        assert backup_root.exists(), "Backup directory must be created"

        # Verify backups contain our data
        backup_items = list(backup_root.iterdir())
        assert len(backup_items) == 2, f"Expected 2 backups (chroma + kuzu), got {len(backup_items)}"

        backup_names = [item.name for item in backup_items]
        assert any("chroma" in name for name in backup_names), "ChromaDB backup missing"
        assert any("kuzu_db" in name for name in backup_names), "KuzuDB backup missing"

    def test_backup_preserves_original_content(self, isolated_home):
        fake_home, chroma_dir, kuzu_path = isolated_home
        backup_root = fake_home / ".elefante" / "data" / "backups" / "factory_reset"

        with patch.dict(os.environ, {"ELEFANTE_PRIVILEGED": "1"}, clear=False):
            factory_reset(apply=True, confirm="DELETE")

        # Find the chroma backup and check contents survived
        chroma_backup = [p for p in backup_root.iterdir() if "chroma" in p.name][0]
        assert (chroma_backup / "chroma.sqlite3").read_text() == "fake-chroma-data"

    def test_reset_on_already_clean_state(self, isolated_home):
        """Reset when databases already absent -> success, no crash."""
        fake_home, chroma_dir, kuzu_path = isolated_home

        # Remove databases manually first
        shutil.rmtree(chroma_dir)
        kuzu_path.unlink()

        with patch.dict(os.environ, {"ELEFANTE_PRIVILEGED": "1"}, clear=False):
            result = factory_reset(apply=True, confirm="DELETE")

        assert result is True, "Reset on clean state must succeed gracefully"

    def test_double_reset_does_not_crash(self, isolated_home):
        """Two consecutive resets must not crash (idempotent)."""
        with patch.dict(os.environ, {"ELEFANTE_PRIVILEGED": "1"}, clear=False):
            result1 = factory_reset(apply=True, confirm="DELETE")
            result2 = factory_reset(apply=True, confirm="DELETE")

        assert result1 is True
        assert result2 is True
