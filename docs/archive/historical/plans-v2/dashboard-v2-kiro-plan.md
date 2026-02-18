# Dashboard v2.0.0 "Clarity" — KIRO Implementation Plan

> **Purpose**: Step-by-step agent-executable plan. Each task is atomic, ordered by dependency, and has a clear verification step. No ambiguity.
>
> **Current state**: Single-file monolith (`GraphCanvas.tsx`, 2888 lines). No routing. No charts. No table. Dashboard `package.json` version is `0.0.0`.
>
> **Target state**: 3-tab architecture (Overview, Memories, Explore) with table view, semantic search, health score, treemap, calendar heatmap, and static network graph.

---

## GROUND RULES FOR THE AGENT

1. **Working directory**: `/Volumes/Hard/2026/AI Projects/Elefante/src/dashboard/ui`
2. **Build check after every phase**: Run `npm run build` and fix all TypeScript errors before moving on.
3. **Do NOT delete `GraphCanvas.tsx` until Phase 5**. It's the reference implementation.
4. **Do NOT touch `src/dashboard/server.py`** until Phase 7 (API changes).
5. **All new components go in `src/components/`** — flat structure, no nesting beyond one level.
6. **Use existing Tailwind colors**: `background`, `surface`, `primary`, `secondary`, `accent`, `text`, `muted` (defined in `tailwind.config.js`).
7. **Dark theme only**. No light mode toggle.
8. **No emojis in UI text**. (Project policy — see `scripts/emoji_policy.py`.)

---

## PHASE 0: Dependencies & Config

> Install all new dependencies and configure the project.

### Task 0.1: Install runtime dependencies

```bash
cd src/dashboard/ui
npm install react-router-dom@6 zustand @tanstack/react-table @nivo/treemap @nivo/calendar @nivo/network
```

**Verify**: `npm ls react-router-dom zustand @tanstack/react-table @nivo/treemap @nivo/calendar @nivo/network` — all resolve without errors.

### Task 0.2: Install shadcn/ui prerequisites

shadcn/ui is copy-paste, not a package. Install the underlying primitives we need:

```bash
npm install @radix-ui/react-tabs @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-tooltip @radix-ui/react-select class-variance-authority
```

**Verify**: `npm ls @radix-ui/react-tabs` resolves.

### Task 0.3: Update `package.json` version

Change `"version": "0.0.0"` to `"version": "2.0.0"`.

**Verify**: `grep '"version"' package.json` shows `"2.0.0"`.

### Task 0.4: Add path alias to Vite config

Update `vite.config.ts` to resolve the `@/` path alias already defined in `tsconfig.json`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
```

**Verify**: `npm run build` succeeds.

---

## PHASE 1: Zustand Store & Data Layer

> Create the global state store and data-fetching hooks BEFORE any UI changes.

### Task 1.1: Create types file

Create `src/types.ts` with all shared TypeScript types extracted from GraphCanvas.tsx:

```typescript
// src/types.ts

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
    ring: string;
    knowledge_type: string;
    topic: string;
    summary: string;
    owner_id: string;
    source: string;
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
```

**Verify**: `npx tsc --noEmit src/types.ts` — no errors.

### Task 1.2: Create Zustand store

Create `src/store.ts`:

```typescript
// src/store.ts
import { create } from 'zustand';
import type { Tab, Snapshot, StatsResponse, MemoryNode, GraphNode } from './types';

interface DashboardStore {
  // Navigation
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;

  // Data
  snapshot: Snapshot | null;
  stats: StatsResponse | null;
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
  activeVisualization: 'treemap' | 'calendar' | 'network';
  setActiveVisualization: (v: 'treemap' | 'calendar' | 'network') => void;

  // Actions
  fetchSnapshot: () => Promise<void>;
  fetchStats: () => Promise<void>;

  // Derived (computed helpers)
  getMemoryNodes: () => MemoryNode[];
  getTopics: () => string[];
  getMemoryTypes: () => string[];
}

export const useDashboardStore = create<DashboardStore>((set, get) => ({
  // Navigation
  activeTab: 'overview',
  setActiveTab: (tab) => set({ activeTab: tab }),

  // Data
  snapshot: null,
  stats: null,
  isLoading: false,
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

  // Actions
  fetchSnapshot: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetch('/api/graph');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      set({ snapshot: { nodes: data.nodes || [], edges: data.edges || [], stats: data.stats }, isLoading: false });
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
    }
  },

  fetchStats: async () => {
    try {
      const res = await fetch('/api/stats');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      set({ stats: data });
    } catch (e: any) {
      console.error('Failed to fetch stats:', e);
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
```

**Verify**: `npx tsc --noEmit src/store.ts` — no errors.

### Task 1.3: Create data transformation hooks

Create `src/hooks/useVisualizationData.ts`:

```typescript
// src/hooks/useVisualizationData.ts
import { useMemo } from 'react';
import { useDashboardStore } from '@/store';
import type { MemoryNode } from '@/types';

// ── Treemap ──────────────────────────────────────────────
export interface TreemapDatum {
  id: string;
  value: number;
  color?: string;
}

export function useTreemapData(): { id: string; value: number }[] {
  const memories = useDashboardStore((s) => s.getMemoryNodes());
  return useMemo(() => {
    const counts = new Map<string, number>();
    memories.forEach((m) => {
      const topic = m.properties?.topic || 'general';
      counts.set(topic, (counts.get(topic) || 0) + 1);
    });
    return Array.from(counts.entries())
      .map(([id, value]) => ({ id, value }))
      .sort((a, b) => b.value - a.value);
  }, [memories]);
}

// ── Calendar Heatmap ─────────────────────────────────────
export interface CalendarDatum {
  day: string;   // YYYY-MM-DD
  value: number;
}

export function useCalendarData(): CalendarDatum[] {
  const memories = useDashboardStore((s) => s.getMemoryNodes());
  return useMemo(() => {
    const counts = new Map<string, number>();
    memories.forEach((m) => {
      const d = m.created_at?.slice(0, 10); // "YYYY-MM-DD"
      if (d) counts.set(d, (counts.get(d) || 0) + 1);
    });
    return Array.from(counts.entries())
      .map(([day, value]) => ({ day, value }))
      .sort((a, b) => a.day.localeCompare(b.day));
  }, [memories]);
}

// ── Network (static) ─────────────────────────────────────
export interface NetworkData {
  nodes: { id: string; label: string; size: number; color: string }[];
  links: { source: string; target: string; distance: number }[];
}

export function useNetworkData(): NetworkData {
  const snapshot = useDashboardStore((s) => s.snapshot);
  return useMemo(() => {
    if (!snapshot) return { nodes: [], links: [] };

    // Only include memory nodes
    const memoryNodes = snapshot.nodes.filter((n) => n.type === 'memory');
    const memoryIds = new Set(memoryNodes.map((n) => n.id));

    const nodes = memoryNodes.map((n) => ({
      id: n.id,
      label: (n as MemoryNode).properties?.summary || n.name || n.id,
      size: Math.max(4, Math.min(16, ((n as MemoryNode).properties?.score || 5) * 1.5)),
      color: typeColor((n as MemoryNode).properties?.memory_type),
    }));

    const links = snapshot.edges
      .filter((e) => memoryIds.has(e.source) && memoryIds.has(e.target))
      .slice(0, 200) // cap edges for performance
      .map((e) => ({
        source: e.source,
        target: e.target,
        distance: 50,
      }));

    return { nodes, links };
  }, [snapshot]);
}

// ── Health Score ──────────────────────────────────────────
export interface HealthScore {
  overall: number;           // 0-100
  freshness: number;         // 0-100
  coverage: number;          // 0-100
  connectivity: number;      // 0-100
  staleCount: number;
  orphanCount: number;
  totalMemories: number;
}

export function useHealthScore(): HealthScore {
  const snapshot = useDashboardStore((s) => s.snapshot);
  return useMemo(() => {
    if (!snapshot) return { overall: 0, freshness: 0, coverage: 0, connectivity: 0, staleCount: 0, orphanCount: 0, totalMemories: 0 };

    const memories = snapshot.nodes.filter((n): n is MemoryNode => n.type === 'memory');
    const total = memories.length;
    if (total === 0) return { overall: 0, freshness: 0, coverage: 0, connectivity: 0, staleCount: 0, orphanCount: 0, totalMemories: 0 };

    // 1. Freshness (40%): How recently were memories created/accessed?
    const now = Date.now();
    const NINETY_DAYS = 90 * 24 * 60 * 60 * 1000;
    let freshSum = 0;
    let staleCount = 0;
    memories.forEach((m) => {
      const created = new Date(m.created_at).getTime();
      const age = now - created;
      const fresh = Math.max(0, 1 - age / NINETY_DAYS);
      freshSum += fresh;
      if (age > NINETY_DAYS) staleCount++;
    });
    const freshness = Math.round((freshSum / total) * 100);

    // 2. Coverage (35%): Are memories spread across multiple topics (not all "general")?
    const topics = new Map<string, number>();
    memories.forEach((m) => {
      const t = m.properties?.topic || 'general';
      topics.set(t, (topics.get(t) || 0) + 1);
    });
    const nonGeneralCount = total - (topics.get('general') || 0);
    const coverage = Math.round((nonGeneralCount / total) * 100);

    // 3. Connectivity (25%): Do memories have edges?
    const memoryIds = new Set(memories.map((m) => m.id));
    const connectedIds = new Set<string>();
    snapshot.edges.forEach((e) => {
      if (memoryIds.has(e.source)) connectedIds.add(e.source);
      if (memoryIds.has(e.target)) connectedIds.add(e.target);
    });
    const connectivity = Math.round((connectedIds.size / total) * 100);
    const orphanCount = total - connectedIds.size;

    // Weighted overall
    const overall = Math.round(freshness * 0.4 + coverage * 0.35 + connectivity * 0.25);

    return { overall, freshness, coverage, connectivity, staleCount, orphanCount, totalMemories: total };
  }, [snapshot]);
}

// ── Helpers ──────────────────────────────────────────────
function typeColor(type?: string): string {
  switch (type) {
    case 'fact': return '#3b82f6';       // blue
    case 'decision': return '#f59e0b';   // amber
    case 'preference': return '#8b5cf6'; // violet
    case 'insight': return '#10b981';    // emerald
    default: return '#64748b';           // slate
  }
}
```

**Verify**: `npx tsc --noEmit src/hooks/useVisualizationData.ts` — no errors.

### Task 1.4: Create search hook

Create `src/hooks/useSearch.ts`:

```typescript
// src/hooks/useSearch.ts
import { useState, useCallback, useRef } from 'react';
import type { SearchResult } from '@/types';

interface UseSearchReturn {
  results: SearchResult[];
  isSearching: boolean;
  searchError: string | null;
  search: (query: string) => Promise<void>;
  clear: () => void;
}

export function useSearch(): UseSearchReturn {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const search = useCallback(async (query: string) => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    // Abort previous request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsSearching(true);
    setSearchError(null);

    try {
      const res = await fetch(
        `/api/search?query=${encodeURIComponent(query)}&limit=20&min_similarity=0.3`,
        { signal: controller.signal }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (!data.success) throw new Error(data.error || 'Search failed');

      setResults(data.results || []);
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setSearchError(e.message);
        setResults([]);
      }
    } finally {
      setIsSearching(false);
    }
  }, []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    setResults([]);
    setSearchError(null);
  }, []);

  return { results, isSearching, searchError, search, clear };
}
```

**Verify**: `npx tsc --noEmit src/hooks/useSearch.ts` — no errors.

---

## PHASE 2: Tab Shell & Layout

> Replace the current full-screen graph with a tabbed layout. The graph still exists but is now inside the "Explore" tab.

### Task 2.1: Create tab navigation component

Create `src/components/TabNav.tsx`:

```typescript
// src/components/TabNav.tsx
import { useDashboardStore } from '@/store';
import type { Tab } from '@/types';
import { LayoutDashboard, Table2, Compass } from 'lucide-react';

const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={16} /> },
  { id: 'memories', label: 'Memories', icon: <Table2 size={16} /> },
  { id: 'explore', label: 'Explore', icon: <Compass size={16} /> },
];

export function TabNav() {
  const activeTab = useDashboardStore((s) => s.activeTab);
  const setActiveTab = useDashboardStore((s) => s.setActiveTab);

  return (
    <nav className="flex items-center gap-1 bg-slate-900/80 backdrop-blur border-b border-slate-700/60 px-4">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveTab(tab.id)}
          className={
            'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 ' +
            (activeTab === tab.id
              ? 'text-cyan-400 border-cyan-400'
              : 'text-slate-400 border-transparent hover:text-slate-200 hover:border-slate-600')
          }
        >
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
```

### Task 2.2: Create placeholder tab panels

Create three placeholder components — these will be filled in subsequent phases:

**`src/components/OverviewTab.tsx`**:
```typescript
import { useHealthScore } from '@/hooks/useVisualizationData';
import { useDashboardStore } from '@/store';

export function OverviewTab() {
  const health = useHealthScore();
  const stats = useDashboardStore((s) => s.stats);

  if (health.totalMemories === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-4">0</div>
          <h2 className="text-xl font-semibold text-slate-200 mb-2">No memories yet</h2>
          <p className="text-slate-400 text-sm">
            Add your first memory via your IDE or MCP tool.
            Memories will appear here once created.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 overflow-auto h-full">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Health Score + Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Health Score - Big */}
          <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-6 flex flex-col items-center justify-center">
            <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Health Score</div>
            <div className={
              'text-5xl font-bold ' +
              (health.overall >= 70 ? 'text-emerald-400' : health.overall >= 40 ? 'text-amber-400' : 'text-red-400')
            }>
              {health.overall}%
            </div>
            <div className="mt-2 text-xs text-slate-500">
              {health.staleCount > 0 && <span className="text-amber-400">{health.staleCount} stale</span>}
              {health.staleCount > 0 && health.orphanCount > 0 && <span> · </span>}
              {health.orphanCount > 0 && <span className="text-slate-400">{health.orphanCount} orphan</span>}
            </div>
          </div>

          {/* Sub-metrics */}
          <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
            <div className="text-xs uppercase tracking-wider text-slate-400 mb-1">Freshness</div>
            <div className="text-2xl font-semibold text-slate-200">{health.freshness}%</div>
            <div className="mt-2 h-1.5 bg-slate-700 rounded-full">
              <div className="h-full bg-cyan-400 rounded-full" style={{ width: `${health.freshness}%` }} />
            </div>
          </div>

          <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
            <div className="text-xs uppercase tracking-wider text-slate-400 mb-1">Topic Coverage</div>
            <div className="text-2xl font-semibold text-slate-200">{health.coverage}%</div>
            <div className="mt-2 h-1.5 bg-slate-700 rounded-full">
              <div className="h-full bg-violet-400 rounded-full" style={{ width: `${health.coverage}%` }} />
            </div>
          </div>

          <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
            <div className="text-xs uppercase tracking-wider text-slate-400 mb-1">Connectivity</div>
            <div className="text-2xl font-semibold text-slate-200">{health.connectivity}%</div>
            <div className="mt-2 h-1.5 bg-slate-700 rounded-full">
              <div className="h-full bg-emerald-400 rounded-full" style={{ width: `${health.connectivity}%` }} />
            </div>
          </div>
        </div>

        {/* Placeholder: Treemap + Activity will go here in Phase 6 */}
        <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">
            {health.totalMemories} memories across {useDashboardStore.getState().getTopics().length} topics
          </h3>
          <p className="text-xs text-slate-500">Treemap visualization will render here.</p>
        </div>
      </div>
    </div>
  );
}
```

**`src/components/MemoriesTab.tsx`**:
```typescript
export function MemoriesTab() {
  return (
    <div className="p-6 overflow-auto h-full">
      <p className="text-slate-400">Table view — Phase 3</p>
    </div>
  );
}
```

**`src/components/ExploreTab.tsx`**:
```typescript
export function ExploreTab() {
  return (
    <div className="p-6 overflow-auto h-full">
      <p className="text-slate-400">Visualization selector — Phase 6</p>
    </div>
  );
}
```

### Task 2.3: Create header bar component

Create `src/components/HeaderBar.tsx`:

Extract the version/stats display from the current App.tsx into a clean header:

```typescript
// src/components/HeaderBar.tsx
import { useDashboardStore } from '@/store';

export function HeaderBar() {
  const stats = useDashboardStore((s) => s.stats);

  const version = stats?.elefante?.package_version || stats?.elefante?.config_version || '?';
  const memories = stats?.vector_store?.total_memories || 0;
  const entities = stats?.graph_store?.total_entities || 0;
  const relationships = stats?.graph_store?.total_relationships || 0;
  const snapshotAt = stats?.snapshot?.generated_at || 'unknown';

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-slate-900/90 backdrop-blur border-b border-slate-700/60">
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-white">Elefante</span>
        <span className="px-2 py-0.5 bg-slate-800 rounded text-xs text-cyan-400 font-mono">v{version}</span>
      </div>

      <div className="flex items-center gap-3 text-xs text-slate-400">
        <span>{memories} memories</span>
        <span className="text-slate-600">|</span>
        <span>{entities} entities</span>
        <span className="text-slate-600">|</span>
        <span>{relationships} links</span>
        <span className="text-slate-600">|</span>
        <span>Snapshot: {snapshotAt}</span>
      </div>
    </header>
  );
}
```

### Task 2.4: Rewrite `App.tsx`

Replace the entire `App.tsx` with the new tabbed layout:

```typescript
// src/App.tsx
import { useEffect } from 'react';
import { useDashboardStore } from '@/store';
import { HeaderBar } from '@/components/HeaderBar';
import { TabNav } from '@/components/TabNav';
import { OverviewTab } from '@/components/OverviewTab';
import { MemoriesTab } from '@/components/MemoriesTab';
import { ExploreTab } from '@/components/ExploreTab';

function App() {
  const activeTab = useDashboardStore((s) => s.activeTab);
  const fetchSnapshot = useDashboardStore((s) => s.fetchSnapshot);
  const fetchStats = useDashboardStore((s) => s.fetchStats);

  useEffect(() => {
    fetchSnapshot();
    fetchStats();
  }, [fetchSnapshot, fetchStats]);

  return (
    <div className="w-full h-screen bg-background text-text flex flex-col overflow-hidden">
      <HeaderBar />
      <TabNav />
      <main className="flex-1 overflow-hidden">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'memories' && <MemoriesTab />}
        {activeTab === 'explore' && <ExploreTab />}
      </main>
    </div>
  );
}

export default App;
```

### Task 2.5: Build and verify

```bash
npm run build
```

**Verify**: Build succeeds. Open `http://localhost:8000` — see header, three tabs, Overview tab shows health score cards. Old graph is gone from the default view.

**CHECKPOINT**: The dashboard now has a tabbed shell. The old monolith still exists as a file but is no longer imported. This is the first shippable increment.

---

## PHASE 3: Memories Table + Search

> The killer feature. Sortable table with live semantic search.

### Task 3.1: Create the memory table component

Create `src/components/MemoryTable.tsx`:

Build a full TanStack Table with columns: Title, Type, Topic, Ring, Score, Created, Status.

Column definitions:
- **Title**: `properties.summary || properties.title || name`. Clickable — sets `inspectedMemoryId`.
- **Type**: `properties.memory_type`. Color-coded badge (fact=blue, decision=amber, preference=violet, insight=emerald).
- **Topic**: `properties.topic`. Plain text.
- **Ring**: `properties.ring`. Badge.
- **Score**: `properties.score`. Number with a mini bar visualization.
- **Created**: `created_at`. Relative time ("2h ago", "65d ago").
- **Status**: `properties.processing_status`. Badge (processed=green, raw=slate).

Features:
- Sortable by all columns (click header to toggle asc/desc).
- Filterable by topic, type, ring via dropdowns from the store.
- Client-side text filter on title/summary.
- Row selection via checkbox column for bulk actions.
- Row click opens detail panel.

**Verify**: Table renders with all 121 memories. Sorting works on every column. Filter dropdowns reduce rows.

### Task 3.2: Create the memory detail panel

Create `src/components/MemoryDetailPanel.tsx`:

A slide-out panel (right side, 400px wide) that shows full memory details when a row is clicked. Extract the sidebar design from GraphCanvas.tsx lines ~1800-2860 — it's well-designed, keep the layout:

- Title (large)
- Summary
- Content (full text, scrollable)
- Metadata grid: Type, Topic, Ring, Score, Status, Tags, Created, Namespace
- Related memories (from edges)
- Debug info (collapsed by default): raw ID

Close button (X) or Escape key sets `inspectedMemoryId` to null.

### Task 3.3: Wire semantic search

Update `src/components/MemoriesTab.tsx`:

- Add search input at the top of the table.
- On input change (debounced 300ms), call `useSearch().search(query)`.
- When search results exist, show them ABOVE the table as a "Search Results" section.
- When search is empty, show the full table.
- Show loading spinner during search.
- Show error state if MCP server is not running: "Semantic search requires the Elefante server. Showing local filter instead."

### Task 3.4: Build and verify

```bash
npm run build
```

**Verify**:
1. Click "Memories" tab — see table with 121 rows.
2. Click "Title" header — rows sort alphabetically.
3. Click "Score" header — rows sort by score.
4. Type in search box — semantic results appear (requires server running).
5. Click a row — detail panel slides in from right.
6. Press Escape — panel closes.

**CHECKPOINT**: The table is now the most useful view in the entire dashboard. This alone is more valuable than the original graph.

---

## PHASE 4: Overview Tab — Treemap + Activity Feed

> Make the Overview tab the "home" that shows health + topic coverage + recent activity.

### Task 4.1: Create Treemap component

Create `src/components/TopicTreemap.tsx`:

Use `@nivo/treemap` with the data from `useTreemapData()`. Configuration:
- Color scheme: dark theme compatible (use custom colors matching the memory type palette).
- Labels: show topic name + count inside each rectangle.
- On click: set `filterTopic` in store and switch to Memories tab (filtered).
- Tooltip: show topic name, count, percentage of total.
- Identity: `id` field. Value: `value` field.
- Tile method: `squarify`.
- Inner/outer padding: 3/6.
- Label skip size: 20 (don't label tiny rectangles).
- Border: 1px slate-700.

**Note**: Nivo treemap expects a root node with children. Transform data:
```typescript
const root = {
  id: 'root',
  children: treemapData.map(d => ({ id: d.id, value: d.value })),
};
```

### Task 4.2: Create Activity Feed component

Create `src/components/ActivityFeed.tsx`:

Show the 15 most recently created memories as a vertical list:
- Each item: relative time + title + type badge.
- Click item → switch to Memories tab with that memory inspected.
- Data: sort `getMemoryNodes()` by `created_at` descending, take 15.

### Task 4.3: Integrate into OverviewTab

Update `src/components/OverviewTab.tsx`:
- Replace the Treemap placeholder with `<TopicTreemap />`.
- Add `<ActivityFeed />` below the treemap.
- Layout: 2-column on desktop (treemap left 60%, activity feed right 40%). Stack on mobile.

### Task 4.4: Build and verify

```bash
npm run build
```

**Verify**:
1. Overview tab shows health score (4 cards at top).
2. Below: Treemap showing topics (will show one giant "general" block — that's correct, the data is 91% general).
3. Right column: Activity Feed with 15 most recent memories.
4. Click a treemap section → goes to Memories tab filtered by that topic.

---

## PHASE 5: Explore Tab — Visualization Selector

> The graph lives here, alongside treemap and calendar heatmap.

### Task 5.1: Create Calendar Heatmap component

Create `src/components/CalendarHeatmap.tsx`:

Use `@nivo/calendar` with data from `useCalendarData()`. Configuration:
- `from`: earliest memory date. `to`: today.
- Color scheme: blues (empty=slate-800, low=blue-900, high=cyan-400).
- Day border: 1px slate-700.
- Month border: 2px slate-600.
- Direction: horizontal.
- On click: set filter to that date's memories + switch to Memories tab.

### Task 5.2: Create Static Network component

Create `src/components/StaticNetwork.tsx`:

Use `@nivo/network` with data from `useNetworkData()`. Configuration:
- Node size: mapped from score (4-16px).
- Node color: mapped from memory_type.
- Link color: slate-700.
- Link thickness: 1.
- Repulsivity: 6 (low — keep it dense).
- Iterations: 120 (converge to stable layout).
- On node click: set `inspectedMemoryId` + open detail panel.

### Task 5.3: Create visualization selector

Update `src/components/ExploreTab.tsx`:

- Top bar: 3 buttons (segmented control style) for Treemap | Calendar | Network.
- Active button: cyan border + bg.
- Below: render the selected visualization full-width.
- Store active selection in `activeVisualization` from Zustand.

### Task 5.4: Build and verify

```bash
npm run build
```

**Verify**:
1. Click "Explore" tab — see 3 visualization buttons.
2. Default is Treemap — same chart as Overview but full-width.
3. Click "Calendar" — see GitHub-style heatmap of memory creation dates.
4. Click "Network" — see static network graph (no physics animation).
5. Click a node in Network — detail panel opens.

---

## PHASE 6: Cleanup & Polish

> Remove dead code, add empty states, finalize styling.

### Task 6.1: Remove old GraphCanvas.tsx

Delete `src/components/GraphCanvas.tsx` (2888 lines). It is no longer imported by anything.

**Verify**: `grep -r "GraphCanvas" src/` returns no results. `npm run build` succeeds.

### Task 6.2: Add empty states to all tabs

Each tab already has data checks. Verify and improve:
- **OverviewTab**: Shows "No memories yet" message + instructions. (Done in Task 2.2)
- **MemoriesTab**: Empty table shows "No memories found. Add your first memory via MCP." in the table body.
- **ExploreTab**: Empty visualization shows "Add memories to see your knowledge map."

### Task 6.3: Keyboard shortcuts

Add global keyboard handler in `App.tsx`:
- `Escape`: Close detail panel, clear search.
- `1`/`2`/`3`: Switch tabs (only when no input is focused).

### Task 6.4: Update `index.css`

Add scrollbar styling for the table and panels:

```css
/* Custom scrollbar for dark theme */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #475569; }
```

Remove `overflow: hidden` from `body` — the table needs scrolling.

### Task 6.5: Final build and verify

```bash
npm run build
```

**Verify**:
1. All 3 tabs render without errors.
2. No console errors.
3. Table sorts, filters, and searches.
4. Visualizations render with real data.
5. Detail panel opens/closes.
6. Empty states show correctly (test by pointing to empty snapshot).
7. `GraphCanvas.tsx` is deleted.
8. Bundle size is reasonable (check `dist/assets/` — should be under 500KB gzipped).

---

## PHASE 7: Server API Enhancement (OPTIONAL — enables write operations)

> Only if the agent has bandwidth. This is Phase 4 from the roadmap (write operations).

### Task 7.1: Add PATCH endpoint for memory editing

In `src/dashboard/server.py`, add:

```python
@app.patch("/api/memories/{memory_id}")
async def update_memory(memory_id: str, updates: dict):
    """Update a memory's metadata (topic, tags, archived status)"""
    # Wire to MCP tool: elefante-MemoryUpdate
```

### Task 7.2: Add DELETE endpoint for archiving

```python
@app.delete("/api/memories/{memory_id}")
async def archive_memory(memory_id: str):
    """Archive (soft-delete) a memory"""
    # Wire to MCP tool: elefante-MemoryDelete
```

### Task 7.3: Wire to MemoriesTab

Add action buttons to the table: Archive, Edit (inline).

**This phase is DEFERRED. Ship Phases 0-6 first.**

---

## FILE INVENTORY (What the agent will create/modify)

### New files — Dashboard UI (create):
```
src/types.ts
src/store.ts
src/hooks/useVisualizationData.ts
src/hooks/useSearch.ts
src/components/TabNav.tsx
src/components/HeaderBar.tsx
src/components/OverviewTab.tsx
src/components/MemoriesTab.tsx
src/components/ExploreTab.tsx
src/components/MemoryTable.tsx
src/components/MemoryDetailPanel.tsx
src/components/TopicTreemap.tsx
src/components/ActivityFeed.tsx
src/components/CalendarHeatmap.tsx
src/components/StaticNetwork.tsx
```

### New files — Migration (create):
```
scripts/migrate_v2_memory_cleanup.py   — Phase M migration script (--dry-run / --execute)
scripts/audit_memory_quality.py        — Already created (11-section data audit)
```

### Modified files:
```
src/dashboard/ui/src/App.tsx           — Complete rewrite (tabbed layout)
src/dashboard/ui/src/main.tsx          — No changes needed
src/dashboard/ui/src/index.css         — Add scrollbar styles, remove overflow:hidden from body
src/dashboard/ui/package.json          — Version bump + new dependencies
src/dashboard/ui/vite.config.ts        — Add path alias
src/core/topology.py                   — Phase M.3/M.4: new topic + knowledge_type rules
```

### Deleted files:
```
src/dashboard/ui/src/components/GraphCanvas.tsx  — Phase 6 only, after all new components work
```

---

## EXECUTION ORDER SUMMARY

```
Phase M  →  Memory migration (3-4 hours)            ← CAN RUN IN PARALLEL WITH 0-3
Phase 0  →  npm install (15 min)
Phase 1  →  Store + hooks (1-2 hours)
Phase 2  →  Tab shell + layout (1-2 hours)           ← SHIPPABLE CHECKPOINT
Phase 3  →  Table + search (3-4 hours)               ← SHIPPABLE CHECKPOINT  
Phase M.7 → Regenerate snapshot (after M is done)    ← DATA CHECKPOINT
Phase 4  →  Overview treemap + feed (2-3 hours)      ← SHIPPABLE CHECKPOINT (now with good data)
Phase 5  →  Explore visualizations (2-3 hours)       ← SHIPPABLE CHECKPOINT
Phase 6  →  Cleanup + delete old code (1 hour)       ← FINAL SHIP
Phase 7  →  DEFERRED (write operations)
```

**Total estimated agent time: 14-19 hours of focused execution.**

Phase M is the highest-leverage work. The dashboard with clean data is 10x more impressive than a beautiful dashboard showing garbage. If forced to choose between finishing the UI or finishing the migration, **finish the migration first**.

Each phase ends with `npm run build` succeeding and a usable dashboard.

---

## PHASE M: MEMORY MIGRATION — "From Garbage to Gold"

> **Run BEFORE or IN PARALLEL with the dashboard build.** The dashboard is only as good as the data it shows. Right now the data is catastrophic.

### The Audit Results (121 memories)

```
TITLE POLLUTION
  doc.* prefix (bulk-ingested docs):          64/121  (53%)
  self./world./intent. prefix (dead V3 taxonomy):  46/121  (38%)
  Clean, human-readable titles:                11/121  (9%)  ← NINE.

TOPIC DISTRIBUTION
  "general" (uncategorized):                  110/121  (91%)
  All other topics combined:                   11/121  (9%)

KNOWLEDGE_TYPE DISTRIBUTION
  "fact" (catchall default):                  113/121  (93%)
  All other types combined:                     8/121  (7%)

PROCESSING STATUS
  "raw" (never classified by ETL):            101/121  (83%)
  "processed" (classified):                    19/121  (16%)
  "processing" (stuck):                         1/121  (1%)

SUMMARY QUALITY
  Summary == Content (useless copy):            5/121  (4%)
  Content > 500 chars (bloated):               68/121  (56%)

SCORE DISTRIBUTION
  score=10 (everything is "critical"):         49/121  (40%)
  score=1 (abandoned V4 test data):             3/121

CONTENT CATEGORIES
  About Elefante itself (navel-gazing):        75/121  (62%)
  About Maestro project:                       29/121  (24%)
  About the actual USER:                        9/121  (7%)
  Other/unclear:                                8/121  (7%)

DUPLICATES
  "V4 Cognitive Retrieval was wired":           3 identical copies

TAG POLLUTION
  Top tag: "documentation" (66 memories)
  #2 tag: "neural-register" (64 memories)
  #3 tag: "law" (36 memories)
  #4 tag: "maestro" (29 memories)
```

### Diagnosis: 7 Diseases

| # | Disease | Severity | Root Cause |
|---|---------|----------|------------|
| 1 | **Title garbage** — `self.preference:`, `world.method:`, `doc.docs/debug/...` | CRITICAL | V3 layer.sublayer taxonomy was prepended to titles. Bulk doc ingestion used file paths as titles. |
| 2 | **91% "general" topic** | CRITICAL | `topology.py` keyword matching is too weak. "code" matches coding-standards, but also matches 90% of all memories because everything mentions code. Most memories fall through to "general". |
| 3 | **93% "fact" knowledge_type** | CRITICAL | Same issue. `infer_knowledge_type()` respects `memory_type` hint, but most memories were stored as `memory_type=fact` or `memory_type=decision` and the pattern matching is too narrow. |
| 4 | **83% unprocessed** | HIGH | ETL Phase 2 (agent classification) was never run on bulk-ingested memories. The ingestion scripts bypassed the ETL pipeline. |
| 5 | **62% about Elefante itself** | HIGH | Bulk doc ingestion (`ingest_inception.py`) ate the neural-register docs — which are debug logs about Elefante's own bugs. These are not user knowledge. They're system logs stored as memories. |
| 6 | **3 duplicate V4 memories** | MEDIUM | Deduplication didn't catch near-identical content with different IDs. |
| 7 | **Score inflation** — 40% at score=10 | MEDIUM | Pre-v1.10.0 memories used user-assigned importance (everyone rates everything 10). v1.10.0 behavioral scoring starts at 50, but old data wasn't migrated. |

### Migration Tasks

#### Task M.1: Delete junk memories (the purge)

**Script**: `scripts/migrate_v2_memory_cleanup.py`

Delete memories that are NOT user knowledge:

1. **Delete 3 duplicate V4 Cognitive Retrieval memories** — keep just 1 (highest score).
2. **Delete neural-register doc chunks** — memories whose tags contain "neural-register" AND whose content starts with "SOURCE: docs/debug/". These are debug logs, not knowledge. Count: ~64 memories.
3. **Delete Maestro implementation details** — memories about `TeachingPolicy`, `brain_v3.py`, `consecutive_low_effort`. Keep Maestro architecture decisions but remove code-level implementation memories that are stale. Be conservative: only delete if content > 500 chars AND tags contain "maestro" AND processing_status == "raw". Count: ~10-15 memories.

**Verification**: Run `python3 scripts/audit_memory_quality.py` after. Total should drop from ~121 to ~40-50 high-value memories.

**CRITICAL**: Back up ChromaDB before running: `cp -r ~/.elefante/data/chromadb ~/.elefante/data/chromadb_backup_pre_v2`

#### Task M.2: Clean titles (strip V3 prefixes)

**Script**: Part of `scripts/migrate_v2_memory_cleanup.py`

For every surviving memory:

1. Strip `self.preference:`, `self.identity:`, `self.constraint:`, `world.method:`, `world.fact:`, `intent.rule:`, `doc.docs/...` prefixes from the title.
2. Strip `[hex_id]` suffixes (e.g., `[47bcd30d]`).
3. Title-case the result.
4. If title is still garbage (> 80 chars or starts with `SOURCE:`), generate a new title from the first sentence of content.
5. Update the `title` field in ChromaDB metadata.

**Examples**:

| Before | After |
|--------|-------|
| `self.preference: User preference: the best-performing LLM models are...` | `LLM Model Preferences` |
| `world.method: V4 Cognitive Retrieval was wired on December 27, 2025. The` | `V4 Cognitive Retrieval Wiring` |
| `doc.docs/debug/database-neural-register.md: LAW #1: Reserved Word Prohibition` | DELETED (neural-register) |
| `intent.rule: CRITICAL BUG FOUND (Jan 9, 2026): Student says "I am` | `Critical Bug: Student Shortcut Pattern` |
| `Self-Limit-Mandator` | `Python 3.11 Mandatory Constraint` |
| `Rule-Limit-Always` | `Always Verify Before Claiming Done` |

#### Task M.3: Re-classify topics

**Do NOT rely on the existing `topology.py` keyword matching.** It's too weak (91% "general" proves it).

Instead, use a deterministic rules-based approach with more specific patterns:

```python
TOPIC_RULES = {
    "ai-memory-systems": [
        r"elefante|chromadb|kuzu|vector.store|graph.store|embedding|memory.system",
        r"mcp|dashboard|snapshot|etl.process|topology",
    ],
    "llm-preferences": [
        r"llm|model|anthropic|opus|chatgpt|gemini|claude|gpt-4",
        r"token|context.window|temperature",
    ],
    "coding-standards": [
        r"python.3\.11|linter|black|emoji.policy|formatting",
        r"pytest|fixture|test.suite|unit.test",
    ],
    "user-identity": [
        r"user.works|data.*ai.*leader|quebec|consulting|side.project",
        r"jaime|architect|inventor|founder",
    ],
    "communication-rules": [
        r"concise|simple.terms|every.token.costs|no.fluff",
        r"claim.success|verify.before|proof.of.work",
        r"bluf|bottom.line",
    ],
    "workflow-methodology": [
        r"ultrathink|kiro|protocol|phase.\d",
        r"requirements.*design.*tasks|understand.*plan.*execute",
    ],
    "bug-reports": [
        r"critical.bug|bug.found|issue.#\d|fix|regression",
        r"symptoms?:|root.cause|workaround",
    ],
    "architecture-decisions": [
        r"chose|decided|selected|migrated|refactored",
        r"v\d+.*wired|architecture|cognitive.retrieval",
    ],
}
```

Run these against every surviving memory's content. First match wins. No match = "general" (but with better rules, this should be < 20%).

#### Task M.4: Re-classify knowledge_type

Same approach — richer pattern matching, NOT relying on weak `topology.py`:

```python
KNOWLEDGE_TYPE_RULES = {
    "law": r"LAW\s*#?\d+|MANDATORY|ALWAYS.*MUST|NEVER|FORBIDDEN|DO NOT|CRITICAL CONSTRAINT|PROHIBITED",
    "preference": r"prefer|ALWAYS\s+(communicate|use|double.check)|user.preference|like|want",
    "decision": r"chose|decided|we.will|selected|wired|migrated|refactored|switched.to",
    "principle": r"prime.directive|core.identity|foundation|the.rule:|context.first",
    "method": r"protocol|workflow|phase.\d|checklist|meta-loop|step.\d|process:",
    "insight": r"learned|realized|key.takeaway|root.cause.was|turned.out|discovery",
    "fact": None,  # fallback
}
```

#### Task M.5: Re-score using behavioral relevance

All surviving memories get their score recalculated using the v1.10.0 formula:
- Start at 50 (equal baseline).
- Apply recency decay based on `created_at` and memory_type decay rate.
- Apply access boost if `access_count > 1`.
- No manual scores. The system decides.

This replaces all the hand-coded 10s and 1s.

#### Task M.6: Re-classify rings

After knowledge_type is corrected, re-run ring classification:
- `core`: principles + top laws (explicit content patterns).
- `domain`: user preferences + identity.
- `topic`: laws + methods that scored high.
- `leaf`: everything else.

#### Task M.7: Regenerate snapshot

```bash
python3 scripts/update_dashboard_data.py
```

**Verification**: Run `python3 scripts/audit_memory_quality.py` after. Expected results:

| Metric | Before | After |
|--------|--------|-------|
| Total memories | 121 | ~40-50 |
| "general" topic | 91% | < 20% |
| "fact" knowledge_type | 93% | < 40% |
| Clean titles | 9% | 100% |
| Processing status "raw" | 83% | 0% |
| Score = 10 (inflated) | 40% | 0% (behavioral) |

### Migration Script Structure

Create `scripts/migrate_v2_memory_cleanup.py`:

```python
"""
Elefante v2.0.0 Memory Migration: From Garbage to Gold

This script:
1. Backs up ChromaDB
2. Deletes junk memories (neural-register docs, duplicates, stale impl details)
3. Cleans titles (strips V3 prefixes, generates human-readable titles)
4. Re-classifies topic, knowledge_type, ring for ALL surviving memories
5. Re-scores using behavioral relevance
6. Regenerates the dashboard snapshot

Run: python3 scripts/migrate_v2_memory_cleanup.py --dry-run   (preview changes)
Run: python3 scripts/migrate_v2_memory_cleanup.py --execute    (apply changes)
"""
```

The script MUST have:
- `--dry-run` mode that prints what it WOULD do without modifying anything.
- `--execute` mode that applies changes.
- A backup step that copies ChromaDB BEFORE any mutations.
- A summary at the end showing before/after counts for every metric.

### Migration Execution Order

```
M.1  →  Back up + delete junk (bulk neural-register + duplicates)
M.2  →  Clean titles on survivors
M.3  →  Re-classify topics
M.4  →  Re-classify knowledge_type
M.5  →  Re-score with behavioral relevance
M.6  →  Re-classify rings
M.7  →  Regenerate snapshot + re-run audit
```

**Total estimated time: 3-4 hours.**

This CAN run in parallel with Phases 0-3 of the dashboard build. The dashboard works with bad data — it just looks ugly (91% "general" treemap). After migration, the dashboard lights up.

### What the Dashboard Will Show AFTER Migration

**Health Score**: Jumps from ~15% to ~65% (better topic coverage, all processed, proper scores).

**Treemap**: Instead of one giant "general" block, shows 7-8 meaningful topic areas:
- ai-memory-systems (largest)
- workflow-methodology
- communication-rules
- coding-standards
- user-identity
- llm-preferences
- bug-reports

**Table**: 40-50 clean, titled, properly classified memories instead of 121 garbage entries.

**Calendar**: Actual activity patterns visible without the noise of bulk doc imports.

---

## ANTI-PATTERNS — DO NOT DO THESE

1. **Do NOT incrementally refactor GraphCanvas.tsx.** It's 2888 lines of coupled state. Rewriting from scratch is faster and cleaner than untangling it.
2. **Do NOT add React Router.** Three tabs don't need URL routing. Zustand tab state is sufficient. Router adds complexity without value at this scale.
3. **Do NOT add dark/light mode toggle.** Dark only. The user hasn't asked for light mode.
4. **Do NOT build Circle Packing, Sunburst, or Radar charts.** Those are v2.1.0. Ship 3 charts, not 6.
5. **Do NOT import any code from GraphCanvas.tsx into new components** except the sidebar design (Task 3.2) and the `typeColor` function. Everything else is tainted by the physics engine.
6. **Do NOT add animation to the tab transitions.** Keep it instant. Fancy transitions on 3 tabs are wasted effort.
7. **Do NOT over-engineer the health score.** Three metrics × hardcoded weights. No ML. No contradiction detection. Ship the simple version.
