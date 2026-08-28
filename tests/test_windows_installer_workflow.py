"""Focused contracts for the branded Windows EXE build handoff."""

from __future__ import annotations

import importlib.util
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def windows_builder():
    return _load_module(
        ROOT / "scripts/ci/build_windows_installer.py",
        "build_windows_installer_contract",
    )


@pytest.fixture
def release_client_builder():
    return _load_module(
        ROOT / "scripts/ci/build_release_client.py",
        "build_release_client_contract",
    )


def _create_customer_payload(tmp_path: Path, builder) -> Path:
    source_root = tmp_path / "source"
    source_root.mkdir()
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
    }
    for relative_path, contents in source_files.items():
        target = source_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
    for relative_path in builder.CLIENT_RUNTIME_SCRIPTS:
        target = source_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("print('runtime script')\n", encoding="utf-8")
    archive_path = tmp_path / "elefante-installer-Windows.zip"
    builder.build_release_client(
        source_root,
        platform_name="Windows",
        publication_status="candidate",
        output_path=archive_path,
    )
    return archive_path


def _write_valid_ico(path: Path) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"test-image"
    directory_end = 6 + 16
    path.write_bytes(
        struct.pack("<HHH", 0, 1, 1)
        + struct.pack("<BBBBHHII", 0, 0, 0, 0, 0, 0, len(png), directory_end)
        + png
    )


def _write_version_file(path: Path, version: str = "2.12.2") -> None:
    values = {
        "CompanyName": "Elefante",
        "FileDescription": "Elefante Installer",
        "FileVersion": f"{version}.0",
        "InternalName": "Elefante-Installer",
        "OriginalFilename": "Elefante-Installer.exe",
        "ProductName": "Elefante",
        "ProductVersion": f"{version}.0",
    }
    lines = [
        "VSVersionInfo(",
        "  ffi=FixedFileInfo(filevers=(2, 12, 2, 0), prodvers=(2, 12, 2, 0)),",
        "  kids=[StringFileInfo([",
    ]
    lines.extend(
        f"    StringStruct(u'{key}', u'{value}')," for key, value in values.items()
    )
    lines.extend(["  ])])", ")"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_pe(path: Path, *, signed: bool = False) -> None:
    data = bytearray(1024)
    data[:2] = b"MZ"
    pe_offset = 0x80
    struct.pack_into("<I", data, 0x3C, pe_offset)
    data[pe_offset : pe_offset + 4] = b"PE\0\0"
    # COFF header: Machine, section count, timestamp, symbol pointers/count,
    # then the 0xe0-byte PE32 optional header.
    struct.pack_into("<H", data, pe_offset + 4, 0x14C)
    struct.pack_into("<H", data, pe_offset + 6, 1)
    struct.pack_into("<H", data, pe_offset + 20, 0xE0)
    optional_offset = pe_offset + 24
    struct.pack_into("<H", data, optional_offset, 0x10B)
    struct.pack_into("<I", data, optional_offset + 92, 16)
    if signed:
        certificate_offset = 900
        certificate_size = 16
        struct.pack_into(
            "<II",
            data,
            optional_offset + 96 + 4 * 8,
            certificate_offset,
            certificate_size,
        )
        data[certificate_offset : certificate_offset + certificate_size] = b"certificate".ljust(
            certificate_size, b"\0"
        )
    path.write_bytes(data)


def _branding(tmp_path: Path, builder, version: str = "2.12.2"):
    icon = tmp_path / "Elefante.ico"
    version_file = tmp_path / "Elefante.version.txt"
    _write_valid_ico(icon)
    _write_version_file(version_file, version)
    return builder.validate_branding_inputs(icon, version_file, expected_version=version)


def test_customer_payload_validation_requires_existing_windows_launcher(
    tmp_path, windows_builder, release_client_builder
):
    archive = _create_customer_payload(tmp_path, release_client_builder)

    payload = windows_builder.validate_customer_payload(archive)

    assert payload.bundle_root == "elefante-installer-Windows"
    assert payload.launcher_member.endswith("Install Elefante.bat")
    assert payload.publication_status == "candidate"

    broken = tmp_path / "broken.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(broken, "w") as target:
        for info in source.infolist():
            if not info.filename.endswith("Install Elefante.bat"):
                target.writestr(info, source.read(info.filename))
    with pytest.raises(ValueError):
        windows_builder.validate_customer_payload(broken)


def test_branding_inputs_fail_when_missing_or_malformed(tmp_path, windows_builder):
    with pytest.raises(windows_builder.BrandingInputError, match="not found"):
        windows_builder.validate_ico(tmp_path / "missing.ico")

    not_ico = tmp_path / "brand.ico"
    not_ico.write_bytes(b"not an ico")
    with pytest.raises(windows_builder.BrandingInputError, match="header"):
        windows_builder.validate_ico(not_ico)

    icon = tmp_path / "Elefante.ico"
    _write_valid_ico(icon)
    version_file = tmp_path / "bad-version.txt"
    version_file.write_text("VSVersionInfo(StringFileInfo([]))\n", encoding="utf-8")
    with pytest.raises(windows_builder.BrandingInputError, match="lacks"):
        windows_builder.validate_branding_inputs(icon, version_file)


def test_branding_inputs_validate_real_ico_and_pyinstaller_metadata(
    tmp_path, windows_builder
):
    branding = _branding(tmp_path, windows_builder)

    assert branding.icon_path.suffix == ".ico"
    assert branding.version_file_path.name == "Elefante.version.txt"
    assert branding.product_name == "Elefante"


def test_pyinstaller_command_is_deterministic_and_branded(
    tmp_path, windows_builder, release_client_builder
):
    archive = _create_customer_payload(tmp_path, release_client_builder)
    payload = windows_builder.validate_customer_payload(archive)
    branding = _branding(tmp_path, windows_builder)
    wrapper = tmp_path / "elefante_windows_bootstrap.py"
    output = tmp_path / "Elefante-Installer.exe"

    first = windows_builder.create_build_plan(
        payload,
        output_path=output,
        branding=branding,
        wrapper_path=wrapper,
        python_executable="C:/Python311/python.exe",
    )
    second = windows_builder.create_build_plan(
        payload,
        output_path=output,
        branding=branding,
        wrapper_path=wrapper,
        python_executable="C:/Python311/python.exe",
    )

    assert first.command == second.command
    assert first.command[:4] == (
        "C:/Python311/python.exe",
        "-m",
        "PyInstaller",
        "--noconfirm",
    )
    assert "--onefile" in first.command
    assert "--noupx" in first.command
    assert first.command[first.command.index("--icon") + 1] == str(branding.icon_path)
    assert first.command[first.command.index("--version-file") + 1] == str(
        branding.version_file_path
    )
    assert first.command[first.command.index("--add-data") + 1] == f"{archive.resolve()};."
    assert first.command[-1] == str(wrapper.resolve())


def test_wrapper_embeds_customer_zip_and_invokes_existing_launcher(windows_builder):
    source = windows_builder.build_wrapper_source()

    assert "PAYLOAD_MEMBER = 'elefante-installer-Windows.zip'" in source
    assert "LAUNCHER_NAME = 'Install Elefante.bat'" in source
    assert "TemporaryDirectory(prefix=\"elefante-installer-\")" in source
    assert '["cmd.exe", "/d", "/c", "call"' in source
    assert "Customer installer contains an unsafe archive path" in source


def test_unsigned_local_artifact_is_distinct_from_publication(tmp_path, windows_builder):
    artifact = tmp_path / "Elefante-Installer.exe"
    _write_pe(artifact)

    local = windows_builder.verify_windows_artifact(
        artifact,
        publication_status="local",
        runner=lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )

    assert local.signature_status == "unsigned-local"
    assert local.publication_allowed is True
    with pytest.raises(windows_builder.PublicationGateError, match="Authenticode"):
        windows_builder.verify_windows_artifact(
            artifact,
            publication_status="release",
            runner=lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
        )


def test_malformed_certificate_table_fails_closed(tmp_path, windows_builder):
    artifact = tmp_path / "Elefante-Installer.exe"
    _write_pe(artifact, signed=True)
    data = bytearray(artifact.read_bytes())
    certificate_size_offset = 0x80 + 24 + 96 + 4 * 8 + 4
    struct.pack_into("<I", data, certificate_size_offset, 1)
    artifact.write_bytes(data)

    with pytest.raises(windows_builder.ArtifactValidationError, match="certificate"):
        windows_builder.verify_windows_artifact(artifact)


def test_signed_publication_requires_signature_verifier_proof(tmp_path, windows_builder):
    artifact = tmp_path / "Elefante-Installer.exe"
    _write_pe(artifact, signed=True)

    report = windows_builder.verify_windows_artifact(
        artifact,
        publication_status="release",
        runner=lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout="", stderr=""
        ),
    )

    assert report.signature_status == "signed-publication"
    assert report.publication_allowed is True


def test_signing_uses_ci_password_without_exposing_it(tmp_path, windows_builder):
    artifact = tmp_path / "Elefante-Installer.exe"
    artifact.write_bytes(b"MZ local artifact")
    certificate = tmp_path / "signing.pfx"
    certificate.write_bytes(b"certificate")
    secret = "ci-password-that-must-not-be-printed"
    captured: dict[str, object] = {}

    def runner(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    safe_command = windows_builder.sign_windows_artifact(
        artifact,
        certificate_path=certificate,
        password_env="CI_SIGNING_PASSWORD",
        env={"CI_SIGNING_PASSWORD": secret},
        runner=runner,
    )

    assert secret not in " ".join(safe_command)
    assert safe_command[safe_command.index("/p") + 1] == "<redacted>"
    assert captured["env"]["CI_SIGNING_PASSWORD"] == secret


def test_publication_build_gate_and_no_publication_command(
    tmp_path, windows_builder, release_client_builder
):
    archive = _create_customer_payload(tmp_path, release_client_builder)
    branding = _branding(tmp_path, windows_builder)
    calls: list[tuple[str, ...]] = []

    def runner(command, **kwargs):
        calls.append(tuple(command))
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

    with pytest.raises(windows_builder.PublicationGateError, match="explicit signing"):
        windows_builder.build_windows_installer(
            archive,
            output_path=tmp_path / "Elefante-Installer.exe",
            icon_path=branding.icon_path,
            version_file_path=branding.version_file_path,
            publication_status="release",
            runner=runner,
            require_windows=False,
        )
    assert calls == []
    assert not any(
        command and command[0].casefold() in {"gh", "vercel", "curl"}
        for command in calls
    )
