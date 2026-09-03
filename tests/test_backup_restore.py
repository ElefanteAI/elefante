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
import shutil
import sqlite3
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.lifecycle.backup_elefante_data import (
    MANIFEST_NAME,
    build_backup_manifest,
    create_backup,
    main as backup_main,
)
from scripts.lifecycle.restore_elefante_data import (
    inspect_archive,
    read_verified_manifest,
    restore_archive,
)
from scripts.debug.reset_kuzu_nuclear import nuclear_reset_kuzu


def _write_data(data_dir: Path, content: str) -> Path:
    state = data_dir / "chroma" / "state.db"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(content, encoding="utf-8")
    return state


def test_backup_cli_accepts_the_exact_managed_data_root(tmp_path):
    elefante_home = tmp_path / "home" / ".elefante"
    custom_data = tmp_path / "custom" / "elefante-data"
    backup_dir = elefante_home / "backups"
    _write_data(custom_data, "custom location")

    assert backup_main(
        [
            "--elefante-home",
            str(elefante_home),
            "--data-dir",
            str(custom_data),
            "--out-dir",
            str(backup_dir),
        ]
    ) == 0
    archives = list(backup_dir.glob("elefante_data_backup_*.zip"))
    assert len(archives) == 1
    assert read_verified_manifest(archives[0])["source_sha256"] == build_backup_manifest(
        custom_data
    )["source_sha256"]


def test_packaged_backup_script_runs_outside_the_source_tree(tmp_path):
    payload_root = tmp_path / "package" / "payload" / "elefante"
    lifecycle_root = payload_root / "scripts" / "lifecycle"
    lifecycle_root.mkdir(parents=True)
    backup_script = lifecycle_root / "backup_elefante_data.py"
    shutil.copy2(
        Path(__file__).parents[1] / "scripts" / "lifecycle" / backup_script.name,
        backup_script,
    )
    shutil.copy2(
        Path(__file__).parents[1] / "scripts" / "lifecycle" / "restore_elefante_data.py",
        lifecycle_root / "restore_elefante_data.py",
    )
    data_dir = tmp_path / "customer" / "data"
    backup_dir = tmp_path / "customer" / "backups"
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    _write_data(data_dir, "packaged backup")

    result = subprocess.run(
        [
            sys.executable,
            str(backup_script),
            "--data-dir",
            str(data_dir),
            "--out-dir",
            str(backup_dir),
        ],
        cwd=outside_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert len(list(backup_dir.glob("elefante_data_backup_*.zip"))) == 1


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


def test_backup_reads_back_final_archive_and_removes_failed_output(monkeypatch, tmp_path):
    data_dir = tmp_path / "home" / "data"
    _write_data(data_dir, "original memory")
    backup_dir = tmp_path / "home" / "backups"

    def reject_readback(_archive_path):
        raise ValueError("simulated final archive corruption")

    monkeypatch.setattr(
        "scripts.lifecycle.restore_elefante_data.read_verified_manifest",
        reject_readback,
    )

    with pytest.raises(ValueError, match="simulated final archive corruption"):
        create_backup(data_dir, backup_dir)

    assert list(backup_dir.glob("*.zip")) == []
    assert list(backup_dir.glob("*.tmp")) == []


def test_backup_rejects_a_source_manifest_when_files_changed(tmp_path):
    data_dir = tmp_path / "home" / "data"
    state = _write_data(data_dir, "original memory")
    manifest = build_backup_manifest(data_dir)
    state.parent.joinpath("new.db").write_text("new state", encoding="utf-8")

    with pytest.raises(ValueError, match="source changed"):
        create_backup(data_dir, tmp_path / "home" / "backups", source_manifest=manifest)


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


def test_restore_uses_exact_predeclared_work_paths(tmp_path):
    home = tmp_path / "home"
    data_dir = home / "data"
    state = _write_data(data_dir, "before backup")
    archive_path = create_backup(data_dir, home / "backups")
    state.write_text("current data", encoding="utf-8")
    staging = home / ".data.restore.operation-123"
    previous = home / "data.pre_restore.operation-123"

    result = restore_archive(
        archive_path,
        data_dir,
        apply=True,
        staging_path=staging,
        previous_path=previous,
    )

    assert result["previous_data"] == previous.resolve()
    assert not staging.exists()
    assert (data_dir / "chroma" / "state.db").read_text(encoding="utf-8") == "before backup"
    assert (previous / "chroma" / "state.db").read_text(encoding="utf-8") == "current data"


def test_restore_rejects_unsafe_or_occupied_predeclared_work_paths(tmp_path):
    home = tmp_path / "home"
    data_dir = home / "data"
    state = _write_data(data_dir, "before backup")
    archive_path = create_backup(data_dir, home / "backups")
    state.write_text("current data", encoding="utf-8")
    occupied = home / ".data.restore.occupied"
    occupied.mkdir()

    unsafe_cases = (
        {
            "staging_path": tmp_path / "outside" / ".data.restore.escape",
            "previous_path": home / "data.pre_restore.escape",
        },
        {
            "staging_path": home / ".data.restore.wrong-stem",
            "previous_path": home / "wrong.previous",
        },
        {
            "staging_path": occupied,
            "previous_path": home / "data.pre_restore.occupied",
        },
    )
    for paths in unsafe_cases:
        with pytest.raises(ValueError, match="Unsafe or occupied restore work path"):
            restore_archive(archive_path, data_dir, apply=True, **paths)

    assert state.read_text(encoding="utf-8") == "current data"
    assert list(home.glob("data.pre_restore.*")) == []


def test_restore_verifies_staged_data_before_switching(tmp_path):
    home = tmp_path / "home"
    data_dir = home / "data"
    state = _write_data(data_dir, "before backup")
    archive_path = create_backup(data_dir, home / "backups")
    state.write_text("current data", encoding="utf-8")
    staging = home / ".data.restore.verify-first"
    previous = home / "data.pre_restore.verify-first"

    def reject_staged(_staged_data):
        raise ValueError("staged database verification failed")

    with pytest.raises(ValueError, match="staged database verification failed"):
        restore_archive(
            archive_path,
            data_dir,
            apply=True,
            staging_path=staging,
            previous_path=previous,
            verify_staged=reject_staged,
        )

    assert state.read_text(encoding="utf-8") == "current data"
    assert not staging.exists()
    assert not previous.exists()


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


def test_restore_rejects_duplicate_manifest_paths_before_mutation(tmp_path):
    data_dir = tmp_path / "home" / "data"
    state = _write_data(data_dir, "current data")
    archive_path = tmp_path / "duplicate-manifest-path.zip"
    body = b"backup content"
    entry = {
        "path": "chroma/state.db",
        "size": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("chroma/state.db", body)
        archive.writestr(
            MANIFEST_NAME,
            json.dumps(
                {
                    "format": "elefante-data-backup",
                    "format_version": 1,
                    "files": [entry, dict(entry)],
                }
            ),
        )

    with pytest.raises(ValueError, match="duplicate or reserved"):
        restore_archive(archive_path, data_dir)

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


def test_kuzu_only_reset_targets_configured_graph_and_never_claims_rebuild(
    monkeypatch, tmp_path, capsys
):
    data_dir = tmp_path / "data"
    vector_path = data_dir / "vector" / "memories.sqlite3"
    graph_path = tmp_path / "custom-graph.kuzu"
    vector_path.parent.mkdir(parents=True)
    vector_path.write_text("memory", encoding="utf-8")
    graph_path.write_text("graph", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "elefante:\n"
        f"  data_dir: {data_dir}\n"
        "  vector_store:\n"
        f"    persist_directory: {vector_path.parent}\n"
        "  graph_store:\n"
        f"    database_path: {graph_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(tmp_path / "isolated-home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "isolated-home"))
    monkeypatch.setenv("ELEFANTE_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ELEFANTE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("ELEFANTE_PRIVILEGED", "1")

    assert nuclear_reset_kuzu(apply=False, confirm="") is True
    dry_run_output = capsys.readouterr().out
    assert str(graph_path) in dry_run_output
    assert str(Path.home() / ".elefante" / "data" / "kuzu_db") not in dry_run_output
    assert graph_path.exists()
    assert nuclear_reset_kuzu(apply=True, confirm="DELETE") is False
    assert graph_path.exists()
    assert nuclear_reset_kuzu(
        apply=True,
        confirm="DELETE",
        confirm_path=str(graph_path),
    ) is True

    output = capsys.readouterr().out
    assert "No automatic graph rebuild is performed" in output
    assert not graph_path.exists()
    assert vector_path.read_text(encoding="utf-8") == "memory"
    backups = list((data_dir / "backups" / "kuzu_reset").iterdir())
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "graph"


def test_kuzu_only_reset_rejects_a_broad_configured_directory(monkeypatch, tmp_path, capsys):
    data_dir = tmp_path / "data"
    vector_path = data_dir / "vector"
    vector_path.mkdir(parents=True)
    marker = tmp_path / "must-survive.txt"
    marker.write_text("preserve", encoding="utf-8")
    config_path = tmp_path / "broad-config.yaml"
    config_path.write_text(
        "elefante:\n"
        f"  data_dir: {data_dir}\n"
        "  vector_store:\n"
        f"    persist_directory: {vector_path}\n"
        "  graph_store:\n"
        f"    database_path: {tmp_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(tmp_path / "isolated-home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "isolated-home"))
    monkeypatch.setenv("ELEFANTE_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ELEFANTE_PRIVILEGED", "1")

    assert nuclear_reset_kuzu(
        apply=True,
        confirm="DELETE",
        confirm_path=str(tmp_path),
    ) is False

    output = capsys.readouterr().out
    assert "broad or contains protected storage" in output
    assert marker.read_text(encoding="utf-8") == "preserve"
