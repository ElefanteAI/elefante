from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from src.core.project_registry import (
    ProjectRegistry,
    ProjectRegistryError,
    ProjectRegistryMode,
    ProjectResolutionStatus,
)


class _Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> UUID:
        self.value += 1
        return UUID(int=self.value)


def _registry(tmp_path: Path) -> ProjectRegistry:
    return ProjectRegistry(
        tmp_path / "data" / "projects.json",
        now=lambda: "2026-08-29T12:00:00+00:00",
        id_factory=_Ids(),
    )


def test_registry_is_compatibility_by_default_and_strict_requires_a_project(tmp_path):
    registry = _registry(tmp_path)

    assert registry.mode is ProjectRegistryMode.COMPATIBILITY
    assert not registry.path.exists()
    with pytest.raises(ProjectRegistryError) as blocked:
        registry.set_mode(ProjectRegistryMode.STRICT)
    assert blocked.value.code == "ACTIVE_PROJECT_REQUIRED"
    assert not registry.path.exists()


def test_register_persists_private_stable_identity_and_rejects_duplicate_folder(
    tmp_path,
):
    root = tmp_path / "company" / "alpha"
    root.mkdir(parents=True)
    registry = _registry(tmp_path)

    project = registry.register("Alpha", root)
    registry.set_mode(ProjectRegistryMode.STRICT)

    assert project.project_id == str(UUID(int=1))
    assert project.scope == f"project:{project.project_id}"
    assert Path(project.root) == root.resolve()
    assert registry.mode is ProjectRegistryMode.STRICT
    assert os.stat(registry.path).st_mode & 0o777 == 0o600
    assert os.stat(registry.strict_marker_path).st_mode & 0o777 == 0o600
    assert json.loads(registry.strict_marker_path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "mode": "strict",
    }
    payload = json.loads(registry.path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["revision"] == 2
    assert payload["mode"] == "strict"
    snapshot = registry.snapshot()
    assert snapshot["scope_policy"] == "isolated"
    assert snapshot["shared_across_projects"] is False

    with pytest.raises(ProjectRegistryError) as duplicate:
        registry.register("Alpha copy", root)
    assert duplicate.value.code == "PROJECT_ROOT_EXISTS"


def test_durable_strict_intent_fails_closed_when_registry_or_marker_is_missing(
    tmp_path,
):
    root = tmp_path / "alpha"
    root.mkdir()
    registry = _registry(tmp_path)
    registry.register("Alpha", root)
    registry.set_mode("strict")

    registry.path.unlink()
    with pytest.raises(ProjectRegistryError) as missing_registry:
        registry.snapshot()
    assert missing_registry.value.code == "PROJECT_REGISTRY_MISSING"

    registry.strict_marker_path.unlink()
    registry.register("Alpha", root)
    registry.set_mode("strict")
    registry.strict_marker_path.unlink()
    with pytest.raises(ProjectRegistryError) as missing_intent:
        registry.snapshot()
    assert missing_intent.value.code == "PROJECT_REGISTRY_INVALID"


def test_corrupt_strict_intent_is_terminal_and_downgrade_is_blocked(tmp_path):
    root = tmp_path / "alpha"
    root.mkdir()
    registry = _registry(tmp_path)
    registry.register("Alpha", root)
    registry.set_mode("strict")

    with pytest.raises(ProjectRegistryError) as downgrade:
        registry.set_mode("compatibility")
    assert downgrade.value.code == "PROJECT_MODE_DOWNGRADE_BLOCKED"

    original = '{"schema_version":1,"mode":"strict","mode":"compatibility"}'
    registry.strict_marker_path.write_text(original, encoding="utf-8")
    with pytest.raises(ProjectRegistryError) as invalid:
        registry.list_projects()
    assert invalid.value.code == "PROJECT_ISOLATION_STATE_INVALID"
    assert registry.strict_marker_path.read_text(encoding="utf-8") == original


def test_nested_projects_choose_unique_deepest_active_folder(tmp_path):
    company = tmp_path / "company"
    alpha = company / "products" / "alpha"
    work = alpha / "src" / "feature"
    work.mkdir(parents=True)
    registry = _registry(tmp_path)
    company_project = registry.register("Company", company)
    alpha_project = registry.register("Alpha", alpha)
    registry.set_mode("strict")

    resolution = registry.resolve_workspace(work)

    assert resolution.status is ProjectResolutionStatus.MATCHED
    assert resolution.project == alpha_project
    assert resolution.project != company_project


def test_unregistered_missing_and_invalid_workspace_fail_closed(tmp_path):
    registered = tmp_path / "registered"
    other = tmp_path / "other"
    registered.mkdir()
    other.mkdir()
    registry = _registry(tmp_path)
    registry.register("Registered", registered)
    registry.set_mode("strict")

    assert (
        registry.resolve_workspace(None).status
        is ProjectResolutionStatus.CONTEXT_REQUIRED
    )
    assert (
        registry.resolve_workspace(other).status
        is ProjectResolutionStatus.UNREGISTERED
    )
    assert (
        registry.resolve_workspace(tmp_path / "missing").status
        is ProjectResolutionStatus.INVALID
    )


def test_rename_move_and_deactivate_preserve_id_but_strict_keeps_one_active(tmp_path):
    first = tmp_path / "first"
    moved = tmp_path / "moved"
    second = tmp_path / "second"
    for path in (first, moved, second):
        path.mkdir()
    registry = _registry(tmp_path)
    alpha = registry.register("Alpha", first)
    beta = registry.register("Beta", second)
    registry.set_mode("strict")

    updated = registry.update(alpha.project_id, name="Alpha Prime", root=moved)
    assert updated.project_id == alpha.project_id
    assert updated.name == "Alpha Prime"
    assert Path(updated.root) == moved.resolve()
    registry.update(beta.project_id, active=False)

    with pytest.raises(ProjectRegistryError) as final_active:
        registry.update(alpha.project_id, active=False)
    assert final_active.value.code == "ACTIVE_PROJECT_REQUIRED"
    assert registry.get(alpha.project_id).active is True

    with pytest.raises(ProjectRegistryError) as invalid_active:
        registry.update(alpha.project_id, active="false")
    assert invalid_active.value.code == "PROJECT_ACTIVE_INVALID"


def test_remove_changes_only_registry_and_never_deletes_project_folder(tmp_path):
    alpha_root = tmp_path / "alpha"
    beta_root = tmp_path / "beta"
    alpha_root.mkdir()
    beta_root.mkdir()
    marker = alpha_root / "customer.txt"
    marker.write_text("preserve", encoding="utf-8")
    registry = _registry(tmp_path)
    alpha = registry.register("Alpha", alpha_root)
    registry.register("Beta", beta_root)
    registry.set_mode("strict")

    removed = registry.remove(alpha.project_id)

    assert removed.project_id == alpha.project_id
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert registry.get(alpha.project_id) is None


def test_missing_folder_is_visible_and_cannot_be_reactivated(tmp_path):
    alpha_root = tmp_path / "alpha"
    beta_root = tmp_path / "beta"
    alpha_root.mkdir()
    beta_root.mkdir()
    registry = _registry(tmp_path)
    alpha = registry.register("Alpha", alpha_root)
    registry.register("Beta", beta_root)
    registry.update(alpha.project_id, active=False)
    alpha_root.rmdir()

    alpha_snapshot = next(
        project
        for project in registry.snapshot()["projects"]
        if project["project_id"] == alpha.project_id
    )
    assert alpha_snapshot["root_status"] == "missing"
    with pytest.raises(ProjectRegistryError) as missing:
        registry.update(alpha.project_id, active=True)
    assert missing.value.code == "PROJECT_ROOT_NOT_DIRECTORY"


def test_corrupt_or_duplicate_key_registry_is_terminal_and_not_rewritten(tmp_path):
    registry = _registry(tmp_path)
    registry.path.parent.mkdir(parents=True)
    original = '{"schema_version":1,"schema_version":1}'
    registry.path.write_text(original, encoding="utf-8")

    with pytest.raises(ProjectRegistryError) as invalid:
        registry.list_projects()

    assert invalid.value.code == "PROJECT_REGISTRY_INVALID"
    assert registry.path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("root_name", ["filesystem", "home"])
def test_registry_rejects_overbroad_project_roots(tmp_path, monkeypatch, root_name):
    registry = _registry(tmp_path)
    if root_name == "filesystem":
        root = Path(Path.cwd().anchor)
    else:
        root = tmp_path / "home"
        root.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: root))

    with pytest.raises(ProjectRegistryError) as broad:
        registry.register("Too broad", root)

    assert broad.value.code == "PROJECT_ROOT_TOO_BROAD"
