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
      {/* Header / Control Bar */}
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-4">
        <div className="bg-surface/80 backdrop-blur-md p-4 rounded-2xl border border-white/10 shadow-xl w-80">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-primary/20 rounded-lg text-primary">
              <LayoutDashboard size={24} />
            </div>
            <div>
              <h1 className="font-bold text-lg">Knowledge Garden</h1>
              <p className="text-xs text-muted">Elefante Local Brain</p>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-2 mb-4">
            <div className="bg-background/50 p-2 rounded-lg text-center">
              <div className="text-xl font-bold text-accent">{stats?.vector_store?.total_memories || 0}</div>
              <div className="text-[10px] text-muted uppercase tracking-wider">Memories</div>
            </div>
            <div className="bg-background/50 p-2 rounded-lg text-center">
              <div className="text-xl font-bold text-primary">{stats?.graph_store?.total_entities || 0}</div>
              <div className="text-[10px] text-muted uppercase tracking-wider">Episodes</div>
            </div>
          </div>

          {/* Filters */}
          <div className="space-y-2">
            <label className="text-xs text-muted font-medium flex items-center gap-2">
              <Filter size={12} /> SPACES
            </label>
            <select 
              className="w-full bg-background border border-white/10 rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
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
