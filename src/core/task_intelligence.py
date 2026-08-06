"""Deterministic, shadow-only Task Brief generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Sequence
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.models.memory import Memory, MemoryStatus, MemoryType
from src.models.query import QueryMode, SearchFilters, SearchResult
from src.utils.token_counter import estimate_tokens


class TaskStage(str, Enum):
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"


class TaskBriefProfile(str, Enum):
    V1 = "v1"
    V2 = "v2"


class EvidenceRole(str, Enum):
    CONSTRAINT = "constraint"
    DECISION = "decision"
    DEPENDENCY = "dependency"
    FAILURE = "failure"
    SAFEGUARD = "safeguard"
    IMPLEMENTATION = "implementation"
    CONTEXT = "context"


class TaskBriefBudget(BaseModel):
    total_tokens: int = Field(default=1500, ge=1, le=1500)
    planning_tokens: int = Field(default=450, ge=1)
    execution_tokens: int = Field(default=750, ge=1)
    validation_tokens: int = Field(default=300, ge=1)
    max_evidence_items: int = Field(default=8, ge=1, le=8)
    max_graph_hops: int = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def validate_stage_total(self) -> "TaskBriefBudget":
        stage_total = (
            self.planning_tokens + self.execution_tokens + self.validation_tokens
        )
        if stage_total != self.total_tokens:
            raise ValueError("Task Brief stage budgets must equal total_tokens")
        return self

    def for_stage(self, stage: TaskStage) -> int:
        return {
            TaskStage.PLANNING: self.planning_tokens,
            TaskStage.EXECUTION: self.execution_tokens,
            TaskStage.VALIDATION: self.validation_tokens,
        }[stage]


class TaskBriefRequest(BaseModel):
    task_id: str | None = Field(default=None, max_length=240)
    task: str = Field(min_length=1, max_length=4000)
    success_criteria: list[str] = Field(default_factory=list, max_length=20)
    project: str | None = Field(default=None, max_length=240)
    workspace: str | None = Field(default=None, max_length=1000)
    profile: TaskBriefProfile = TaskBriefProfile.V1
    stage: TaskStage | None = None
    budget: TaskBriefBudget = Field(default_factory=TaskBriefBudget)


class TaskBriefEvidence(BaseModel):
    memory_id: str
    stage: TaskStage
    content_excerpt: str
    truncated: bool
    retrieval_score: float
    source: str
    source_detail: str
    source_reliability: float
    verified: bool
    project: str | None = None
    workspace: str | None = None
    file_path: str | None = None
    line_number: int | None = None
    graph_hop: int = Field(ge=0, le=1)
    relationship_path: list[str] = Field(default_factory=list)
    role: EvidenceRole = EvidenceRole.CONTEXT
    reason_selected: str = "legacy score ordering"
    conflict_ids: list[str] = Field(default_factory=list)
    retrieval_signals: dict[str, Any] = Field(default_factory=dict)


class TaskBriefConflict(BaseModel):
    memory_id: str
    related_memory_ids: list[str]
    reason: str


class TaskBriefOmission(BaseModel):
    memory_id: str
    reason: str


class TaskBriefPacket(BaseModel):
    stage: TaskStage
    evidence: list[TaskBriefEvidence]
    rendered_context: str
    estimated_tokens: int
    token_budget: int


class TaskBrief(BaseModel):
    profile: TaskBriefProfile = TaskBriefProfile.V1
    task_id: str | None = None
    task_summary: str = ""
    success_criteria: list[str] = Field(default_factory=list)
    shadow_mode: bool = True
    packets: list[TaskBriefPacket]
    conflicts: list[TaskBriefConflict]
    omissions: list[TaskBriefOmission]
    selected_memory_ids: list[str]
    rendered_context: str
    estimated_tokens: int
    token_budget: int
    mutated_memory_count: int = 0
    abstained: bool = False
    abstention_reason: str | None = None


@dataclass(frozen=True)
class _RankedEvidence:
    result: SearchResult
    graph_hop: int
    role: EvidenceRole = EvidenceRole.CONTEXT
    stage: TaskStage = TaskStage.EXECUTION
    actionability_score: float = 0.0
    reason_selected: str = ""
    retrieval_signals: dict[str, Any] | None = None


class TaskBriefCompiler:
    """Pure compiler that never reads from or writes to a memory store."""

    MIN_RELIABILITY = 0.5
    MIN_RETRIEVAL_SCORE = 0.3
    _VALIDATION_MARKERS = (
        "acceptance",
        "assert",
        "guard",
        "regression",
        "safeguard",
        "test",
        "validate",
        "verify",
    )
    _PLANNING_MARKERS = (
        "architecture",
        "constraint",
        "decision",
        "design",
        "preference",
        "requirement",
        "specification",
    )
    _TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}")
    _STOP_WORDS = frozenset(
        {
            "about",
            "after",
            "against",
            "also",
            "before",
            "being",
            "from",
            "have",
            "into",
            "make",
            "must",
            "only",
            "should",
            "that",
            "their",
            "then",
            "this",
            "through",
            "using",
            "when",
            "where",
            "while",
            "with",
        }
    )
    _SOURCE_SUFFIXES = frozenset(
        {
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".sh",
            ".ps1",
            ".swift",
            ".toml",
            ".yaml",
            ".yml",
        }
    )
    _ALLOWED_GRAPH_RELATIONSHIPS = frozenset(
        {"BLOCKS", "DEPENDS_ON", "ENFORCES", "GOVERNS", "SUPERSEDES"}
    )

    def compile(
        self,
        request: TaskBriefRequest,
        candidates: Sequence[SearchResult],
    ) -> TaskBrief:
        if request.profile == TaskBriefProfile.V2:
            return self._compile_v2(request, candidates)
        ranked = self._rank_candidates(candidates)
        eligible: list[_RankedEvidence] = []
        omissions: list[TaskBriefOmission] = []
        conflicts: list[TaskBriefConflict] = []

        for item in ranked:
            memory = item.result.memory
            reason = self._exclusion_reason(request, item.result)
            if reason:
                omissions.append(
                    TaskBriefOmission(memory_id=str(memory.id), reason=reason)
                )
                continue
            eligible.append(item)
            conflict = self._conflict(memory)
            if conflict is not None:
                conflicts.append(conflict)

        selected = eligible[: request.budget.max_evidence_items]
        for item in eligible[request.budget.max_evidence_items :]:
            omissions.append(
                TaskBriefOmission(
                    memory_id=str(item.result.memory.id),
                    reason="max-evidence-items",
                )
            )

        by_stage: dict[TaskStage, list[_RankedEvidence]] = {
            stage: [] for stage in TaskStage
        }
        for item in selected:
            by_stage[self._stage_for(item.result.memory)].append(item)

        packets: list[TaskBriefPacket] = []
        delivered_ids: list[str] = []
        for stage in TaskStage:
            packet, packet_omissions = self._build_packet(
                stage,
                by_stage[stage],
                request.budget.for_stage(stage),
            )
            packets.append(packet)
            omissions.extend(packet_omissions)
            delivered_ids.extend(evidence.memory_id for evidence in packet.evidence)

        rendered = "\n\n".join(
            packet.rendered_context for packet in packets if packet.rendered_context
        )
        estimated_tokens = estimate_tokens(rendered)
        return TaskBrief(
            profile=request.profile,
            task_id=request.task_id,
            task_summary=request.task,
            success_criteria=request.success_criteria,
            packets=packets,
            conflicts=sorted(conflicts, key=lambda item: item.memory_id),
            omissions=sorted(
                omissions,
                key=lambda item: (item.memory_id, item.reason),
            ),
            selected_memory_ids=delivered_ids,
            rendered_context=rendered,
            estimated_tokens=estimated_tokens,
            token_budget=request.budget.total_tokens,
        )

    def _compile_v2(
        self,
        request: TaskBriefRequest,
        candidates: Sequence[SearchResult],
    ) -> TaskBrief:
        ranked = self._rank_candidates_v2(request, candidates)
        eligible: list[_RankedEvidence] = []
        omissions: list[TaskBriefOmission] = []
        conflicts: list[TaskBriefConflict] = []

        for item in ranked:
            memory = item.result.memory
            reason = self._exclusion_reason(request, item.result)
            if reason:
                omissions.append(
                    TaskBriefOmission(memory_id=str(memory.id), reason=reason)
                )
                continue
            conflict = self._conflict(memory)
            if conflict is not None:
                conflicts.append(conflict)
                omissions.append(
                    TaskBriefOmission(
                        memory_id=str(memory.id),
                        reason="unresolved-conflict",
                    )
                )
                continue
            if not self._is_actionable(item):
                omissions.append(
                    TaskBriefOmission(
                        memory_id=str(memory.id),
                        reason="insufficient-independent-relevance",
                    )
                )
                continue
            eligible.append(item)

        by_stage: dict[TaskStage, list[_RankedEvidence]] = {
            stage: [] for stage in TaskStage
        }
        for item in eligible:
            by_stage[request.stage or item.stage].append(item)

        packets: list[TaskBriefPacket] = []
        delivered_ids: list[str] = []
        remaining_slots = request.budget.max_evidence_items
        for stage in TaskStage:
            packet, packet_omissions = self._build_packet(
                stage,
                by_stage[stage][:remaining_slots],
                request.budget.for_stage(stage),
            )
            packets.append(packet)
            omissions.extend(packet_omissions)
            delivered = [evidence.memory_id for evidence in packet.evidence]
            delivered_ids.extend(delivered)
            remaining_slots -= len(delivered)

        delivered = set(delivered_ids)
        for item in eligible:
            memory_id = str(item.result.memory.id)
            if memory_id not in delivered and not any(
                omission.memory_id == memory_id for omission in omissions
            ):
                omissions.append(
                    TaskBriefOmission(memory_id=memory_id, reason="max-evidence-items")
                )

        evidence_context = "\n\n".join(
            packet.rendered_context for packet in packets if packet.rendered_context
        )
        abstained = not delivered_ids
        if abstained:
            rendered = "ELEFANTE TASK BRIEF\nABSTAIN: no evidence met the independent relevance gate."
        else:
            criteria = "\n".join(f"- {item}" for item in request.success_criteria)
            preamble = ["ELEFANTE TASK BRIEF", f"Task: {request.task}"]
            if criteria:
                preamble.extend(["Success criteria:", criteria])
            rendered = "\n".join([*preamble, "", evidence_context])
        return TaskBrief(
            profile=request.profile,
            task_id=request.task_id,
            task_summary=request.task,
            success_criteria=request.success_criteria,
            packets=packets,
            conflicts=sorted(conflicts, key=lambda item: item.memory_id),
            omissions=sorted(omissions, key=lambda item: (item.memory_id, item.reason)),
            selected_memory_ids=delivered_ids,
            rendered_context=rendered,
            estimated_tokens=estimate_tokens(rendered),
            token_budget=request.budget.total_tokens,
            abstained=abstained,
            abstention_reason=(
                "no evidence met the independent relevance gate" if abstained else None
            ),
        )

    def _rank_candidates_v2(
        self,
        request: TaskBriefRequest,
        candidates: Sequence[SearchResult],
    ) -> list[_RankedEvidence]:
        unique: dict[str, _RankedEvidence] = {}
        query_terms = self._terms(" ".join([request.task, *request.success_criteria]))
        for result in candidates:
            memory = result.memory
            memory_id = str(memory.id)
            content_terms = self._terms(
                " ".join([memory.content, memory.metadata.summary or ""])
            )
            path_terms = self._terms(memory.metadata.file_path or "")
            custom = memory.metadata.custom_metadata or {}
            symbol_terms = self._terms(str(custom.get("symbol", "")))
            lexical = self._overlap(query_terms, content_terms)
            path = self._focused_overlap(query_terms, path_terms)
            symbol = self._focused_overlap(query_terms, symbol_terms)
            relationships = [
                str(item).upper() for item in result.relationship_path or []
            ]
            dependency = float(
                any(item in self._ALLOWED_GRAPH_RELATIONSHIPS for item in relationships)
            )
            source_code = float(self._is_source_code(memory.metadata.file_path))
            semantic = float(
                result.vector_score if result.vector_score is not None else result.score
            )
            role = self._role_for(memory, relationships)
            stage = self._stage_for_role(role)
            role_value = 1.0 if role != EvidenceRole.CONTEXT else 0.0
            actionability = min(
                1.0,
                0.35 * semantic
                + 0.25 * lexical
                + 0.15 * max(path, symbol)
                + 0.15 * max(source_code, dependency)
                + 0.10 * role_value,
            )
            signals = {
                "semantic": round(semantic, 6),
                "lexical": round(lexical, 6),
                "path": round(path, 6),
                "symbol": round(symbol, 6),
                "dependency": dependency,
                "source_code": source_code,
                "actionability": round(actionability, 6),
            }
            positive_signals = [
                name
                for name in ("lexical", "path", "symbol", "dependency", "source_code")
                if float(signals[name]) > 0
            ]
            reason = (
                f"{role.value}; signals={','.join(positive_signals) or 'semantic-only'}; "
                f"actionability={actionability:.3f}"
            )
            ranked = _RankedEvidence(
                result=result,
                graph_hop=1 if result.source == "graph-hop" else 0,
                role=role,
                stage=stage,
                actionability_score=actionability,
                reason_selected=reason,
                retrieval_signals=signals,
            )
            current = unique.get(memory_id)
            if (
                current is None
                or ranked.actionability_score > current.actionability_score
            ):
                unique[memory_id] = ranked
        return sorted(
            unique.values(),
            key=lambda item: (
                -item.actionability_score,
                -item.result.memory.metadata.source_reliability,
                -int(item.result.memory.metadata.verified),
                str(item.result.memory.id),
            ),
        )

    def _is_actionable(self, item: _RankedEvidence) -> bool:
        signals = item.retrieval_signals or {}
        independent = sum(
            (
                float(signals.get("semantic", 0.0)) >= 0.55,
                float(signals.get("lexical", 0.0)) > 0.0,
                float(signals.get("path", 0.0)) > 0.0,
                float(signals.get("symbol", 0.0)) > 0.0,
                float(signals.get("dependency", 0.0)) > 0.0,
                item.role
                in {
                    EvidenceRole.CONSTRAINT,
                    EvidenceRole.DECISION,
                    EvidenceRole.FAILURE,
                    EvidenceRole.SAFEGUARD,
                },
            )
        )
        action_anchor = (
            float(signals.get("path", 0.0)) > 0.0
            or float(signals.get("symbol", 0.0)) > 0.0
            or float(signals.get("dependency", 0.0)) > 0.0
            or item.role
            in {
                EvidenceRole.CONSTRAINT,
                EvidenceRole.DECISION,
                EvidenceRole.FAILURE,
                EvidenceRole.SAFEGUARD,
            }
        )
        return independent >= 2 and action_anchor and item.actionability_score >= 0.3

    @classmethod
    def _terms(cls, value: str) -> set[str]:
        terms: set[str] = set()
        for raw in cls._TOKEN_PATTERN.findall(value):
            for part in (
                re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw).replace("-", "_").split("_")
            ):
                term = part.casefold()
                if len(term) >= 3 and term not in cls._STOP_WORDS:
                    terms.add(term)
                    if term.endswith("ies") and len(term) > 4:
                        terms.add(term[:-3] + "y")
                    elif (
                        term.endswith("s")
                        and len(term) > 4
                        and not term.endswith(("ss", "us"))
                    ):
                        terms.add(term[:-1])
        return terms

    @staticmethod
    def _overlap(query_terms: set[str], evidence_terms: set[str]) -> float:
        if not query_terms or not evidence_terms:
            return 0.0
        return len(query_terms & evidence_terms) / len(query_terms)

    @classmethod
    def _focused_overlap(cls, query_terms: set[str], evidence_terms: set[str]) -> float:
        """Reward a focused path or symbol without relying on task-specific aliases."""
        return max(
            cls._overlap(query_terms, evidence_terms),
            cls._overlap(evidence_terms, query_terms),
        )

    def _is_source_code(self, file_path: str | None) -> bool:
        return bool(
            file_path
            and PurePosixPath(file_path).suffix.casefold() in self._SOURCE_SUFFIXES
        )

    def _role_for(self, memory: Memory, relationships: Sequence[str]) -> EvidenceRole:
        custom_role = str(
            (memory.metadata.custom_metadata or {}).get("evidence_role", "")
        )
        if custom_role in {role.value for role in EvidenceRole}:
            return EvidenceRole(custom_role)
        memory_type = str(memory.metadata.memory_type).casefold()
        if memory_type == MemoryType.DECISION.value:
            return EvidenceRole.DECISION
        if memory_type in {MemoryType.DIRECTIVE.value, MemoryType.SPECIFICATION.value}:
            return EvidenceRole.CONSTRAINT
        if any(item in self._ALLOWED_GRAPH_RELATIONSHIPS for item in relationships):
            return EvidenceRole.DEPENDENCY
        searchable = " ".join(
            [memory.content, memory.metadata.summary or ""]
        ).casefold()
        if re.search(
            r"\b(root cause|failed|failure|regression|incident|postmortem)\b",
            searchable,
        ):
            return EvidenceRole.FAILURE
        if re.search(
            r"\b(assert|guard|safeguard|validate|verification|verify)\b", searchable
        ):
            return EvidenceRole.SAFEGUARD
        if self._is_source_code(memory.metadata.file_path):
            return EvidenceRole.IMPLEMENTATION
        return EvidenceRole.CONTEXT

    @staticmethod
    def _stage_for_role(role: EvidenceRole) -> TaskStage:
        if role in {EvidenceRole.CONSTRAINT, EvidenceRole.DECISION}:
            return TaskStage.PLANNING
        if role == EvidenceRole.SAFEGUARD:
            return TaskStage.VALIDATION
        return TaskStage.EXECUTION

    def _rank_candidates(
        self,
        candidates: Sequence[SearchResult],
    ) -> list[_RankedEvidence]:
        unique: dict[str, _RankedEvidence] = {}
        for result in candidates:
            memory_id = str(result.memory.id)
            hop = 1 if result.source == "graph-hop" else 0
            current = unique.get(memory_id)
            if current is None or result.score > current.result.score:
                unique[memory_id] = _RankedEvidence(result=result, graph_hop=hop)
        return sorted(
            unique.values(),
            key=lambda item: (
                -item.result.score,
                -item.result.memory.metadata.source_reliability,
                -int(item.result.memory.metadata.verified),
                str(item.result.memory.id),
            ),
        )

    def _exclusion_reason(
        self,
        request: TaskBriefRequest,
        result: SearchResult,
    ) -> str | None:
        metadata = result.memory.metadata
        status = str(metadata.status).casefold()
        if metadata.deprecated or status == MemoryStatus.DEPRECATED.value:
            return "deprecated"
        if metadata.archived or status == MemoryStatus.ARCHIVED.value:
            return "archived"
        if metadata.superseded_by_id is not None:
            return "superseded"
        if metadata.source_reliability < self.MIN_RELIABILITY:
            return "low-source-reliability"
        if result.score < self.MIN_RETRIEVAL_SCORE:
            return "low-retrieval-score"
        if request.project and metadata.project and metadata.project != request.project:
            return "cross-project"
        if (
            request.workspace
            and metadata.workspace
            and metadata.workspace != request.workspace
        ):
            return "cross-workspace"
        return None

    def _stage_for(self, memory: Memory) -> TaskStage:
        metadata = memory.metadata
        searchable = " ".join(
            [
                memory.content,
                metadata.summary or "",
                " ".join(metadata.concepts),
                " ".join(metadata.tags),
            ]
        ).casefold()
        if any(marker in searchable for marker in self._VALIDATION_MARKERS):
            return TaskStage.VALIDATION
        memory_type = str(metadata.memory_type).casefold()
        planning_types = {
            MemoryType.DECISION.value,
            MemoryType.DIRECTIVE.value,
            MemoryType.PREFERENCE.value,
            MemoryType.SPECIFICATION.value,
        }
        if memory_type in planning_types or any(
            marker in searchable for marker in self._PLANNING_MARKERS
        ):
            return TaskStage.PLANNING
        return TaskStage.EXECUTION

    def _conflict(self, memory: Memory) -> TaskBriefConflict | None:
        metadata = memory.metadata
        status = str(metadata.status).casefold()
        related = sorted(str(memory_id) for memory_id in metadata.conflict_ids)
        if related:
            return TaskBriefConflict(
                memory_id=str(memory.id),
                related_memory_ids=related,
                reason="stored-conflict-relationship",
            )
        if status == MemoryStatus.CONTRADICTORY.value:
            return TaskBriefConflict(
                memory_id=str(memory.id),
                related_memory_ids=[],
                reason="contradictory-status",
            )
        return None

    def _build_packet(
        self,
        stage: TaskStage,
        items: Sequence[_RankedEvidence],
        token_budget: int,
    ) -> tuple[TaskBriefPacket, list[TaskBriefOmission]]:
        header = f"{stage.value.upper()} EVIDENCE"
        lines = [header]
        evidence: list[TaskBriefEvidence] = []
        omissions: list[TaskBriefOmission] = []
        for item in items:
            line, excerpt, truncated = self._fit_line(
                item,
                lines,
                token_budget,
            )
            memory_id = str(item.result.memory.id)
            if line is None:
                omissions.append(
                    TaskBriefOmission(memory_id=memory_id, reason="stage-token-budget")
                )
                continue
            lines.append(line)
            metadata = item.result.memory.metadata
            evidence.append(
                TaskBriefEvidence(
                    memory_id=memory_id,
                    stage=stage,
                    content_excerpt=excerpt,
                    truncated=truncated,
                    retrieval_score=round(item.result.score, 6),
                    source=str(metadata.source),
                    source_detail=metadata.source_detail,
                    source_reliability=metadata.source_reliability,
                    verified=metadata.verified,
                    project=metadata.project,
                    workspace=metadata.workspace,
                    file_path=metadata.file_path,
                    line_number=metadata.line_number,
                    graph_hop=item.graph_hop,
                    relationship_path=item.result.relationship_path or [],
                    role=item.role,
                    reason_selected=item.reason_selected or "legacy score ordering",
                    conflict_ids=sorted(
                        str(conflict_id)
                        for conflict_id in item.result.memory.metadata.conflict_ids
                    ),
                    retrieval_signals=item.retrieval_signals or {},
                )
            )
        rendered = "\n".join(lines) if evidence else ""
        return (
            TaskBriefPacket(
                stage=stage,
                evidence=evidence,
                rendered_context=rendered,
                estimated_tokens=estimate_tokens(rendered),
                token_budget=token_budget,
            ),
            omissions,
        )

    def _fit_line(
        self,
        item: _RankedEvidence,
        existing_lines: Sequence[str],
        token_budget: int,
    ) -> tuple[str | None, str, bool]:
        memory = item.result.memory
        metadata = memory.metadata
        provenance = f"source={metadata.source}:{metadata.source_detail}"
        if metadata.verified:
            provenance += "; verified"
        if metadata.file_path:
            provenance += f"; file={metadata.file_path}"
            if metadata.line_number is not None:
                provenance += f":{metadata.line_number}"
        if item.graph_hop:
            provenance += "; graph-hop=1"
        if item.retrieval_signals is None:
            prefix = f"- [{memory.id}] "
        else:
            role = item.role.value if item.role else EvidenceRole.CONTEXT.value
            reason = item.reason_selected or "legacy score ordering"
            prefix = f"- [{memory.id}] role={role}; why={reason} :: "
        suffix = f" | {provenance}; score={item.result.score:.3f}"

        def render(content: str) -> str:
            return prefix + content + suffix

        def fits(line: str) -> bool:
            return estimate_tokens("\n".join([*existing_lines, line])) <= token_budget

        content = " ".join(memory.content.split())
        full = render(content)
        if fits(full):
            return full, content, False
        low = 0
        high = len(content)
        best = ""
        while low <= high:
            middle = (low + high) // 2
            excerpt = content[:middle].rstrip() + "..."
            if fits(render(excerpt)):
                best = excerpt
                low = middle + 1
            else:
                high = middle - 1
        if len(best.removesuffix("...")) < 40:
            return None, "", False
        return render(best), best, True


class TaskBriefService:
    """Read-only adapter over the existing orchestrator and one-hop graph."""

    def __init__(self, orchestrator) -> None:
        self.orchestrator = orchestrator
        self.compiler = TaskBriefCompiler()

    async def generate(self, request: TaskBriefRequest) -> TaskBrief:
        filters = SearchFilters(
            project=request.project,
            include_conversation=False,
            include_stored=True,
        )
        query = request.task
        if request.profile == TaskBriefProfile.V2 and request.success_criteria:
            query = "\n".join([request.task, *request.success_criteria])
        results = await self.orchestrator.search_memories(
            query,
            mode=QueryMode.HYBRID,
            limit=max(16, request.budget.max_evidence_items * 2),
            filters=filters,
            include_conversation=False,
            include_stored=True,
            apply_temporal_decay=False,
            reinforce_access=False,
        )
        graph_results = await self._one_hop_results(
            results[: request.budget.max_evidence_items],
            request=request,
        )
        return self.compiler.compile(request, [*results, *graph_results])

    async def _one_hop_results(
        self,
        seeds: Sequence[SearchResult],
        *,
        request: TaskBriefRequest | None = None,
    ) -> list[SearchResult]:
        discovered: dict[str, SearchResult] = {}
        seed_ids = {str(seed.memory.id) for seed in seeds}
        for seed in seeds:
            try:
                relationships = await self.orchestrator.graph_store.get_relationships(
                    seed.memory.id,
                    direction="both",
                )
            except Exception:
                relationships = []
            for relationship in relationships:
                relationship_name = relationship.relationship_type.value
                if (
                    request is not None
                    and request.profile == TaskBriefProfile.V2
                    and relationship_name
                    not in self.compiler._ALLOWED_GRAPH_RELATIONSHIPS
                ):
                    continue
                other_id: UUID
                if relationship.from_entity_id == seed.memory.id:
                    other_id = relationship.to_entity_id
                else:
                    other_id = relationship.from_entity_id
                if str(other_id) in seed_ids or str(other_id) in discovered:
                    continue
                memory = await self.orchestrator.vector_store.get_memory(other_id)
                if memory is None:
                    continue
                if request is not None and request.profile == TaskBriefProfile.V2:
                    if (
                        request.project
                        and memory.metadata.project
                        and memory.metadata.project != request.project
                    ):
                        continue
                    if (
                        request.workspace
                        and memory.metadata.workspace
                        and memory.metadata.workspace != request.workspace
                    ):
                        continue
                score = max(0.0, min(1.0, seed.score * relationship.strength))
                discovered[str(other_id)] = SearchResult(
                    memory=memory,
                    score=score,
                    source="graph-hop",
                    graph_score=relationship.strength,
                    matched_entities=[seed.memory.id],
                    relationship_path=[relationship_name],
                )
        return [discovered[key] for key in sorted(discovered)]
