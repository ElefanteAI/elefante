#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : bootstrap_release_bundle.py
# PURPOSE : Place a shipped Elefante installer bundle into a stable install
#           location, then delegate the real install work to scripts/setup/install.py.
# WHEN    : Running a downloadable Elefante installer bundle outside a source checkout.
# USAGE   : python scripts/setup/bootstrap_release_bundle.py [--install-root PATH]
#           [--venv-mode ask|fresh|backup|reuse|abort] [--dry-run]
# NOTES   : Does not duplicate dependency, database, or IDE setup logic. It only
#           copies the payload into a durable path and hands off to install.py.
# ─────────────────────────────────────────────────────────────────────────────
"""Bootstrap a shipped Elefante installer bundle into a stable install root."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_BUNDLE_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE_NAME = "installer-manifest.json"
BUILD_IDENTITY_FILE_NAME = "elefante-build.json"
PAYLOAD_RELATIVE_ROOT = Path("payload") / "elefante"
INSTALL_SCRIPT_RELATIVE_PATH = Path("scripts") / "setup" / "install.py"
INSTALL_LOG_FILE_NAME = ".elefante-install.log"
INSTALL_STATUS_FILE_NAME = ".elefante-install-status.txt"
INSTALL_SUMMARY_FILE_NAME = ".elefante-install-summary.txt"
VENV_CHOICES = ["ask", "fresh", "backup", "reuse", "abort"]
RELEASE_PROFILE_DEVELOPER = "developer"
RELEASE_PROFILE_CLIENT = "client"
RELEASE_PROFILES = {RELEASE_PROFILE_DEVELOPER, RELEASE_PROFILE_CLIENT}
RELEASE_CHANNELS = {"candidate", "development", "release"}
SEMVER_PATTERN = re.compile(r"\d+\.\d+\.\d+")
SOURCE_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
SUPPORTED_PYTHON_MIN = (3, 11)
SUPPORTED_PYTHON_MAX = (3, 14)


def resolve_bundle_root(provided_path: str | None) -> Path:
    if provided_path:
        return Path(provided_path).expanduser().resolve()
    return DEFAULT_BUNDLE_ROOT


def _python_version(executable: str) -> tuple[int, int, int] | None:
    try:
        result = subprocess.run(
            [
                executable,
                "-c",
                "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}')",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    raw = result.stdout.strip()
    try:
        major, minor, patch = (int(part) for part in raw.split(".", 2))
    except ValueError:
        return None
    return major, minor, patch


def _python_is_supported(executable: str) -> bool:
    version = _python_version(executable)
    if version is None:
        return False
    return SUPPORTED_PYTHON_MIN <= version[:2] < SUPPORTED_PYTHON_MAX


def resolve_install_python(provided_executable: str | None) -> str:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str | None) -> None:
        if not candidate:
            return
        normalized = str(Path(candidate).expanduser()) if any(sep in candidate for sep in ("/", "\\")) else candidate
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    add(provided_executable)
    add(sys.executable)

    if os.name != "nt":
        for candidate in (
            "/opt/homebrew/bin/python3.13",
            "/opt/homebrew/bin/python3.12",
            "/opt/homebrew/bin/python3.11",
            "/usr/local/bin/python3.13",
            "/usr/local/bin/python3.12",
            "/usr/local/bin/python3.11",
            "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
            "/usr/bin/python3",
        ):
            if Path(candidate).exists():
                add(candidate)

    for command_name in ("python3.13", "python3.12", "python3.11", "python3", "python"):
        add(shutil.which(command_name))

    for candidate in candidates:
        if _python_is_supported(candidate):
            return candidate

    raise RuntimeError(
        "No compatible Python found. Elefante requires Python 3.11, 3.12, or 3.13."
    )


def get_default_install_root(
    *,
    os_name: str | None = None,
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the durable install path for the current platform."""
    env_map = env or os.environ
    system_name = os_name or ("Windows" if os.name == "nt" else os.uname().sysname)
    home_dir = Path(home or Path.home())

    if system_name == "Windows":
        local_app_data = env_map.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Elefante" / "app" / "current"
        return home_dir / "AppData" / "Local" / "Elefante" / "app" / "current"

    return home_dir / ".elefante" / "app" / "current"


def load_manifest(bundle_root: Path) -> dict[str, object]:
    manifest_path = bundle_root / MANIFEST_FILE_NAME
    if not manifest_path.exists():
        return {}

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_payload_root(bundle_root: Path) -> Path:
    return bundle_root / PAYLOAD_RELATIVE_ROOT


def get_release_profile(manifest: dict[str, object]) -> str:
    """Return the declared installer profile, rejecting unknown bundle contracts."""
    profile = manifest.get("release_profile", RELEASE_PROFILE_DEVELOPER)
    if profile not in RELEASE_PROFILES:
        raise ValueError(f"Installer bundle has an unsupported release profile: {profile!r}")
    return str(profile)


def ensure_bundle_layout(bundle_root: Path, *, release_profile: str) -> Path:
    payload_root = get_payload_root(bundle_root)
    dependency_files = (
        [payload_root / "requirements.client.txt", payload_root / "requirements.client.lock"]
        if release_profile == RELEASE_PROFILE_CLIENT
        else [payload_root / "requirements.txt", payload_root / "requirements.lock"]
    )
    required_paths = [
        payload_root,
        payload_root / INSTALL_SCRIPT_RELATIVE_PATH,
        *dependency_files,
        bundle_root / "scripts" / "setup" / "bootstrap_release_bundle.py",
    ]
    # Customer bundles are never accepted without an exact build identity.
    # Developer bundles built by the current pipeline carry one too, but old
    # developer archives remain dry-run compatible for local recovery and
    # historical acceptance fixtures.
    if release_profile == RELEASE_PROFILE_CLIENT:
        required_paths.insert(1, payload_root / BUILD_IDENTITY_FILE_NAME)

    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Installer bundle is incomplete. Missing required paths: " + ", ".join(missing)
        )

    return payload_root


def load_build_identity(
    bundle_root: Path,
    manifest: dict[str, object],
    *,
    release_profile: str,
) -> dict[str, object] | None:
    """Validate that archive metadata and the payload identify the same build."""
    identity_path = get_payload_root(bundle_root) / BUILD_IDENTITY_FILE_NAME
    if not identity_path.exists() and release_profile == RELEASE_PROFILE_DEVELOPER:
        return None
    try:
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Installer payload has invalid build identity") from error
    if not isinstance(identity, dict) or identity.get("schema_version") != 1:
        raise ValueError("Installer payload has unsupported build identity")

    version = identity.get("version")
    commit = identity.get("source_commit")
    clean = identity.get("source_clean")
    channel = identity.get("release_channel")
    if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
        raise ValueError("Installer payload has invalid semantic version identity")
    if not isinstance(clean, bool) or channel not in RELEASE_CHANNELS:
        raise ValueError("Installer payload has invalid source provenance")
    if not isinstance(commit, str) or not (
        SOURCE_COMMIT_PATTERN.fullmatch(commit)
        or (channel == "development" and commit == "unavailable")
    ):
        raise ValueError("Installer payload has invalid source commit identity")

    source = manifest.get("source")
    expected_channel = (
        manifest.get("publication_status")
        if release_profile == RELEASE_PROFILE_CLIENT
        else manifest.get("release_channel")
    )
    if (
        manifest.get("version") != version
        or not isinstance(source, dict)
        or source.get("commit") != commit
        or source.get("clean") is not clean
        or expected_channel != channel
    ):
        raise ValueError("Installer archive and payload build identities do not match")

    if release_profile == RELEASE_PROFILE_CLIENT and (
        channel not in {"candidate", "release"}
        or not SOURCE_COMMIT_PATTERN.fullmatch(commit)
        or clean is not True
    ):
        raise ValueError("Customer installer requires clean identified candidate or release source")
    return identity


def build_backup_dir(install_root: Path) -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = install_root.parent / f"current.backup.{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = install_root.parent / f"current.backup.{stamp}.{suffix}"
        suffix += 1
    return candidate


def place_payload(payload_root: Path, install_root: Path) -> Path | None:
    """Copy the shipped payload into the durable install root."""
    install_root.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    staging_root = install_root.parent / f".elefante-staging.{stamp}"
    backup_root: Path | None = None

    if staging_root.exists():
        shutil.rmtree(staging_root, ignore_errors=True)

    shutil.copytree(payload_root, staging_root)

    try:
        if install_root.exists():
            backup_root = build_backup_dir(install_root)
            shutil.move(str(install_root), str(backup_root))
        shutil.move(str(staging_root), str(install_root))
    except Exception:
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)
        if backup_root and backup_root.exists() and not install_root.exists():
            shutil.move(str(backup_root), str(install_root))
            backup_root = None
        raise

    return backup_root


def build_install_artifact_paths(install_root: Path) -> dict[str, Path]:
    install_root = Path(install_root)
    return {
        "log": install_root / INSTALL_LOG_FILE_NAME,
        "status": install_root / INSTALL_STATUS_FILE_NAME,
        "summary": install_root / INSTALL_SUMMARY_FILE_NAME,
    }


def render_install_artifact_paths(install_root: Path) -> list[str]:
    paths = build_install_artifact_paths(install_root)
    return [
        "Persistent installer files:",
        f"Log file: {paths['log']}",
        f"Status file: {paths['status']}",
        f"Summary file: {paths['summary']}",
    ]


def render_failed_install_guidance(install_root: Path) -> list[str]:
    paths = build_install_artifact_paths(install_root)
    return [
        "Delegated installer failed. Read these persisted files in order:",
        f"1. Summary file: {paths['summary']}",
        f"2. Status file: {paths['status']}",
        f"3. Log file: {paths['log']}",
    ]


def build_install_command(
    install_root: Path,
    *,
    python_executable: str,
    venv_mode: str,
    release_profile: str = RELEASE_PROFILE_DEVELOPER,
    build_identity: dict[str, object] | None = None,
    verbose: bool = False,
    hosts: list[str] | None = None,
) -> list[str]:
    paths = build_install_artifact_paths(install_root)
    cmd = [
        python_executable,
        str(Path(install_root) / INSTALL_SCRIPT_RELATIVE_PATH),
        "--log-file",
        str(paths["log"]),
        "--status-file",
        str(paths["status"]),
        "--summary-file",
        str(paths["summary"]),
        "--venv-mode",
        venv_mode,
        "--installation-scope",
        "customer" if release_profile == RELEASE_PROFILE_CLIENT else "developer",
    ]
    if build_identity is not None:
        cmd.extend(
            [
                "--expected-version",
                str(build_identity["version"]),
                "--source-commit",
                str(build_identity["source_commit"]),
                "--release-channel",
                str(build_identity["release_channel"]),
            ]
        )
        if build_identity.get("source_clean") is True:
            cmd.append("--source-clean")
    if release_profile == RELEASE_PROFILE_CLIENT:
        cmd.extend(["--release-profile", RELEASE_PROFILE_CLIENT])
    if verbose:
        cmd.append("--verbose")
    return cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Place a shipped Elefante bundle in a stable location and run the installer"
    )
    parser.add_argument("--bundle-root", help="Override the unpacked installer bundle root")
    parser.add_argument("--install-root", help="Override the durable install root")
    parser.add_argument(
        "--venv-mode",
        choices=VENV_CHOICES,
        default="ask",
        help="Pass through the repository .venv handling mode to install.py",
    )
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python interpreter used to launch the delegated installer",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate bundle layout and print the delegated install command without executing it",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full subprocess output during installation (passed through to install.py)",
    )
    parser.add_argument(
        "--host",
        action="append",
        help="Deprecated compatibility option; customer installs configure every detected host.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_root = resolve_bundle_root(args.bundle_root)
    manifest = load_manifest(bundle_root)
    try:
        release_profile = get_release_profile(manifest)
        payload_root = ensure_bundle_layout(bundle_root, release_profile=release_profile)
        build_identity = load_build_identity(
            bundle_root,
            manifest,
            release_profile=release_profile,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc
    try:
        install_python = resolve_install_python(args.python_executable)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc

    install_root = (
        Path(args.install_root).expanduser().resolve()
        if args.install_root
        else get_default_install_root().resolve()
    )

    print("=" * 68)
    print("ELEFANTE INSTALLER BUNDLE")
    print("=" * 68)
    if manifest.get("version"):
        print(f"Version: {manifest['version']}")
    if manifest.get("platform"):
        print(f"Bundle Platform: {manifest['platform']}")
    if release_profile == RELEASE_PROFILE_CLIENT:
        print("Release Profile: Client (runtime-only payload)")
    if build_identity is not None:
        print(f"Release Channel: {build_identity['release_channel']}")
        print(f"Source Commit: {str(build_identity['source_commit'])[:12]}")
    print(f"Bundle Root: {bundle_root}")
    print(f"Payload Root: {payload_root}")
    print(f"Install Root: {install_root}")
    print(f"Installer Python: {install_python}")

    install_command = build_install_command(
        install_root,
        python_executable=install_python,
        venv_mode=args.venv_mode,
        release_profile=release_profile,
        build_identity=build_identity,
        verbose=args.verbose,
        hosts=args.host,
    )

    if args.dry_run:
        print("Dry run only. No files were changed.")
        print("Delegated installer command:")
        print(" ".join(install_command))
        return

    backup_root = place_payload(payload_root, install_root)
    if backup_root:
        print(f"Previous install moved to: {backup_root}")
    print(f"Payload placed at: {install_root}")
    for line in render_install_artifact_paths(install_root):
        print(line)

    result = subprocess.run(install_command, cwd=install_root, check=False)
    if result.returncode != 0:
        print("")
        for line in render_failed_install_guidance(install_root):
            print(line)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
