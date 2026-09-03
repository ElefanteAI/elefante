import type { ReactNode } from 'react';
import { Database, HeartPulse, Link2, SearchCheck } from 'lucide-react';
import { edgeEndpoints, type GraphEdge, type MemoryNode, type SearchResult } from '@/types';

export interface RetrievalEvidence {
  query: string;
  result: SearchResult;
  rank: number;
  total: number;
  edges: GraphEdge[];
}

interface RetrievalExplanationProps {
  memory: MemoryNode;
  evidence: RetrievalEvidence;
}

const healthLabels: Record<string, string> = {
  healthy: 'Healthy',
  stale: 'Stale',
  at_risk: 'At risk',
  orphan: 'Orphan',
};

const healthClasses: Record<string, string> = {
  healthy: 'text-emerald-300',
  stale: 'text-amber-300',
  at_risk: 'text-red-300',
  orphan: 'text-slate-300',
};

function finiteNumber(value: unknown, fallback = 0): number {
  const number = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function formatLabel(value: string): string {
  return value.replace(/[_-]/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function relationshipEvidence(memoryId: string, edges: GraphEdge[]): Array<{ label: string; direction: 'inbound' | 'outbound'; neighbor: string }> {
  const seen = new Set<string>();
  const relationships: Array<{ label: string; direction: 'inbound' | 'outbound'; neighbor: string }> = [];

  edges.forEach((edge) => {
    const { source, target } = edgeEndpoints(edge);
    if (source !== memoryId && target !== memoryId) return;

    const neighbor = source === memoryId ? target : source;
    if (!neighbor || neighbor === memoryId) return;

    const label = String(edge.label || edge.type || 'RELATED');
    const direction = source === memoryId ? 'outbound' : 'inbound';
    const key = `${direction}:${neighbor}:${label}`;
    if (seen.has(key)) return;
    seen.add(key);
    relationships.push({ label, direction, neighbor });
  });

  return relationships;
}

function EvidenceCell({ icon, label, value, detail, valueClass = 'text-slate-100' }: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  valueClass?: string;
}) {
  return (
    <div className="min-w-0 border border-slate-800/70 bg-slate-950/35 px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[9px] text-slate-500 elefante-mono uppercase tracking-[0.1em]">
        {icon}
        <span>{label}</span>
      </div>
      <strong className={`mt-2 block truncate text-sm font-medium ${valueClass}`} title={value}>
        {value}
      </strong>
      <span className="mt-1 block text-[10px] leading-relaxed text-slate-600">
        {detail}
      </span>
    </div>
  );
}

export function RetrievalExplanation({ memory, evidence }: RetrievalExplanationProps) {
  const { query, result, rank, total, edges } = evidence;
  const metadata = result.metadata || {};
  const similarity = Math.max(0, Math.min(1, finiteNumber(result.similarity)));
  const relationships = relationshipEvidence(memory.id, edges);
  const metadataConnectionCount = finiteNumber(metadata.connection_count, Number.NaN);
  const connectionCount = Number.isFinite(metadataConnectionCount)
    ? Math.max(0, Math.round(metadataConnectionCount))
    : new Set(relationships.map((relationship) => relationship.neighbor)).size;

  const rawHealth = metadata.health_status ?? memory.properties?.health_status;
  const healthStatus = typeof rawHealth === 'string' && rawHealth.trim() ? rawHealth : null;
  const healthLabel = healthStatus ? (healthLabels[healthStatus] || formatLabel(healthStatus)) : 'Not reported';
  const healthReason = String(metadata.health_reason ?? memory.properties?.health_reason ?? 'No health reason in this snapshot.');
  const source = metadata.storage_backend ?? memory.properties?.storage_backend;
  const sourceLabel = source === 'sqlite' ? 'SQLite' : source ? formatLabel(String(source)) : 'Not reported';
  const rankLabel = `#${Math.max(1, Math.round(finiteNumber(rank, 1)))} of ${Math.max(1, Math.round(finiteNumber(total, 1)))}`;
  const title = memory.properties?.title || memory.name || 'Selected memory';

  return (
    <section aria-label="Retrieval explanation" className="border-b border-slate-800/60 bg-slate-950/25 px-5 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.16em]">
            Retrieval explanation
          </div>
          <h3 className="mt-1 truncate text-sm font-medium text-slate-100" title={title}>
            Dashboard evidence for this result
          </h3>
        </div>
        <span className="flex-none text-[10px] text-slate-500 elefante-mono uppercase tracking-[0.1em]">
          {rankLabel}
        </span>
      </div>

      <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
        This snapshot search returned the memory for <span className="text-slate-300">“{query.trim() || 'the current query'}”</span> with a {Math.round(similarity * 100)}% lexical match.
      </p>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <EvidenceCell
          icon={<SearchCheck size={12} className="text-cyan-400" />}
          label="Query match"
          value={`${Math.round(similarity * 100)}% lexical`}
          detail="Snapshot search ratio"
        />
        <EvidenceCell
          icon={<SearchCheck size={12} className="text-amber-300" />}
          label="Selection"
          value={rankLabel}
          detail="Returned order from snapshot search"
        />
        <EvidenceCell
          icon={<Database size={12} className="text-[#c8894d]" />}
          label="Storage source"
          value={sourceLabel}
          detail="Configured backend in the snapshot"
        />
        <EvidenceCell
          icon={<HeartPulse size={12} className={healthStatus ? healthClasses[healthStatus] || 'text-slate-300' : 'text-slate-500'} />}
          label="Health"
          value={healthLabel}
          detail={healthReason}
          valueClass={healthStatus ? healthClasses[healthStatus] || 'text-slate-100' : 'text-slate-500'}
        />
      </div>

      <div className="mt-2 border border-slate-800/70 bg-slate-950/35 px-3 py-2.5">
        <div className="flex items-center gap-1.5 text-[9px] text-slate-500 elefante-mono uppercase tracking-[0.1em]">
          <Link2 size={12} className="text-emerald-300" />
          <span>Relationships</span>
          <span className="ml-auto text-slate-400">{connectionCount}</span>
        </div>
        {relationships.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {relationships.slice(0, 8).map((relationship) => (
              <span
                key={`${relationship.direction}:${relationship.neighbor}:${relationship.label}`}
                className="border border-slate-700/70 px-2 py-1 text-[10px] text-slate-400"
                title={`${relationship.direction} relationship to ${relationship.neighbor}`}
              >
                {relationship.direction === 'outbound' ? 'out · ' : 'in · '}{formatLabel(relationship.label)}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-1 text-[10px] leading-relaxed text-slate-600">
            No explicit graph relationship is represented for this memory in the current snapshot.
          </p>
        )}
      </div>

      <p className="mt-3 text-[10px] leading-relaxed text-slate-600">
        This explains the dashboard’s redacted snapshot search only. The dashboard API does not expose the MCP retriever’s vector, concept, co-activation, authority, or temporal signal breakdown.
      </p>
    </section>
  );
}
