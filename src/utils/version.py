"""Single source of truth for the Elefante runtime version."""

from __future__ import annotations

import sys


SUPPORTED_PYTHON = (3, 11)


def get_supported_python_message(found_version: tuple[int, int] | None = None) -> str:
    """Return the canonical runtime compatibility message."""
    major, minor = found_version or sys.version_info[:2]
    return (
        "Elefante requires Python 3.11.x because Kuzu 0.11.3 is not supported on newer "
        f"CPython runtimes. Found Python {major}.{minor}. Recreate .venv with python3.11 "
        "and restart the server."
    )


def is_supported_python(found_version: tuple[int, int] | None = None) -> bool:
    """Return True only for the supported Elefante runtime."""
    return (found_version or sys.version_info[:2]) == SUPPORTED_PYTHON


def ensure_supported_python(found_version: tuple[int, int] | None = None) -> None:
    """Abort immediately when Elefante is launched under an unsupported Python version."""
    version = found_version or sys.version_info[:2]
    if is_supported_python(version):
        return
    raise RuntimeError(get_supported_python_message(version))


def get_package_version() -> str:
    try:
        from src import __version__ as version

        if isinstance(version, str) and version.strip():
            return version
    except Exception:
        pass

    return "unknown"


PACKAGE_VERSION: str = get_package_version()
