import { useDashboardStore } from '@/store';
import type { Tab } from '@/types';

const tabs: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Briefing' },
  { id: 'memories', label: 'Memories' },
  { id: 'explore', label: 'Connections' },
];

export function TabNav() {
  const activeTab = useDashboardStore((s) => s.activeTab);
  const setActiveTab = useDashboardStore((s) => s.setActiveTab);

  return (
    <nav className="flex items-center justify-center gap-6 md:gap-10 bg-slate-950/75 backdrop-blur border-b elefante-hairline px-4">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveTab(tab.id)}
          aria-current={activeTab === tab.id ? 'page' : undefined}
          className={
            'px-2 py-3 text-xs font-medium tracking-wide transition-colors border-b-2 ' +
            (activeTab === tab.id
              ? 'text-slate-100 border-cyan-400'
              : 'text-slate-600 border-transparent hover:text-slate-300 hover:border-slate-700')
          }
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
