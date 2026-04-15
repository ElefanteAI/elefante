// Elefante Dashboard v2.6.0 - Tab Navigation
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
