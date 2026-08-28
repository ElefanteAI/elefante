"""Canonical Windows branding resource generation."""

import importlib.util
import struct
from pathlib import Path

import pytest

from scripts.ci.build_windows_installer import METADATA_KEYS


ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "ci" / "prepare_windows_branding.py"
    spec = importlib.util.spec_from_file_location("prepare_windows_branding", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _png(width=256, height=256):
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(
        ">II", width, height
    ) + b"\x08\x06\x00\x00\x00" + b"pixels"


def test_prepare_branding_wraps_canonical_pixels_and_emits_required_metadata(tmp_path):
    module = _load()
    logo = tmp_path / "logo.png"
    logo.write_bytes(_png())

    result = module.prepare_branding(
        source_png=logo, output_dir=tmp_path / "out", version="2.12.3"
    )

    ico = Path(result["icon"]).read_bytes()
    assert struct.unpack_from("<HHH", ico, 0) == (0, 1, 1)
    assert ico[22:] == logo.read_bytes()
    resource = Path(result["version_file"]).read_text(encoding="utf-8")
    for key in METADATA_KEYS:
        assert f"StringStruct(u'{key}'" in resource
    assert "2.12.3.0" in resource
    assert "Elefante Local Memory Installer" in resource


@pytest.mark.parametrize(
    "payload, message",
    [
        (b"not-png", "must be a PNG"),
        (_png(128, 128), "at least 256px"),
        (_png(256, 128), "square"),
    ],
)
def test_invalid_canonical_logo_is_rejected(tmp_path, payload, message):
    module = _load()
    logo = tmp_path / "logo.png"
    logo.write_bytes(payload)
    with pytest.raises(module.WindowsBrandingError, match=message):
        module.write_ico(logo, tmp_path / "logo.ico")


def test_version_resource_rejects_non_semver():
    module = _load()
    with pytest.raises(module.WindowsBrandingError, match="semantic"):
        module.version_resource("next")
