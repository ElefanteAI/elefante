// Elefante Dashboard v2.2.3 - Type Definitions

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
  source: string;
  target: string;
  type?: string;
  label?: string;
  similarity?: number;
}

export interface Snapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats?: {
    memories: number;
    entities: number;
    edges: number;
    total_nodes: number;
  };
  generated_at?: string;
}

export interface StatsResponse {
  elefante: {
    package_version: string | null;
    config_version: string | null;
    data_dir: string;
  };
  vector_store: { total_memories: number };
  graph_store: { total_entities: number; total_relationships: number };
  snapshot: {
    path: string;
    generated_at: string;
    total_nodes: number;
    memories: number;
    entities: number;
    edges: number;
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
