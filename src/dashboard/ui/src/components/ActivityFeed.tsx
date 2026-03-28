// Elefante Dashboard v2.2.2 - Activity Feed
import { useMemo } from 'react';
import { Clock, ArrowRight } from 'lucide-react';
import { useDashboardStore } from '@/store';
import type { MemoryNode } from '@/types';

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

const typeColors: Record<string, string> = {
  fact: 'bg-cyan-500/20 text-cyan-300',
  decision: 'bg-amber-500/20 text-amber-300',
  preference: 'bg-pink-500/20 text-pink-300',
  insight: 'bg-emerald-500/20 text-emerald-300',
};

export function ActivityFeed() {
  const getMemoryNodes = useDashboardStore((s) => s.getMemoryNodes);
  const setActiveTab = useDashboardStore((s) => s.setActiveTab);
  const setInspectedMemoryId = useDashboardStore((s) => s.setInspectedMemoryId);
  const memories = getMemoryNodes();

  const recentMemories = useMemo(() => {
    return [...memories]
      .sort((a, b) => {
        const aTime = new Date(a.created_at || 0).getTime();
        const bTime = new Date(b.created_at || 0).getTime();
        return bTime - aTime;
      })
      .slice(0, 15);
  }, [memories]);

  const handleClick = (memory: MemoryNode) => {
    setInspectedMemoryId(memory.id);
    setActiveTab('memories');
  };

  if (recentMemories.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-slate-500">
        No recent activity
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {recentMemories.map((memory) => (
        <button
          key={memory.id}
          onClick={() => handleClick(memory)}
          className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-slate-700/40 transition-colors group"
        >
          <div className="flex items-start gap-2.5">
            <div className="flex-shrink-0 mt-0.5">
              <Clock size={12} className="text-slate-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm text-slate-200 truncate group-hover:text-white transition-colors">
                {memory.properties.title || memory.properties.summary || memory.name || 'Untitled'}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[11px] text-slate-500">
                  {formatRelativeTime(memory.created_at)}
                </span>
                {memory.properties.memory_type && (
                  <span className={`px-1.5 py-0 rounded text-[10px] ${typeColors[memory.properties.memory_type] || 'bg-slate-500/20 text-slate-400'}`}>
                    {memory.properties.memory_type}
                  </span>
                )}
              </div>
            </div>
            <ArrowRight size={12} className="text-slate-700 group-hover:text-slate-400 transition-colors mt-1 flex-shrink-0" />
          </div>
        </button>
      ))}
    </div>
  );
}
