"""Resolve whether Elefante is running from a developer checkout or client payload."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


DEVELOPER_PROFILE = "developer"
CLIENT_PROFILE = "client"
VALID_PROFILES = frozenset({DEVELOPER_PROFILE, CLIENT_PROFILE})
PROFILE_ENVIRONMENT_VARIABLE = "ELEFANTE_RUNTIME_PROFILE"
REPO_ROOT = Path(__file__).resolve().parents[2]


def runtime_profile(
    *,
    root: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Return the explicit profile or infer it from the installed lock contract."""
    environment = environment or os.environ
    explicit = environment.get(PROFILE_ENVIRONMENT_VARIABLE, "").strip().lower()
    if explicit:
        if explicit not in VALID_PROFILES:
            raise ValueError(
                f"{PROFILE_ENVIRONMENT_VARIABLE} must be one of: "
                + ", ".join(sorted(VALID_PROFILES))
            )
        return explicit

    root = Path(root or REPO_ROOT)
    client_lock = root / "requirements.client.lock"
    developer_lock = root / "requirements.lock"
    if client_lock.is_file() and not developer_lock.exists():
        return CLIENT_PROFILE
    return DEVELOPER_PROFILE


def is_client_runtime(*, root: Path | None = None) -> bool:
    return runtime_profile(root=root) == CLIENT_PROFILE
