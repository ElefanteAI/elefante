#!/usr/bin/env python3
"""Run exact-package product scenarios and emit content-free evidence receipts.

This harness is deliberately outside the customer payload. It talks to the
installed product through the shipped stdio bridge, uses generated disposable
content on an isolated acceptance machine, and writes only bounded check names
and artifact identity to its receipts. It never converts source tests into
package evidence.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import plistlib
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from typing import Any, Protocol
from uuid import UUID, uuid4
import zipfile

from scripts.ci.verify_product_release_gate import REQUIRED_SCENARIO_CHECKS


CONFIRMATION = "ISOLATED-EXACT-PACKAGE"
MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_TIMEOUT_SECONDS = 120.0
PACKAGE_TIMEOUT_SECONDS = 30 * 60.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
RECEIPT_SCHEMA_VERSION = 1
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SCENARIO_FILE_PATTERN = "scenario-{scenario}.json"
GATE_FILE_PATTERN = "scenario-{scenario}.gate.json"
PACKAGE_RECEIPT_FILE_NAME = ".elefante-package-receipt.json"
BUILD_IDENTITY_FILE_NAME = ".elefante-build.json"
FIRST_RUN_RECEIPT_FILE_NAME = ".elefante-first-run-receipt.json"
INSTALL_MARKER = b"Payload placed at:"


class ScenarioFailure(RuntimeError):
    """A bounded acceptance failure that never carries customer content."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _read_json(path: Path, *, max_bytes: int = MAX_RESPONSE_BYTES) -> dict[str, Any]:
    target = Path(path)
    if target.is_symlink() or not target.is_file() or target.stat().st_size > max_bytes:
        raise ScenarioFailure("SCENARIO_JSON_UNSAFE")
    try:
        payload = json.loads(
            target.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise ScenarioFailure("SCENARIO_JSON_INVALID") from error
    if not isinstance(payload, dict):
        raise ScenarioFailure("SCENARIO_JSON_INVALID")
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_uuid(value: object) -> str:
    try:
        normalized = str(UUID(str(value)))
    except (TypeError, ValueError) as error:
        raise ScenarioFailure("SCENARIO_UUID_INVALID") from error
    return normalized


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ScenarioFailure(code)


def _resolved_external_path(value: object, *, code: str) -> Path:
    """Resolve one caller path only after rejecting a symlink at its visible leaf."""
    raw = Path(str(value or "")).expanduser()
    _require(bool(str(value or "").strip()) and not raw.is_symlink(), code)
    return raw.resolve()


def _prepare_scenario_root(value: object, *, code: str) -> Path:
    root = _resolved_external_path(value, code=code)
    actual_home = Path.home().resolve()
    customer_root = actual_home / ".elefante"
    _require(
        not root.exists()
        and root != actual_home
        and root != customer_root
        and customer_root not in root.parents,
        code,
    )
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(root, 0o700)
    return root


def _prepare_evidence_directory(value: object, *, scenario_root: Path) -> Path:
    """Use one private evidence directory shared by separate A-F executions."""
    output = _resolved_external_path(value, code="SCENARIO_EVIDENCE_ROOT_INVALID")
    _require(
        output != scenario_root
        and scenario_root not in output.parents
        and output not in scenario_root.parents,
        "SCENARIO_EVIDENCE_ROOT_INVALID",
    )
    if output.exists():
        _require(
            output.is_dir()
            and not output.is_symlink()
            and stat.S_IMODE(output.stat().st_mode) & 0o077 == 0,
            "SCENARIO_EVIDENCE_ROOT_INVALID",
        )
    else:
        output.mkdir(parents=True, mode=0o700, exist_ok=False)
        os.chmod(output, 0o700)
    return output


def _atomic_private_write(path: Path, payload: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class ScenarioContext:
    artifact_path: Path
    artifact_sha256: str
    install_root: Path
    data_root: Path
    customer_home: Path
    project_alpha: Path
    project_beta: Path
    machine_id: str
    output_dir: Path
    scenario_root: Path | None = None
    bundle_root: Path | None = None
    codex_executable: Path | None = None
    base_environment: Mapping[str, str] | None = None


@dataclass(frozen=True)
class LifecycleScenarioContext:
    """All mutable package-lifecycle paths derived under one disposable root."""

    artifact_path: Path
    artifact_sha256: str
    scenario_root: Path
    codex_executable: Path
    machine_id: str
    output_dir: Path
    baseline_artifact_path: Path | None = None
    baseline_artifact_sha256: str | None = None

    def lane_home(self, lane: str) -> Path:
        return self.scenario_root / lane / "home"

    def lane_install_root(self, lane: str) -> Path:
        return self.lane_home(lane) / ".elefante" / "app" / "current"

    def lane_data_root(self, lane: str) -> Path:
        return self.lane_home(lane) / ".elefante" / "data"

    def lane_project(self, lane: str, name: str) -> Path:
        return self.scenario_root / lane / "projects" / name


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: bytes
    marker_seen: bool = False


class ProductClient(Protocol):
    async def start(self) -> None: ...

    async def call_tool(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]: ...

    async def close(self) -> None: ...


ClientFactory = Callable[[Path], ProductClient]


class MCPBridgeClient:
    """Minimal exact-installed-product MCP client with bounded parsing."""

    def __init__(
        self,
        install_root: Path,
        workspace: Path,
        *,
        base_environment: Mapping[str, str] | None = None,
    ) -> None:
        self.install_root = Path(install_root).resolve()
        self.workspace = Path(workspace).resolve()
        self.base_environment = dict(base_environment) if base_environment is not None else None
        self.process: asyncio.subprocess.Process | None = None
        self.request_id = 0

    def _python(self) -> Path:
        candidates = (
            self.install_root / ".venv" / "bin" / "python",
            self.install_root / ".venv" / "Scripts" / "python.exe",
        )
        target = next((item for item in candidates if item.is_file()), None)
        if target is None:
            raise ScenarioFailure("INSTALLED_PYTHON_MISSING")
        return target

    async def start(self) -> None:
        _require(self.workspace.is_dir(), "SCENARIO_WORKSPACE_MISSING")
        environment = {
            **(self.base_environment or os.environ),
            "PYTHONPATH": str(self.install_root),
            "ELEFANTE_CLIENT_CWD": str(self.workspace),
            "ELEFANTE_CLIENT_TOOL": "elefante-release-scenario",
            "ELEFANTE_CLIENT_INSTANCE_ID": f"scenario-{uuid4().hex}",
        }
        self.process = await asyncio.create_subprocess_exec(
            str(self._python()),
            "-m",
            "src.mcp.stdio_bridge",
            cwd=str(self.install_root),
            env=environment,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=MAX_RESPONSE_BYTES,
        )
        initialized = await self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "ElefanteProductReleaseScenario",
                    "version": "1.0",
                },
            },
        )
        _require(isinstance(initialized, dict), "MCP_INITIALIZE_FAILED")
        await self._notify("notifications/initialized", {})

    def _streams(self):
        if (
            self.process is None
            or self.process.stdin is None
            or self.process.stdout is None
            or self.process.stderr is None
        ):
            raise ScenarioFailure("MCP_BRIDGE_NOT_STARTED")
        return self.process.stdin, self.process.stdout, self.process.stderr

    async def _request(self, method: str, params: Mapping[str, Any]) -> Any:
        self.request_id += 1
        request_id = self.request_id
        stdin, stdout, stderr = self._streams()
        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": dict(params),
        }
        stdin.write(
            json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        )
        await stdin.drain()
        while True:
            line = await asyncio.wait_for(
                stdout.readline(),
                timeout=MCP_TIMEOUT_SECONDS,
            )
            if not line:
                await stderr.read(MAX_RESPONSE_BYTES)
                raise ScenarioFailure("MCP_BRIDGE_CLOSED")
            if len(line) > MAX_RESPONSE_BYTES:
                raise ScenarioFailure("MCP_RESPONSE_TOO_LARGE")
            try:
                response = json.loads(
                    line.decode("utf-8"),
                    object_pairs_hook=_strict_object,
                )
            except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(response, dict) or response.get("id") != request_id:
                continue
            if "error" in response:
                raise ScenarioFailure("MCP_PROTOCOL_ERROR")
            return response.get("result")

    async def _notify(self, method: str, params: Mapping[str, Any]) -> None:
        stdin, _, _ = self._streams()
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": dict(params),
        }
        stdin.write(
            json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        )
        await stdin.drain()

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        result = await self._request(
            "tools/call",
            {"name": name, "arguments": dict(arguments)},
        )
        content = result.get("content") if isinstance(result, dict) else None
        if not isinstance(content, list):
            raise ScenarioFailure("MCP_TOOL_RESPONSE_INVALID")
        text = next(
            (
                block.get("text")
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ),
            None,
        )
        if text is None or len(text.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise ScenarioFailure("MCP_TOOL_RESPONSE_INVALID")
        try:
            payload = json.loads(text, object_pairs_hook=_strict_object)
        except (ValueError, json.JSONDecodeError) as error:
            raise ScenarioFailure("MCP_TOOL_RESPONSE_INVALID") from error
        if not isinstance(payload, dict):
            raise ScenarioFailure("MCP_TOOL_RESPONSE_INVALID")
        return payload

    async def close(self) -> None:
        if self.process is None or self.process.returncode is not None:
            return
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=5)
        except asyncio.TimeoutError:
            self.process.kill()
            await self.process.wait()


def _default_client_factory(context: ScenarioContext) -> ClientFactory:
    return lambda workspace: MCPBridgeClient(
        context.install_root,
        workspace,
        base_environment=context.base_environment,
    )


async def _store_memory(
    client: ProductClient,
    content: str,
    *,
    force_new: bool = True,
) -> str:
    search = await client.call_tool(
        "elefante-Memory",
        {"action": "search", "query": content, "limit": 5},
    )
    _require(search.get("success") is True, "MEMORY_SEARCH_GATE_FAILED")
    stored = await client.call_tool(
        "elefante-Memory",
        {
            "action": "add",
            "content": content,
            "memory_type": "fact",
            "domain": "project",
            "category": "release-scenario",
            "tags": ["elefante-release-scenario"],
            "force_new": force_new,
            "invocation_mode": "user_directed",
        },
    )
    _require(stored.get("status") == "stored", "MEMORY_STORE_FAILED")
    return _safe_uuid(stored.get("memory_id") or stored.get("embedding_id"))


async def _remember_verified(
    client: ProductClient,
    content: str,
    *,
    verification_question: str,
) -> str:
    search = await client.call_tool(
        "elefante-Memory",
        {"action": "search", "query": content, "limit": 5},
    )
    _require(search.get("success") is True, "REMEMBER_SEARCH_GATE_FAILED")
    remembered = await client.call_tool(
        "elefante-Memory",
        {
            "action": "add",
            "content": content,
            "memory_type": "decision",
            "knowledge_kind": "decision",
            "domain": "project",
            "category": "release-scenario",
            "tags": ["elefante-release-scenario"],
            "verification_question": verification_question,
            "invocation_mode": "user_directed",
        },
    )
    _require(
        _all_receipt_checks_passed(remembered)
        and remembered.get("remember_status") == "VERIFIED_COMPLETE"
        and remembered.get("memory_written") is True
        and remembered.get("classification") == "VERIFIED",
        "VERIFIED_REMEMBER_FAILED",
    )
    return _safe_uuid(remembered.get("memory_id") or remembered.get("embedding_id"))


async def _list_memory_ids(client: ProductClient) -> set[str]:
    response = await client.call_tool(
        "elefante-Memory",
        {"action": "search", "list_all": True, "limit": 1000},
    )
    _require(response.get("success") is True, "MEMORY_LIST_FAILED")
    memories = response.get("memories")
    _require(isinstance(memories, list), "MEMORY_LIST_INVALID")
    return {
        str(item.get("id"))
        for item in memories
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


async def _recall(client: ProductClient, question: str) -> dict[str, Any]:
    return await client.call_tool("elefante-Recall", {"question": question})


def _recall_supplies(payload: Mapping[str, Any], required: str, forbidden: str) -> bool:
    context = payload.get("context")
    return bool(
        payload.get("status") == "supplied"
        and payload.get("read_only") is True
        and isinstance(context, str)
        and required in context
        and forbidden not in context
    )


def _blocked_without_delivery(payload: Mapping[str, Any]) -> bool:
    return bool(
        payload.get("status") == "blocked"
        and payload.get("supplied_count") == 0
        and payload.get("delivery_blocked") is True
        and payload.get("read_only") is True
    )


def _snapshot_project_policy(data_root: Path) -> bool:
    snapshot = _read_json(Path(data_root) / "dashboard_snapshot.json")
    registry = snapshot.get("project_registry")
    return bool(
        isinstance(registry, dict)
        and registry.get("mode") == "strict"
        and registry.get("scope_policy") == "isolated"
        and registry.get("shared_across_projects") is False
    )


def _validate_first_run_receipt(context: ScenarioContext) -> None:
    receipt_path = context.install_root / FIRST_RUN_RECEIPT_FILE_NAME
    receipt = _read_json(receipt_path)
    expected_fields = {
        "schema_version",
        "operation",
        "status",
        "finished_at",
        "checks",
        "acceptance_operation_id",
        "backup_operation_id",
        "initial_backup",
        "memory_content_included",
        "project_path_included",
        "next_action",
    }
    expected_checks = {
        "project_isolation",
        "disposable_recall",
        "acceptance_cleanup",
        "initial_backup",
    }
    checks = receipt.get("checks")
    _require(
        stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
        and set(receipt) == expected_fields
        and receipt.get("schema_version") == 1
        and receipt.get("operation") == "first_run_acceptance"
        and receipt.get("status") == "VERIFIED_COMPLETE"
        and receipt.get("memory_content_included") is False
        and receipt.get("project_path_included") is False
        and receipt.get("next_action") == "open_elefante_home"
        and isinstance(receipt.get("finished_at"), str)
        and isinstance(receipt.get("acceptance_operation_id"), str)
        and isinstance(receipt.get("backup_operation_id"), str)
        and isinstance(checks, list)
        and len(checks) == len(expected_checks)
        and all(
            isinstance(check, dict)
            and set(check) == {"name", "passed", "code"}
            and check.get("passed") is True
            and isinstance(check.get("code"), str)
            for check in checks
        )
        and {check["name"] for check in checks} == expected_checks,
        "A_FIRST_RUN_RECEIPT_INVALID",
    )
    initial_backup = receipt.get("initial_backup")
    _require(
        isinstance(initial_backup, dict)
        and set(initial_backup) == {"archive_name", "archive_sha256"}
        and isinstance(initial_backup.get("archive_name"), str)
        and initial_backup["archive_name"] == Path(initial_backup["archive_name"]).name
        and isinstance(initial_backup.get("archive_sha256"), str)
        and SHA256_PATTERN.fullmatch(initial_backup["archive_sha256"]) is not None,
        "A_INITIAL_BACKUP_RECEIPT_INVALID",
    )
    backup = context.data_root.parent / "backups" / initial_backup["archive_name"]
    _require(
        backup.is_file()
        and not backup.is_symlink()
        and _sha256_file(backup) == initial_backup["archive_sha256"],
        "A_INITIAL_BACKUP_INVALID",
    )


def _strict_project_ids(context: ScenarioContext) -> dict[str, str]:
    registry = _read_json(context.data_root / "projects.json")
    projects = registry.get("projects")
    _require(
        registry.get("schema_version") == 1
        and registry.get("mode") == "strict"
        and isinstance(projects, list)
        and len(projects) == 2,
        "A_PROJECT_REGISTRY_INVALID",
    )
    project_ids = {
        str(Path(project["root"]).resolve()): _safe_uuid(project.get("project_id"))
        for project in projects
        if isinstance(project, dict)
        and project.get("active") is True
        and isinstance(project.get("root"), str)
    }
    _require(
        set(project_ids)
        == {str(context.project_alpha.resolve()), str(context.project_beta.resolve())},
        "A_PROJECT_SELECTION_INVALID",
    )
    return project_ids


def _validate_first_run_projects(context: ScenarioContext) -> None:
    _strict_project_ids(context)


async def run_scenario_a(
    context: ScenarioContext,
    *,
    client_factory: ClientFactory | None = None,
) -> set[str]:
    """Prove first use, cleanup, and Recall after a fresh agent process."""
    _validate_first_run_receipt(context)
    _validate_first_run_projects(context)
    factory = client_factory or _default_client_factory(context)
    anchor = f"release-first-use-{uuid4().hex}"
    content = f"{anchor}: the accepted launch decision is copper."
    first = factory(context.project_alpha)
    try:
        await first.start()
        health_payload = await first.call_tool("elefante-Recover", {"action": "health"})
        health = health_payload.get("health")
        _require(
            health_payload.get("success") is True
            and isinstance(health, dict)
            and health.get("state") == "READY"
            and "Codex" in health.get("connected_agents", []),
            "A_AGENT_CONNECTION_FAILED",
        )
        memories = await first.call_tool(
            "elefante-Memory",
            {"action": "search", "list_all": True, "limit": 1000},
        )
        listed = memories.get("memories")
        _require(
            memories.get("success") is True and isinstance(listed, list),
            "A_ACCEPTANCE_CLEANUP_UNVERIFIED",
        )
        _require(
            not any(
                isinstance(item, dict)
                and isinstance(item.get("metadata"), dict)
                and item["metadata"].get("category") == "system-test"
                and item["metadata"].get("source_detail")
                == "official_package_acceptance"
                for item in listed
            ),
            "A_ACCEPTANCE_MEMORY_REMAINS",
        )
        await _remember_verified(
            first,
            content,
            verification_question=f"What is the accepted launch decision for {anchor}?",
        )
    finally:
        await first.close()

    restarted = factory(context.project_alpha)
    try:
        await restarted.start()
        recalled = await _recall(
            restarted,
            f"What is the accepted launch decision for {anchor}?",
        )
        _require(
            recalled.get("status") == "supplied"
            and recalled.get("read_only") is True
            and anchor in str(recalled.get("context") or "")
            and "copper" in str(recalled.get("context") or ""),
            "A_RESTART_RECALL_FAILED",
        )
    finally:
        await restarted.close()

    return set(REQUIRED_SCENARIO_CHECKS["A"])


async def run_scenario_b(
    context: ScenarioContext,
    *,
    client_factory: ClientFactory | None = None,
) -> set[str]:
    """Prove two real installed projects have zero cross-project exposure."""
    factory = client_factory or _default_client_factory(context)
    anchor = f"release-isolation-{uuid4().hex}"
    alpha_content = f"{anchor}: this project's acceptance color is amber."
    beta_content = f"{anchor}: this project's acceptance color is violet."
    alpha = factory(context.project_alpha)
    beta = factory(context.project_beta)
    missing_root = context.customer_home / f"unregistered-{uuid4().hex}"
    missing_root.mkdir(parents=True, exist_ok=False)
    missing = factory(missing_root)
    try:
        await alpha.start()
        await beta.start()
        alpha_id = await _remember_verified(
            alpha,
            alpha_content,
            verification_question=f"What acceptance color applies to {anchor}?",
        )
        beta_id = await _remember_verified(
            beta,
            beta_content,
            verification_question=f"What acceptance color applies to {anchor}?",
        )

        alpha_ids = await _list_memory_ids(alpha)
        beta_ids = await _list_memory_ids(beta)
        _require(alpha_id in alpha_ids and beta_id not in alpha_ids, "B_ALPHA_LEAK")
        _require(beta_id in beta_ids and alpha_id not in beta_ids, "B_BETA_LEAK")

        alpha_recall = await _recall(alpha, f"What acceptance color applies to {anchor}?")
        beta_recall = await _recall(beta, f"What acceptance color applies to {anchor}?")
        _require(
            _recall_supplies(alpha_recall, "amber", "violet"),
            "B_ALPHA_RECALL_FAILED",
        )
        _require(
            _recall_supplies(beta_recall, "violet", "amber"),
            "B_BETA_RECALL_FAILED",
        )

        await missing.start()
        missing_recall = await _recall(
            missing,
            f"What acceptance color applies to {anchor}?",
        )
        _require(_blocked_without_delivery(missing_recall), "B_MISSING_PROJECT_READ")

        registry_path = context.data_root / "projects.json"
        original = registry_path.read_bytes()
        original_mode = stat.S_IMODE(registry_path.stat().st_mode)
        try:
            _atomic_private_write(registry_path, b'{"schema_version":')
            invalid_recall = await _recall(
                alpha,
                f"What acceptance color applies to {anchor}?",
            )
            _require(
                _blocked_without_delivery(invalid_recall),
                "B_INVALID_PROJECT_STATE_READ",
            )
        finally:
            _atomic_private_write(registry_path, original)
            os.chmod(registry_path, original_mode)

        _require(_snapshot_project_policy(context.data_root), "B_SHARING_POLICY_INVALID")
    finally:
        await missing.close()
        await beta.close()
        await alpha.close()

    return set(REQUIRED_SCENARIO_CHECKS["B"])


def _all_receipt_checks_passed(payload: Mapping[str, Any]) -> bool:
    receipt = payload.get("receipt")
    checks = receipt.get("checks") if isinstance(receipt, dict) else None
    return bool(
        payload.get("success") is True
        and payload.get("status") == "VERIFIED_COMPLETE"
        and isinstance(checks, list)
        and checks
        and all(
            isinstance(check, dict)
            and check.get("passed") is True
            and isinstance(check.get("code"), str)
            for check in checks
        )
    )


async def _apply_correction(
    client: ProductClient,
    *,
    memory_id: str,
    correction: str,
    question: str,
    reason: str,
    content: str | None = None,
    related_memory_id: str | None = None,
    winner_memory_id: str | None = None,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "action": "correct",
        "memory_id": memory_id,
        "correction": correction,
        "invocation_mode": "user_directed",
    }
    if content is not None:
        base["content"] = content
    if related_memory_id is not None:
        base["related_memory_id"] = related_memory_id
    if winner_memory_id is not None:
        base["winner_memory_id"] = winner_memory_id
    plan_payload = await client.call_tool("elefante-Memory", base)
    plan = plan_payload.get("plan")
    _require(
        plan_payload.get("success") is True and isinstance(plan, dict),
        f"C_{correction.upper()}_PLAN_FAILED",
    )
    applicable = (
        plan.get("applicable")
        if correction != "resolve"
        else (plan.get("product_gate") or {}).get("applicable")
    )
    _require(applicable is True, f"C_{correction.upper()}_PLAN_BLOCKED")

    gate = await client.call_tool(
        "elefante-Memory",
        {"action": "search", "query": question, "limit": 5},
    )
    _require(gate.get("success") is True, "C_COMPLIANCE_SEARCH_FAILED")
    apply_args = {
        **base,
        "apply": True,
        "reason": reason,
        "verification_question": question,
    }
    if correction != "resolve":
        apply_args["expected_record_sha256"] = plan.get("record_sha256")
        apply_args["expected_graph_sha256"] = plan.get("graph_sha256")
        if correction in {"edit", "replace"}:
            apply_args["expected_content_sha256"] = plan.get("content_sha256")
    if correction == "permanent_delete":
        apply_args["confirm_permanent"] = True
    result = await client.call_tool("elefante-Memory", apply_args)
    _require(
        _all_receipt_checks_passed(result),
        f"C_{correction.upper()}_APPLY_FAILED",
    )
    return result


def _snapshot_has_correction_history(data_root: Path, memory_id: str) -> bool:
    snapshot = _read_json(Path(data_root) / "dashboard_snapshot.json")
    nodes = snapshot.get("nodes")
    if not isinstance(nodes, list):
        return False
    node = next(
        (
            item
            for item in nodes
            if isinstance(item, dict) and item.get("id") == memory_id
        ),
        None,
    )
    properties = node.get("properties") if isinstance(node, dict) else None
    history = (
        properties.get("verified_correction_history")
        if isinstance(properties, dict)
        else None
    )
    return bool(
        isinstance(history, list)
        and any(
            isinstance(item, dict) and item.get("action") == "edit"
            for item in history
        )
    )


def _permanent_delete_is_final(
    result: Mapping[str, Any],
    *,
    data_root: Path,
    memory_id: str,
    remaining_ids: set[str],
) -> bool:
    receipt = result.get("receipt")
    archive_name = (
        receipt.get("recovery_archive_name")
        if isinstance(receipt, dict)
        else None
    )
    return bool(
        isinstance(receipt, dict)
        and receipt.get("recoverable") is False
        and isinstance(archive_name, str)
        and archive_name == Path(archive_name).name
        and not (Path(data_root).parent / "backups" / archive_name).exists()
        and memory_id not in remaining_ids
    )


async def run_scenario_c(
    context: ScenarioContext,
    *,
    client_factory: ClientFactory | None = None,
) -> set[str]:
    """Exercise every Correct action through the installed MCP product path."""
    factory = client_factory or _default_client_factory(context)
    client = factory(context.project_alpha)
    anchor = f"release-correct-{uuid4().hex}"
    try:
        await client.start()
        edit_id = await _store_memory(client, f"{anchor}: edit value is bronze.")
        replace_id = await _store_memory(client, f"{anchor}: replace value is cedar.")
        lifecycle_id = await _store_memory(client, f"{anchor}: lifecycle value is active.")
        conflict_left = await _store_memory(
            client,
            f"{anchor}: conflict switch is enabled.",
        )
        conflict_right = await _store_memory(
            client,
            f"{anchor}: conflict switch is not enabled.",
            force_new=False,
        )
        delete_id = await _store_memory(client, f"{anchor}: delete value is temporary.")

        edit = await _apply_correction(
            client,
            memory_id=edit_id,
            correction="edit",
            content=f"{anchor}: edit value is copper.",
            question=f"What is the edit value for {anchor}?",
            reason="Exact-package Scenario C edit acceptance.",
        )
        replace = await _apply_correction(
            client,
            memory_id=replace_id,
            correction="replace",
            content=f"{anchor}: replace value is maple.",
            question=f"What is the replace value for {anchor}?",
            reason="Exact-package Scenario C replacement acceptance.",
        )
        archive = await _apply_correction(
            client,
            memory_id=lifecycle_id,
            correction="archive",
            question=f"Should the archived lifecycle value for {anchor} be supplied?",
            reason="Exact-package Scenario C archive acceptance.",
        )
        restore = await _apply_correction(
            client,
            memory_id=lifecycle_id,
            correction="restore",
            question=f"What is the lifecycle value for {anchor}?",
            reason="Exact-package Scenario C restore acceptance.",
        )
        resolve = await _apply_correction(
            client,
            memory_id=conflict_left,
            related_memory_id=conflict_right,
            winner_memory_id=conflict_right,
            correction="resolve",
            question=f"Is the conflict switch enabled for {anchor}?",
            reason="Exact-package Scenario C conflict acceptance.",
        )
        permanent = await _apply_correction(
            client,
            memory_id=delete_id,
            correction="permanent_delete",
            question=f"What temporary delete value exists for {anchor}?",
            reason="Exact-package Scenario C permanent deletion acceptance.",
        )

        results = (edit, replace, archive, restore, resolve, permanent)
        _require(
            all(_all_receipt_checks_passed(item) for item in results),
            "C_RECEIPT_CHECK_FAILED",
        )
        _require(
            any(
                check.get("name") == "scoped_recall" and check.get("passed") is True
                for result in results
                for check in (
                    result.get("receipt", {}).get("checks", [])
                    if isinstance(result.get("receipt"), dict)
                    else []
                )
                if isinstance(check, dict)
            ),
            "C_SCOPED_RECALL_MISSING",
        )
        _require(
            _snapshot_has_correction_history(context.data_root, edit_id),
            "C_HISTORY_MISSING",
        )
        remaining_ids = await _list_memory_ids(client)
        _require(
            _permanent_delete_is_final(
                permanent,
                data_root=context.data_root,
                memory_id=delete_id,
                remaining_ids=remaining_ids,
            ),
            "C_PERMANENT_DELETE_RECOVERABLE",
        )
    finally:
        await client.close()

    return set(REQUIRED_SCENARIO_CHECKS["C"])


def _read_support_report(archive_path: Path) -> tuple[bytes, dict[str, Any]]:
    target = Path(archive_path)
    _require(
        target.is_file() and not target.is_symlink(),
        "F_SUPPORT_ARCHIVE_MISSING",
    )
    try:
        with zipfile.ZipFile(target) as archive:
            _require(
                archive.namelist() == ["support-report.json"],
                "F_SUPPORT_ARCHIVE_LAYOUT_INVALID",
            )
            payload = archive.read("support-report.json")
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        raise ScenarioFailure("F_SUPPORT_ARCHIVE_INVALID") from error
    try:
        report = json.loads(payload, object_pairs_hook=_strict_object)
    except (ValueError, json.JSONDecodeError) as error:
        raise ScenarioFailure("F_SUPPORT_REPORT_INVALID") from error
    _require(isinstance(report, dict), "F_SUPPORT_REPORT_INVALID")
    return payload, report


async def run_scenario_f(
    context: ScenarioContext,
    *,
    client_factory: ClientFactory | None = None,
) -> set[str]:
    """Create a real diagnosable failure and prove support disclosure limits."""
    _require(sys.platform == "darwin", "F_CERTIFIED_PLATFORM_REQUIRED")
    _require(
        context.bundle_root is not None
        and context.scenario_root is not None
        and context.codex_executable is not None
        and context.base_environment is not None,
        "F_EXACT_PACKAGE_CONTEXT_REQUIRED",
    )
    factory = client_factory or _default_client_factory(context)
    token = uuid4().hex
    canaries = {
        "memory": f"SCENARIO_F_MEMORY_{token}",
        "prompt": f"SCENARIO_F_PROMPT_{token}",
        "credential": f"sk-scenario-{token}",
        "host": f"SCENARIO_F_HOST_CONFIG_{token}",
        "log": f"SCENARIO_F_APPLICATION_LOG_{token}",
        "project_name": context.project_alpha.name,
        "project_path": str(context.project_alpha),
    }

    # Prove the installed product works before inducing the package failure. The
    # private canaries are kept only in the disposable scenario data root.
    initial_client = factory(context.project_alpha)
    try:
        await initial_client.start()
        await _store_memory(
            initial_client,
            f"{canaries['memory']}: the support acceptance state is copper.",
        )
        initial_recall = await _recall(
            initial_client,
            (
                f"What is the support acceptance state for {canaries['memory']}? "
                f"{canaries['prompt']}"
            ),
        )
        _require(
            initial_recall.get("status") == "supplied"
            and initial_recall.get("read_only") is True
            and canaries["memory"] in str(initial_recall.get("context") or ""),
            "F_PRE_FAILURE_RECALL_FAILED",
        )
    finally:
        await initial_client.close()

    description = await _describe_package_operation(
        context.bundle_root,
        context.install_root,
        context.base_environment,
    )
    _require(
        description.get("operation") == "repair"
        and description.get("requires_confirmation") is False,
        "F_REPAIR_DESCRIPTION_INVALID",
    )
    wrapper_dir = context.scenario_root / "runtime" / "scenario-f-failure-bin"
    _write_failing_codex_wrapper(wrapper_dir)
    failure_flag = context.scenario_root / "runtime" / "scenario-f-fail-next-codex"
    failure_environment = dict(context.base_environment)
    failure_environment.update(
        {
            "PATH": os.pathsep.join(
                [
                    str(wrapper_dir),
                    str(context.codex_executable.parent),
                    failure_environment.get("PATH", ""),
                ]
            ),
            "ELEFANTE_SCENARIO_CODEX_FAIL_FLAG": str(failure_flag),
            "ELEFANTE_SCENARIO_REAL_CODEX": str(context.codex_executable),
        }
    )

    def arm_failure(_process: asyncio.subprocess.Process) -> None:
        _atomic_private_write(failure_flag, b"fail once\n")

    repair = await _run_bounded_command(
        _package_command(
            context.bundle_root,
            context.install_root,
            "--venv-mode",
            "fresh",
        ),
        cwd=context.bundle_root,
        environment=failure_environment,
        marker=INSTALL_MARKER,
        on_marker=arm_failure,
    )
    _require(repair.marker_seen, "F_REPAIR_SWITCH_NOT_REACHED")
    _require(repair.returncode != 0, "F_FORCED_REPAIR_FAILURE_NOT_OBSERVED")
    _require(not failure_flag.exists(), "F_CODEX_FAILURE_NOT_CONSUMED")
    package_identity = _package_identity(context.bundle_root)
    await _require_ready_product(
        context.install_root,
        package_identity,
        failure_environment,
    )
    _verify_installed_payload_matches_package(context.bundle_root, context.install_root)
    package_receipt = _read_json(
        context.install_root / PACKAGE_RECEIPT_FILE_NAME
    )
    _require(
        package_receipt.get("operation") == "repair"
        and package_receipt.get("status") == "FAILED_ROLLED_BACK"
        and package_receipt.get("failed_stage") == "4"
        and package_receipt.get("rollback") == "previous_product_restored"
        and package_receipt.get("recoverable") is True
        and package_receipt.get("changed") is False
        and package_receipt.get("next_action") == "create_support_report",
        "F_FAILED_REPAIR_RECEIPT_INVALID",
    )

    client = factory(context.project_alpha)
    service_path = (
        context.customer_home
        / "Library"
        / "LaunchAgents"
        / "ai.elefante.daemon.plist"
    )
    host_path = context.customer_home / ".codex" / "scenario-support-canary.txt"
    log_path = context.install_root / ".elefante-install.log"
    _require(service_path.is_file() and not service_path.is_symlink(), "F_SERVICE_FILE_MISSING")
    preserved: dict[Path, tuple[bytes | None, int | None]] = {}
    for path in (service_path, host_path, log_path):
        preserved[path] = (
            path.read_bytes() if path.is_file() and not path.is_symlink() else None,
            stat.S_IMODE(path.stat().st_mode)
            if path.is_file() and not path.is_symlink()
            else None,
        )

    try:
        await client.start()
        _atomic_private_write(host_path, (canaries["host"] + "\n").encode("utf-8"))
        existing_log = preserved[log_path][0] or b""
        _atomic_private_write(
            log_path,
            existing_log + ("\n" + canaries["log"] + "\n").encode("utf-8"),
        )
        service_bytes = preserved[service_path][0]
        _require(service_bytes is not None, "F_SERVICE_FILE_MISSING")
        _atomic_private_write(
            service_path,
            service_bytes
            + (
                "\n<!-- "
                + canaries["credential"]
                + " "
                + canaries["host"]
                + " -->\n"
            ).encode("utf-8"),
        )

        health_result = await client.call_tool(
            "elefante-Recover",
            {"action": "health"},
        )
        health = health_result.get("health")
        package_health = (
            health.get("package_maintenance", {}).get("receipt", {})
            if isinstance(health, Mapping)
            else {}
        )
        _require(
            health_result.get("success") is True
            and isinstance(health, Mapping)
            and health.get("state") == "NEEDS_ATTENTION"
            and health.get("next_action") == "create_support_report"
            and "package_followup_required" in health.get("diagnostic_codes", [])
            and isinstance(package_health, Mapping)
            and package_health.get("operation") == "repair"
            and package_health.get("status") == "FAILED_ROLLED_BACK"
            and package_health.get("failed_stage") == "4",
            "F_HOME_FAILED_STAGE_NOT_IDENTIFIED",
        )

        preview = await client.call_tool(
            "elefante-Recover",
            {"action": "support_report"},
        )
        plan = preview.get("plan")
        _require(
            preview.get("success") is True
            and isinstance(plan, dict)
            and plan.get("applicable") is True
            and isinstance(plan.get("report_sha256"), str)
            and SHA256_PATTERN.fullmatch(str(plan["report_sha256"])) is not None,
            "F_SUPPORT_PREVIEW_FAILED",
        )
        serialized_preview = json.dumps(preview, sort_keys=True)
        _require(
            all(value not in serialized_preview for value in canaries.values()),
            "F_PREVIEW_DISCLOSED_CONTENT",
        )
        exported = await client.call_tool(
            "elefante-Recover",
            {
                "action": "support_report",
                "apply": True,
                "confirm": True,
                "expected_report_sha256": plan["report_sha256"],
                "invocation_mode": "workflow_managed",
            },
        )
        _require(_all_receipt_checks_passed(exported), "F_SUPPORT_EXPORT_FAILED")
        receipt = exported.get("receipt")
        archive_name = receipt.get("archive_name") if isinstance(receipt, dict) else None
        _require(
            isinstance(archive_name, str)
            and archive_name == Path(archive_name).name,
            "F_SUPPORT_ARCHIVE_NAME_INVALID",
        )
        report_bytes, report = _read_support_report(
            context.data_root.parent / "support" / archive_name
        )
        diagnostics = (
            report.get("evidence", {}).get("diagnostic_codes", [])
            if isinstance(report.get("evidence"), dict)
            else []
        )
        report_package_receipt = (
            report.get("evidence", {})
            .get("operation_receipts", {})
            .get("package", {})
            .get("receipt", {})
            if isinstance(report.get("evidence"), dict)
            else {}
        )
        _require(
            isinstance(diagnostics, list)
            and "daemon_service_user_managed" in diagnostics
            and isinstance(report_package_receipt, Mapping)
            and report_package_receipt.get("operation") == "repair"
            and report_package_receipt.get("status") == "FAILED_ROLLED_BACK"
            and report_package_receipt.get("failed_stage") == "4",
            "F_FAILED_STAGE_NOT_IDENTIFIED",
        )
        _require(
            all(value.encode("utf-8") not in report_bytes for value in canaries.values()),
            "F_SUPPORT_REPORT_DISCLOSED_CONTENT",
        )
    finally:
        await client.close()
        for path, (payload, mode) in preserved.items():
            if payload is None:
                path.unlink(missing_ok=True)
                continue
            _atomic_private_write(path, payload)
            if mode is not None:
                os.chmod(path, mode)

    return set(REQUIRED_SCENARIO_CHECKS["F"])


def _append_bounded_output(current: bytearray, chunk: bytes) -> None:
    current.extend(chunk)
    if len(current) > MAX_RESPONSE_BYTES:
        del current[: len(current) - MAX_RESPONSE_BYTES]


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            process.kill()
        await process.wait()


async def _run_bounded_command(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    marker: bytes | None = None,
    on_marker: Callable[[asyncio.subprocess.Process], None] | None = None,
    marker_delay_seconds: float = 0.0,
    timeout_seconds: float = PACKAGE_TIMEOUT_SECONDS,
) -> CommandResult:
    """Run one isolated package command while retaining only a bounded output tail."""
    process = await asyncio.create_subprocess_exec(
        *[str(part) for part in command],
        cwd=str(cwd),
        env=dict(environment),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    _require(process.stdout is not None, "PACKAGE_COMMAND_STREAM_MISSING")
    output = bytearray()
    search_tail = b""
    marker_seen = False
    try:
        async with asyncio.timeout(timeout_seconds):
            while True:
                chunk = await process.stdout.read(64 * 1024)
                if not chunk:
                    break
                _append_bounded_output(output, chunk)
                if marker is not None and not marker_seen:
                    search_window = search_tail + chunk
                    if marker in search_window:
                        marker_seen = True
                        if marker_delay_seconds > 0:
                            await asyncio.sleep(marker_delay_seconds)
                        if on_marker is not None and process.returncode is None:
                            on_marker(process)
                    search_tail = search_window[-max(len(marker) - 1, 0) :]
            returncode = await process.wait()
    except TimeoutError as error:
        await _terminate_process(process)
        raise ScenarioFailure("PACKAGE_COMMAND_TIMEOUT") from error
    except Exception:
        await _terminate_process(process)
        raise
    return CommandResult(
        returncode=returncode,
        output=bytes(output),
        marker_seen=marker_seen,
    )


def _json_from_output(payload: bytes, *, code: str) -> dict[str, Any]:
    for line in reversed(payload.splitlines()):
        candidate = line.strip()
        if not candidate.startswith(b"{"):
            continue
        try:
            value = json.loads(candidate.decode("utf-8"), object_pairs_hook=_strict_object)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            return value
    raise ScenarioFailure(code)


def _scenario_environment(
    context: LifecycleScenarioContext,
    home: Path,
    *,
    scenario: str = "D",
    wrapper_dir: Path | None = None,
    failure_flag: Path | None = None,
) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    codex_home = home / ".codex"
    xdg_home = home / ".config"
    temporary = home / "tmp"
    for path in (codex_home, xdg_home, temporary):
        path.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    for key in tuple(environment):
        if key.startswith("ELEFANTE_") or key in {"CODEX_HOME", "PYTHONPATH"}:
            environment.pop(key, None)
    path_prefix = wrapper_dir or context.codex_executable.parent
    environment.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "XDG_CONFIG_HOME": str(xdg_home),
            "TMPDIR": str(temporary),
            "PYTHONUNBUFFERED": "1",
            "PATH": os.pathsep.join(
                [str(path_prefix), str(context.codex_executable.parent), environment.get("PATH", "")]
            ),
            "ELEFANTE_RELEASE_SCENARIO": scenario,
        }
    )
    if failure_flag is not None:
        environment["ELEFANTE_SCENARIO_CODEX_FAIL_FLAG"] = str(failure_flag)
        environment["ELEFANTE_SCENARIO_REAL_CODEX"] = str(context.codex_executable)
    return environment


def _validate_zip_members(artifact: Path) -> None:
    try:
        with zipfile.ZipFile(artifact) as archive:
            members = archive.infolist()
            _require(bool(members), "PACKAGE_ARCHIVE_EMPTY")
            for member in members:
                name = member.filename
                path = PurePosixPath(name)
                mode = member.external_attr >> 16
                _require(
                    bool(name)
                    and "\\" not in name
                    and not path.is_absolute()
                    and ".." not in path.parts
                    and not stat.S_ISLNK(mode),
                    "PACKAGE_ARCHIVE_UNSAFE",
                )
    except (OSError, zipfile.BadZipFile) as error:
        raise ScenarioFailure("PACKAGE_ARCHIVE_INVALID") from error


def _locate_bundle_root(root: Path) -> Path:
    candidates = {
        candidate.parent.resolve()
        for candidate in Path(root).rglob("install.sh")
        if candidate.is_file()
        and not candidate.is_symlink()
        and (candidate.parent / "bundle-manifest.json").is_file()
    }
    _require(len(candidates) == 1, "PACKAGE_BUNDLE_ROOT_AMBIGUOUS")
    bundle_root = next(iter(candidates))
    _require(
        (bundle_root / BUILD_IDENTITY_FILE_NAME).is_file(),
        "PACKAGE_BUILD_IDENTITY_MISSING",
    )
    return bundle_root


def _dmg_mount_point(payload: bytes) -> Path:
    try:
        document = plistlib.loads(payload)
    except (ValueError, plistlib.InvalidFileException) as error:
        raise ScenarioFailure("PACKAGE_DMG_ATTACH_INVALID") from error
    entities = document.get("system-entities") if isinstance(document, dict) else None
    mount_points = {
        Path(item["mount-point"]).resolve()
        for item in entities or []
        if isinstance(item, dict) and isinstance(item.get("mount-point"), str)
    }
    _require(len(mount_points) == 1, "PACKAGE_DMG_MOUNT_AMBIGUOUS")
    return next(iter(mount_points))


@contextmanager
def _materialize_package(artifact: Path, destination: Path) -> Iterator[Path]:
    """Yield the bundle root derived directly from one ZIP or read-only DMG."""
    artifact = Path(artifact)
    suffix = artifact.suffix.casefold()
    if suffix == ".zip":
        _validate_zip_members(artifact)
        destination.mkdir(parents=True, exist_ok=False)
        result = subprocess.run(
            ["ditto", "-x", "-k", str(artifact), str(destination)],
            capture_output=True,
            check=False,
        )
        _require(result.returncode == 0, "PACKAGE_ARCHIVE_EXTRACTION_FAILED")
        yield _locate_bundle_root(destination)
        return
    _require(suffix == ".dmg", "PACKAGE_ARTIFACT_FORMAT_UNSUPPORTED")
    result = subprocess.run(
        ["hdiutil", "attach", "-readonly", "-nobrowse", "-plist", str(artifact)],
        capture_output=True,
        check=False,
    )
    _require(result.returncode == 0, "PACKAGE_DMG_ATTACH_FAILED")
    mount_point = _dmg_mount_point(result.stdout)
    try:
        yield _locate_bundle_root(mount_point)
    finally:
        detached = subprocess.run(
            ["hdiutil", "detach", str(mount_point)],
            capture_output=True,
            check=False,
        )
        _require(detached.returncode == 0, "PACKAGE_DMG_DETACH_FAILED")


def _package_identity(bundle_root: Path) -> dict[str, Any]:
    identity = _read_json(Path(bundle_root) / BUILD_IDENTITY_FILE_NAME)
    _require(
        identity.get("schema_version") == 1
        and isinstance(identity.get("version"), str)
        and re.fullmatch(r"\d+\.\d+\.\d+", str(identity["version"])) is not None
        and isinstance(identity.get("source_commit"), str)
        and re.fullmatch(r"[0-9a-f]{40}", str(identity["source_commit"])) is not None
        and identity.get("source_clean") is True
        and identity.get("release_channel") in {"candidate", "release"},
        "PACKAGE_BUILD_IDENTITY_INVALID",
    )
    return identity


def _verify_installed_payload_matches_package(
    bundle_root: Path,
    install_root: Path,
) -> str:
    """Bind every shipped payload file to the fresh installed runtime bytes."""
    payload_root = Path(bundle_root) / "payload" / "elefante"
    installed_root = Path(install_root)
    _require(
        payload_root.is_dir()
        and not payload_root.is_symlink()
        and installed_root.is_dir()
        and not installed_root.is_symlink(),
        "RUNTIME_PAYLOAD_ROOT_UNSAFE",
    )
    digest = hashlib.sha256()
    entries = 0
    for source in sorted(
        payload_root.rglob("*"),
        key=lambda item: item.relative_to(payload_root).as_posix(),
    ):
        relative = source.relative_to(payload_root)
        target = installed_root / relative
        _require(
            not source.is_symlink() and not target.is_symlink(),
            "RUNTIME_PAYLOAD_SYMLINK_UNSAFE",
        )
        encoded = relative.as_posix().encode("utf-8")
        if source.is_dir():
            _require(target.is_dir(), "RUNTIME_PAYLOAD_DIRECTORY_MISMATCH")
            digest.update(b"D\0" + encoded + b"\0")
            entries += 1
            continue
        _require(
            source.is_file() and target.is_file(),
            "RUNTIME_PAYLOAD_FILE_MISSING",
        )
        source_sha256 = _sha256_file(source)
        target_sha256 = _sha256_file(target)
        _require(source_sha256 == target_sha256, "RUNTIME_PAYLOAD_FILE_MISMATCH")
        digest.update(
            b"F\0"
            + encoded
            + b"\0"
            + source_sha256.encode("ascii")
            + b"\0"
        )
        entries += 1
    _require(entries > 0, "RUNTIME_PAYLOAD_EMPTY")
    return digest.hexdigest()


def _package_command(
    bundle_root: Path,
    install_root: Path,
    *arguments: str,
) -> list[str]:
    return [
        "/bin/bash",
        str(Path(bundle_root) / "install.sh"),
        "--install-root",
        str(install_root),
        *arguments,
    ]


async def _describe_package_operation(
    bundle_root: Path,
    install_root: Path,
    environment: Mapping[str, str],
) -> dict[str, Any]:
    result = await _run_bounded_command(
        _package_command(bundle_root, install_root, "--describe-operation"),
        cwd=bundle_root,
        environment=environment,
    )
    _require(result.returncode == 0, "D_OPERATION_DESCRIPTION_FAILED")
    return _json_from_output(result.output, code="D_OPERATION_DESCRIPTION_INVALID")


async def _doctor_report(
    install_root: Path,
    environment: Mapping[str, str],
) -> dict[str, Any]:
    python = install_root / ".venv" / "bin" / "python"
    doctor = install_root / "scripts" / "lifecycle" / "doctor.py"
    _require(python.is_file() and doctor.is_file(), "D_INSTALLED_RUNTIME_MISSING")
    result = await _run_bounded_command(
        [str(python), str(doctor), "--json"],
        cwd=install_root,
        environment=environment,
    )
    _require(result.returncode == 0, "D_DOCTOR_FAILED")
    return _json_from_output(result.output, code="D_DOCTOR_INVALID")


async def _require_ready_product(
    install_root: Path,
    expected_identity: Mapping[str, Any],
    environment: Mapping[str, str],
) -> None:
    installed_identity = _read_json(install_root / BUILD_IDENTITY_FILE_NAME)
    _require(installed_identity == dict(expected_identity), "D_ACTIVE_BUILD_IDENTITY_MISMATCH")
    doctor = await _doctor_report(install_root, environment)
    _require(
        doctor.get("ready") is True
        and doctor.get("customer_ready") is True
        and doctor.get("daemon", {}).get("daemon_health") is True
        and doctor.get("recall", {}).get("ready") is True,
        "D_PRODUCT_NOT_READY",
    )


async def _exercise_interrupted_install(
    context: LifecycleScenarioContext,
    candidate_root: Path,
    candidate_identity: Mapping[str, Any],
) -> tuple[Path, Path, dict[str, str]]:
    lane = "interrupted-install"
    home = context.lane_home(lane)
    install_root = context.lane_install_root(lane)
    project_alpha = context.lane_project(lane, "Alpha")
    project_beta = context.lane_project(lane, "Beta")
    project_alpha.mkdir(parents=True, exist_ok=False)
    project_beta.mkdir(parents=True, exist_ok=False)
    environment = _scenario_environment(context, home)
    install_command = _package_command(
        candidate_root,
        install_root,
        "--venv-mode",
        "fresh",
        "--project",
        f"Alpha={project_alpha}",
        "--project",
        f"Beta={project_beta}",
    )

    def interrupt(process: asyncio.subprocess.Process) -> None:
        try:
            os.killpg(process.pid, signal.SIGINT)
        except (OSError, ProcessLookupError) as error:
            raise ScenarioFailure("D_INSTALL_INTERRUPT_FAILED") from error

    interrupted = await _run_bounded_command(
        install_command,
        cwd=candidate_root,
        environment=environment,
        marker=INSTALL_MARKER,
        on_marker=interrupt,
        marker_delay_seconds=0.75,
    )
    _require(interrupted.marker_seen, "D_INSTALL_SWITCH_NOT_REACHED")
    _require(interrupted.returncode != 0, "D_INSTALL_INTERRUPT_NOT_OBSERVED")
    failure_receipt = _read_json(install_root / PACKAGE_RECEIPT_FILE_NAME)
    _require(
        failure_receipt.get("operation") == "install"
        and failure_receipt.get("status") == "NEEDS_HUMAN"
        and failure_receipt.get("changed") is False,
        "D_INSTALL_INTERRUPT_RECEIPT_INVALID",
    )
    retry_description = await _describe_package_operation(
        candidate_root,
        install_root,
        environment,
    )
    _require(
        retry_description.get("operation") == "install"
        and retry_description.get("requires_confirmation") is False,
        "D_INSTALL_RETRY_NOT_SAFE",
    )
    resumed = await _run_bounded_command(
        install_command,
        cwd=candidate_root,
        environment=environment,
    )
    _require(resumed.returncode == 0, "D_INSTALL_RESUME_FAILED")
    await _require_ready_product(install_root, candidate_identity, environment)
    first_run = _read_json(install_root / FIRST_RUN_RECEIPT_FILE_NAME)
    _require(
        first_run.get("status") == "VERIFIED_COMPLETE"
        and first_run.get("memory_content_included") is False
        and first_run.get("project_path_included") is False,
        "D_INSTALL_RESUME_ACCEPTANCE_INVALID",
    )
    return install_root, project_alpha, environment


async def _exercise_daemon_restart_and_stale_session(
    install_root: Path,
    project_alpha: Path,
    environment: Mapping[str, str],
) -> None:
    client = MCPBridgeClient(
        install_root,
        project_alpha,
        base_environment=environment,
    )
    anchor = f"release-daemon-restart-{uuid4().hex}"
    content = f"{anchor}: the restart acceptance value is copper."
    try:
        await client.start()
        await _store_memory(client, content)
        initial = await _recall(client, f"What is the restart acceptance value for {anchor}?")
        _require(
            initial.get("status") == "supplied" and anchor in str(initial.get("context") or ""),
            "D_PRE_RESTART_RECALL_FAILED",
        )
        python = install_root / ".venv" / "bin" / "python"
        service = install_root / "scripts" / "lifecycle" / "daemon_service.py"
        stopped = await _run_bounded_command(
            [str(python), str(service), "stop", "--apply"],
            cwd=install_root,
            environment=environment,
        )
        _require(stopped.returncode == 0, "D_DAEMON_STOP_FAILED")
        started = await _run_bounded_command(
            [str(python), str(service), "start", "--apply"],
            cwd=install_root,
            environment=environment,
        )
        _require(started.returncode == 0, "D_DAEMON_START_FAILED")
        recovered = await _recall(client, f"What is the restart acceptance value for {anchor}?")
        _require(
            recovered.get("status") == "supplied"
            and anchor in str(recovered.get("context") or ""),
            "D_STALE_SESSION_RECOVERY_FAILED",
        )
    finally:
        await client.close()


def _write_failing_codex_wrapper(wrapper_dir: Path) -> Path:
    wrapper_dir.mkdir(parents=True, exist_ok=False)
    wrapper = wrapper_dir / "codex"
    source = """#!/usr/bin/env python3
from pathlib import Path
import os
import sys

flag = Path(os.environ["ELEFANTE_SCENARIO_CODEX_FAIL_FLAG"])
real = os.environ["ELEFANTE_SCENARIO_REAL_CODEX"]
if flag.is_file():
    flag.unlink()
    raise SystemExit(93)
os.execv(real, [real, *sys.argv[1:]])
"""
    _atomic_private_write(wrapper, source.encode("utf-8"))
    os.chmod(wrapper, 0o700)
    return wrapper


def _validate_failed_update_receipt(receipt: Mapping[str, Any]) -> None:
    checks = {
        item.get("name"): item
        for item in receipt.get("checks", [])
        if isinstance(item, Mapping) and isinstance(item.get("name"), str)
    }
    _require(
        receipt.get("operation") == "update"
        and receipt.get("status") == "FAILED_ROLLED_BACK"
        and receipt.get("failed_stage") == "4"
        and receipt.get("rollback") == "previous_product_restored"
        and receipt.get("recoverable") is True
        and receipt.get("changed") is False
        and receipt.get("next_action") == "create_support_report"
        and receipt.get("failed_candidate_name") is None
        and checks.get("safety_backup", {}).get("passed") is True
        and checks.get("product_readiness", {}).get("passed") is True,
        "D_FAILED_UPDATE_RECEIPT_INVALID",
    )


async def _exercise_failed_update_rollback(
    context: LifecycleScenarioContext,
    candidate_root: Path,
    candidate_identity: Mapping[str, Any],
    baseline_root: Path,
    baseline_identity: Mapping[str, Any],
) -> tuple[Path, dict[str, str]]:
    lane = "failed-update"
    home = context.lane_home(lane)
    install_root = context.lane_install_root(lane)
    project_alpha = context.lane_project(lane, "Alpha")
    project_beta = context.lane_project(lane, "Beta")
    project_alpha.mkdir(parents=True, exist_ok=False)
    project_beta.mkdir(parents=True, exist_ok=False)
    baseline_environment = _scenario_environment(context, home)
    installed = await _run_bounded_command(
        _package_command(
            baseline_root,
            install_root,
            "--venv-mode",
            "fresh",
            "--project",
            f"Alpha={project_alpha}",
            "--project",
            f"Beta={project_beta}",
        ),
        cwd=baseline_root,
        environment=baseline_environment,
    )
    _require(installed.returncode == 0, "D_BASELINE_INSTALL_FAILED")
    await _require_ready_product(install_root, baseline_identity, baseline_environment)

    client = MCPBridgeClient(
        install_root,
        project_alpha,
        base_environment=baseline_environment,
    )
    anchor = f"release-update-rollback-{uuid4().hex}"
    content = f"{anchor}: the rollback acceptance value is intact."
    try:
        await client.start()
        await _store_memory(client, content)
    finally:
        await client.close()

    baseline_identity_bytes = (install_root / BUILD_IDENTITY_FILE_NAME).read_bytes()
    description = await _describe_package_operation(
        candidate_root,
        install_root,
        baseline_environment,
    )
    _require(
        description.get("operation") == "update"
        and description.get("requires_confirmation") is False,
        "D_CANDIDATE_NOT_UPDATE",
    )

    wrapper_dir = context.scenario_root / lane / "failure-bin"
    _write_failing_codex_wrapper(wrapper_dir)
    failure_flag = context.scenario_root / lane / "fail-next-codex"
    update_environment = _scenario_environment(
        context,
        home,
        wrapper_dir=wrapper_dir,
        failure_flag=failure_flag,
    )

    def arm_failure(_process: asyncio.subprocess.Process) -> None:
        _atomic_private_write(failure_flag, b"fail once\n")

    update = await _run_bounded_command(
        _package_command(candidate_root, install_root, "--venv-mode", "fresh"),
        cwd=candidate_root,
        environment=update_environment,
        marker=INSTALL_MARKER,
        on_marker=arm_failure,
    )
    _require(update.marker_seen, "D_UPDATE_SWITCH_NOT_REACHED")
    _require(update.returncode != 0, "D_FORCED_UPDATE_FAILURE_NOT_OBSERVED")
    _require(not failure_flag.exists(), "D_CODEX_FAILURE_NOT_CONSUMED")
    _require(
        (install_root / BUILD_IDENTITY_FILE_NAME).read_bytes() == baseline_identity_bytes,
        "D_PREVIOUS_BUILD_NOT_RESTORED",
    )
    await _require_ready_product(install_root, baseline_identity, update_environment)
    receipt = _read_json(install_root / PACKAGE_RECEIPT_FILE_NAME)
    _validate_failed_update_receipt(receipt)

    restored_client = MCPBridgeClient(
        install_root,
        project_alpha,
        base_environment=update_environment,
    )
    try:
        await restored_client.start()
        recalled = await _recall(
            restored_client,
            f"What is the rollback acceptance value for {anchor}?",
        )
        _require(
            recalled.get("status") == "supplied"
            and anchor in str(recalled.get("context") or ""),
            "D_ROLLBACK_DATA_RECALL_FAILED",
        )
        home_health = await restored_client.call_tool(
            "elefante-Recover",
            {"action": "health"},
        )
        health = home_health.get("health")
        _require(
            home_health.get("success") is True
            and isinstance(health, Mapping)
            and health.get("state") == "NEEDS_ATTENTION"
            and health.get("next_action") == "create_support_report"
            and "package_followup_required" in health.get("diagnostic_codes", [])
            and health.get("package_maintenance", {}).get("receipt", {}).get("status")
            == "FAILED_ROLLED_BACK",
            "D_HOME_NEXT_ACTION_INVALID",
        )
    finally:
        await restored_client.close()
    _require(candidate_identity != baseline_identity, "D_BUILD_IDENTITIES_NOT_DISTINCT")
    return install_root, update_environment


async def _stop_lane_service(
    install_root: Path,
    environment: Mapping[str, str],
) -> None:
    python = install_root / ".venv" / "bin" / "python"
    service = install_root / "scripts" / "lifecycle" / "daemon_service.py"
    if not python.is_file() or not service.is_file():
        return
    await _run_bounded_command(
        [str(python), str(service), "stop", "--apply"],
        cwd=install_root,
        environment=environment,
        timeout_seconds=60,
    )


def _require_clean_scenario_machine(context: LifecycleScenarioContext) -> None:
    _require(
        not (Path.home() / ".elefante" / "app" / "current").exists(),
        "NON_ISOLATED_ELEFANTE_PRESENT",
    )
    try:
        service = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/ai.elefante.daemon"],
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise ScenarioFailure("D_SERVICE_PREFLIGHT_UNAVAILABLE") from error
    _require(service.returncode != 0, "NON_ISOLATED_DAEMON_PRESENT")
    try:
        codex = subprocess.run(
            [str(context.codex_executable), "--version"],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ScenarioFailure("D_CODEX_PREFLIGHT_UNAVAILABLE") from error
    _require(
        codex.returncode == 0
        and len(codex.stdout) <= 64 * 1024
        and len(codex.stderr) <= 64 * 1024,
        "D_CODEX_PREFLIGHT_FAILED",
    )


async def run_scenario_d(context: LifecycleScenarioContext) -> set[str]:
    """Prove interruption, live-session recovery, and failed-update rollback."""
    _require_clean_scenario_machine(context)
    _require(
        context.baseline_artifact_path is not None,
        "D_BASELINE_ARTIFACT_REQUIRED",
    )
    candidate_extract = context.scenario_root / "packages" / "candidate"
    baseline_extract = context.scenario_root / "packages" / "baseline"
    with _materialize_package(context.artifact_path, candidate_extract) as candidate_root:
        with _materialize_package(
            context.baseline_artifact_path,
            baseline_extract,
        ) as baseline_root:
            candidate_identity = _package_identity(candidate_root)
            baseline_identity = _package_identity(baseline_root)
            _require(candidate_identity != baseline_identity, "D_BUILD_IDENTITIES_NOT_DISTINCT")

            fresh_install: Path | None = None
            fresh_environment: dict[str, str] | None = None
            update_install: Path | None = None
            update_environment: dict[str, str] | None = None
            try:
                fresh_install, project_alpha, fresh_environment = (
                    await _exercise_interrupted_install(
                        context,
                        candidate_root,
                        candidate_identity,
                    )
                )
                await _exercise_daemon_restart_and_stale_session(
                    fresh_install,
                    project_alpha,
                    fresh_environment,
                )
                await _stop_lane_service(fresh_install, fresh_environment)
                update_install, update_environment = await _exercise_failed_update_rollback(
                    context,
                    candidate_root,
                    candidate_identity,
                    baseline_root,
                    baseline_identity,
                )
            finally:
                if fresh_install is not None and fresh_environment is not None:
                    await _stop_lane_service(fresh_install, fresh_environment)
                if update_install is not None and update_environment is not None:
                    await _stop_lane_service(update_install, update_environment)

    return set(REQUIRED_SCENARIO_CHECKS["D"])


def _recovery_receipt(
    payload: Mapping[str, Any],
    *,
    operation: str,
    required_checks: set[str],
    code: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    receipt = payload.get("receipt")
    checks = receipt.get("checks") if isinstance(receipt, dict) else None
    check_map = {
        str(check.get("name")): check
        for check in checks or []
        if isinstance(check, dict) and isinstance(check.get("name"), str)
    }
    _require(
        _all_receipt_checks_passed(payload)
        and payload.get("recovery_status") == "VERIFIED_COMPLETE"
        and isinstance(receipt, dict)
        and receipt.get("operation") == operation
        and receipt.get("authority") == "user_directed"
        and receipt.get("changed") is True
        and receipt.get("recoverable") is True
        and receipt.get("error_codes") == []
        and receipt.get("next_action") == "none"
        and required_checks.issubset(check_map),
        code,
    )
    return receipt, check_map


def _no_memory_delivery(payload: Mapping[str, Any], anchor: str) -> bool:
    return bool(
        payload.get("status") == "no_match"
        and payload.get("supplied_count") == 0
        and payload.get("abstained") is True
        and payload.get("delivery_blocked") is False
        and payload.get("read_only") is True
        and anchor not in str(payload.get("context") or "")
    )


def _tree_sha256(root: Path) -> str:
    target = Path(root)
    _require(target.is_dir() and not target.is_symlink(), "E_DATA_ROOT_UNSAFE")
    digest = hashlib.sha256()
    for path in sorted(target.rglob("*"), key=lambda item: item.relative_to(target).as_posix()):
        _require(not path.is_symlink(), "E_DATA_TREE_SYMLINK_UNSAFE")
        relative = path.relative_to(target).as_posix().encode("utf-8")
        if path.is_dir():
            digest.update(b"D\0" + relative + b"\0")
            continue
        _require(path.is_file(), "E_DATA_TREE_ENTRY_UNSAFE")
        digest.update(b"F\0" + relative + b"\0")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _canary_snapshot(paths: Sequence[Path]) -> dict[Path, tuple[bytes, int]]:
    return {
        path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        for path in paths
    }


def _require_canaries_unchanged(
    snapshot: Mapping[Path, tuple[bytes, int]],
) -> None:
    _require(
        all(
            path.is_file()
            and not path.is_symlink()
            and path.read_bytes() == expected
            and stat.S_IMODE(path.stat().st_mode) == mode
            for path, (expected, mode) in snapshot.items()
        ),
        "E_CUSTOMER_FILE_CHANGED",
    )


async def _install_exact_candidate(
    *,
    bundle_root: Path,
    install_root: Path,
    identity: Mapping[str, Any],
    environment: Mapping[str, str],
    projects: Sequence[tuple[str, Path]],
    failure_code: str,
) -> None:
    description = await _describe_package_operation(
        bundle_root,
        install_root,
        environment,
    )
    _require(
        description.get("operation") == "install"
        and description.get("requires_confirmation") is False,
        f"{failure_code}_DESCRIPTION_INVALID",
    )
    project_arguments = [
        argument
        for name, root in projects
        for argument in ("--project", f"{name}={root}")
    ]
    result = await _run_bounded_command(
        _package_command(
            bundle_root,
            install_root,
            "--venv-mode",
            "fresh",
            *project_arguments,
        ),
        cwd=bundle_root,
        environment=environment,
    )
    _require(result.returncode == 0, failure_code)
    await _require_ready_product(install_root, identity, environment)


async def _exercise_data_lifecycle(
    context: LifecycleScenarioContext,
    candidate_root: Path,
    candidate_identity: Mapping[str, Any],
) -> None:
    lane = "data-lifecycle"
    home = context.lane_home(lane)
    install_root = context.lane_install_root(lane)
    data_root = context.lane_data_root(lane)
    project_alpha = context.lane_project(lane, "Alpha")
    project_beta = context.lane_project(lane, "Beta")
    project_alpha.mkdir(parents=True, exist_ok=False)
    project_beta.mkdir(parents=True, exist_ok=False)
    environment = _scenario_environment(context, home, scenario="E")
    customer_canaries = (
        home / "Documents" / "customer-owned-scenario-e.txt",
        home / ".codex" / "customer-owned-scenario-e.txt",
    )
    for index, canary in enumerate(customer_canaries, start=1):
        canary.parent.mkdir(parents=True, exist_ok=True)
        _atomic_private_write(
            canary,
            f"customer-owned-{index}-{uuid4().hex}\n".encode("utf-8"),
        )
    canary_state = _canary_snapshot(customer_canaries)
    runtime_context = ScenarioContext(
        artifact_path=context.artifact_path,
        artifact_sha256=context.artifact_sha256,
        install_root=install_root,
        data_root=data_root,
        customer_home=home,
        project_alpha=project_alpha,
        project_beta=project_beta,
        machine_id=context.machine_id,
        output_dir=context.output_dir,
    )

    try:
        await _install_exact_candidate(
            bundle_root=candidate_root,
            install_root=install_root,
            identity=candidate_identity,
            environment=environment,
            projects=(("Alpha", project_alpha), ("Beta", project_beta)),
            failure_code="E_FRESH_INSTALL_FAILED",
        )
        _validate_first_run_receipt(runtime_context)
        project_ids = _strict_project_ids(runtime_context)
        _require_canaries_unchanged(canary_state)

        anchor = f"release-recovery-{uuid4().hex}"
        original = f"{anchor}: the recovery acceptance state is copper."
        changed = f"{anchor}: the recovery acceptance state is violet."
        alpha = MCPBridgeClient(
            install_root,
            project_alpha,
            base_environment=environment,
        )
        try:
            await alpha.start()
            memory_id = await _store_memory(alpha, original)
            initial_recall = await _recall(
                alpha,
                f"What is the recovery acceptance state for {anchor}?",
            )
            _require(
                _recall_supplies(initial_recall, "copper", "violet"),
                "E_INITIAL_RECALL_FAILED",
            )

            backup_preview = await alpha.call_tool(
                "elefante-Recover",
                {"action": "backup"},
            )
            backup_plan = backup_preview.get("plan")
            _require(
                backup_preview.get("success") is True
                and isinstance(backup_plan, dict)
                and backup_plan.get("applicable") is True
                and SHA256_PATTERN.fullmatch(str(backup_plan.get("layout_sha256") or ""))
                is not None
                and Path(str(backup_plan.get("backup_directory") or "")).resolve()
                == data_root.parent / "backups",
                "E_BACKUP_PREVIEW_FAILED",
            )
            backup_result = await alpha.call_tool(
                "elefante-Recover",
                {
                    "action": "backup",
                    "apply": True,
                    "confirm": True,
                    "expected_layout_sha256": backup_plan["layout_sha256"],
                    "invocation_mode": "user_directed",
                },
            )
            backup_receipt, backup_checks = _recovery_receipt(
                backup_result,
                operation="backup",
                required_checks={
                    "archive_readback",
                    "staged_restore",
                    "sqlite_integrity",
                    "kuzu_integrity",
                },
                code="E_BACKUP_VERIFICATION_FAILED",
            )
            archive_name = backup_receipt.get("archive_name")
            archive_sha256 = backup_receipt.get("archive_sha256")
            _require(
                isinstance(archive_name, str)
                and archive_name == Path(archive_name).name
                and isinstance(archive_sha256, str)
                and SHA256_PATTERN.fullmatch(archive_sha256) is not None
                and _sha256_file(data_root.parent / "backups" / archive_name)
                == archive_sha256
                and backup_checks["sqlite_integrity"].get("code") == "SQLITE_OK"
                and backup_checks["kuzu_integrity"].get("code") == "KUZU_OK",
                "E_BACKUP_INTEGRITY_FAILED",
            )

            await _apply_correction(
                alpha,
                memory_id=memory_id,
                correction="edit",
                content=changed,
                question=f"What is the recovery acceptance state for {anchor}?",
                reason="Exact-package Scenario E creates a state newer than its backup.",
            )
            changed_recall = await _recall(
                alpha,
                f"What is the recovery acceptance state for {anchor}?",
            )
            _require(
                _recall_supplies(changed_recall, "violet", "copper"),
                "E_CHANGED_STATE_UNVERIFIED",
            )

            restore_preview = await alpha.call_tool(
                "elefante-Recover",
                {"action": "restore", "archive_name": archive_name},
            )
            restore_plan = restore_preview.get("plan")
            _require(
                restore_preview.get("success") is True
                and isinstance(restore_plan, dict)
                and restore_plan.get("applicable") is True
                and restore_plan.get("archive_name") == archive_name
                and restore_plan.get("archive_sha256") == archive_sha256
                and SHA256_PATTERN.fullmatch(str(restore_plan.get("layout_sha256") or ""))
                is not None,
                "E_RESTORE_PREVIEW_FAILED",
            )
            restore_result = await alpha.call_tool(
                "elefante-Recover",
                {
                    "action": "restore",
                    "archive_name": archive_name,
                    "apply": True,
                    "confirm": True,
                    "expected_layout_sha256": restore_plan["layout_sha256"],
                    "expected_archive_sha256": archive_sha256,
                    "verification_question": (
                        f"What is the recovery acceptance state for {anchor}?"
                    ),
                    "invocation_mode": "user_directed",
                },
            )
            restore_receipt, restore_checks = _recovery_receipt(
                restore_result,
                operation="restore",
                required_checks={
                    "safety_archive_readback",
                    "safety_staged_restore",
                    "safety_sqlite_integrity",
                    "safety_kuzu_integrity",
                    "staged_manifest",
                    "staged_sqlite_integrity",
                    "staged_kuzu_integrity",
                    "active_manifest",
                    "active_sqlite_integrity",
                    "active_kuzu_integrity",
                    "snapshot_refresh",
                    "recall_verification",
                },
                code="E_RESTORE_VERIFICATION_FAILED",
            )
            _require(
                restore_receipt.get("archive_sha256") == archive_sha256
                and all(
                    restore_checks[name].get("code") == expected
                    for name, expected in {
                        "staged_sqlite_integrity": "SQLITE_OK",
                        "staged_kuzu_integrity": "KUZU_OK",
                        "active_sqlite_integrity": "SQLITE_OK",
                        "active_kuzu_integrity": "KUZU_OK",
                        "snapshot_refresh": "SNAPSHOT_REFRESH_OK",
                        "recall_verification": "RECALL_OK",
                    }.items()
                ),
                "E_RESTORE_INTEGRITY_FAILED",
            )
        finally:
            await alpha.close()

        restored_alpha = MCPBridgeClient(
            install_root,
            project_alpha,
            base_environment=environment,
        )
        beta = MCPBridgeClient(
            install_root,
            project_beta,
            base_environment=environment,
        )
        try:
            await restored_alpha.start()
            restored_recall = await _recall(
                restored_alpha,
                f"What is the recovery acceptance state for {anchor}?",
            )
            _require(
                _recall_supplies(restored_recall, "copper", "violet"),
                "E_RESTORED_RECALL_FAILED",
            )
            await beta.start()
            beta_recall = await _recall(
                beta,
                f"What is the recovery acceptance state for {anchor}?",
            )
            _require(
                _no_memory_delivery(beta_recall, anchor),
                "E_PROJECT_ISOLATION_FAILED",
            )
        finally:
            await beta.close()
            await restored_alpha.close()

        _require(
            _strict_project_ids(runtime_context) == project_ids,
            "E_RESTORE_PROJECT_IDS_CHANGED",
        )
        _require_canaries_unchanged(canary_state)
        await _stop_lane_service(install_root, environment)
        data_before_uninstall = _tree_sha256(data_root)

        described = await _run_bounded_command(
            _package_command(candidate_root, install_root, "--describe-uninstall"),
            cwd=candidate_root,
            environment=environment,
        )
        _require(described.returncode == 0, "E_UNINSTALL_DESCRIPTION_FAILED")
        uninstall_plan = _json_from_output(
            described.output,
            code="E_UNINSTALL_DESCRIPTION_INVALID",
        )
        confirmation_token = uninstall_plan.get("confirmation_token")
        _require(
            uninstall_plan.get("available") is True
            and uninstall_plan.get("requires_confirmation") is True
            and uninstall_plan.get("data_effect") == "preserved"
            and uninstall_plan.get("data_present") is True
            and isinstance(confirmation_token, str)
            and SHA256_PATTERN.fullmatch(confirmation_token) is not None,
            "E_UNINSTALL_PLAN_INVALID",
        )
        uninstalled = await _run_bounded_command(
            _package_command(
                candidate_root,
                install_root,
                "--uninstall",
                confirmation_token,
            ),
            cwd=candidate_root,
            environment=environment,
        )
        uninstall_result = _json_from_output(
            uninstalled.output,
            code="E_UNINSTALL_RESULT_INVALID",
        )
        _require(
            uninstalled.returncode == 0
            and uninstall_result.get("success") is True
            and uninstall_result.get("status") == "VERIFIED_COMPLETE"
            and uninstall_result.get("data_preserved") is True
            and uninstall_result.get("backup_verified") is True
            and uninstall_result.get("app_removed") is True
            and not install_root.exists()
            and data_root.is_dir()
            and _tree_sha256(data_root) == data_before_uninstall,
            "E_UNINSTALL_POSTCONDITION_FAILED",
        )
        preservation_path = home / ".elefante" / "data-preservation.json"
        preservation = _read_json(preservation_path)
        _require(
            stat.S_IMODE(preservation_path.stat().st_mode) == 0o600
            and preservation.get("status") == "VERIFIED_COMPLETE"
            and preservation.get("app_removed") is True
            and Path(str(preservation.get("app_root") or "")).resolve()
            == install_root
            and Path(str(preservation.get("data_root") or "")).resolve()
            == data_root,
            "E_DATA_PRESERVATION_RECEIPT_INVALID",
        )
        _require(
            _strict_project_ids(runtime_context) == project_ids,
            "E_UNINSTALL_PROJECT_IDS_CHANGED",
        )
        _require_canaries_unchanged(canary_state)

        await _install_exact_candidate(
            bundle_root=candidate_root,
            install_root=install_root,
            identity=candidate_identity,
            environment=environment,
            projects=(),
            failure_code="E_REINSTALL_FAILED",
        )
        _validate_first_run_receipt(runtime_context)
        _require(
            not preservation_path.exists(),
            "E_DATA_PRESERVATION_RECEIPT_NOT_CONSUMED",
        )
        _require(
            _strict_project_ids(runtime_context) == project_ids,
            "E_REINSTALL_PROJECT_IDS_CHANGED",
        )
        _require_canaries_unchanged(canary_state)

        reinstalled_alpha = MCPBridgeClient(
            install_root,
            project_alpha,
            base_environment=environment,
        )
        reinstalled_beta = MCPBridgeClient(
            install_root,
            project_beta,
            base_environment=environment,
        )
        try:
            await reinstalled_alpha.start()
            reinstalled_recall = await _recall(
                reinstalled_alpha,
                f"What is the recovery acceptance state for {anchor}?",
            )
            _require(
                _recall_supplies(reinstalled_recall, "copper", "violet"),
                "E_REINSTALL_RECALL_FAILED",
            )
            await reinstalled_beta.start()
            beta_recall = await _recall(
                reinstalled_beta,
                f"What is the recovery acceptance state for {anchor}?",
            )
            _require(
                _no_memory_delivery(beta_recall, anchor),
                "E_REINSTALL_PROJECT_ISOLATION_FAILED",
            )
        finally:
            await reinstalled_beta.close()
            await reinstalled_alpha.close()
    finally:
        await _stop_lane_service(install_root, environment)


async def run_scenario_e(context: LifecycleScenarioContext) -> set[str]:
    """Prove backup, restore, uninstall, and reinstall preserve the second brain."""
    _require_clean_scenario_machine(context)
    candidate_extract = context.scenario_root / "packages" / "candidate"
    with _materialize_package(context.artifact_path, candidate_extract) as candidate_root:
        candidate_identity = _package_identity(candidate_root)
        await _exercise_data_lifecycle(
            context,
            candidate_root,
            candidate_identity,
        )
    return set(REQUIRED_SCENARIO_CHECKS["E"])


def write_scenario_receipt(
    context: ScenarioContext | LifecycleScenarioContext,
    scenario: str,
    checks: Sequence[str],
) -> dict[str, Any]:
    required = REQUIRED_SCENARIO_CHECKS.get(scenario)
    _require(required is not None, "SCENARIO_ID_INVALID")
    normalized = sorted(set(checks))
    _require(set(normalized) == set(required), "SCENARIO_CHECK_SET_INCOMPLETE")
    executed_at = datetime.now(timezone.utc).isoformat()
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "scenario": scenario,
        "status": "PASS",
        "artifact_sha256": context.artifact_sha256,
        "executed_at": executed_at,
        "machine_id": context.machine_id,
        "isolation_preflight_passed": True,
        "unattended": True,
        "customer_content_included": False,
        "checks": [
            {"name": name, "passed": True, "code": f"{scenario}_{name.upper()}_VERIFIED"}
            for name in normalized
        ],
    }
    receipt_bytes = (
        json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")
    receipt_path = context.output_dir / SCENARIO_FILE_PATTERN.format(scenario=scenario)
    gate_path = context.output_dir / GATE_FILE_PATTERN.format(scenario=scenario)
    _require(
        not receipt_path.exists() and not gate_path.exists(),
        "SCENARIO_RECEIPT_ALREADY_EXISTS",
    )
    _atomic_private_write(receipt_path, receipt_bytes)
    receipt_sha256 = _sha256_bytes(receipt_bytes)
    gate = {
        "status": "PASS",
        "artifact_sha256": context.artifact_sha256,
        "executed_at": executed_at,
        "receipt_sha256": receipt_sha256,
        "machine_id": context.machine_id,
        "isolation_preflight_passed": True,
        "unattended": True,
        "customer_content_included": False,
        "checks": normalized,
    }
    _atomic_private_write(
        gate_path,
        (json.dumps(gate, sort_keys=True, indent=2) + "\n").encode("utf-8"),
    )
    return gate


def _build_isolated_package_context(
    args: argparse.Namespace,
    *,
    require_baseline: bool,
    error_prefix: str,
) -> LifecycleScenarioContext:
    _require(args.confirm_isolated_machine == CONFIRMATION, "ISOLATED_CONFIRMATION_REQUIRED")
    _require(platform.system() == "Darwin", "CERTIFIED_PLATFORM_REQUIRED")
    _require(platform.machine().casefold() == "arm64", "CERTIFIED_ARCHITECTURE_REQUIRED")
    _require(bool(args.scenario_root), f"{error_prefix}_LIFECYCLE_ARGUMENTS_REQUIRED")

    artifact = _resolved_external_path(
        args.artifact,
        code=f"{error_prefix}_PACKAGE_ARTIFACT_MISSING",
    )
    _require(artifact.is_file(), f"{error_prefix}_PACKAGE_ARTIFACT_MISSING")
    digest = _sha256_file(artifact)
    if args.expected_artifact_sha256 is not None:
        _require(digest == args.expected_artifact_sha256, "ARTIFACT_SHA256_MISMATCH")

    baseline: Path | None = None
    baseline_digest: str | None = None
    if require_baseline:
        _require(bool(args.baseline_artifact), "D_LIFECYCLE_ARGUMENTS_REQUIRED")
        baseline = _resolved_external_path(
            args.baseline_artifact,
            code="D_PACKAGE_ARTIFACT_MISSING",
        )
        _require(baseline.is_file(), "D_PACKAGE_ARTIFACT_MISSING")
        baseline_digest = _sha256_file(baseline)
        _require(digest != baseline_digest, "D_PACKAGE_ARTIFACTS_NOT_DISTINCT")
    else:
        _require(args.baseline_artifact is None, f"{error_prefix}_BASELINE_NOT_ALLOWED")

    scenario_root = _prepare_scenario_root(
        args.scenario_root,
        code=f"{error_prefix}_SCENARIO_ROOT_UNSAFE",
    )
    output = _prepare_evidence_directory(
        args.output_dir,
        scenario_root=scenario_root,
    )
    executable_value = args.codex_executable or shutil.which("codex")
    _require(bool(executable_value), f"{error_prefix}_CODEX_EXECUTABLE_MISSING")
    codex = Path(str(executable_value)).expanduser()
    if not codex.is_absolute():
        codex = Path(shutil.which(str(codex)) or "")
    _require(
        codex.name == "codex" and codex.is_file() and os.access(codex, os.X_OK),
        f"{error_prefix}_CODEX_EXECUTABLE_UNSAFE",
    )
    return LifecycleScenarioContext(
        artifact_path=artifact,
        artifact_sha256=digest,
        scenario_root=scenario_root,
        codex_executable=codex.absolute(),
        machine_id=_safe_uuid(args.machine_id),
        output_dir=output,
        baseline_artifact_path=baseline,
        baseline_artifact_sha256=baseline_digest,
    )


def build_context(args: argparse.Namespace) -> LifecycleScenarioContext:
    """Build the disposable exact-package context for runtime scenarios A/B/C/F."""
    return _build_isolated_package_context(
        args,
        require_baseline=False,
        error_prefix="RUNTIME",
    )


def build_lifecycle_context(args: argparse.Namespace) -> LifecycleScenarioContext:
    return _build_isolated_package_context(
        args,
        require_baseline=True,
        error_prefix="D",
    )


def build_data_lifecycle_context(args: argparse.Namespace) -> LifecycleScenarioContext:
    """Build the isolated exact-package context used only by Scenario E."""
    return _build_isolated_package_context(
        args,
        require_baseline=False,
        error_prefix="E",
    )


def verify_runtime_artifact_identity(context: ScenarioContext) -> None:
    """Bind installed identity and shipped source bytes to the supplied package."""
    if context.bundle_root is not None:
        package_identity = _package_identity(context.bundle_root)
        _verify_installed_payload_matches_package(
            context.bundle_root,
            context.install_root,
        )
    else:
        context.output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".elefante-artifact-identity.",
            dir=context.output_dir,
        ) as temporary_name:
            extraction = Path(temporary_name) / "package"
            with _materialize_package(context.artifact_path, extraction) as bundle_root:
                package_identity = _package_identity(bundle_root)
    installed_identity = _read_json(context.install_root / BUILD_IDENTITY_FILE_NAME)
    _require(
        installed_identity == package_identity,
        "RUNTIME_ARTIFACT_IDENTITY_MISMATCH",
    )


async def run_selected_runtime_scenarios(
    context: ScenarioContext,
    scenarios: Sequence[str],
) -> dict[str, dict[str, Any]]:
    verify_runtime_artifact_identity(context)
    results: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        if scenario == "A":
            checks = await run_scenario_a(context)
        elif scenario == "B":
            checks = await run_scenario_b(context)
        elif scenario == "C":
            checks = await run_scenario_c(context)
        elif scenario == "F":
            checks = await run_scenario_f(context)
        else:
            raise ScenarioFailure("RUNTIME_SCENARIO_UNSUPPORTED")
        results[scenario] = write_scenario_receipt(context, scenario, sorted(checks))
    return results


async def run_runtime_package_scenarios(
    context: LifecycleScenarioContext,
    scenarios: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Install the exact package in one disposable lane, then run A/B/C/F."""
    _require_clean_scenario_machine(context)
    lane = "runtime"
    home = context.lane_home(lane)
    install_root = context.lane_install_root(lane)
    data_root = context.lane_data_root(lane)
    project_alpha = context.lane_project(lane, "Alpha")
    project_beta = context.lane_project(lane, "Beta")
    project_alpha.mkdir(parents=True, exist_ok=False)
    project_beta.mkdir(parents=True, exist_ok=False)
    environment = _scenario_environment(context, home, scenario="runtime")
    candidate_extract = context.scenario_root / "packages" / "candidate"
    with _materialize_package(context.artifact_path, candidate_extract) as bundle_root:
        identity = _package_identity(bundle_root)
        try:
            await _install_exact_candidate(
                bundle_root=bundle_root,
                install_root=install_root,
                identity=identity,
                environment=environment,
                projects=(("Alpha", project_alpha), ("Beta", project_beta)),
                failure_code="RUNTIME_EXACT_PACKAGE_INSTALL_FAILED",
            )
            runtime = ScenarioContext(
                artifact_path=context.artifact_path,
                artifact_sha256=context.artifact_sha256,
                install_root=install_root,
                data_root=data_root,
                customer_home=home,
                project_alpha=project_alpha,
                project_beta=project_beta,
                machine_id=context.machine_id,
                output_dir=context.output_dir,
                scenario_root=context.scenario_root,
                bundle_root=bundle_root,
                codex_executable=context.codex_executable,
                base_environment=environment,
            )
            before_sha256 = _verify_installed_payload_matches_package(
                bundle_root,
                install_root,
            )
            results = await run_selected_runtime_scenarios(runtime, scenarios)
            after_sha256 = _verify_installed_payload_matches_package(
                bundle_root,
                install_root,
            )
            _require(
                after_sha256 == before_sha256,
                "RUNTIME_PAYLOAD_CHANGED_DURING_SCENARIOS",
            )
            return results
        finally:
            await _stop_lane_service(install_root, environment)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run exact-package Elefante runtime scenarios A/B/C/F or isolated "
            "package-lifecycle scenarios D/E."
        )
    )
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--expected-artifact-sha256")
    parser.add_argument(
        "--baseline-artifact",
        help="Distinct known-good compatible package used only by Scenario D.",
    )
    parser.add_argument(
        "--scenario-root",
        required=True,
        help="Nonexistent disposable root; every mutable package and runtime path is derived below it.",
    )
    parser.add_argument(
        "--codex-executable",
        help="Exact certified Codex executable; defaults to the first codex on PATH.",
    )
    parser.add_argument("--machine-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--scenario",
        action="append",
        choices=("A", "B", "C", "D", "E", "F"),
        dest="scenarios",
        help="Scenario to run; repeat as needed. Defaults to A, B, C, and F.",
    )
    parser.add_argument(
        "--confirm-isolated-machine",
        required=True,
        help=f"Must be {CONFIRMATION}; never run this against customer data.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        scenarios = args.scenarios or ["A", "B", "C", "F"]
        if any(scenario in {"D", "E"} for scenario in scenarios):
            _require(len(scenarios) == 1, "LIFECYCLE_SCENARIO_MUST_RUN_ALONE")
            scenario = scenarios[0]
            if scenario == "D":
                context: ScenarioContext | LifecycleScenarioContext = (
                    build_lifecycle_context(args)
                )
                checks = asyncio.run(run_scenario_d(context))
            else:
                context = build_data_lifecycle_context(args)
                checks = asyncio.run(run_scenario_e(context))
            results = {
                scenario: write_scenario_receipt(context, scenario, sorted(checks))
            }
        else:
            context = build_context(args)
            results = asyncio.run(run_runtime_package_scenarios(context, scenarios))
    except ScenarioFailure as error:
        print(json.dumps({"status": "FAIL", "error_code": error.code}, sort_keys=True))
        return 1
    except (OSError, asyncio.TimeoutError):
        print(
            json.dumps(
                {"status": "FAIL", "error_code": "SCENARIO_RUNTIME_UNAVAILABLE"},
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": "PASS",
                "artifact_sha256": context.artifact_sha256,
                "scenarios": results,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
