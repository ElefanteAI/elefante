// Elefante Dashboard v2.7.1 - Main App
import { useEffect, useCallback } from 'react';
import { useDashboardStore } from '@/store';
import { HeaderBar } from '@/components/HeaderBar';
import { TabNav } from '@/components/TabNav';
import { OverviewTab } from '@/components/OverviewTab';
import { MemoriesTab } from '@/components/MemoriesTab';
import { ExploreTab } from '@/components/ExploreTab';
import type { Tab } from '@/types';

function App() {
  const activeTab = useDashboardStore((s) => s.activeTab);
  const setActiveTab = useDashboardStore((s) => s.setActiveTab);
  const fetchStats = useDashboardStore((s) => s.fetchStats);
  const fetchSnapshot = useDashboardStore((s) => s.fetchSnapshot);
  const isLoading = useDashboardStore((s) => s.isLoading);
  const error = useDashboardStore((s) => s.error);
  const setInspectedMemoryId = useDashboardStore((s) => s.setInspectedMemoryId);
  const setSearchQuery = useDashboardStore((s) => s.setSearchQuery);
  const version = useDashboardStore((s) => s.stats?.elefante?.package_version ?? '...');

  // Initial data fetch
  useEffect(() => {
    fetchStats();
    fetchSnapshot();
  }, [fetchStats, fetchSnapshot]);

  // Global keyboard shortcuts
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Skip if user is typing in an input
    const target = e.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return;

    const tabMap: Record<string, Tab> = { '1': 'overview', '2': 'memories', '3': 'explore' };
    if (tabMap[e.key]) {
      setActiveTab(tabMap[e.key]);
      return;
    }

    if (e.key === 'Escape') {
      setInspectedMemoryId(null);
      setSearchQuery('');
    }
  }, [setActiveTab, setInspectedMemoryId, setSearchQuery]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const renderTab = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewTab />;
      case 'memories':
        return <MemoriesTab />;
      case 'explore':
        return <ExploreTab />;
      default:
        return <OverviewTab />;
    }
  };

  return (
    <div className="w-full h-screen bg-slate-950 text-slate-100 overflow-hidden flex flex-col">
      {/* Header */}
      <HeaderBar />

      {/* Tab Navigation */}
      <TabNav />

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {error && (
          <div className="p-4 m-4 bg-red-900/30 border border-red-500/50 rounded-lg text-red-200 text-sm">
            <strong>Error:</strong> {error}
          </div>
        )}
        
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="w-12 h-12 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <div className="text-slate-400">Connecting to Elefante server...</div>
              <div className="text-slate-600 text-xs mt-2">This may take a moment on first launch</div>
            </div>
          </div>
        ) : (
          renderTab()
        )}
      </main>

      {/* Footer */}
      <footer className="px-4 py-2 bg-slate-900/50 border-t border-slate-800 text-center">
        <span className="text-xs text-slate-500">
          Elefante v{version} &middot; Knowledge Workbench &middot; <span className="text-slate-600">1/2/3 to switch tabs</span>
        </span>
      </footer>
    </div>
  );
}

export default App;
