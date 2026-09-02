import { useEffect, useLayoutEffect, useCallback, useState } from 'react';
import { useDashboardStore } from '@/store';
import { HeaderBar } from '@/components/HeaderBar';
import { TabNav } from '@/components/TabNav';
import { OverviewTab } from '@/components/OverviewTab';
import { RecallTab } from '@/components/RecallTab';
import { MemoriesTab } from '@/components/MemoriesTab';
import { ExploreTab } from '@/components/ExploreTab';
import { ProjectsTab } from '@/components/ProjectsTab';
import { RecoverTab } from '@/components/RecoverTab';
import type { Tab } from '@/types';

type Theme = 'light' | 'dark';

function App() {
  const [theme, setTheme] = useState<Theme>(() => (
    window.localStorage.getItem('elefante-dashboard-theme') === 'dark' ? 'dark' : 'light'
  ));
  const activeTab = useDashboardStore((s) => s.activeTab);
  const setActiveTab = useDashboardStore((s) => s.setActiveTab);
  const fetchStats = useDashboardStore((s) => s.fetchStats);
  const fetchSnapshot = useDashboardStore((s) => s.fetchSnapshot);
  const fetchSessionIntelligence = useDashboardStore((s) => s.fetchSessionIntelligence);
  const isLoading = useDashboardStore((s) => s.isLoading);
  const error = useDashboardStore((s) => s.error);
  const setInspectedMemoryId = useDashboardStore((s) => s.setInspectedMemoryId);
  const setSearchQuery = useDashboardStore((s) => s.setSearchQuery);
  const version = useDashboardStore((s) => s.stats?.elefante?.package_version ?? '...');
  const controlConnecting = useDashboardStore((s) => s.controlConnecting);
  const controlEnabled = useDashboardStore((s) => s.controlEnabled);
  const controlAvailability = useDashboardStore((s) => s.controlAvailability);
  const controlSessionError = useDashboardStore((s) => s.controlSessionError);
  const activeProjectId = useDashboardStore((s) => s.activeProjectId);
  const snapshotContext = useDashboardStore((s) => s.snapshot?.snapshot_context);
  const initializeControlSession = useDashboardStore((s) => s.initializeControlSession);
  const surfaceLabel = snapshotContext?.mode === 'showcase'
    ? 'example workspace'
    : controlEnabled
      ? 'live local session'
      : controlAvailability === 'snapshot_only'
        ? 'read-only snapshot'
        : 'local snapshot';

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem('elefante-dashboard-theme', theme);
  }, [theme]);

  // Prefer a one-time contextual fragment when an agent supplied one; a bare
  // localhost visit establishes the same bounded session through the daemon.
  useLayoutEffect(() => {
    void initializeControlSession();
  }, [initializeControlSession]);

  // Initial data fetch
  useEffect(() => {
    fetchStats();
    fetchSessionIntelligence();
    fetchSnapshot();
  }, [fetchStats, fetchSessionIntelligence, fetchSnapshot]);

  // Global keyboard shortcuts
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Skip if user is typing in an input
    const target = e.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return;

    const tabMap: Record<string, Tab> = {
      '1': 'overview',
      '2': 'recall',
      '3': 'memories',
      '4': 'explore',
      '5': 'projects',
      '6': 'recover',
    };
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
      case 'recall':
        return <RecallTab />;
      case 'memories':
        return <MemoriesTab />;
      case 'explore':
        return <ExploreTab />;
      case 'projects':
        return <ProjectsTab />;
      case 'recover':
        return <RecoverTab />;
      default:
        return <OverviewTab />;
    }
  };

  return (
    <div className="elefante-shell w-full h-screen bg-slate-950 text-slate-100 overflow-hidden flex flex-col">
      {/* Header */}
      <HeaderBar
        theme={theme}
        onToggleTheme={() => setTheme((current) => current === 'light' ? 'dark' : 'light')}
      />

      {/* Tab Navigation */}
      <TabNav />

      {controlSessionError && !controlEnabled && (
        <div role="alert" className="relative z-[60] flex shrink-0 items-center justify-between gap-4 border-b border-amber-300/40 bg-slate-950 px-5 py-3 text-xs text-amber-200">
          <span>{controlSessionError} No operation is retried automatically.</span>
          <button type="button" disabled={controlConnecting} onClick={() => void initializeControlSession(activeProjectId ?? undefined)} className="min-h-10 shrink-0 border border-amber-300/50 px-4 disabled:opacity-40">
            {controlConnecting ? 'Reconnecting…' : 'Reconnect Home'}
          </button>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {error && (
          <div className="p-4 m-4 bg-red-900/30 border border-red-500/50 text-red-200 text-sm">
            <strong>Error:</strong> {error}
          </div>
        )}
        
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="w-10 h-10 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <div className="text-slate-300">Reading the local memory snapshot...</div>
              <div className={`text-xs mt-2 elefante-mono uppercase tracking-widest ${controlEnabled ? 'text-amber-300' : 'text-slate-600'}`}>
                {snapshotContext?.mode === 'showcase'
                  ? 'Reading example workspace · no customer data'
                  : controlEnabled
                  ? 'Local session active · loopback'
                  : controlConnecting
                    ? 'Connecting to Elefante · loopback'
                    : 'Local snapshot · loopback'}
              </div>
            </div>
          </div>
        ) : (
          renderTab()
        )}
      </main>

      {/* Footer */}
      <footer className="px-4 py-2 bg-slate-900/50 border-t elefante-hairline text-center">
        <span className="text-xs text-slate-500">
          Elefante v{version} &middot; Memory Intelligence &middot;{' '}
          <span className={controlEnabled ? 'text-amber-300' : snapshotContext?.mode === 'showcase' ? 'text-cyan-300' : 'text-slate-600'}>
            {controlConnecting ? 'connecting local service' : surfaceLabel}
          </span>{' '}
          <span className="text-slate-600">· 1/2/3/4/5/6 to switch views</span>
        </span>
      </footer>
    </div>
  );
}

export default App;
