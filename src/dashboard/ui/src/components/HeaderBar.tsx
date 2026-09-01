import { useDashboardStore } from '@/store';
import { Moon, RefreshCw, Sun } from 'lucide-react';

interface HeaderBarProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

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

export function HeaderBar({ theme, onToggleTheme }: HeaderBarProps) {
  const stats = useDashboardStore((s) => s.stats);
  const snapshotContext = useDashboardStore((s) => s.snapshot?.snapshot_context);
  const isRefreshing = useDashboardStore((s) => s.isRefreshing);
  const refreshSnapshot = useDashboardStore((s) => s.refreshSnapshot);

  const version = stats?.elefante?.package_version || stats?.elefante?.config_version || '?';
  const memories = stats?.vector_store?.total_memories || 0;
  const entities = stats?.graph_store?.total_entities || 0;
  const relationships = stats?.graph_store?.total_relationships || 0;
  const snapshotAt = stats?.snapshot?.generated_at || 'unknown';
  const { label: ageLabel, stale } = formatSnapshotAge(snapshotAt);
  const isShowcase = snapshotContext?.mode === 'showcase';

  return (
    <header className="grid min-h-[104px] grid-cols-1 content-center gap-2 px-4 py-3 sm:min-h-[72px] sm:flex sm:items-center sm:justify-between sm:px-6 sm:py-0 md:px-8 bg-slate-950/90 backdrop-blur border-b elefante-hairline">
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

      <div className="flex w-full min-w-0 items-center justify-between gap-2 text-[10px] text-slate-500 elefante-mono uppercase tracking-[0.08em] sm:w-auto sm:justify-end sm:gap-3">
        <span className="hidden lg:inline">{memories} memories</span>
        <span className="hidden lg:inline text-slate-700">·</span>
        <span className="hidden lg:inline">{entities} entities</span>
        <span className="hidden lg:inline text-slate-700">·</span>
        <span className="hidden md:inline">{relationships} links</span>
        <span className="hidden md:inline text-slate-700">·</span>
        <span
          className={`min-w-0 truncate ${isShowcase ? 'text-cyan-300' : stale ? 'text-amber-400/90' : 'text-emerald-400/90'}`}
          title={isShowcase ? 'Deterministic dashboard example' : `Snapshot generated: ${snapshotAt}`}
        >
          {isShowcase ? 'Example workspace' : stale ? `stale · ${ageLabel}` : `current · ${ageLabel}`}
        </span>

        <button
          type="button"
          onClick={onToggleTheme}
          title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
          className="flex shrink-0 items-center gap-1.5 border elefante-hairline bg-slate-900/60 px-2.5 py-1.5 text-[10px] font-medium text-slate-500 transition-colors hover:text-slate-100"
        >
          {theme === 'light' ? <Moon size={12} aria-hidden="true" /> : <Sun size={12} aria-hidden="true" />}
          <span className="hidden sm:inline">{theme === 'light' ? 'Dark' : 'Light'}</span>
        </button>

        <button
          onClick={() => refreshSnapshot()}
          disabled={isRefreshing}
          title={isShowcase ? 'Reload the example snapshot' : 'Reload the current dashboard snapshot'}
          className={
            'flex shrink-0 items-center gap-1.5 px-2.5 py-1.5 text-[10px] font-medium border transition-colors ' +
            (isRefreshing
              ? 'bg-slate-800/40 elefante-hairline text-slate-600 cursor-not-allowed'
              : stale
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20'
              : 'bg-slate-800/40 elefante-hairline text-slate-400 hover:text-slate-100 hover:border-cyan-500/50')
          }
        >
          <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
          <span className="hidden sm:inline">
            {isRefreshing ? 'Reloading...' : isShowcase ? 'Reload example' : 'Reload'}
          </span>
          <span className="sm:hidden">{isRefreshing ? 'Loading...' : 'Reload'}</span>
        </button>
      </div>
    </header>
  );
}
