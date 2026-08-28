"""Black-box acceptance for restore path containment before mutation."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESTORE = ROOT / "scripts" / "lifecycle" / "restore_elefante_data.py"


def test_restore_rejects_traversal_before_changing_customer_data(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    state = home / "data" / "state.txt"
    state.parent.mkdir(parents=True)
    state.write_text("current customer data", encoding="utf-8")
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.txt", "unsafe")

    result = subprocess.run(
        [
            sys.executable,
            str(RESTORE),
            "--elefante-home",
            str(home),
            "--archive",
            str(archive_path),
            "--force",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert state.read_text(encoding="utf-8") == "current customer data"
    assert not (tmp_path / "outside.txt").exists()
