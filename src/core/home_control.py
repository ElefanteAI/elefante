"""In-memory capabilities for named state-changing actions in Elefante Home.

Home remains a snapshot reader unless it is connected to the running Elefante
daemon. The trusted loopback Home origin receives a short-lived bearer
capability and keeps it in browser memory; only hashes are retained here.
Resolve and Correct apply additionally require one exact, one-use plan ticket
so a browser cannot mutate different knowledge than the user just inspected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import secrets
import time
from typing import Callable, Mapping
from uuid import UUID


DEFAULT_HOME_ORIGINS = frozenset(
    {
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    }
)


class HomeControlError(RuntimeError):
    """A bounded control-plane rejection safe to return to Home."""

    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class HomeControlGrant:
    token: str
    expires_in_seconds: int


@dataclass(frozen=True)
class HomeResolveTicket:
    ticket_id: str
    left_memory_id: str
    right_memory_id: str
    winner_memory_id: str | None
    confirm_protected: bool
    record_sha256: dict[str, str]
    expires_at_monotonic: float


@dataclass(frozen=True)
class HomeCorrectionTicket:
    ticket_id: str
    memory_id: str
    action: str
    confirm_protected: bool
    record_sha256: dict[str, str]
    graph_sha256: dict[str, str]
    content_sha256: str | None
    expires_at_monotonic: float


@dataclass(frozen=True)
class HomeRecoveryTicket:
    ticket_id: str
    action: str
    layout_sha256: str | None
    archive_name: str | None
    archive_sha256: str | None
    report_sha256: str | None
    project_id: str | None
    workspace_sha256: str | None
    expires_at_monotonic: float


@dataclass(frozen=True)
class HomeRememberTicket:
    ticket_id: str
    project_id: str
    knowledge_kind: str
    content_sha256: str
    question_sha256: str
    overlap_sha256: dict[str, str]
    expires_at_monotonic: float


@dataclass(frozen=True)
class HomeProjectAssignmentTicket:
    ticket_id: str
    memory_id: str
    project_id: str
    confirm_protected: bool
    record_sha256: str
    graph_existed: bool
    graph_sha256: str | None
    relationship_sha256: str
    target_scope_sha256: str
    expires_at_monotonic: float


@dataclass
class _HomeSession:
    origin: str
    expires_at_monotonic: float
    project_id: str | None = None
    requests_used: int = 0
    plans: dict[
        str,
        HomeResolveTicket
        | HomeCorrectionTicket
        | HomeRecoveryTicket
        | HomeRememberTicket
        | HomeProjectAssignmentTicket,
    ] = field(
        default_factory=dict
    )


class HomeControlRegistry:
    """Bounded process-local capability and Resolve-plan registry."""

    def __init__(
        self,
        *,
        now: Callable[[], float] | None = None,
        token_factory: Callable[[], str] | None = None,
        session_ttl_seconds: int = 900,
        plan_ttl_seconds: int | None = None,
        max_requests: int = 24,
        max_sessions: int = 8,
        max_plans_per_session: int = 4,
        allowed_origins: frozenset[str] = DEFAULT_HOME_ORIGINS,
    ) -> None:
        if not 30 <= session_ttl_seconds <= 3600:
            raise ValueError("session_ttl_seconds must be from 30 to 3600")
        effective_plan_ttl = min(300, session_ttl_seconds) if plan_ttl_seconds is None else plan_ttl_seconds
        if not 5 <= effective_plan_ttl <= session_ttl_seconds:
            raise ValueError("plan_ttl_seconds must be from 5 through the session TTL")
        if not 1 <= max_requests <= 100:
            raise ValueError("max_requests must be from 1 to 100")
        if not 1 <= max_sessions <= 32:
            raise ValueError("max_sessions must be from 1 to 32")
        if not 1 <= max_plans_per_session <= 16:
            raise ValueError("max_plans_per_session must be from 1 to 16")
        self._now = now or time.monotonic
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self.session_ttl_seconds = session_ttl_seconds
        self.plan_ttl_seconds = effective_plan_ttl
        self.max_requests = max_requests
        self.max_sessions = max_sessions
        self.max_plans_per_session = max_plans_per_session
        self.allowed_origins = allowed_origins
        self._sessions: dict[str, _HomeSession] = {}

    def __repr__(self) -> str:
        return (
            f"HomeControlRegistry(active_sessions={len(self._sessions)}, "
            f"max_sessions={self.max_sessions})"
        )

    @staticmethod
    def _token_sha256(token: str) -> str:
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_hashes(record_sha256: Mapping[str, str]) -> dict[str, str]:
        if set(record_sha256) != {"left", "right"}:
            raise HomeControlError(
                "Resolve plan requires exact left and right record hashes.",
                code="CONTROL_PLAN_HASH_INVALID",
                status_code=400,
            )
        normalized = {key: str(value).casefold() for key, value in record_sha256.items()}
        if any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in normalized.values()
        ):
            raise HomeControlError(
                "Resolve plan record hashes are invalid.",
                code="CONTROL_PLAN_HASH_INVALID",
                status_code=400,
            )
        return normalized

    @staticmethod
    def _validate_correction_hashes(
        values: Mapping[str, str],
        *,
        label: str,
        expected_keys: frozenset[str] = frozenset({"target"}),
    ) -> dict[str, str]:
        if set(values) != expected_keys:
            raise HomeControlError(
                f"Correction plan requires the exact {label} hashes.",
                code="CONTROL_PLAN_HASH_INVALID",
                status_code=400,
            )
        normalized = {
            key: str(values[key]).casefold()
            for key in sorted(expected_keys)
        }
        if any(
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            for digest in normalized.values()
        ):
            raise HomeControlError(
                f"Correction plan {label} hash is invalid.",
                code="CONTROL_PLAN_HASH_INVALID",
                status_code=400,
            )
        return normalized

    @staticmethod
    def _validate_optional_digest(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).casefold()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise HomeControlError(
                "Correction plan content hash is invalid.",
                code="CONTROL_PLAN_HASH_INVALID",
                status_code=400,
            )
        return normalized

    def _prune(self) -> None:
        now = self._now()
        self._sessions = {
            key: session
            for key, session in self._sessions.items()
            if session.expires_at_monotonic > now
        }
        for session in self._sessions.values():
            session.plans = {
                key: plan
                for key, plan in session.plans.items()
                if plan.expires_at_monotonic > now
            }

    def issue(
        self,
        origin: str,
        *,
        project_id: str | None = None,
    ) -> HomeControlGrant:
        """Create one short-lived grant while retaining only its digest."""
        if origin not in self.allowed_origins:
            raise HomeControlError(
                "Home control origin is not allowed.",
                code="CONTROL_ORIGIN_REJECTED",
                status_code=403,
            )
        self._prune()
        if len(self._sessions) >= self.max_sessions:
            oldest = min(
                self._sessions,
                key=lambda key: self._sessions[key].expires_at_monotonic,
            )
            self._sessions.pop(oldest, None)
        token = str(self._token_factory())
        if len(token) < 12:
            raise RuntimeError("Home control token factory returned an unsafe token")
        digest = self._token_sha256(token)
        if digest in self._sessions:
            raise RuntimeError("Home control token factory returned a duplicate token")
        normalized_project_id: str | None = None
        if project_id is not None:
            try:
                normalized_project_id = str(UUID(str(project_id)))
            except (TypeError, ValueError) as error:
                raise HomeControlError(
                    "Home project identity is invalid.",
                    code="CONTROL_PROJECT_INVALID",
                    status_code=400,
                ) from error
        self._sessions[digest] = _HomeSession(
            origin=origin,
            expires_at_monotonic=self._now() + self.session_ttl_seconds,
            project_id=normalized_project_id,
        )
        return HomeControlGrant(
            token=token,
            expires_in_seconds=self.session_ttl_seconds,
        )

    def authorize(self, token: str, origin: str) -> _HomeSession:
        """Authorize one bounded request without ever logging or storing raw token."""
        digest = self._token_sha256(token)
        session = self._sessions.get(digest)
        if session is None:
            raise HomeControlError(
                "Home control session is invalid.",
                code="CONTROL_SESSION_INVALID",
                status_code=401,
            )
        if session.expires_at_monotonic <= self._now():
            self._sessions.pop(digest, None)
            raise HomeControlError(
                "Home session expired; reload Home to reconnect.",
                code="CONTROL_SESSION_EXPIRED",
                status_code=401,
            )
        if origin != session.origin or origin not in self.allowed_origins:
            raise HomeControlError(
                "Home control origin does not match the issued session.",
                code="CONTROL_ORIGIN_REJECTED",
                status_code=403,
            )
        if session.requests_used >= self.max_requests:
            raise HomeControlError(
                "Home session request limit reached; reload Home to reconnect.",
                code="CONTROL_REQUEST_LIMIT",
                status_code=429,
            )
        session.requests_used += 1
        return session

    def create_resolve_plan(
        self,
        token: str,
        origin: str,
        *,
        left_memory_id: str,
        right_memory_id: str,
        winner_memory_id: str | None,
        confirm_protected: bool,
        record_sha256: Mapping[str, str],
    ) -> str:
        session = self.authorize(token, origin)
        return self.create_resolve_plan_for_session(
            session,
            left_memory_id=left_memory_id,
            right_memory_id=right_memory_id,
            winner_memory_id=winner_memory_id,
            confirm_protected=confirm_protected,
            record_sha256=record_sha256,
        )

    def create_resolve_plan_for_session(
        self,
        session: _HomeSession,
        *,
        left_memory_id: str,
        right_memory_id: str,
        winner_memory_id: str | None,
        confirm_protected: bool,
        record_sha256: Mapping[str, str],
    ) -> str:
        """Create a ticket after this exact request already authorized once."""
        if not any(candidate is session for candidate in self._sessions.values()):
            raise HomeControlError(
                "Home control session is invalid.",
                code="CONTROL_SESSION_INVALID",
                status_code=401,
            )
        now = self._now()
        session.plans = {
            key: plan
            for key, plan in session.plans.items()
            if plan.expires_at_monotonic > now
        }
        if len(session.plans) >= self.max_plans_per_session:
            oldest = min(
                session.plans,
                key=lambda key: session.plans[key].expires_at_monotonic,
            )
            session.plans.pop(oldest, None)
        ticket_id = str(self._token_factory())
        if len(ticket_id) < 8 or ticket_id in session.plans:
            raise RuntimeError("Home control token factory returned an unsafe plan ticket")
        session.plans[ticket_id] = HomeResolveTicket(
            ticket_id=ticket_id,
            left_memory_id=str(left_memory_id),
            right_memory_id=str(right_memory_id),
            winner_memory_id=(str(winner_memory_id) if winner_memory_id else None),
            confirm_protected=bool(confirm_protected),
            record_sha256=self._validate_hashes(record_sha256),
            expires_at_monotonic=min(
                session.expires_at_monotonic,
                now + self.plan_ttl_seconds,
            ),
        )
        return ticket_id

    def consume_resolve_plan(
        self,
        token: str,
        origin: str,
        ticket_id: str,
    ) -> HomeResolveTicket:
        session = self.authorize(token, origin)
        ticket = session.plans.get(str(ticket_id))
        if not isinstance(ticket, HomeResolveTicket):
            raise HomeControlError(
                "Resolve plan was not found or was already used.",
                code="CONTROL_PLAN_NOT_FOUND",
                status_code=409,
            )
        session.plans.pop(str(ticket_id), None)
        if ticket.expires_at_monotonic <= self._now():
            raise HomeControlError(
                "Resolve plan expired; inspect the memories again.",
                code="CONTROL_PLAN_EXPIRED",
                status_code=409,
            )
        return ticket

    def create_correction_plan_for_session(
        self,
        session: _HomeSession,
        *,
        memory_id: str,
        action: str,
        confirm_protected: bool,
        record_sha256: Mapping[str, str],
        graph_sha256: Mapping[str, str],
        content_sha256: str | None,
    ) -> str:
        """Create one content-free ticket after an authorized inspection."""
        if not any(candidate is session for candidate in self._sessions.values()):
            raise HomeControlError(
                "Home control session is invalid.",
                code="CONTROL_SESSION_INVALID",
                status_code=401,
            )
        selected = str(action).strip()
        if selected not in {
            "edit",
            "replace",
            "archive",
            "restore",
            "permanent_delete",
        }:
            raise HomeControlError(
                "Home correction action is invalid.",
                code="CORRECTION_ACTION_INVALID",
                status_code=400,
            )
        now = self._now()
        session.plans = {
            key: plan
            for key, plan in session.plans.items()
            if plan.expires_at_monotonic > now
        }
        if len(session.plans) >= self.max_plans_per_session:
            oldest = min(
                session.plans,
                key=lambda key: session.plans[key].expires_at_monotonic,
            )
            session.plans.pop(oldest, None)
        ticket_id = str(self._token_factory())
        if len(ticket_id) < 8 or ticket_id in session.plans:
            raise RuntimeError("Home control token factory returned an unsafe plan ticket")
        normalized_content = self._validate_optional_digest(content_sha256)
        if selected in {"edit", "replace"} and normalized_content is None:
            raise HomeControlError(
                "Edit and Replace plans require one exact content hash.",
                code="CONTROL_PLAN_HASH_INVALID",
                status_code=400,
            )
        session.plans[ticket_id] = HomeCorrectionTicket(
            ticket_id=ticket_id,
            memory_id=str(memory_id),
            action=selected,
            confirm_protected=bool(confirm_protected),
            record_sha256=self._validate_correction_hashes(
                record_sha256,
                label="record",
            ),
            graph_sha256=self._validate_correction_hashes(
                graph_sha256,
                label="graph",
                expected_keys=frozenset({"target", "target_relationships"}),
            ),
            content_sha256=normalized_content,
            expires_at_monotonic=min(
                session.expires_at_monotonic,
                now + self.plan_ttl_seconds,
            ),
        )
        return ticket_id

    def consume_correction_plan(
        self,
        token: str,
        origin: str,
        ticket_id: str,
        *,
        confirm_permanent: bool = False,
    ) -> HomeCorrectionTicket:
        session = self.authorize(token, origin)
        ticket = session.plans.get(str(ticket_id))
        if not isinstance(ticket, HomeCorrectionTicket):
            raise HomeControlError(
                "Correction plan was not found or was already used.",
                code="CONTROL_PLAN_NOT_FOUND",
                status_code=409,
            )
        if ticket.expires_at_monotonic <= self._now():
            session.plans.pop(str(ticket_id), None)
            raise HomeControlError(
                "Correction plan expired; inspect the memory again.",
                code="CONTROL_PLAN_EXPIRED",
                status_code=409,
            )
        if ticket.action == "permanent_delete" and not confirm_permanent:
            raise HomeControlError(
                "Permanent deletion requires a separate final confirmation.",
                code="PERMANENT_CONFIRMATION_REQUIRED",
                status_code=400,
            )
        session.plans.pop(str(ticket_id), None)
        return ticket

    def create_recovery_plan_for_session(
        self,
        session: _HomeSession,
        *,
        action: str,
        layout_sha256: str | None = None,
        archive_name: str | None = None,
        archive_sha256: str | None = None,
        report_sha256: str | None = None,
        project_id: str | None = None,
        workspace_sha256: str | None = None,
    ) -> str:
        """Create one content-free lifecycle ticket after inspection."""
        if not any(candidate is session for candidate in self._sessions.values()):
            raise HomeControlError(
                "Home control session is invalid.",
                code="CONTROL_SESSION_INVALID",
                status_code=401,
            )
        selected = str(action).strip()
        if selected not in {"backup", "restore", "support_report"}:
            raise HomeControlError(
                "Home Recover action is not supported.",
                code="RECOVERY_ACTION_UNSUPPORTED",
                status_code=400,
            )
        selected_archive: str | None = None
        normalized_archive_sha256: str | None = None
        normalized_project_id: str | None = None
        normalized_workspace_sha256: str | None = None
        if selected == "restore":
            selected_archive = str(archive_name or "").strip()
            if (
                not selected_archive
                or len(selected_archive) > 255
                or "/" in selected_archive
                or "\\" in selected_archive
                or not selected_archive.lower().endswith(".zip")
            ):
                raise HomeControlError(
                    "Recover archive selection is invalid.",
                    code="RECOVERY_ARCHIVE_NAME_INVALID",
                    status_code=400,
                )
            normalized_archive_sha256 = self._validate_optional_digest(
                archive_sha256
            )
            if normalized_archive_sha256 is None:
                raise HomeControlError(
                    "Recover archive hash is invalid.",
                    code="CONTROL_PLAN_HASH_INVALID",
                    status_code=400,
                )
            try:
                normalized_project_id = str(UUID(str(project_id)))
            except (TypeError, ValueError) as error:
                raise HomeControlError(
                    "Restore project identity is invalid.",
                    code="CONTROL_PROJECT_INVALID",
                    status_code=400,
                ) from error
            if session.project_id != normalized_project_id:
                raise HomeControlError(
                    "Restore project does not match this Home session.",
                    code="CONTROL_PROJECT_MISMATCH",
                    status_code=409,
                )
            normalized_workspace_sha256 = self._validate_optional_digest(
                workspace_sha256
            )
            if normalized_workspace_sha256 is None:
                raise HomeControlError(
                    "Restore workspace binding is invalid.",
                    code="CONTROL_PLAN_HASH_INVALID",
                    status_code=400,
                )
        elif archive_name is not None or archive_sha256 is not None:
            raise HomeControlError(
                "This Recover plan cannot bind a restore archive.",
                code="CONTROL_PLAN_INVALID",
                status_code=400,
            )
        elif project_id is not None or workspace_sha256 is not None:
            raise HomeControlError(
                "This Recover plan cannot bind a project.",
                code="CONTROL_PLAN_INVALID",
                status_code=400,
            )
        normalized_layout: str | None = None
        normalized_report: str | None = None
        if selected == "support_report":
            if layout_sha256 is not None:
                raise HomeControlError(
                    "Support-report plans cannot bind a storage layout.",
                    code="CONTROL_PLAN_INVALID",
                    status_code=400,
                )
            normalized_report = self._validate_optional_digest(report_sha256)
            if normalized_report is None:
                raise HomeControlError(
                    "Support-report plan hash is invalid.",
                    code="CONTROL_PLAN_HASH_INVALID",
                    status_code=400,
                )
        else:
            if report_sha256 is not None:
                raise HomeControlError(
                    "Data recovery plans cannot bind a support report.",
                    code="CONTROL_PLAN_INVALID",
                    status_code=400,
                )
            normalized_layout = self._validate_optional_digest(layout_sha256)
            if normalized_layout is None:
                raise HomeControlError(
                    "Recover plan layout hash is invalid.",
                    code="CONTROL_PLAN_HASH_INVALID",
                    status_code=400,
                )
        now = self._now()
        session.plans = {
            key: plan
            for key, plan in session.plans.items()
            if plan.expires_at_monotonic > now
        }
        if len(session.plans) >= self.max_plans_per_session:
            oldest = min(
                session.plans,
                key=lambda key: session.plans[key].expires_at_monotonic,
            )
            session.plans.pop(oldest, None)
        ticket_id = str(self._token_factory())
        if len(ticket_id) < 8 or ticket_id in session.plans:
            raise RuntimeError("Home control token factory returned an unsafe plan ticket")
        session.plans[ticket_id] = HomeRecoveryTicket(
            ticket_id=ticket_id,
            action=selected,
            layout_sha256=normalized_layout,
            archive_name=selected_archive,
            archive_sha256=normalized_archive_sha256,
            report_sha256=normalized_report,
            project_id=normalized_project_id,
            workspace_sha256=normalized_workspace_sha256,
            expires_at_monotonic=min(
                session.expires_at_monotonic,
                now + self.plan_ttl_seconds,
            ),
        )
        return ticket_id

    def consume_recovery_plan(
        self,
        token: str,
        origin: str,
        ticket_id: str,
    ) -> HomeRecoveryTicket:
        session = self.authorize(token, origin)
        ticket = session.plans.get(str(ticket_id))
        if not isinstance(ticket, HomeRecoveryTicket):
            raise HomeControlError(
                "Recover plan was not found or was already used.",
                code="CONTROL_PLAN_NOT_FOUND",
                status_code=409,
            )
        session.plans.pop(str(ticket_id), None)
        if ticket.expires_at_monotonic <= self._now():
            raise HomeControlError(
                "Recover plan expired; inspect the operation again.",
                code="CONTROL_PLAN_EXPIRED",
                status_code=409,
            )
        return ticket

    def create_remember_plan_for_session(
        self,
        session: _HomeSession,
        *,
        project_id: str,
        knowledge_kind: str,
        content_sha256: str,
        question_sha256: str,
        overlap_sha256: Mapping[str, str],
    ) -> str:
        """Create one content-free ticket for an explicit keep-both choice."""
        if not any(candidate is session for candidate in self._sessions.values()):
            raise HomeControlError(
                "Home control session is invalid.",
                code="CONTROL_SESSION_INVALID",
                status_code=401,
            )
        try:
            normalized_project_id = str(UUID(str(project_id)))
        except (TypeError, ValueError) as error:
            raise HomeControlError(
                "Remember project identity is invalid.",
                code="CONTROL_PROJECT_INVALID",
                status_code=400,
            ) from error
        if session.project_id != normalized_project_id:
            raise HomeControlError(
                "Remember project does not match this Home session.",
                code="CONTROL_PROJECT_MISMATCH",
                status_code=409,
            )
        selected_kind = str(knowledge_kind).strip()
        if selected_kind not in {"decision", "constraint", "preference", "lesson"}:
            raise HomeControlError(
                "Remember kind is invalid.",
                code="REMEMBER_KIND_INVALID",
                status_code=400,
            )
        normalized_content = self._validate_optional_digest(content_sha256)
        normalized_question = self._validate_optional_digest(question_sha256)
        if normalized_content is None or normalized_question is None:
            raise HomeControlError(
                "Remember plan hashes are invalid.",
                code="CONTROL_PLAN_HASH_INVALID",
                status_code=400,
            )
        if not 1 <= len(overlap_sha256) <= 3:
            raise HomeControlError(
                "Remember overlap plan is invalid.",
                code="CONTROL_PLAN_INVALID",
                status_code=400,
            )
        normalized_overlaps: dict[str, str] = {}
        for memory_id, digest in overlap_sha256.items():
            try:
                normalized_id = str(UUID(str(memory_id)))
            except (TypeError, ValueError) as error:
                raise HomeControlError(
                    "Remember overlap identity is invalid.",
                    code="CONTROL_PLAN_INVALID",
                    status_code=400,
                ) from error
            normalized_digest = self._validate_optional_digest(str(digest))
            if normalized_digest is None:
                raise HomeControlError(
                    "Remember overlap hash is invalid.",
                    code="CONTROL_PLAN_HASH_INVALID",
                    status_code=400,
                )
            normalized_overlaps[normalized_id] = normalized_digest
        now = self._now()
        session.plans = {
            key: plan
            for key, plan in session.plans.items()
            if plan.expires_at_monotonic > now
        }
        if len(session.plans) >= self.max_plans_per_session:
            oldest = min(
                session.plans,
                key=lambda key: session.plans[key].expires_at_monotonic,
            )
            session.plans.pop(oldest, None)
        ticket_id = str(self._token_factory())
        if len(ticket_id) < 8 or ticket_id in session.plans:
            raise RuntimeError("Home control token factory returned an unsafe plan ticket")
        session.plans[ticket_id] = HomeRememberTicket(
            ticket_id=ticket_id,
            project_id=normalized_project_id,
            knowledge_kind=selected_kind,
            content_sha256=normalized_content,
            question_sha256=normalized_question,
            overlap_sha256=normalized_overlaps,
            expires_at_monotonic=min(
                session.expires_at_monotonic,
                now + self.plan_ttl_seconds,
            ),
        )
        return ticket_id

    def consume_remember_plan(
        self,
        token: str,
        origin: str,
        ticket_id: str,
        *,
        content: str,
        verification_question: str,
    ) -> HomeRememberTicket:
        """Consume one keep-both plan only when the private inputs still match."""
        session = self.authorize(token, origin)
        ticket = session.plans.get(str(ticket_id))
        if not isinstance(ticket, HomeRememberTicket):
            raise HomeControlError(
                "Remember plan was not found or was already used.",
                code="CONTROL_PLAN_NOT_FOUND",
                status_code=409,
            )
        if ticket.expires_at_monotonic <= self._now():
            session.plans.pop(str(ticket_id), None)
            raise HomeControlError(
                "Remember plan expired; inspect the overlap again.",
                code="CONTROL_PLAN_EXPIRED",
                status_code=409,
            )
        if (
            hashlib.sha256(str(content).encode("utf-8")).hexdigest()
            != ticket.content_sha256
            or hashlib.sha256(
                str(verification_question).encode("utf-8")
            ).hexdigest()
            != ticket.question_sha256
        ):
            raise HomeControlError(
                "Remember content changed; inspect the overlap again.",
                code="CONTROL_PLAN_STALE",
                status_code=409,
            )
        session.plans.pop(str(ticket_id), None)
        return ticket

    def create_project_assignment_plan_for_session(
        self,
        session: _HomeSession,
        *,
        memory_id: str,
        project_id: str,
        confirm_protected: bool,
        record_sha256: str,
        graph_existed: bool,
        graph_sha256: str | None,
        relationship_sha256: str,
        target_scope_sha256: str,
    ) -> str:
        """Create one content-free ticket for a legacy project assignment."""
        if not any(candidate is session for candidate in self._sessions.values()):
            raise HomeControlError(
                "Home control session is invalid.",
                code="CONTROL_SESSION_INVALID",
                status_code=401,
            )
        try:
            normalized_memory_id = str(UUID(str(memory_id)))
            normalized_project_id = str(UUID(str(project_id)))
        except (TypeError, ValueError) as error:
            raise HomeControlError(
                "Project assignment identity is invalid.",
                code="CONTROL_PLAN_INVALID",
                status_code=400,
            ) from error
        normalized_record = self._validate_optional_digest(record_sha256)
        normalized_graph = self._validate_optional_digest(graph_sha256)
        normalized_relationship = self._validate_optional_digest(
            relationship_sha256
        )
        normalized_scope = self._validate_optional_digest(target_scope_sha256)
        if (
            normalized_record is None
            or normalized_relationship is None
            or normalized_scope is None
            or (graph_existed and normalized_graph is None)
            or (not graph_existed and normalized_graph is not None)
        ):
            raise HomeControlError(
                "Project assignment plan hashes are invalid.",
                code="CONTROL_PLAN_HASH_INVALID",
                status_code=400,
            )
        now = self._now()
        session.plans = {
            key: plan
            for key, plan in session.plans.items()
            if plan.expires_at_monotonic > now
        }
        if len(session.plans) >= self.max_plans_per_session:
            oldest = min(
                session.plans,
                key=lambda key: session.plans[key].expires_at_monotonic,
            )
            session.plans.pop(oldest, None)
        ticket_id = str(self._token_factory())
        if len(ticket_id) < 8 or ticket_id in session.plans:
            raise RuntimeError("Home control token factory returned an unsafe plan ticket")
        session.plans[ticket_id] = HomeProjectAssignmentTicket(
            ticket_id=ticket_id,
            memory_id=normalized_memory_id,
            project_id=normalized_project_id,
            confirm_protected=bool(confirm_protected),
            record_sha256=normalized_record,
            graph_existed=bool(graph_existed),
            graph_sha256=normalized_graph,
            relationship_sha256=normalized_relationship,
            target_scope_sha256=normalized_scope,
            expires_at_monotonic=min(
                session.expires_at_monotonic,
                now + self.plan_ttl_seconds,
            ),
        )
        return ticket_id

    def consume_project_assignment_plan(
        self,
        token: str,
        origin: str,
        ticket_id: str,
    ) -> HomeProjectAssignmentTicket:
        """Consume one exact project-assignment plan once."""
        session = self.authorize(token, origin)
        ticket = session.plans.get(str(ticket_id))
        if not isinstance(ticket, HomeProjectAssignmentTicket):
            raise HomeControlError(
                "Project assignment plan was not found or was already used.",
                code="CONTROL_PLAN_NOT_FOUND",
                status_code=409,
            )
        session.plans.pop(str(ticket_id), None)
        if ticket.expires_at_monotonic <= self._now():
            raise HomeControlError(
                "Project assignment plan expired; inspect the memory again.",
                code="CONTROL_PLAN_EXPIRED",
                status_code=409,
            )
        return ticket


__all__ = [
    "DEFAULT_HOME_ORIGINS",
    "HomeControlError",
    "HomeControlGrant",
    "HomeControlRegistry",
    "HomeCorrectionTicket",
    "HomeProjectAssignmentTicket",
    "HomeRecoveryTicket",
    "HomeRememberTicket",
    "HomeResolveTicket",
]
