# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_backup_restore.py
# PROVES  : verified backup/restore preflight, path safety, integrity, and
#           recoverable replacement behavior for the durable data directory.
# RUN     : .venv/bin/python -m pytest tests/test_backup_restore.py -v
# WHEN    : After any change to scripts/lifecycle backup or restore behavior.
# ─────────────────────────────────────────────────────────────────────────────
"""Safety contracts for Elefante file-level backup and restore."""

import hashlib
import json
import sqlite3
import stat
import zipfile
from pathlib import Path

import pytest

from scripts.lifecycle.backup_elefante_data import MANIFEST_NAME, create_backup
from scripts.lifecycle.restore_elefante_data import inspect_archive, restore_archive


def _write_data(data_dir: Path, content: str) -> Path:
    state = data_dir / "chroma" / "state.db"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(content, encoding="utf-8")
    return state


def test_backup_writes_verified_manifest_and_excludes_nested_recovery_archives(tmp_path):
    data_dir = tmp_path / "home" / "data"
    _write_data(data_dir, "original memory")
    nested_backup = data_dir / "backups" / "factory_reset" / "old.zip"
    nested_backup.parent.mkdir(parents=True)
    nested_backup.write_bytes(b"old recovery archive")

    archive_path = create_backup(data_dir, tmp_path / "home" / "backups")

    assert inspect_archive(archive_path) == {
        "archive": archive_path.resolve(),
        "files": 1,
        "verified_manifest": True,
    }
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {"chroma/state.db", MANIFEST_NAME}


def test_backup_refuses_an_output_directory_inside_data(tmp_path):
    data_dir = tmp_path / "home" / "data"
    _write_data(data_dir, "original memory")

    with pytest.raises(ValueError, match="must not be inside"):
        create_backup(data_dir, data_dir / "archives")


def test_restore_is_dry_run_first_then_preserves_replaced_data(tmp_path):
    home = tmp_path / "home"
    data_dir = home / "data"
    state = _write_data(data_dir, "before backup")
    archive_path = create_backup(data_dir, home / "backups")
    state.write_text("current data", encoding="utf-8")

    preview = restore_archive(archive_path, data_dir)

    assert preview["applied"] is False
    assert preview["existing_data"] is True
    assert state.read_text(encoding="utf-8") == "current data"

    result = restore_archive(archive_path, data_dir, apply=True)

    assert result["applied"] is True
    assert (data_dir / "chroma" / "state.db").read_text(encoding="utf-8") == "before backup"
    assert result["previous_data"] is not None
    assert (result["previous_data"] / "chroma" / "state.db").read_text(encoding="utf-8") == "current data"


def test_backup_restore_preserves_the_opt_in_sqlite_vector_store_file(tmp_path):
    home = tmp_path / "home"
    data_dir = home / "data"
    database = data_dir / "vector" / "memories.sqlite3"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE memory (content TEXT NOT NULL)")
        connection.execute("INSERT INTO memory (content) VALUES (?)", ("before backup",))

    archive_path = create_backup(data_dir, home / "backups")
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE memory SET content = ?", ("current data",))

    result = restore_archive(archive_path, data_dir, apply=True)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT content FROM memory").fetchone() == ("before backup",)
    assert result["previous_data"] is not None
    with sqlite3.connect(result["previous_data"] / "vector" / "memories.sqlite3") as connection:
        assert connection.execute("SELECT content FROM memory").fetchone() == ("current data",)


def test_restore_rejects_unsafe_zip_members_without_touching_data(tmp_path):
    home = tmp_path / "home"
    data_dir = home / "data"
    state = _write_data(data_dir, "current data")
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.txt", "unsafe")

    with pytest.raises(ValueError, match="Unsafe archive member path"):
        restore_archive(archive_path, data_dir)

    assert state.read_text(encoding="utf-8") == "current data"
    assert not (tmp_path / "outside.txt").exists()


def test_restore_rejects_symlinks_and_checksum_tampering_before_mutation(tmp_path):
    home = tmp_path / "home"
    data_dir = home / "data"
    state = _write_data(data_dir, "current data")
    symlink_archive = tmp_path / "symlink.zip"
    with zipfile.ZipFile(symlink_archive, "w") as archive:
        member = zipfile.ZipInfo("link")
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(member, "target")
    with pytest.raises(ValueError, match="symlink"):
        restore_archive(symlink_archive, data_dir)

    tampered_archive = tmp_path / "tampered.zip"
    body = b"backup content"
    with zipfile.ZipFile(tampered_archive, "w") as archive:
        archive.writestr("chroma/state.db", body)
        archive.writestr(
            MANIFEST_NAME,
            json.dumps(
                {
                    "format": "elefante-data-backup",
                    "format_version": 1,
                    "files": [
                        {
                            "path": "chroma/state.db",
                            "size": len(body),
                            "sha256": hashlib.sha256(b"different content").hexdigest(),
                        }
                    ],
                }
            ),
        )
    with pytest.raises(ValueError, match="integrity check failed"):
        restore_archive(tampered_archive, data_dir)

    assert state.read_text(encoding="utf-8") == "current data"


def test_discard_requires_explicit_confirmation_after_verified_staging(tmp_path):
    home = tmp_path / "home"
    data_dir = home / "data"
    state = _write_data(data_dir, "before backup")
    archive_path = create_backup(data_dir, home / "backups")
    state.write_text("current data", encoding="utf-8")

    with pytest.raises(ValueError, match="confirm DISCARD"):
        restore_archive(archive_path, data_dir, apply=True, discard_existing=True)

    result = restore_archive(
        archive_path,
        data_dir,
        apply=True,
        discard_existing=True,
        discard_confirmation="DISCARD",
    )

    assert result["previous_data"] is None
    assert (data_dir / "chroma" / "state.db").read_text(encoding="utf-8") == "before backup"
