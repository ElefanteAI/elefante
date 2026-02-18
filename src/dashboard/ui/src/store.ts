// Elefante Dashboard v2.0.0 - Zustand Store
import { create } from 'zustand';
import type { Tab, Snapshot, StatsResponse, MemoryNode, VisualizationType } from './types';

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
  activeVisualization: VisualizationType;
  setActiveVisualization: (v: VisualizationType) => void;

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
      set({ 
        snapshot: { 
          nodes: data.nodes || [], 
          edges: data.edges || [], 
          stats: data.stats 
        }, 
        isLoading: false 
      });
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
