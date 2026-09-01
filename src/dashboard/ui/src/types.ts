
export type MemoryHealthStatus = 'healthy' | 'stale' | 'at_risk' | 'orphan';

export interface UsageSummary {
  total_accesses: number;
  retrieved_memories: number;
  never_retrieved: number;
  retrieval_rate: number;
  average_access_count: number;
  max_access_count: number;
}

export type ProjectRegistryStatus = 'ready' | 'invalid' | 'unavailable';
export type ProjectRegistryMode = 'compatibility' | 'strict' | 'invalid';

export interface RegisteredProject {
  project_id: string;
  name: string;
  root: string;
  active: boolean;
  root_status?: 'available' | 'missing' | 'unknown';
  created_at?: string;
  updated_at?: string;
}

export interface ProjectRegistrySnapshot {
  status: ProjectRegistryStatus;
  schema_version: number | null;
  mode: ProjectRegistryMode;
  revision: number | null;
  scope_policy?: 'isolated';
  shared_across_projects?: false;
  projects: RegisteredProject[];
  error_code?: string;
}

export type ProjectAction =
  | { action: 'register'; name: string; root: string }
  | {
      action: 'update';
      project_id: string;
      name?: string;
      root?: string;
      active?: boolean;
    }
  | { action: 'remove'; project_id: string; confirm: true }
  | { action: 'set_mode'; mode: 'strict'; confirm: true };

export interface ProjectManageResponse {
  success: boolean;
  status?: string;
  changed?: boolean;
  project?: RegisteredProject | null;
  project_registry?: ProjectRegistrySnapshot;
  error?: string;
  error_code?: string;
}

export interface ProjectReviewMemory {
  memory_id: string;
  title: string;
  summary: string;
  memory_type: string;
  status: string;
  protected: boolean;
  created_at: string;
}

export interface ProjectReviewResponse {
  success: boolean;
  status?: 'READY' | 'SCAN_LIMIT_REACHED' | 'PROJECT_REVIEW_REJECTED';
  total_unscoped: number;
  offset: number;
  limit: number;
  returned_count: number;
  has_more: boolean;
  scan_complete: boolean;
  review_required: boolean;
  memories: ProjectReviewMemory[];
  memory_content_returned?: false;
  error?: string;
  error_code?: string;
}

export type ProjectAssignmentTerminalStatus = ResolveTerminalStatus;

export interface ProjectAssignmentPlan {
  schema_version?: number;
  memory_id: string;
  project_id: string;
  project_name: string;
  applicable: boolean;
  reason_code: string | null;
  reason: string;
  protected: boolean;
}

export interface ProjectAssignmentReceipt {
  schema_version?: number;
  operation_id?: string;
  operation?: 'assign_project';
  status: ProjectAssignmentTerminalStatus;
  authority?: string;
  started_at?: string;
  finished_at?: string;
  memory_id?: string;
  project_id?: string;
  checks?: ResolveCheck[];
  error_codes?: string[];
  rollback?: string;
  changed?: boolean;
}

export interface ProjectAssignmentResponse {
  success: boolean;
  assignment_status?: ProjectAssignmentTerminalStatus;
  status?: ProjectAssignmentTerminalStatus;
  plan_id?: string | null;
  plan?: ProjectAssignmentPlan;
  receipt?: ProjectAssignmentReceipt;
  assigned?: {
    memory_id: string;
    title: string;
    project: { project_id: string; name: string };
  };
  error?: string;
  error_code?: string;
}

export type KnowledgeKind = 'decision' | 'constraint' | 'preference' | 'lesson';
export type RememberTerminalStatus = ResolveTerminalStatus;

export interface RememberOverlap {
  memory_id: string;
  relation: 'duplicate' | 'conflict' | 'related';
  title: string;
}

export interface RememberPlan {
  applicable: boolean;
  reason_code: string | null;
  reason: string;
  knowledge_kind: KnowledgeKind;
  project_name: string;
  choices: Array<'update' | 'supersede' | 'keep_both' | 'cancel'>;
  overlaps: RememberOverlap[];
}

export interface RememberReceipt {
  status: RememberTerminalStatus;
  operation_id?: string;
  operation?: 'remember';
  authority?: string;
  memory_id?: string | null;
  knowledge_kind?: KnowledgeKind;
  project_id?: string;
  project_name?: string;
  checks?: ResolveCheck[];
  error_codes?: string[];
  rollback?: string;
  changed?: boolean;
  recoverable?: boolean;
}

export interface RememberResponse {
  success: boolean;
  remember_status?: RememberTerminalStatus | 'CANCELLED';
  plan_id: string | null;
  plan?: RememberPlan;
  receipt?: RememberReceipt;
  remembered?: {
    title: string;
    kind: KnowledgeKind;
    project: { project_id: string; name: string };
    recall_verified: boolean;
  };
  error?: string;
  error_code?: string;
}

export interface RecallTestResponse {
  success: boolean;
  recall_status?: 'supplied' | 'no_match' | 'blocked' | 'unavailable';
  selected_count?: number;
  selected_memory_ids?: string[];
  conflict_count?: number;
  delivery_blocked?: boolean;
  verified_at?: string;
  project?: { project_id: string; name: string };
  memory_content_returned?: false;
  error?: string;
  error_code?: string;
}

export type ResolveTerminalStatus =
  | 'VERIFIED_COMPLETE'
  | 'FAILED_NO_CHANGE'
  | 'FAILED_ROLLED_BACK'
  | 'NEEDS_HUMAN'
  | 'UNSAFE';

export interface ResolveResolution {
  action: string;
  left_memory_id?: string | null;
  right_memory_id?: string | null;
  winner_memory_id: string | null;
  loser_memory_id: string | null;
  assessment?: string;
  reason?: string;
  requires_user_winner?: boolean;
  protected_loser?: boolean;
  [key: string]: unknown;
}

export interface ResolvePlan {
  applicable: boolean;
  reason_code: string | null;
  reason: string;
  resolution: ResolveResolution;
  [key: string]: unknown;
}

export interface ResolveCheck {
  name: string;
  passed: boolean;
  attempts: number;
  code: string;
}

export type CorrectionAction = 'edit' | 'replace' | 'archive' | 'restore' | 'permanent_delete';
export type CorrectionTerminalStatus = ResolveTerminalStatus;
export type CorrectionCheck = ResolveCheck;

export interface CorrectionPlan {
  schema_version?: number;
  action: CorrectionAction;
  memory_id: string;
  applicable: boolean;
  reason_code: string | null;
  reason: string;
  protected: boolean;
  irreversible: boolean;
  [key: string]: unknown;
}

export interface CorrectionReceipt {
  schema_version?: number;
  operation_id?: string;
  operation?: string;
  status: CorrectionTerminalStatus;
  authority?: string;
  started_at?: string;
  finished_at?: string;
  memory_ids?: Record<string, string>;
  scope_sha256?: string;
  record_sha256?: Record<string, string>;
  graph_sha256?: Record<string, string>;
  checks?: CorrectionCheck[];
  error_codes?: string[];
  rollback?: string;
  changed?: boolean;
  recoverable?: boolean;
  [key: string]: unknown;
}

export interface CorrectionPlanResponse {
  success: boolean;
  plan_id: string | null;
  plan?: CorrectionPlan;
  error?: string;
  error_code?: string;
  [key: string]: unknown;
}

export interface CorrectionApplyResponse {
  success: boolean;
  correction_status?: CorrectionTerminalStatus;
  status?: CorrectionTerminalStatus;
  plan?: CorrectionPlan;
  receipt?: CorrectionReceipt;
  error?: string;
  error_code?: string;
  [key: string]: unknown;
}

export type RecoveryTerminalStatus = ResolveTerminalStatus;
export type RecoveryAction = 'health' | 'backup' | 'restore' | 'support_report';
export type RecoveryHealthState =
  | 'READY'
  | 'NEEDS_ATTENTION'
  | 'RECOVERY_REQUIRED'
  | 'UNSUPPORTED';

export type PackageMaintenanceOperation = 'install' | 'repair' | 'update' | 'rollback';

export interface PackageMaintenanceReceipt {
  operation: PackageMaintenanceOperation;
  status: RecoveryTerminalStatus | 'RUNNING';
  operation_id?: string;
  started_at?: string;
  finished_at?: string;
  previous_version?: string | null;
  target_version?: string | null;
  checks: ResolveCheck[];
  changed?: boolean;
  rollback?: string;
  recoverable?: boolean;
}

export interface PackageMaintenanceState {
  authority: 'official_package';
  handoff_required: true;
  status: 'available' | 'not_found' | 'not_configured' | 'invalid';
  receipt?: PackageMaintenanceReceipt;
}

export interface RecoveryHealth {
  schema_version?: number;
  state: RecoveryHealthState;
  summary: string;
  next_action: string;
  checked_at?: string;
  diagnostic_codes: string[];
  checks: ResolveCheck[];
  connected_agents: string[];
  recall_verified_at?: string | null;
  valid_backups: number;
  invalid_backups: number;
  latest_verified_backup_at?: string | null;
  backup_directory: string;
  package_maintenance: PackageMaintenanceState;
}

export interface RecoveryBackupArchive {
  archive_name: string;
  valid: boolean;
  reason_code?: string | null;
  created_at?: string | null;
  files: number;
  bytes: number;
}

export interface RecoveryPlan {
  schema_version?: number;
  action: RecoveryAction;
  applicable: boolean;
  reason_code: string | null;
  reason: string;
  storage_layout?: 'managed' | 'unsupported';
  data_directory?: string;
  backup_directory?: string;
  estimated_files?: number;
  estimated_bytes: number;
  irreversible: boolean;
  archive_name?: string | null;
  preview?: RecoverySupportReportPreview;
  included?: string[];
  excluded?: string[];
}

export interface RecoverySupportReportPreview {
  schema_version: number;
  product: {
    recorded: boolean;
    scope?: string;
    version?: string;
    source_commit?: string;
    release_channel?: string;
    source_clean?: boolean;
  };
  environment: Record<string, string>;
  readiness: {
    ready: boolean | null;
    customer_ready: boolean | null;
    runtime: Record<string, boolean>;
    daemon: Record<string, string | boolean>;
    recall: Record<string, string | number | boolean | null>;
  };
  agent_connection: {
    detected: string[];
    verified: string[];
    uncovered: string[];
  };
  installer_ownership: {
    files?: number;
    host_registrations?: number;
    configured_surfaces?: string[];
  };
  diagnostic_codes: string[];
  backups: {
    valid: number;
    invalid: number;
    latest_verified_at: string | null;
  };
  operation_receipts: {
    package: Record<string, unknown>;
    recovery_history_status: string;
    recovery: Array<Record<string, unknown>>;
    omitted_invalid_receipts: number;
  };
}

export interface RecoveryReceipt {
  schema_version?: number;
  operation_id?: string;
  operation?: RecoveryAction;
  status: RecoveryTerminalStatus;
  authority?: string;
  started_at?: string;
  finished_at?: string;
  layout_sha256?: string;
  source_sha256?: string | null;
  archive_sha256?: string | null;
  archive_name?: string | null;
  report_sha256?: string;
  files?: number;
  bytes?: number;
  checks?: ResolveCheck[];
  error_codes?: string[];
  changed?: boolean;
  rollback?: string;
  recoverable?: boolean;
  next_action?: string;
  safety_archive_name?: string | null;
  staging_name?: string | null;
  previous_data_name?: string | null;
  failed_restore_name?: string | null;
}

export interface RecoveryHistoryEntry extends Omit<RecoveryReceipt, 'status'> {
  status: RecoveryTerminalStatus | 'RUNNING';
}

export interface RecoveryPlanResponse {
  success: boolean;
  plan_id: string | null;
  plan?: RecoveryPlan;
  health?: RecoveryHealth;
  available_backups?: RecoveryBackupArchive[];
  recovery_history?: RecoveryHistoryEntry[];
  error?: string;
  error_code?: string;
}

export interface RecoveryApplyResponse {
  success: boolean;
  recovery_status?: RecoveryTerminalStatus;
  status?: RecoveryTerminalStatus;
  plan?: RecoveryPlan;
  receipt?: RecoveryReceipt;
  recovery_history?: RecoveryHistoryEntry[];
  error?: string;
  error_code?: string;
}

export interface ResolveReceipt {
  schema_version?: number;
  operation_id?: string;
  operation?: string;
  status: ResolveTerminalStatus;
  authority?: string;
  started_at?: string;
  finished_at?: string;
  memory_ids?: Record<string, string>;
  scope_sha256?: string;
  record_sha256?: Record<string, string>;
  checks?: ResolveCheck[];
  error_codes?: string[];
  rollback?: string;
  changed?: boolean;
  [key: string]: unknown;
}

export interface ResolvePlanResponse {
  success: boolean;
  plan_id: string | null;
  plan?: ResolvePlan;
  error?: string;
  error_code?: string;
  [key: string]: unknown;
}

export interface ResolveApplyResponse {
  success: boolean;
  resolution_status?: ResolveTerminalStatus;
  status?: ResolveTerminalStatus;
  plan?: ResolvePlan;
  receipt?: ResolveReceipt;
  error?: string;
  error_code?: string;
  [key: string]: unknown;
}

export interface ConflictResolutionHistoryEntry {
  at?: string;
  action?: string;
  winner_memory_id?: string;
  loser_memory_id?: string;
  reason?: string;
  invocation_mode?: string;
  [key: string]: unknown;
}

export interface VerifiedCorrectionHistoryEntry {
  operation_id?: string;
  at?: string;
  action?: string;
  reason?: string;
  invocation_mode?: string;
  memory_ids?: Record<string, string>;
  [key: string]: unknown;
}

export interface HealthSummary {
  score: number;
  freshness: number;
  coverage: number;
  usage: number;
  connectivity: number;
  counts: Record<string, number>;
}

export interface MemoryNode {
  id: string;
  name: string;
  type: 'memory';
  description: string;
  created_at: string;
  properties: {
    content: string;
    memory_type: 'fact' | 'decision' | 'preference' | 'insight' | string;
    score: number;
    tags: string;
    status: string;
    archived: boolean;
    deprecated: boolean;
    processing_status: string;
    namespace: string;
    title: string;
    topic: string;
    summary: string;
    source: string;
    access_count: number;
    last_accessed: string;
    health_status?: MemoryHealthStatus;
    health_reason?: string;
    connection_count?: number;
    source_detail?: string;
    storage_backend?: string;
    project?: string | null;
    workspace?: string | null;
    scope?: string | null;
    source_reliability?: number | string | null;
    authority_score?: number | string | null;
    verified?: boolean;
    author?: string;
    retention_policy?: string;
    injection_policy?: string;
    user_locked?: boolean;
    version?: number | string;
    conflict_ids?: string[] | string;
    conflict_resolution_history?: ConflictResolutionHistoryEntry[];
    verified_correction_history?: VerifiedCorrectionHistoryEntry[];
    [key: string]: any; // allow extra fields
  };
}

export interface EntityNode {
  id: string;
  name: string;
  type: 'entity';
  description?: string;
  properties?: Record<string, any>;
}

export type GraphNode = MemoryNode | EntityNode | {
  id: string;
  name: string;
  type: 'signal' | 'cluster' | 'session' | 'anchor' | 'concept';
  description?: string;
  properties?: Record<string, any>;
};

export interface GraphEdge {
  source?: string;
  target?: string;
  from?: string;
  to?: string;
  type?: string;
  label?: string;
  similarity?: number;
}

export type SnapshotMode = 'showcase' | 'local_snapshot';

export interface SnapshotContext {
  mode: SnapshotMode;
  label: 'Example workspace' | 'Local snapshot';
  contains_user_data: boolean | null;
  source_grounded_content: boolean | null;
  synthetic_behavioral_metadata: boolean | null;
  disclaimer: string;
}

export type ControlAvailability = 'checking' | 'available' | 'snapshot_only' | 'unavailable';

export function edgeEndpoints(edge: GraphEdge): { source: string; target: string } {
  return {
    source: edge.source ?? edge.from ?? '',
    target: edge.target ?? edge.to ?? '',
  };
}

export interface Snapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
  snapshot_context?: SnapshotContext;
  project_registry?: ProjectRegistrySnapshot;
  project_registry_generated_at?: string;
  stats?: {
    memories: number;
    entities: number;
    edges: number;
    total_nodes: number;
    health?: HealthSummary;
    usage?: UsageSummary;
  };
  generated_at?: string;
}

export interface StatsResponse {
  elefante: {
    package_version: string | null;
    config_version: string | null;
  };
  vector_store: { total_memories: number };
  graph_store: { total_entities: number; total_relationships: number };
  snapshot: {
    generated_at: string;
    total_nodes: number;
    memories: number;
    entities: number;
    edges: number;
    health?: HealthSummary;
    usage?: UsageSummary;
  };
}

export interface SessionIntelligenceResponse {
  schema_version: number;
  generated_at: string | null;
  consent: {
    schema_version: number;
    enabled: boolean;
    purposes: string[];
  };
  signal_card: null | {
    card_id: string;
    scope: Record<string, any>;
    usage: {
      event_count: number;
      session_count: number;
      statuses: Record<string, number>;
      actual: Record<string, any>;
      estimated: Record<string, any>;
    };
    cost: {
      status: string;
      amount: string;
      currency: string | null;
      evidence_class: string;
      unknown_reason?: string | null;
    };
    accepted_outcome_evidence: {
      accepted: boolean | null;
      accepted_outcome_status: string;
      evidence_class: string;
      accepted_count: number;
      rejected_count: number;
    };
    unknowns: string[];
    hypothesis: string;
  };
  enterprise_report: null | {
    aggregation: string;
    groups: Array<Record<string, any>>;
    hypotheses: Array<Record<string, any>>;
    hypotheses_only: boolean;
    employee_ranking: boolean;
    sensitive_trait_inference: boolean;
  };
  privacy: {
    metadata_only: boolean;
    prompts_stored: boolean;
    transcripts_stored: boolean;
    responses_stored: boolean;
    employee_ranking: boolean;
    sensitive_trait_inference: boolean;
  };
}

export interface SearchResult {
  id: string;
  content: string;
  metadata: Record<string, any>;
  similarity: number;
}

export type Tab = 'overview' | 'recall' | 'memories' | 'explore' | 'projects' | 'recover';

export type VisualizationType = 'treemap' | 'calendar' | 'network';
