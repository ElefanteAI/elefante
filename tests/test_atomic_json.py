from __future__ import annotations

import json
import stat

import pytest

from src.utils.atomic_json import (
    capture_private_file,
    read_json_strict,
    restore_private_file,
    write_json_atomically,
)


def test_atomic_json_is_private_complete_and_leaves_no_temporary_file(tmp_path):
    target = tmp_path / "private" / "dashboard_snapshot.json"

    write_json_atomically(target, {"generation_id": "generation-1", "nodes": []})

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "generation_id": "generation-1",
        "nodes": [],
    }
    assert target.read_text(encoding="utf-8").endswith("\n")
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert list(target.parent.glob(f".{target.name}.*.tmp")) == []


def test_failed_atomic_json_serialization_preserves_previous_target(tmp_path):
    target = tmp_path / "dashboard_snapshot.json"
    target.write_text('{"generation_id":"old"}\n', encoding="utf-8")

    with pytest.raises(TypeError):
        write_json_atomically(target, {"invalid": object()})

    assert target.read_text(encoding="utf-8") == '{"generation_id":"old"}\n'
    assert list(tmp_path.glob(f".{target.name}.*.tmp")) == []


def test_private_file_capture_restores_exact_bytes_mode_and_prior_absence(tmp_path):
    existing = tmp_path / "existing.json"
    absent = tmp_path / "absent.json"
    existing.write_bytes(b'{"before":true}\n')
    existing.chmod(0o640)
    before_existing = capture_private_file(existing)
    before_absent = capture_private_file(absent)

    existing.write_bytes(b'{"after":true}\n')
    existing.chmod(0o600)
    absent.write_text("temporary", encoding="utf-8")

    restore_private_file(existing, before_existing)
    restore_private_file(absent, before_absent)

    assert existing.read_bytes() == b'{"before":true}\n'
    assert stat.S_IMODE(existing.stat().st_mode) == 0o640
    assert not absent.exists()


def test_strict_json_reader_rejects_duplicate_keys_at_any_depth(tmp_path):
    target = tmp_path / "duplicate.json"
    target.write_text('{"outer":{"mode":"strict","mode":"compatibility"}}', encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        read_json_strict(target)
