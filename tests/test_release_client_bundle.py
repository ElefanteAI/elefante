"""Regression tests for the clean customer runtime archives."""

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
        "src/__init__.py": '__version__ = "2.12.2"\n',
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


def _build(builder, source_root: Path, output_path: Path, platform: str = "macOS"):
    return builder.build_release_client(
        source_root,
        platform_name=platform,
        publication_status="candidate",
        output_path=output_path,
    )


@pytest.mark.parametrize(
    ("platform", "launchers"),
    [
        ("macOS", {"install.sh", "Install Elefante.command"}),
        ("Linux", {"install.sh"}),
        ("Windows", {"Install Elefante.bat"}),
    ],
)
def test_build_release_client_contains_only_customer_runtime(
    tmp_path, platform, launchers
):
    builder = _load_module(
        ROOT / "scripts/ci/build_release_client.py",
        f"build_release_client_{platform}",
    )
    verifier = _load_module(
        ROOT / "scripts/ci/verify_release_client.py",
        f"verify_release_client_{platform}",
    )
    source_root = tmp_path / "source"
    source_root.mkdir()
    _create_client_source(source_root, builder)
    output_path = tmp_path / f"Elefante-{platform}.zip"

    _build(builder, source_root, output_path, platform)
    verifier.validate_release_client_archive(
        output_path,
        expected_publication_status="candidate",
        expected_platform=platform,
    )

    bundle_root = f"elefante-installer-{platform}"
    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read(f"{bundle_root}/installer-manifest.json"))
        root_names = {
            name.removeprefix(f"{bundle_root}/")
            for name in names
            if name.count("/") == 1
        }
        timestamps = [
            info.date_time for info in archive.infolist() if not info.is_dir()
        ]

    assert manifest["release_profile"] == "client"
    assert manifest["version"] == "2.12.2"
    assert manifest["candidate"] == "v2.12.2-rc.1"
    assert manifest["candidate_lane"] == "Release Client Candidate 1.0"
    assert manifest["publication_status"] == "candidate"
    assert manifest["platform"] == platform
    assert manifest["customer_contract"]["includes_developer_workspace"] is False
    assert launchers.issubset(root_names)
    assert f"{bundle_root}/payload/elefante/requirements.client.lock" in names
    assert f"{bundle_root}/payload/elefante/requirements.lock" not in names
    assert not any("/workspace/" in name for name in names)
    assert not any("/tests/" in name for name in names)
    assert all(timestamp[0] >= 2026 for timestamp in timestamps)


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
    _build(builder, source_root, output_path)

    with zipfile.ZipFile(output_path, "a") as archive:
        archive.writestr(
            "elefante-installer-macOS/payload/elefante/workspace/private.md",
            "leak",
        )

    with pytest.raises(ValueError, match="Developer material leaked"):
        verifier.validate_release_client_archive(output_path)


def test_release_client_archive_is_reproducible(tmp_path):
    builder = _load_module(
        ROOT / "scripts/ci/build_release_client.py",
        "build_release_client_repeat_module",
    )
    source_root = tmp_path / "source"
    source_root.mkdir()
    _create_client_source(source_root, builder)
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    _build(builder, source_root, first)
    _build(builder, source_root, second)

    assert first.read_bytes() == second.read_bytes()


def test_release_archive_has_no_candidate_metadata(tmp_path):
    builder = _load_module(
        ROOT / "scripts/ci/build_release_client.py", "build_release_client_final_module"
    )
    verifier = _load_module(
        ROOT / "scripts/ci/verify_release_client.py",
        "verify_release_client_final_module",
    )
    source_root = tmp_path / "source"
    source_root.mkdir()
    _create_client_source(source_root, builder)
    output_path = tmp_path / "Elefante-release.zip"

    builder.build_release_client(
        source_root,
        platform_name="Linux",
        publication_status="release",
        output_path=output_path,
    )
    verifier.validate_release_client_archive(
        output_path,
        expected_publication_status="release",
        expected_platform="Linux",
    )

    with zipfile.ZipFile(output_path) as archive:
        manifest = json.loads(
            archive.read("elefante-installer-Linux/installer-manifest.json")
        )
    assert "candidate" not in manifest
    assert "candidate_lane" not in manifest


def test_runtime_profile_infers_client_only_from_client_payload(tmp_path):
    module = _load_module(
        ROOT / "src/utils/runtime_profile.py", "runtime_profile_client_module"
    )
    (tmp_path / "requirements.client.lock").write_text("runtime\n", encoding="utf-8")

    assert module.runtime_profile(root=tmp_path, environment={}) == "client"

    (tmp_path / "requirements.lock").write_text("developer\n", encoding="utf-8")
    assert module.runtime_profile(root=tmp_path, environment={}) == "developer"
