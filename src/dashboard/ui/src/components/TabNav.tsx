import { useDashboardStore } from '@/store';
import type { Tab } from '@/types';

const tabs: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Home' },
  { id: 'recall', label: 'Recall' },
  { id: 'memories', label: 'Memory Intelligence' },
  { id: 'explore', label: 'Connections' },
  { id: 'projects', label: 'Projects' },
  { id: 'recover', label: 'Recover' },
];

export function TabNav() {
  const activeTab = useDashboardStore((s) => s.activeTab);
  const setActiveTab = useDashboardStore((s) => s.setActiveTab);

  return (
    <nav aria-label="Elefante Home workspaces" className="flex items-center justify-start gap-4 overflow-x-auto bg-slate-950/75 px-4 backdrop-blur border-b elefante-hairline lg:justify-center lg:gap-8">
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
