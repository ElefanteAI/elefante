#!/usr/bin/env python3
"""Derive Windows ICO and version resources from Elefante's canonical assets."""

from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOGO = ROOT / "assets" / "icons" / "Elefante-installer-icon.svg.png"
SEMVER = re.compile(r"\d+\.\d+\.\d+")


class WindowsBrandingError(ValueError):
    """Raised when canonical branding cannot produce valid Windows resources."""


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise WindowsBrandingError("Canonical Windows logo must be a PNG")
    if data[12:16] != b"IHDR":
        raise WindowsBrandingError("Canonical Windows logo lacks a PNG IHDR")
    width, height = struct.unpack(">II", data[16:24])
    if width != height or width < 256:
        raise WindowsBrandingError("Canonical Windows logo must be square and at least 256px")
    return width, height


def write_ico(source_png: Path, output: Path) -> Path:
    """Wrap canonical PNG pixels in a single-image Windows ICO container."""
    data = source_png.expanduser().resolve().read_bytes()
    _png_dimensions(data)
    # ICO uses zero for a 256px-or-larger PNG entry. Modern Windows decoders
    # read the embedded PNG dimensions directly and scale the canonical image.
    header = struct.pack("<HHH", 0, 1, 1)
    directory = struct.pack("<BBBBHHII", 0, 0, 0, 0, 0, 0, len(data), 22)
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(header + directory + data)
    return output


def _version_tuple(version: str) -> str:
    major, minor, patch = (int(value) for value in version.split("."))
    return f"({major}, {minor}, {patch}, 0)"


def version_resource(version: str) -> str:
    if not SEMVER.fullmatch(version):
        raise WindowsBrandingError("Windows branding version must be semantic x.y.z")
    tuple_value = _version_tuple(version)
    dotted = f"{version}.0"
    values = {
        "CompanyName": "ElefanteAI",
        "FileDescription": "Elefante Local Memory Installer",
        "FileVersion": dotted,
        "InternalName": "ElefanteInstaller",
        "OriginalFilename": "Elefante-Installer.exe",
        "ProductName": "Elefante",
        "ProductVersion": dotted,
    }
    strings = "\n".join(
        f"          StringStruct(u'{name}', u'{value}'),"
        for name, value in values.items()
    )
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={tuple_value},
    prodvers={tuple_value},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
{strings}
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""


def write_version_resource(version: str, output: Path) -> Path:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(version_resource(version), encoding="utf-8", newline="\n")
    return output


def prepare_branding(
    *, source_png: Path, output_dir: Path, version: str
) -> dict[str, str]:
    output_dir = output_dir.expanduser().resolve()
    icon = write_ico(source_png, output_dir / "Elefante.ico")
    version_file = write_version_resource(version, output_dir / "Elefante.version.txt")
    return {"icon": str(icon), "version_file": str(version_file), "version": version}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-png", type=Path, default=DEFAULT_LOGO)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            prepare_branding(
                source_png=args.source_png,
                output_dir=args.output_dir,
                version=args.version,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
