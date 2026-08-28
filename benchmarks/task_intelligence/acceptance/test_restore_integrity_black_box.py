"""Black-box acceptance for restore integrity before mutation."""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESTORE = ROOT / "scripts" / "lifecycle" / "restore_elefante_data.py"


def _run_restore(home: Path, archive: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RESTORE),
            "--elefante-home",
            str(home),
            "--archive",
            str(archive),
            "--force",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _current_state(home: Path) -> Path:
    state = home / "data" / "state.txt"
    state.parent.mkdir(parents=True)
    state.write_text("current customer data", encoding="utf-8")
    return state


def test_restore_rejects_symlink_and_checksum_tampering_before_mutation(
    tmp_path: Path,
) -> None:
    symlink_home = tmp_path / "symlink-home"
    symlink_state = _current_state(symlink_home)
    symlink_archive = tmp_path / "symlink.zip"
    with zipfile.ZipFile(symlink_archive, "w") as archive:
        member = zipfile.ZipInfo("link")
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(member, "target")

    symlink_result = _run_restore(symlink_home, symlink_archive)

    assert symlink_result.returncode != 0
    assert symlink_state.read_text(encoding="utf-8") == "current customer data"

    checksum_home = tmp_path / "checksum-home"
    checksum_state = _current_state(checksum_home)
    checksum_archive = tmp_path / "checksum.zip"
    body = b"backup content"
    with zipfile.ZipFile(checksum_archive, "w") as archive:
        archive.writestr("store/state.db", body)
        archive.writestr(
            "elefante-backup-manifest.json",
            json.dumps(
                {
                    "format": "elefante-data-backup",
                    "format_version": 1,
                    "files": [
                        {
                            "path": "store/state.db",
                            "size": len(body),
                            "sha256": hashlib.sha256(b"tampered").hexdigest(),
                        }
                    ],
                }
            ),
        )

    checksum_result = _run_restore(checksum_home, checksum_archive)

    assert checksum_result.returncode != 0
    assert checksum_state.read_text(encoding="utf-8") == "current customer data"
