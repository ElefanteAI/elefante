import { useEffect, useCallback } from 'react';
import { X, Clock, Tag, Layers, Brain, Star, Hash, Globe, User, Check } from 'lucide-react';
import type { MemoryHealthStatus, MemoryNode } from '@/types';
import { RetrievalExplanation, type RetrievalEvidence } from '@/components/RetrievalExplanation';
import { ResolveMemoryDialog } from '@/components/ResolveMemoryDialog';
import { CorrectionDialog } from '@/components/CorrectionDialog';

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

const typeColors: Record<string, string> = {
  fact: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  decision: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  preference: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/25',
  insight: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  note: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  conversation: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  specification: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  directive: 'bg-red-500/20 text-red-300 border-red-500/30',
};

const ringColors: Record<string, string> = {
  core: 'bg-amber-500/20 text-amber-300',
  domain: 'bg-cyan-500/20 text-cyan-300',
  topic: 'bg-cyan-500/15 text-cyan-300',
  leaf: 'bg-slate-500/20 text-slate-300',
};

interface MemoryDetailPanelProps {
  memory: MemoryNode;
  onClose: () => void;
  relatedMemories?: MemoryNode[];
  conflictMemories?: MemoryNode[];
  onNavigateToMemory?: (id: string) => void;
  health_status?: MemoryHealthStatus;
  retrievalEvidence?: RetrievalEvidence;
}

const tooltipMap: Record<MemoryHealthStatus, string> = {healthy: "Healthy", stale: "Stale - refresh", at_risk: "At risk - review", orphan: "Orphan - link"};
const healthClasses: Record<MemoryHealthStatus, string> = {
  healthy: 'text-emerald-300',
  stale: 'text-amber-300',
  at_risk: 'text-red-300',
  orphan: 'text-slate-400',
};

function formatLabel(value: string): string {
  return value.replace(/[_-]/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function parseListValue(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }

  if (typeof value !== 'string') {
    return [];
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return [];
  }

  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item).trim()).filter(Boolean);
      }
    } catch {
      return [];
    }
  }

  if (trimmed.includes(',')) {
    return trimmed.split(',').map((item) => item.trim()).filter(Boolean);
  }

  return [trimmed];
}

export function MemoryDetailPanel({ memory, onClose, relatedMemories = [], conflictMemories = [], onNavigateToMemory, health_status, retrievalEvidence }: MemoryDetailPanelProps) {
  // Escape to close
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && !e.defaultPrevented && !document.querySelector('[role="dialog"]')) onClose();
  }, [onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const p = memory.properties;
  const tags = parseListValue(p.tags);
  const concepts = parseListValue(p.concepts);
  const surfacesWhen = parseListValue(p.surfaces_when);
  const recallCues = parseListValue(p.recall_cues);
  const lifecycleStatus = p.status ? formatLabel(String(p.status)) : '-';
  const processingStatus = p.processing_status ? formatLabel(String(p.processing_status)) : '-';
  const topic = p.topic ? formatLabel(String(p.topic)) : 'General';
  const memoryType = p.memory_type ? formatLabel(String(p.memory_type)) : '-';
  const ring = p.ring ? formatLabel(String(p.ring)) : '-';
  const knowledgeType = p.knowledge_type ? formatLabel(String(p.knowledge_type)) : '-';
  const healthStatus = health_status || p.health_status;
  const conflictIds = Array.from(new Set(parseListValue(p.conflict_ids)));
  const conflictHistory = Array.isArray(p.conflict_resolution_history)
    ? p.conflict_resolution_history.slice(-10)
    : [];
  const correctionHistory = Array.isArray(p.verified_correction_history)
    ? p.verified_correction_history.slice(-10).reverse()
    : [];

  const displayValue = (value: unknown): string => {
    if (value === null || value === undefined || value === '') return '-';
    return String(value);
  };

  const displayBoolean = (value: unknown): string => {
    if (typeof value !== 'boolean') return '-';
    return value ? 'Yes' : 'No';
  };

  const memoryLabelForId = (id: unknown): string => {
    if (typeof id !== 'string') return '-';
    const matched = id === memory.id ? memory : conflictMemories.find((candidate) => candidate.id === id);
    return matched
      ? String(matched.properties?.title || matched.properties?.summary || matched.name || id)
      : id;
  };

  return (
    <div className="absolute right-0 top-0 h-full w-full sm:w-[420px] bg-slate-900/98 backdrop-blur border-l border-slate-700/60 shadow-2xl z-50 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-700/60 bg-slate-800/40 flex-shrink-0">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-semibold text-slate-100 leading-snug">
              {p.title || p.summary || memory.name || 'Untitled Memory'}
            </h2>
            <div className="flex items-center gap-2 mt-2">
              {p.memory_type && (
                <span className={`px-2 py-0.5 rounded text-xs border ${typeColors[p.memory_type] || 'bg-slate-500/20 text-slate-300 border-slate-500/30'}`}>
                  {memoryType}
                </span>
              )}
              {p.ring && (
                <span className={`px-2 py-0.5 rounded text-xs ${ringColors[p.ring] || 'bg-slate-500/20 text-slate-300'}`}>
                  {ring}
                </span>
              )}
              {p.knowledge_type && (
                <span className="px-2 py-0.5 rounded text-xs bg-slate-700/70 text-slate-200 border border-slate-600/70">
                  {knowledgeType}
                </span>
              )}
              {memory.created_at && (
                <span className="text-xs text-slate-500 flex items-center gap-1">
                  <Clock size={11} />
                  {formatRelativeTime(memory.created_at)}
                </span>
              )}
            </div>
              {healthStatus && (
                <div className={`health-status text-[10px] elefante-mono uppercase tracking-wider ${healthClasses[healthStatus]}`} title={tooltipMap[healthStatus]}>
                  {tooltipMap[healthStatus]}
                </div>
              )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white transition-colors flex-shrink-0"
            aria-label="Close panel"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Summary */}
        {p.summary && p.summary !== p.content && (
          <div className="px-5 py-3 border-b border-slate-800/60">
            <div className="text-xs uppercase tracking-wider text-slate-500 mb-1.5">Summary</div>
            <p className="text-sm text-slate-300 leading-relaxed">{p.summary}</p>
          </div>
        )}

        {retrievalEvidence && (
          <RetrievalExplanation memory={memory} evidence={retrievalEvidence} />
        )}

        {/* Content */}
        <div className="px-5 py-3 border-b border-slate-800/60">
          <div className="text-xs uppercase tracking-wider text-slate-500 mb-1.5">Content</div>
          <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">
            {p.content || 'No content'}
          </div>
        </div>

        {/* Metadata Grid */}
        <div className="px-5 py-3 border-b border-slate-800/60">
          <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Metadata</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-xs">
            <MetaRow icon={<Layers size={12} />} label="Topic" value={topic} />
            <MetaRow icon={<Brain size={12} />} label="Type" value={memoryType} />
            <MetaRow icon={<Layers size={12} />} label="Ring" value={ring} />
            <MetaRow icon={<Brain size={12} />} label="Knowledge" value={knowledgeType} />
            <MetaRow icon={<Star size={12} />} label="Vitality" value={p.score != null ? (() => {
              const n = Number(p.score);
              const label = n >= 80 ? 'Fresh' : n >= 60 ? 'Healthy' : n >= 40 ? 'Aging' : n >= 20 ? 'Fading' : 'Dormant';
              return `${Math.round(n)} / 100 — ${label}`;
            })() : '-'} />
            <MetaRow icon={<Hash size={12} />} label="Lifecycle" value={lifecycleStatus} />
            <MetaRow icon={<Hash size={12} />} label="Health" value={healthStatus ? tooltipMap[healthStatus] : '-'} />
            <MetaRow icon={<Hash size={12} />} label="Connections" value={p.connection_count != null ? String(p.connection_count) : '-'} />
            <MetaRow icon={<Hash size={12} />} label="Processing" value={processingStatus} />
            <MetaRow icon={<Globe size={12} />} label="Namespace" value={p.namespace || '-'} />
            <MetaRow icon={<User size={12} />} label="Source" value={p.source || '-'} />
          </div>
          {p.health_reason && (
            <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
              Health signal: {p.health_reason}
            </p>
          )}
        </div>

        {/* Provenance and declared scope */}
        <div className="px-5 py-3 border-b border-slate-800/60">
          <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Provenance &amp; scope</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-xs">
            <MetaRow icon={<Globe size={12} />} label="Storage" value={displayValue(p.storage_backend)} />
            <MetaRow icon={<User size={12} />} label="Source detail" value={displayValue(p.source_detail)} />
            <MetaRow icon={<Layers size={12} />} label="Project" value={displayValue(p.project)} />
            <MetaRow icon={<Layers size={12} />} label="Workspace" value={displayValue(p.workspace)} />
            <MetaRow icon={<Layers size={12} />} label="Scope" value={displayValue(p.scope)} />
            <MetaRow icon={<User size={12} />} label="Author" value={displayValue(p.author)} />
          </div>
        </div>

        {/* Governance */}
        <div className="px-5 py-3 border-b border-slate-800/60">
          <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Governance</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-xs">
            <MetaRow icon={<Star size={12} />} label="Authority" value={displayValue(p.authority_score)} />
            <MetaRow icon={<Star size={12} />} label="Reliability" value={displayValue(p.source_reliability)} />
            <MetaRow icon={<Check size={12} />} label="Source verified" value={displayBoolean(p.verified)} />
            <MetaRow icon={<Hash size={12} />} label="Version" value={displayValue(p.version)} />
            <MetaRow icon={<Hash size={12} />} label="Retention" value={displayValue(p.retention_policy)} />
            <MetaRow icon={<Hash size={12} />} label="Injection" value={displayValue(p.injection_policy)} />
            <MetaRow icon={<User size={12} />} label="User locked" value={displayBoolean(p.user_locked)} />
          </div>
        </div>

        <CorrectionDialog memory={memory} />

        {concepts.length > 0 && (
          <div className="px-5 py-3 border-b border-slate-800/60">
            <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Concepts</div>
            <div className="flex flex-wrap gap-1.5">
              {concepts.map((concept) => (
                <span key={concept} className="px-2 py-0.5 bg-cyan-500/10 text-cyan-200 rounded text-xs border border-cyan-500/20">
                  {concept}
                </span>
              ))}
            </div>
          </div>
        )}

        {recallCues.length > 0 && (
          <div className="px-5 py-3 border-b border-slate-800/60">
            <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">Recall questions</div>
            <p className="mb-2 text-[11px] leading-relaxed text-slate-500">
              Saved questions that help Recall find this knowledge later, including supported paraphrases.
            </p>
            <div className="space-y-1.5">
              {recallCues.map((cue) => (
                <div key={cue} className="text-xs text-slate-200 bg-cyan-950/20 border border-cyan-500/20 rounded px-2.5 py-2">
                  {cue}
                </div>
              ))}
            </div>
          </div>
        )}

        {surfacesWhen.length > 0 && (
          <div className="px-5 py-3 border-b border-slate-800/60">
            <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Surfaces When</div>
            <div className="space-y-1.5">
              {surfacesWhen.map((surface) => (
                <div key={surface} className="text-xs text-slate-300 bg-slate-800/40 border border-slate-700/50 rounded px-2.5 py-2">
                  {surface}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tags */}
        {tags.length > 0 && (
          <div className="px-5 py-3 border-b border-slate-800/60">
            <div className="text-xs uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
              <Tag size={12} />
              Tags
            </div>
            <div className="flex flex-wrap gap-1.5">
              {tags.map((tag: string, i: number) => (
                <span key={i} className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-xs border border-slate-700/60">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Conflicts and bounded correction history */}
        {(conflictIds.length > 0 || conflictHistory.length > 0) && (
          <div className="px-5 py-3 border-b border-slate-800/60">
            <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">
              Conflicts {conflictIds.length > 0 ? `(${conflictIds.length})` : ''}
            </div>
            {conflictIds.length > 0 ? (
              <div className="space-y-1.5">
                {conflictIds.map((conflictId) => {
                  const peer = conflictMemories.find((candidate) => candidate.id === conflictId);
                  return peer && onNavigateToMemory ? (
                    <button
                      key={conflictId}
                      type="button"
                      onClick={() => onNavigateToMemory(peer.id)}
                      className="flex w-full items-center justify-between gap-3 rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-left transition-colors hover:border-amber-400/45 hover:bg-amber-500/10"
                    >
                      <span className="min-w-0 truncate text-xs text-amber-100">{memoryLabelForId(conflictId)}</span>
                      <span className="flex-shrink-0 text-[10px] text-amber-300">Inspect</span>
                    </button>
                  ) : (
                    <div key={conflictId} className="rounded-md border border-slate-700/50 bg-slate-800/30 px-3 py-2 text-xs text-slate-500">
                      {memoryLabelForId(conflictId)} <span className="text-slate-600">(not in current snapshot)</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-xs text-slate-500">No active conflict IDs are recorded.</div>
            )}

            {conflictHistory.length > 0 ? (
              <div className="mt-4 space-y-2">
                <div className="text-[10px] uppercase tracking-widest text-slate-600">Resolution history · latest {conflictHistory.length}</div>
                {conflictHistory.map((event, index) => (
                  <div key={`${String(event.at || 'event')}-${index}`} className="rounded-md border border-slate-800/70 bg-slate-950/35 px-3 py-2">
                    <div className="flex items-center justify-between gap-3 text-[11px]">
                      <span className="text-slate-300">{formatLabel(String(event.action || 'resolution'))}</span>
                      {event.at && <span className="text-slate-600">{formatRelativeTime(String(event.at))}</span>}
                    </div>
                    {event.reason && <p className="mt-1 text-xs leading-relaxed text-slate-400">{String(event.reason)}</p>}
                    {(event.winner_memory_id || event.loser_memory_id) && (
                      <div className="mt-1.5 text-[10px] text-slate-600">
                        Winner: <span className="text-slate-500">{memoryLabelForId(event.winner_memory_id)}</span>
                        {' · '}
                        Loser: <span className="text-slate-500">{memoryLabelForId(event.loser_memory_id)}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-3 text-[11px] text-slate-600">No prior resolution history.</div>
            )}

            <ResolveMemoryDialog memory={memory} conflictMemories={conflictMemories} />
          </div>
        )}

        {correctionHistory.length > 0 && (
          <div className="border-b border-slate-800/60 px-5 py-3">
            <div className="text-xs uppercase tracking-wider text-slate-500">
              Correction history · latest {correctionHistory.length}
            </div>
            <div className="mt-3 space-y-2">
              {correctionHistory.map((event, index) => {
                const reason = typeof event.reason === 'string' ? event.reason : '';
                const boundedReason = reason.length > 240 ? `${reason.slice(0, 240)}…` : reason;
                return (
                  <div
                    key={`${String(event.at || 'correction')}-${index}`}
                    className="rounded-md border border-slate-800/70 bg-slate-950/35 px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-3 text-[11px]">
                      <span className="text-slate-300">{formatLabel(String(event.action || 'correction'))}</span>
                      {event.at && <span className="text-slate-600">{formatRelativeTime(String(event.at))}</span>}
                    </div>
                    {boundedReason && (
                      <p className="mt-1 text-xs leading-relaxed text-slate-400">{boundedReason}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Related Memories */}
        {relatedMemories.length > 0 && (
          <div className="px-5 py-3 border-b border-slate-800/60">
            <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">
              Related ({relatedMemories.length})
            </div>
            <div className="space-y-1.5">
              {relatedMemories.slice(0, 8).map((rm) => (
                <div
                  key={rm.id}
                  className="px-3 py-2 bg-slate-800/40 rounded-lg border border-slate-700/40 hover:border-cyan-500/40 hover:bg-slate-800/70 transition-colors cursor-pointer"
                  onClick={() => onNavigateToMemory?.(rm.id)}
                >
                  <div className="text-xs text-slate-200 truncate">
                    {rm.properties.title || rm.properties.summary || rm.name}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {formatLabel(String(rm.properties.topic || 'general'))} · {formatLabel(String(rm.properties.memory_type || 'unknown'))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Debug Info */}
        <details className="px-5 py-3">
          <summary className="text-xs text-slate-600 cursor-pointer hover:text-slate-400 transition-colors">
            Debug Info
          </summary>
          <div className="mt-2 space-y-1 text-[11px] text-slate-500 font-mono">
            <div>ID: {memory.id}</div>
            <div>Created: {memory.created_at}</div>
            <div>Archived: {String(p.archived)}</div>
            <div>Deprecated: {String(p.deprecated)}</div>
            <div>Supersedes: {p.supersedes_id || '-'}</div>
            <div>Superseded By: {p.superseded_by_id || '-'}</div>
          </div>
        </details>
      </div>
    </div>
  );
}

function MetaRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-slate-500">{icon}</span>
      <span className="text-slate-500">{label}:</span>
      <span className="text-slate-300 truncate">{value}</span>
    </div>
  );
}
