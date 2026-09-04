"""Deterministic, shadow-only Task Brief generation."""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Sequence
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.core.governance import governance_reason, is_mandatory
from src.core.retrieval import CognitiveRetriever
from src.models.memory import InjectionPolicy, Memory, MemoryStatus, MemoryType
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


class CurrentSourceState(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNAVAILABLE = "unavailable"


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
    success_criteria: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        default_factory=list, max_length=20
    )
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
    current_source_state: CurrentSourceState = CurrentSourceState.UNAVAILABLE


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
    delivery_blocked: bool = False
    governance_warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _RankedEvidence:
    result: SearchResult
    graph_hop: int
    role: EvidenceRole = EvidenceRole.CONTEXT
    stage: TaskStage = TaskStage.EXECUTION
    actionability_score: float = 0.0
    reason_selected: str = ""
    retrieval_signals: dict[str, Any] | None = None
    mandatory: bool = False


class TaskBriefCompiler:
    """Pure compiler that never reads from or writes to a memory store."""

    MIN_RELIABILITY = 0.5
    MIN_RETRIEVAL_SCORE = 0.3
    MIN_ROLE_ANCHOR_COVERAGE = 0.20
    MIN_GOVERNING_DIRECTIVE_SEMANTIC = 0.85
    MIN_RECALL_CUE_SIMILARITY = 0.93
    MIN_FOCUSED_CUE_SIMILARITY = 0.85
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
            "all",
            "and",
            "any",
            "about",
            "after",
            "against",
            "also",
            "are",
            "before",
            "been",
            "being",
            "can",
            "does",
            "each",
            "for",
            "from",
            "had",
            "has",
            "have",
            "instead",
            "into",
            "its",
            "make",
            "most",
            "must",
            "not",
            "only",
            "other",
            "our",
            "over",
            "should",
            "that",
            "than",
            "the",
            "their",
            "then",
            "this",
            "through",
            "under",
            "using",
            "was",
            "when",
            "where",
            "while",
            "will",
            "without",
            "with",
            "within",
            "were",
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

    @staticmethod
    def _source_identity(item: _RankedEvidence) -> str:
        """Return a stable source boundary for evidence portfolio diversity."""
        metadata = item.result.memory.metadata
        return (
            metadata.file_path or metadata.source_detail or str(item.result.memory.id)
        )

    def _diversify_sources(
        self, items: Sequence[_RankedEvidence]
    ) -> list[_RankedEvidence]:
        """Prefer one item per source before taking a second chunk from a source."""
        first: list[_RankedEvidence] = []
        repeated: list[_RankedEvidence] = []
        seen: set[str] = set()
        for item in items:
            identity = self._source_identity(item)
            if identity in seen:
                repeated.append(item)
                continue
            seen.add(identity)
            first.append(item)
        return [*first, *repeated]

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
        preamble = self._render_preamble(request)
        if estimate_tokens(preamble) + 12 >= request.budget.total_tokens:
            return self._blocked_v2_brief(
                request,
                candidates,
                reason="task-contract-exceeds-token-budget",
                warning=(
                    "Task statement and success criteria exceed the hard Task Brief "
                    "budget; no memory was delivered."
                ),
            )

        ranked = self._rank_candidates_v2(request, candidates)
        eligible: list[_RankedEvidence] = []
        omissions: list[TaskBriefOmission] = []
        conflicts: list[TaskBriefConflict] = []
        mandatory_governance_failures: list[TaskBriefOmission] = []

        for item in ranked:
            memory = item.result.memory
            reason = self._exclusion_reason(request, item.result)
            if reason:
                omission = TaskBriefOmission(memory_id=str(memory.id), reason=reason)
                omissions.append(omission)
                if item.mandatory and reason in {
                    "current-source-contradicted",
                    "privacy-redaction",
                }:
                    mandatory_governance_failures.append(omission)
                continue
            conflict = self._conflict(memory)
            if conflict is not None:
                conflicts.append(conflict)
                omission = TaskBriefOmission(
                    memory_id=str(memory.id),
                    reason="unresolved-conflict",
                )
                omissions.append(omission)
                if item.mandatory:
                    mandatory_governance_failures.append(omission)
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

        if mandatory_governance_failures:
            return self._blocked_v2_brief(
                request,
                candidates,
                reason="mandatory-governance-conflict",
                warning=(
                    "Required user-locked evidence conflicts with current source, "
                    "stored evidence, or privacy policy; no memory was delivered."
                ),
                omissions=omissions,
                conflicts=conflicts,
            )

        mandatory_eligible = [item for item in eligible if item.mandatory]
        if len(mandatory_eligible) > request.budget.max_evidence_items:
            overflow = mandatory_eligible[request.budget.max_evidence_items :]
            omissions.extend(
                TaskBriefOmission(
                    memory_id=str(item.result.memory.id),
                    reason="mandatory-evidence-item-budget",
                )
                for item in overflow
            )
            return self._blocked_v2_brief(
                request,
                candidates,
                reason="mandatory-context-exceeds-evidence-budget",
                warning=(
                    "More required user-locked memories apply than the hard evidence "
                    "limit permits; no memory was delivered."
                ),
                omissions=omissions,
                conflicts=conflicts,
            )
        optional_by_stage: dict[TaskStage, list[_RankedEvidence]] = {
            stage: self._diversify_sources(
                [
                    item
                    for item in eligible
                    if not item.mandatory and (request.stage or item.stage) == stage
                ]
            )
            for stage in TaskStage
        }

        by_stage: dict[TaskStage, list[_RankedEvidence]] = {
            stage: [] for stage in TaskStage
        }
        for item in mandatory_eligible:
            by_stage[request.stage or item.stage].append(item)
        for stage in TaskStage:
            by_stage[stage].extend(optional_by_stage[stage])

        packets: list[TaskBriefPacket] = []
        delivered_ids: list[str] = []
        remaining_slots = request.budget.max_evidence_items
        remaining_token_budget = max(
            0,
            request.budget.total_tokens - estimate_tokens(preamble) - 12,
        )
        requested_stage_budgets = {
            stage: request.budget.for_stage(stage) for stage in TaskStage
        }
        stage_token_budgets: dict[TaskStage, int] = {}
        unallocated = remaining_token_budget
        stages = list(TaskStage)
        for stage in stages[:-1]:
            allocation = int(
                remaining_token_budget
                * requested_stage_budgets[stage]
                / request.budget.total_tokens
            )
            stage_token_budgets[stage] = allocation
            unallocated -= allocation
        stage_token_budgets[stages[-1]] = unallocated
        for stage in TaskStage:
            mandatory_in_later_stages = sum(
                item.mandatory
                for later_stage in stages[stages.index(stage) + 1 :]
                for item in by_stage[later_stage]
            )
            stage_item_limit = max(0, remaining_slots - mandatory_in_later_stages)
            packet, packet_omissions = self._build_packet(
                stage,
                by_stage[stage],
                stage_token_budgets[stage],
                max_items=stage_item_limit,
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

        mandatory_budget_omissions = [
            omission
            for omission in omissions
            if omission.reason == "mandatory-stage-token-budget"
        ]
        mandatory_ids = {str(item.result.memory.id) for item in mandatory_eligible}
        truncated_mandatory_ids = {
            evidence.memory_id
            for packet in packets
            for evidence in packet.evidence
            if evidence.memory_id in mandatory_ids and evidence.truncated
        }
        if mandatory_budget_omissions or truncated_mandatory_ids:
            omissions.extend(
                TaskBriefOmission(
                    memory_id=memory_id,
                    reason="mandatory-context-truncation",
                )
                for memory_id in sorted(truncated_mandatory_ids)
            )
            return self._blocked_v2_brief(
                request,
                candidates,
                reason="mandatory-context-exceeds-token-budget",
                warning=(
                    "Required user-locked evidence could not fit intact inside the "
                    "hard Task Brief budget; no memory was delivered."
                ),
                omissions=omissions,
                conflicts=conflicts,
            )

        evidence_context = "\n\n".join(
            packet.rendered_context for packet in packets if packet.rendered_context
        )
        abstained = not delivered_ids
        if abstained:
            rendered = "ELEFANTE TASK BRIEF\nABSTAIN: no evidence met the independent relevance gate."
        else:
            rendered = "\n\n".join([preamble, evidence_context])
        if estimate_tokens(rendered) > request.budget.total_tokens:
            return self._blocked_v2_brief(
                request,
                candidates,
                reason="final-render-exceeds-token-budget",
                warning=(
                    "The complete Task Brief exceeded the hard token budget after "
                    "rendering; no memory was delivered."
                ),
                omissions=omissions,
                conflicts=conflicts,
            )
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

    @staticmethod
    def _render_preamble(request: TaskBriefRequest) -> str:
        lines = ["ELEFANTE TASK BRIEF", f"Task: {request.task}"]
        if request.success_criteria:
            lines.append("Success criteria:")
            lines.extend(f"- {item}" for item in request.success_criteria)
        return "\n".join(lines)

    def _blocked_v2_brief(
        self,
        request: TaskBriefRequest,
        candidates: Sequence[SearchResult],
        *,
        reason: str,
        warning: str,
        omissions: Sequence[TaskBriefOmission] | None = None,
        conflicts: Sequence[TaskBriefConflict] | None = None,
    ) -> TaskBrief:
        rendered = "ELEFANTE TASK BRIEF\nBLOCKED: " + warning
        if estimate_tokens(rendered) > request.budget.total_tokens:
            rendered = "ELEFANTE TASK BRIEF\nBLOCKED: task contract exceeds budget."
        known_omissions = list(omissions or [])
        omitted_ids = {item.memory_id for item in known_omissions}
        known_omissions.extend(
            TaskBriefOmission(
                memory_id=str(candidate.memory.id),
                reason=reason,
            )
            for candidate in candidates
            if str(candidate.memory.id) not in omitted_ids
        )
        return TaskBrief(
            profile=request.profile,
            task_id=request.task_id,
            task_summary=request.task,
            success_criteria=request.success_criteria,
            packets=[
                TaskBriefPacket(
                    stage=stage,
                    evidence=[],
                    rendered_context="",
                    estimated_tokens=0,
                    token_budget=request.budget.for_stage(stage),
                )
                for stage in TaskStage
            ],
            conflicts=sorted(list(conflicts or []), key=lambda item: item.memory_id),
            omissions=sorted(
                known_omissions,
                key=lambda item: (item.memory_id, item.reason),
            ),
            selected_memory_ids=[],
            rendered_context=rendered,
            estimated_tokens=estimate_tokens(rendered),
            token_budget=request.budget.total_tokens,
            abstained=True,
            abstention_reason=reason,
            delivery_blocked=True,
            governance_warnings=[warning],
        )

    def _rank_candidates_v2(
        self,
        request: TaskBriefRequest,
        candidates: Sequence[SearchResult],
    ) -> list[_RankedEvidence]:
        unique: dict[str, _RankedEvidence] = {}
        query_text = " ".join([request.task, *request.success_criteria])
        # A request to explain or summarize is not evidence that a record
        # containing that presentation instruction answers the actual topic.
        lexical_query = re.sub(
            r"^\s*(?:please\s+)?(?:explain|describe|summari[sz]e|tell\s+me|show\s+me)\b[:\s]*",
            "", query_text, count=1, flags=re.IGNORECASE,
        )
        query_counts = self._canonical_term_counts(lexical_query)
        query_terms = set(query_counts)
        mechanism = re.search(
            r"\bhow\s+(?:do|does|did)\s+(.+)", request.task.partition("?")[0], re.IGNORECASE,
        )
        mechanism_terms = self._canonical_terms(mechanism[1]) if mechanism else set()
        minimum_text_matches = min(2, len(query_terms))
        query_identifiers = {
            term for term in query_terms if any(character.isdigit() for character in term)
        }
        anchor_terms = {term for term, count in query_counts.items() if count >= 2}
        query_intent = CognitiveRetriever.infer_intent(query_text)
        for result in candidates:
            memory = result.memory
            memory_id = str(memory.id)
            content_terms = self._canonical_terms(
                " ".join([memory.content, memory.metadata.summary or ""])
            )
            path_terms = self._canonical_terms(memory.metadata.file_path or "")
            custom = memory.metadata.custom_metadata or {}
            symbol_terms = self._canonical_terms(str(custom.get("symbol", "")))
            lexical = self._overlap(query_terms, content_terms)
            path = self._location_overlap(query_terms, path_terms)
            symbol = self._location_overlap(query_terms, symbol_terms)
            matched_terms = query_terms & (content_terms | path_terms | symbol_terms)
            matched_identifiers = query_identifiers & matched_terms
            matched_anchors = anchor_terms & matched_terms
            relationships = [
                str(item).upper() for item in result.relationship_path or []
            ]
            dependency = float(
                any(item in self._ALLOWED_GRAPH_RELATIONSHIPS for item in relationships)
                or bool(custom.get("structural_dependency", False))
            )
            source_code = float(self._is_source_code(memory.metadata.file_path))
            specificity = max(
                0.0,
                min(1.0, float(custom.get("retrieval_specificity", 0.0))),
            )
            surface_match = float(bool(result.surface_matches))
            recall_cue_match = float(bool(result.recall_cue_match))
            recall_cue_similarity = float(result.recall_cue_similarity or 0.0)
            cue_focus = self._recall_cue_focus(query_text, memory)
            semantic = float(
                0.0
                if surface_match or recall_cue_match
                else (
                    result.vector_score
                    if result.vector_score is not None
                    else result.score
                )
            )
            memory_type = str(memory.metadata.memory_type).casefold()
            governing_directive = float(
                query_intent == "decide"
                and memory_type == MemoryType.DIRECTIVE.value
                and bool(memory.metadata.user_locked)
                and str(memory.metadata.injection_policy).casefold()
                == InjectionPolicy.RANKED.value
                and self._declared_scope_anchor(
                    memory.metadata.scope,
                    query_text,
                    project=request.project,
                    workspace=request.workspace,
                )
                and semantic >= self.MIN_GOVERNING_DIRECTIVE_SEMANTIC
            )
            role = self._role_for(memory, relationships)
            stage = self._stage_for_role(role)
            mandatory = is_mandatory(
                memory.metadata,
                query_text,
                project=request.project,
                workspace=request.workspace,
            )
            role_value = 1.0 if role != EvidenceRole.CONTEXT else 0.0
            raw_actionability = (
                1.0
                if surface_match or recall_cue_match
                else (
                    0.25 * semantic
                    + 0.15 * lexical
                    + 0.15 * max(path, symbol)
                    + 0.10 * max(source_code, dependency)
                    + 0.10 * role_value
                    + 0.25 * specificity
                )
            )
            actionability = min(1.0, max(raw_actionability, recall_cue_similarity))
            signals = {
                "semantic": round(semantic, 6),
                "lexical": round(lexical, 6),
                "path": round(path, 6),
                "symbol": round(symbol, 6),
                "dependency": dependency,
                "source_code": source_code,
                "specificity": round(specificity, 6),
                "matched_terms": len(matched_terms),
                "query_terms": len(query_terms),
                "matched_identifiers": len(matched_identifiers),
                "query_identifiers": len(query_identifiers),
                "matched_anchors": len(matched_anchors),
                "query_anchors": len(anchor_terms),
                "query_coverage": round(
                    len(matched_terms) / len(query_terms) if query_terms else 0.0,
                    6,
                ),
                "actionability": round(actionability, 6),
                "governing_directive": governing_directive,
                "surface_match": surface_match,
                "recall_cue_match": recall_cue_match,
                "recall_cue_similarity": recall_cue_similarity,
                "recall_cue_focus": cue_focus,
                "recall_focus_similarity": float(result.recall_focus_similarity or 0.0),
            }
            signals["direct_answer"] = float(
                semantic >= 0.78
                and len(matched_terms) >= minimum_text_matches
                and float(signals["query_coverage"]) >= 0.25
                and (not query_identifiers or bool(matched_identifiers))
            )
            # A saved example question is not an exhaustive content boundary.
            # Require independent body terms beyond that cue's shared topic;
            # high semantic similarity or a role label alone is insufficient.
            body_only_terms = mechanism_terms - self._canonical_terms(
                " ".join(memory.metadata.recall_cues)
            )
            signals["mechanism_body_evidence"] = float(
                signals["direct_answer"]
                and bool(body_only_terms)
                and len(body_only_terms & content_terms) >= min(2, len(body_only_terms))
            )
            positive_signals = [
                name
                for name in (
                    "lexical",
                    "path",
                "symbol",
                "dependency",
                "source_code",
                "governing_directive",
                "surface_match",
                "recall_cue_match",
                "recall_cue_similarity",
            )
                if float(signals[name]) > 0
            ]
            reason = (
                f"{role.value}; signals={','.join(positive_signals) or 'semantic-only'}; "
                f"actionability={actionability:.3f}"
            )
            if mandatory:
                reason = "user-locked always-inject; " + reason
            ranked = _RankedEvidence(
                result=result,
                graph_hop=1 if result.source == "graph-hop" else 0,
                role=role,
                stage=stage,
                actionability_score=actionability,
                reason_selected=reason,
                retrieval_signals=signals,
                mandatory=mandatory,
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
                -int(item.mandatory),
                -item.actionability_score,
                -item.result.memory.metadata.source_reliability,
                -int(item.result.memory.metadata.verified),
                str(item.result.memory.id),
            ),
        )

    def _is_actionable(self, item: _RankedEvidence) -> bool:
        if item.mandatory:
            return True
        signals = item.retrieval_signals or {}
        # A complete, project-scoped question saved by the customer through a
        # verified memory operation is direct evidence for that exact query.
        if float(signals.get("recall_cue_match", 0.0)) > 0.0:
            return True
        # A matching literal trigger is the complete, explicit evidence for
        # this opt-in path.  Lifecycle, scope, privacy, conflict, and source
        # trust have already been checked by ``_exclusion_reason``.
        if float(signals.get("surface_match", 0.0)) > 0.0:
            return True
        query_term_count = int(signals.get("query_terms", 0))
        minimum_matches = min(2, query_term_count)
        strong_location_match = (
            max(
                float(signals.get("path", 0.0)),
                float(signals.get("symbol", 0.0)),
            )
            >= 0.5
        )
        governing_directive = (
            float(signals.get("governing_directive", 0.0)) > 0.0
        )
        # Topic overlap cannot override a known mismatch between the fact
        # requested and the questions this memory was saved to support.
        # Structural and explicit governing evidence retain their own paths.
        if (
            (
                signals.get("recall_cue_focus") == "different"
                or (
                    signals.get("recall_cue_focus") == "choice"
                    and float(signals.get("recall_focus_similarity", 0.0)) < self.MIN_FOCUSED_CUE_SIMILARITY
                )
                or (
                    signals.get("recall_cue_focus") == "property"
                    and float(signals.get("recall_cue_similarity", 0.0)) < self.MIN_RECALL_CUE_SIMILARITY
                    and not float(signals.get("mechanism_body_evidence", 0.0))
                )
            )
            and not strong_location_match
            and not governing_directive
            and float(signals.get("dependency", 0.0)) == 0.0
        ):
            return False
        if (
            int(signals.get("query_identifiers", 0)) > 0
            and int(signals.get("matched_identifiers", 0)) == 0
            and float(signals.get("dependency", 0.0)) == 0.0
            and not strong_location_match
            and not governing_directive
        ):
            return False
        # The orchestrator compares complete saved questions, requires a clear
        # margin over other memories, and never marks an ambiguous winner.
        # Keep identifier and all earlier governance gates in front of it.
        if (
            float(signals.get("recall_cue_similarity", 0.0))
            >= (
                self.MIN_FOCUSED_CUE_SIMILARITY
                if signals.get("recall_cue_focus") in {"same", "choice"}
                else self.MIN_RECALL_CUE_SIMILARITY
            )
        ):
            return int(signals.get("matched_identifiers", 0)) == int(
                signals.get("query_identifiers", 0)
            )
        if (
            int(signals.get("matched_terms", 0)) < minimum_matches
            and float(signals.get("dependency", 0.0)) == 0.0
            and not strong_location_match
            and not governing_directive
        ):
            return False
        independent = sum(
            (
                float(signals.get("semantic", 0.0)) >= 0.55,
                float(signals.get("lexical", 0.0)) > 0.0,
                float(signals.get("path", 0.0)) > 0.0,
                float(signals.get("symbol", 0.0)) > 0.0,
                float(signals.get("dependency", 0.0)) > 0.0,
                governing_directive,
            )
        )
        decision_bearing_role = item.role in {
            EvidenceRole.CONSTRAINT,
            EvidenceRole.DECISION,
            EvidenceRole.FAILURE,
            EvidenceRole.SAFEGUARD,
        }
        role_text_anchor = (
            decision_bearing_role
            and int(signals.get("matched_terms", 0)) >= minimum_matches
            and float(signals.get("query_coverage", 0.0))
            >= self.MIN_ROLE_ANCHOR_COVERAGE
        )
        # Repeated words are useful for disambiguating generic context, not
        # mandatory answer tokens. Preserve independently qualified answers
        # and decision-bearing evidence with the existing coverage floor.
        # The earlier scope, trust, focus, and identifier gates still apply.
        if (
            float(signals.get("specificity", 0.0)) == 0.0
            and float(signals.get("direct_answer", 0.0)) == 0.0
            and not role_text_anchor
        ):
            anchor_count = int(signals.get("query_anchors", 0))
            minimum_anchors = min(2, anchor_count)
            if (
                minimum_anchors
                and int(signals.get("matched_anchors", 0)) < minimum_anchors
            ):
                return False
        action_anchor = (
            float(signals.get("path", 0.0)) > 0.0
            or float(signals.get("symbol", 0.0)) > 0.0
            or float(signals.get("dependency", 0.0)) > 0.0
            or float(signals.get("specificity", 0.0)) > 0.0
            or float(signals.get("direct_answer", 0.0)) > 0.0
            or governing_directive
            or role_text_anchor
            or float(signals.get("surface_match", 0.0)) > 0.0
            or float(signals.get("recall_cue_match", 0.0)) > 0.0
        )
        # A candidate already classified as a direct answer has strong semantic
        # similarity plus bounded lexical coverage. Do not reject that evidence
        # only because it lacks source-code, graph, role, or path signals; those
        # signals measure implementation actionability, not answerability.
        direct_answer = float(signals.get("direct_answer", 0.0)) > 0.0
        return (
            independent >= 2
            and action_anchor
            and (direct_answer or item.actionability_score >= 0.3)
        )

    @staticmethod
    def _question_focus(text: str) -> str | None:
        """Recognize explicit question targets, not subjects or product names.

        This deliberately small English grammar distinguishes e.g. where from
        when, and 'which airline' from 'which seat'. Unknown wording supplies
        no evidence. There is no domain vocabulary or answer generation here.
        """
        text = " ".join(text.casefold().split())
        auxiliary = r"(?:am|is|are|was|were|do|does|did|can|could|should|would|will|must|have|has)"
        match = re.search(r"\b(where|when|who|why|how|what|which)\b", text)
        if not match:
            if re.match(auxiliary + r"\b", text) and " or " in text:
                # For a closed choice, compare the requested property with the
                # alternatives themselves, not the shared subject words.
                before, after = text.rsplit(" or ", 1)
                option = re.split(r"\b(?:in|with|by|as|using|choose|prefer|want)\b", before)[-1]
                return "choice:" + (option.strip() + " or " + after).rstrip("?.!")
            return None
        word, rest = match[1], text[match.end():].strip()
        if word in {"where", "when", "who", "why"}:
            return {"where": "location", "when": "time", "who": "person", "why": "reason"}[word]
        if word == "how":
            measure = re.match(r"(many|much|long|often|old)\b(.*)", rest)
            if measure:
                kind, tail = measure.groups()
                if kind in {"many", "much"} and re.match(
                    r"\s+(?:time|seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b", tail,
                ):
                    return "duration"
                return {"many": "count", "much": "amount", "long": "duration", "often": "frequency", "old": "age"}[kind]
            if re.match(r"(?:do|does|did)\b", rest):
                return "mechanism"
            return "method" if re.match(auxiliary + r"\b", rest) else None
        # A noun phrase before the auxiliary names the requested property.
        # Bare 'what is X?' has no explicit property and remains unknown.
        if re.match(auxiliary + r"\b", rest):
            return None
        # Procedural nouns ask how to act, not for an absent named fact.
        # This changes intent classification only, never the relevance gates.
        if re.match(r"(?:steps?|checks?|actions?|procedures?|precautions?)\s+" + auxiliary + r"\b", rest):
            return "method"
        phrase = re.match(r"(.+?)\s+" + auxiliary + r"\b", rest)
        if not phrase:
            # Subject questions can use a simple verb without an auxiliary:
            # "Which supplier provides ...?" still requests the supplier.
            subject = re.match(r"([a-z]+)\s+[a-z]+(?:s|ed)\s+", rest)
            return "property:" + subject[1] if subject else None
        words = re.findall(r"[a-z]+", re.split(r"\b(?:of|for|in|on)\b", phrase[1])[0])
        if not words:
            return None
        head = words[-1]
        if head == "time":
            return "time"
        return "property:" + " ".join(words)

    @classmethod
    def _recall_cue_focus(cls, question: str, memory: Memory) -> str:
        """Compare explicit targets; ambiguity neither proves nor vetoes fit."""
        from src.utils.curation import canonicalize_recall_cues

        target = cls._question_focus(question)
        if target is None:
            return "unknown"
        focuses = [cls._question_focus(cue) for cue in canonicalize_recall_cues(memory.metadata.recall_cues)]
        def key(focus: str | None) -> str | None:
            if focus in {"method", "mechanism"}:
                return "method"
            if focus and focus.startswith("property:"):
                return "property:" + focus.partition(":")[2].split()[-1]
            return focus

        if key(target) in [key(focus) for focus in focuses]:
            return "same"
        # Describing how something works is not a request for every rule about
        # its topic. A different named property needs the existing strong cue
        # evidence; the specification label and shared subject do not prove it.
        if target == "mechanism" and any(
            focus and focus.startswith("property:") for focus in focuses
        ):
            return "property"
        # Open-ended guidance can use constraints or facts saved under a more
        # specific question. A different question form alone is not a veto.
        if target in {"method", "mechanism", "reason"}:
            return "unknown"
        # A named property present in the body may be covered by a broader
        # saved question. Do not turn cues into an exhaustive whitelist.
        if target.startswith("property:"):
            if any(focus and focus.startswith("choice:") for focus in focuses):
                return "choice"
            head = target.partition(":")[2].split()[-1]
            # A type label establishes only the generic category, not a
            # qualified property such as staffing or privacy constraints.
            if cls._canonical_terms(target.partition(":")[2]) in ({"constraint"}, {"rule"}) and str(memory.metadata.memory_type).casefold() in {
                MemoryType.SPECIFICATION.value, MemoryType.DIRECTIVE.value,
            }:
                return "unknown"
            if head in cls._canonical_terms(memory.content):
                return "unknown"
            if any(focus and focus.startswith("property:") for focus in focuses):
                return "property"
            # A shared subject cannot establish an absent requested property,
            # including when no cue was saved. This uses the question's noun
            # phrase, never a product-specific vocabulary.
            return "different"
        if target in {"amount", "count", "duration", "frequency", "age"}:
            # Quantitative questions need quantitative evidence. A matching
            # saved question above remains an independent path for values
            # expressed in other forms; a generic cue supplies no such proof.
            quantity_words = {
                "zero", "one", "two", "three", "four", "five", "six", "seven",
                "eight", "nine", "ten", "eleven", "twelve", "thirteen",
                "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
                "nineteen", "twenty", "thirty", "forty", "fifty", "sixty",
                "seventy", "eighty", "ninety", "hundred", "thousand", "million",
            }
            if not (
                re.search(r"\b(?:\d+(?:[.,]\d+)?|no|none)\b", memory.content, re.IGNORECASE)
                or quantity_words & cls._canonical_terms(memory.content)
            ):
                return "different"
        if not focuses or None in focuses:
            return "unknown"
        return "different"

    @staticmethod
    def _declared_scope_anchor(
        scope: str | None,
        query: str,
        *,
        project: str | None,
        workspace: str | None,
    ) -> bool:
        """Require the declared non-global scope to be explicit in this task."""
        declared = str(scope or "").strip().casefold()
        if not declared or declared == "global":
            return False
        aliases = {declared}
        if ":" in declared:
            aliases.add(declared.split(":", 1)[1])
        explicit = {
            str(project or "").strip().casefold(),
            str(workspace or "").strip().casefold(),
        }
        explicit.discard("")
        if aliases & explicit:
            return True
        query_folded = str(query or "").casefold()
        return any(
            bool(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", query_folded))
            for alias in aliases
            if alias
        )

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

    @classmethod
    def _canonical_terms(cls, value: str) -> set[str]:
        """Collapse simple inflections so one concept cannot count twice."""
        return set(cls._canonical_term_counts(value))

    @classmethod
    def _canonical_term_counts(cls, value: str) -> Counter[str]:
        counts: Counter[str] = Counter()
        for raw in cls._TOKEN_PATTERN.findall(value):
            for part in (
                re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw).replace("-", "_").split("_")
            ):
                term = part.casefold()
                if len(term) < 3 or term in cls._STOP_WORDS:
                    continue
                if term.endswith("ies") and len(term) > 4:
                    term = term[:-3] + "y"
                elif (
                    term.endswith("s")
                    and len(term) > 4
                    and not term.endswith(("ss", "us"))
                ):
                    term = term[:-1]
                counts[term] += 1
        return counts

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

    @classmethod
    def _location_overlap(
        cls, query_terms: set[str], location_terms: set[str]
    ) -> float:
        """Reject one-word symbols while rewarding multi-term path/symbol anchors."""
        if len(location_terms) < 2:
            return 0.0
        return cls._focused_overlap(query_terms, location_terms)

    def _is_source_code(self, file_path: str | None) -> bool:
        return bool(
            file_path
            and PurePosixPath(file_path).suffix.casefold() in self._SOURCE_SUFFIXES
        )

    @staticmethod
    def _is_test_artifact(file_path: str | None) -> bool:
        if not file_path:
            return False
        path = PurePosixPath(file_path)
        name = path.name.casefold()
        parts = {part.casefold() for part in path.parts}
        return bool(
            "tests" in parts
            or "test" in parts
            or name.startswith("test_")
            or ".test." in name
            or ".spec." in name
        )

    def _role_for(self, memory: Memory, relationships: Sequence[str]) -> EvidenceRole:
        custom_role = str(
            (memory.metadata.custom_metadata or {}).get("evidence_role", "")
        )
        if custom_role in {role.value for role in EvidenceRole}:
            return EvidenceRole(custom_role)
        source_kind = str(
            (memory.metadata.custom_metadata or {}).get("source_kind", "")
        ).casefold()
        if source_kind in {"configuration", "documentation"}:
            return EvidenceRole.CONTEXT
        memory_type = str(memory.metadata.memory_type).casefold()
        if memory_type == MemoryType.DECISION.value:
            return EvidenceRole.DECISION
        if memory_type in {MemoryType.DIRECTIVE.value, MemoryType.SPECIFICATION.value}:
            return EvidenceRole.CONSTRAINT
        if any(item in self._ALLOWED_GRAPH_RELATIONSHIPS for item in relationships):
            return EvidenceRole.DEPENDENCY
        if self._is_test_artifact(memory.metadata.file_path):
            return EvidenceRole.SAFEGUARD
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
        current_source_state = str(
            (metadata.custom_metadata or {}).get(
                "current_source_state", CurrentSourceState.UNAVAILABLE.value
            )
        ).casefold()
        if current_source_state == CurrentSourceState.CONTRADICTED.value:
            return "current-source-contradicted"
        from src.modules.distiller.privacy import PrivacyFilter

        _, privacy_redactions, _ = PrivacyFilter().scrub_payload(
            {
                "content": result.memory.content,
                "source_detail": metadata.source_detail,
                "project": metadata.project,
                "workspace": metadata.workspace,
                "file_path": metadata.file_path,
            }
        )
        if privacy_redactions:
            return "privacy-redaction"
        if request.project and metadata.project and metadata.project != request.project:
            return "cross-project"
        if (
            request.workspace
            and metadata.workspace
            and metadata.workspace != request.workspace
        ):
            return "cross-workspace"
        context = " ".join([request.task, *request.success_criteria])
        governance = governance_reason(
            metadata,
            context,
            project=request.project,
            workspace=request.workspace,
        )
        if governance:
            return governance
        mandatory = is_mandatory(
            metadata,
            context,
            project=request.project,
            workspace=request.workspace,
        )
        if not mandatory and metadata.source_reliability < self.MIN_RELIABILITY:
            return "low-source-reliability"
        if (
            not mandatory
            and not result.recall_cue_match
            and result.score < self.MIN_RETRIEVAL_SCORE
        ):
            return "low-retrieval-score"
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
        *,
        max_items: int | None = None,
    ) -> tuple[TaskBriefPacket, list[TaskBriefOmission]]:
        header = f"{stage.value.upper()} EVIDENCE"
        lines = [header]
        evidence: list[TaskBriefEvidence] = []
        omissions: list[TaskBriefOmission] = []
        for item in items:
            if max_items is not None and len(evidence) >= max_items:
                omissions.append(
                    TaskBriefOmission(
                        memory_id=str(item.result.memory.id),
                        reason="max-evidence-items",
                    )
                )
                continue
            line, excerpt, truncated = self._fit_line(
                item,
                lines,
                token_budget,
            )
            memory_id = str(item.result.memory.id)
            if line is None:
                omissions.append(
                    TaskBriefOmission(
                        memory_id=memory_id,
                        reason=(
                            "mandatory-stage-token-budget"
                            if item.mandatory
                            else "stage-token-budget"
                        ),
                    )
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
                    current_source_state=(metadata.custom_metadata or {}).get(
                        "current_source_state",
                        CurrentSourceState.UNAVAILABLE.value,
                    ),
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
        current_source_state = str(
            (metadata.custom_metadata or {}).get(
                "current_source_state", CurrentSourceState.UNAVAILABLE.value
            )
        )
        provenance += f"; current-source={current_source_state}"
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

    @classmethod
    async def prepare_candidates(
        cls,
        results: Sequence[SearchResult],
        *,
        workspace: str | None,
    ) -> list[SearchResult]:
        """Clone and source-check candidates before any delivery compiler runs.

        Search adapters may return store-backed model instances.  Source state is
        therefore attached only to deep copies, and the shared method is usable by
        the explicit Task Brief, prompt, search-metadata, and opt-in injection paths.
        """
        candidates = [result.model_copy(deep=True) for result in results]
        await asyncio.gather(
            *(
                asyncio.to_thread(
                    cls._annotate_current_source,
                    result.memory,
                    workspace,
                )
                for result in candidates
            )
        )
        return candidates

    async def generate(self, request: TaskBriefRequest) -> TaskBrief:
        filters = SearchFilters(
            project=request.project,
            workspace=request.workspace,
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
        candidates = await self.prepare_candidates(
            [*results, *graph_results],
            workspace=request.workspace,
        )
        return self.compiler.compile(request, candidates)

    @staticmethod
    def _annotate_current_source(memory: Memory, workspace: str | None) -> None:
        """Attach a conservative current-source state without persisting it.

        Absence or a text mismatch is UNKNOWN (`unavailable`), not contradiction.
        Only an explicit source-file digest mismatch can prove contradiction.
        """
        state = CurrentSourceState.UNAVAILABLE.value
        file_path = memory.metadata.file_path
        if workspace and file_path:
            try:
                root = Path(workspace).expanduser().resolve(strict=True)
                candidate = Path(file_path).expanduser()
                if not candidate.is_absolute():
                    candidate = root / candidate
                candidate = candidate.resolve(strict=True)
                candidate.relative_to(root)
                if candidate.is_file() and candidate.stat().st_size <= 2_000_000:
                    custom = memory.metadata.custom_metadata or {}
                    expected_digest = str(
                        custom.get("source_file_sha256", "") or ""
                    ).casefold()
                    if re.fullmatch(r"[0-9a-f]{64}", expected_digest):
                        observed = hashlib.sha256(candidate.read_bytes()).hexdigest()
                        state = (
                            CurrentSourceState.SUPPORTED.value
                            if observed == expected_digest
                            else CurrentSourceState.CONTRADICTED.value
                        )
                    else:
                        content = candidate.read_text(
                            encoding="utf-8", errors="replace"
                        )
                        normalized_memory = " ".join(memory.content.split())
                        normalized_source = " ".join(content.split())
                        if (
                            len(normalized_memory) >= 20
                            and normalized_memory in normalized_source
                        ):
                            state = CurrentSourceState.SUPPORTED.value
            except (OSError, UnicodeError, ValueError):
                state = CurrentSourceState.UNAVAILABLE.value
        custom = dict(memory.metadata.custom_metadata or {})
        custom["current_source_state"] = state
        memory.metadata.custom_metadata = custom

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
