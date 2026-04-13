// Elefante Dashboard v2.3.1 - Explore Tab
import { useDashboardStore } from '@/store';
import { KnowledgeGraph } from '@/components/KnowledgeGraph';
import { TopicTreemap } from '@/components/TopicTreemap';
import { CalendarHeatmap } from '@/components/CalendarHeatmap';
import { LayoutGrid, BarChart2, Network } from 'lucide-react';
import type { VisualizationType } from '@/types';

const vizOptions: { id: VisualizationType; label: string; icon: React.ReactNode; desc: string }[] = [
  { id: 'treemap',  label: 'Topics',   icon: <LayoutGrid size={14} />, desc: 'Knowledge grouped by topic' },
  { id: 'calendar', label: 'Insights', icon: <BarChart2 size={14} />,  desc: 'Score & type breakdown' },
  { id: 'network',  label: 'Graph',    icon: <Network size={14} />,    desc: 'Topic hub-spoke network' },
];

export function ExploreTab() {
  const isLoading       = useDashboardStore((s) => s.isLoading);
  const activeViz       = useDashboardStore((s) => s.activeVisualization);
  const setActiveViz    = useDashboardStore((s) => s.setActiveVisualization);
  const getMemoryNodes  = useDashboardStore((s) => s.getMemoryNodes);
  const memories        = getMemoryNodes();

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-10 bg-slate-800 rounded w-48 animate-pulse" />
        <div className="h-96 bg-slate-800/60 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (memories.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <h2 className="text-xl font-semibold text-slate-200 mb-2">No data to visualise</h2>
          <p className="text-slate-400 text-sm">Add memories to see your knowledge map.</p>
        </div>
      </div>
    );
  }

  const active = vizOptions.find((v) => v.id === activeViz);

  return (
    <div className="h-full flex flex-col">
      {/* Selector */}
      <div className="px-6 py-3 border-b border-slate-700/60 bg-slate-800/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1 bg-slate-900/60 rounded-lg p-1 border border-slate-700/40">
            {vizOptions.map((opt) => (
              <button
                key={opt.id}
                onClick={() => setActiveViz(opt.id)}
                className={
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ' +
                  (activeViz === opt.id
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200 border border-transparent')
                }
              >
                {opt.icon}
                {opt.label}
              </button>
            ))}
          </div>
          <div className="text-xs text-slate-500 hidden sm:block">
            {active?.desc}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 bg-slate-900/40 overflow-hidden">
        {activeViz === 'treemap'  && <TopicTreemap />}
        {activeViz === 'calendar' && <CalendarHeatmap />}
        {activeViz === 'network'  && <KnowledgeGraph />}
      </div>
    </div>
  );
}