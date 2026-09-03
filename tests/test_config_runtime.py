"""Regression checks for explicit runtime configuration selection."""

from pathlib import Path


def test_get_config_honors_config_path_set_after_import(monkeypatch, tmp_path: Path) -> None:
    from src.utils.config import get_config

    data_dir = tmp_path / "data"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"elefante:\n  data_dir: {data_dir}\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("ELEFANTE_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("ELEFANTE_DATA_DIR", raising=False)

    assert Path(get_config().elefante.data_dir) == data_dir
