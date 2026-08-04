"""Regression tests for the clean customer runtime archive."""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_client_source(root_dir: Path, builder) -> None:
    source_files = {
        "src/__init__.py": '__version__ = "2.12.0"\n',
        "src/main.py": "print('runtime')\n",
        "src/dashboard/ui/dist/index.html": "<html></html>\n",
        "scripts/setup/bootstrap_release_bundle.py": "print('bootstrap')\n",
        "requirements.client.txt": "fastapi==0.139.2\n",
        "requirements.client.lock": (
            "# uv pip compile --universal --generate-hashes\n"
            "fastapi==0.139.2 --hash=sha256:example\n"
        ),
        "LICENSE": "license\n",
        "config.yaml": "storage: local\n",
        "workspace/private-notes.md": "must never ship\n",
        "requirements.lock": "pytest==9.0.3 --hash=sha256:example\n",
    }
    for relative_path, contents in source_files.items():
        target = root_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")

    for relative_path in builder.CLIENT_RUNTIME_SCRIPTS:
        target = root_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("print('runtime script')\n", encoding="utf-8")


def test_build_release_client_contains_only_customer_runtime(tmp_path):
    builder = _load_module(
        ROOT / "scripts/ci/build_release_client.py", "build_release_client_module"
    )
    verifier = _load_module(
        ROOT / "scripts/ci/verify_release_client.py", "verify_release_client_module"
    )
    source_root = tmp_path / "source"
    source_root.mkdir()
    _create_client_source(source_root, builder)
    output_path = tmp_path / "Elefante-RCC1.zip"

    builder.build_release_client(source_root, output_path=output_path)
    verifier.validate_release_client_archive(output_path)

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(
            archive.read(
                "elefante-release-client-candidate-1.0-macOS/installer-manifest.json"
            )
        )
        command_info = archive.getinfo(
            "elefante-release-client-candidate-1.0-macOS/Install Elefante.command"
        )

    assert manifest["release_profile"] == "client"
    assert manifest["customer_contract"]["includes_developer_workspace"] is False
    assert (
        "elefante-release-client-candidate-1.0-macOS/payload/elefante/requirements.client.lock"
        in names
    )
    assert (
        "elefante-release-client-candidate-1.0-macOS/payload/elefante/requirements.lock"
        not in names
    )
    assert not any("/workspace/" in name for name in names)
    assert not any("/tests/" in name for name in names)
    assert (command_info.external_attr >> 16) & 0o111


def test_release_client_verifier_rejects_leaked_developer_file(tmp_path):
    builder = _load_module(
        ROOT / "scripts/ci/build_release_client.py", "build_release_client_leak_module"
    )
    verifier = _load_module(
        ROOT / "scripts/ci/verify_release_client.py",
        "verify_release_client_leak_module",
    )
    source_root = tmp_path / "source"
    source_root.mkdir()
    _create_client_source(source_root, builder)
    output_path = tmp_path / "Elefante-RCC1.zip"
    builder.build_release_client(source_root, output_path=output_path)

    with zipfile.ZipFile(output_path, "a") as archive:
        archive.writestr(
            "elefante-release-client-candidate-1.0-macOS/payload/elefante/workspace/private.md",
            "leak",
        )

    with pytest.raises(ValueError, match="Developer material leaked"):
        verifier.validate_release_client_archive(output_path)
