#!/usr/bin/env python3
"""Build and verify a branded Windows Elefante installer executable.

The executable is a thin PyInstaller wrapper around the existing customer
installer ZIP.  At runtime it extracts that ZIP into a temporary directory and
invokes the ZIP's existing ``Install Elefante.bat`` launcher.  This keeps the
customer payload and installer behavior in their maintained source-of-truth
paths instead of creating a second Windows installer implementation.

This script never uploads, publishes, edits host configuration, or touches
Elefante user data.  ``local`` builds may remain unsigned.  ``candidate`` and
``release`` verification modes require a successfully verified Authenticode
signature; signing credentials are read from an explicitly named CI
environment variable and are never printed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, TypeAlias


ROOT_DIR = Path(__file__).resolve().parents[2]
RELEASE_VERIFIER_PATH = ROOT_DIR / "scripts" / "ci" / "verify_release_client.py"
WINDOWS_BUNDLE_ROOT = "elefante-installer-Windows"
WINDOWS_LAUNCHER = "Install Elefante.bat"
DEFAULT_PYINSTALLER_MODULE = "PyInstaller"
DEFAULT_SIGNTOOL = "signtool"
DEFAULT_PASSWORD_ENV = "ELEFANTE_WINDOWS_SIGNING_PASSWORD"
DEFAULT_CERTIFICATE_ENV = "ELEFANTE_WINDOWS_SIGNING_CERTIFICATE_PATH"
DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"
PUBLICATION_STATUSES = frozenset({"local", "candidate", "release"})
MAX_ICON_BYTES = 4 * 1024 * 1024
MAX_VERSION_FILE_BYTES = 64 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
METADATA_KEYS = (
    "CompanyName",
    "FileDescription",
    "FileVersion",
    "InternalName",
    "OriginalFilename",
    "ProductName",
    "ProductVersion",
)


class WindowsInstallerError(ValueError):
    """Base class for deterministic build and verification failures."""


class BrandingInputError(WindowsInstallerError):
    """Raised when explicit icon or version-resource inputs are invalid."""


class PayloadContractError(WindowsInstallerError):
    """Raised when the existing customer payload does not match its contract."""


class ArtifactValidationError(WindowsInstallerError):
    """Raised when the output is not a valid Windows PE artifact."""


class PublicationGateError(WindowsInstallerError):
    """Raised when a publication-class artifact lacks signed proof."""


class SigningCredentialError(PublicationGateError):
    """Raised when explicitly named CI signing credentials are unavailable."""


@dataclass(frozen=True, slots=True)
class BrandingInputs:
    """Validated, explicit branding files passed to PyInstaller."""

    icon_path: Path
    version_file_path: Path
    product_name: str = "Elefante"


@dataclass(frozen=True, slots=True)
class CustomerPayload:
    """Validated metadata from the existing customer ZIP."""

    archive_path: Path
    version: str
    publication_status: str
    launcher_member: str
    bundle_root: str


@dataclass(frozen=True, slots=True)
class BuildPlan:
    """Deterministic PyInstaller invocation and its source inputs."""

    command: tuple[str, ...]
    output_path: Path
    payload_path: Path
    wrapper_path: Path
    branding: BrandingInputs
    publication_status: str


@dataclass(frozen=True, slots=True)
class ArtifactVerification:
    """Safe verification result suitable for CI summaries."""

    artifact_path: Path
    format: str
    signature_status: str
    publication_status: str
    publication_allowed: bool


@dataclass(frozen=True, slots=True)
class SigningConfig:
    """Non-secret signing configuration; the password stays in ``env``."""

    certificate_path: Path
    password_env: str = DEFAULT_PASSWORD_ENV
    timestamp_url: str = DEFAULT_TIMESTAMP_URL
    signtool: str = DEFAULT_SIGNTOOL


Runner: TypeAlias = Callable[..., subprocess.CompletedProcess[str]]


def _load_release_verifier() -> Any:
    """Load the maintained customer-archive verifier without importing src."""

    spec = importlib.util.spec_from_file_location(
        "elefante_release_client_verifier", RELEASE_VERIFIER_PATH
    )
    if spec is None or spec.loader is None:
        raise PayloadContractError(
            f"Could not load maintained release verifier: {RELEASE_VERIFIER_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_archive_path(archive_path: Path) -> Path:
    resolved = archive_path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Customer payload not found: {resolved}")
    if resolved.stat().st_size > MAX_ARCHIVE_BYTES:
        raise PayloadContractError("Customer payload exceeds the archive size limit")
    if resolved.suffix.casefold() != ".zip":
        raise PayloadContractError("Customer payload must be a ZIP archive")
    return resolved


def validate_customer_payload(
    archive_path: Path,
    *,
    publication_status: str = "local",
) -> CustomerPayload:
    """Validate the existing customer archive and its Windows launcher."""

    if publication_status not in PUBLICATION_STATUSES:
        raise PayloadContractError(
            f"Unsupported publication status: {publication_status!r}"
        )
    archive_path = _validate_archive_path(archive_path)
    verifier = _load_release_verifier()
    verifier.validate_release_client_archive(
        archive_path,
        require_clean_source=publication_status != "local",
        expected_publication_status=(
            None if publication_status == "local" else publication_status
        ),
        expected_platform="Windows",
    )

    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = [info.filename for info in archive.infolist() if not info.is_dir()]
            launcher_member = f"{WINDOWS_BUNDLE_ROOT}/{WINDOWS_LAUNCHER}"
            if launcher_member not in names:
                raise PayloadContractError(
                    f"Customer payload is missing {WINDOWS_LAUNCHER!r}"
                )
            manifest = json.loads(
                archive.read(f"{WINDOWS_BUNDLE_ROOT}/installer-manifest.json")
            )
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as error:
        raise PayloadContractError("Could not inspect the customer payload") from error

    if not isinstance(manifest, dict):
        raise PayloadContractError("Customer payload manifest is not an object")
    version = manifest.get("version")
    payload_status = manifest.get("publication_status")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise PayloadContractError("Customer payload has no valid semantic version")
    if payload_status not in {"candidate", "release"}:
        raise PayloadContractError(
            "Windows EXE input must be an existing candidate or release customer payload"
        )
    if publication_status != "local" and payload_status != publication_status:
        raise PayloadContractError(
            "Requested publication status does not match customer payload status"
        )
    return CustomerPayload(
        archive_path=archive_path,
        version=version,
        publication_status=payload_status,
        launcher_member=launcher_member,
        bundle_root=WINDOWS_BUNDLE_ROOT,
    )


def validate_ico(icon_path: Path) -> Path:
    """Validate a real Windows ICO container, not merely its file extension."""

    resolved = icon_path.expanduser().resolve()
    if not resolved.is_file():
        raise BrandingInputError(f"Windows icon not found: {resolved}")
    if resolved.suffix.casefold() != ".ico":
        raise BrandingInputError("Windows branding icon must use the .ico format")
    data = resolved.read_bytes()
    if not data or len(data) > MAX_ICON_BYTES:
        raise BrandingInputError("Windows ICO is empty or exceeds its size limit")
    if len(data) < 6:
        raise BrandingInputError("Windows ICO header is truncated")
    reserved, icon_type, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or icon_type != 1 or not 1 <= count <= 64:
        raise BrandingInputError("Windows ICO header is malformed")
    directory_end = 6 + count * 16
    if len(data) < directory_end:
        raise BrandingInputError("Windows ICO directory is truncated")
    for index in range(count):
        offset = 6 + index * 16
        width, height, _, _, planes, bit_count, size, image_offset = struct.unpack_from(
            "<BBBBHHII", data, offset
        )
        # A zero width/height encodes 256 pixels in the ICO directory.  PNG
        # icons may legally leave planes/bit-count at zero; DIB entries may
        # not.
        if (width == 0) != (height == 0):
            raise BrandingInputError("Windows ICO contains an invalid image size")
        if size == 0:
            raise BrandingInputError("Windows ICO contains an empty image entry")
        if image_offset < directory_end or image_offset + size > len(data):
            raise BrandingInputError("Windows ICO image points outside the file")
        image_data = data[image_offset : image_offset + size]
        if not image_data.startswith(b"\x89PNG\r\n\x1a\n") and (
            planes == 0 or bit_count == 0
        ):
            raise BrandingInputError("Windows ICO contains an invalid image entry")
    return resolved


def validate_version_file(
    version_file_path: Path,
    *,
    expected_product: str = "Elefante",
    expected_version: str | None = None,
) -> Path:
    """Validate a PyInstaller Windows version-resource script."""

    resolved = version_file_path.expanduser().resolve()
    if not resolved.is_file():
        raise BrandingInputError(f"Windows version-resource file not found: {resolved}")
    if resolved.stat().st_size > MAX_VERSION_FILE_BYTES:
        raise BrandingInputError("Windows version-resource file exceeds its size limit")
    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise BrandingInputError("Windows version-resource file is not valid UTF-8") from error
    if "\x00" in text or any(
        ord(char) < 32 and char not in "\t\n\r" for char in text
    ):
        raise BrandingInputError("Windows version-resource file contains control bytes")
    if "VSVersionInfo(" not in text or "StringFileInfo(" not in text:
        raise BrandingInputError("Windows version-resource file is not a PyInstaller resource")
    for key in METADATA_KEYS:
        pattern = rf"StringStruct\(\s*u?[\"']{re.escape(key)}[\"']\s*,"
        if re.search(pattern, text) is None:
            raise BrandingInputError(f"Windows version-resource file lacks {key}")
    if expected_product and expected_product.casefold() not in text.casefold():
        raise BrandingInputError("Windows version-resource file is not branded for Elefante")
    if expected_version:
        escaped = re.escape(expected_version)
        if re.search(rf"{escaped}(?:\.0)?(?:[\"']|\s|$)", text) is None:
            raise BrandingInputError(
                "Windows version-resource version does not match the customer payload"
            )
    return resolved


def validate_branding_inputs(
    icon_path: Path,
    version_file_path: Path,
    *,
    expected_product: str = "Elefante",
    expected_version: str | None = None,
) -> BrandingInputs:
    """Require and validate both explicit branding inputs."""

    if not isinstance(icon_path, Path) or not isinstance(version_file_path, Path):
        raise BrandingInputError("Branding icon and version-resource paths are required")
    return BrandingInputs(
        icon_path=validate_ico(icon_path),
        version_file_path=validate_version_file(
            version_file_path,
            expected_product=expected_product,
            expected_version=expected_version,
        ),
        product_name=expected_product,
    )


def build_wrapper_source(
    *,
    payload_member: str = "elefante-installer-Windows.zip",
    bundle_root: str = WINDOWS_BUNDLE_ROOT,
    launcher_name: str = WINDOWS_LAUNCHER,
) -> str:
    """Return the deterministic PyInstaller entrypoint source."""

    for value, label in (
        (payload_member, "payload member"),
        (bundle_root, "bundle root"),
        (launcher_name, "launcher name"),
    ):
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise PayloadContractError(f"Unsafe {label}: {value!r}")
    return f'''"""Generated Elefante Windows customer launcher wrapper."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


PAYLOAD_MEMBER = {payload_member!r}
BUNDLE_ROOT = {bundle_root!r}
LAUNCHER_NAME = {launcher_name!r}


def _resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _safe_extract(archive_path: Path, target: Path) -> None:
    target = target.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            relative = PurePosixPath(info.filename)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise RuntimeError("Customer installer contains an unsafe archive path")
            destination = (target / Path(*relative.parts)).resolve()
            if target != destination and target not in destination.parents:
                raise RuntimeError("Customer installer escaped its temporary directory")
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(info))


def main() -> int:
    archive_path = _resource_root() / PAYLOAD_MEMBER
    if not archive_path.is_file():
        raise RuntimeError("Embedded Elefante customer payload was not found")
    with tempfile.TemporaryDirectory(prefix="elefante-installer-") as temporary:
        extraction_root = Path(temporary)
        _safe_extract(archive_path, extraction_root)
        launcher = extraction_root / BUNDLE_ROOT / LAUNCHER_NAME
        if not launcher.is_file():
            raise RuntimeError("Embedded Elefante Windows launcher was not found")
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "call", str(launcher), *sys.argv[1:]],
            check=False,
        )
        return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build_pyinstaller_command(
    *,
    payload_path: Path,
    output_path: Path,
    wrapper_path: Path,
    branding: BrandingInputs,
    python_executable: str = sys.executable,
    pyinstaller_module: str = DEFAULT_PYINSTALLER_MODULE,
) -> tuple[str, ...]:
    """Build a stable, Windows-targeted PyInstaller command line."""

    payload_path = payload_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    wrapper_path = wrapper_path.expanduser().resolve()
    if output_path.suffix.casefold() != ".exe":
        raise WindowsInstallerError("Windows installer output must use the .exe suffix")
    if not output_path.stem or any(char in output_path.stem for char in '\\/:*?"<>|'):
        raise WindowsInstallerError("Windows installer output name is invalid")
    if not isinstance(python_executable, str) or not python_executable:
        raise WindowsInstallerError("Python executable is required for PyInstaller")
    if not isinstance(pyinstaller_module, str) or not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_.]*", pyinstaller_module
    ):
        raise WindowsInstallerError("PyInstaller module name is invalid")
    dist_path = output_path.parent
    build_path = output_path.parent / ".elefante-windows-build"
    work_path = build_path / "work"
    spec_path = build_path / "spec"
    return (
        python_executable,
        "-m",
        pyinstaller_module,
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--noupx",
        "--name",
        output_path.stem,
        "--distpath",
        str(dist_path),
        "--workpath",
        str(work_path),
        "--specpath",
        str(spec_path),
        "--icon",
        str(branding.icon_path),
        "--version-file",
        str(branding.version_file_path),
        "--add-data",
        f"{payload_path};.",
        str(wrapper_path),
    )


def create_build_plan(
    payload: CustomerPayload,
    *,
    output_path: Path,
    branding: BrandingInputs,
    python_executable: str = sys.executable,
    pyinstaller_module: str = DEFAULT_PYINSTALLER_MODULE,
    wrapper_path: Path | None = None,
    publication_status: str = "local",
) -> BuildPlan:
    """Create a deterministic build plan without running or publishing it."""

    if publication_status not in PUBLICATION_STATUSES:
        raise WindowsInstallerError(
            f"Unsupported publication status: {publication_status!r}"
        )
    output_path = output_path.expanduser().resolve()
    wrapper_path = (
        wrapper_path.expanduser().resolve()
        if wrapper_path is not None
        else output_path.parent / "elefante_windows_bootstrap.py"
    )
    command = build_pyinstaller_command(
        payload_path=payload.archive_path,
        output_path=output_path,
        wrapper_path=wrapper_path,
        branding=branding,
        python_executable=python_executable,
        pyinstaller_module=pyinstaller_module,
    )
    return BuildPlan(
        command=command,
        output_path=output_path,
        payload_path=payload.archive_path,
        wrapper_path=wrapper_path,
        branding=branding,
        publication_status=publication_status,
    )


def _pe_security_directory(data: bytes) -> tuple[int, int]:
    """Return the PE certificate-table offset and size, or ``(0, 0)``."""

    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ArtifactValidationError("Windows installer is not an MZ executable")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset < 0x40 or pe_offset + 24 > len(data):
        raise ArtifactValidationError("Windows installer has an invalid PE offset")
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ArtifactValidationError("Windows installer has no PE signature")
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    optional_offset = pe_offset + 24
    if optional_size < 96 or optional_offset + optional_size > len(data):
        raise ArtifactValidationError("Windows installer has a truncated PE header")
    magic = struct.unpack_from("<H", data, optional_offset)[0]
    directory_count_offset = optional_offset + (92 if magic == 0x10B else 108)
    directory_offset = optional_offset + (96 if magic == 0x10B else 112)
    if magic not in {0x10B, 0x20B} or directory_offset + 5 * 8 > optional_offset + optional_size:
        raise ArtifactValidationError("Windows installer has an unsupported PE header")
    directory_count = struct.unpack_from("<I", data, directory_count_offset)[0]
    if directory_count <= 4:
        return 0, 0
    certificate_offset, certificate_size = struct.unpack_from(
        "<II", data, directory_offset + 4 * 8
    )
    if (certificate_offset == 0) != (certificate_size == 0):
        raise ArtifactValidationError("Windows installer has a malformed certificate table")
    if certificate_size and certificate_size < 8:
        raise ArtifactValidationError("Windows installer has a truncated certificate table")
    if certificate_offset + certificate_size > len(data):
        raise ArtifactValidationError("Windows installer certificate table is out of bounds")
    return certificate_offset, certificate_size


def _signature_probe(
    artifact_path: Path,
    *,
    signtool: str,
    runner: Runner,
) -> bool | None:
    """Return signtool verification, or ``None`` when signtool is unavailable."""

    command = (signtool, "verify", "/pa", "/all", str(artifact_path))
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    return result.returncode == 0


def verify_windows_artifact(
    artifact_path: Path,
    *,
    publication_status: str = "local",
    signtool: str = DEFAULT_SIGNTOOL,
    runner: Runner = subprocess.run,
) -> ArtifactVerification:
    """Verify PE structure and separate local unsigned from signed publication."""

    if publication_status not in PUBLICATION_STATUSES:
        raise ArtifactValidationError(
            f"Unsupported publication status: {publication_status!r}"
        )
    resolved = artifact_path.expanduser().resolve()
    if not resolved.is_file():
        raise ArtifactValidationError(f"Windows installer artifact not found: {resolved}")
    data = resolved.read_bytes()
    certificate_offset, certificate_size = _pe_security_directory(data)
    certificate_present = certificate_offset > 0 and certificate_size > 0
    signtool_result = _signature_probe(resolved, signtool=signtool, runner=runner)

    if certificate_present and signtool_result is False:
        raise ArtifactValidationError(
            "Windows installer contains a signature that signtool could not verify"
        )
    if certificate_present and signtool_result is True:
        signature_status = "signed-publication" if publication_status != "local" else "signed-local"
    elif certificate_present:
        signature_status = "signed-unverified-local"
    else:
        signature_status = "unsigned-local"

    publication_allowed = (
        publication_status == "local"
        or signature_status == "signed-publication"
    )
    if publication_status != "local" and not publication_allowed:
        raise PublicationGateError(
            "Publication verification requires a verified Authenticode signature"
        )
    return ArtifactVerification(
        artifact_path=resolved,
        format="PE/Windows",
        signature_status=signature_status,
        publication_status=publication_status,
        publication_allowed=publication_allowed,
    )


def _resolve_signing_config(
    *,
    certificate_path: Path | None,
    certificate_env: str,
    password_env: str,
    timestamp_url: str,
    signtool: str,
    env: Mapping[str, str] | None,
) -> tuple[SigningConfig, dict[str, str]]:
    environment = dict(os.environ)
    if env is not None:
        environment.update(env)
    certificate_value = str(certificate_path) if certificate_path else environment.get(certificate_env)
    if not certificate_value:
        raise SigningCredentialError(
            f"Signing certificate path is required via --certificate or {certificate_env}"
        )
    resolved_certificate = Path(certificate_value).expanduser().resolve()
    if not resolved_certificate.is_file():
        raise SigningCredentialError("Signing certificate file is unavailable")
    if not environment.get(password_env):
        raise SigningCredentialError(
            f"Signing password is unavailable in environment variable {password_env}"
        )
    if not re.fullmatch(r"https?://[^\s]+", timestamp_url):
        raise SigningCredentialError("Timestamp URL is invalid")
    return (
        SigningConfig(
            certificate_path=resolved_certificate,
            password_env=password_env,
            timestamp_url=timestamp_url,
            signtool=signtool,
        ),
        environment,
    )


def redact_command(
    command: Sequence[str],
    *,
    secrets: Sequence[str] = (),
) -> tuple[str, ...]:
    """Redact password and supplied secret values for CI-safe diagnostics."""

    redacted: list[str] = []
    mask_next = False
    secret_values = {value for value in secrets if value}
    for argument in command:
        if mask_next:
            redacted.append("<redacted>")
            mask_next = False
            continue
        if argument.casefold() in {"/p", "/password", "--password"}:
            redacted.append(argument)
            mask_next = True
            continue
        redacted.append("<redacted>" if argument in secret_values else argument)
    return tuple(redacted)


def sign_windows_artifact(
    artifact_path: Path,
    *,
    certificate_path: Path | None = None,
    certificate_env: str = DEFAULT_CERTIFICATE_ENV,
    password_env: str = DEFAULT_PASSWORD_ENV,
    timestamp_url: str = DEFAULT_TIMESTAMP_URL,
    signtool: str = DEFAULT_SIGNTOOL,
    env: Mapping[str, str] | None = None,
    runner: Runner = subprocess.run,
) -> tuple[str, ...]:
    """Sign one artifact using CI credentials without logging their values."""

    resolved_artifact = artifact_path.expanduser().resolve()
    if not resolved_artifact.is_file():
        raise SigningCredentialError("Windows installer artifact is unavailable for signing")
    config, environment = _resolve_signing_config(
        certificate_path=certificate_path,
        certificate_env=certificate_env,
        password_env=password_env,
        timestamp_url=timestamp_url,
        signtool=signtool,
        env=env,
    )
    password = environment[config.password_env]
    command = (
        config.signtool,
        "sign",
        "/fd",
        "SHA256",
        "/tr",
        config.timestamp_url,
        "/td",
        "SHA256",
        "/f",
        str(config.certificate_path),
        "/p",
        password,
        str(resolved_artifact),
    )
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
    except (FileNotFoundError, OSError) as error:
        raise SigningCredentialError(
            "Windows signing tool is unavailable; credential values were not logged"
        ) from error
    if result.returncode != 0:
        raise SigningCredentialError(
            "Windows signing failed; credential values were not logged"
        )
    return redact_command(command, secrets=(password,))


def build_windows_installer(
    payload_path: Path,
    *,
    output_path: Path,
    icon_path: Path,
    version_file_path: Path,
    publication_status: str = "local",
    sign: bool = False,
    certificate_path: Path | None = None,
    certificate_env: str = DEFAULT_CERTIFICATE_ENV,
    password_env: str = DEFAULT_PASSWORD_ENV,
    timestamp_url: str = DEFAULT_TIMESTAMP_URL,
    signtool: str = DEFAULT_SIGNTOOL,
    python_executable: str = sys.executable,
    pyinstaller_module: str = DEFAULT_PYINSTALLER_MODULE,
    runner: Runner = subprocess.run,
    env: Mapping[str, str] | None = None,
    overwrite: bool = False,
    require_windows: bool = True,
) -> ArtifactVerification:
    """Build, optionally sign, and verify one Windows installer artifact."""

    if require_windows and os.name != "nt":
        raise WindowsInstallerError(
            "Windows EXE builds must run on Windows; use plan-only for cross-platform CI preparation"
        )
    if publication_status != "local" and not sign:
        raise PublicationGateError(
            "Candidate/release artifacts require explicit signing before publication verification"
        )
    customer_payload = validate_customer_payload(
        payload_path,
        publication_status=publication_status,
    )
    branding = validate_branding_inputs(
        icon_path,
        version_file_path,
        expected_version=customer_payload.version,
    )
    output_path = output_path.expanduser().resolve()
    if output_path.exists() and not overwrite:
        raise WindowsInstallerError(
            f"Output already exists; pass overwrite=True explicitly: {output_path}"
        )
    with tempfile.TemporaryDirectory(prefix="elefante-windows-build-") as build_dir:
        wrapper_path = Path(build_dir) / "elefante_windows_bootstrap.py"
        wrapper_path.write_text(build_wrapper_source(), encoding="utf-8", newline="\n")
        plan = create_build_plan(
            customer_payload,
            output_path=output_path,
            branding=branding,
            python_executable=python_executable,
            pyinstaller_module=pyinstaller_module,
            wrapper_path=wrapper_path,
            publication_status=publication_status,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            build_environment = dict(os.environ)
            if env is not None:
                build_environment.update(env)
            result = runner(
                plan.command,
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                check=False,
                env=build_environment,
            )
        except (FileNotFoundError, OSError) as error:
            raise WindowsInstallerError(
                "PyInstaller is unavailable; build output was not echoed"
            ) from error
        if result.returncode != 0:
            raise WindowsInstallerError(
                "PyInstaller build failed; build output was intentionally not echoed"
            )
    if sign:
        sign_windows_artifact(
            output_path,
            certificate_path=certificate_path,
            certificate_env=certificate_env,
            password_env=password_env,
            timestamp_url=timestamp_url,
            signtool=signtool,
            env=env,
            runner=runner,
        )
    return verify_windows_artifact(
        output_path,
        publication_status=publication_status,
        signtool=signtool,
        runner=runner,
    )


def _format_command(command: Sequence[str], *, secrets: Sequence[str] = ()) -> str:
    return " ".join(redact_command(command, secrets=secrets))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", "--payload-zip", dest="payload")
    parser.add_argument("--icon")
    parser.add_argument("--version-file", dest="version_file")
    parser.add_argument("--output")
    parser.add_argument(
        "--publication-status",
        choices=sorted(PUBLICATION_STATUSES),
        default="local",
        help="local permits an unsigned build; candidate/release require signed verification",
    )
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--pyinstaller-module", default=DEFAULT_PYINSTALLER_MODULE)
    parser.add_argument("--signtool", default=DEFAULT_SIGNTOOL)
    parser.add_argument("--certificate")
    parser.add_argument("--certificate-env", default=DEFAULT_CERTIFICATE_ENV)
    parser.add_argument("--password-env", default=DEFAULT_PASSWORD_ENV)
    parser.add_argument("--timestamp-url", default=DEFAULT_TIMESTAMP_URL)
    parser.add_argument("--sign", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="validate inputs and print a redacted deterministic PyInstaller command",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify an existing EXE without building, signing, or publishing",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.verify_only:
        if not args.output:
            raise SystemExit("--verify-only requires --output")
        report = verify_windows_artifact(
            Path(args.output),
            publication_status=args.publication_status,
            signtool=args.signtool,
        )
        print(json.dumps(asdict(report), default=str, sort_keys=True))
        return 0

    required = {
        "--payload": args.payload,
        "--icon": args.icon,
        "--version-file": args.version_file,
        "--output": args.output,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit("Missing required build inputs: " + ", ".join(missing))
    payload = validate_customer_payload(
        Path(args.payload), publication_status=args.publication_status
    )
    branding = validate_branding_inputs(
        Path(args.icon),
        Path(args.version_file),
        expected_version=payload.version,
    )
    output_path = Path(args.output).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="elefante-windows-plan-") as plan_dir:
        wrapper_path = Path(plan_dir) / "elefante_windows_bootstrap.py"
        plan = create_build_plan(
            payload,
            output_path=output_path,
            branding=branding,
            python_executable=args.python_executable,
            pyinstaller_module=args.pyinstaller_module,
            wrapper_path=wrapper_path,
            publication_status=args.publication_status,
        )
        if args.plan_only:
            print(_format_command(plan.command))
            return 0

    report = build_windows_installer(
        Path(args.payload),
        output_path=output_path,
        icon_path=Path(args.icon),
        version_file_path=Path(args.version_file),
        publication_status=args.publication_status,
        sign=args.sign,
        certificate_path=Path(args.certificate) if args.certificate else None,
        certificate_env=args.certificate_env,
        password_env=args.password_env,
        timestamp_url=args.timestamp_url,
        signtool=args.signtool,
        python_executable=args.python_executable,
        pyinstaller_module=args.pyinstaller_module,
        overwrite=args.overwrite,
    )
    print(json.dumps(asdict(report), default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
