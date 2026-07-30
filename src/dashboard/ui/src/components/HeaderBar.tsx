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
    <header className="min-h-[72px] flex items-center justify-between px-6 md:px-8 bg-slate-950/90 backdrop-blur border-b elefante-hairline">
      <div className="flex items-center gap-3.5">
        <div className="elefante-mark" aria-hidden="true">
          <div className="elefante-emblem" />
          <div className="elefante-emblem elefante-emblem-network" />
        </div>
        <div>
          <div className="flex items-center gap-2.5">
            <span className="text-sm font-semibold text-slate-100">Elefante</span>
            <span className="text-[10px] text-cyan-400 elefante-mono">v{version}</span>
          </div>
          <span className="block mt-0.5 text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.18em]">
            Memory intelligence
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 text-[10px] text-slate-500 elefante-mono uppercase tracking-[0.08em]">
        <span className="hidden lg:inline">{memories} memories</span>
        <span className="hidden lg:inline text-slate-700">·</span>
        <span className="hidden lg:inline">{entities} entities</span>
        <span className="hidden lg:inline text-slate-700">·</span>
        <span className="hidden md:inline">{relationships} links</span>
        <span className="hidden md:inline text-slate-700">·</span>
        <span
          className={stale ? 'text-amber-400/90' : 'text-emerald-400/90'}
          title={`Snapshot generated: ${snapshotAt}`}
        >
          {stale ? `stale · ${ageLabel}` : `current · ${ageLabel}`}
        </span>

        <button
          onClick={() => refreshSnapshot()}
          disabled={isRefreshing}
          title="Reload the current dashboard snapshot"
          className={
            'flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] font-medium border transition-colors ' +
            (isRefreshing
              ? 'bg-slate-800/40 elefante-hairline text-slate-600 cursor-not-allowed'
              : stale
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20'
              : 'bg-slate-800/40 elefante-hairline text-slate-400 hover:text-slate-100 hover:border-cyan-500/50')
          }
        >
          <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
          {isRefreshing ? 'Reloading...' : 'Reload'}
        </button>
      </div>
    </header>
  );
}
