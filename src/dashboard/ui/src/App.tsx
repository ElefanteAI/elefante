import { useState, useEffect } from 'react';

import GraphCanvas from './components/GraphCanvas';
import { LayoutDashboard, Filter, ZoomIn, ZoomOut, Maximize } from 'lucide-react';

function App() {
  const [stats, setStats] = useState<any>(null);
  const [graphStats, setGraphStats] = useState<{ memories: number; signalCoverage: number; avgConnections: number } | null>(null);
  const [space, setSpace] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [environment, setEnvironment] = useState<'all' | 'production' | 'test'>('all');
  const [status, setStatus] = useState<'all' | 'processed' | 'unprocessed'>('all');
  const [hideTestArtifacts, setHideTestArtifacts] = useState<boolean>(true);
  const [canvasCommand, setCanvasCommand] = useState<{ type: 'zoomIn' | 'zoomOut' | 'resetView'; nonce: number } | null>(null);

  useEffect(() => {
    // Fetch stats
    fetch('/api/stats')
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error("Failed to fetch stats", err));
  }, []);

  const versionLabel = stats?.elefante?.package_version || stats?.elefante?.config_version || 'unknown';

  return (
    <div className="w-full h-screen bg-background text-text overflow-hidden relative">
      <div className="absolute top-0 left-0 right-0 z-20 pointer-events-none">
        <div className="mx-4 mt-4 p-3 bg-slate-900/85 backdrop-blur border border-slate-700/60 rounded-xl shadow-lg flex flex-wrap items-center gap-3 pointer-events-auto">
          <div className="flex items-center gap-2 pr-3 border-r border-slate-700/60">
            <div className="p-2 bg-slate-800/80 rounded-lg text-cyan-400"><LayoutDashboard size={18} /></div>
            <div>
              <div className="text-sm font-semibold text-white">Cognitive Mirror</div>
              <div className="text-[10px] text-slate-400 uppercase tracking-wide">Snapshot view</div>
            </div>
          </div>

          <div className="flex items-center gap-2 pr-3 border-r border-slate-700/60 text-[11px]">
            <div className="px-2 py-1 rounded-lg bg-slate-800/80 text-cyan-300 font-semibold">{stats?.vector_store?.total_memories || 0} memories</div>
            <div className="px-2 py-1 rounded-lg bg-slate-800/80 text-emerald-300 font-semibold">{stats?.graph_store?.total_entities || 0} entities</div>
            <div className="px-2 py-1 rounded-lg bg-slate-800/80 text-amber-300 font-semibold">{stats?.graph_store?.total_relationships || 0} links</div>
          </div>

          <div className="flex items-center gap-2 pr-3 border-r border-slate-700/60 text-[11px] flex-wrap">
            <div className="px-2 py-1 rounded-lg bg-slate-800/80 text-slate-200 font-semibold">
              Elefante {stats?.elefante?.package_version || stats?.elefante?.config_version || 'unknown'}
            </div>
            <div className="px-2 py-1 rounded-lg bg-slate-800/80 text-slate-300">
              Snapshot: {stats?.snapshot?.generated_at || 'unknown'}
            </div>
            <div className="px-2 py-1 rounded-lg bg-slate-800/80 text-slate-300">
              {stats?.snapshot?.total_nodes ?? 0} nodes / {stats?.snapshot?.edges ?? 0} edges
            </div>
            {graphStats && (
              <div className="px-2 py-1 rounded-lg bg-slate-800/80 text-slate-300">
                Coverage {graphStats.signalCoverage}% · Avg {graphStats.avgConnections}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 pr-3 border-r border-slate-700/60">
            <input
              type="text"
              placeholder="Search memories"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setSearchTerm('');
              }}
              className="w-48 bg-slate-800 text-white p-2 rounded-lg border border-slate-600 focus:border-cyan-500 outline-none text-sm placeholder-slate-500"
            />
          </div>

          <div className="flex items-center gap-2 flex-wrap text-sm">
            <label className="flex items-center gap-2 text-slate-400">
              <Filter size={12} />
              <span className="text-[11px] uppercase tracking-wide">Space</span>
              <select
                className="bg-slate-800 border border-slate-700 rounded-lg p-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                value={space}
                onChange={(e) => setSpace(e.target.value)}
              >
                <option value="all">All</option>
                <option value="personal">Personal</option>
                <option value="work">Work</option>
                <option value="learning">Learning</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-slate-400">
              <span className="text-[11px] uppercase tracking-wide">Env</span>
              <select
                className="bg-slate-800 border border-slate-700 rounded-lg p-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                value={environment}
                onChange={(e) => setEnvironment(e.target.value as any)}
              >
                <option value="all">All</option>
                <option value="production">Production</option>
                <option value="test">Test</option>
              </select>
            </label>

            <button
              type="button"
              className={
                "px-3 py-2 rounded-lg border text-xs uppercase tracking-wide font-semibold transition-colors " +
                (hideTestArtifacts
                  ? "bg-slate-800/80 border-slate-700 text-emerald-300 hover:border-emerald-400"
                  : "bg-slate-800/80 border-slate-700 text-amber-300 hover:border-amber-400")
              }
              onClick={() => setHideTestArtifacts((v) => !v)}
              title="Toggle client-side hiding of test artifacts"
            >
              {hideTestArtifacts ? 'Tests: Hidden' : 'Tests: Shown'}
            </button>

            {environment === 'test' && (
              <div className="px-2 py-2 rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-200 text-xs uppercase tracking-wide font-semibold">
                Env: TEST
              </div>
            )}
            <label className="flex items-center gap-2 text-slate-400">
              <span className="text-[11px] uppercase tracking-wide">Status</span>
              <select
                className="bg-slate-800 border border-slate-700 rounded-lg p-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                value={status}
                onChange={(e) => setStatus(e.target.value as any)}
              >
                <option value="all">All</option>
                <option value="processed">Processed</option>
                <option value="unprocessed">Unprocessed</option>
              </select>
            </label>
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <button
              className="p-2 bg-slate-800/80 rounded-full border border-slate-700 hover:border-cyan-500 transition-colors"
              onClick={() => setCanvasCommand({ type: 'zoomIn', nonce: Date.now() })}
            >
              <ZoomIn size={16} />
            </button>
            <button
              className="p-2 bg-slate-800/80 rounded-full border border-slate-700 hover:border-cyan-500 transition-colors"
              onClick={() => setCanvasCommand({ type: 'zoomOut', nonce: Date.now() })}
            >
              <ZoomOut size={16} />
            </button>
            <button
              className="p-2 bg-slate-800/80 rounded-full border border-slate-700 hover:border-cyan-500 transition-colors"
              onClick={() => setCanvasCommand({ type: 'resetView', nonce: Date.now() })}
            >
              <Maximize size={16} />
            </button>
          </div>
        </div>
      </div>

      <GraphCanvas
        space={space}
        searchTerm={searchTerm}
        onSearchTermChange={setSearchTerm}
        environment={environment}
        status={status}
        hideTestArtifacts={hideTestArtifacts}
        onGraphStats={setGraphStats}
        command={canvasCommand}
      />

      <div className="absolute bottom-0 left-0 right-0 z-30 flex justify-center pb-4 pointer-events-none">
        <div className="pointer-events-auto px-4 py-2 rounded-full shadow-2xl border border-white/20 text-white text-sm font-semibold bg-gradient-to-r from-sky-500 via-indigo-500 to-pink-500 animate-pulse">
          Elefante v{versionLabel}
        </div>
      </div>
    </div>
  );
}

export default App;
