from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from src.core.home_control import (
    HomeControlError,
    HomeControlRegistry,
    HomeCorrectionTicket,
    HomeRecoveryTicket,
    HomeResolveTicket,
)
from src.core.verified_resolve import VerifiedResolveStatus
from src.models.memory import Memory, MemoryMetadata


class _Clock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


def test_home_control_capability_is_origin_bound_bounded_and_expires():
    clock = _Clock()
    tokens = iter(["private-capability", "private-capability-2"])
    registry = HomeControlRegistry(
        now=clock,
        token_factory=lambda: next(tokens),
        session_ttl_seconds=60,
        max_requests=2,
    )

    grant = registry.issue("http://localhost:8000")

    assert grant.token == "private-capability"
    assert grant.expires_in_seconds == 60
    assert "private-capability" not in repr(registry)
    with pytest.raises(HomeControlError, match="origin") as wrong_origin:
        registry.authorize(grant.token, "http://evil.example")
    assert wrong_origin.value.code == "CONTROL_ORIGIN_REJECTED"

    registry.authorize(grant.token, "http://localhost:8000")
    registry.authorize(grant.token, "http://localhost:8000")
    with pytest.raises(HomeControlError) as exhausted:
        registry.authorize(grant.token, "http://localhost:8000")
    assert exhausted.value.code == "CONTROL_REQUEST_LIMIT"

    second = registry.issue("http://localhost:8000")
    clock.value += 61
    with pytest.raises(HomeControlError) as expired:
        registry.authorize(second.token, "http://localhost:8000")
    assert expired.value.code == "CONTROL_SESSION_EXPIRED"


def test_resolve_plan_ticket_binds_exact_pair_hashes_and_is_one_use():
    clock = _Clock()
    tokens = iter(["control-token", "plan-ticket"])
    registry = HomeControlRegistry(
        now=clock,
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        plan_ttl_seconds=30,
        max_requests=10,
    )
    grant = registry.issue("http://127.0.0.1:8000")

    ticket_id = registry.create_resolve_plan(
        grant.token,
        "http://127.0.0.1:8000",
        left_memory_id="left-id",
        right_memory_id="right-id",
        winner_memory_id="left-id",
        confirm_protected=False,
        record_sha256={"left": "a" * 64, "right": "b" * 64},
    )
    ticket = registry.consume_resolve_plan(
        grant.token,
        "http://127.0.0.1:8000",
        ticket_id,
    )

    assert ticket.ticket_id == "plan-ticket"
    assert ticket.left_memory_id == "left-id"
    assert ticket.right_memory_id == "right-id"
    assert ticket.winner_memory_id == "left-id"
    assert ticket.record_sha256 == {"left": "a" * 64, "right": "b" * 64}
    with pytest.raises(HomeControlError) as replay:
        registry.consume_resolve_plan(
            grant.token,
            "http://127.0.0.1:8000",
            ticket_id,
        )
    assert replay.value.code == "CONTROL_PLAN_NOT_FOUND"


def test_resolve_plan_ticket_expires_before_apply():
    clock = _Clock()
    tokens = iter(["control-token", "plan-ticket"])
    registry = HomeControlRegistry(
        now=clock,
        token_factory=lambda: next(tokens),
        plan_ttl_seconds=10,
    )
    grant = registry.issue("http://localhost:8000")
    ticket_id = registry.create_resolve_plan(
        grant.token,
        "http://localhost:8000",
        left_memory_id="left-id",
        right_memory_id="right-id",
        winner_memory_id=None,
        confirm_protected=False,
        record_sha256={"left": "a" * 64, "right": "b" * 64},
    )

    clock.value += 11
    with pytest.raises(HomeControlError) as expired:
        registry.consume_resolve_plan(
            grant.token,
            "http://localhost:8000",
            ticket_id,
        )
    assert expired.value.code == "CONTROL_PLAN_EXPIRED"


def test_correction_ticket_binds_hashes_without_storing_content_and_is_one_use():
    tokens = iter(["control-token", "correction-ticket"])
    registry = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        plan_ttl_seconds=30,
        max_requests=10,
    )
    grant = registry.issue("http://localhost:8000")
    session = registry.authorize(grant.token, "http://localhost:8000")
    ticket_id = registry.create_correction_plan_for_session(
        session,
        memory_id="memory-id",
        action="edit",
        confirm_protected=False,
        record_sha256={"target": "a" * 64},
        graph_sha256={
            "target": "b" * 64,
            "target_relationships": "d" * 64,
        },
        content_sha256="c" * 64,
    )
    ticket = registry.consume_correction_plan(
        grant.token,
        "http://localhost:8000",
        ticket_id,
    )

    assert ticket.action == "edit"
    assert ticket.record_sha256 == {"target": "a" * 64}
    assert ticket.graph_sha256 == {
        "target": "b" * 64,
        "target_relationships": "d" * 64,
    }
    assert ticket.content_sha256 == "c" * 64
    assert not hasattr(ticket, "content")
    with pytest.raises(HomeControlError) as replay:
        registry.consume_correction_plan(
            grant.token,
            "http://localhost:8000",
            ticket_id,
        )
    assert replay.value.code == "CONTROL_PLAN_NOT_FOUND"


def test_permanent_correction_ticket_survives_missing_final_confirmation():
    tokens = iter(["control-token", "permanent-delete-ticket"])
    registry = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        plan_ttl_seconds=30,
        max_requests=10,
    )
    grant = registry.issue("http://localhost:8000")
    session = registry.authorize(grant.token, "http://localhost:8000")
    ticket_id = registry.create_correction_plan_for_session(
        session,
        memory_id="memory-id",
        action="permanent_delete",
        confirm_protected=False,
        record_sha256={"target": "a" * 64},
        graph_sha256={
            "target": "b" * 64,
            "target_relationships": "c" * 64,
        },
        content_sha256=None,
    )

    with pytest.raises(HomeControlError) as missing_confirmation:
        registry.consume_correction_plan(
            grant.token,
            "http://localhost:8000",
            ticket_id,
        )
    assert missing_confirmation.value.code == "PERMANENT_CONFIRMATION_REQUIRED"

    ticket = registry.consume_correction_plan(
        grant.token,
        "http://localhost:8000",
        ticket_id,
        confirm_permanent=True,
    )
    assert ticket.action == "permanent_delete"


def test_recovery_ticket_binds_one_layout_hash_and_is_one_use():
    tokens = iter(["control-token", "recovery-ticket"])
    registry = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        plan_ttl_seconds=30,
        max_requests=10,
    )
    grant = registry.issue("http://localhost:8000")
    session = registry.authorize(grant.token, "http://localhost:8000")
    ticket_id = registry.create_recovery_plan_for_session(
        session,
        action="backup",
        layout_sha256="d" * 64,
    )

    ticket = registry.consume_recovery_plan(
        grant.token,
        "http://localhost:8000",
        ticket_id,
    )

    assert isinstance(ticket, HomeRecoveryTicket)
    assert ticket.action == "backup"
    assert ticket.layout_sha256 == "d" * 64
    assert ticket.archive_name is None
    assert ticket.archive_sha256 is None
    with pytest.raises(HomeControlError) as replay:
        registry.consume_recovery_plan(
            grant.token,
            "http://localhost:8000",
            ticket_id,
        )
    assert replay.value.code == "CONTROL_PLAN_NOT_FOUND"


def test_restore_ticket_binds_configured_archive_identity_and_rejects_paths():
    tokens = iter(["control-token", "restore-ticket"])
    project_id = "11111111-1111-4111-8111-111111111111"
    registry = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        plan_ttl_seconds=30,
        max_requests=10,
    )
    grant = registry.issue("http://localhost:8000", project_id=project_id)
    session = registry.authorize(grant.token, "http://localhost:8000")
    ticket_id = registry.create_recovery_plan_for_session(
        session,
        action="restore",
        layout_sha256="d" * 64,
        archive_name="elefante_data_backup_20260829.zip",
        archive_sha256="e" * 64,
        project_id=project_id,
        workspace_sha256="f" * 64,
    )

    ticket = registry.consume_recovery_plan(
        grant.token,
        "http://localhost:8000",
        ticket_id,
    )

    assert ticket.action == "restore"
    assert ticket.archive_name == "elefante_data_backup_20260829.zip"
    assert ticket.archive_sha256 == "e" * 64
    assert ticket.project_id == project_id
    assert ticket.workspace_sha256 == "f" * 64

    second_session = registry.authorize(grant.token, "http://localhost:8000")
    with pytest.raises(HomeControlError) as unsafe:
        registry.create_recovery_plan_for_session(
            second_session,
            action="restore",
            layout_sha256="d" * 64,
            archive_name="../outside.zip",
            archive_sha256="e" * 64,
            project_id=project_id,
            workspace_sha256="f" * 64,
        )
    assert unsafe.value.code == "RECOVERY_ARCHIVE_NAME_INVALID"


def test_home_restore_plan_and_apply_bind_the_same_live_project(monkeypatch, tmp_path):
    from src.mcp.server import ElefanteMCPServer

    project_id = "11111111-1111-4111-8111-111111111111"
    project_root = tmp_path / "Alpha"
    project_root.mkdir()
    project = SimpleNamespace(
        project_id=project_id,
        root=str(project_root.resolve()),
        active=True,
    )
    server = ElefanteMCPServer()
    service_bindings: list[dict[str, str]] = []

    class _RecoveryService:
        @staticmethod
        def history():
            return ()

        @staticmethod
        def available_backups():
            return ()

        @staticmethod
        def plan_restore(archive_name):
            return SimpleNamespace(
                to_dict=lambda: {
                    "applicable": True,
                    "layout_sha256": "d" * 64,
                    "archive_name": archive_name,
                    "archive_sha256": "e" * 64,
                }
            )

        @staticmethod
        async def execute_restore(*_args, **_kwargs):
            return SimpleNamespace(
                status=SimpleNamespace(value="VERIFIED_COMPLETE"),
                to_dict=lambda: {
                    "success": True,
                    "status": "VERIFIED_COMPLETE",
                },
            )

    def recovery_service(**kwargs):
        service_bindings.append(dict(kwargs))
        return _RecoveryService()

    monkeypatch.setattr(
        server,
        "_home_bound_project",
        lambda selected: (project, None) if selected == project_id else (None, "invalid"),
    )
    monkeypatch.setattr(server, "_verified_recovery_service", recovery_service)

    plan = asyncio.run(
        server._handle_home_recovery_plan(
            action="restore",
            archive_name="elefante_data_backup_20260829.zip",
            project_id=project_id,
        )
    )
    workspace_sha256 = hashlib.sha256(project.root.encode("utf-8")).hexdigest()
    assert plan["_recovery_project_id"] == project_id
    assert plan["_recovery_workspace_sha256"] == workspace_sha256
    assert service_bindings[-1] == {
        "verification_project": project_id,
        "verification_workspace": project.root,
    }

    ticket = HomeRecoveryTicket(
        ticket_id="restore-ticket",
        action="restore",
        layout_sha256="d" * 64,
        archive_name="elefante_data_backup_20260829.zip",
        archive_sha256="e" * 64,
        report_sha256=None,
        project_id=project_id,
        workspace_sha256=workspace_sha256,
        expires_at_monotonic=999.0,
    )
    applied = asyncio.run(
        server._handle_home_recovery_apply(
            ticket,
            verification_question="What restored decision applies?",
        )
    )
    assert applied["recovery_status"] == "VERIFIED_COMPLETE"

    replacement = tmp_path / "Replacement"
    replacement.mkdir()
    project.root = str(replacement.resolve())
    drifted = asyncio.run(
        server._handle_home_recovery_apply(
            ticket,
            verification_question="What restored decision applies?",
        )
    )
    assert drifted["recovery_status"] == "FAILED_NO_CHANGE"
    assert drifted["error_code"] == "RECOVERY_PROJECT_SCOPE_CHANGED"


def test_support_report_ticket_binds_preview_hash_without_storage_paths():
    tokens = iter(["control-token", "support-report-ticket"])
    registry = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        plan_ttl_seconds=30,
        max_requests=10,
    )
    grant = registry.issue("http://localhost:8000")
    session = registry.authorize(grant.token, "http://localhost:8000")
    ticket_id = registry.create_recovery_plan_for_session(
        session,
        action="support_report",
        report_sha256="f" * 64,
    )

    ticket = registry.consume_recovery_plan(
        grant.token,
        "http://localhost:8000",
        ticket_id,
    )

    assert ticket.action == "support_report"
    assert ticket.report_sha256 == "f" * 64
    assert ticket.layout_sha256 is None
    assert ticket.archive_name is None
    assert ticket.archive_sha256 is None

    second_session = registry.authorize(grant.token, "http://localhost:8000")
    with pytest.raises(HomeControlError) as mixed:
        registry.create_recovery_plan_for_session(
            second_session,
            action="support_report",
            layout_sha256="d" * 64,
            report_sha256="f" * 64,
        )
    assert mixed.value.code == "CONTROL_PLAN_INVALID"


def test_remember_ticket_binds_project_and_private_input_hashes_without_content():
    tokens = iter(["control-token", "remember-ticket"])
    project_id = "11111111-1111-4111-8111-111111111111"
    content = "Decision: preserve the customer-safe product boundary."
    question = "What product boundary should Elefante preserve?"
    registry = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        plan_ttl_seconds=30,
        max_requests=10,
    )
    grant = registry.issue("http://localhost:8000", project_id=project_id)
    session = registry.authorize(grant.token, "http://localhost:8000")
    ticket_id = registry.create_remember_plan_for_session(
        session,
        project_id=project_id,
        knowledge_kind="decision",
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        question_sha256=hashlib.sha256(question.encode()).hexdigest(),
        overlap_sha256={
            "22222222-2222-4222-8222-222222222222": "a" * 64,
        },
    )

    ticket = registry.consume_remember_plan(
        grant.token,
        "http://localhost:8000",
        ticket_id,
        content=content,
        verification_question=question,
    )

    assert ticket.project_id == project_id
    assert ticket.knowledge_kind == "decision"
    assert ticket.overlap_sha256 == {
        "22222222-2222-4222-8222-222222222222": "a" * 64,
    }
    assert content not in repr(registry)
    assert question not in repr(registry)
    with pytest.raises(HomeControlError) as replay:
        registry.consume_remember_plan(
            grant.token,
            "http://localhost:8000",
            ticket_id,
            content=content,
            verification_question=question,
        )
    assert replay.value.code == "CONTROL_PLAN_NOT_FOUND"


def test_project_assignment_ticket_binds_exact_preimage_and_is_one_use():
    tokens = iter(["control-token", "assignment-ticket"])
    registry = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        plan_ttl_seconds=30,
        max_requests=10,
    )
    grant = registry.issue("http://localhost:8000")
    session = registry.authorize(grant.token, "http://localhost:8000")
    ticket_id = registry.create_project_assignment_plan_for_session(
        session,
        memory_id="11111111-1111-4111-8111-111111111111",
        project_id="22222222-2222-4222-8222-222222222222",
        confirm_protected=True,
        record_sha256="a" * 64,
        graph_existed=True,
        graph_sha256="b" * 64,
        relationship_sha256="c" * 64,
        target_scope_sha256="d" * 64,
    )

    ticket = registry.consume_project_assignment_plan(
        grant.token,
        "http://localhost:8000",
        ticket_id,
    )

    assert ticket.memory_id == "11111111-1111-4111-8111-111111111111"
    assert ticket.project_id == "22222222-2222-4222-8222-222222222222"
    assert ticket.confirm_protected is True
    assert ticket.record_sha256 == "a" * 64
    assert ticket.graph_sha256 == "b" * 64
    with pytest.raises(HomeControlError) as replay:
        registry.consume_project_assignment_plan(
            grant.token,
            "http://localhost:8000",
            ticket_id,
        )
    assert replay.value.code == "CONTROL_PLAN_NOT_FOUND"


@pytest.mark.asyncio
async def test_dashboard_open_places_capability_only_in_browser_fragment(monkeypatch):
    from src.mcp.server import ElefanteMCPServer
    from types import SimpleNamespace

    tokens = iter(["private-dashboard-capability"])
    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=60,
    )
    captured: dict[str, object] = {}

    async def open_dashboard(*, force_restart, control_fragment):
        captured["force_restart"] = force_restart
        captured["control_fragment"] = control_fragment
        return {
            "success": True,
            "url": "http://localhost:8000",
            "message": "opened",
        }

    monkeypatch.setattr(server, "_start_dashboard_and_open", open_dashboard)
    monkeypatch.setattr(
        server,
        "_strict_project_resolution",
        lambda _args: SimpleNamespace(
            matched=True,
            project=SimpleNamespace(
                project_id="11111111-1111-4111-8111-111111111111"
            ),
        ),
    )
    monkeypatch.setenv("ELEFANTE_DAEMON_PORT", "8765")

    result = await server._handle_get_elefante_dashboard(
        {"refresh": False, "workspace": "/private/customer/project"}
    )

    assert result["success"] is True
    assert result["control"] == {
        "enabled": True,
        "expires_in_seconds": 60,
        "operations": [
            "remember",
            "recall_test",
            "correct",
            "resolve",
            "projects",
            "recover",
        ],
    }
    assert captured["force_restart"] is False
    assert "private-dashboard-capability" in str(captured["control_fragment"])
    assert "daemon_port=8765" in str(captured["control_fragment"])
    assert "active_project_id=11111111-1111-4111-8111-111111111111" in str(
        captured["control_fragment"]
    )
    assert "private-dashboard-capability" not in json.dumps(result)
    assert "11111111-1111-4111-8111-111111111111" not in json.dumps(result)
    session = server.home_control.authorize(
        "private-dashboard-capability",
        "http://localhost:8000",
    )
    assert session.project_id == "11111111-1111-4111-8111-111111111111"


@pytest.mark.asyncio
async def test_dashboard_open_rejects_unknown_fields_and_invalid_workspace():
    from src.mcp.server import ElefanteMCPServer

    server = ElefanteMCPServer()

    unknown = await server._handle_get_elefante_dashboard({"shell": "whoami"})
    invalid = await server._handle_get_elefante_dashboard({"workspace": "\n"})

    assert unknown["error_code"] == "DASHBOARD_FIELDS_INVALID"
    assert invalid["error_code"] == "DASHBOARD_WORKSPACE_INVALID"


@pytest.mark.asyncio
async def test_daemon_remember_control_binds_overlap_choice_and_verifies_once(
    monkeypatch,
):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    project_id = "11111111-1111-4111-8111-111111111111"
    overlap_id = "22222222-2222-4222-8222-222222222222"
    content = "Decision: use SQLite for the project index."
    question = "What database should the project index use?"
    tokens = iter(["browser-control-token", "remember-plan-ticket"])
    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        max_requests=10,
    )
    grant = server.home_control.issue(
        "http://localhost:8000",
        project_id=project_id,
    )
    applied: list[dict[str, object]] = []

    async def remember_handler(bound_project_id, payload):
        assert bound_project_id == project_id
        if payload.get("overlap_choice") == "keep_both":
            applied.append(dict(payload))
            return {
                "success": True,
                "status": "VERIFIED_COMPLETE",
                "remember_status": "VERIFIED_COMPLETE",
                "memory_written": True,
                "receipt": {
                    "status": "VERIFIED_COMPLETE",
                    "checks": [{"name": "scoped_recall", "passed": True}],
                },
            }
        assert payload == {
            "content": content,
            "knowledge_kind": "decision",
            "verification_question": question,
        }
        return {
            "success": False,
            "status": "NEEDS_HUMAN",
            "remember_status": "NEEDS_HUMAN",
            "memory_written": False,
            "plan": {
                "applicable": False,
                "reason_code": "REMEMBER_OVERLAP_REQUIRES_CHOICE",
                "reason": "Related project knowledge already exists.",
                "knowledge_kind": "decision",
                "memory_type": "decision",
                "project_id": project_id,
                "project_name": "Customer project",
                "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "scope_sha256": "b" * 64,
                "choices": ["update", "supersede", "keep_both", "cancel"],
                "overlaps": [
                    {
                        "memory_id": overlap_id,
                        "relation": "duplicate",
                        "title": "SQLite project index",
                        "record_sha256": "a" * 64,
                    }
                ],
            },
            "receipt": {"status": "NEEDS_HUMAN", "changed": False},
        }

    monkeypatch.setattr(server, "_handle_home_remember", remember_handler)
    app = daemon.create_app(elefante=server)
    transport = httpx.ASGITransport(app=app)
    headers = {
        "Origin": "http://localhost:8000",
        "Authorization": f"Bearer {grant.token}",
    }

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1:8765",
    ) as client:
        planned = await client.post(
            "/control/remember",
            headers=headers,
            json={
                "content": content,
                "knowledge_kind": "decision",
                "verification_question": question,
            },
        )
        assert planned.status_code == 200
        plan_body = planned.json()
        assert plan_body["plan_id"] == "remember-plan-ticket"
        assert "content_sha256" not in plan_body["plan"]
        assert "scope_sha256" not in plan_body["plan"]
        assert "record_sha256" not in plan_body["plan"]["overlaps"][0]

        completed = await client.post(
            "/control/remember/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "content": content,
                "verification_question": question,
                "choice": "keep_both",
                "confirm": True,
            },
        )
        replay = await client.post(
            "/control/remember/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "content": content,
                "verification_question": question,
                "choice": "keep_both",
                "confirm": True,
            },
        )

    assert completed.status_code == 200
    assert completed.json()["remember_status"] == "VERIFIED_COMPLETE"
    assert applied == [
        {
            "content": content,
            "knowledge_kind": "decision",
            "verification_question": question,
            "overlap_choice": "keep_both",
            "expected_overlap_sha256": {overlap_id: "a" * 64},
        }
    ]
    assert replay.status_code == 409
    assert replay.json()["error_code"] == "CONTROL_PLAN_NOT_FOUND"


@pytest.mark.asyncio
async def test_daemon_recall_test_returns_only_content_free_project_proof(
    monkeypatch,
):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    project_id = "11111111-1111-4111-8111-111111111111"
    memory_id = "22222222-2222-4222-8222-222222222222"
    question = "What database should the project index use?"
    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(session_ttl_seconds=300)
    grant = server.home_control.issue(
        "http://localhost:8000",
        project_id=project_id,
    )

    async def recall_handler(bound_project_id, supplied_question):
        assert bound_project_id == project_id
        assert supplied_question == question
        return {
            "success": True,
            "recall_status": "supplied",
            "selected_count": 1,
            "selected_memory_ids": [memory_id],
            "conflict_count": 0,
            "delivery_blocked": False,
            "verified_at": "2026-08-30T18:00:00Z",
            "project": {"project_id": project_id, "name": "Customer project"},
            "memory_content_returned": False,
        }

    monkeypatch.setattr(server, "_handle_home_recall_test", recall_handler)
    app = daemon.create_app(elefante=server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1:8765",
    ) as client:
        response = await client.post(
            "/control/recall/test",
            headers={
                "Origin": "http://localhost:8000",
                "Authorization": f"Bearer {grant.token}",
            },
            json={"question": question},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["recall_status"] == "supplied"
    assert body["selected_memory_ids"] == [memory_id]
    assert body["memory_content_returned"] is False
    assert question not in response.text


@pytest.mark.asyncio
async def test_daemon_project_review_lists_and_assigns_without_memory_content(
    monkeypatch,
):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    memory_id = "11111111-1111-4111-8111-111111111111"
    project_id = "22222222-2222-4222-8222-222222222222"
    tokens = iter(["browser-control-token", "assignment-plan-ticket"])
    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        max_requests=12,
    )
    grant = server.home_control.issue("http://localhost:8000")
    applied = []

    async def review_handler(*, offset, limit):
        assert (offset, limit) == (0, 25)
        return {
            "success": True,
            "status": "READY",
            "total_unscoped": 1,
            "offset": 0,
            "limit": 25,
            "returned_count": 1,
            "has_more": False,
            "scan_complete": True,
            "review_required": True,
            "memories": [
                {
                    "memory_id": memory_id,
                    "title": "SQLite project index",
                    "summary": "Local recovery decision.",
                    "memory_type": "decision",
                    "status": "new",
                    "protected": False,
                    "created_at": "2026-08-30T18:00:00",
                }
            ],
            "memory_content_returned": False,
        }

    async def plan_handler(payload):
        assert payload == {
            "memory_id": memory_id,
            "project_id": project_id,
            "confirm_protected": False,
        }
        return {
            "success": True,
            "plan": {
                "schema_version": 1,
                "memory_id": memory_id,
                "project_id": project_id,
                "project_name": "Customer project",
                "applicable": True,
                "reason_code": None,
                "reason": "Ready for verified assignment.",
                "protected": False,
                "record_sha256": "a" * 64,
                "graph_existed": True,
                "graph_sha256": "b" * 64,
                "relationship_sha256": "c" * 64,
                "target_scope_sha256": "d" * 64,
            },
        }

    async def apply_handler(ticket):
        applied.append(ticket)
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "assignment_status": "VERIFIED_COMPLETE",
            "receipt": {
                "status": "VERIFIED_COMPLETE",
                "checks": [
                    {"name": "project_filter", "passed": True},
                ],
            },
            "assigned": {
                "memory_id": memory_id,
                "title": "SQLite project index",
                "project": {
                    "project_id": project_id,
                    "name": "Customer project",
                },
            },
        }

    monkeypatch.setattr(server, "_legacy_unscoped_review", review_handler)
    monkeypatch.setattr(server, "_handle_home_project_assignment_plan", plan_handler)
    monkeypatch.setattr(server, "_handle_home_project_assignment_apply", apply_handler)
    app = daemon.create_app(elefante=server)
    headers = {
        "Origin": "http://localhost:8000",
        "Authorization": f"Bearer {grant.token}",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8765",
    ) as client:
        listed = await client.post(
            "/control/projects/unscoped/list",
            headers=headers,
            json={"offset": 0, "limit": 25},
        )
        planned = await client.post(
            "/control/projects/unscoped/plan",
            headers=headers,
            json={
                "memory_id": memory_id,
                "project_id": project_id,
                "confirm_protected": False,
            },
        )
        completed = await client.post(
            "/control/projects/unscoped/apply",
            headers=headers,
            json={"plan_id": planned.json()["plan_id"], "confirm": True},
        )
        replay = await client.post(
            "/control/projects/unscoped/apply",
            headers=headers,
            json={"plan_id": planned.json()["plan_id"], "confirm": True},
        )

    assert listed.status_code == 200
    assert listed.json()["memory_content_returned"] is False
    assert planned.status_code == 200
    assert planned.json()["plan_id"] == "assignment-plan-ticket"
    for private_field in (
        "record_sha256",
        "graph_sha256",
        "relationship_sha256",
        "target_scope_sha256",
        "graph_existed",
    ):
        assert private_field not in planned.json()["plan"]
    assert completed.status_code == 200
    assert completed.json()["assignment_status"] == "VERIFIED_COMPLETE"
    assert len(applied) == 1
    assert replay.status_code == 409
    assert replay.json()["error_code"] == "CONTROL_PLAN_NOT_FOUND"


@pytest.mark.asyncio
async def test_daemon_resolve_control_requires_capability_and_one_use_plan(
    monkeypatch,
):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    left_id = "11111111-1111-4111-8111-111111111111"
    right_id = "22222222-2222-4222-8222-222222222222"
    tokens = iter(["browser-control-token", "one-use-plan-ticket"])
    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        max_requests=10,
    )
    applied: list[object] = []

    async def plan_handler(payload):
        assert payload == {
            "memory_id": left_id,
            "related_memory_id": right_id,
            "winner_memory_id": left_id,
            "confirm_protected": False,
        }
        return {
            "success": True,
            "plan": {
                "applicable": True,
                "reason_code": None,
                "reason": "The selected assertion can supersede its conflict.",
                "record_sha256": {"left": "a" * 64, "right": "b" * 64},
                "resolution": {
                    "action": "supersede",
                    "winner_memory_id": left_id,
                    "loser_memory_id": right_id,
                },
            },
        }

    async def apply_handler(ticket, *, reason, verification_question):
        applied.append((ticket, reason, verification_question))
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "resolution_status": "VERIFIED_COMPLETE",
            "receipt": {"status": "VERIFIED_COMPLETE"},
        }

    monkeypatch.setattr(server, "_handle_home_resolve_plan", plan_handler)
    monkeypatch.setattr(server, "_handle_home_resolve_apply", apply_handler)
    app = daemon.create_app(elefante=server)
    transport = httpx.ASGITransport(app=app)
    origin = "http://localhost:8000"
    plan_payload = {
        "memory_id": left_id,
        "related_memory_id": right_id,
        "winner_memory_id": left_id,
        "confirm_protected": False,
    }

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1:8765",
    ) as client:
        unauthenticated = await client.post(
            "/control/resolve/plan",
            headers={"Origin": origin},
            json=plan_payload,
        )
        assert unauthenticated.status_code == 401
        assert unauthenticated.json()["error_code"] == "CONTROL_AUTH_REQUIRED"

        grant = server.home_control.issue(origin)
        headers = {
            "Origin": origin,
            "Authorization": f"Bearer {grant.token}",
        }
        planned = await client.post(
            "/control/resolve/plan",
            headers=headers,
            json=plan_payload,
        )
        assert planned.status_code == 200
        plan_body = planned.json()
        assert plan_body["plan_id"] == "one-use-plan-ticket"
        assert "record_sha256" not in plan_body["plan"]

        missing_confirmation = await client.post(
            "/control/resolve/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "confirm": False,
                "reason": "Current source verifies SQLite.",
                "verification_question": "Which database does Elefante use?",
            },
        )
        assert missing_confirmation.status_code == 400
        assert missing_confirmation.json()["error_code"] == "CONFIRMATION_REQUIRED"

        applied_response = await client.post(
            "/control/resolve/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "confirm": True,
                "reason": "Current source verifies SQLite.",
                "verification_question": "Which database does Elefante use?",
            },
        )
        assert applied_response.status_code == 200
        assert applied_response.json()["resolution_status"] == "VERIFIED_COMPLETE"

        replay = await client.post(
            "/control/resolve/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "confirm": True,
                "reason": "Current source verifies SQLite.",
                "verification_question": "Which database does Elefante use?",
            },
        )
        assert replay.status_code == 409
        assert replay.json()["error_code"] == "CONTROL_PLAN_NOT_FOUND"

    assert len(applied) == 1


@pytest.mark.asyncio
async def test_daemon_correction_control_binds_content_free_one_use_plan(monkeypatch):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    memory_id = "11111111-1111-4111-8111-111111111111"
    tokens = iter(["browser-control-token", "one-use-correction-ticket"])
    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        max_requests=10,
    )
    applied: list[object] = []

    async def plan_handler(payload):
        assert payload == {
            "memory_id": memory_id,
            "correction": "edit",
            "content": "Corrected project decision.",
            "confirm_protected": False,
        }
        return {
            "success": True,
            "plan": {
                "schema_version": 1,
                "action": "edit",
                "memory_id": memory_id,
                "applicable": True,
                "reason_code": None,
                "reason": "The correction is ready for explicit confirmation.",
                "protected": False,
                "irreversible": False,
                "record_sha256": {"target": "a" * 64},
                "graph_sha256": {
                    "target": "b" * 64,
                    "target_relationships": "e" * 64,
                },
                "scope_sha256": "d" * 64,
                "content_sha256": "c" * 64,
            },
            "privacy_redactions": 0,
            "privacy_redacted_types": [],
        }

    async def apply_handler(
        ticket,
        *,
        content,
        reason,
        verification_question,
        confirm_permanent,
    ):
        assert confirm_permanent is False
        applied.append((ticket, content, reason, verification_question))
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "correction_status": "VERIFIED_COMPLETE",
            "receipt": {"status": "VERIFIED_COMPLETE"},
        }

    monkeypatch.setattr(server, "_handle_home_correction_plan", plan_handler)
    monkeypatch.setattr(server, "_handle_home_correction_apply", apply_handler)
    app = daemon.create_app(elefante=server)
    origin = "http://localhost:8000"
    grant = server.home_control.issue(origin)
    headers = {
        "Origin": origin,
        "Authorization": f"Bearer {grant.token}",
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8765",
    ) as client:
        planned = await client.post(
            "/control/corrections/plan",
            headers=headers,
            json={
                "memory_id": memory_id,
                "correction": "edit",
                "content": "Corrected project decision.",
                "confirm_protected": False,
            },
        )
        assert planned.status_code == 200
        plan_body = planned.json()
        assert plan_body["plan_id"] == "one-use-correction-ticket"
        assert "record_sha256" not in plan_body["plan"]
        assert "graph_sha256" not in plan_body["plan"]
        assert "content_sha256" not in plan_body["plan"]
        assert "Corrected project decision." not in json.dumps(plan_body)

        applied_response = await client.post(
            "/control/corrections/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "confirm": True,
                "content": "Corrected project decision.",
                "reason": "The user corrected this decision.",
                "verification_question": "What project decision applies?",
            },
        )
        assert applied_response.status_code == 200
        assert applied_response.json()["correction_status"] == "VERIFIED_COMPLETE"

        replay = await client.post(
            "/control/corrections/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "confirm": True,
                "content": "Corrected project decision.",
                "reason": "The user corrected this decision.",
                "verification_question": "What project decision applies?",
            },
        )
        assert replay.status_code == 409
        assert replay.json()["error_code"] == "CONTROL_PLAN_NOT_FOUND"

    assert len(applied) == 1
    ticket = applied[0][0]
    assert isinstance(ticket, HomeCorrectionTicket)
    assert ticket.content_sha256 == "c" * 64
    assert not hasattr(ticket, "content")


@pytest.mark.asyncio
async def test_daemon_permanent_delete_keeps_plan_until_final_confirmation(
    monkeypatch,
):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    memory_id = "22222222-2222-4222-8222-222222222222"
    tokens = iter(["browser-control-token", "permanent-delete-ticket"])
    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        max_requests=10,
    )
    applied: list[HomeCorrectionTicket] = []

    async def plan_handler(_payload):
        return {
            "success": True,
            "plan": {
                "schema_version": 1,
                "action": "permanent_delete",
                "memory_id": memory_id,
                "applicable": True,
                "reason_code": None,
                "reason": "A temporary verified backup will protect the operation.",
                "protected": False,
                "irreversible": True,
                "record_sha256": {"target": "a" * 64},
                "graph_sha256": {
                    "target": "b" * 64,
                    "target_relationships": "c" * 64,
                },
            },
            "privacy_redactions": 0,
            "privacy_redacted_types": [],
        }

    async def apply_handler(
        ticket,
        *,
        content,
        reason,
        verification_question,
        confirm_permanent,
    ):
        assert content is None
        assert reason and verification_question
        assert confirm_permanent is True
        applied.append(ticket)
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "correction_status": "VERIFIED_COMPLETE",
            "receipt": {
                "status": "VERIFIED_COMPLETE",
                "recoverable": False,
            },
        }

    monkeypatch.setattr(server, "_handle_home_correction_plan", plan_handler)
    monkeypatch.setattr(server, "_handle_home_correction_apply", apply_handler)
    app = daemon.create_app(elefante=server)
    origin = "http://localhost:8000"
    grant = server.home_control.issue(origin)
    headers = {
        "Origin": origin,
        "Authorization": f"Bearer {grant.token}",
    }
    apply_payload = {
        "plan_id": "permanent-delete-ticket",
        "confirm": True,
        "reason": "The user requested erasure.",
        "verification_question": "What should no longer be recalled?",
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8765",
    ) as client:
        planned = await client.post(
            "/control/corrections/plan",
            headers=headers,
            json={
                "memory_id": memory_id,
                "correction": "permanent_delete",
                "confirm_protected": False,
            },
        )
        assert planned.status_code == 200

        missing = await client.post(
            "/control/corrections/apply",
            headers=headers,
            json=apply_payload,
        )
        assert missing.status_code == 400
        assert missing.json()["error_code"] == "PERMANENT_CONFIRMATION_REQUIRED"
        assert applied == []

        confirmed = await client.post(
            "/control/corrections/apply",
            headers=headers,
            json={**apply_payload, "confirm_permanent": True},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["receipt"]["recoverable"] is False

    assert len(applied) == 1


@pytest.mark.asyncio
async def test_daemon_health_control_returns_read_only_state_without_ticket(
    monkeypatch,
):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: "browser-control-token",
        session_ttl_seconds=300,
        max_requests=5,
    )

    async def plan_handler(*, action, archive_name, project_id):
        assert action == "health"
        assert archive_name is None
        assert project_id is None
        return {
            "success": True,
            "health": {
                "schema_version": 1,
                "state": "NEEDS_ATTENTION",
                "summary": "A verified backup is required.",
                "next_action": "back_up_now",
                "diagnostic_codes": ["verified_backup_missing"],
                "checks": [],
                "connected_agents": ["Codex"],
                "recall_verified_at": "2026-08-30T12:00:00+00:00",
                "valid_backups": 0,
                "invalid_backups": 0,
                "latest_verified_backup_at": None,
            },
            "recovery_history": [],
        }

    monkeypatch.setattr(server, "_handle_home_recovery_plan", plan_handler)
    app = daemon.create_app(elefante=server)
    origin = "http://localhost:8000"
    grant = server.home_control.issue(origin)
    headers = {
        "Origin": origin,
        "Authorization": f"Bearer {grant.token}",
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8765",
    ) as client:
        response = await client.post(
            "/control/recovery/plan",
            headers=headers,
            json={"action": "health"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["plan_id"] is None
        assert body["plan"] is None
        assert body["health"]["state"] == "NEEDS_ATTENTION"
        assert body["health"]["next_action"] == "back_up_now"
        assert body["health"]["connected_agents"] == ["Codex"]

        rejected = await client.post(
            "/control/recovery/plan",
            headers=headers,
            json={"action": "health", "archive_name": "backup.zip"},
        )
        assert rejected.status_code == 400
        assert rejected.json()["error_code"] == "CONTROL_FIELDS_INVALID"


@pytest.mark.asyncio
async def test_daemon_recover_control_binds_content_free_one_use_plan(monkeypatch):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    tokens = iter(["browser-control-token", "one-use-recovery-ticket"])
    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        max_requests=10,
    )
    applied: list[HomeRecoveryTicket] = []

    async def plan_handler(*, action, archive_name, project_id):
        assert action == "backup"
        assert archive_name is None
        assert project_id is None
        return {
            "success": True,
            "plan": {
                "schema_version": 1,
                "action": "backup",
                "applicable": True,
                "reason_code": None,
                "reason": "Writes will pause while the archive is verified.",
                "layout_sha256": "d" * 64,
                "storage_layout": "managed",
                "data_directory": "/private/customer/data",
                "backup_directory": "/private/customer/backups",
                "estimated_files": 4,
                "estimated_bytes": 4096,
                "irreversible": False,
            },
            "recovery_history": [
                {
                    "operation_id": "previous-operation",
                    "status": "VERIFIED_COMPLETE",
                    "archive_name": "previous.zip",
                }
            ],
        }

    async def apply_handler(ticket, *, verification_question):
        assert verification_question is None
        applied.append(ticket)
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "recovery_status": "VERIFIED_COMPLETE",
            "receipt": {
                "status": "VERIFIED_COMPLETE",
                "archive_name": "new-backup.zip",
            },
        }

    monkeypatch.setattr(server, "_handle_home_recovery_plan", plan_handler)
    monkeypatch.setattr(server, "_handle_home_recovery_apply", apply_handler)
    app = daemon.create_app(elefante=server)
    origin = "http://localhost:8000"
    grant = server.home_control.issue(origin)
    headers = {
        "Origin": origin,
        "Authorization": f"Bearer {grant.token}",
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8765",
    ) as client:
        planned = await client.post(
            "/control/recovery/plan",
            headers=headers,
            json={"action": "backup"},
        )
        assert planned.status_code == 200
        plan_body = planned.json()
        assert plan_body["plan_id"] == "one-use-recovery-ticket"
        assert "layout_sha256" not in plan_body["plan"]
        assert "private customer" not in json.dumps(plan_body)

        missing_confirmation = await client.post(
            "/control/recovery/apply",
            headers=headers,
            json={"plan_id": plan_body["plan_id"], "confirm": False},
        )
        assert missing_confirmation.status_code == 400
        assert missing_confirmation.json()["error_code"] == "CONFIRMATION_REQUIRED"

        completed = await client.post(
            "/control/recovery/apply",
            headers=headers,
            json={"plan_id": plan_body["plan_id"], "confirm": True},
        )
        assert completed.status_code == 200
        assert completed.json()["recovery_status"] == "VERIFIED_COMPLETE"

        replay = await client.post(
            "/control/recovery/apply",
            headers=headers,
            json={"plan_id": plan_body["plan_id"], "confirm": True},
        )
        assert replay.status_code == 409
        assert replay.json()["error_code"] == "CONTROL_PLAN_NOT_FOUND"

    assert len(applied) == 1
    assert isinstance(applied[0], HomeRecoveryTicket)
    assert applied[0].layout_sha256 == "d" * 64


@pytest.mark.asyncio
async def test_daemon_restore_control_lists_then_binds_one_archive_and_question(
    monkeypatch,
):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    tokens = iter(["browser-control-token", "one-use-restore-ticket"])
    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        max_requests=10,
    )
    archive_name = "elefante_data_backup_20260829.zip"
    project_id = "11111111-1111-4111-8111-111111111111"
    workspace_sha256 = "c" * 64
    applied: list[tuple[HomeRecoveryTicket, str | None]] = []

    async def plan_handler(*, action, archive_name: str | None, project_id: str | None):
        assert action == "restore"
        assert project_id == "11111111-1111-4111-8111-111111111111"
        return {
            "success": True,
            "plan": (
                {
                    "schema_version": 1,
                    "action": "restore",
                    "applicable": True,
                    "reason_code": None,
                    "reason": "Current data will be backed up before restore.",
                    "layout_sha256": "d" * 64,
                    "archive_name": archive_name,
                    "archive_sha256": "e" * 64,
                    "source_sha256": "f" * 64,
                    "estimated_files": 4,
                    "estimated_bytes": 4096,
                    "irreversible": False,
                }
                if archive_name is not None
                else None
            ),
            "available_backups": [
                {
                    "archive_name": "elefante_data_backup_20260829.zip",
                    "valid": True,
                    "archive_sha256": "e" * 64,
                    "source_sha256": "f" * 64,
                    "files": 4,
                    "bytes": 4096,
                }
            ],
            "recovery_history": [],
            "_recovery_project_id": project_id,
            "_recovery_workspace_sha256": workspace_sha256,
        }

    async def apply_handler(ticket, *, verification_question):
        applied.append((ticket, verification_question))
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "recovery_status": "VERIFIED_COMPLETE",
            "receipt": {
                "status": "VERIFIED_COMPLETE",
                "operation": "restore",
                "archive_name": ticket.archive_name,
            },
        }

    monkeypatch.setattr(server, "_handle_home_recovery_plan", plan_handler)
    monkeypatch.setattr(server, "_handle_home_recovery_apply", apply_handler)
    app = daemon.create_app(elefante=server)
    origin = "http://localhost:8000"
    grant = server.home_control.issue(origin, project_id=project_id)
    headers = {
        "Origin": origin,
        "Authorization": f"Bearer {grant.token}",
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8765",
    ) as client:
        listed = await client.post(
            "/control/recovery/plan",
            headers=headers,
            json={"action": "restore"},
        )
        assert listed.status_code == 200
        assert listed.json()["plan_id"] is None
        listed_archive = listed.json()["available_backups"][0]
        assert listed_archive["archive_name"] == archive_name
        assert "archive_sha256" not in listed_archive
        assert "source_sha256" not in listed_archive

        planned = await client.post(
            "/control/recovery/plan",
            headers=headers,
            json={"action": "restore", "archive_name": archive_name},
        )
        assert planned.status_code == 200
        plan_body = planned.json()
        assert plan_body["plan_id"] == "one-use-restore-ticket"
        assert "layout_sha256" not in plan_body["plan"]
        assert "archive_sha256" not in plan_body["plan"]
        assert "source_sha256" not in plan_body["plan"]

        missing_question = await client.post(
            "/control/recovery/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "action": "restore",
                "confirm": True,
            },
        )
        assert missing_question.status_code == 400
        assert (
            missing_question.json()["error_code"]
            == "RECOVERY_VERIFICATION_QUESTION_REQUIRED"
        )

        completed = await client.post(
            "/control/recovery/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "action": "restore",
                "confirm": True,
                "verification_question": "What restored decision applies?",
            },
        )
        assert completed.status_code == 200
        assert completed.json()["recovery_status"] == "VERIFIED_COMPLETE"
        assert "What restored decision applies?" not in completed.text

        replay = await client.post(
            "/control/recovery/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "action": "restore",
                "confirm": True,
                "verification_question": "What restored decision applies?",
            },
        )
        assert replay.status_code == 409
        assert replay.json()["error_code"] == "CONTROL_PLAN_NOT_FOUND"

    assert len(applied) == 1
    ticket, question = applied[0]
    assert ticket.action == "restore"
    assert ticket.archive_name == archive_name
    assert ticket.archive_sha256 == "e" * 64
    assert ticket.project_id == project_id
    assert ticket.workspace_sha256 == workspace_sha256
    assert question == "What restored decision applies?"


@pytest.mark.asyncio
async def test_daemon_support_report_previews_applies_once_and_downloads(monkeypatch):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    tokens = iter(["browser-control-token", "one-use-support-ticket"])
    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: next(tokens),
        session_ttl_seconds=300,
        max_requests=12,
    )
    applied: list[HomeRecoveryTicket] = []
    archive_name = "elefante_support_20260830120000_12345678.zip"
    archive_bytes = b"PK\x03\x04verified-private-report"

    async def plan_handler(*, action, archive_name, project_id):
        assert action == "support_report"
        assert archive_name is None
        assert project_id is None
        return {
            "success": True,
            "plan": {
                "schema_version": 1,
                "action": "support_report",
                "applicable": True,
                "reason_code": None,
                "reason": "Preview only allowlisted facts.",
                "report_sha256": "f" * 64,
                "preview": {
                    "schema_version": 1,
                    "product": {"recorded": True, "version": "2.13.0"},
                    "environment": {"operating_system": "Darwin"},
                    "readiness": {
                        "ready": True,
                        "customer_ready": True,
                        "runtime": {},
                        "daemon": {},
                        "recall": {},
                    },
                    "agent_connection": {
                        "detected": ["codex"],
                        "verified": ["codex"],
                        "uncovered": [],
                    },
                    "installer_ownership": {},
                    "diagnostic_codes": [],
                    "backups": {"valid": 1, "invalid": 0, "latest_verified_at": None},
                    "operation_receipts": {
                        "package": {"status": "available"},
                        "recovery_history_status": "available",
                        "recovery": [],
                        "omitted_invalid_receipts": 0,
                    },
                },
                "included": ["product and build identity"],
                "excluded": ["memory content"],
                "estimated_bytes": 1024,
                "irreversible": False,
            },
            "recovery_history": [],
        }

    async def apply_handler(ticket, *, verification_question):
        assert verification_question is None
        applied.append(ticket)
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "recovery_status": "VERIFIED_COMPLETE",
            "receipt": {
                "status": "VERIFIED_COMPLETE",
                "operation": "support_report",
                "archive_name": archive_name,
            },
        }

    class _ReportService:
        @staticmethod
        def support_report_bytes(selected):
            assert selected == archive_name
            return archive_bytes

    monkeypatch.setattr(server, "_handle_home_recovery_plan", plan_handler)
    monkeypatch.setattr(server, "_handle_home_recovery_apply", apply_handler)
    monkeypatch.setattr(server, "_verified_recovery_service", lambda: _ReportService())
    app = daemon.create_app(elefante=server)
    origin = "http://localhost:8000"
    grant = server.home_control.issue(origin)
    headers = {"Origin": origin, "Authorization": f"Bearer {grant.token}"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8765",
    ) as client:
        planned = await client.post(
            "/control/recovery/plan",
            headers=headers,
            json={"action": "support_report"},
        )
        assert planned.status_code == 200
        plan_body = planned.json()
        assert plan_body["plan_id"] == "one-use-support-ticket"
        assert "report_sha256" not in plan_body["plan"]
        assert plan_body["plan"]["excluded"] == ["memory content"]

        completed = await client.post(
            "/control/recovery/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "action": "support_report",
                "confirm": True,
            },
        )
        assert completed.status_code == 200
        assert completed.json()["recovery_status"] == "VERIFIED_COMPLETE"

        downloaded = await client.post(
            "/control/recovery/support-report/download",
            headers=headers,
            json={"archive_name": archive_name},
        )
        assert downloaded.status_code == 200
        assert downloaded.content == archive_bytes
        assert downloaded.headers["cache-control"] == "no-store"
        assert archive_name in downloaded.headers["content-disposition"]

        replay = await client.post(
            "/control/recovery/apply",
            headers=headers,
            json={
                "plan_id": plan_body["plan_id"],
                "action": "support_report",
                "confirm": True,
            },
        )
        assert replay.status_code == 409
        assert replay.json()["error_code"] == "CONTROL_PLAN_NOT_FOUND"

    assert len(applied) == 1
    assert applied[0].report_sha256 == "f" * 64


@pytest.mark.asyncio
async def test_daemon_control_rejects_duplicate_json_unknown_fields_and_origins(
    monkeypatch,
):
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    server = ElefanteMCPServer()
    server.home_control = HomeControlRegistry(
        token_factory=lambda: "security-control-token",
        max_requests=10,
    )

    async def forbidden_plan(_payload):
        raise AssertionError("Rejected requests must not inspect durable stores")

    monkeypatch.setattr(server, "_handle_home_resolve_plan", forbidden_plan)
    app = daemon.create_app(elefante=server)
    transport = httpx.ASGITransport(app=app)
    origin = "http://localhost:8000"
    grant = server.home_control.issue(origin)
    headers = {
        "Origin": origin,
        "Authorization": f"Bearer {grant.token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1:8765",
    ) as client:
        duplicate = await client.post(
            "/control/resolve/plan",
            headers=headers,
            content=(
                '{"memory_id":"one","memory_id":"two",'
                '"related_memory_id":"three"}'
            ),
        )
        assert duplicate.status_code == 400
        assert duplicate.json()["error_code"] == "CONTROL_JSON_INVALID"

        unknown = await client.post(
            "/control/resolve/plan",
            headers=headers,
            json={
                "memory_id": "one",
                "related_memory_id": "two",
                "action": "arbitrary-mcp-call",
            },
        )
        assert unknown.status_code == 400
        assert unknown.json()["error_code"] == "CONTROL_FIELDS_INVALID"

        wrong_origin = await client.post(
            "/control/resolve/plan",
            headers={**headers, "Origin": "http://evil.example"},
            json={"memory_id": "one", "related_memory_id": "two"},
        )
        assert wrong_origin.status_code == 403
        assert wrong_origin.json()["error_code"] == "CONTROL_ORIGIN_REJECTED"
        assert "access-control-allow-origin" not in wrong_origin.headers

        oversized = await client.post(
            "/control/resolve/plan",
            headers=headers,
            content=b"{" + (b" " * daemon.MAX_HOME_CONTROL_BYTES) + b"}",
        )
        assert oversized.status_code == 413
        assert oversized.json()["error_code"] == "CONTROL_BODY_TOO_LARGE"

        preflight = await client.options(
            "/control/resolve/plan",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin
        assert "authorization" in preflight.headers[
            "access-control-allow-headers"
        ].casefold()

        generic_mcp_preflight = await client.options(
            "/mcp",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert "access-control-allow-origin" not in generic_mcp_preflight.headers

        event_preflight = await client.options(
            "/events/surface",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" not in event_preflight.headers


@pytest.mark.asyncio
async def test_home_apply_uses_ticket_hashes_and_bypasses_mcp_compliance_gate(
    monkeypatch,
):
    from src.mcp.server import ElefanteMCPServer

    left = Memory(
        content="Elefante uses SQLite.",
        metadata=MemoryMetadata(project="elefante", scope="project:elefante"),
    )
    right = Memory(
        content="Elefante uses ChromaDB.",
        metadata=MemoryMetadata(project="elefante", scope="project:elefante"),
    )
    memories = {left.id: left, right.id: right}
    captured: dict[str, object] = {}

    class Store:
        async def get_memory(self, memory_id):
            return memories.get(memory_id)

    class Service:
        async def execute(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                status=VerifiedResolveStatus.VERIFIED_COMPLETE,
                to_dict=lambda: {
                    "success": True,
                    "status": "VERIFIED_COMPLETE",
                    "receipt": {"status": "VERIFIED_COMPLETE"},
                },
            )

    @asynccontextmanager
    async def acquired_write():
        yield SimpleNamespace(acquired=True)

    server = ElefanteMCPServer()

    async def get_orchestrator():
        return SimpleNamespace(vector_store=Store())

    monkeypatch.setattr(server, "_get_orchestrator", get_orchestrator)
    monkeypatch.setattr(server, "_verified_resolve_service", lambda _value: Service())
    monkeypatch.setattr(server, "_write_operation", acquired_write)
    monkeypatch.setattr(server, "_authority_violation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        server,
        "_check_compliance_gate",
        lambda _tool: (_ for _ in ()).throw(
            AssertionError("Home ticket replaces the MCP search receipt")
        ),
    )
    hashes = {"left": "a" * 64, "right": "b" * 64}
    ticket = HomeResolveTicket(
        ticket_id=str(uuid4()),
        left_memory_id=str(left.id),
        right_memory_id=str(right.id),
        winner_memory_id=str(left.id),
        confirm_protected=False,
        record_sha256=hashes,
        expires_at_monotonic=999.0,
    )

    result = await server._handle_home_resolve_apply(
        ticket,
        reason="Current source verifies SQLite.",
        verification_question="Which database does Elefante use?",
    )

    assert result["resolution_status"] == "VERIFIED_COMPLETE"
    assert captured["args"] == (left.id, right.id)
    assert captured["kwargs"]["expected_record_sha256"] == hashes
    assert captured["kwargs"]["verification_question"] == (
        "Which database does Elefante use?"
    )


@pytest.mark.asyncio
async def test_home_correction_apply_uses_ticket_hashes_and_write_lock(monkeypatch):
    from src.mcp.server import ElefanteMCPServer

    memory = Memory(
        content="Old project decision.",
        metadata=MemoryMetadata(
            project="elefante",
            workspace="/tmp/elefante",
            scope="project:elefante",
        ),
    )
    captured: dict[str, object] = {}

    class Store:
        async def get_memory(self, memory_id):
            return memory if memory_id == memory.id else None

    class Service:
        async def execute(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                status=SimpleNamespace(value="VERIFIED_COMPLETE"),
                to_dict=lambda: {
                    "success": True,
                    "status": "VERIFIED_COMPLETE",
                    "receipt": {"status": "VERIFIED_COMPLETE"},
                },
            )

    @asynccontextmanager
    async def acquired_write():
        captured["locked"] = True
        yield SimpleNamespace(acquired=True)

    server = ElefanteMCPServer()

    async def get_orchestrator():
        return SimpleNamespace(vector_store=Store())

    monkeypatch.setattr(server, "_get_orchestrator", get_orchestrator)
    monkeypatch.setattr(server, "_verified_correction_service", lambda *_a, **_k: Service())
    monkeypatch.setattr(server, "_write_operation", acquired_write)
    monkeypatch.setattr(server, "_authority_violation", lambda *_a, **_k: None)
    monkeypatch.setattr(
        server,
        "_check_compliance_gate",
        lambda _tool: (_ for _ in ()).throw(
            AssertionError("Home ticket replaces the MCP search receipt")
        ),
    )
    ticket = HomeCorrectionTicket(
        ticket_id=str(uuid4()),
        memory_id=str(memory.id),
        action="edit",
        confirm_protected=False,
        record_sha256={"target": "a" * 64},
        graph_sha256={
            "target": "b" * 64,
            "target_relationships": "d" * 64,
        },
        content_sha256="c" * 64,
        expires_at_monotonic=999.0,
    )

    result = await server._handle_home_correction_apply(
        ticket,
        content="Corrected project decision.",
        reason="The user corrected this decision.",
        verification_question="What project decision applies?",
    )

    assert result["correction_status"] == "VERIFIED_COMPLETE"
    assert captured["locked"] is True
    assert captured["args"] == (memory.id,)
    assert captured["kwargs"]["expected_record_sha256"] == {"target": "a" * 64}
    assert captured["kwargs"]["expected_graph_sha256"] == {
        "target": "b" * 64,
        "target_relationships": "d" * 64,
    }
    assert captured["kwargs"]["expected_content_sha256"] == "c" * 64


@pytest.mark.asyncio
async def test_home_project_control_manages_registry_without_touching_project_files(
    tmp_path,
    monkeypatch,
):
    from src.core.project_registry import ProjectRegistry
    from src.mcp import daemon
    from src.mcp.server import ElefanteMCPServer

    alpha_root = tmp_path / "company" / "alpha"
    beta_root = tmp_path / "company" / "beta"
    alpha_root.mkdir(parents=True)
    beta_root.mkdir(parents=True)
    marker = alpha_root / "customer.txt"
    marker.write_text("preserve", encoding="utf-8")

    server = ElefanteMCPServer()
    server._project_registry = ProjectRegistry(tmp_path / "data" / "projects.json")
    server.home_control = HomeControlRegistry(
        token_factory=lambda: "project-control-token",
        max_requests=20,
    )

    @asynccontextmanager
    async def acquired_write():
        yield SimpleNamespace(acquired=True)

    async def empty_project_review(*, offset, limit):
        assert (offset, limit) == (0, 1)
        return {"success": True, "review_required": False}

    monkeypatch.setattr(server, "_write_operation", acquired_write)
    monkeypatch.setattr(server, "_legacy_unscoped_review", empty_project_review)
    app = daemon.create_app(elefante=server)
    origin = "http://localhost:8000"
    grant = server.home_control.issue(origin)
    headers = {
        "Origin": origin,
        "Authorization": f"Bearer {grant.token}",
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1:8765",
    ) as client:
        unauthenticated = await client.post(
            "/control/projects/manage",
            headers={"Origin": origin},
            json={"action": "register", "name": "Alpha", "root": str(alpha_root)},
        )
        assert unauthenticated.status_code == 401

        alpha = await client.post(
            "/control/projects/manage",
            headers=headers,
            json={"action": "register", "name": "Alpha", "root": str(alpha_root)},
        )
        beta = await client.post(
            "/control/projects/manage",
            headers=headers,
            json={"action": "register", "name": "Beta", "root": str(beta_root)},
        )
        assert alpha.status_code == 200
        assert beta.status_code == 200
        alpha_id = alpha.json()["project"]["project_id"]

        strict = await client.post(
            "/control/projects/manage",
            headers=headers,
            json={"action": "set_mode", "mode": "strict", "confirm": True},
        )
        assert strict.status_code == 200
        assert strict.json()["project_registry"]["mode"] == "strict"

        unconfirmed = await client.post(
            "/control/projects/manage",
            headers=headers,
            json={"action": "remove", "project_id": alpha_id, "confirm": False},
        )
        assert unconfirmed.status_code == 409
        assert unconfirmed.json()["error_code"] == "CONFIRMATION_REQUIRED"

        removed = await client.post(
            "/control/projects/manage",
            headers=headers,
            json={"action": "remove", "project_id": alpha_id, "confirm": True},
        )
        assert removed.status_code == 200
        assert removed.json()["status"] == "PROJECT_REMOVED"
        assert marker.read_text(encoding="utf-8") == "preserve"

        downgrade = await client.post(
            "/control/projects/manage",
            headers=headers,
            json={"action": "set_mode", "mode": "compatibility", "confirm": True},
        )
        assert downgrade.status_code == 409
        assert downgrade.json()["error_code"] == "PROJECT_MODE_INVALID"

    project_snapshot_path = Path(server._project_registry.path.parent) / "dashboard_snapshot.json"
    snapshot = json.loads(project_snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["project_registry"]["mode"] == "strict"
    assert [project["name"] for project in snapshot["project_registry"]["projects"]] == ["Beta"]


@pytest.mark.asyncio
async def test_strict_project_mode_waits_for_legacy_review(tmp_path, monkeypatch):
    from src.core.project_registry import ProjectRegistry
    from src.mcp.server import ElefanteMCPServer

    root = tmp_path / "customer-project"
    root.mkdir()
    server = ElefanteMCPServer()
    registry = ProjectRegistry(tmp_path / "data" / "projects.json")
    registry.register("Customer project", root)
    server._project_registry = registry

    @asynccontextmanager
    async def acquired_write():
        yield SimpleNamespace(acquired=True)

    async def pending_review(*, offset, limit):
        assert (offset, limit) == (0, 1)
        return {
            "success": True,
            "review_required": True,
            "total_unscoped": 1,
        }

    monkeypatch.setattr(server, "_write_operation", acquired_write)
    monkeypatch.setattr(server, "_legacy_unscoped_review", pending_review)

    result = await server._handle_home_project_action(
        {"action": "set_mode", "mode": "strict", "confirm": True}
    )

    assert result["success"] is False
    assert result["changed"] is False
    assert result["error_code"] == "PROJECT_REVIEW_REQUIRED"
    assert registry.mode.value == "compatibility"
    assert not registry.strict_marker_path.exists()


@pytest.mark.asyncio
async def test_home_project_change_restores_exact_registry_when_snapshot_publish_fails(
    tmp_path,
    monkeypatch,
):
    from src.core.project_registry import ProjectRegistry
    from src.mcp.server import ElefanteMCPServer

    alpha_root = tmp_path / "alpha"
    beta_root = tmp_path / "beta"
    alpha_root.mkdir()
    beta_root.mkdir()
    server = ElefanteMCPServer()
    registry = ProjectRegistry(tmp_path / "data" / "projects.json")
    registry.register("Alpha", alpha_root)
    server._project_registry = registry
    snapshot_path = registry.path.parent / "dashboard_snapshot.json"
    snapshot_path.write_text(
        '{"schema_version":2,"project_registry":{},"project_registry":{}}',
        encoding="utf-8",
    )
    snapshot_path.chmod(0o640)
    registry_before = registry.path.read_bytes()
    registry_mode_before = registry.path.stat().st_mode & 0o777
    snapshot_before = snapshot_path.read_bytes()

    @asynccontextmanager
    async def acquired_write():
        yield SimpleNamespace(acquired=True)

    monkeypatch.setattr(server, "_write_operation", acquired_write)

    result = await server._handle_home_project_action(
        {"action": "register", "name": "Beta", "root": str(beta_root)}
    )

    assert result["success"] is False
    assert result["status"] == "PROJECT_FAILED_ROLLED_BACK"
    assert result["changed"] is False
    assert result["error_code"] == "PROJECT_OPERATION_FAILED"
    assert registry.path.read_bytes() == registry_before
    assert registry.path.stat().st_mode & 0o777 == registry_mode_before
    assert snapshot_path.read_bytes() == snapshot_before
    assert snapshot_path.stat().st_mode & 0o777 == 0o640
    assert [project.name for project in registry.list_projects()] == ["Alpha"]
    assert not registry.strict_marker_path.exists()
