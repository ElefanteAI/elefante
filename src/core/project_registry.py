"""Private project identity and deterministic workspace mapping.

The registry is the product boundary between a host working directory and the
opaque project ID stored on new memories.  It never inspects memory content and
never guesses from semantic similarity.  Missing, invalid, or unmatched
workspace context fails closed when strict mode is enabled.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
import threading
from typing import Any, Callable, Iterable, Mapping
from uuid import UUID, uuid4

from src.utils.atomic_json import write_json_atomically


PROJECT_REGISTRY_SCHEMA_VERSION = 1
PROJECT_ISOLATION_SCHEMA_VERSION = 1
PROJECT_ISOLATION_FILE_NAME = "project_isolation.json"
PROJECT_SCOPE_POLICY = "isolated"
SHARED_ACROSS_PROJECTS = False
MAX_PROJECTS = 128
MAX_PROJECT_NAME_LENGTH = 100
MAX_PROJECT_ROOT_LENGTH = 2048


class ProjectRegistryMode(str, Enum):
    """Compatibility preserves legacy behavior; strict requires one project."""

    COMPATIBILITY = "compatibility"
    STRICT = "strict"


class ProjectResolutionStatus(str, Enum):
    MATCHED = "MATCHED"
    CONTEXT_REQUIRED = "CONTEXT_REQUIRED"
    UNREGISTERED = "UNREGISTERED"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"


class ProjectRegistryError(RuntimeError):
    """A bounded registry rejection with a stable customer-safe code."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RegisteredProject:
    """One stable project identity independent of name and folder changes."""

    project_id: str
    name: str
    root: str
    active: bool
    created_at: str
    updated_at: str

    @property
    def scope(self) -> str:
        return f"project:{self.project_id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectResolution:
    status: ProjectResolutionStatus
    project: RegisteredProject | None = None
    error_code: str | None = None

    @property
    def matched(self) -> bool:
        return self.status is ProjectResolutionStatus.MATCHED and self.project is not None

    def to_dict(self, *, include_root: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status.value,
            "matched": self.matched,
            "error_code": self.error_code,
        }
        if self.project is not None:
            payload["project"] = {
                "project_id": self.project.project_id,
                "name": self.project.name,
                "active": self.project.active,
                "scope": self.project.scope,
            }
            if include_root:
                payload["project"]["root"] = self.project.root
        return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Project Registry JSON contains duplicate keys")
        result[key] = value
    return result


class ProjectRegistry:
    """Versioned, atomic, process-local project registry.

    The daemon is the normal writer. Installer or recovery tooling must stop the
    daemon before changing the same file; atomic replacement prevents readers
    from observing partial JSON but is not a multi-process transaction system.
    """

    def __init__(
        self,
        path: Path,
        *,
        now: Callable[[], str] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self.path = Path(path).expanduser()
        self.strict_marker_path = self.path.with_name(PROJECT_ISOLATION_FILE_NAME)
        self._now = now or _utc_now
        self._id_factory = id_factory or uuid4
        self._lock = threading.RLock()

    @staticmethod
    def _validate_name(value: str) -> str:
        name = str(value or "").strip()
        if (
            not 1 <= len(name) <= MAX_PROJECT_NAME_LENGTH
            or not name.isprintable()
        ):
            raise ProjectRegistryError(
                "Project name must be printable and from 1 to 100 characters.",
                code="PROJECT_NAME_INVALID",
            )
        return name

    @staticmethod
    def _canonical_root(value: str | Path, *, require_directory: bool) -> str:
        raw = str(value or "").strip()
        if not raw or len(raw) > MAX_PROJECT_ROOT_LENGTH or not raw.isprintable():
            raise ProjectRegistryError(
                "Project folder is invalid.",
                code="PROJECT_ROOT_INVALID",
            )
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            raise ProjectRegistryError(
                "Project folder must be an absolute path.",
                code="PROJECT_ROOT_NOT_ABSOLUTE",
            )
        try:
            canonical = candidate.resolve(strict=require_directory)
        except (OSError, RuntimeError) as error:
            raise ProjectRegistryError(
                "Project folder could not be resolved.",
                code="PROJECT_ROOT_INVALID",
            ) from error
        if require_directory and not canonical.is_dir():
            raise ProjectRegistryError(
                "Project folder must be an existing directory.",
                code="PROJECT_ROOT_NOT_DIRECTORY",
            )
        filesystem_root = Path(canonical.anchor)
        user_home = Path.home().resolve(strict=False)
        if canonical == filesystem_root or canonical == user_home:
            raise ProjectRegistryError(
                "Project folder is too broad; choose the actual project directory.",
                code="PROJECT_ROOT_TOO_BROAD",
            )
        return str(canonical)

    @staticmethod
    def _path_key(value: str) -> str:
        return os.path.normcase(value)

    @staticmethod
    def _record_from_payload(payload: Mapping[str, Any]) -> RegisteredProject:
        allowed = {
            "project_id",
            "name",
            "root",
            "active",
            "created_at",
            "updated_at",
        }
        if set(payload) != allowed:
            raise ValueError("Project Registry record fields are invalid")
        project_id = str(UUID(str(payload["project_id"])))
        name = ProjectRegistry._validate_name(str(payload["name"]))
        root = ProjectRegistry._canonical_root(
            str(payload["root"]),
            require_directory=False,
        )
        active = payload["active"]
        if not isinstance(active, bool):
            raise ValueError("Project Registry active flag is invalid")
        created_at = str(payload["created_at"])
        updated_at = str(payload["updated_at"])
        if not created_at or not updated_at:
            raise ValueError("Project Registry timestamps are invalid")
        return RegisteredProject(
            project_id=project_id,
            name=name,
            root=root,
            active=active,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _strict_intent(self) -> bool:
        """Return durable strict intent; corrupt intent always fails closed."""
        if not self.strict_marker_path.exists():
            return False
        try:
            payload = json.loads(
                self.strict_marker_path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
            if payload != {
                "schema_version": PROJECT_ISOLATION_SCHEMA_VERSION,
                "mode": ProjectRegistryMode.STRICT.value,
            }:
                raise ValueError("Project isolation state is invalid")
        except Exception as error:
            raise ProjectRegistryError(
                "Project isolation state is invalid and requires repair.",
                code="PROJECT_ISOLATION_STATE_INVALID",
            ) from error
        return True

    def _ensure_strict_intent(self) -> None:
        if self._strict_intent():
            return
        write_json_atomically(
            self.strict_marker_path,
            {
                "schema_version": PROJECT_ISOLATION_SCHEMA_VERSION,
                "mode": ProjectRegistryMode.STRICT.value,
            },
        )

    def _load(self) -> tuple[ProjectRegistryMode, int, list[RegisteredProject]]:
        strict_intent = self._strict_intent()
        if not self.path.exists():
            if strict_intent:
                raise ProjectRegistryError(
                    "Strict project isolation is enabled, but the Project Registry is missing.",
                    code="PROJECT_REGISTRY_MISSING",
                )
            return ProjectRegistryMode.COMPATIBILITY, 0, []
        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
            if not isinstance(payload, dict):
                raise ValueError("Project Registry must be a JSON object")
            if set(payload) != {
                "schema_version",
                "generation_id",
                "revision",
                "updated_at",
                "mode",
                "projects",
            }:
                raise ValueError("Project Registry fields are invalid")
            if payload["schema_version"] != PROJECT_REGISTRY_SCHEMA_VERSION:
                raise ValueError("Project Registry schema is unsupported")
            UUID(str(payload["generation_id"]))
            revision = int(payload["revision"])
            if revision < 1:
                raise ValueError("Project Registry revision is invalid")
            mode = ProjectRegistryMode(str(payload["mode"]))
            if strict_intent and mode is not ProjectRegistryMode.STRICT:
                raise ValueError("Project isolation state conflicts with the registry")
            if mode is ProjectRegistryMode.STRICT and not strict_intent:
                raise ValueError("Strict Project Registry is missing isolation state")
            raw_projects = payload["projects"]
            if not isinstance(raw_projects, list) or len(raw_projects) > MAX_PROJECTS:
                raise ValueError("Project Registry project list is invalid")
            projects = [self._record_from_payload(item) for item in raw_projects]
            self._validate_collection(projects, mode=mode)
            return mode, revision, projects
        except ProjectRegistryError:
            raise
        except Exception as error:
            raise ProjectRegistryError(
                "Project Registry is invalid and requires repair.",
                code="PROJECT_REGISTRY_INVALID",
            ) from error

    @classmethod
    def _validate_collection(
        cls,
        projects: list[RegisteredProject],
        *,
        mode: ProjectRegistryMode,
    ) -> None:
        ids = [project.project_id for project in projects]
        names = [project.name.casefold() for project in projects]
        roots = [cls._path_key(project.root) for project in projects]
        if len(ids) != len(set(ids)):
            raise ValueError("Project Registry contains duplicate IDs")
        if len(names) != len(set(names)):
            raise ValueError("Project Registry contains duplicate names")
        if len(roots) != len(set(roots)):
            raise ValueError("Project Registry contains duplicate folders")
        if mode is ProjectRegistryMode.STRICT and not any(
            project.active for project in projects
        ):
            raise ValueError("Strict Project Registry requires an active project")

    def _write(
        self,
        mode: ProjectRegistryMode,
        revision: int,
        projects: list[RegisteredProject],
    ) -> None:
        self._validate_collection(projects, mode=mode)
        if mode is ProjectRegistryMode.STRICT:
            # Write the irreversible intent first. If the following registry
            # replacement fails, subsequent reads fail closed instead of
            # silently returning to compatibility behavior.
            self._ensure_strict_intent()
        elif self._strict_intent():
            raise ProjectRegistryError(
                "Strict project isolation cannot be downgraded through the registry.",
                code="PROJECT_MODE_DOWNGRADE_BLOCKED",
            )
        write_json_atomically(
            self.path,
            {
                "schema_version": PROJECT_REGISTRY_SCHEMA_VERSION,
                "generation_id": str(uuid4()),
                "revision": revision,
                "updated_at": self._now(),
                "mode": mode.value,
                "projects": [project.to_dict() for project in projects],
            },
        )

    @property
    def mode(self) -> ProjectRegistryMode:
        with self._lock:
            mode, _, _ = self._load()
            return mode

    def list_projects(self, *, include_inactive: bool = True) -> list[RegisteredProject]:
        with self._lock:
            _, _, projects = self._load()
            selected = projects if include_inactive else [p for p in projects if p.active]
            return sorted(selected, key=lambda project: (project.name.casefold(), project.project_id))

    def get(self, project_id: str) -> RegisteredProject | None:
        expected = str(UUID(str(project_id)))
        return next(
            (project for project in self.list_projects() if project.project_id == expected),
            None,
        )

    def register(self, name: str, root: str | Path) -> RegisteredProject:
        with self._lock:
            mode, revision, projects = self._load()
            if len(projects) >= MAX_PROJECTS:
                raise ProjectRegistryError(
                    "Project Registry reached its supported project limit.",
                    code="PROJECT_LIMIT_REACHED",
                )
            normalized_name = self._validate_name(name)
            normalized_root = self._canonical_root(root, require_directory=True)
            if any(p.name.casefold() == normalized_name.casefold() for p in projects):
                raise ProjectRegistryError(
                    "A project already uses that name.",
                    code="PROJECT_NAME_EXISTS",
                )
            if any(self._path_key(p.root) == self._path_key(normalized_root) for p in projects):
                raise ProjectRegistryError(
                    "That folder is already registered.",
                    code="PROJECT_ROOT_EXISTS",
                )
            timestamp = self._now()
            project = RegisteredProject(
                project_id=str(self._id_factory()),
                name=normalized_name,
                root=normalized_root,
                active=True,
                created_at=timestamp,
                updated_at=timestamp,
            )
            self._write(mode, revision + 1, [*projects, project])
            return project

    def update(
        self,
        project_id: str,
        *,
        name: str | None = None,
        root: str | Path | None = None,
        active: bool | None = None,
    ) -> RegisteredProject:
        with self._lock:
            mode, revision, projects = self._load()
            expected = str(UUID(str(project_id)))
            index = next(
                (position for position, project in enumerate(projects) if project.project_id == expected),
                None,
            )
            if index is None:
                raise ProjectRegistryError(
                    "Project registration was not found.",
                    code="PROJECT_NOT_FOUND",
                )
            if active is not None and not isinstance(active, bool):
                raise ProjectRegistryError(
                    "Project active state must be true or false.",
                    code="PROJECT_ACTIVE_INVALID",
                )
            current = projects[index]
            next_name = self._validate_name(name) if name is not None else current.name
            next_root = (
                self._canonical_root(root, require_directory=True)
                if root is not None
                else current.root
            )
            next_active = active if active is not None else current.active
            if next_active and not Path(next_root).is_dir():
                raise ProjectRegistryError(
                    "An active project folder must be an existing directory.",
                    code="PROJECT_ROOT_NOT_DIRECTORY",
                )
            if any(
                project.project_id != expected
                and project.name.casefold() == next_name.casefold()
                for project in projects
            ):
                raise ProjectRegistryError(
                    "A project already uses that name.",
                    code="PROJECT_NAME_EXISTS",
                )
            if any(
                project.project_id != expected
                and self._path_key(project.root) == self._path_key(next_root)
                for project in projects
            ):
                raise ProjectRegistryError(
                    "That folder is already registered.",
                    code="PROJECT_ROOT_EXISTS",
                )
            candidate = replace(
                current,
                name=next_name,
                root=next_root,
                active=next_active,
                updated_at=self._now(),
            )
            updated = list(projects)
            updated[index] = candidate
            if mode is ProjectRegistryMode.STRICT and not any(p.active for p in updated):
                raise ProjectRegistryError(
                    "Strict mode requires at least one active project.",
                    code="ACTIVE_PROJECT_REQUIRED",
                )
            self._write(mode, revision + 1, updated)
            return candidate

    def remove(self, project_id: str) -> RegisteredProject:
        with self._lock:
            mode, revision, projects = self._load()
            expected = str(UUID(str(project_id)))
            removed = next((p for p in projects if p.project_id == expected), None)
            if removed is None:
                raise ProjectRegistryError(
                    "Project registration was not found.",
                    code="PROJECT_NOT_FOUND",
                )
            remaining = [p for p in projects if p.project_id != expected]
            if mode is ProjectRegistryMode.STRICT and not any(p.active for p in remaining):
                raise ProjectRegistryError(
                    "Strict mode requires at least one active project.",
                    code="ACTIVE_PROJECT_REQUIRED",
                )
            self._write(mode, revision + 1, remaining)
            return removed

    def set_mode(self, mode: ProjectRegistryMode | str) -> ProjectRegistryMode:
        with self._lock:
            selected = ProjectRegistryMode(str(getattr(mode, "value", mode)))
            current_mode, revision, projects = self._load()
            if (
                current_mode is ProjectRegistryMode.STRICT
                and selected is not ProjectRegistryMode.STRICT
            ):
                raise ProjectRegistryError(
                    "Strict project isolation cannot be downgraded through the registry.",
                    code="PROJECT_MODE_DOWNGRADE_BLOCKED",
                )
            if selected is ProjectRegistryMode.STRICT and not any(
                project.active and Path(project.root).is_dir()
                for project in projects
            ):
                raise ProjectRegistryError(
                    "Register at least one active, available project before enabling strict mode.",
                    code="ACTIVE_PROJECT_REQUIRED",
                )
            self._write(selected, revision + 1, projects)
            return selected

    def resolve_workspace(self, workspace: str | Path | None) -> ProjectResolution:
        """Return the unique deepest active project containing ``workspace``."""
        if workspace is None or not str(workspace).strip():
            return ProjectResolution(
                status=ProjectResolutionStatus.CONTEXT_REQUIRED,
                error_code="PROJECT_CONTEXT_REQUIRED",
            )
        try:
            candidate = Path(
                self._canonical_root(workspace, require_directory=True)
            )
        except ProjectRegistryError as error:
            return ProjectResolution(
                status=ProjectResolutionStatus.INVALID,
                error_code=error.code,
            )
        try:
            projects = self.list_projects(include_inactive=False)
        except ProjectRegistryError:
            return ProjectResolution(
                status=ProjectResolutionStatus.INVALID,
                error_code="PROJECT_REGISTRY_INVALID",
            )
        matches: list[RegisteredProject] = []
        for project in projects:
            root = Path(project.root)
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            matches.append(project)
        if not matches:
            return ProjectResolution(
                status=ProjectResolutionStatus.UNREGISTERED,
                error_code="PROJECT_NOT_REGISTERED",
            )
        deepest = max(len(Path(project.root).parts) for project in matches)
        winners = [p for p in matches if len(Path(p.root).parts) == deepest]
        if len(winners) != 1:
            return ProjectResolution(
                status=ProjectResolutionStatus.AMBIGUOUS,
                error_code="PROJECT_CONTEXT_AMBIGUOUS",
            )
        return ProjectResolution(
            status=ProjectResolutionStatus.MATCHED,
            project=winners[0],
        )

    def snapshot(self) -> dict[str, Any]:
        """Return private Home state; callers decide whether roots are rendered."""
        with self._lock:
            mode, revision, projects = self._load()
            return {
                "schema_version": PROJECT_REGISTRY_SCHEMA_VERSION,
                "mode": mode.value,
                "revision": revision,
                "scope_policy": PROJECT_SCOPE_POLICY,
                "shared_across_projects": SHARED_ACROSS_PROJECTS,
                "projects": [
                    {
                        **project.to_dict(),
                        "root_status": (
                            "available" if Path(project.root).is_dir() else "missing"
                        ),
                    }
                    for project in projects
                ],
            }


__all__ = [
    "MAX_PROJECTS",
    "PROJECT_ISOLATION_FILE_NAME",
    "PROJECT_ISOLATION_SCHEMA_VERSION",
    "PROJECT_REGISTRY_SCHEMA_VERSION",
    "PROJECT_SCOPE_POLICY",
    "SHARED_ACROSS_PROJECTS",
    "ProjectRegistry",
    "ProjectRegistryError",
    "ProjectRegistryMode",
    "ProjectResolution",
    "ProjectResolutionStatus",
    "RegisteredProject",
]
