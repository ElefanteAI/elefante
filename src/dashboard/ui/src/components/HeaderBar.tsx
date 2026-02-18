// Elefante Dashboard v2.0.0 - Header Bar
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
