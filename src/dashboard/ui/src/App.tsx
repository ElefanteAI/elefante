import { useState, useEffect } from 'react';

import GraphCanvas from './components/GraphCanvas';
import { LayoutDashboard, Filter, ZoomIn, ZoomOut, Maximize } from 'lucide-react';

function App() {
  const [stats, setStats] = useState<any>(null);
  const [space, setSpace] = useState<string>('all');

  useEffect(() => {
    // Fetch stats
    fetch('/api/stats')
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error("Failed to fetch stats", err));
  }, []);

  return (
    <div className="w-full h-screen bg-background text-text overflow-hidden relative">
      {/* CANARY: Visual Proof of New Code */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        background: 'linear-gradient(90deg, #06b6d4, #8b5cf6, #ec4899)',
        color: 'white',
        zIndex: 9999,
        textAlign: 'center',
        fontWeight: 'bold',
        padding: '8px',
        fontSize: '14px',
        letterSpacing: '2px'
      }}>
        🧠 VERSION 30.0 - V3 LEGEND IMPLEMENTATION - PROTOCOL ACTIVE 🧠
      </div>
      
      {/* V3.0 COGNITIVE MIRROR - V3 LEGEND */}
      <div className="absolute top-4 right-4 bg-slate-900/95 p-4 rounded-xl border border-cyan-500/30 shadow-[0_0_20px_rgba(6,182,212,0.15)] text-xs font-mono z-50" style={{ marginTop: '40px', minWidth: '220px' }}>
        <div className="font-bold text-cyan-400 mb-3 text-sm">🧠 V30 LEGEND</div>
        
        {/* Stats Row */}
        <div className="flex justify-between mb-3 pb-2 border-b border-slate-700">
          <div className="text-center">
            <div className="text-lg font-bold text-white">{stats?.vector_store?.total_memories || 0}</div>
            <div className="text-[9px] text-slate-500">MEMORIES</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-emerald-400">{stats?.graph_store?.total_entities || 0}</div>
            <div className="text-[9px] text-slate-500">ENTITIES</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-amber-400">{stats?.graph_store?.total_relationships || 0}</div>
            <div className="text-[9px] text-slate-500">LINKS</div>
          </div>
        </div>

        {/* Memory Type Legend - V3 LAYERS */}
        <div className="mb-3">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">V3 Layers</div>
          <div className="space-y-1.5">
            {/* SELF LAYER */}
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]"></div>
              <span className="text-slate-300">SELF (Identity)</span>
              <span className="text-[9px] text-red-500 ml-auto">WHO</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-orange-500 shadow-[0_0_6px_rgba(249,115,22,0.5)]"></div>
              <span className="text-slate-300">SELF (Pref)</span>
            </div>

            {/* WORLD LAYER */}
            <div className="flex items-center gap-2 mt-2">
              <div className="w-3 h-3 rounded-full bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.5)]"></div>
              <span className="text-slate-300">WORLD (Fact)</span>
              <span className="text-[9px] text-blue-500 ml-auto">WHAT</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-purple-600 shadow-[0_0_6px_rgba(124,58,237,0.5)]"></div>
              <span className="text-slate-300">WORLD (Fail)</span>
            </div>

            {/* INTENT LAYER */}
            <div className="flex items-center gap-2 mt-2">
              <div className="w-3 h-3 rounded-full bg-white shadow-[0_0_6px_rgba(255,255,255,0.5)]"></div>
              <span className="text-slate-300">INTENT (Rule)</span>
              <span className="text-[9px] text-white ml-auto">HOW</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.5)]"></div>
              <span className="text-slate-300">INTENT (Goal)</span>
            </div>
          </div>
        </div>

        {/* Size Legend */}
        <div className="pt-2 border-t border-slate-700">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">Importance</div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              <div className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center text-[8px]">●</div>
              <span className="text-[9px] text-slate-500">Low</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded-full bg-white/40 flex items-center justify-center text-[8px]">●</div>
              <span className="text-[9px] text-slate-500">Med</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-white/60 animate-pulse"></div>
              <span className="text-[9px] text-slate-500">Critical</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* SPRINT 8: FIX UI COLLISION - Vertical Stack Layout */}
      <div className="absolute top-4 left-4 z-50 flex flex-col gap-3 pointer-events-auto" style={{ marginTop: '40px' }}>
        
        {/* 1. Title Card - COGNITIVE MIRROR */}
        <div className="bg-slate-900/90 backdrop-blur-md p-4 rounded-xl border border-cyan-500/30 shadow-xl w-80">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-gradient-to-br from-cyan-500/30 to-purple-500/30 rounded-lg text-cyan-400 animate-pulse">
              <LayoutDashboard size={24} />
            </div>
            <div>
              <h1 className="font-bold text-lg text-white">Cognitive Mirror</h1>
              <p className="text-[10px] text-cyan-400/80">Your Second Brain • Elefante v28</p>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-gradient-to-r from-cyan-500/10 to-purple-500/10 p-3 rounded-lg mb-3 border border-cyan-500/20">
            <div className="text-[10px] text-cyan-400 uppercase tracking-wider mb-1">💡 Quick Tip</div>
            <div className="text-xs text-slate-300">Click any node to inspect. Shift+Click to focus and see connections.</div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-slate-800/50 p-2 rounded-lg text-center border border-slate-700/50 hover:border-cyan-500/50 transition-colors">
              <div className="text-lg font-bold text-cyan-400">{stats?.vector_store?.total_memories || 0}</div>
              <div className="text-[9px] text-slate-400 uppercase tracking-wider">Thoughts</div>
            </div>
            <div className="bg-slate-800/50 p-2 rounded-lg text-center border border-slate-700/50 hover:border-emerald-500/50 transition-colors">
              <div className="text-lg font-bold text-emerald-400">{stats?.graph_store?.total_relationships || 0}</div>
              <div className="text-[9px] text-slate-400 uppercase tracking-wider">Connections</div>
            </div>
          </div>
        </div>

        {/* 2. Search Bar (Separate Card) */}
        <div className="bg-slate-900/90 backdrop-blur-md p-3 rounded-xl border border-slate-700 shadow-xl w-80">
          <input
            type="text"
            placeholder="🔍 Search memories..."
            className="w-full bg-slate-800 text-white p-2 rounded-lg border border-slate-600 focus:border-cyan-500 outline-none text-sm placeholder-slate-500"
          />
        </div>

        {/* 3. Filters (Separate Card) */}
        <div className="bg-slate-900/90 backdrop-blur-md p-3 rounded-xl border border-slate-700 shadow-xl w-80">
          <label className="text-xs text-slate-400 font-medium flex items-center gap-2 mb-2">
            <Filter size={12} /> SPACES
          </label>
          <select
            className="w-full bg-slate-800 border border-slate-600 rounded-lg p-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
            value={space}
            onChange={(e) => setSpace(e.target.value)}
          >
            <option value="all">All Spaces</option>
            <option value="personal">Personal</option>
            <option value="work">Work</option>
            <option value="learning">Learning</option>
          </select>
        </div>
      </div>

      {/* Main Canvas */}
      <GraphCanvas space={space} />
      
      {/* Zoom Controls (Mock) */}
      <div className="absolute bottom-8 right-8 flex flex-col gap-2">
        <button className="p-3 bg-surface/80 backdrop-blur-md rounded-full border border-white/10 hover:bg-white/10 transition-colors">
          <ZoomIn size={20} />
        </button>
        <button className="p-3 bg-surface/80 backdrop-blur-md rounded-full border border-white/10 hover:bg-white/10 transition-colors">
          <ZoomOut size={20} />
        </button>
        <button className="p-3 bg-surface/80 backdrop-blur-md rounded-full border border-white/10 hover:bg-white/10 transition-colors">
          <Maximize size={20} />
        </button>
      </div>
    </div>
  );
}

export default App;
