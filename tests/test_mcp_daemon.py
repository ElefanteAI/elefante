"""Runtime contracts for the shared local MCP daemon and its bridge."""

from contextlib import asynccontextmanager, contextmanager
import concurrent.futures
import io
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from mcp import types as mcp_types

from src.mcp.server import (
    ElefanteMCPServer,
    MEMORY_SEARCH_GUIDANCE,
    RECALL_MAX_RESPONSE_TOKENS,
    answer_context_metadata,
    compile_answer_context,
)
from src.models.memory import Memory, MemoryMetadata, MemoryType
from src.models.query import SearchResult
from src.utils.token_counter import estimate_tokens


BRIDGE_RESPONSE_TIMEOUT_SECONDS = 60
EXPECTED_CUSTOMER_TOOLS = {
    "elefante-Memory",
    "elefante-Recall",
    "elefante-GraphConnect",
    "elefante-GraphQuery",
    "elefante-ContextGet",
    "elefante-SessionsList",
    "elefante-SystemStatusGet",
    "elefante-System",
    "elefante-Recover",
    "elefante-DashboardOpen",
    "elefante-ETLProcess",
    "elefante-ETLClassify",
    "elefante-TaskCreate",
    "elefante-TaskUpdate",
    "elefante-TaskGraph",
    "elefante-DirectiveAdd",
    "elefante-DirectiveList",
    "elefante-DirectiveRemove",
}


def _context_result(
    content: str,
    *,
    category: str = "project",
    memory_type: MemoryType = MemoryType.FACT,
    score: float = 0.7,
    vector_score: float = 0.7,
) -> SearchResult:
    return SearchResult(
        memory=Memory(
            content=content,
            metadata=MemoryMetadata(
                category=category,
                memory_type=memory_type,
            ),
        ),
        score=score,
        vector_score=vector_score,
        source="vector",
    )


def test_answer_context_selects_answer_bearing_memory_and_rejects_related_noise():
    relevant = _context_result(
        "Elefante customer installation uses one global runtime for every compatible IDE.",
        memory_type=MemoryType.DECISION,
        vector_score=0.70,
    )
    relevant.explanation = {
        "signals": [{"name": "concept_overlap", "score": 0.40}]
    }
    noise = _context_result(
        "Cognitive retrieval combines vector, authority, temporal, and concept scores.",
        score=0.95,
        vector_score=0.60,
    )

    context = compile_answer_context(
        "What did we decide about global installation across IDEs?",
        [noise, relevant],
    )

    assert "one global runtime" in context.text
    assert "Cognitive retrieval" not in context.text
    assert context.text.startswith("# Elefante answer context")
    assert context.selected_count == 1
    assert "decision" in context.selection_reasons[0]
    assert "signals=lexical" in context.selection_reasons[0]
    assert str(relevant.memory.id) not in context.text
    assert "[Evidence 1]" in context.text
    assert estimate_tokens(context.text) <= 450
    metadata = answer_context_metadata(
        "What did we decide about global installation across IDEs?",
        [noise, relevant],
    )
    assert metadata["selected_result_numbers"] == [2]
    assert metadata["selected_evidence"][0]["verified"] is False
    assert metadata["selected_evidence"][0]["reason_selected"] == context.selection_reasons[0]


def test_answer_context_abstains_and_withholds_unrequested_system_test_memory():
    passcode = _context_result(
        "The Elefante test passcode is Indigo-Echo.",
        category="system-test",
        score=0.99,
        vector_score=0.99,
    )

    unrelated = compile_answer_context(
        "How should Elefante improve answers using prior decisions?",
        [passcode],
    )
    explicit = compile_answer_context(
        "What is my Elefante test passcode?",
        [passcode],
    )

    assert unrelated.selected_count == 0
    assert "Indigo-Echo" not in unrelated.text
    assert explicit.selected_count == 1
    assert "Indigo-Echo" in explicit.text


def test_answer_context_abstains_when_only_one_weak_signal_matches():
    lexical_only = _context_result(
        "The global runtime decision is retained for compatible IDEs.",
        score=0.70,
        vector_score=0.70,
    )

    context = compile_answer_context(
        "What is the global runtime decision for compatible IDEs?",
        [lexical_only],
    )

    assert context.selected_count == 0
    assert context.selection_reasons == ()


def test_answer_context_surfaces_known_conflict_without_selecting_either_side():
    conflicting = _context_result(
        "Decision: use a global customer runtime for every compatible IDE.",
        memory_type=MemoryType.DECISION,
        score=0.95,
        vector_score=0.95,
    )
    conflicting.memory.metadata.conflict_ids = [uuid4()]

    context = compile_answer_context(
        "What is the customer runtime installation decision?",
        [conflicting],
    )

    assert context.selected_count == 0
    assert context.conflict_count == 1
    assert len(context.conflict_warnings) == 1
    assert "unresolved stored conflict" in context.text
    assert conflicting.memory.content not in context.text
    assert str(conflicting.memory.id) not in context.text

    metadata = answer_context_metadata(
        "What is the customer runtime installation decision?",
        [conflicting],
        context=context,
    )
    assert metadata["conflict_count"] == 1
    assert metadata["conflict_warnings"] == list(context.conflict_warnings)


def test_answer_context_reserves_user_locked_always_memory() -> None:
    mandatory = _context_result(
        "The customer release must use the signed installer.",
        score=0.05,
        vector_score=0.05,
    )
    mandatory.memory.metadata.injection_policy = "always"
    mandatory.memory.metadata.user_locked = True

    context = compile_answer_context("What is the release rule?", [mandatory])

    assert context.selected_count == 1
    assert str(mandatory.memory.id) in context.selected_memory_ids
    assert "user-locked always-inject" in context.selection_reasons[0]


def test_answer_context_rejects_unmatched_triggered_memory() -> None:
    triggered = _context_result("Installer signing policy for customer releases.")
    triggered.memory.metadata.injection_policy = "triggered"
    triggered.memory.metadata.trigger = ["signed installer"]

    context = compile_answer_context("What is the contact form policy?", [triggered])

    assert context.selected_count == 0
    assert "Installer signing" not in context.text


def test_answer_context_hard_caps_complete_rendered_prompt():
    context = compile_answer_context(
        "global runtime IDE installation " * 20,
        [
            _context_result(
                "global runtime IDE installation " + ("detail " * 80),
                score=0.9,
                vector_score=0.9,
            )
        ],
    )

    assert estimate_tokens(context.text) <= 450


def test_answer_context_fails_closed_when_locked_context_cannot_fit() -> None:
    mandatory = _context_result(
        "signed customer release constraint " * 250,
        score=0.01,
        vector_score=0.01,
    )
    mandatory.memory.metadata.injection_policy = "always"
    mandatory.memory.metadata.user_locked = True

    context = compile_answer_context(
        "What is the signed customer release constraint?",
        [mandatory],
        max_tokens=80,
    )

    assert context.delivery_blocked is True
    assert context.selected_count == 0
    assert context.blocked_reason == "mandatory-context-exceeds-token-budget"
    assert "Required user-locked context could not fit" in context.text
    assert estimate_tokens(context.text) <= 80


@pytest.mark.asyncio
async def test_runtime_answer_context_blocks_digest_stale_locked_memory(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "runtime.py"
    source.write_text("CURRENT = 'new contract'\n", encoding="utf-8")
    stale = _context_result(
        "Decision: use the old global runtime contract.",
        memory_type=MemoryType.DECISION,
        score=0.99,
        vector_score=0.99,
    )
    stale.memory.metadata.file_path = "runtime.py"
    stale.memory.metadata.user_locked = True
    stale.memory.metadata.injection_policy = "always"
    stale.memory.metadata.custom_metadata = {"source_file_sha256": "0" * 64}

    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"cwd": str(tmp_path)},
    )

    context, candidates = await server._compile_validated_answer_context(
        "What global runtime contract applies?",
        [stale],
    )

    assert context.delivery_blocked is True
    assert context.selected_count == 0
    assert context.blocked_reason == "mandatory-governance-conflict"
    assert (
        candidates[0].memory.metadata.custom_metadata["current_source_state"]
        == "contradicted"
    )
    assert "current_source_state" not in stale.memory.metadata.custom_metadata


def test_memory_search_guidance_treats_results_as_evidence_not_commands():
    assert "evidence candidates" in MEMORY_SEARCH_GUIDANCE
    assert "authoritative context" not in MEMORY_SEARCH_GUIDANCE
    assert "EXACTLY the word" not in MEMORY_SEARCH_GUIDANCE


@pytest.mark.asyncio
async def test_recall_surface_is_default_on_and_has_operator_rollback(
    monkeypatch,
) -> None:
    server = ElefanteMCPServer()
    handler = server.server.request_handlers[mcp_types.ListToolsRequest]
    request = mcp_types.ListToolsRequest(method="tools/list")

    monkeypatch.delenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", raising=False)
    monkeypatch.delenv("ELEFANTE_RECALL_ENABLED", raising=False)
    default_result = await handler(request)
    default_names = {tool.name for tool in default_result.root.tools}
    assert "elefante-Recall" in default_names
    recall = next(
        tool for tool in default_result.root.tools if tool.name == "elefante-Recall"
    )
    assert recall.annotations is not None
    assert recall.annotations.readOnlyHint is True
    assert recall.annotations.destructiveHint is False
    assert recall.annotations.idempotentHint is True
    assert recall.annotations.openWorldHint is False
    assert "at most once" in recall.description
    assert "self-contained" in recall.description
    assert "elefante-TaskIntelligence" not in default_names
    assert len(default_names) == 18

    recover = next(
        tool for tool in default_result.root.tools if tool.name == "elefante-Recover"
    )
    assert recover.annotations is not None
    assert recover.annotations.readOnlyHint is False
    assert recover.annotations.destructiveHint is True
    assert recover.annotations.idempotentHint is False
    assert recover.inputSchema["properties"]["action"]["enum"] == [
        "health",
        "backup",
        "restore",
        "support_report",
        "installation_acceptance",
    ]
    assert "installer-only" in recover.description
    assert recover.inputSchema["properties"]["workspace"]["maxLength"] == 2048

    monkeypatch.setenv("ELEFANTE_RECALL_ENABLED", "0")
    rolled_back_result = await handler(request)
    rolled_back_names = {tool.name for tool in rolled_back_result.root.tools}
    assert "elefante-Recall" not in rolled_back_names
    assert len(rolled_back_names) == 17

    call_handler = server.server.request_handlers[mcp_types.CallToolRequest]
    response = await call_handler(
        mcp_types.CallToolRequest(
            params=mcp_types.CallToolRequestParams(
                name="elefante-Recall",
                arguments={"question": "What did we decide about installation?"},
            )
        )
    )
    payload = json.loads(response.root.content[0].text)
    assert set(payload) == {
        "success",
        "status",
        "context",
        "supplied_count",
        "abstained",
        "delivery_blocked",
        "read_only",
    }
    assert payload["success"] is False
    assert payload["status"] == "unavailable"
    assert "disabled by the local operator" in payload["context"]
    assert "MANDATORY_PROTOCOLS_READ_THIS_FIRST" not in payload
    assert "ENTRYPOINT_SEQUENCE_READ_THIS_FIRST" not in payload
    assert "DIRECTIVES" not in payload
    assert "TOKEN_STATS" not in payload


@pytest.mark.asyncio
async def test_recover_backup_is_plan_first_and_binds_apply_to_exact_layout(
    monkeypatch,
) -> None:
    from src.core.verified_operation import VerifiedOperationStatus

    server = ElefanteMCPServer()
    applied: list[dict[str, str]] = []

    class _Plan:
        layout_sha256 = "a" * 64

        def to_dict(self):
            return {
                "schema_version": 1,
                "action": "backup",
                "applicable": True,
                "layout_sha256": self.layout_sha256,
                "reason": "Verified local backup plan.",
            }

    class _Result:
        status = VerifiedOperationStatus.VERIFIED_COMPLETE

        def to_dict(self):
            return {
                "success": True,
                "status": self.status.value,
                "receipt": {
                    "status": self.status.value,
                    "authority": "user_directed",
                    "archive_name": "elefante_data_backup.zip",
                },
            }

    class _Service:
        def plan_backup(self):
            return _Plan()

        def history(self):
            return ({"status": "VERIFIED_COMPLETE"},)

        async def execute_backup(self, *, expected_layout_sha256, authority):
            applied.append(
                {
                    "expected_layout_sha256": expected_layout_sha256,
                    "authority": authority,
                }
            )
            return _Result()

    monkeypatch.setattr(server, "_verified_recovery_service", lambda: _Service())

    preview = await server._handle_recover({"action": "backup"})

    assert preview["success"] is True
    assert preview["plan"]["layout_sha256"] == "a" * 64
    assert preview["recovery_history"] == [{"status": "VERIFIED_COMPLETE"}]
    assert applied == []

    unconfirmed = await server._handle_recover(
        {
            "action": "backup",
            "apply": True,
            "expected_layout_sha256": "a" * 64,
        }
    )
    assert unconfirmed["error_code"] == "CONFIRMATION_REQUIRED"
    assert applied == []

    result = await server._handle_recover(
        {
            "action": "backup",
            "apply": True,
            "confirm": True,
            "expected_layout_sha256": "a" * 64,
            "invocation_mode": "user_directed",
        }
    )

    assert result["success"] is True
    assert result["recovery_status"] == "VERIFIED_COMPLETE"
    assert applied == [
        {
            "expected_layout_sha256": "a" * 64,
            "authority": "user_directed",
        }
    ]


@pytest.mark.asyncio
async def test_installation_acceptance_rejects_non_installer_before_project_access(
    monkeypatch,
) -> None:
    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {
            "tool": "unknown-stdio",
            "transport": "stdio",
            "cwd": "/private/tmp/project",
        },
    )

    def unexpected_project_access(_args):
        raise AssertionError("project registry must not be read")

    monkeypatch.setattr(server, "_strict_project_resolution", unexpected_project_access)

    result = await server._handle_recover(
        {
            "action": "installation_acceptance",
            "workspace": "/private/tmp/project",
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "INSTALL_ACCEPTANCE_AUTHORITY_REQUIRED"
    assert result["recovery_status"] == "FAILED_NO_CHANGE"


@pytest.mark.asyncio
async def test_installation_acceptance_requires_strict_registered_project(
    monkeypatch,
) -> None:
    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"tool": "elefante-installer", "transport": "stdio"},
    )
    monkeypatch.setattr(server, "_strict_project_resolution", lambda _args: None)

    async def unexpected_orchestrator():
        raise AssertionError("storage must not open before strict project resolution")

    monkeypatch.setattr(server, "_get_orchestrator", unexpected_orchestrator)

    result = await server._handle_recover(
        {
            "action": "installation_acceptance",
            "workspace": "/private/tmp/project",
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "PROJECT_STRICT_MODE_REQUIRED"
    assert result["memory_read"] is False
    assert result["memory_written"] is False


@pytest.mark.asyncio
async def test_installation_acceptance_delegates_canonical_project_under_lock(
    monkeypatch,
) -> None:
    from src.core.verified_operation import VerifiedOperationStatus

    server = ElefanteMCPServer()
    project = SimpleNamespace(
        project_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        scope="project:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        root="/private/tmp/project",
    )
    resolution = SimpleNamespace(matched=True, project=project)
    orchestrator = SimpleNamespace()
    executed: list[dict[str, str]] = []

    class _Result:
        status = VerifiedOperationStatus.VERIFIED_COMPLETE

        def to_dict(self):
            return {
                "success": True,
                "action": "installation_acceptance",
                "status": self.status.value,
                "receipt": {"memory_content_included": False},
            }

    class _Service:
        async def execute(self, **kwargs):
            executed.append(kwargs)
            return _Result()

    async def get_orchestrator():
        return orchestrator

    @asynccontextmanager
    async def locked_operation():
        yield SimpleNamespace(acquired=True)

    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"tool": "elefante-installer", "transport": "stdio"},
    )
    monkeypatch.setattr(
        server,
        "_strict_project_resolution",
        lambda _args: resolution,
    )
    monkeypatch.setattr(server, "_get_orchestrator", get_orchestrator)
    monkeypatch.setattr(
        server,
        "_install_acceptance_service",
        lambda selected: _Service() if selected is orchestrator else None,
    )
    monkeypatch.setattr(server, "_write_operation", locked_operation)

    result = await server._handle_recover(
        {
            "action": "installation_acceptance",
            "workspace": "/private/tmp/project/nested",
        }
    )

    assert result["success"] is True
    assert result["recovery_status"] == "VERIFIED_COMPLETE"
    assert executed == [
        {
            "project_id": project.project_id,
            "project_scope": project.scope,
            "workspace": project.root,
        }
    ]


@pytest.mark.asyncio
async def test_installation_acceptance_fails_closed_when_write_lock_is_busy(
    monkeypatch,
) -> None:
    server = ElefanteMCPServer()
    project = SimpleNamespace(
        project_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        scope="project:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        root="/private/tmp/project",
    )

    async def get_orchestrator():
        return SimpleNamespace()

    @asynccontextmanager
    async def busy_operation():
        yield SimpleNamespace(acquired=False)

    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"tool": "elefante-installer", "transport": "stdio"},
    )
    monkeypatch.setattr(
        server,
        "_strict_project_resolution",
        lambda _args: SimpleNamespace(matched=True, project=project),
    )
    monkeypatch.setattr(server, "_get_orchestrator", get_orchestrator)
    monkeypatch.setattr(server, "_install_acceptance_service", lambda _item: object())
    monkeypatch.setattr(server, "_write_operation", busy_operation)

    result = await server._handle_recover(
        {
            "action": "installation_acceptance",
            "workspace": project.root,
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "WRITE_LOCK_BUSY"
    assert result["retry"] is True


@pytest.mark.asyncio
async def test_recover_health_is_read_only_and_returns_one_safe_next_action(
    monkeypatch,
) -> None:
    server = ElefanteMCPServer()

    class _Health:
        def to_dict(self):
            return {
                "schema_version": 1,
                "state": "NEEDS_ATTENTION",
                "summary": "A verified backup is required.",
                "next_action": "back_up_now",
                "diagnostic_codes": ["verified_backup_missing"],
                "checks": [],
                "valid_backups": 0,
                "invalid_backups": 0,
                "latest_verified_backup_at": None,
            }

    class _Service:
        def history(self):
            return ({"status": "VERIFIED_COMPLETE"},)

        async def check_health(self):
            return _Health()

    monkeypatch.setattr(server, "_verified_recovery_service", lambda: _Service())

    result = await server._handle_recover({"action": "health"})

    assert result["success"] is True
    assert result["action"] == "health"
    assert result["health"]["state"] == "NEEDS_ATTENTION"
    assert result["health"]["next_action"] == "back_up_now"
    assert result["recovery_history"] == [{"status": "VERIFIED_COMPLETE"}]

    rejected = await server._handle_recover(
        {"action": "health", "apply": True, "confirm": True}
    )
    assert rejected["success"] is False
    assert rejected["error_code"] == "RECOVERY_FIELDS_INVALID"


@pytest.mark.asyncio
async def test_recovery_health_uses_existing_doctor_through_async_boundary(
    monkeypatch,
    tmp_path,
) -> None:
    from scripts.lifecycle import doctor
    from src.utils import config as config_module

    data_dir = tmp_path / "home" / "data"
    fake_config = SimpleNamespace(
        elefante=SimpleNamespace(
            data_dir=str(data_dir),
            vector_store=SimpleNamespace(
                persist_directory=str(data_dir / "vector"),
            ),
            graph_store=SimpleNamespace(
                database_path=str(data_dir / "kuzu_db"),
            ),
        )
    )
    seen: dict[str, Path] = {}

    def build_report(*, repo_root, home):
        seen["repo_root"] = repo_root
        seen["home"] = home
        return {
            "ready": True,
            "customer_ready": True,
            "daemon": {"daemon_health": True},
            "host_coverage": {"verified": ["codex"]},
            "recall": {"required": True, "ready": True},
            "diagnostics": [],
            "customer_diagnostics": [],
        }

    monkeypatch.setattr(config_module, "get_config", lambda: fake_config)
    monkeypatch.setattr(doctor, "build_report", build_report)
    monkeypatch.setenv(
        "ELEFANTE_BACKUP_DIR",
        str(tmp_path / "customer-selected-path-must-be-ignored"),
    )

    recovery = ElefanteMCPServer()._verified_recovery_service()
    assert recovery.backup_dir == tmp_path / "home" / "backups"
    health = await recovery.check_health()

    assert health.state == "NEEDS_ATTENTION"
    assert health.next_action == "back_up_now"
    assert seen["repo_root"] == Path(__file__).resolve().parents[1]
    assert seen["home"] == Path.home()


@pytest.mark.asyncio
async def test_recover_restore_lists_then_binds_archive_and_private_recall_question(
    monkeypatch,
) -> None:
    from src.core.verified_operation import VerifiedOperationStatus

    server = ElefanteMCPServer()
    applied: list[dict[str, str]] = []
    recovery_scopes: list[dict[str, str]] = []
    archive_name = "elefante_data_backup_20260829.zip"

    class _Archive:
        def to_dict(self):
            return {
                "archive_name": archive_name,
                "valid": True,
                "archive_sha256": "b" * 64,
                "source_sha256": "c" * 64,
                "files": 4,
                "bytes": 4096,
            }

    class _Plan:
        layout_sha256 = "a" * 64
        archive_sha256 = "b" * 64

        def to_dict(self):
            return {
                "schema_version": 1,
                "action": "restore",
                "applicable": True,
                "layout_sha256": self.layout_sha256,
                "archive_name": archive_name,
                "archive_sha256": self.archive_sha256,
                "source_sha256": "c" * 64,
                "reason": "Verified restore plan.",
            }

    class _Result:
        status = VerifiedOperationStatus.VERIFIED_COMPLETE

        def to_dict(self):
            return {
                "success": True,
                "status": self.status.value,
                "receipt": {
                    "status": self.status.value,
                    "operation": "restore",
                    "archive_name": archive_name,
                },
            }

    class _Service:
        def history(self):
            return ()

        def available_backups(self):
            return (_Archive(),)

        def plan_restore(self, selected):
            assert selected == archive_name
            return _Plan()

        async def execute_restore(
            self,
            selected,
            *,
            expected_layout_sha256,
            expected_archive_sha256,
            verification_question,
            authority,
        ):
            applied.append(
                {
                    "archive_name": selected,
                    "expected_layout_sha256": expected_layout_sha256,
                    "expected_archive_sha256": expected_archive_sha256,
                    "verification_question": verification_question,
                    "authority": authority,
                }
            )
            return _Result()

    project = SimpleNamespace(
        project_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        root="/private/tmp/Alpha",
    )
    monkeypatch.setattr(
        server,
        "_strict_project_resolution",
        lambda _args: SimpleNamespace(matched=True, project=project),
    )

    def recovery_service(**scope):
        recovery_scopes.append(scope)
        return _Service()

    monkeypatch.setattr(server, "_verified_recovery_service", recovery_service)

    listed = await server._handle_recover({"action": "restore"})
    assert listed["success"] is True
    assert listed["available_backups"][0]["archive_name"] == archive_name
    assert applied == []

    preview = await server._handle_recover(
        {"action": "restore", "archive_name": archive_name}
    )
    assert preview["plan"]["archive_sha256"] == "b" * 64
    assert applied == []

    missing_hash = await server._handle_recover(
        {
            "action": "restore",
            "archive_name": archive_name,
            "apply": True,
            "confirm": True,
            "expected_layout_sha256": "a" * 64,
            "verification_question": "What was restored?",
        }
    )
    assert missing_hash["error_code"] == "RECOVERY_ARCHIVE_HASH_REQUIRED"
    assert applied == []

    result = await server._handle_recover(
        {
            "action": "restore",
            "archive_name": archive_name,
            "apply": True,
            "confirm": True,
            "expected_layout_sha256": "a" * 64,
            "expected_archive_sha256": "b" * 64,
            "verification_question": "What was restored?",
            "invocation_mode": "user_directed",
        }
    )
    assert result["recovery_status"] == "VERIFIED_COMPLETE"
    assert "What was restored?" not in json.dumps(result)
    assert recovery_scopes == [
        {
            "verification_project": project.project_id,
            "verification_workspace": project.root,
        }
    ] * 4
    assert applied == [
        {
            "archive_name": archive_name,
            "expected_layout_sha256": "a" * 64,
            "expected_archive_sha256": "b" * 64,
            "verification_question": "What was restored?",
            "authority": "user_directed",
        }
    ]


@pytest.mark.asyncio
async def test_recover_support_report_requires_exact_preview_hash(monkeypatch) -> None:
    from src.core.verified_operation import VerifiedOperationStatus

    server = ElefanteMCPServer()
    applied: list[dict[str, str]] = []

    class _Plan:
        report_sha256 = "f" * 64

        def to_dict(self):
            return {
                "schema_version": 1,
                "action": "support_report",
                "applicable": True,
                "reason_code": None,
                "reason": "Previewed allowlisted evidence only.",
                "report_sha256": self.report_sha256,
                "preview": {"schema_version": 1},
                "included": ["product and build identity"],
                "excluded": ["memory content"],
                "estimated_bytes": 1024,
                "irreversible": False,
            }

    class _Result:
        status = VerifiedOperationStatus.VERIFIED_COMPLETE

        def to_dict(self):
            return {
                "success": True,
                "status": self.status.value,
                "receipt": {
                    "status": self.status.value,
                    "operation": "support_report",
                    "archive_name": "elefante_support_20260830.zip",
                },
            }

    class _Service:
        def history(self):
            return ()

        async def plan_support_report(self):
            return _Plan()

        async def execute_support_report(self, *, expected_report_sha256, authority):
            applied.append(
                {
                    "expected_report_sha256": expected_report_sha256,
                    "authority": authority,
                }
            )
            return _Result()

    monkeypatch.setattr(server, "_verified_recovery_service", lambda: _Service())

    preview = await server._handle_recover({"action": "support_report"})
    assert preview["success"] is True
    assert preview["plan"]["report_sha256"] == "f" * 64
    assert applied == []

    missing_hash = await server._handle_recover(
        {"action": "support_report", "apply": True, "confirm": True}
    )
    assert missing_hash["error_code"] == "RECOVERY_SUPPORT_REPORT_HASH_REQUIRED"
    assert applied == []

    completed = await server._handle_recover(
        {
            "action": "support_report",
            "apply": True,
            "confirm": True,
            "expected_report_sha256": "f" * 64,
            "invocation_mode": "user_directed",
        }
    )
    assert completed["recovery_status"] == "VERIFIED_COMPLETE"
    assert applied == [
        {
            "expected_report_sha256": "f" * 64,
            "authority": "user_directed",
        }
    ]


@pytest.mark.asyncio
async def test_memory_tool_exposes_correct_as_primary_verified_repair_action() -> None:
    server = ElefanteMCPServer()
    handler = server.server.request_handlers[mcp_types.ListToolsRequest]
    result = await handler(mcp_types.ListToolsRequest(method="tools/list"))
    memory_tool = next(
        tool for tool in result.root.tools if tool.name == "elefante-Memory"
    )

    action_schema = memory_tool.inputSchema["properties"]["action"]
    correction_schema = memory_tool.inputSchema["properties"]["correction"]
    assert "correct" in action_schema["enum"]
    assert correction_schema["enum"] == [
        "edit",
        "replace",
        "resolve",
        "archive",
        "restore",
        "permanent_delete",
    ]
    assert "primary customer repair path" in memory_tool.description


@pytest.mark.asyncio
async def test_grounding_prompt_limits_recall_to_one_contextual_call() -> None:
    from mcp.types import GetPromptRequest, GetPromptRequestParams

    server = ElefanteMCPServer()
    handler = server.server.request_handlers[GetPromptRequest]
    response = await handler(
        GetPromptRequest(
            params=GetPromptRequestParams(
                name="elefante-grounding",
                arguments={},
            )
        )
    )
    guidance = response.root.messages[0].content.text

    assert "at most once" in guidance
    assert "self-contained question" in guidance
    assert "do not retry" in guidance


@pytest.mark.asyncio
async def test_recall_call_boundary_keeps_customer_payload_minimal(monkeypatch) -> None:
    server = ElefanteMCPServer()

    async def recall(_arguments):
        return {
            "success": True,
            "status": "supplied",
            "context": "# Elefante answer context\n\n- [Evidence 1] Copper-Orbit",
            "supplied_count": 1,
            "abstained": False,
            "delivery_blocked": False,
            "read_only": True,
        }

    monkeypatch.setattr(server, "_handle_recall", recall)
    handler = server.server.request_handlers[mcp_types.CallToolRequest]
    response = await handler(
        mcp_types.CallToolRequest(
            params=mcp_types.CallToolRequestParams(
                name="elefante-Recall",
                arguments={"question": "What is the launch codename?"},
            )
        )
    )
    payload = json.loads(response.root.content[0].text)

    assert set(payload) == {
        "success",
        "status",
        "context",
        "supplied_count",
        "abstained",
        "delivery_blocked",
        "read_only",
    }
    assert estimate_tokens(response.root.content[0].text) <= RECALL_MAX_RESPONSE_TOKENS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {"question": ""},
        {"question": "x" * 1001},
        {"question": 7},
    ],
)
async def test_recall_invalid_input_keeps_seven_field_terminal_contract(arguments) -> None:
    server = ElefanteMCPServer()
    handler = server.server.request_handlers[mcp_types.CallToolRequest]

    response = await handler(
        mcp_types.CallToolRequest(
            params=mcp_types.CallToolRequestParams(
                name="elefante-Recall",
                arguments=arguments,
            )
        )
    )
    rendered = response.root.content[0].text
    payload = json.loads(rendered)

    assert set(payload) == {
        "success",
        "status",
        "context",
        "supplied_count",
        "abstained",
        "delivery_blocked",
        "read_only",
    }
    assert payload["success"] is False
    assert payload["status"] == "blocked"
    assert payload["supplied_count"] == 0
    assert payload["abstained"] is True
    assert payload["delivery_blocked"] is True
    assert payload["read_only"] is True
    question = arguments.get("question")
    if isinstance(question, str) and question:
        assert question not in payload["context"]
    assert estimate_tokens(rendered) <= RECALL_MAX_RESPONSE_TOKENS


@pytest.mark.asyncio
async def test_recall_missing_question_is_rejected_by_required_mcp_schema() -> None:
    server = ElefanteMCPServer()
    handler = server.server.request_handlers[mcp_types.CallToolRequest]

    response = await handler(
        mcp_types.CallToolRequest(
            params=mcp_types.CallToolRequestParams(
                name="elefante-Recall",
                arguments={},
            )
        )
    )
    rendered = response.root.content[0].text

    assert response.root.isError is True
    assert "Input validation error" in rendered
    assert "'question' is a required property" in rendered


@pytest.mark.asyncio
async def test_recall_serializes_multilingual_context_without_ascii_expansion(
    monkeypatch,
) -> None:
    server = ElefanteMCPServer()
    multilingual_context = "記" * 900

    async def recall(_arguments):
        return {
            "success": True,
            "status": "supplied",
            "context": multilingual_context,
            "supplied_count": 1,
            "abstained": False,
            "delivery_blocked": False,
            "read_only": True,
        }

    monkeypatch.setattr(server, "_handle_recall", recall)
    handler = server.server.request_handlers[mcp_types.CallToolRequest]
    response = await handler(
        mcp_types.CallToolRequest(
            params=mcp_types.CallToolRequestParams(
                name="elefante-Recall",
                arguments={"question": "What prior multilingual decision applies?"},
            )
        )
    )
    rendered = response.root.content[0].text

    assert "記" in rendered
    assert "\\u8a18" not in rendered
    assert estimate_tokens(rendered) <= 500


@pytest.mark.asyncio
async def test_recall_no_match_does_not_echo_a_maximum_length_question(
    monkeypatch,
) -> None:
    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return []

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))
    question = "x" * 1000

    response = await server._handle_recall({"question": question})
    rendered = json.dumps(response, indent=2, ensure_ascii=False)

    assert response["status"] == "no_match"
    assert question not in response["context"]
    assert estimate_tokens(rendered) <= 128


@pytest.mark.asyncio
async def test_recall_fails_closed_when_complete_response_exceeds_hard_budget(
    monkeypatch,
) -> None:
    server = ElefanteMCPServer()

    async def oversized_context(_question):
        return SimpleNamespace(
            text="\x00" * 1578,
            selected_count=1,
            delivery_blocked=False,
        )

    monkeypatch.setattr(server, "_recall_answer_context", oversized_context)

    response = await server._handle_recall(
        {"question": "Which previously stored decision applies?"}
    )
    rendered = json.dumps(response, indent=2, ensure_ascii=False)

    assert response["status"] == "blocked"
    assert response["success"] is False
    assert response["supplied_count"] == 0
    assert response["delivery_blocked"] is True
    assert "\x00" not in response["context"]
    assert estimate_tokens(rendered) <= 1000


@pytest.mark.asyncio
async def test_recall_returns_only_bounded_governed_context_without_internal_ids(
    monkeypatch,
) -> None:
    relevant = _context_result(
        "Elefante customer installation uses one global runtime for every compatible IDE.",
        memory_type=MemoryType.DECISION,
        score=0.7,
        vector_score=0.7,
    )
    noise = _context_result(
        "Cognitive retrieval combines vector, temporal, and authority scores.",
        score=0.99,
        vector_score=0.6,
    )

    class Orchestrator:
        async def search_memories(self, **kwargs):
            assert kwargs["mode"].value == "hybrid"
            assert kwargs["limit"] == 12
            assert kwargs["include_conversation"] is False
            assert kwargs["include_stored"] is True
            assert kwargs["reinforce_access"] is False
            return [noise, relevant]

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    question = "What did we decide about global installation across IDEs?"
    response = await server._handle_recall({"question": question})

    assert response["success"] is True
    assert response["status"] == "supplied"
    assert response["supplied_count"] == 1
    assert response["read_only"] is True
    assert "one global runtime" in response["context"]
    assert question not in response["context"]
    assert "Cognitive retrieval" not in response["context"]
    assert estimate_tokens(response["context"]) <= 450
    rendered = json.dumps(response)
    assert str(relevant.memory.id) not in rendered
    assert str(noise.memory.id) not in rendered


@pytest.mark.asyncio
async def test_recall_abstains_when_no_memory_safely_answers_question(
    monkeypatch,
) -> None:
    passcode = _context_result(
        "The Elefante system test passcode is Indigo-Echo.",
        category="system-test",
        score=0.99,
        vector_score=0.99,
    )

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [passcode]

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    response = await server._handle_recall(
        {"question": "How should Elefante answer using prior project decisions?"}
    )

    assert response["success"] is True
    assert response["status"] == "no_match"
    assert response["supplied_count"] == 0
    assert response["abstained"] is True
    assert "Indigo-Echo" not in response["context"]


@pytest.mark.asyncio
async def test_legacy_implicit_context_is_default_off(monkeypatch) -> None:
    class FailIfCalled:
        async def search_memories(self, **_kwargs):
            raise AssertionError("default-off context must not search")

    server = ElefanteMCPServer()
    monkeypatch.setenv("ELEFANTE_TASK_CONTEXT_ON_TOOL_CALL", "1")
    monkeypatch.delenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", raising=False)
    monkeypatch.delenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", raising=False)
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(FailIfCalled()))

    payload = {"success": True}
    returned = await server._inject_context(
        payload,
        "elefante-TaskCreate",
        {"description": "Configure global runtime installation"},
    )

    assert returned is payload
    assert "RELEVANT_CONTEXT" not in returned


@pytest.mark.asyncio
async def test_opt_in_tool_context_uses_governed_answer_selector(monkeypatch) -> None:
    relevant = _context_result(
        "Decision: customer installation uses one global runtime for every compatible IDE.",
        memory_type=MemoryType.DECISION,
        score=0.7,
        vector_score=0.7,
    )
    noise = _context_result(
        "Cognitive retrieval uses temporal and authority scores.",
        score=0.99,
        vector_score=0.6,
    )

    class Orchestrator:
        async def search_memories(self, **kwargs):
            assert kwargs["mode"].value == "hybrid"
            assert kwargs["reinforce_access"] is False
            assert kwargs["apply_temporal_decay"] is False
            return [noise, relevant]

    server = ElefanteMCPServer()
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", "1")
    monkeypatch.setenv("ELEFANTE_TASK_CONTEXT_ON_TOOL_CALL", "1")
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    returned = await server._inject_context(
        {"success": True},
        "elefante-TaskCreate",
        {"description": "Use the global runtime installation decision across IDEs"},
    )

    context = returned["RELEVANT_CONTEXT"]
    assert context["status"] == "delivered"
    assert "one global runtime" in context["rendered_context"]
    assert "Cognitive retrieval" not in context["rendered_context"]
    assert context["selected_memory_ids"] == [str(relevant.memory.id)]


@pytest.mark.asyncio
async def test_opt_in_tool_context_surfaces_known_conflict_as_warning(monkeypatch) -> None:
    conflicting = _context_result(
        "Decision: customer installation uses one global runtime for every compatible IDE.",
        memory_type=MemoryType.DECISION,
        score=0.95,
        vector_score=0.95,
    )
    conflicting.memory.metadata.conflict_ids = [uuid4()]

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [conflicting]

    server = ElefanteMCPServer()
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", "1")
    monkeypatch.setenv("ELEFANTE_TASK_CONTEXT_ON_TOOL_CALL", "1")
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    returned = await server._inject_context(
        {"success": True},
        "elefante-TaskCreate",
        {"description": "Choose the customer installation runtime"},
    )

    context = returned["RELEVANT_CONTEXT"]
    assert context["status"] == "warning"
    assert context["selected_memory_ids"] == []
    assert context["conflict_count"] == 1
    assert "unresolved stored conflict" in context["rendered_context"]
    assert str(conflicting.memory.id) not in context["rendered_context"]


@pytest.mark.asyncio
async def test_opt_in_tool_context_never_injects_digest_stale_locked_memory(
    monkeypatch,
    tmp_path,
) -> None:
    (tmp_path / "runtime.py").write_text("CURRENT = True\n", encoding="utf-8")
    stale = _context_result(
        "Decision: use the stale global runtime contract.",
        memory_type=MemoryType.DECISION,
        score=0.99,
        vector_score=0.99,
    )
    stale.memory.metadata.file_path = "runtime.py"
    stale.memory.metadata.user_locked = True
    stale.memory.metadata.injection_policy = "always"
    stale.memory.metadata.custom_metadata = {"source_file_sha256": "0" * 64}

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [stale]

    server = ElefanteMCPServer()
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", "1")
    monkeypatch.setenv("ELEFANTE_TASK_CONTEXT_ON_TOOL_CALL", "1")
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"cwd": str(tmp_path)},
    )
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    returned = await server._inject_context(
        {"success": True},
        "elefante-TaskCreate",
        {"description": "Apply the global runtime contract"},
    )

    assert returned["RELEVANT_CONTEXT"]["status"] == "blocked"
    assert stale.memory.content not in returned["RELEVANT_CONTEXT"]["rendered_context"]


def test_compliance_receipts_are_session_bound_one_use_and_hash_queries(monkeypatch) -> None:
    server = ElefanteMCPServer()
    active = {
        "tool": "codex",
        "instance_id": "window-a",
        "session_id": "session-a",
        "cwd": "/repo",
        "transport": "streamable-http",
    }
    monkeypatch.setattr(server, "_request_provenance", lambda: dict(active))

    receipt = server._record_compliance_search("private project decision", 2)
    stored = server._compliance_receipts[("codex", "window-a", "session-a")]

    assert stored["receipt_id"] == receipt
    assert stored["query_sha256"] != "private project decision"
    assert "private project decision" not in json.dumps(stored)

    active.update(tool="claude-code", instance_id="window-b", session_id="session-b")
    assert server._check_compliance_gate("elefante-MemoryAdd") is not None

    active.update(tool="codex", instance_id="window-a", session_id="session-a")
    assert server._check_compliance_gate("elefante-MemoryAdd") is None
    assert server._check_compliance_gate("elefante-MemoryAdd") is not None


def test_stdio_bridge_accepts_only_loopback_and_emits_client_identity(monkeypatch):
    from src.mcp import stdio_bridge

    monkeypatch.setenv("ELEFANTE_DAEMON_URL", "http://127.0.0.1:8765/mcp/")
    monkeypatch.setenv("ELEFANTE_CLIENT_TOOL", "codex")
    monkeypatch.setenv("ELEFANTE_CLIENT_CWD", "/workspace/product")
    assert stdio_bridge.daemon_url() == "http://127.0.0.1:8765/mcp/"

    headers = stdio_bridge.provenance_headers()
    assert headers["X-Elefante-Client-Tool"] == "codex"
    assert headers["X-Elefante-Client-Instance-ID"] == stdio_bridge.BRIDGE_INSTANCE_ID
    assert headers["X-Elefante-Client-CWD"] == "/workspace/product"

    for unsafe_url in (
        "http://localhost:8765/mcp/",
        "https://memory.example.test/mcp",
        "http://127.0.0.1:8765/not-mcp",
        "http://127.0.0.1:70000/mcp",
    ):
        monkeypatch.setenv("ELEFANTE_DAEMON_URL", unsafe_url)
        with pytest.raises(RuntimeError, match="requires"):
            stdio_bridge.daemon_url()


def test_stdio_bridge_rejects_oversized_or_non_object_messages_before_forwarding():
    from src.mcp import stdio_bridge

    assert stdio_bridge.parse_request_line('{"jsonrpc":"2.0","id":1,"method":"ping"}') == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "ping",
    }
    with pytest.raises(ValueError, match="bridge limit"):
        stdio_bridge.parse_request_line("x" * (stdio_bridge.MAX_BRIDGE_MESSAGE_BYTES + 1))
    with pytest.raises(ValueError, match="JSON object"):
        stdio_bridge.parse_request_line("[]")


def test_stdio_bridge_does_not_reuse_an_id_after_a_later_parse_failure(monkeypatch):
    from src.mcp import stdio_bridge

    class FakeResponse:
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {"jsonrpc": "2.0", "id": 7, "result": {"ok": True}}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setenv("ELEFANTE_DAEMON_URL", "http://127.0.0.1:8765/mcp/")
    monkeypatch.setattr(stdio_bridge.httpx, "Client", lambda **_: FakeClient())
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"id":7,"method":"ping"}\nnot json\n'))
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)

    stdio_bridge.main()

    assert [json.loads(line) for line in stdout.getvalue().splitlines()] == [
        {"jsonrpc": "2.0", "id": 7, "result": {"ok": True}}
    ]


def test_stdio_bridge_reinitializes_once_after_daemon_session_loss(monkeypatch):
    from src.mcp import stdio_bridge

    class FakeResponse:
        def __init__(self, status_code, payload=None, headers=None):
            self.status_code = status_code
            self._payload = payload
            self.headers = headers or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                request = httpx.Request("POST", "http://127.0.0.1:8765/mcp/")
                response = httpx.Response(self.status_code, request=request)
                raise httpx.HTTPStatusError(
                    f"status {self.status_code}",
                    request=request,
                    response=response,
                )

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self):
            self.calls = []
            self.responses = iter(
                [
                    FakeResponse(
                        200,
                        {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "elefante"}}},
                        {"mcp-session-id": "old-session"},
                    ),
                    FakeResponse(202),
                    FakeResponse(404),
                    FakeResponse(
                        200,
                        {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "elefante"}}},
                        {"mcp-session-id": "new-session"},
                    ),
                    FakeResponse(202),
                    FakeResponse(
                        200,
                        {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}},
                        {"mcp-session-id": "new-session"},
                    ),
                ]
            )

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, *, json, headers):
            self.calls.append({"url": url, "request": json, "headers": dict(headers)})
            return next(self.responses)

    client = FakeClient()
    monkeypatch.setenv("ELEFANTE_DAEMON_URL", "http://127.0.0.1:8765/mcp/")
    monkeypatch.setattr(stdio_bridge.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            "\n".join(
                [
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-06-18",
                                "capabilities": {},
                                "clientInfo": {"name": "Codex", "version": "1"},
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {},
                        }
                    ),
                    json.dumps(
                        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
                    ),
                    "",
                ]
            )
        ),
    )
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)

    stdio_bridge.main()

    assert [json.loads(line) for line in stdout.getvalue().splitlines()] == [
        {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "elefante"}}},
        {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}},
    ]
    assert [call["request"]["method"] for call in client.calls] == [
        "initialize",
        "notifications/initialized",
        "tools/list",
        "initialize",
        "notifications/initialized",
        "tools/list",
    ]
    assert client.calls[2]["headers"]["mcp-session-id"] == "old-session"
    assert "mcp-session-id" not in client.calls[3]["headers"]
    assert client.calls[4]["headers"]["mcp-session-id"] == "new-session"
    assert client.calls[5]["headers"]["mcp-session-id"] == "new-session"


def test_stdio_bridge_recovers_when_initialized_notification_finds_stale_session(
    monkeypatch,
):
    from src.mcp import stdio_bridge

    class FakeResponse:
        def __init__(self, status_code, payload=None, headers=None):
            self.status_code = status_code
            self._payload = payload
            self.headers = headers or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"daemon status {self.status_code}")

        def json(self):
            return self._payload

    responses = iter(
        [
            FakeResponse(
                200,
                {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "elefante"}}},
                {"mcp-session-id": "old-session"},
            ),
            FakeResponse(202),
            FakeResponse(404),
            FakeResponse(
                200,
                {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "elefante"}}},
                {"mcp-session-id": "new-session"},
            ),
            FakeResponse(202),
            FakeResponse(
                200,
                {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}},
                {"mcp-session-id": "new-session"},
            ),
        ]
    )
    calls = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_post_request(_client, _url, request, session_id=None):
        calls.append((request["method"], session_id))
        return next(responses)

    monkeypatch.setenv("ELEFANTE_DAEMON_URL", "http://127.0.0.1:8765/mcp/")
    monkeypatch.setattr(stdio_bridge.httpx, "Client", lambda **_: FakeClient())
    monkeypatch.setattr(stdio_bridge, "post_request", fake_post_request)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            "\n".join(
                [
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-06-18",
                                "capabilities": {},
                                "clientInfo": {"name": "Codex", "version": "1"},
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {},
                        }
                    ),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {},
                        }
                    ),
                    json.dumps(
                        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
                    ),
                    "",
                ]
            )
        ),
    )
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)

    stdio_bridge.main()

    assert calls == [
        ("initialize", None),
        ("notifications/initialized", "old-session"),
        ("notifications/initialized", "old-session"),
        ("initialize", None),
        ("notifications/initialized", "new-session"),
        ("tools/list", "new-session"),
    ]
    assert [json.loads(line) for line in stdout.getvalue().splitlines()] == [
        {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "elefante"}}},
        {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}},
    ]


def test_stdio_bridge_does_not_recover_an_unrelated_http_failure(monkeypatch):
    from src.mcp import stdio_bridge

    class FakeResponse:
        def __init__(self, status_code, payload=None, headers=None):
            self.status_code = status_code
            self._payload = payload
            self.headers = headers or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"daemon status {self.status_code}")

        def json(self):
            return self._payload

    responses = iter(
        [
            FakeResponse(
                200,
                {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "elefante"}}},
                {"mcp-session-id": "active-session"},
            ),
            FakeResponse(202),
            FakeResponse(500),
        ]
    )
    calls = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_post_request(_client, _url, request, session_id=None):
        calls.append((request["method"], session_id))
        return next(responses)

    monkeypatch.setenv("ELEFANTE_DAEMON_URL", "http://127.0.0.1:8765/mcp/")
    monkeypatch.setattr(stdio_bridge.httpx, "Client", lambda **_: FakeClient())
    monkeypatch.setattr(stdio_bridge, "post_request", fake_post_request)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            "\n".join(
                [
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-06-18",
                                "capabilities": {},
                                "clientInfo": {"name": "Codex", "version": "1"},
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {},
                        }
                    ),
                    json.dumps(
                        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
                    ),
                    "",
                ]
            )
        ),
    )
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)

    stdio_bridge.main()

    assert calls == [
        ("initialize", None),
        ("notifications/initialized", "active-session"),
        ("tools/list", "active-session"),
    ]
    output = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert output[0]["result"]["serverInfo"]["name"] == "elefante"
    assert output[1]["id"] == 2
    assert output[1]["error"]["message"] == "daemon status 500"


def test_daemon_rejects_non_loopback_bind(monkeypatch):
    from src.mcp import daemon

    monkeypatch.setenv("ELEFANTE_DAEMON_HOST", "0.0.0.0")
    with pytest.raises(RuntimeError, match="127.0.0.1"):
        daemon.main()


@pytest.mark.asyncio
async def test_daemon_request_boundary_replays_valid_bodies_and_rejects_oversized_ones():
    """Direct HTTP clients must not bypass the bridge's input-size boundary."""
    from src.mcp.daemon import BoundedRequestBody

    received_bodies: list[bytes] = []

    async def inner_app(_scope, receive, send):
        received_bodies.append((await receive())["body"])
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def invoke(messages, headers=()):
        sent = []
        pending = iter(messages)

        async def receive():
            return next(pending, {"type": "http.disconnect"})

        async def send(message):
            sent.append(message)

        await BoundedRequestBody(inner_app, max_bytes=4)(
            {"type": "http", "method": "POST", "headers": list(headers)}, receive, send
        )
        return sent

    valid = await invoke([{"type": "http.request", "body": b"ping", "more_body": False}])
    assert received_bodies == [b"ping"]
    assert valid[0]["status"] == 204

    declared = await invoke(
        [{"type": "http.request", "body": b"", "more_body": False}],
        [(b"content-length", b"5")],
    )
    chunked = await invoke(
        [
            {"type": "http.request", "body": b"pin", "more_body": True},
            {"type": "http.request", "body": b"gg", "more_body": False},
        ]
    )
    assert received_bodies == [b"ping"]
    assert declared[0]["status"] == 413
    assert chunked[0]["status"] == 413


@pytest.mark.parametrize("port", ("0", "65536", "invalid"))
def test_daemon_rejects_invalid_local_port(monkeypatch, port):
    from src.mcp import daemon

    monkeypatch.setenv("ELEFANTE_DAEMON_PORT", port)
    with pytest.raises(RuntimeError, match="1 to 65535"):
        daemon.daemon_port()


def test_configuration_creates_a_clean_home_directory(monkeypatch, tmp_path):
    """A first-run home may not exist yet in containers or fresh accounts."""
    from src.utils.config import Config

    clean_home = tmp_path / "new-user-home"
    monkeypatch.setenv("HOME", str(clean_home))
    monkeypatch.setenv("ELEFANTE_DATA_DIR", str(clean_home / ".elefante" / "data"))
    config = Config()
    config._config = None
    config.load()

    assert (clean_home / ".elefante" / "data" / "vector").is_dir()


def test_server_uses_transport_owned_http_provenance(monkeypatch):
    server = ElefanteMCPServer()
    request = SimpleNamespace(
        headers={
            "mcp-session-id": "session-a",
            "x-elefante-client-tool": "claude-code",
            "x-elefante-client-instance-id": "window-a",
            "x-elefante-client-cwd": "/repo/elefante",
        }
    )
    # The SDK exposes request_context as a property. Patch the class-level
    # property for this unit boundary rather than manufacturing an HTTP stack.
    monkeypatch.setattr(
        type(server.server),
        "request_context",
        property(lambda _: SimpleNamespace(request=request, session=SimpleNamespace(client_params=None))),
    )

    args = server._with_request_provenance({"action": "add", "content": "remember"})
    assert args["metadata"]["elefante_source"] == {
        "tool": "claude-code",
        "instance_id": "window-a",
        "session_id": "session-a",
        "cwd": "/repo/elefante",
        "transport": "streamable-http",
    }


def test_server_rejects_control_characters_and_bounds_http_provenance(monkeypatch):
    """Untrusted bridge headers must remain safe to persist and render."""
    server = ElefanteMCPServer()
    request = SimpleNamespace(
        headers={
            "mcp-session-id": "session\nspoofed",
            "x-elefante-client-tool": "tool-" + ("a" * 200),
            "x-elefante-client-instance-id": "window\tspoofed",
            "x-elefante-client-cwd": "/repo/" + ("nested/" * 300),
        }
    )
    monkeypatch.setattr(
        type(server.server),
        "request_context",
        property(lambda _: SimpleNamespace(request=request, session=SimpleNamespace(client_params=None))),
    )

    source = server._with_request_provenance({"action": "add", "content": "remember"})[
        "metadata"
    ]["elefante_source"]

    assert source["tool"] == "tool-" + ("a" * 123)
    assert source["instance_id"] == "unknown-http-instance"
    assert source["session_id"] == "initializing"
    assert source["cwd"] == ("/repo/" + ("nested/" * 300))[:1024]


def test_server_rejects_control_characters_in_stdio_provenance(monkeypatch):
    monkeypatch.setenv("ELEFANTE_CLIENT_TOOL", "codex\r\nspoofed")
    monkeypatch.setenv("ELEFANTE_CLIENT_INSTANCE_ID", "window\tspoofed")
    monkeypatch.setenv("ELEFANTE_CLIENT_CWD", "/repo\tspoofed")

    source = ElefanteMCPServer()._request_provenance()

    assert source == {
        "tool": "unknown-stdio",
        "instance_id": source["instance_id"],
        "session_id": "stdio",
        "cwd": "",
        "transport": "stdio",
    }
    assert len(source["instance_id"]) == 32


def test_entrypoint_protocol_routes_to_the_current_issue_tracker():
    result = ElefanteMCPServer._inject_entrypoint_protocol(object(), {})
    pitfalls = ElefanteMCPServer._inject_pitfalls(object(), {}, "elefante-Memory")

    assert all("docs/debug" not in step for step in result["ENTRYPOINT_SEQUENCE_READ_THIS_FIRST"])
    assert any("workspace/ISSUES.md" in step for step in result["ENTRYPOINT_SEQUENCE_READ_THIS_FIRST"])
    assert any("workspace/ISSUES.md" in item for item in pitfalls["MANDATORY_PROTOCOLS_READ_THIS_FIRST"])


def test_client_protocol_excludes_developer_workspace_routing(monkeypatch):
    from src.mcp import server as server_module

    monkeypatch.setattr(server_module, "is_client_runtime", lambda: True)
    result = ElefanteMCPServer._inject_entrypoint_protocol(object(), {})
    pitfalls = ElefanteMCPServer._inject_pitfalls(object(), {}, "elefante-Memory")
    rendered = json.dumps({"result": result, "pitfalls": pitfalls})
    entrypoint = "\n".join(result["ENTRYPOINT_SEQUENCE_READ_THIS_FIRST"])

    assert "workspace/" not in rendered
    assert "tests/" not in rendered
    assert "API keys" in rendered
    assert "explicitly asks Elefante to remember" in rendered
    assert 'invocation_mode="user_directed"' in entrypoint
    assert "never use descriptive prose" in rendered
    assert "Stored is not proof of deliverable" in rendered
    assert "ordinary conversation" in rendered


@pytest.mark.asyncio
async def test_memory_write_lock_encloses_the_actual_store_operation(monkeypatch):
    from src.mcp import server as server_module

    events: list[str] = []

    @contextmanager
    def recording_lock():
        events.append("entered")
        yield SimpleNamespace(acquired=True)
        events.append("exited")

    class FakeOrchestrator:
        _last_rejection_reason = None

        async def add_memory(self, **_: object) -> Memory:
            assert events == ["entered"]
            return Memory(content="remembered", metadata=MemoryMetadata(memory_type=MemoryType.NOTE))

    monkeypatch.setattr(server_module, "write_lock", recording_lock)
    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(FakeOrchestrator()))
    monkeypatch.setattr(server, "_with_request_provenance", lambda args: {**args, "metadata": {}})

    result = await server._handle_add_memory({"content": "remembered", "memory_type": "note"})
    assert result["status"] == "stored"
    assert events == ["entered", "exited"]


@pytest.mark.asyncio
async def test_graph_connect_scrubs_properties_and_holds_lock_through_writes(monkeypatch):
    from src.mcp import server as server_module

    events: list[str] = []
    captured: dict[str, object] = {}
    secret = "sk-" + ("g" * 32)

    @contextmanager
    def recording_lock():
        events.append("entered")
        yield SimpleNamespace(acquired=True)
        events.append("exited")

    class FakeOrchestrator:
        async def create_entity(self, **kwargs):
            assert events == ["entered"]
            captured["entity"] = kwargs
            return SimpleNamespace(
                id=uuid4(),
                name=kwargs["name"],
                type=SimpleNamespace(value=kwargs["entity_type"]),
            )

        async def create_relationship(self, **kwargs):
            assert events == ["entered"]
            captured["relationship"] = kwargs
            return SimpleNamespace(
                from_entity_id=kwargs["from_entity_id"],
                to_entity_id=kwargs["to_entity_id"],
                relationship_type=SimpleNamespace(value=kwargs["relationship_type"]),
                properties=kwargs["properties"],
            )

    monkeypatch.setattr(server_module, "write_lock", recording_lock)
    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(FakeOrchestrator()),
    )

    result = await server._handle_set_elefante_connection(
        {
            "entities": [
                {
                    "ref": "project",
                    "name": "Elefante",
                    "type": "project",
                    "properties": {"credential": secret},
                },
                {
                    "ref": "decision",
                    "name": "Local memory",
                    "type": "decision",
                },
            ],
            "relationships": [
                {
                    "from_ref": "decision",
                    "to_ref": "project",
                    "relationship_type": "RELATES_TO",
                    "properties": {"token": f"Bearer {secret}"},
                }
            ],
        }
    )

    assert events == ["entered", "exited"]
    assert secret not in json.dumps(captured, default=str)
    assert secret not in json.dumps(result, default=str)
    assert result["privacy_redactions"] == 2


@pytest.mark.asyncio
async def test_etl_process_scrubs_legacy_secrets_from_agent_response(monkeypatch):
    from src.core import etl as etl_module
    from src.mcp import server as server_module

    events: list[str] = []
    secret = "sk-" + ("p" * 32)

    @contextmanager
    def recording_lock():
        events.append("entered")
        yield SimpleNamespace(acquired=True)
        events.append("exited")

    class FakeETL:
        vector_store = None

        async def get_raw_memories(self, limit):
            assert events == ["entered"]
            assert limit == 1
            return [{"id": str(uuid4()), "content": f"Legacy secret {secret}"}]

    monkeypatch.setattr(server_module, "write_lock", recording_lock)
    server = ElefanteMCPServer()
    monkeypatch.setattr(etl_module, "get_etl_processor", lambda: FakeETL())
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=object())),
    )

    result = await server._handle_etl_process({"limit": 1})

    assert events == ["entered", "exited"]
    assert secret not in json.dumps(result)
    assert result["privacy_redactions"] == 1


@pytest.mark.asyncio
async def test_etl_classify_scrubs_enrichment_before_persistence(monkeypatch):
    from src.core import etl as etl_module
    from src.mcp import server as server_module

    captured: dict[str, object] = {}
    secret = "sk-" + ("c" * 32)

    @contextmanager
    def recording_lock():
        yield SimpleNamespace(acquired=True)

    class FakeETL:
        vector_store = None

        async def apply_classification(self, **kwargs):
            captured.update(kwargs)
            return {"success": True, **kwargs}

    monkeypatch.setattr(server_module, "write_lock", recording_lock)
    monkeypatch.setattr(etl_module, "get_etl_processor", lambda: FakeETL())
    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=object())),
    )

    result = await server._handle_etl_classify(
        {
            "memory_id": str(uuid4()),
            "summary": f"Do not persist {secret}",
            "concepts": ["privacy", secret],
            "surfaces_when": [f"Bearer {secret}"],
        }
    )

    assert secret not in json.dumps(captured)
    assert secret not in json.dumps(result)
    assert result["privacy_redactions"] == 3


@pytest.mark.asyncio
async def test_memory_add_forwards_governance_fields(monkeypatch):
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        _last_rejection_reason = None

        async def add_memory(self, **kwargs: object) -> Memory:
            captured.update(kwargs)
            return Memory(content="protected", metadata=MemoryMetadata())

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(FakeOrchestrator()))
    monkeypatch.setattr(server, "_with_request_provenance", lambda args: args)

    result = await server._handle_add_memory(
        {
            "content": "protected",
            "memory_type": "fact",
            "retention_policy": "permanent",
            "injection_policy": "always",
            "scope": "global",
            "trigger": ["protected"],
            "user_locked": True,
            "invocation_mode": "user_directed",
        }
    )

    assert result["status"] == "stored"
    metadata = captured["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["retention_policy"] == "permanent"
    assert metadata["injection_policy"] == "always"
    assert metadata["scope"] == "global"
    assert metadata["trigger"] == ["protected"]
    assert metadata["user_locked"] is True
    assert metadata["invocation_mode"] == "user_directed"


@pytest.mark.asyncio
async def test_memory_add_persists_portable_attachment_descriptors(
    monkeypatch, tmp_path
):
    captured: dict[str, object] = {}
    source = tmp_path / "diagram.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nlocal-image-bytes")
    data_dir = tmp_path / "elefante-data"

    class FakeOrchestrator:
        _last_rejection_reason = None

        async def add_memory(self, **kwargs: object) -> Memory:
            captured.update(kwargs)
            return Memory(content="diagram", metadata=MemoryMetadata())

    monkeypatch.setattr("src.utils.config.DATA_DIR", data_dir)
    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(
        server, "_get_orchestrator", lambda: _async_value(FakeOrchestrator())
    )
    monkeypatch.setattr(server, "_with_request_provenance", lambda args: args)

    result = await server._handle_add_memory(
        {
            "content": "Architecture diagram",
            "memory_type": "fact",
            "invocation_mode": "user_directed",
            "attachments": [
                {
                    "path": str(source),
                    "description": "Diagram of the local daemon boundary.",
                }
            ],
        }
    )

    assert result["status"] == "stored"
    assert result["attachment_count"] == 1
    metadata = captured["metadata"]
    assert isinstance(metadata, dict)
    descriptor = metadata["attachments"][0]
    assert descriptor == result["attachments"][0]
    assert descriptor["storage_path"].startswith("attachments/")
    assert not Path(descriptor["storage_path"]).is_absolute()
    assert str(source) not in json.dumps(descriptor)
    stored = data_dir / descriptor["storage_path"]
    assert stored.read_bytes() == source.read_bytes()
    assert stored.stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
async def test_workflow_cannot_claim_user_memory_authority(monkeypatch):
    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: (_ for _ in ()).throw(AssertionError("blocked before storage")),
    )

    result = await server._handle_add_memory(
        {
            "content": "automation cannot lock this",
            "memory_type": "fact",
            "user_locked": True,
        }
    )

    assert result["success"] is False
    assert result["authority_status"] == "BLOCKED"
    assert "cannot assert user_locked" in result["error"]


@pytest.mark.asyncio
async def test_memory_add_scrubs_secrets_before_storage(monkeypatch):
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        _last_rejection_reason = None

        async def add_memory(self, **kwargs):
            captured.update(kwargs)
            return Memory(content=str(kwargs["content"]), metadata=MemoryMetadata())

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(FakeOrchestrator()))

    secret = "sk-" + ("a" * 32)
    result = await server._handle_add_memory(
        {
            "content": f"Never persist this key {secret}",
            "memory_type": "fact",
            "metadata": {"private_note": f"duplicate {secret}"},
        }
    )

    assert secret not in str(captured["content"])
    assert secret not in json.dumps(captured["metadata"])
    assert "[REDACTED:OPENAI_KEY]" in str(captured["content"])
    assert result["privacy_redactions"] == 2


@pytest.mark.asyncio
async def test_legacy_content_update_routes_to_verified_correct_before_storage(
    monkeypatch,
):
    memory = Memory(content="existing decision", metadata=MemoryMetadata())

    class VectorStore:
        async def get_memory(self, _memory_id):
            raise AssertionError("legacy content update must not open memory storage")

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_strict_project_resolution", lambda _args: None)
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=VectorStore())),
    )

    result = await server._handle_update_memory(
        {
            "memory_id": str(memory.id),
            "content": "Correct this decision through the verified path.",
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "USE_VERIFIED_CORRECT"
    assert result["memory_read"] is False
    assert result["memory_written"] is False


@pytest.mark.asyncio
async def test_memory_governance_update_scrubs_secrets_before_storage(monkeypatch):
    memory = Memory(content="existing decision", metadata=MemoryMetadata())
    captured: dict[str, object] = {}

    class VectorStore:
        async def get_memory(self, _memory_id):
            return memory

        async def update_memory(self, _memory_id, values):
            captured.update(values)
            return True

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_strict_project_resolution", lambda _args: None)
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=VectorStore())),
    )

    secret = "sk-" + ("a" * 32)
    result = await server._handle_update_memory(
        {
            "memory_id": str(memory.id),
            "tags": [f"Never persist this key {secret}"],
        }
    )

    assert secret not in str(captured["tags"])
    assert "[REDACTED:OPENAI_KEY]" in str(captured["tags"])
    assert result["privacy_redactions"] == 1


@pytest.mark.asyncio
async def test_correct_plan_is_read_only_and_returns_exact_product_plan(monkeypatch):
    memory = Memory(
        content="Scoped decision",
        metadata=MemoryMetadata(
            project="project-id",
            workspace="/tmp/project",
            scope="project:project-id",
        ),
    )

    class VectorStore:
        async def get_memory(self, _memory_id):
            return memory

    class CorrectionService:
        async def plan(self, memory_id, **kwargs):
            assert memory_id == memory.id
            assert kwargs["action"].value == "archive"
            return SimpleNamespace(
                applicable=True,
                to_dict=lambda: {
                    "action": "archive",
                    "record_sha256": {"target": "a" * 64},
                    "graph_sha256": {"target": "b" * 64},
                },
            )

        async def execute(self, *_args, **_kwargs):
            raise AssertionError("planning must not write")

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_strict_project_resolution", lambda _args: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=VectorStore())),
    )
    monkeypatch.setattr(
        server,
        "_verified_correction_service",
        lambda _orchestrator: CorrectionService(),
    )

    result = await server._handle_correct_memory(
        {"memory_id": str(memory.id), "correction": "archive"}
    )

    assert result["success"] is True
    assert result["applied"] is False
    assert result["correction_status"] == "READY"
    assert result["plan"]["record_sha256"]["target"] == "a" * 64


@pytest.mark.asyncio
async def test_correct_apply_requires_inspected_hashes_before_opening_stores(
    monkeypatch,
):
    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_strict_project_resolution", lambda _args: None)

    async def forbidden_orchestrator():
        raise AssertionError("validation must finish before opening durable stores")

    monkeypatch.setattr(server, "_get_orchestrator", forbidden_orchestrator)
    result = await server._handle_correct_memory(
        {
            "memory_id": str(uuid4()),
            "correction": "archive",
            "apply": True,
            "reason": "No longer current.",
            "verification_question": "What decision is current?",
            "invocation_mode": "user_directed",
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "CORRECTION_PLAN_REQUIRED"


@pytest.mark.asyncio
async def test_correct_apply_uses_gate_lock_and_verified_service(monkeypatch):
    memory = Memory(
        content="Scoped decision",
        metadata=MemoryMetadata(
            project="project-id",
            workspace="/tmp/project",
            scope="project:project-id",
        ),
    )
    captured: dict[str, object] = {}

    class VectorStore:
        async def get_memory(self, _memory_id):
            return memory

    class CorrectionService:
        async def execute(self, memory_id, **kwargs):
            captured["memory_id"] = memory_id
            captured.update(kwargs)
            return SimpleNamespace(
                status=SimpleNamespace(value="VERIFIED_COMPLETE"),
                to_dict=lambda: {
                    "success": True,
                    "status": "VERIFIED_COMPLETE",
                    "receipt": {"status": "VERIFIED_COMPLETE"},
                },
            )

    class AcquiredWrite:
        async def __aenter__(self):
            captured["locked"] = True
            return SimpleNamespace(acquired=True)

        async def __aexit__(self, *_args):
            return False

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_strict_project_resolution", lambda _args: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=VectorStore())),
    )
    monkeypatch.setattr(
        server,
        "_verified_correction_service",
        lambda _orchestrator: CorrectionService(),
    )
    monkeypatch.setattr(server, "_write_operation", lambda: AcquiredWrite())
    monkeypatch.setattr(
        server,
        "_check_compliance_gate",
        lambda tool: captured.setdefault("gate", tool) and None,
    )

    result = await server._handle_correct_memory(
        {
            "memory_id": str(memory.id),
            "correction": "archive",
            "apply": True,
            "reason": "No longer current.",
            "verification_question": "What decision is current?",
            "expected_record_sha256": {"target": "a" * 64},
            "expected_graph_sha256": {"target": "b" * 64},
            "invocation_mode": "user_directed",
        }
    )

    assert result["success"] is True
    assert result["correction_status"] == "VERIFIED_COMPLETE"
    assert captured["gate"] == "elefante-MemoryCorrect"
    assert captured["locked"] is True
    assert captured["memory_id"] == memory.id
    assert captured["expected_record_sha256"] == {"target": "a" * 64}


@pytest.mark.asyncio
async def test_permanent_correct_requires_final_confirmation_before_storage(monkeypatch):
    server = ElefanteMCPServer()

    async def forbidden_orchestrator():
        raise AssertionError("missing final confirmation must not open storage")

    monkeypatch.setattr(server, "_get_orchestrator", forbidden_orchestrator)

    result = await server._handle_correct_memory(
        {
            "memory_id": str(uuid4()),
            "correction": "permanent_delete",
            "apply": True,
            "reason": "User requested erasure.",
            "verification_question": "What should no longer be recalled?",
            "expected_record_sha256": {"target": "a" * 64},
            "expected_graph_sha256": {
                "target": "b" * 64,
                "target_relationships": "c" * 64,
            },
            "invocation_mode": "user_directed",
        }
    )

    assert result["error_code"] == "PERMANENT_CONFIRMATION_REQUIRED"
    assert result["correction_status"] == "NEEDS_HUMAN"


@pytest.mark.asyncio
async def test_permanent_correct_runs_backup_bound_service_under_write_lock(monkeypatch):
    from src.core.verified_operation import VerifiedOperationStatus

    memory = Memory(
        content="Scoped decision",
        metadata=MemoryMetadata(
            project="project-id",
            workspace="/tmp/project",
            scope="project:project-id",
        ),
    )
    captured: dict[str, object] = {}

    class VectorStore:
        async def get_memory(self, _memory_id):
            return memory

    class CorrectionService:
        async def plan(self, *_args, **_kwargs):
            raise AssertionError("apply uses the inspected hashes")

    class Result:
        status = VerifiedOperationStatus.VERIFIED_COMPLETE

        @staticmethod
        def to_dict():
            return {
                "success": True,
                "status": "VERIFIED_COMPLETE",
                "receipt": {
                    "operation": "permanent_delete",
                    "status": "VERIFIED_COMPLETE",
                    "recoverable": False,
                },
            }

    async def apply_permanent(**kwargs):
        captured.update(kwargs)
        return Result()

    class AcquiredWrite:
        async def __aenter__(self):
            captured["locked"] = True
            return SimpleNamespace(acquired=True)

        async def __aexit__(self, *_args):
            return False

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_strict_project_resolution", lambda _args: None)
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _tool: None)
    monkeypatch.setattr(server, "_authority_violation", lambda *_a, **_k: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=VectorStore())),
    )
    monkeypatch.setattr(
        server,
        "_verified_correction_service",
        lambda _orchestrator: CorrectionService(),
    )
    monkeypatch.setattr(server, "_write_operation", lambda: AcquiredWrite())
    monkeypatch.setattr(
        server,
        "_apply_permanent_delete_with_held_lock",
        apply_permanent,
    )

    result = await server._handle_correct_memory(
        {
            "memory_id": str(memory.id),
            "correction": "permanent_delete",
            "apply": True,
            "reason": "User requested erasure.",
            "verification_question": "What should no longer be recalled?",
            "confirm_permanent": True,
            "expected_record_sha256": {"target": "a" * 64},
            "expected_graph_sha256": {
                "target": "b" * 64,
                "target_relationships": "c" * 64,
            },
            "invocation_mode": "user_directed",
        }
    )

    assert result["correction_status"] == "VERIFIED_COMPLETE"
    assert captured["memory_id"] == memory.id
    assert captured["existing"] is memory
    assert captured["locked"] is True
    assert captured["expected_graph_sha256"] == {
        "target": "b" * 64,
        "target_relationships": "c" * 64,
    }


@pytest.mark.asyncio
async def test_correct_rejects_memory_outside_active_strict_project(monkeypatch):
    memory = Memory(
        content="Other project decision",
        metadata=MemoryMetadata(
            project="other-project",
            workspace="/tmp/other",
            scope="project:other-project",
        ),
    )
    project = SimpleNamespace(
        project_id="active-project",
        root="/tmp/active",
        scope="project:active-project",
    )

    class VectorStore:
        async def get_memory(self, _memory_id):
            return memory

    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_strict_project_resolution",
        lambda _args: SimpleNamespace(matched=True, project=project),
    )
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=VectorStore())),
    )
    monkeypatch.setattr(
        server,
        "_verified_correction_service",
        lambda _orchestrator: (_ for _ in ()).throw(
            AssertionError("mismatched scope must not reach correction service")
        ),
    )

    result = await server._handle_correct_memory(
        {"memory_id": str(memory.id), "correction": "archive"}
    )

    assert result["success"] is False
    assert result["error_code"] == "PROJECT_SCOPE_MISMATCH"
    assert result["memory_written"] is False


@pytest.mark.asyncio
async def test_memory_search_scrubs_legacy_secrets_from_complete_response(monkeypatch):
    secret = "sk-" + ("a" * 32)
    memory = Memory(
        content=f"Legacy content {secret}",
        metadata=MemoryMetadata(source_detail=f"api_key={secret.removeprefix('sk-')}"),
    )
    result = SearchResult(
        memory=memory,
        score=0.9,
        vector_score=0.9,
        source="vector",
    )

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [result]

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    response = await server._handle_search_memories(
        {"query": "legacy content", "include_conversation": False}
    )

    assert secret not in json.dumps(response)
    assert response["privacy_redactions"] == 2
    assert response["answer_context"]["selected_count"] == 0


@pytest.mark.asyncio
async def test_memory_search_answer_context_blocks_digest_stale_locked_memory(
    monkeypatch,
    tmp_path,
) -> None:
    (tmp_path / "runtime.py").write_text("CURRENT = True\n", encoding="utf-8")
    stale = _context_result(
        "Decision: use the stale global runtime contract.",
        memory_type=MemoryType.DECISION,
        score=0.99,
        vector_score=0.99,
    )
    stale.memory.metadata.file_path = "runtime.py"
    stale.memory.metadata.user_locked = True
    stale.memory.metadata.injection_policy = "always"
    stale.memory.metadata.custom_metadata = {"source_file_sha256": "0" * 64}

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [stale]

    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {
            "tool": "pytest",
            "instance_id": "instance",
            "session_id": "session",
            "transport": "stdio",
            "cwd": str(tmp_path),
        },
    )
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    response = await server._handle_search_memories(
        {"query": "What global runtime contract applies?", "include_conversation": False}
    )

    assert response["count"] == 1  # Broad search remains available for inspection.
    assert response["answer_context"]["delivery_blocked"] is True
    assert response["answer_context"]["selected_count"] == 0
    assert response["answer_context"]["blocked_reason"] == "mandatory-governance-conflict"


@pytest.mark.asyncio
async def test_prompt_and_recall_block_digest_stale_locked_memory(
    monkeypatch,
    tmp_path,
) -> None:
    from mcp.types import GetPromptRequest, GetPromptRequestParams

    (tmp_path / "runtime.py").write_text("CURRENT = True\n", encoding="utf-8")
    stale = _context_result(
        "Decision: use the stale global runtime contract.",
        memory_type=MemoryType.DECISION,
        score=0.99,
        vector_score=0.99,
    )
    stale.memory.metadata.file_path = "runtime.py"
    stale.memory.metadata.user_locked = True
    stale.memory.metadata.injection_policy = "always"
    stale.memory.metadata.custom_metadata = {"source_file_sha256": "0" * 64}

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [stale]

    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"cwd": str(tmp_path)},
    )
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))
    handler = server.server.request_handlers[GetPromptRequest]

    response = await handler(
        GetPromptRequest(
            params=GetPromptRequestParams(
                name="elefante-context",
                arguments={"topic": "What global runtime contract applies?"},
            )
        )
    )
    rendered = response.root.messages[0].content.text

    assert "BLOCKED" in rendered
    assert stale.memory.content not in rendered

    recall = await server._handle_recall(
        {"question": "What global runtime contract applies?"}
    )
    assert recall["success"] is False
    assert recall["status"] == "blocked"
    assert recall["delivery_blocked"] is True
    assert stale.memory.content not in recall["context"]


@pytest.mark.asyncio
async def test_context_get_scrubs_nested_legacy_secrets(monkeypatch):
    secret = "sk-" + ("a" * 32)

    class Orchestrator:
        async def get_context(self, **_kwargs):
            return {
                "memories": [{"content": f"Legacy content {secret}"}],
                "entities": [{"properties": {"token": f"Bearer {secret}"}}],
            }

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    response = await server._handle_get_context({})

    assert secret not in json.dumps(response)
    assert response["privacy_redactions"] == 2


@pytest.mark.asyncio
async def test_workflow_cannot_change_protected_memory(monkeypatch):
    protected = Memory(
        content="user decision",
        metadata=MemoryMetadata(user_locked=True),
    )

    class VectorStore:
        async def get_memory(self, _memory_id):
            return protected

        async def update_memory(self, *_args, **_kwargs):
            raise AssertionError("protected memory must not be changed")

    orchestrator = SimpleNamespace(vector_store=VectorStore())
    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_strict_project_resolution", lambda _args: None)
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(orchestrator))

    result = await server._handle_update_memory(
        {"memory_id": str(protected.id), "tags": ["automation rewrite"]}
    )

    assert result["success"] is False
    assert result["authority_status"] == "BLOCKED"
    assert "user-directed" in result["error"]


@pytest.mark.asyncio
async def test_legacy_delete_routes_archive_to_verified_correct(monkeypatch):
    server = ElefanteMCPServer()

    async def forbidden_orchestrator():
        raise AssertionError("legacy archive guidance must not open durable stores")

    monkeypatch.setattr(server, "_get_orchestrator", forbidden_orchestrator)

    result = await server._handle_delete_memory(
        {"memory_id": str(uuid4()), "reason": "no longer active"}
    )

    assert result["success"] is False
    assert result["delete_mode"] == "archive"
    assert result["error_code"] == "USE_VERIFIED_CORRECT"
    assert result["memory_read"] is False
    assert result["memory_written"] is False


@pytest.mark.asyncio
async def test_permanent_delete_requires_user_confirmation(monkeypatch):
    memory = Memory(content="ordinary note", metadata=MemoryMetadata())

    class VectorStore:
        async def get_memory(self, _memory_id):
            return memory

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=VectorStore())),
    )

    result = await server._handle_delete_memory(
        {
            "memory_id": str(memory.id),
            "reason": "requested cleanup",
            "delete_mode": "permanent",
        }
    )

    assert result["success"] is False
    assert result["authority_status"] == "CONFIRMATION_REQUIRED"
    assert "confirm_permanent=true" in result["error"]


@pytest.mark.asyncio
async def test_confirmed_legacy_permanent_delete_routes_to_verified_correct(monkeypatch):
    memory = Memory(content="ordinary note", metadata=MemoryMetadata())

    class VectorStore:
        async def get_memory(self, _memory_id):
            return memory

        async def delete_memory(self, _memory_id):
            raise AssertionError("permanent deletion must remain blocked")

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=VectorStore())),
    )

    result = await server._handle_delete_memory(
        {
            "memory_id": str(memory.id),
            "reason": "requested cleanup",
            "delete_mode": "permanent",
            "invocation_mode": "user_directed",
            "confirm_permanent": True,
        }
    )

    assert result["success"] is False
    assert result["error_code"] == "USE_VERIFIED_CORRECT"
    assert result["recoverable"] is True
    assert result["memory_written"] is False


@pytest.mark.asyncio
async def test_daemon_lifespan_releases_a_loaded_orchestrator():
    from src.mcp import daemon

    class CloseTrackingOrchestrator:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    app = daemon.create_app()
    orchestrator = CloseTrackingOrchestrator()

    async with app.router.lifespan_context(app):
        app.state.elefante_server.orchestrator = orchestrator

    assert orchestrator.closed
    assert app.state.elefante_server.orchestrator is None


@pytest.mark.asyncio
async def test_direct_stdio_main_releases_server_resources(monkeypatch):
    from src.mcp import server as server_module

    events: list[str] = []

    class CloseTrackingServer:
        async def run(self):
            events.append("run")

        async def close(self):
            events.append("close")

    monkeypatch.setattr(server_module, "ElefanteMCPServer", CloseTrackingServer)

    await server_module.main()

    assert events == ["run", "close"]


async def _async_value(value):
    return value


@pytest.mark.integration
@pytest.mark.slow
def test_bridge_reinitializes_against_a_restarted_daemon():
    """One live bridge survives daemon replacement without host reconnection."""
    repo = Path(__file__).resolve().parents[1]
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()

    with tempfile.TemporaryDirectory(prefix="elefante-bridge-restart-") as temp_dir:
        temp_root = Path(temp_dir)
        env = {
            **os.environ,
            "PYTHONPATH": str(repo),
            "HOME": str(temp_root / "home"),
            "USERPROFILE": str(temp_root / "home"),
            "ELEFANTE_DATA_DIR": str(temp_root / "data"),
            "ELEFANTE_DAEMON_PORT": str(port),
            "ELEFANTE_RECALL_ENABLED": "1",
            "ELEFANTE_TASK_INTELLIGENCE_ENABLED": "0",
            "HF_HOME": os.environ.get(
                "HF_HOME",
                str(Path.home() / ".cache" / "huggingface"),
            ),
        }
        daemon = _start_daemon(repo, env)
        bridge = None
        try:
            _wait_for_daemon(port, daemon)
            bridge = _start_bridge(repo, env, port, "codex", "restart-window")
            initialized = _bridge_request(
                bridge,
                1,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "Codex", "version": "1"},
                },
            )
            assert initialized["serverInfo"]["name"] == "elefante"
            _bridge_notification(bridge, "notifications/initialized", {})
            first_tools = _bridge_request(bridge, 2, "tools/list", {})
            assert {tool["name"] for tool in first_tools["tools"]} == EXPECTED_CUSTOMER_TOOLS

            _terminate(daemon)
            daemon = _start_daemon(repo, env)
            _wait_for_daemon(port, daemon)

            recovered_tools = _bridge_request(bridge, 3, "tools/list", {})
            assert [tool["name"] for tool in recovered_tools["tools"]] == [
                tool["name"] for tool in first_tools["tools"]
            ]
            status = _bridge_request(
                bridge,
                4,
                "tools/call",
                {"name": "elefante-SystemStatusGet", "arguments": {}},
            )
            status_payload = json.loads(status["content"][0]["text"])
            assert status_payload["success"] is True
            assert status_payload["status"]["enabled"] is True
            recall = _bridge_request(
                bridge,
                5,
                "tools/call",
                {
                    "name": "elefante-Recall",
                    "arguments": {
                        "question": "What prior decision applies to this isolated test?"
                    },
                },
            )
            recall_payload = json.loads(recall["content"][0]["text"])
            assert set(recall_payload) == {
                "success",
                "status",
                "context",
                "supplied_count",
                "abstained",
                "delivery_blocked",
                "read_only",
            }
            assert recall_payload["status"] == "no_match"
            assert recall_payload["read_only"] is True
        finally:
            if bridge is not None:
                _terminate(bridge)
            _terminate(daemon)


@pytest.mark.integration
@pytest.mark.slow
def test_two_bridge_clients_share_one_daemon_with_distinct_sources():
    """Two hosts write concurrently through one daemon without Kuzu contention."""
    repo = Path(__file__).resolve().parents[1]
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()

    with tempfile.TemporaryDirectory(prefix="elefante-daemon-") as temp_dir:
        temp_root = Path(temp_dir)
        host_huggingface_cache = Path(
            os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")
        )
        env = {
            **os.environ,
            "PYTHONPATH": str(repo),
            "HOME": str(temp_root / "home"),
            "USERPROFILE": str(temp_root / "home"),
            "ELEFANTE_DATA_DIR": str(temp_root / "data"),
            "ELEFANTE_DAEMON_PORT": str(port),
            "ELEFANTE_ALLOW_TEST_MEMORIES": "1",
            # Isolate Elefante data without forcing a second model download.
            # The fast suite warms this cache before the slow runtime proof.
            "HF_HOME": str(host_huggingface_cache),
        }
        daemon = _start_daemon(repo, env)
        bridges: list[subprocess.Popen[str]] = []
        memory_ids: list[str] = []
        try:
            _wait_for_daemon(port, daemon)
            first = _start_bridge(repo, env, port, "codex", "codex-window")
            second = _start_bridge(repo, env, port, "claude-code", "claude-window")
            bridges.extend((first, second))

            for bridge, client_name in ((first, "Codex"), (second, "Claude Code")):
                initialized = _bridge_request(
                    bridge,
                    1,
                    "initialize",
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": client_name, "version": "1"},
                    },
                )
                assert initialized["serverInfo"]["name"] == "elefante"
                _bridge_notification(bridge, "notifications/initialized", {})
                _bridge_request(
                    bridge,
                    2,
                    "tools/call",
                    {
                        "name": "elefante-Memory",
                        "arguments": {
                            "action": "search",
                            "query": "shared daemon provenance marker",
                            "limit": 1,
                        },
                    },
                )

            marker = f"shared-daemon-{port}"
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        _bridge_request,
                        bridge,
                        3,
                        "tools/call",
                        {
                            "name": "elefante-Memory",
                            "arguments": {
                                "action": "add",
                                "content": f"Daemon provenance {marker} host {index}",
                                "memory_type": "note",
                                "domain": "project",
                                "category": "provenance",
                                "force_new": True,
                            },
                        },
                    )
                    for index, bridge in enumerate((first, second), start=1)
                ]
                stored = [future.result() for future in futures]

            payloads = [json.loads(response["content"][0]["text"]) for response in stored]
            assert [payload["status"] for payload in payloads] == ["stored", "stored"]
            memory_ids = [payload["memory_id"] for payload in payloads]
        finally:
            for bridge in bridges:
                _terminate(bridge)
            _terminate(daemon)

        verifier = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import asyncio, json, sys; "
                    "from src.core.graph_store import GraphStore; "
                    "store = GraphStore(database_path=sys.argv[1]); "
                    "query = sys.argv[2]; "
                    "print(json.dumps(asyncio.run(store.execute_query(query)), default=str))"
                ),
                str(temp_root / "data" / "kuzu_db"),
                (
                    "MATCH (m:Entity)-[:WRITTEN_BY]->(s:Source) "
                    f"WHERE m.id IN ['{memory_ids[0]}', '{memory_ids[1]}'] "
                    "RETURN s.tool, s.instance_id, s.transport"
                ),
            ],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert verifier.returncode == 0, verifier.stderr
        rows = json.loads(verifier.stdout)
        provenance = {tuple(row["values"]) for row in rows}
        assert provenance == {
            ("codex", "codex-window", "streamable-http"),
            ("claude-code", "claude-window", "streamable-http"),
        }


def _wait_for_daemon(port: int, daemon: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1)
            if response.json() == {
                "status": "ok",
                "service": "elefante-daemon",
                "transport": "streamable-http",
            }:
                return
        except (httpx.HTTPError, ValueError):
            time.sleep(0.1)
    stderr = daemon.stderr.read() if daemon.stderr else ""
    raise AssertionError(f"daemon did not become ready: {stderr[-1000:]}")


def _start_daemon(repo: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "src.mcp.daemon"],
        cwd=repo,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )


def _start_bridge(
    repo: Path, base_env: dict[str, str], port: int, tool: str, instance_id: str
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "src.mcp.stdio_bridge"],
        cwd=repo,
        env={
            **base_env,
            "ELEFANTE_DAEMON_URL": f"http://127.0.0.1:{port}/mcp/",
            "ELEFANTE_CLIENT_TOOL": tool,
            "ELEFANTE_CLIENT_INSTANCE_ID": instance_id,
            "ELEFANTE_CLIENT_CWD": f"/workspace/{tool}",
        },
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )


def _bridge_request(
    bridge: subprocess.Popen[str], request_id: int, method: str, params: dict
) -> dict:
    assert bridge.stdin is not None
    assert bridge.stdout is not None
    assert bridge.stderr is not None
    bridge.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n")
    bridge.stdin.flush()
    ready, _, _ = select.select([bridge.stdout], [], [], BRIDGE_RESPONSE_TIMEOUT_SECONDS)
    if not ready:
        raise AssertionError(f"bridge timed out during {method}: {_available_stderr(bridge)[-1000:]}")
    line = bridge.stdout.readline()
    if not line:
        raise AssertionError(f"bridge ended during {method}: {_available_stderr(bridge)[-1000:]}")
    response = json.loads(line)
    assert "error" not in response, response
    return response["result"]


def _available_stderr(process: subprocess.Popen[str]) -> str:
    """Read only buffered diagnostics; never deadlock a timeout reporter."""
    if process.stderr is None:
        return ""
    chunks: list[bytes] = []
    while select.select([process.stderr], [], [], 0)[0]:
        chunk = os.read(process.stderr.fileno(), 4096)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _bridge_notification(bridge: subprocess.Popen[str], method: str, params: dict) -> None:
    assert bridge.stdin is not None
    bridge.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n")
    bridge.stdin.flush()


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
