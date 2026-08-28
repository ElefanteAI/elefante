
export type MemoryHealthStatus = 'healthy' | 'stale' | 'at_risk' | 'orphan';

export interface UsageSummary {
  total_accesses: number;
  retrieved_memories: number;
  never_retrieved: number;
  retrieval_rate: number;
  average_access_count: number;
  max_access_count: number;
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

export function edgeEndpoints(edge: GraphEdge): { source: string; target: string } {
  return {
    source: edge.source ?? edge.from ?? '',
    target: edge.target ?? edge.to ?? '',
  };
}

export interface Snapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
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

export type Tab = 'overview' | 'memories' | 'explore';

export type VisualizationType = 'treemap' | 'calendar' | 'network';
