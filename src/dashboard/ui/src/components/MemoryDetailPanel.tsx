// Elefante Dashboard v3.0.0 - Memory Detail Panel
import { useEffect, useCallback } from 'react';
import { X, Clock, Tag, Layers, Brain, Star, Hash, Globe, User } from 'lucide-react';
import type { MemoryNode } from '@/types';

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
  preference: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
  insight: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  note: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  conversation: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
  specification: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  directive: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
};

const ringColors: Record<string, string> = {
  core: 'bg-amber-500/20 text-amber-300',
  domain: 'bg-cyan-500/20 text-cyan-300',
  topic: 'bg-violet-500/20 text-violet-300',
  leaf: 'bg-slate-500/20 text-slate-300',
};

interface MemoryDetailPanelProps {
  memory: MemoryNode;
  onClose: () => void;
  relatedMemories?: MemoryNode[];
  onNavigateToMemory?: (id: string) => void;
  health_status?: 'healthy'|'stale'|'at_risk'|'orphan';
}

const iconMap = {healthy: "✓", stale: "⏰", at_risk: "⚠", orphan: "🔗"};
const colorMap = {healthy: "green", stale: "yellow", at_risk: "red", orphan: "gray"};

const tooltipMap = {healthy: "Healthy", stale: "Stale - refresh", at_risk: "At risk - review", orphan: "Orphan - link"};

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

export function MemoryDetailPanel({ memory, onClose, relatedMemories = [], onNavigateToMemory , health_status }: MemoryDetailPanelProps) {
  // Escape to close
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
  }, [onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const p = memory.properties;
  const tags = p.tags ? p.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : [];
  const concepts = parseListValue(p.concepts);
  const surfacesWhen = parseListValue(p.surfaces_when);
  const lifecycleStatus = p.status ? formatLabel(String(p.status)) : '-';
  const processingStatus = p.processing_status ? formatLabel(String(p.processing_status)) : '-';
  const topic = p.topic ? formatLabel(String(p.topic)) : 'General';
  const memoryType = p.memory_type ? formatLabel(String(p.memory_type)) : '-';
  const ring = p.ring ? formatLabel(String(p.ring)) : '-';
  const knowledgeType = p.knowledge_type ? formatLabel(String(p.knowledge_type)) : '-';

  return (
    <div className="fixed right-0 top-0 h-full w-[420px] bg-slate-900/98 backdrop-blur border-l border-slate-700/60 shadow-2xl z-50 flex flex-col overflow-hidden">
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
              {health_status && (
                <div className={`health-status ${health_status}`} style={{color: colorMap[health_status]}} title={tooltipMap[health_status]}>
                  {iconMap[health_status]}
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
            <MetaRow icon={<Hash size={12} />} label="Processing" value={processingStatus} />
            <MetaRow icon={<Globe size={12} />} label="Namespace" value={p.namespace || '-'} />
            <MetaRow icon={<User size={12} />} label="Source" value={p.source || '-'} />
          </div>
        </div>

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
