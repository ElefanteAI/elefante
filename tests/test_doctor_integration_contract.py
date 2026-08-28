from __future__ import annotations

import json
from pathlib import Path

from scripts.lifecycle import doctor


def _customer_fixture(tmp_path: Path, matrix: str, surfaces: list[str]) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    (repo / "config.yaml").write_text("app_name: elefante\n", encoding="utf-8")
    matrix_path = repo / "agents" / "manifests" / "ide-integration.yaml"
    matrix_path.parent.mkdir(parents=True)
    matrix_path.write_text(matrix, encoding="utf-8")

    home = tmp_path / "home"
    manifest_path = home / ".elefante" / "install-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    files = {
        f"/opaque/owned/{index}": {"surface": surface}
        for index, surface in enumerate(surfaces)
    }
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "files": files,
                "commands": {},
            }
        ),
        encoding="utf-8",
    )
    return repo, home


def test_parse_integration_declarations_is_deterministic_and_conservative() -> None:
    declarations, diagnostics = doctor._parse_integration_declarations(
        {
            "schema_version": 1,
            "surfaces": [
                {"id": "codex", "status": "compatible"},
                {"id": "agent-zero", "status": "community"},
                {"id": "windsurf", "status": "planned-v2.12"},
                {"id": "codex", "status": "community"},
                {"id": "broken", "status": "not-a-status"},
                {"id": "bad/id", "status": "compatible"},
            ],
        }
    )

    assert declarations == {
        "agent-zero": "community",
        "codex": "compatible",
        "windsurf": "planned-v2.12",
    }
    assert diagnostics == [
        "integration_matrix_duplicate_id",
        "integration_matrix_invalid",
        "integration_matrix_unknown_status",
    ]


def test_compare_integration_surfaces_normalizes_aliases_and_blocks_non_ready_tiers() -> None:
    result = doctor._compare_integration_surfaces(
        {
            "bob": "partial",
            "codex": "compatible",
            "agent-zero": "community",
            "windsurf": "planned",
        },
        {
            "ibm-bob",
            "codex",
            "agent-zero",
            "windsurf",
            "codex-recall-routing",
            "daemon-service",
        },
    )

    assert result["installer_owned_surfaces"] == [
        "agent-zero",
        "bob",
        "codex",
        "windsurf",
    ]
    assert result["non_customer_ready_surfaces"] == [
        "agent-zero",
        "bob",
        "windsurf",
    ]
    assert result["unknown_installer_surfaces"] == []
    assert result["diagnostics"] == []
    assert result["customer_diagnostics"] == [
        "integration_surface_not_customer_ready"
    ]


def test_compare_integration_surfaces_reports_unknown_installer_and_compatible_matrix_ids() -> None:
    result = doctor._compare_integration_surfaces(
        {
            "codex": "compatible",
            "made-up-compatible": "compatible",
        },
        {"codex", "unlisted-host"},
    )

    assert result["unknown_installer_surfaces"] == ["unlisted-host"]
    assert result["unknown_compatible_matrix_surfaces"] == ["made-up-compatible"]
    assert result["diagnostics"] == [
        "install_manifest_surface_unknown",
        "integration_matrix_unknown_surface",
    ]


def test_build_report_diagnoses_non_ready_surface_without_mutating_or_leaking_manifest(
    tmp_path: Path,
) -> None:
    repo, home = _customer_fixture(
        tmp_path,
        "surfaces:\n  - id: agent-zero\n    status: community\n",
        ["agent-zero"],
    )
    manifest_path = home / ".elefante" / "install-manifest.json"
    before = manifest_path.read_bytes()

    report = doctor.build_report(
        repo_root=repo,
        home=home,
        service_inspector=lambda _: {
            "daemon_health": True,
            "service_runtime": "active",
            "service_file": "/private/user-service",
        },
        host_detector=lambda **_: set(),
        surface_inspector=lambda _: set(),
    )
    rendered = doctor._render_text(report)
    serialized = json.dumps(report, sort_keys=True)

    assert report["customer_ready"] is False
    assert "integration_surface_not_customer_ready" in report["customer_diagnostics"]
    assert report["integration_contract"]["non_customer_ready_surfaces"] == [
        "agent-zero"
    ]
    assert manifest_path.read_bytes() == before
    assert "/private/user-service" not in rendered
    assert "/private/user-service" not in serialized
    assert str(repo) not in serialized
    assert str(home) not in serialized


def test_manifest_duplicate_keys_are_diagnosed_without_echoing_key_or_value(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    target = home / ".elefante" / "install-manifest.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        '{"files": {}, "files": {"/private/config": '
        '{"surface":"secret-command"}}}',
        encoding="utf-8",
    )

    summary, diagnostics = doctor._read_manifest(home)

    assert summary == {"files": 0, "host_registrations": 0, "configured_surfaces": []}
    assert diagnostics == ["install_manifest_duplicate_key"]
    assert "secret-command" not in json.dumps(summary)
