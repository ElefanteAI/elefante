from __future__ import annotations

import pytest

from src.utils.elefante_mode import (
    LOCK_DIR,
    TransactionLock,
    runtime_lock_dir,
    runtime_lock_file,
)


def test_write_lock_follows_the_configured_data_installation(tmp_path, monkeypatch):
    data_dir = tmp_path / "isolated-install" / "data"
    monkeypatch.setenv("ELEFANTE_DATA_DIR", str(data_dir))
    monkeypatch.delenv("ELEFANTE_LOCK_DIR", raising=False)

    expected_dir = data_dir.parent / "locks"
    assert runtime_lock_dir() == expected_dir
    assert runtime_lock_file("write") == expected_dir / "write.lock"
    assert runtime_lock_file("write") != LOCK_DIR / "write.lock"

    with TransactionLock(timeout=0.5) as lock:
        assert lock.acquired is True
        assert lock._lock_path == expected_dir / "write.lock"
        assert lock._lock_path.is_file()

    assert (expected_dir / "write.lock").read_text(encoding="utf-8") == ""


def test_explicit_lock_directory_must_be_absolute(monkeypatch):
    monkeypatch.setenv("ELEFANTE_LOCK_DIR", "relative-locks")

    with pytest.raises(ValueError, match="absolute"):
        runtime_lock_dir()
