# ─────────────────────────────────────────────────────────────────────────────
# MODULE  : src/utils/version.py
# PURPOSE : Single source of truth for the runtime version string; enforces
#           minimum Python version at startup.
# ROLE    : Utils — imported by __init__.py and main.py. Do NOT use
#           src/__init__.py directly for version; read it from here.
# TOUCHED : When adding a new Python version constraint or changing how the
#           version constant is exposed. bump_version.py updates src/__init__.py,
#           not this file directly.
# ─────────────────────────────────────────────────────────────────────────────
"""Single source of truth for the Elefante runtime version."""

from __future__ import annotations

import sys


SUPPORTED_PYTHON_MIN = (3, 11)
SUPPORTED_PYTHON_MAX_EXCLUSIVE = (3, 14)


def get_supported_python_message(found_version: tuple[int, int] | None = None) -> str:
    """Return the canonical runtime compatibility message."""
    major, minor = found_version or sys.version_info[:2]
    return (
        "Elefante requires Python 3.11, 3.12, or 3.13. "
        f"Found Python {major}.{minor}. Recreate the environment with a supported "
        "interpreter and restart Elefante."
    )


def is_supported_python(found_version: tuple[int, int] | None = None) -> bool:
    """Return True only for the supported Elefante runtime."""
    version = found_version or sys.version_info[:2]
    return SUPPORTED_PYTHON_MIN <= version < SUPPORTED_PYTHON_MAX_EXCLUSIVE


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
