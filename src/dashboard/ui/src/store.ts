import { create } from 'zustand';
import type {
  Tab,
  Snapshot,
  StatsResponse,
  SessionIntelligenceResponse,
  MemoryNode,
  VisualizationType,
  ResolveApplyResponse,
  ResolvePlan,
  ResolvePlanResponse,
  ResolveReceipt,
  ResolveResolution,
  ResolveTerminalStatus,
  CorrectionAction,
  CorrectionApplyResponse,
  CorrectionPlan,
  CorrectionPlanResponse,
  CorrectionReceipt,
  CorrectionTerminalStatus,
  ProjectAction,
  ProjectAssignmentPlan,
  ProjectAssignmentReceipt,
  ProjectAssignmentResponse,
  ProjectAssignmentTerminalStatus,
  ProjectManageResponse,
  ProjectRegistrySnapshot,
  ProjectReviewMemory,
  ProjectReviewResponse,
  RegisteredProject,
  KnowledgeKind,
  RememberPlan,
  RememberReceipt,
  RememberResponse,
  RememberTerminalStatus,
  RecallTestResponse,
  RecoveryAction,
  RecoveryApplyResponse,
  RecoveryBackupArchive,
  RecoveryHealth,
  RecoveryHistoryEntry,
  PackageMaintenanceState,
  RecoveryPlan,
  RecoveryPlanResponse,
  RecoveryReceipt,
  RecoverySupportReportPreview,
  RecoveryTerminalStatus,
  ControlAvailability,
  SnapshotContext,
} from './types';

// All named controls share one fail-closed session state. Never replay a request.
async function fetchControl(url: string, init: RequestInit): Promise<Response> {
  const response = await fetch(url, init);
  const state = useDashboardStore.getState();
  if ((response.status === 401 || response.status === 429)
    && new Headers(init.headers).get('Authorization') === `Bearer ${state.controlToken}`) {
    useDashboardStore.setState({
      controlEnabled: false, controlBaseUrl: null, controlToken: null,
      controlAvailability: 'unavailable',
      controlSessionError: response.status === 401
        ? 'Local session expired. Reconnect Home to continue.'
        : 'Local session request limit reached. Reconnect Home to continue.',
    });
  }
  return response;
}

const CONTROL_TOKEN_MIN_LENGTH = 12;
const CONTROL_TOKEN_MAX_LENGTH = 256;
const RESOLVE_TERMINAL_STATUSES: readonly ResolveTerminalStatus[] = [
  'VERIFIED_COMPLETE',
  'FAILED_NO_CHANGE',
  'FAILED_ROLLED_BACK',
  'NEEDS_HUMAN',
  'UNSAFE',
];
const CORRECTION_ACTIONS: readonly CorrectionAction[] = [
  'edit',
  'replace',
  'archive',
  'restore',
  'permanent_delete',
];
const CORRECTION_TERMINAL_STATUSES: readonly CorrectionTerminalStatus[] = [
  'VERIFIED_COMPLETE',
  'FAILED_NO_CHANGE',
  'FAILED_ROLLED_BACK',
  'NEEDS_HUMAN',
  'UNSAFE',
];
const RECOVERY_TERMINAL_STATUSES: readonly RecoveryTerminalStatus[] = [
  'VERIFIED_COMPLETE',
  'FAILED_NO_CHANGE',
  'FAILED_ROLLED_BACK',
  'NEEDS_HUMAN',
  'UNSAFE',
];
const REMEMBER_TERMINAL_STATUSES: readonly RememberTerminalStatus[] = [
  'VERIFIED_COMPLETE',
  'FAILED_NO_CHANGE',
  'FAILED_ROLLED_BACK',
  'NEEDS_HUMAN',
  'UNSAFE',
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function normalizeSnapshotContext(value: unknown): SnapshotContext {
  if (
    isRecord(value)
    && value.mode === 'showcase'
    && value.label === 'Example workspace'
    && value.contains_user_data === false
  ) {
    return {
      mode: 'showcase',
      label: 'Example workspace',
      contains_user_data: false,
      source_grounded_content: value.source_grounded_content === true,
      synthetic_behavioral_metadata: value.synthetic_behavioral_metadata === true,
      disclaimer: 'Deterministic example data; counts and activity do not describe customer behavior or product performance.',
    };
  }
  return {
    mode: 'local_snapshot',
    label: 'Local snapshot',
    contains_user_data: null,
    source_grounded_content: null,
    synthetic_behavioral_metadata: null,
    disclaimer: 'Read-only snapshot evidence; live actions require a verified local control session.',
  };
}

function normalizeRegisteredProject(value: unknown, token: string | null): RegisteredProject | null {
  if (
    !isRecord(value)
    || typeof value.project_id !== 'string'
    || typeof value.name !== 'string'
    || typeof value.root !== 'string'
    || typeof value.active !== 'boolean'
  ) {
    return null;
  }

  const project: RegisteredProject = {
    project_id: safeText(value.project_id, token),
    name: safeText(value.name, token),
    root: safeText(value.root, token),
    active: value.active,
    root_status:
      value.root_status === 'available' || value.root_status === 'missing'
        ? value.root_status
        : 'unknown',
  };
  if (typeof value.created_at === 'string') project.created_at = safeText(value.created_at, token);
  if (typeof value.updated_at === 'string') project.updated_at = safeText(value.updated_at, token);
  return project;
}

function normalizeProjectRegistry(value: unknown, token: string | null): ProjectRegistrySnapshot | null {
  if (!isRecord(value)) return null;

  const status = value.status === 'ready'
    || value.status === 'invalid'
    || value.status === 'unavailable'
    ? value.status
    : null;
  const mode = value.mode === 'compatibility' || value.mode === 'strict' || value.mode === 'invalid'
    ? value.mode
    : null;
  const rawProjects = value.projects;
  const projects = Array.isArray(rawProjects)
    ? rawProjects.map((project) => normalizeRegisteredProject(project, token))
    : [];
  const hasInvalidProject = projects.some((project) => project === null);
  const schemaVersion = typeof value.schema_version === 'number' ? value.schema_version : null;
  const revision = typeof value.revision === 'number' ? value.revision : null;
  const errorCode = typeof value.error_code === 'string'
    ? safeText(value.error_code, token)
    : undefined;

  if (!status || !mode || !Array.isArray(rawProjects) || hasInvalidProject) {
    return {
      status: 'invalid',
      schema_version: schemaVersion,
      mode: 'invalid',
      revision,
      projects: [],
      error_code: errorCode || 'PROJECT_REGISTRY_INVALID',
    };
  }

  return {
    status,
    schema_version: schemaVersion,
    mode,
    revision,
    projects: projects.filter((project): project is RegisteredProject => project !== null),
    ...(errorCode ? { error_code: errorCode } : {}),
  };
}

function normalizeProjectReviewMemory(
  value: unknown,
  token: string | null,
): ProjectReviewMemory | null {
  if (
    !isRecord(value)
    || typeof value.memory_id !== 'string'
    || !isValidProjectId(value.memory_id)
    || typeof value.title !== 'string'
    || typeof value.summary !== 'string'
    || typeof value.memory_type !== 'string'
    || typeof value.status !== 'string'
    || typeof value.protected !== 'boolean'
    || typeof value.created_at !== 'string'
  ) {
    return null;
  }
  return {
    memory_id: safeText(value.memory_id, token),
    title: safeText(value.title, token),
    summary: safeText(value.summary, token),
    memory_type: safeText(value.memory_type, token),
    status: safeText(value.status, token),
    protected: value.protected,
    created_at: safeText(value.created_at, token),
  };
}

function normalizeProjectReview(
  value: unknown,
  token: string | null,
): ProjectReviewResponse | null {
  if (
    !isRecord(value)
    || value.success !== true
    || value.status !== 'READY'
    || typeof value.total_unscoped !== 'number'
    || typeof value.offset !== 'number'
    || typeof value.limit !== 'number'
    || typeof value.returned_count !== 'number'
    || typeof value.has_more !== 'boolean'
    || value.scan_complete !== true
    || typeof value.review_required !== 'boolean'
    || value.memory_content_returned !== false
    || !Array.isArray(value.memories)
  ) {
    return null;
  }
  const memories = value.memories.map((item) => normalizeProjectReviewMemory(item, token));
  if (memories.some((item) => item === null)) return null;
  return {
    success: true,
    status: 'READY',
    total_unscoped: Math.max(0, value.total_unscoped),
    offset: Math.max(0, value.offset),
    limit: Math.max(1, value.limit),
    returned_count: Math.max(0, value.returned_count),
    has_more: value.has_more,
    scan_complete: true,
    review_required: value.review_required,
    memories: memories.filter((item): item is ProjectReviewMemory => item !== null),
    memory_content_returned: false,
  };
}

function normalizeProjectAssignmentPlan(
  value: unknown,
  token: string | null,
): ProjectAssignmentPlan | null {
  if (
    !isRecord(value)
    || typeof value.memory_id !== 'string'
    || !isValidProjectId(value.memory_id)
    || typeof value.project_id !== 'string'
    || !isValidProjectId(value.project_id)
    || typeof value.project_name !== 'string'
    || typeof value.applicable !== 'boolean'
    || typeof value.reason !== 'string'
    || typeof value.protected !== 'boolean'
    || (value.reason_code !== null && typeof value.reason_code !== 'string')
  ) {
    return null;
  }
  return {
    ...(typeof value.schema_version === 'number'
      ? { schema_version: value.schema_version }
      : {}),
    memory_id: safeText(value.memory_id, token),
    project_id: safeText(value.project_id, token),
    project_name: safeText(value.project_name, token),
    applicable: value.applicable,
    reason_code: value.reason_code === null ? null : safeText(value.reason_code, token),
    reason: safeText(value.reason, token),
    protected: value.protected,
  };
}

function isResolveTerminalStatus(value: unknown): value is ResolveTerminalStatus {
  return typeof value === 'string' && RESOLVE_TERMINAL_STATUSES.includes(value as ResolveTerminalStatus);
}

function isCorrectionAction(value: unknown): value is CorrectionAction {
  return typeof value === 'string' && CORRECTION_ACTIONS.includes(value as CorrectionAction);
}

function isCorrectionTerminalStatus(value: unknown): value is CorrectionTerminalStatus {
  return typeof value === 'string'
    && CORRECTION_TERMINAL_STATUSES.includes(value as CorrectionTerminalStatus);
}

function isRecoveryTerminalStatus(value: unknown): value is RecoveryTerminalStatus {
  return typeof value === 'string'
    && RECOVERY_TERMINAL_STATUSES.includes(value as RecoveryTerminalStatus);
}

function isRememberTerminalStatus(value: unknown): value is RememberTerminalStatus {
  return typeof value === 'string'
    && REMEMBER_TERMINAL_STATUSES.includes(value as RememberTerminalStatus);
}

function safeText(value: unknown, token: string | null, fallback = ''): string {
  if (typeof value !== 'string') return fallback;
  return token ? value.split(token).join('[redacted]') : value;
}

function safeOptionalText(value: unknown, token: string | null): string | undefined {
  return typeof value === 'string' ? safeText(value, token) : undefined;
}

function safeNullableId(value: unknown, token: string | null): string | null {
  return typeof value === 'string' ? safeText(value, token) : null;
}

function isValidControlToken(value: string | null): value is string {
  return Boolean(
    value &&
      value.length >= CONTROL_TOKEN_MIN_LENGTH &&
      value.length <= CONTROL_TOKEN_MAX_LENGTH &&
      !/[\s\u0000-\u001f\u007f]/.test(value),
  );
}

function isValidProjectId(value: string | null): value is string {
  return Boolean(
    value
      && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value),
  );
}

function parseDaemonPort(value: string | null): number | null {
  if (!value || !/^\d{1,5}$/.test(value)) return null;
  const port = Number(value);
  return Number.isInteger(port) && port >= 1 && port <= 65535 ? port : null;
}

function normalizeResolvePlan(value: unknown, token: string | null): ResolvePlan | null {
  if (!isRecord(value) || typeof value.applicable !== 'boolean' || typeof value.reason !== 'string') {
    return null;
  }
  if (value.reason_code !== null && value.reason_code !== undefined && typeof value.reason_code !== 'string') {
    return null;
  }
  if (!isRecord(value.resolution) || typeof value.resolution.action !== 'string') {
    return null;
  }

  const resolution: ResolveResolution = {
    action: safeText(value.resolution.action, token),
    left_memory_id: safeNullableId(value.resolution.left_memory_id, token),
    right_memory_id: safeNullableId(value.resolution.right_memory_id, token),
    winner_memory_id: safeNullableId(value.resolution.winner_memory_id, token),
    loser_memory_id: safeNullableId(value.resolution.loser_memory_id, token),
    assessment: safeOptionalText(value.resolution.assessment, token),
    reason: safeOptionalText(value.resolution.reason, token),
    requires_user_winner:
      typeof value.resolution.requires_user_winner === 'boolean'
        ? value.resolution.requires_user_winner
        : undefined,
    protected_loser:
      typeof value.resolution.protected_loser === 'boolean'
        ? value.resolution.protected_loser
        : undefined,
  };

  return {
    applicable: value.applicable,
    reason_code: value.reason_code == null ? null : safeText(value.reason_code, token),
    reason: safeText(value.reason, token),
    resolution,
  };
}

function normalizeCorrectionPlan(value: unknown, token: string | null): CorrectionPlan | null {
  if (
    !isRecord(value)
    || !isCorrectionAction(value.action)
    || typeof value.memory_id !== 'string'
    || typeof value.applicable !== 'boolean'
    || typeof value.reason !== 'string'
    || typeof value.protected !== 'boolean'
    || typeof value.irreversible !== 'boolean'
  ) {
    return null;
  }

  if (
    value.reason_code !== null
    && value.reason_code !== undefined
    && typeof value.reason_code !== 'string'
  ) {
    return null;
  }

  const plan: CorrectionPlan = {
    action: value.action,
    memory_id: safeText(value.memory_id, token),
    applicable: value.applicable,
    reason_code: value.reason_code == null ? null : safeText(value.reason_code, token),
    reason: safeText(value.reason, token),
    protected: value.protected,
    irreversible: value.irreversible,
  };
  if (typeof value.schema_version === 'number') plan.schema_version = value.schema_version;
  return plan;
}

function normalizeChecks(value: unknown, token: string | null): ResolveReceipt['checks'] {
  if (!Array.isArray(value)) return undefined;
  return value.reduce<NonNullable<ResolveReceipt['checks']>>((checks, item) => {
    if (!isRecord(item) || typeof item.name !== 'string' || typeof item.passed !== 'boolean') {
      return checks;
    }
    checks.push({
      name: safeText(item.name, token),
      passed: item.passed,
      attempts: typeof item.attempts === 'number' ? item.attempts : 0,
      code: safeText(item.code, token),
    });
    return checks;
  }, []);
}

function normalizeStringRecord(value: unknown, token: string | null): Record<string, string> | undefined {
  if (!isRecord(value)) return undefined;
  const entries = Object.entries(value).filter(([, item]) => typeof item === 'string');
  if (entries.length === 0) return undefined;
  return Object.fromEntries(entries.map(([key, item]) => [safeText(key, token), safeText(item, token)]));
}

function normalizeReceipt(
  value: unknown,
  status: ResolveTerminalStatus,
  token: string | null,
): ResolveReceipt | undefined {
  if (!isRecord(value)) return undefined;
  const receipt: ResolveReceipt = { status };
  if (typeof value.schema_version === 'number') receipt.schema_version = value.schema_version;
  for (const key of ['operation_id', 'operation', 'authority', 'started_at', 'finished_at', 'scope_sha256', 'rollback']) {
    const safeValue = safeOptionalText(value[key], token);
    if (safeValue !== undefined) receipt[key] = safeValue;
  }
  const memoryIds = normalizeStringRecord(value.memory_ids, token);
  if (memoryIds) receipt.memory_ids = memoryIds;
  const recordHashes = normalizeStringRecord(value.record_sha256, token);
  if (recordHashes) receipt.record_sha256 = recordHashes;
  const checks = normalizeChecks(value.checks, token);
  if (checks) receipt.checks = checks;
  if (Array.isArray(value.error_codes)) {
    receipt.error_codes = value.error_codes
      .filter((code): code is string => typeof code === 'string')
      .map((code) => safeText(code, token));
  }
  if (typeof value.changed === 'boolean') receipt.changed = value.changed;
  return receipt;
}

function normalizeProjectAssignmentReceipt(
  value: unknown,
  status: ProjectAssignmentTerminalStatus,
  token: string | null,
): ProjectAssignmentReceipt | undefined {
  if (!isRecord(value)) return undefined;
  const receipt: ProjectAssignmentReceipt = { status };
  if (typeof value.schema_version === 'number') receipt.schema_version = value.schema_version;
  if (value.operation === 'assign_project') receipt.operation = 'assign_project';
  for (const key of ['operation_id', 'authority', 'started_at', 'finished_at', 'memory_id', 'project_id', 'rollback'] as const) {
    const item = safeOptionalText(value[key], token);
    if (item !== undefined) receipt[key] = item;
  }
  const checks = normalizeChecks(value.checks, token);
  if (checks) receipt.checks = checks;
  if (Array.isArray(value.error_codes)) {
    receipt.error_codes = value.error_codes
      .filter((code): code is string => typeof code === 'string')
      .map((code) => safeText(code, token));
  }
  if (typeof value.changed === 'boolean') receipt.changed = value.changed;
  return receipt;
}

function normalizeCorrectionReceipt(
  value: unknown,
  status: CorrectionTerminalStatus,
  token: string | null,
): CorrectionReceipt | undefined {
  const base = normalizeReceipt(value, status, token);
  if (!base) return undefined;

  const receipt: CorrectionReceipt = { ...base };
  const graphHashes = normalizeStringRecord(
    isRecord(value) ? value.graph_sha256 : undefined,
    token,
  );
  if (graphHashes) receipt.graph_sha256 = graphHashes;
  if (isRecord(value) && typeof value.recoverable === 'boolean') {
    receipt.recoverable = value.recoverable;
  }
  return receipt;
}

function normalizeRememberPlan(value: unknown, token: string | null): RememberPlan | null {
  if (
    !isRecord(value)
    || typeof value.applicable !== 'boolean'
    || typeof value.reason !== 'string'
    || !['decision', 'constraint', 'preference', 'lesson'].includes(
      String(value.knowledge_kind),
    )
    || typeof value.project_name !== 'string'
    || !Array.isArray(value.choices)
    || !Array.isArray(value.overlaps)
  ) {
    return null;
  }
  if (
    value.reason_code !== null
    && value.reason_code !== undefined
    && typeof value.reason_code !== 'string'
  ) {
    return null;
  }
  const choices = value.choices.filter(
    (choice): choice is 'update' | 'supersede' | 'keep_both' | 'cancel' => (
      choice === 'update'
      || choice === 'supersede'
      || choice === 'keep_both'
      || choice === 'cancel'
    ),
  );
  if (choices.length !== value.choices.length) return null;
  const overlaps = value.overlaps.reduce<RememberPlan['overlaps']>((items, item) => {
    if (
      !isRecord(item)
      || typeof item.memory_id !== 'string'
      || typeof item.title !== 'string'
      || !['duplicate', 'conflict', 'related'].includes(String(item.relation))
    ) {
      return items;
    }
    items.push({
      memory_id: safeText(item.memory_id, token),
      relation: item.relation as 'duplicate' | 'conflict' | 'related',
      title: safeText(item.title, token),
    });
    return items;
  }, []);
  if (overlaps.length !== value.overlaps.length) return null;
  return {
    applicable: value.applicable,
    reason_code: value.reason_code == null
      ? null
      : safeText(value.reason_code, token),
    reason: safeText(value.reason, token),
    knowledge_kind: value.knowledge_kind as KnowledgeKind,
    project_name: safeText(value.project_name, token),
    choices,
    overlaps,
  };
}

function normalizeRememberReceipt(
  value: unknown,
  status: RememberTerminalStatus,
  token: string | null,
): RememberReceipt | undefined {
  if (!isRecord(value)) return undefined;
  const receipt: RememberReceipt = { status };
  for (const key of ['operation_id', 'authority', 'project_id', 'project_name', 'rollback'] as const) {
    const item = safeOptionalText(value[key], token);
    if (item !== undefined) receipt[key] = item;
  }
  if (value.operation === 'remember') receipt.operation = 'remember';
  if (value.memory_id === null) receipt.memory_id = null;
  else if (typeof value.memory_id === 'string') receipt.memory_id = safeText(value.memory_id, token);
  if (['decision', 'constraint', 'preference', 'lesson'].includes(String(value.knowledge_kind))) {
    receipt.knowledge_kind = value.knowledge_kind as KnowledgeKind;
  }
  const checks = normalizeChecks(value.checks, token);
  if (checks) receipt.checks = checks;
  if (Array.isArray(value.error_codes)) {
    receipt.error_codes = value.error_codes
      .filter((code): code is string => typeof code === 'string')
      .map((code) => safeText(code, token));
  }
  if (typeof value.changed === 'boolean') receipt.changed = value.changed;
  if (typeof value.recoverable === 'boolean') receipt.recoverable = value.recoverable;
  return receipt;
}

function normalizeRemembered(
  value: unknown,
  token: string | null,
): RememberResponse['remembered'] | undefined {
  if (
    !isRecord(value)
    || typeof value.title !== 'string'
    || !['decision', 'constraint', 'preference', 'lesson'].includes(String(value.kind))
    || !isRecord(value.project)
    || typeof value.project.project_id !== 'string'
    || typeof value.project.name !== 'string'
    || typeof value.recall_verified !== 'boolean'
  ) {
    return undefined;
  }
  return {
    title: safeText(value.title, token),
    kind: value.kind as KnowledgeKind,
    project: {
      project_id: safeText(value.project.project_id, token),
      name: safeText(value.project.name, token),
    },
    recall_verified: value.recall_verified,
  };
}

function normalizeRecoveryPlan(value: unknown, token: string | null): RecoveryPlan | null {
  if (
    isRecord(value)
    && value.action === 'support_report'
    && typeof value.applicable === 'boolean'
    && typeof value.reason === 'string'
    && typeof value.estimated_bytes === 'number'
    && typeof value.irreversible === 'boolean'
  ) {
    const preview = normalizeSupportReportPreview(value.preview, token);
    if (!preview || !Array.isArray(value.included) || !Array.isArray(value.excluded)) {
      return null;
    }
    const included = value.included
      .filter((item): item is string => typeof item === 'string')
      .slice(0, 16)
      .map((item) => safeText(item, token));
    const excluded = value.excluded
      .filter((item): item is string => typeof item === 'string')
      .slice(0, 16)
      .map((item) => safeText(item, token));
    if (included.length !== value.included.length || excluded.length !== value.excluded.length) {
      return null;
    }
    return {
      ...(typeof value.schema_version === 'number'
        ? { schema_version: value.schema_version }
        : {}),
      action: 'support_report',
      applicable: value.applicable,
      reason_code: value.reason_code == null
        ? null
        : safeOptionalText(value.reason_code, token) ?? null,
      reason: safeText(value.reason, token),
      estimated_bytes: Math.max(0, value.estimated_bytes),
      irreversible: value.irreversible,
      preview,
      included,
      excluded,
    };
  }
  if (
    !isRecord(value)
    || (value.action !== 'backup' && value.action !== 'restore')
    || typeof value.applicable !== 'boolean'
    || typeof value.reason !== 'string'
    || (value.storage_layout !== 'managed' && value.storage_layout !== 'unsupported')
    || typeof value.data_directory !== 'string'
    || typeof value.backup_directory !== 'string'
    || typeof value.estimated_files !== 'number'
    || typeof value.estimated_bytes !== 'number'
    || typeof value.irreversible !== 'boolean'
  ) {
    return null;
  }
  if (
    value.reason_code !== null
    && value.reason_code !== undefined
    && typeof value.reason_code !== 'string'
  ) {
    return null;
  }
  return {
    ...(typeof value.schema_version === 'number'
      ? { schema_version: value.schema_version }
      : {}),
    action: value.action,
    applicable: value.applicable,
    reason_code: value.reason_code == null
      ? null
      : safeText(value.reason_code, token),
    reason: safeText(value.reason, token),
    storage_layout: value.storage_layout,
    data_directory: safeText(value.data_directory, token),
    backup_directory: safeText(value.backup_directory, token),
    estimated_files: Math.max(0, value.estimated_files),
    estimated_bytes: Math.max(0, value.estimated_bytes),
    irreversible: value.irreversible,
    ...(value.archive_name === null
      ? { archive_name: null }
      : typeof value.archive_name === 'string'
        ? { archive_name: safeText(value.archive_name, token) }
        : {}),
  };
}

function normalizeSupportReportPreview(
  value: unknown,
  token: string | null,
): RecoverySupportReportPreview | null {
  if (
    !isRecord(value)
    || typeof value.schema_version !== 'number'
    || !isRecord(value.product)
    || typeof value.product.recorded !== 'boolean'
    || !isRecord(value.environment)
    || !isRecord(value.readiness)
    || !isRecord(value.readiness.runtime)
    || !isRecord(value.readiness.daemon)
    || !isRecord(value.readiness.recall)
    || !isRecord(value.agent_connection)
    || !Array.isArray(value.agent_connection.detected)
    || !Array.isArray(value.agent_connection.verified)
    || !Array.isArray(value.agent_connection.uncovered)
    || !isRecord(value.installer_ownership)
    || !Array.isArray(value.diagnostic_codes)
    || !isRecord(value.backups)
    || typeof value.backups.valid !== 'number'
    || typeof value.backups.invalid !== 'number'
    || !isRecord(value.operation_receipts)
    || !Array.isArray(value.operation_receipts.recovery)
    || typeof value.operation_receipts.recovery_history_status !== 'string'
    || typeof value.operation_receipts.omitted_invalid_receipts !== 'number'
  ) {
    return null;
  }

  const stringList = (candidate: unknown, limit = 32): string[] | null => {
    if (!Array.isArray(candidate) || candidate.some((item) => typeof item !== 'string')) {
      return null;
    }
    return candidate.slice(0, limit).map((item) => safeText(item, token));
  };
  const detected = stringList(value.agent_connection.detected, 16);
  const verified = stringList(value.agent_connection.verified, 16);
  const uncovered = stringList(value.agent_connection.uncovered, 16);
  const diagnosticCodes = stringList(value.diagnostic_codes, 32);
  if (!detected || !verified || !uncovered || !diagnosticCodes) return null;

  const product: RecoverySupportReportPreview['product'] = {
    recorded: value.product.recorded,
  };
  for (const key of ['scope', 'version', 'source_commit', 'release_channel'] as const) {
    if (typeof value.product[key] === 'string') {
      product[key] = safeText(value.product[key], token);
    }
  }
  if (typeof value.product.source_clean === 'boolean') {
    product.source_clean = value.product.source_clean;
  }

  const environment = Object.fromEntries(
    Object.entries(value.environment)
      .filter((entry): entry is [string, string] => typeof entry[1] === 'string')
      .slice(0, 8)
      .map(([key, item]) => [safeText(key, token), safeText(item, token)]),
  );
  const runtime = Object.fromEntries(
    Object.entries(value.readiness.runtime)
      .filter((entry): entry is [string, boolean] => typeof entry[1] === 'boolean')
      .slice(0, 16)
      .map(([key, item]) => [safeText(key, token), item]),
  );
  const daemon = Object.fromEntries(
    Object.entries(value.readiness.daemon)
      .filter((entry): entry is [string, string | boolean] => (
        typeof entry[1] === 'string' || typeof entry[1] === 'boolean'
      ))
      .slice(0, 16)
      .map(([key, item]) => [
        safeText(key, token),
        typeof item === 'string' ? safeText(item, token) : item,
      ]),
  );
  const recall = Object.fromEntries(
    Object.entries(value.readiness.recall)
      .filter((entry): entry is [string, string | number | boolean | null] => (
        entry[1] === null
        || typeof entry[1] === 'string'
        || typeof entry[1] === 'number'
        || typeof entry[1] === 'boolean'
      ))
      .slice(0, 20)
      .map(([key, item]) => [
        safeText(key, token),
        typeof item === 'string' ? safeText(item, token) : item,
      ]),
  );
  const configuredSurfaces = stringList(value.installer_ownership.configured_surfaces, 32);
  const packageReceipt = isRecord(value.operation_receipts.package)
    ? value.operation_receipts.package
    : {};
  const recoveryReceipts = value.operation_receipts.recovery
    .filter(isRecord)
    .slice(0, 10);

  return {
    schema_version: value.schema_version,
    product,
    environment,
    readiness: {
      ready: typeof value.readiness.ready === 'boolean' ? value.readiness.ready : null,
      customer_ready: typeof value.readiness.customer_ready === 'boolean'
        ? value.readiness.customer_ready
        : null,
      runtime,
      daemon,
      recall,
    },
    agent_connection: { detected, verified, uncovered },
    installer_ownership: {
      ...(typeof value.installer_ownership.files === 'number'
        ? { files: Math.max(0, value.installer_ownership.files) }
        : {}),
      ...(typeof value.installer_ownership.host_registrations === 'number'
        ? { host_registrations: Math.max(0, value.installer_ownership.host_registrations) }
        : {}),
      ...(configuredSurfaces ? { configured_surfaces: configuredSurfaces } : {}),
    },
    diagnostic_codes: diagnosticCodes,
    backups: {
      valid: Math.max(0, value.backups.valid),
      invalid: Math.max(0, value.backups.invalid),
      latest_verified_at: value.backups.latest_verified_at == null
        ? null
        : safeOptionalText(value.backups.latest_verified_at, token) ?? null,
    },
    operation_receipts: {
      package: packageReceipt,
      recovery_history_status: safeText(
        value.operation_receipts.recovery_history_status,
        token,
      ),
      recovery: recoveryReceipts,
      omitted_invalid_receipts: Math.max(
        0,
        value.operation_receipts.omitted_invalid_receipts,
      ),
    },
  };
}

function normalizeRecoveryBackups(
  value: unknown,
  token: string | null,
): RecoveryBackupArchive[] {
  if (!Array.isArray(value)) return [];
  return value.reduce<RecoveryBackupArchive[]>((backups, item) => {
    if (
      !isRecord(item)
      || typeof item.archive_name !== 'string'
      || typeof item.valid !== 'boolean'
      || typeof item.files !== 'number'
      || typeof item.bytes !== 'number'
    ) {
      return backups;
    }
    backups.push({
      archive_name: safeText(item.archive_name, token),
      valid: item.valid,
      reason_code: item.reason_code == null
        ? null
        : safeOptionalText(item.reason_code, token),
      created_at: item.created_at == null
        ? null
        : safeOptionalText(item.created_at, token),
      files: Math.max(0, item.files),
      bytes: Math.max(0, item.bytes),
    });
    return backups;
  }, []);
}

function normalizePackageMaintenance(
  value: unknown,
  token: string | null,
): PackageMaintenanceState | null {
  if (
    !isRecord(value)
    || value.authority !== 'official_package'
    || value.handoff_required !== true
    || !['available', 'not_found', 'not_configured', 'invalid'].includes(String(value.status))
  ) {
    return null;
  }
  const status = value.status as PackageMaintenanceState['status'];
  if (status !== 'available') {
    return {
      authority: 'official_package',
      handoff_required: true,
      status,
    };
  }
  const rawReceipt = value.receipt;
  if (
    !isRecord(rawReceipt)
    || !['install', 'repair', 'update', 'rollback'].includes(String(rawReceipt.operation))
    || (rawReceipt.status !== 'RUNNING' && !isRecoveryTerminalStatus(rawReceipt.status))
  ) {
    return null;
  }
  const checks = normalizeChecks(rawReceipt.checks, token);
  if (!checks) return null;
  const receipt: NonNullable<PackageMaintenanceState['receipt']> = {
    operation: rawReceipt.operation as NonNullable<PackageMaintenanceState['receipt']>['operation'],
    status: rawReceipt.status,
    checks,
  };
  for (const key of ['operation_id', 'started_at', 'finished_at', 'rollback'] as const) {
    if (typeof rawReceipt[key] === 'string') {
      receipt[key] = safeText(rawReceipt[key], token);
    }
  }
  for (const key of ['previous_version', 'target_version'] as const) {
    const item = rawReceipt[key];
    if (item === null) receipt[key] = null;
    else if (typeof item === 'string') receipt[key] = safeText(item, token);
  }
  if (typeof rawReceipt.changed === 'boolean') receipt.changed = rawReceipt.changed;
  if (typeof rawReceipt.recoverable === 'boolean') receipt.recoverable = rawReceipt.recoverable;
  return {
    authority: 'official_package',
    handoff_required: true,
    status,
    receipt,
  };
}

function normalizeRecoveryHealth(
  value: unknown,
  token: string | null,
): RecoveryHealth | undefined {
  if (
    !isRecord(value)
    || !['READY', 'NEEDS_ATTENTION', 'RECOVERY_REQUIRED', 'UNSUPPORTED'].includes(
      String(value.state),
    )
    || typeof value.summary !== 'string'
    || typeof value.next_action !== 'string'
    || !Array.isArray(value.diagnostic_codes)
    || !Array.isArray(value.connected_agents)
    || value.connected_agents.some((agent) => typeof agent !== 'string')
    || typeof value.valid_backups !== 'number'
    || typeof value.invalid_backups !== 'number'
    || typeof value.backup_directory !== 'string'
  ) {
    return undefined;
  }
  const checks = normalizeChecks(value.checks, token) ?? [];
  const packageMaintenance = value.package_maintenance === undefined
    ? {
        authority: 'official_package' as const,
        handoff_required: true as const,
        status: 'not_configured' as const,
      }
    : normalizePackageMaintenance(value.package_maintenance, token) ?? {
        authority: 'official_package' as const,
        handoff_required: true as const,
        status: 'invalid' as const,
      };
  return {
    ...(typeof value.schema_version === 'number'
      ? { schema_version: value.schema_version }
      : {}),
    state: value.state as RecoveryHealth['state'],
    summary: safeText(value.summary, token),
    next_action: safeText(value.next_action, token),
    checked_at: safeOptionalText(value.checked_at, token),
    diagnostic_codes: value.diagnostic_codes
      .filter((code): code is string => typeof code === 'string')
      .slice(0, 32)
      .map((code) => safeText(code, token)),
    checks,
    connected_agents: value.connected_agents
      .slice(0, 16)
      .map((agent) => safeText(agent, token)),
    recall_verified_at: value.recall_verified_at == null
      ? null
      : safeOptionalText(value.recall_verified_at, token),
    valid_backups: Math.max(0, value.valid_backups),
    invalid_backups: Math.max(0, value.invalid_backups),
    latest_verified_backup_at: value.latest_verified_backup_at == null
      ? null
      : safeOptionalText(value.latest_verified_backup_at, token),
    backup_directory: safeText(value.backup_directory, token),
    package_maintenance: packageMaintenance,
  };
}

function normalizeRecoveryReceipt(
  value: unknown,
  status: RecoveryTerminalStatus,
  token: string | null,
): RecoveryReceipt | undefined {
  const base = normalizeReceipt(value, status, token);
  if (!base || !isRecord(value)) return undefined;
  const { operation: ignoredOperation, ...baseWithoutOperation } = base;
  void ignoredOperation;
  const receipt: RecoveryReceipt = {
    ...baseWithoutOperation,
    status,
    operation: value.operation === 'backup'
      || value.operation === 'restore'
      || value.operation === 'support_report'
      ? value.operation
      : undefined,
  };
  if (typeof value.layout_sha256 === 'string') {
    receipt.layout_sha256 = safeText(value.layout_sha256, token);
  }
  if (typeof value.report_sha256 === 'string') {
    receipt.report_sha256 = safeText(value.report_sha256, token);
  }
  for (const key of ['source_sha256', 'archive_sha256', 'archive_name'] as const) {
    const item = value[key];
    if (item === null) receipt[key] = null;
    else if (typeof item === 'string') receipt[key] = safeText(item, token);
  }
  if (typeof value.next_action === 'string') {
    receipt.next_action = safeText(value.next_action, token);
  }
  if (typeof value.files === 'number') receipt.files = Math.max(0, value.files);
  if (typeof value.bytes === 'number') receipt.bytes = Math.max(0, value.bytes);
  if (typeof value.recoverable === 'boolean') receipt.recoverable = value.recoverable;
  for (const key of [
    'safety_archive_name',
    'staging_name',
    'previous_data_name',
    'failed_restore_name',
  ] as const) {
    const item = value[key];
    if (item === null) receipt[key] = null;
    else if (typeof item === 'string') receipt[key] = safeText(item, token);
  }
  return receipt;
}

function normalizeRecoveryHistory(
  value: unknown,
  token: string | null,
): RecoveryHistoryEntry[] {
  if (!Array.isArray(value)) return [];
  return value.reduce<RecoveryHistoryEntry[]>((history, item) => {
    if (!isRecord(item)) return history;
    const rawStatus = item.status;
    if (rawStatus === 'RUNNING') {
      history.push({
        status: 'RUNNING',
        operation: item.operation === 'backup'
          || item.operation === 'restore'
          || item.operation === 'support_report'
          ? item.operation
          : undefined,
        operation_id: safeOptionalText(item.operation_id, token),
        authority: safeOptionalText(item.authority, token),
        started_at: safeOptionalText(item.started_at, token),
        finished_at: safeOptionalText(item.finished_at, token),
        archive_name: item.archive_name === null
          ? null
          : safeOptionalText(item.archive_name, token),
        next_action: safeOptionalText(item.next_action, token),
        changed: item.changed === true,
        recoverable: item.recoverable === true,
      });
      return history;
    }
    if (!isRecoveryTerminalStatus(rawStatus)) return history;
    const receipt = normalizeRecoveryReceipt(item, rawStatus, token);
    if (receipt) history.push({ ...receipt, status: rawStatus });
    return history;
  }, []);
}

async function readJson(response: Response): Promise<Record<string, unknown>> {
  try {
    const value: unknown = await response.json();
    return isRecord(value) ? value : {};
  } catch {
    return {};
  }
}

function controlErrorMessage(
  response: Response | null,
  body: Record<string, unknown>,
  token: string | null,
  operation: 'plan' | 'apply' | 'project' | 'recovery' | 'remember' | 'recall',
): string {
  const serverMessage = safeText(body.error, token).trim();
  if (serverMessage) return serverMessage.slice(0, 320);
  if (response?.status === 401) return 'Local session expired. Reload Home to reconnect.';
  if (response?.status === 403) return 'Management session is not authorized for this dashboard.';
  if (response?.status === 409) {
    if (operation === 'remember') {
      const receipt = isRecord(body.receipt) ? body.receipt : null;
      const errorCodes = receipt && Array.isArray(receipt.error_codes)
        ? receipt.error_codes.filter((code): code is string => typeof code === 'string')
        : [];
      if (errorCodes.includes('RECALL_POSTCONDITION_FAILED')) {
        return 'Elefante could not prove this memory would be recalled from that question. Nothing was saved.';
      }
      if (receipt?.status === 'FAILED_ROLLED_BACK' || receipt?.rollback === 'verified') {
        return 'Remember failed safely and Elefante verified the rollback. Nothing was saved.';
      }
      return 'The related knowledge changed. Inspect Remember again before choosing.';
    }
    if (operation === 'recall') {
      return 'Recall withheld this result because the project knowledge needs review.';
    }
    if (operation === 'recovery') {
      return 'The recovery plan is no longer current. Inspect the backup operation again.';
    }
    return operation === 'project'
      ? 'The Project Registry rejected this change. Inspect the registry and try again.'
      : 'The correction plan is no longer current. Inspect the memories and request a new plan.';
  }
  if (response?.status === 500) {
    if (operation === 'remember') {
      return 'Remember could not prove a safe terminal state. Inspect the receipt before retrying.';
    }
    if (operation === 'recovery') {
      return 'Recover could not verify a safe terminal state. Inspect the receipt before retrying.';
    }
    return operation === 'project'
      ? 'The control service could not apply this project change.'
      : 'The control service could not verify this correction.';
  }
  if (operation === 'project') return 'Could not reach the local control service for this project change.';
  if (operation === 'recovery') return 'Could not reach the local Recover service.';
  if (operation === 'remember') return 'Could not reach the local Remember service.';
  if (operation === 'recall') return 'Could not reach the local Recall service.';
  return operation === 'plan'
    ? 'Could not request a correction plan from the local control service.'
    : 'Could not reach the local control service for this correction.';
}

interface DashboardStore {
  // Navigation
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;
  memoryWorkspaceView: 'library' | 'review';
  setMemoryWorkspaceView: (view: 'library' | 'review') => void;

  // Data
  snapshot: Snapshot | null;
  stats: StatsResponse | null;
  sessionIntelligence: SessionIntelligenceResponse | null;
  isLoading: boolean;
  error: string | null;

  // Selection
  selectedMemoryIds: string[];
  selectMemory: (id: string) => void;
  deselectMemory: (id: string) => void;
  toggleMemory: (id: string) => void;
  clearSelection: () => void;
  selectAll: (ids: string[]) => void;

  // Filters
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  filterTopic: string;
  setFilterTopic: (t: string) => void;
  filterType: string;
  setFilterType: (t: string) => void;
  filterRing: string;
  setFilterRing: (r: string) => void;

  // Detail panel
  inspectedMemoryId: string | null;
  setInspectedMemoryId: (id: string | null) => void;

  // Explore tab
  activeVisualization: VisualizationType;
  setActiveVisualization: (v: VisualizationType) => void;

  // Actions
  fetchSnapshot: () => Promise<void>;
  fetchStats: () => Promise<void>;
  fetchSessionIntelligence: () => Promise<void>;
  refreshSnapshot: () => Promise<void>;
  isRefreshing: boolean;

  // Derived (computed helpers)
  getMemoryNodes: () => MemoryNode[];
  getTopics: () => string[];
  getMemoryTypes: () => string[];

  // Home management capability. The raw token is intentionally in-memory only.
  controlParsed: boolean;
  controlConnecting: boolean;
  controlSessionError: string | null;
  controlEnabled: boolean;
  controlAvailability: ControlAvailability;
  controlBaseUrl: string | null;
  controlToken: string | null;
  activeProjectId: string | null;
  initializeControlSession: (projectId?: string) => Promise<void>;
  projectRegistry: ProjectRegistrySnapshot | null;
  isProjectManaging: boolean;
  projectError: string | null;
  clearProjectError: () => void;
  manageProjects: (payload: ProjectAction) => Promise<ProjectManageResponse>;
  projectReview: ProjectReviewResponse | null;
  projectReviewError: string | null;
  isProjectReviewLoading: boolean;
  isProjectAssigning: boolean;
  clearProjectReviewError: () => void;
  fetchProjectReview: (offset?: number, limit?: number) => Promise<ProjectReviewResponse | null>;
  assignProjectMemory: (
    memoryId: string,
    projectId: string,
    confirmProtected: boolean,
  ) => Promise<ProjectAssignmentResponse>;
  isRemembering: boolean;
  rememberError: string | null;
  clearRememberError: () => void;
  remember: (
    content: string,
    knowledgeKind: KnowledgeKind,
    verificationQuestion: string,
  ) => Promise<RememberResponse>;
  keepBothMemories: (
    planId: string,
    content: string,
    verificationQuestion: string,
  ) => Promise<RememberResponse>;
  isRecallTesting: boolean;
  recallQuestion: string;
  recallResult: RecallTestResponse | null;
  setRecallQuestion: (question: string) => void;
  recallTestError: string | null;
  clearRecallTestError: () => void;
  testRecall: (question: string) => Promise<RecallTestResponse>;
  isResolvePlanning: boolean;
  isResolveApplying: boolean;
  resolveError: string | null;
  clearResolveError: () => void;
  requestResolvePlan: (
    memoryId: string,
    relatedMemoryId: string,
    winnerMemoryId: string | null,
    confirmProtected: boolean,
  ) => Promise<ResolvePlanResponse>;
  applyResolvePlan: (
    planId: string,
    reason: string,
    verificationQuestion: string,
  ) => Promise<ResolveApplyResponse>;
  isCorrectionPlanning: boolean;
  isCorrectionApplying: boolean;
  correctionError: string | null;
  clearCorrectionError: () => void;
  requestCorrectionPlan: (
    memoryId: string,
    correction: CorrectionAction,
    content: string | undefined,
    confirmProtected: boolean,
  ) => Promise<CorrectionPlanResponse>;
  applyCorrectionPlan: (
    planId: string,
    content: string | undefined,
    reason: string,
    verificationQuestion: string,
    confirmPermanent: boolean,
  ) => Promise<CorrectionApplyResponse>;
  isRecoveryPlanning: boolean;
  isRecoveryApplying: boolean;
  recoveryError: string | null;
  recoveryHistory: RecoveryHistoryEntry[];
  clearRecoveryError: () => void;
  requestRecoveryPlan: (
    action: RecoveryAction,
    archiveName?: string,
  ) => Promise<RecoveryPlanResponse>;
  applyRecoveryPlan: (
    planId: string,
    action: RecoveryAction,
    verificationQuestion?: string,
  ) => Promise<RecoveryApplyResponse>;
  downloadSupportReport: (
    archiveName: string,
  ) => Promise<{ success: boolean; error?: string }>;
}

export const useDashboardStore = create<DashboardStore>((set, get) => ({
  // Navigation
  activeTab: 'overview',
  setActiveTab: (tab) => set({ activeTab: tab }),
  memoryWorkspaceView: 'library',
  setMemoryWorkspaceView: (view) => set({ memoryWorkspaceView: view }),

  // Data
  snapshot: null,
  stats: null,
  sessionIntelligence: null,
  isLoading: false,
  isRefreshing: false,
  error: null,

  // Selection
  selectedMemoryIds: [],
  selectMemory: (id) => set((s) => ({
    selectedMemoryIds: s.selectedMemoryIds.includes(id)
      ? s.selectedMemoryIds
      : [...s.selectedMemoryIds, id],
  })),
  deselectMemory: (id) => set((s) => ({
    selectedMemoryIds: s.selectedMemoryIds.filter((x) => x !== id),
  })),
  toggleMemory: (id) => set((s) => ({
    selectedMemoryIds: s.selectedMemoryIds.includes(id)
      ? s.selectedMemoryIds.filter((x) => x !== id)
      : [...s.selectedMemoryIds, id],
  })),
  clearSelection: () => set({ selectedMemoryIds: [] }),
  selectAll: (ids) => set({ selectedMemoryIds: ids }),

  // Filters
  searchQuery: '',
  setSearchQuery: (q) => set({ searchQuery: q }),
  filterTopic: 'all',
  setFilterTopic: (t) => set({ filterTopic: t }),
  filterType: 'all',
  setFilterType: (t) => set({ filterType: t }),
  filterRing: 'all',
  setFilterRing: (r) => set({ filterRing: r }),

  // Detail panel
  inspectedMemoryId: null,
  setInspectedMemoryId: (id) => set({ inspectedMemoryId: id }),

  // Explore tab
  activeVisualization: 'treemap',
  setActiveVisualization: (v) => set({ activeVisualization: v }),

  // Home management capability
  controlParsed: false,
  controlConnecting: false,
  controlSessionError: null,
  controlEnabled: false,
  controlAvailability: 'checking',
  controlBaseUrl: null,
  controlToken: null,
  activeProjectId: null,
  projectRegistry: null,
  isProjectManaging: false,
  projectError: null,
  projectReview: null,
  projectReviewError: null,
  isProjectReviewLoading: false,
  isProjectAssigning: false,
  initializeControlSession: async (requestedProjectId) => {
    if (get().controlConnecting) return;
    if (requestedProjectId && !isValidProjectId(requestedProjectId)) {
      set({ controlSessionError: 'Choose a valid registered project.' });
      return;
    }
    if (
      get().controlEnabled
      && (!requestedProjectId || requestedProjectId === get().activeProjectId)
    ) return;

    if (requestedProjectId && requestedProjectId !== get().activeProjectId) {
      set({ recallQuestion: '', recallResult: null, recallTestError: null });
    }

    set({
      controlConnecting: true,
      controlAvailability: 'checking',
      controlSessionError: null,
    });

    let fragmentToken: string | null = null;
    let fragmentPort: number | null = null;
    let fragmentProjectId: string | null = null;
    if (!get().controlParsed && typeof window !== 'undefined') {
      set({ controlParsed: true });
      if (window.location.hash) {
        const fragment = window.location.hash;
        const params = new URLSearchParams(fragment.startsWith('#') ? fragment.slice(1) : fragment);
        fragmentToken = params.get('elefante_control')?.trim() ?? null;
        fragmentPort = parseDaemonPort(params.get('daemon_port'));
        fragmentProjectId = params.get('active_project_id')?.trim() ?? null;
        // Remove one-time context before any UI render can expose it again.
        window.history.replaceState(
          window.history.state,
          document.title,
          `${window.location.pathname}${window.location.search}`,
        );
      }
    }

    if (
      !requestedProjectId
      && isValidControlToken(fragmentToken)
      && fragmentPort !== null
    ) {
      set({
        controlConnecting: false,
        controlEnabled: true,
        controlAvailability: 'available',
        controlBaseUrl: `http://127.0.0.1:${fragmentPort}`,
        controlToken: fragmentToken,
        activeProjectId: isValidProjectId(fragmentProjectId) ? fragmentProjectId : null,
      });
      return;
    }

    try {
      const configResponse = await fetch('/api/control-config', {
        cache: 'no-store',
        credentials: 'omit',
        headers: { Accept: 'application/json' },
      });
      const config = await readJson(configResponse);
      const reasonCode = typeof config.reason_code === 'string' ? config.reason_code : null;
      if (configResponse.ok && config.available === false) {
        set({
          controlConnecting: false,
          controlEnabled: false,
          controlAvailability: reasonCode === 'CONTROL_ORIGIN_UNAVAILABLE'
            || reasonCode === 'SHOWCASE_SNAPSHOT_READ_ONLY'
            ? 'snapshot_only'
            : 'unavailable',
          controlBaseUrl: null,
          controlToken: null,
          activeProjectId: null,
          controlSessionError: null,
        });
        return;
      }
      const port = parseDaemonPort(
        typeof config.daemon_port === 'number' ? String(config.daemon_port) : null,
      );
      if (!configResponse.ok || config.available !== true || port === null) {
        throw new Error('control configuration unavailable');
      }

      const controlBaseUrl = `http://127.0.0.1:${port}`;
      const projectId = requestedProjectId
        || (isValidProjectId(fragmentProjectId) ? fragmentProjectId : null);
      const sessionResponse = await fetch(`${controlBaseUrl}/control/session`, {
        method: 'POST',
        cache: 'no-store',
        credentials: 'omit',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(projectId ? { project_id: projectId } : {}),
      });
      const session = await readJson(sessionResponse);
      const token = typeof session.token === 'string' ? session.token.trim() : null;
      const activeProjectId = typeof session.project_id === 'string'
        ? session.project_id.trim()
        : null;
      if (!sessionResponse.ok || session.success !== true || !isValidControlToken(token)) {
        const message = safeText(session.error, token).trim();
        throw new Error(message || 'local control session unavailable');
      }

      set({
        controlConnecting: false,
        controlEnabled: true,
        controlAvailability: 'available',
        controlBaseUrl,
        controlToken: token,
        activeProjectId: isValidProjectId(activeProjectId) ? activeProjectId : null,
        controlSessionError: null,
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message.trim() : '';
      set({
        controlConnecting: false,
        controlEnabled: false,
        controlAvailability: 'unavailable',
        controlBaseUrl: null,
        controlToken: null,
        activeProjectId: null,
        controlSessionError: detail
          && !detail.includes('control configuration')
          && !/failed to fetch|networkerror/i.test(detail)
          ? detail.slice(0, 320)
          : 'The live Elefante service could not be verified from this page.',
      });
    }
  },
  clearProjectError: () => set({ projectError: null }),
  manageProjects: async (payload) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ projectError: error });
      return { success: false, error, error_code: 'CONTROL_SESSION_UNAVAILABLE' };
    }

    set({ isProjectManaging: true, projectError: null });
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/projects/manage`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      const body = await readJson(response);
      const projectRegistry = normalizeProjectRegistry(body.project_registry, controlToken);
      const project = body.project === null
        ? null
        : normalizeRegisteredProject(body.project, controlToken);
      if (projectRegistry) {
        set((state) => ({
          projectRegistry,
          snapshot: state.snapshot
            ? { ...state.snapshot, project_registry: projectRegistry }
            : state.snapshot,
        }));
      }

      if (!response.ok || body.success !== true) {
        const error = controlErrorMessage(response, body, controlToken, 'project');
        set({ projectError: error });
        return {
          success: false,
          status: safeOptionalText(body.status, controlToken),
          changed: body.changed === true,
          project,
          project_registry: projectRegistry || undefined,
          error,
          error_code: safeOptionalText(body.error_code, controlToken),
        };
      }

      set({ projectError: null });
      return {
        success: true,
        status: safeOptionalText(body.status, controlToken),
        changed: body.changed === true,
        project,
        project_registry: projectRegistry || undefined,
        error: safeOptionalText(body.error, controlToken),
        error_code: safeOptionalText(body.error_code, controlToken),
      };
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'project');
      set({ projectError: error });
      return { success: false, error };
    } finally {
      set({ isProjectManaging: false });
    }
  },
  clearProjectReviewError: () => set({ projectReviewError: null }),
  fetchProjectReview: async (offset = 0, limit = 25) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ projectReviewError: error, projectReview: null });
      return null;
    }
    set({ isProjectReviewLoading: true, projectReviewError: null });
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/projects/unscoped/list`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ offset, limit }),
      });
      const body = await readJson(response);
      const review = normalizeProjectReview(body, controlToken);
      if (!response.ok || !review) {
        const error = controlErrorMessage(response, body, controlToken, 'project');
        set({ projectReviewError: error, projectReview: null });
        return null;
      }
      set({ projectReview: review, projectReviewError: null });
      return review;
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'project');
      set({ projectReviewError: error, projectReview: null });
      return null;
    } finally {
      set({ isProjectReviewLoading: false });
    }
  },
  assignProjectMemory: async (memoryId, projectId, confirmProtected) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ projectReviewError: error });
      return { success: false, error };
    }
    if (!isValidProjectId(memoryId) || !isValidProjectId(projectId)) {
      const error = 'Choose one valid unassigned memory and registered project.';
      set({ projectReviewError: error });
      return { success: false, error };
    }
    set({ isProjectAssigning: true, projectReviewError: null });
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/projects/unscoped/plan`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          memory_id: memoryId,
          project_id: projectId,
          confirm_protected: confirmProtected,
        }),
      });
      const planBody = await readJson(response);
      const plan = normalizeProjectAssignmentPlan(planBody.plan, controlToken);
      const planId = typeof planBody.plan_id === 'string'
        ? safeText(planBody.plan_id, controlToken)
        : null;
      if (!response.ok || planBody.success !== true || !plan) {
        const error = controlErrorMessage(response, planBody, controlToken, 'project');
        set({ projectReviewError: error });
        return {
          success: false,
          plan_id: planId,
          plan: plan || undefined,
          error,
          error_code: safeOptionalText(planBody.error_code, controlToken),
        };
      }
      if (!plan.applicable || !planId || planId.length < 8) {
        const error = plan.reason || 'This legacy memory needs review before assignment.';
        set({ projectReviewError: error });
        return {
          success: false,
          assignment_status: 'NEEDS_HUMAN',
          plan_id: planId,
          plan,
          error,
          error_code: plan.reason_code || undefined,
        };
      }

      response = await fetchControl(`${controlBaseUrl}/control/projects/unscoped/apply`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ plan_id: planId, confirm: true }),
      });
      const body = await readJson(response);
      const rawStatus = body.assignment_status ?? body.status;
      if (!isResolveTerminalStatus(rawStatus)) {
        const error = controlErrorMessage(response, body, controlToken, 'project');
        set({ projectReviewError: error });
        return { success: false, plan_id: null, plan, error };
      }
      const receipt = normalizeProjectAssignmentReceipt(
        body.receipt,
        rawStatus,
        controlToken,
      );
      const rawAssigned = body.assigned;
      const assigned = isRecord(rawAssigned)
        && typeof rawAssigned.memory_id === 'string'
        && typeof rawAssigned.title === 'string'
        && isRecord(rawAssigned.project)
        && typeof rawAssigned.project.project_id === 'string'
        && typeof rawAssigned.project.name === 'string'
        ? {
            memory_id: safeText(rawAssigned.memory_id, controlToken),
            title: safeText(rawAssigned.title, controlToken),
            project: {
              project_id: safeText(rawAssigned.project.project_id, controlToken),
              name: safeText(rawAssigned.project.name, controlToken),
            },
          }
        : undefined;
      const result: ProjectAssignmentResponse = {
        success: body.success === true,
        assignment_status: rawStatus,
        status: rawStatus,
        plan_id: null,
        plan,
        receipt,
        assigned,
        error: safeOptionalText(body.error, controlToken),
        error_code: safeOptionalText(body.error_code, controlToken),
      };
      if (
        rawStatus !== 'VERIFIED_COMPLETE'
        || !result.success
        || !receipt
        || !assigned
        || assigned.memory_id !== memoryId
        || assigned.project.project_id !== projectId
      ) {
        const error = result.error
          || controlErrorMessage(response, body, controlToken, 'project');
        set({ projectReviewError: error });
        result.error = error;
        return result;
      }
      await get().fetchSnapshot();
      const currentReview = get().projectReview;
      await get().fetchProjectReview(
        currentReview?.offset ?? 0,
        currentReview?.limit ?? 25,
      );
      set({ projectReviewError: null });
      return result;
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'project');
      set({ projectReviewError: error });
      return { success: false, error };
    } finally {
      set({ isProjectAssigning: false });
    }
  },
  isRemembering: false,
  rememberError: null,
  clearRememberError: () => set({ rememberError: null }),
  remember: async (content, knowledgeKind, verificationQuestion) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ rememberError: error });
      return { success: false, plan_id: null, error };
    }
    set({ isRemembering: true, rememberError: null });
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/remember`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content,
          knowledge_kind: knowledgeKind,
          verification_question: verificationQuestion,
        }),
      });
      const body = await readJson(response);
      const rawStatus = body.remember_status ?? body.status;
      const planId = body.plan_id === null || typeof body.plan_id === 'string'
        ? body.plan_id
        : null;
      if (!isRememberTerminalStatus(rawStatus)) {
        const error = controlErrorMessage(response, body, controlToken, 'remember');
        set({ rememberError: error });
        return {
          success: false,
          plan_id: null,
          error,
          error_code: safeOptionalText(body.error_code, controlToken),
        };
      }
      const plan = normalizeRememberPlan(body.plan, controlToken) ?? undefined;
      const receipt = normalizeRememberReceipt(body.receipt, rawStatus, controlToken);
      const remembered = normalizeRemembered(body.remembered, controlToken);
      const result: RememberResponse = {
        success: body.success === true,
        remember_status: rawStatus,
        plan_id: planId,
        plan,
        receipt,
        remembered,
        error: safeOptionalText(body.error, controlToken),
        error_code: safeOptionalText(body.error_code, controlToken),
      };
      if (
        rawStatus === 'NEEDS_HUMAN'
        && (!plan || !planId || plan.reason_code !== 'REMEMBER_OVERLAP_REQUIRES_CHOICE')
      ) {
        const error = 'Remember stopped, but its overlap plan was incomplete.';
        set({ rememberError: error });
        return { success: false, plan_id: null, error };
      }
      if (rawStatus === 'VERIFIED_COMPLETE' && (!result.success || !receipt || !remembered)) {
        const error = 'Remember did not return one complete verification receipt.';
        set({ rememberError: error });
        return { success: false, plan_id: null, error };
      }
      if (rawStatus === 'VERIFIED_COMPLETE') {
        await get().refreshSnapshot();
        set({ rememberError: null });
      } else if (rawStatus !== 'NEEDS_HUMAN') {
        const error = result.error || controlErrorMessage(response, body, controlToken, 'remember');
        set({ rememberError: error });
        result.error = error;
      }
      return result;
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'remember');
      set({ rememberError: error });
      return { success: false, plan_id: null, error };
    } finally {
      set({ isRemembering: false });
    }
  },
  keepBothMemories: async (planId, content, verificationQuestion) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ rememberError: error });
      return { success: false, plan_id: null, error };
    }
    set({ isRemembering: true, rememberError: null });
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/remember/apply`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          plan_id: planId,
          content,
          verification_question: verificationQuestion,
          choice: 'keep_both',
          confirm: true,
        }),
      });
      const body = await readJson(response);
      const rawStatus = body.remember_status ?? body.status;
      if (!isRememberTerminalStatus(rawStatus)) {
        const error = controlErrorMessage(response, body, controlToken, 'remember');
        set({ rememberError: error });
        return { success: false, plan_id: null, error };
      }
      const receipt = normalizeRememberReceipt(body.receipt, rawStatus, controlToken);
      const remembered = normalizeRemembered(body.remembered, controlToken);
      if (rawStatus !== 'VERIFIED_COMPLETE' || body.success !== true || !receipt || !remembered) {
        const error = safeOptionalText(body.error, controlToken)
          || controlErrorMessage(response, body, controlToken, 'remember');
        set({ rememberError: error });
        return {
          success: false,
          remember_status: rawStatus,
          plan_id: null,
          receipt,
          error,
          error_code: safeOptionalText(body.error_code, controlToken),
        };
      }
      await get().refreshSnapshot();
      set({ rememberError: null });
      return {
        success: true,
        remember_status: rawStatus,
        plan_id: null,
        receipt,
        remembered,
      };
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'remember');
      set({ rememberError: error });
      return { success: false, plan_id: null, error };
    } finally {
      set({ isRemembering: false });
    }
  },
  isRecallTesting: false,
  recallQuestion: '',
  recallResult: null,
  setRecallQuestion: (question) => set({ recallQuestion: question, recallResult: null, recallTestError: null }),
  recallTestError: null,
  clearRecallTestError: () => set({ recallTestError: null }),
  testRecall: async (question) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    const projectId = get().activeProjectId;
    const finish = (result: RecallTestResponse) => {
      if (get().recallQuestion.trim() === question && get().activeProjectId === projectId) {
        set({ recallResult: result });
      }
      return result;
    };
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ recallTestError: error });
      return finish({ success: false, recall_status: 'unavailable', error });
    }
    set({ isRecallTesting: true, recallTestError: null });
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/recall/test`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question }),
      });
      const body = await readJson(response);
      const status = body.recall_status;
      if (!['supplied', 'no_match', 'blocked', 'unavailable'].includes(String(status))) {
        const error = controlErrorMessage(response, body, controlToken, 'recall');
        set({ recallTestError: error });
        return finish({ success: false, recall_status: 'unavailable', error });
      }
      if (body.memory_content_returned !== false) {
        const error = 'Recall test rejected an unsafe response containing unverified content.';
        set({ recallTestError: error });
        return finish({ success: false, recall_status: 'unavailable', error });
      }
      const selectedIds = Array.isArray(body.selected_memory_ids)
        ? body.selected_memory_ids
          .filter((item): item is string => typeof item === 'string')
          .slice(0, 3)
          .map((item) => safeText(item, controlToken))
        : [];
      const project = isRecord(body.project)
        && typeof body.project.project_id === 'string'
        && typeof body.project.name === 'string'
        ? {
            project_id: safeText(body.project.project_id, controlToken),
            name: safeText(body.project.name, controlToken),
          }
        : undefined;
      const result: RecallTestResponse = {
        success: body.success === true,
        recall_status: status as RecallTestResponse['recall_status'],
        selected_count: typeof body.selected_count === 'number'
          ? Math.max(0, body.selected_count)
          : selectedIds.length,
        selected_memory_ids: selectedIds,
        conflict_count: typeof body.conflict_count === 'number'
          ? Math.max(0, body.conflict_count)
          : 0,
        delivery_blocked: body.delivery_blocked === true,
        verified_at: safeOptionalText(body.verified_at, controlToken),
        project,
        memory_content_returned: false,
        error: safeOptionalText(body.error, controlToken),
        error_code: safeOptionalText(body.error_code, controlToken),
      };
      if (!response.ok && status !== 'blocked') {
        result.error = result.error || controlErrorMessage(response, body, controlToken, 'recall');
      }
      set({ recallTestError: result.error || null });
      return finish(result);
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'recall');
      set({ recallTestError: error });
      return finish({ success: false, recall_status: 'unavailable', error });
    } finally {
      set({ isRecallTesting: false });
    }
  },
  isResolvePlanning: false,
  isResolveApplying: false,
  resolveError: null,
  clearResolveError: () => set({ resolveError: null }),
  requestResolvePlan: async (memoryId, relatedMemoryId, winnerMemoryId, confirmProtected) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ resolveError: error });
      return { success: false, plan_id: null, error, error_code: 'CONTROL_SESSION_UNAVAILABLE' };
    }

    set({ isResolvePlanning: true, resolveError: null });
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/resolve/plan`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          memory_id: memoryId,
          related_memory_id: relatedMemoryId,
          winner_memory_id: winnerMemoryId,
          confirm_protected: confirmProtected,
        }),
      });
      const body = await readJson(response);
      const plan = normalizeResolvePlan(body.plan, controlToken);
      const planId = body.plan_id === null || typeof body.plan_id === 'string' ? body.plan_id : null;
      if (!response.ok || body.success !== true || !plan) {
        const error = controlErrorMessage(response, body, controlToken, 'plan');
        set({ resolveError: error });
        return { success: false, plan_id: null, error, error_code: safeOptionalText(body.error_code, controlToken) };
      }
      set({ resolveError: null });
      return { success: true, plan_id: planId, plan };
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'plan');
      set({ resolveError: error });
      return { success: false, plan_id: null, error };
    } finally {
      set({ isResolvePlanning: false });
    }
  },
  applyResolvePlan: async (planId, reason, verificationQuestion) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ resolveError: error });
      return { success: false, error, error_code: 'CONTROL_SESSION_UNAVAILABLE' };
    }

    set({ isResolveApplying: true, resolveError: null });
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/resolve/apply`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          plan_id: planId,
          confirm: true,
          reason,
          verification_question: verificationQuestion,
        }),
      });
      const body = await readJson(response);
      const rawStatus = body.resolution_status ?? body.status;
      if (!isResolveTerminalStatus(rawStatus)) {
        const error = response.ok
          ? 'The control service did not return a terminal resolution status.'
          : controlErrorMessage(response, body, controlToken, 'apply');
        set({ resolveError: error });
        return { success: false, error, error_code: safeOptionalText(body.error_code, controlToken) };
      }

      const plan = normalizeResolvePlan(body.plan, controlToken) ?? undefined;
      const receipt = normalizeReceipt(body.receipt, rawStatus, controlToken);
      const result: ResolveApplyResponse = {
        success: body.success === true,
        resolution_status: rawStatus,
        status: isResolveTerminalStatus(body.status) ? body.status : undefined,
        plan,
        receipt,
        error: safeOptionalText(body.error, controlToken),
        error_code: safeOptionalText(body.error_code, controlToken),
      };

      set({ resolveError: result.error || null });
      return result;
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'apply');
      set({ resolveError: error });
      return { success: false, error };
    } finally {
      set({ isResolveApplying: false });
    }
  },
  isCorrectionPlanning: false,
  isCorrectionApplying: false,
  correctionError: null,
  clearCorrectionError: () => set({ correctionError: null }),
  requestCorrectionPlan: async (memoryId, correction, content, confirmProtected) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ correctionError: error });
      return { success: false, plan_id: null, error, error_code: 'CONTROL_SESSION_UNAVAILABLE' };
    }

    set({ isCorrectionPlanning: true, correctionError: null });
    let response: Response | null = null;
    try {
      const payload: Record<string, unknown> = {
        memory_id: memoryId,
        correction,
        confirm_protected: confirmProtected,
      };
      if (content !== undefined) payload.content = content;

      response = await fetchControl(`${controlBaseUrl}/control/corrections/plan`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      const body = await readJson(response);
      const plan = normalizeCorrectionPlan(body.plan, controlToken);
      const planId = body.plan_id === null || typeof body.plan_id === 'string' ? body.plan_id : null;
      if (!response.ok || body.success !== true || !plan) {
        const error = controlErrorMessage(response, body, controlToken, 'plan');
        set({ correctionError: error });
        return {
          success: false,
          plan_id: null,
          error,
          error_code: safeOptionalText(body.error_code, controlToken),
        };
      }
      set({ correctionError: null });
      return { success: true, plan_id: planId, plan };
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'plan');
      set({ correctionError: error });
      return { success: false, plan_id: null, error };
    } finally {
      set({ isCorrectionPlanning: false });
    }
  },
  applyCorrectionPlan: async (
    planId,
    content,
    reason,
    verificationQuestion,
    confirmPermanent,
  ) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ correctionError: error });
      return { success: false, error, error_code: 'CONTROL_SESSION_UNAVAILABLE' };
    }

    set({ isCorrectionApplying: true, correctionError: null });
    let response: Response | null = null;
    try {
      const payload: Record<string, unknown> = {
        plan_id: planId,
        confirm: true,
        reason,
        verification_question: verificationQuestion,
        confirm_permanent: confirmPermanent,
      };
      if (content !== undefined) payload.content = content;

      response = await fetchControl(`${controlBaseUrl}/control/corrections/apply`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      const body = await readJson(response);
      const rawStatus = body.correction_status ?? body.status;
      if (!isCorrectionTerminalStatus(rawStatus)) {
        const error = response.ok
          ? 'The control service did not return a terminal correction status.'
          : controlErrorMessage(response, body, controlToken, 'apply');
        set({ correctionError: error });
        return {
          success: false,
          error,
          error_code: safeOptionalText(body.error_code, controlToken),
        };
      }

      const plan = normalizeCorrectionPlan(body.plan, controlToken) ?? undefined;
      const receipt = normalizeCorrectionReceipt(body.receipt, rawStatus, controlToken);
      const result: CorrectionApplyResponse = {
        success: body.success === true,
        correction_status: rawStatus,
        status: isCorrectionTerminalStatus(body.status) ? body.status : undefined,
        plan,
        receipt,
        error: safeOptionalText(body.error, controlToken),
        error_code: safeOptionalText(body.error_code, controlToken),
      };

      set({ correctionError: result.error || null });
      return result;
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'apply');
      set({ correctionError: error });
      return { success: false, error };
    } finally {
      set({ isCorrectionApplying: false });
    }
  },
  isRecoveryPlanning: false,
  isRecoveryApplying: false,
  recoveryError: null,
  recoveryHistory: [],
  clearRecoveryError: () => set({ recoveryError: null }),
  requestRecoveryPlan: async (action, archiveName) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ recoveryError: error });
      return { success: false, plan_id: null, error, error_code: 'CONTROL_SESSION_UNAVAILABLE' };
    }

    set({ isRecoveryPlanning: true, recoveryError: null });
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/recovery/plan`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action,
          ...(archiveName ? { archive_name: archiveName } : {}),
        }),
      });
      const body = await readJson(response);
      const plan = normalizeRecoveryPlan(body.plan, controlToken);
      const health = normalizeRecoveryHealth(body.health, controlToken);
      const availableBackups = normalizeRecoveryBackups(
        body.available_backups,
        controlToken,
      );
      const planId = body.plan_id === null || typeof body.plan_id === 'string'
        ? body.plan_id
        : null;
      const history = normalizeRecoveryHistory(body.recovery_history, controlToken);
      set({ recoveryHistory: history });
      const requiresPlan = action === 'backup'
        || action === 'support_report'
        || Boolean(archiveName);
      const requiresHealth = action === 'health';
      if (
        !response.ok
        || body.success !== true
        || (requiresPlan && !plan)
        || (requiresHealth && !health)
      ) {
        const error = controlErrorMessage(response, body, controlToken, 'recovery');
        set({ recoveryError: error });
        return {
          success: false,
          plan_id: null,
          ...(health ? { health } : {}),
          available_backups: availableBackups,
          recovery_history: history,
          error,
          error_code: safeOptionalText(body.error_code, controlToken),
        };
      }
      set({ recoveryError: null });
      return {
        success: true,
        plan_id: planId,
        ...(plan ? { plan } : {}),
        ...(health ? { health } : {}),
        available_backups: availableBackups,
        recovery_history: history,
      };
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'recovery');
      set({ recoveryError: error });
      return { success: false, plan_id: null, error };
    } finally {
      set({ isRecoveryPlanning: false });
    }
  },
  applyRecoveryPlan: async (planId, action, verificationQuestion) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ recoveryError: error });
      return { success: false, error, error_code: 'CONTROL_SESSION_UNAVAILABLE' };
    }

    set({ isRecoveryApplying: true, recoveryError: null });
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/recovery/apply`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          plan_id: planId,
          action,
          confirm: true,
          ...(action === 'restore'
            ? { verification_question: verificationQuestion || '' }
            : {}),
        }),
      });
      const body = await readJson(response);
      const rawStatus = body.recovery_status ?? body.status;
      if (!isRecoveryTerminalStatus(rawStatus)) {
        const error = controlErrorMessage(response, body, controlToken, 'recovery');
        set({ recoveryError: error });
        return {
          success: false,
          error,
          error_code: safeOptionalText(body.error_code, controlToken),
        };
      }

      const plan = normalizeRecoveryPlan(body.plan, controlToken) ?? undefined;
      const receipt = normalizeRecoveryReceipt(body.receipt, rawStatus, controlToken);
      const history = normalizeRecoveryHistory(body.recovery_history, controlToken);
      set({ recoveryHistory: history });
      const result: RecoveryApplyResponse = {
        success: body.success === true,
        recovery_status: rawStatus,
        status: isRecoveryTerminalStatus(body.status) ? body.status : undefined,
        plan,
        receipt,
        recovery_history: history,
        error: safeOptionalText(body.error, controlToken),
        error_code: safeOptionalText(body.error_code, controlToken),
      };
      if (
        action === 'restore'
        && rawStatus === 'VERIFIED_COMPLETE'
        && result.success
        && receipt
      ) {
        set({ selectedMemoryIds: [], inspectedMemoryId: null });
        await get().refreshSnapshot();
      }
      set({ recoveryError: result.error || null });
      return result;
    } catch {
      const error = controlErrorMessage(response, {}, controlToken, 'recovery');
      set({ recoveryError: error });
      return { success: false, error };
    } finally {
      set({ isRecoveryApplying: false });
    }
  },
  downloadSupportReport: async (archiveName) => {
    const { controlEnabled, controlBaseUrl, controlToken } = get();
    if (!controlEnabled || !controlBaseUrl || !controlToken) {
      const error = 'Local session is not active. Reload Home to reconnect.';
      set({ recoveryError: error });
      return { success: false, error };
    }
    let response: Response | null = null;
    try {
      response = await fetchControl(`${controlBaseUrl}/control/recovery/support-report/download`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${controlToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ archive_name: archiveName }),
      });
      if (!response.ok) {
        const body = await readJson(response);
        const error = controlErrorMessage(response, body, controlToken, 'recovery');
        set({ recoveryError: error });
        return { success: false, error };
      }
      const blob = await response.blob();
      const contentType = response.headers.get('content-type') || '';
      if (
        blob.size === 0
        || blob.size > 1024 * 1024
        || !contentType.toLowerCase().startsWith('application/zip')
      ) {
        const error = 'The support report download failed its local response check.';
        set({ recoveryError: error });
        return { success: false, error };
      }
      const objectUrl = URL.createObjectURL(blob);
      try {
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = archiveName;
        link.rel = 'noopener';
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      } catch (error) {
        URL.revokeObjectURL(objectUrl);
        throw error;
      }
      set({ recoveryError: null });
      return { success: true };
    } catch {
      const error = 'The support report was created, but Home could not download it.';
      set({ recoveryError: error });
      return { success: false, error };
    }
  },

  // Actions
  fetchSnapshot: async () => {
    // Only the initial snapshot load may replace the active surface with the
    // loading screen. Background refreshes after verified customer actions
    // must preserve local UI state such as the Remember receipt.
    set({ isLoading: get().snapshot === null, error: null });
    const maxRetries = 4;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const res = await fetch('/api/graph');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const projectRegistry = normalizeProjectRegistry(data.project_registry, get().controlToken);
        const snapshotContext = normalizeSnapshotContext(data.snapshot_context);
        if (get().snapshot?.generated_at !== data.generated_at) set({ recallResult: null });
        set({ 
          snapshot: { 
            nodes: data.nodes || [], 
            edges: data.edges || [], 
            stats: data.stats,
            snapshot_context: snapshotContext,
            ...(typeof data.generated_at === 'string' ? { generated_at: data.generated_at } : {}),
            ...(projectRegistry ? { project_registry: projectRegistry } : {}),
            ...(typeof data.project_registry_generated_at === 'string'
              ? { project_registry_generated_at: data.project_registry_generated_at }
              : {}),
          }, 
          projectRegistry,
          isLoading: false,
          error: null,
        });
        return;
      } catch (e: any) {
        if (attempt < maxRetries) {
          // Exponential backoff: 1s, 2s, 4s, 8s
          await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, attempt)));
        } else {
          set({ error: e.message, isLoading: false });
        }
      }
    }
  },

  fetchStats: async () => {
    const maxRetries = 4;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const res = await fetch('/api/stats');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        set({ stats: data });
        return;
      } catch (e: any) {
        if (attempt < maxRetries) {
          await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, attempt)));
        } else {
          console.error('Failed to fetch stats after retries:', e);
        }
      }
    }
  },

  fetchSessionIntelligence: async () => {
    try {
      const res = await fetch('/api/session-intelligence');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      set({ sessionIntelligence: data });
    } catch (e) {
      console.error('Failed to fetch Session Intelligence snapshot:', e);
    }
  },

  refreshSnapshot: async () => {
    set({ isRefreshing: true, error: null });
    try {
      // The dashboard is an inspection surface. Reload only the existing
      // snapshot; live regeneration belongs to the explicit MCP or CLI path.
      await get().fetchStats();
      await get().fetchSessionIntelligence();
      await get().fetchSnapshot();
    } catch (e: any) {
      set({ error: `Snapshot reload failed: ${e.message}` });
    } finally {
      set({ isRefreshing: false });
    }
  },

  // Derived
  getMemoryNodes: () => {
    const snap = get().snapshot;
    if (!snap) return [];
    return snap.nodes.filter((n): n is MemoryNode => n.type === 'memory');
  },

  getTopics: () => {
    const memories = get().getMemoryNodes();
    const topics = new Set(memories.map((m) => m.properties?.topic || 'general'));
    return Array.from(topics).sort();
  },

  getMemoryTypes: () => {
    const memories = get().getMemoryNodes();
    const types = new Set(memories.map((m) => m.properties?.memory_type || 'unknown'));
    return Array.from(types).sort();
  },
}));
