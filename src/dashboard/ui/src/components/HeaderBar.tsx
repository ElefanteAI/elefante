// Elefante Dashboard v2.4.0 - Header Bar
import { useDashboardStore } from '@/store';
import { RefreshCw } from 'lucide-react';

function formatSnapshotAge(generatedAt: string): { label: string; stale: boolean } {
  if (!generatedAt || generatedAt === 'unknown') return { label: 'unknown', stale: true };
  const then = new Date(generatedAt).getTime();
  if (isNaN(then)) return { label: 'unknown', stale: true };
  const diffMs = Date.now() - then;
  const minutes = Math.floor(diffMs / 60000);
  const hours = Math.floor(diffMs / 3600000);
  const days = Math.floor(diffMs / 86400000);
  const stale = minutes >= 60;
  let label: string;
  if (minutes < 1) label = 'just now';
  else if (minutes < 60) label = `${minutes}m ago`;
  else if (hours < 24) label = `${hours}h ago`;
  else label = `${days}d ago`;
  return { label, stale };
}

export function HeaderBar() {
  const stats = useDashboardStore((s) => s.stats);
  const isRefreshing = useDashboardStore((s) => s.isRefreshing);
  const refreshSnapshot = useDashboardStore((s) => s.refreshSnapshot);

  const version = stats?.elefante?.package_version || stats?.elefante?.config_version || '?';
  const memories = stats?.vector_store?.total_memories || 0;
  const entities = stats?.graph_store?.total_entities || 0;
  const relationships = stats?.graph_store?.total_relationships || 0;
  const snapshotAt = stats?.snapshot?.generated_at || 'unknown';
  const { label: ageLabel, stale } = formatSnapshotAge(snapshotAt);

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
        <span
          className={stale ? 'text-amber-400/80' : 'text-slate-400'}
          title={`Snapshot generated: ${snapshotAt}`}
        >
          {stale ? `⚠ ${ageLabel}` : ageLabel}
        </span>

        <button
          onClick={() => refreshSnapshot()}
          disabled={isRefreshing}
          title="Regenerate snapshot from live data"
          className={
            'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-all ' +
            (isRefreshing
              ? 'bg-slate-800/40 border-slate-700/40 text-slate-600 cursor-not-allowed'
              : stale
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20'
              : 'bg-slate-800/40 border-slate-700/40 text-slate-400 hover:text-slate-200 hover:border-slate-600')
          }
        >
          <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>
    </header>
  );
}
