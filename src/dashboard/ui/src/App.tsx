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
        background: 'red',
        color: 'white',
        zIndex: 9999,
        textAlign: 'center',
        fontWeight: 'bold',
        padding: '8px',
        fontSize: '14px'
      }}>
        🚨 DEBUG: VERSION 26.0 - TOPOLOGY PRIME (DATA SYNCED) 🚨
      </div>
      
      {/* SPRINT 8: FIX UI COLLISION - Vertical Stack Layout */}
      <div className="absolute top-4 left-4 z-50 flex flex-col gap-3 pointer-events-auto" style={{ marginTop: '40px' }}>
        
        {/* 1. Title Card */}
        <div className="bg-slate-900/90 backdrop-blur-md p-4 rounded-xl border border-slate-700 shadow-xl w-80">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg text-cyan-400">
              <LayoutDashboard size={20} />
            </div>
            <div>
              <h1 className="font-bold text-base text-white">Knowledge Garden</h1>
              <p className="text-[10px] text-slate-400">Elefante Local Brain</p>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-slate-800/50 p-2 rounded-lg text-center">
              <div className="text-lg font-bold text-cyan-400">{stats?.vector_store?.total_memories || 0}</div>
              <div className="text-[9px] text-slate-400 uppercase tracking-wider">Memories</div>
            </div>
            <div className="bg-slate-800/50 p-2 rounded-lg text-center">
              <div className="text-lg font-bold text-emerald-400">{stats?.graph_store?.total_entities || 0}</div>
              <div className="text-[9px] text-slate-400 uppercase tracking-wider">Entities</div>
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
