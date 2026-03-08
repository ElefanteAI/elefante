// Elefante Dashboard v2.2.0 - Memories Tab
import { useState, useEffect } from 'react';
import { useDashboardStore } from '@/store';
import { useSearch } from '@/hooks/useSearch';
import { MemoryTable } from '@/components/MemoryTable';
import { MemoryDetailPanel } from '@/components/MemoryDetailPanel';
import { Sparkles, X } from 'lucide-react';
import type { MemoryNode, SearchResult } from '@/types';

export function MemoriesTab() {
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<'browse' | 'search'>('browse');
  
  const isLoading = useDashboardStore((s) => s.isLoading);
  const inspectedMemoryId = useDashboardStore((s) => s.inspectedMemoryId);
  const setInspectedMemoryId = useDashboardStore((s) => s.setInspectedMemoryId);
  const getMemoryNodes = useDashboardStore((s) => s.getMemoryNodes);
  const snapshot = useDashboardStore((s) => s.snapshot);
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
          score: r.similarity,
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
        },
      }))
    : memories;

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
      {/* Semantic Search Bar */}
      <div className="p-4 border-b border-slate-700/60 bg-slate-800/40">
        <div className="max-w-2xl mx-auto">
          <div className="relative">
            <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 text-violet-400" size={16} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Semantic search... (2+ characters)"
              className="w-full pl-10 pr-10 py-3 bg-slate-900/60 border border-slate-700/60 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50"
            />
            {isSearching && (
              <div className="absolute right-10 top-1/2 -translate-y-1/2">
                <div className="w-4 h-4 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
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
              {isSearching ? 'Searching...' : `${results.length} semantic results for "${query}"`}
            </div>
          )}
        </div>
      </div>

      {/* Memory Table + Detail Panel */}
      <div className="flex-1 overflow-hidden relative">
        <MemoryTable
          memories={searchMemories}
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
            if (e.source === selectedId) relatedIds.add(e.target);
            if (e.target === selectedId) relatedIds.add(e.source);
          });
          const related = memories.filter((m) => relatedIds.has(m.id));

          return (
            <MemoryDetailPanel
              memory={mem}
              relatedMemories={related}
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