"""Deterministic, shadow-only Task Brief generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.models.memory import Memory, MemoryStatus, MemoryType
from src.models.query import QueryMode, SearchFilters, SearchResult
from src.utils.token_counter import estimate_tokens


class TaskStage(str, Enum):
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"


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
            self.planning_tokens
            + self.execution_tokens
            + self.validation_tokens
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
    task: str = Field(min_length=1, max_length=4000)
    success_criteria: list[str] = Field(default_factory=list, max_length=20)
    project: str | None = Field(default=None, max_length=240)
    workspace: str | None = Field(default=None, max_length=1000)
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
    shadow_mode: bool = True
    packets: list[TaskBriefPacket]
    conflicts: list[TaskBriefConflict]
    omissions: list[TaskBriefOmission]
    selected_memory_ids: list[str]
    rendered_context: str
    estimated_tokens: int
    token_budget: int
    mutated_memory_count: int = 0


@dataclass(frozen=True)
class _RankedEvidence:
    result: SearchResult
    graph_hop: int


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

    def compile(
        self,
        request: TaskBriefRequest,
        candidates: Sequence[SearchResult],
    ) -> TaskBrief:
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
        if request.workspace and metadata.workspace and metadata.workspace != request.workspace:
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
        prefix = f"- [{memory.id}] "
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
        results = await self.orchestrator.search_memories(
            request.task,
            mode=QueryMode.HYBRID,
            limit=max(16, request.budget.max_evidence_items * 2),
            filters=filters,
            include_conversation=False,
            include_stored=True,
            apply_temporal_decay=False,
            reinforce_access=False,
        )
        graph_results = await self._one_hop_results(
            results[: request.budget.max_evidence_items]
        )
        return self.compiler.compile(request, [*results, *graph_results])

    async def _one_hop_results(
        self,
        seeds: Sequence[SearchResult],
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
                score = max(0.0, min(1.0, seed.score * relationship.strength))
                discovered[str(other_id)] = SearchResult(
                    memory=memory,
                    score=score,
                    source="graph-hop",
                    graph_score=relationship.strength,
                    matched_entities=[seed.memory.id],
                    relationship_path=[relationship.relationship_type.value],
                )
        return [discovered[key] for key in sorted(discovered)]
