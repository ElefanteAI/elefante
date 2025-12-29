"""Single source of truth for the Elefante runtime version."""

from __future__ import annotations


def get_package_version() -> str:
    try:
        from src import __version__ as version

        if isinstance(version, str) and version.strip():
            return version
    except Exception:
        pass

    return "unknown"


PACKAGE_VERSION: str = get_package_version()
