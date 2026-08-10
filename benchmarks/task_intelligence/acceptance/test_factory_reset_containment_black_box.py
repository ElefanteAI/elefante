"""Black-box acceptance for factory-reset recovery containment."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESET = ROOT / "scripts" / "lifecycle" / "reset_factory.py"


def test_factory_reset_rejects_a_store_containing_its_recovery_directory(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    data_dir = home / "data"
    unsafe_store = data_dir / "backups" / "factory_reset"
    unsafe_store.mkdir(parents=True)
    marker = unsafe_store / "customer-state.sqlite3"
    marker.write_text("preserve", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        json.dumps(
            {
                "elefante": {
                    "data_dir": str(data_dir),
                    "vector_store": {
                        "type": "sqlite",
                        "persist_directory": str(unsafe_store),
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "ELEFANTE_CONFIG_PATH": str(config_path),
            "ELEFANTE_PRIVILEGED": "1",
        }
    )

    result = subprocess.run(
        [sys.executable, str(RESET), "--apply", "--confirm", "DELETE"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert marker.read_text(encoding="utf-8") == "preserve"
