import { useState, useEffect } from 'react';
import { useDashboardStore } from '@/store';
import { useSearch } from '@/hooks/useSearch';
import { MemoryTable } from '@/components/MemoryTable';
import { MemoryDetailPanel } from '@/components/MemoryDetailPanel';
import { BookOpen, ListChecks, Search, X } from 'lucide-react';
import { edgeEndpoints, type MemoryNode, type SearchResult } from '@/types';

function parseListValue(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof value !== 'string') return [];

  const trimmed = value.trim();
  if (!trimmed) return [];
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    try {
      const parsed: unknown = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item).trim()).filter(Boolean);
      }
    } catch {
      return [];
    }
  }
  return trimmed.includes(',')
    ? trimmed.split(',').map((item) => item.trim()).filter(Boolean)
    : [trimmed];
}

function needsReview(memory: MemoryNode): boolean {
  const health = String(memory.properties?.health_status || '').toLowerCase();
  const status = String(memory.properties?.status || '').toLowerCase();
  return Boolean(
    (health && health !== 'healthy')
      || memory.properties?.archived
      || memory.properties?.deprecated
      || ['contradictory', 'redundant', 'superseded'].includes(status),
  );
}

export function MemoriesTab() {
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<'browse' | 'search'>('browse');
  const [workspaceView, setWorkspaceView] = useState<'library' | 'review'>('library');
  
  const isLoading = useDashboardStore((s) => s.isLoading);
  const inspectedMemoryId = useDashboardStore((s) => s.inspectedMemoryId);
  const setInspectedMemoryId = useDashboardStore((s) => s.setInspectedMemoryId);
  const getMemoryNodes = useDashboardStore((s) => s.getMemoryNodes);
  const snapshot = useDashboardStore((s) => s.snapshot);
  const isShowcase = snapshot?.snapshot_context?.mode === 'showcase';
  const memories = getMemoryNodes();

  // Auto-open detail panel from external navigation (e.g. ActivityFeed click)
  useEffect(() => {
    if (inspectedMemoryId) {
      setSelectedId(inspectedMemoryId);
    }
  }, [inspectedMemoryId]);
  
  const { results, isSearching, search } = useSearch();
  
  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.trim().length >= 2) {
        setMode('search');
        search(query);
      } else {
        setMode('browse');
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, search]);

  // Convert search results to memory-like format for table
  const searchMemories: MemoryNode[] = mode === 'search' && results.length > 0
    ? results.map((r: SearchResult) => ({
        id: r.id,
        name: r.content.slice(0, 50),
        type: 'memory' as const,
        description: r.content,
        created_at: r.metadata?.created_at || new Date().toISOString(),
        properties: {
          content: r.content,
          title: r.metadata?.title || '',
          topic: r.metadata?.topic || '',
          memory_type: r.metadata?.memory_type || '',
          score: Number.isFinite(Number(r.metadata?.score)) ? Number(r.metadata.score) : 0,
          tags: r.metadata?.tags || '',
          status: r.metadata?.status || '',
          archived: r.metadata?.archived || false,
          deprecated: r.metadata?.deprecated || false,
          processing_status: r.metadata?.processing_status || '',
          namespace: r.metadata?.namespace || '',
          summary: r.metadata?.summary || '',
          source: r.metadata?.source || '',
          access_count: r.metadata?.access_count || 0,
          last_accessed: r.metadata?.last_accessed || '',
          health_status: r.metadata?.health_status,
          health_reason: r.metadata?.health_reason,
          connection_count: r.metadata?.connection_count,
        },
      }))
    : memories;
  const reviewCount = memories.filter(needsReview).length;
  const visibleMemories = workspaceView === 'review'
    ? searchMemories.filter(needsReview)
    : searchMemories;

  const selectedSearchResultIndex = mode === 'search'
    ? results.findIndex((result) => result.id === selectedId)
    : -1;
  const selectedSearchResult = selectedSearchResultIndex >= 0
    ? results[selectedSearchResultIndex]
    : undefined;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <div className="text-slate-400">Loading memories...</div>
        </div>
      </div>
    );
  }

  if (memories.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <h2 className="text-xl font-semibold text-slate-200 mb-2">No memories</h2>
          <p className="text-slate-400 text-sm">
            Add memories via your IDE or MCP tool to see them here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <header className="flex flex-col gap-4 border-b border-slate-700/60 bg-slate-900/35 px-5 py-4 lg:flex-row lg:items-end lg:justify-between lg:px-7">
        <div>
          <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.18em]">Memory Intelligence</div>
          <h1 className="mt-1 text-2xl font-medium tracking-[-0.025em] text-slate-100">
            {isShowcase ? 'Inspect the example memory corpus.' : 'Inspect the complete local memory corpus.'}
          </h1>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
            {isShowcase
              ? 'Example workspace · read-only inspection. Search and review describe this snapshot only.'
              : 'View scope: all memories, read only. Correct remains bound to one active project and its verified postconditions.'}
          </p>
        </div>
        <div className="flex items-center gap-1 border border-slate-800 bg-slate-950/55 p-1" aria-label="Memory Intelligence view">
          <button
            type="button"
            onClick={() => setWorkspaceView('library')}
            aria-pressed={workspaceView === 'library'}
            className={`inline-flex min-h-9 items-center gap-2 px-3 text-xs ${
              workspaceView === 'library'
                ? 'bg-cyan-950/30 text-cyan-200'
                : 'text-slate-500 hover:text-slate-200'
            }`}
          >
            <BookOpen size={13} aria-hidden="true" />
            Library · {memories.length}
          </button>
          <button
            type="button"
            onClick={() => setWorkspaceView('review')}
            aria-pressed={workspaceView === 'review'}
            className={`inline-flex min-h-9 items-center gap-2 px-3 text-xs ${
              workspaceView === 'review'
                ? 'bg-amber-950/30 text-amber-200'
                : 'text-slate-500 hover:text-slate-200'
            }`}
          >
            <ListChecks size={13} aria-hidden="true" />
            Review · {reviewCount}
          </button>
        </div>
      </header>

      {workspaceView === 'review' && (
        <div className="border-b border-amber-400/20 bg-amber-950/10 px-5 py-2 text-[10px] leading-relaxed text-amber-100/80 lg:px-7">
          Review groups direct snapshot health or lifecycle signals. It does not grade truth, usefulness, project scope, or whether a correction is necessary.
        </div>
      )}

      {/* Semantic Search Bar */}
      <div className="p-4 border-b border-slate-700/60 bg-slate-800/40">
        <div className="max-w-2xl mx-auto">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-cyan-400" size={16} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Snapshot search... (2+ characters)"
              className="w-full pl-10 pr-10 py-3 bg-slate-900/60 border border-slate-700/60 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500/50"
            />
            {isSearching && (
              <div className="absolute right-10 top-1/2 -translate-y-1/2">
                <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
              </div>
            )}
            {query && (
              <button
                onClick={() => setQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-slate-700 rounded"
              >
                <X size={14} className="text-slate-400" />
              </button>
            )}
          </div>
          {mode === 'search' && query.trim().length >= 2 && (
            <div className="mt-2 text-xs text-slate-500">
              {isSearching ? 'Searching...' : `${results.length} snapshot results for "${query}"`}
            </div>
          )}
        </div>
      </div>

      {/* Memory Table + Detail Panel */}
      <div className="flex-1 overflow-hidden relative">
        <MemoryTable
          memories={visibleMemories}
          selectedId={selectedId}
          onSelectMemory={(memory) => {
            const newId = selectedId === memory.id ? null : memory.id;
            setSelectedId(newId);
            setInspectedMemoryId(newId);
          }}
        />

        {/* Detail Panel */}
        {selectedId && (() => {
          const mem = memories.find((m) => m.id === selectedId);
          if (!mem) return null;

          // Find related memories via edges
          const relatedIds = new Set<string>();
          snapshot?.edges.forEach((e) => {
            const { source, target } = edgeEndpoints(e);
            if (source === selectedId && target) relatedIds.add(target);
            if (target === selectedId && source) relatedIds.add(source);
          });
          const related = memories.filter((m) => relatedIds.has(m.id));
          const conflictIds = parseListValue(mem.properties?.conflict_ids);
          const conflictMemories = memories.filter(
            (candidate) => candidate.id !== mem.id && conflictIds.includes(candidate.id),
          );

          return (
            <MemoryDetailPanel
              memory={mem}
              relatedMemories={related}
              conflictMemories={conflictMemories}
              health_status={mem.properties?.health_status}
              retrievalEvidence={selectedSearchResult ? {
                query,
                result: selectedSearchResult,
                rank: selectedSearchResultIndex + 1,
                total: results.length,
                edges: snapshot?.edges || [],
              } : undefined}
              onClose={() => {
                setSelectedId(null);
                setInspectedMemoryId(null);
              }}
              onNavigateToMemory={(id) => {
                setSelectedId(id);
                setInspectedMemoryId(id);
              }}
            />
          );
        })()}
      </div>
    </div>
  );
}
