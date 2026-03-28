// Elefante Dashboard v2.2.2 — Memory Insights
import { useMemo } from 'react';
import { useDashboardStore } from '@/store';

const TYPE_COLORS: Record<string, string> = {
  fact: '#3b82f6', decision: '#f59e0b',
  preference: '#8b5cf6', insight: '#10b981',
  note: '#64748b', conversation: '#94a3b8',
};

const TOPIC_COLORS: Record<string, string> = {
  communication: '#22d3ee', workflow: '#fbbf24',
  'agent-behavior': '#a78bfa', debugging: '#f87171',
  'coding-standards': '#4ade80', architecture: '#fb923c',
  'tools-environment': '#38bdf8', 'user-profile': '#f472b6',
  collaboration: '#34d399', general: '#64748b',
};

function cleanTitle(title: string): string {
  const s = title.replace(/^\[[\w]+\]\s*/, '');
  const parts = s.split(' :: ');
  return parts[parts.length - 1] || s;
}

function BarRow({
  label, count, total, color,
}: { label: string; count: number; total: number; color: string }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-400 w-28 truncate capitalize">{label.replace(/-/g, ' ')}</span>
      <div className="flex-1 bg-slate-700/50 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-1.5 rounded-full"
          style={{ width: `${pct}%`, backgroundColor: color, transition: 'width 0.4s ease' }}
        />
      </div>
      <span className="text-xs text-slate-400 w-5 text-right">{count}</span>
    </div>
  );
}

export function CalendarHeatmap() {
  const getMemoryNodes = useDashboardStore((s) => s.getMemoryNodes);
  const memories = getMemoryNodes();

  const data = useMemo(() => {
    if (memories.length === 0) return null;

    const scores = memories.map((m) => Number(m.properties?.score) || 0);
    const scoreDist: Record<string, number> = {};
    scores.forEach((s) => {
      const k = String(s);
      scoreDist[k] = (scoreDist[k] || 0) + 1;
    });

    const types: Record<string, number> = {};
    memories.forEach((m) => {
      const t = m.properties?.memory_type || 'other';
      types[t] = (types[t] || 0) + 1;
    });

    const topics: Record<string, number> = {};
    memories.forEach((m) => {
      const t = (m.properties?.topic || 'general').toLowerCase();
      topics[t] = (topics[t] || 0) + 1;
    });

    const byScore = [...memories].sort(
      (a, b) => (Number(b.properties?.score) || 0) - (Number(a.properties?.score) || 0)
    );

    return {
      total: memories.length,
      maxScore: Math.max(...scores),
      minScore: Math.min(...scores),
      avgScore: Math.round(scores.reduce((s, v) => s + v, 0) / scores.length),
      scoreDist,
      types,
      topics,
      topByScore: byScore.slice(0, 6),
    };
  }, [memories]);

  if (!data) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        No memory data to display
      </div>
    );
  }

  const { total, maxScore, minScore, avgScore, scoreDist, types, topics, topByScore } = data;

  // Build score bar from sorted score values
  const sortedScores = Object.entries(scoreDist).sort((a, b) => Number(a[0]) - Number(b[0]));

  return (
    <div className="p-5 overflow-auto h-full">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 max-w-4xl mx-auto">

        {/* Score Stats + Distribution */}
        <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-200">Score Distribution</h3>

          {/* KPI row */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Average', value: avgScore },
              { label: 'Highest', value: maxScore },
              { label: 'Lowest',  value: minScore },
            ].map(({ label, value }) => (
              <div key={label} className="bg-slate-900/60 rounded-lg p-3 text-center">
                <div className="text-xl font-black text-cyan-300 tabular-nums">{value}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">{label}</div>
              </div>
            ))}
          </div>

          {/* Per-score bars */}
          <div className="space-y-2">
            {sortedScores.reverse().map(([score, count]) => (
              <BarRow
                key={score}
                label={`Score ${score}`}
                count={count}
                total={total}
                color={Number(score) >= 8 ? '#22d3ee' : Number(score) >= 6 ? '#fbbf24' : '#f87171'}
              />
            ))}
          </div>
        </div>

        {/* Type + Topic breakdown */}
        <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl p-5 space-y-5">
          <div>
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Memory Types</h3>
            <div className="space-y-2">
              {Object.entries(types)
                .sort((a, b) => b[1] - a[1])
                .map(([type, count]) => (
                  <BarRow
                    key={type}
                    label={type}
                    count={count}
                    total={total}
                    color={TYPE_COLORS[type] ?? '#64748b'}
                  />
                ))}
            </div>
          </div>

          <div className="border-t border-slate-700/40 pt-4">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Topics</h3>
            <div className="space-y-2">
              {Object.entries(topics)
                .sort((a, b) => b[1] - a[1])
                .map(([topic, count]) => (
                  <BarRow
                    key={topic}
                    label={topic}
                    count={count}
                    total={total}
                    color={TOPIC_COLORS[topic] ?? '#64748b'}
                  />
                ))}
            </div>
          </div>
        </div>

        {/* Top 6 by score */}
        <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Highest Scored Memories</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {topByScore.map((m) => {
              const score = Number(m.properties?.score) || 0;
              const type  = m.properties?.memory_type || '';
              const topic = (m.properties?.topic || 'general').toLowerCase();
              const tc    = TOPIC_COLORS[topic] ?? '#64748b';
              return (
                <div
                  key={m.id}
                  className="bg-slate-900/60 border border-slate-700/30 rounded-lg p-3 flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between">
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded font-medium capitalize"
                      style={{ backgroundColor: `${tc}20`, color: tc }}
                    >
                      {topic.replace(/-/g, ' ')}
                    </span>
                    <span className="text-xs font-bold text-cyan-400 tabular-nums">{score}</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed line-clamp-3">
                    {cleanTitle(m.properties?.title || m.id.slice(0, 24))}
                  </p>
                  {type && (
                    <span
                      className="self-start text-[10px] px-1.5 py-0.5 rounded"
                      style={{
                        backgroundColor: `${TYPE_COLORS[type] ?? '#64748b'}20`,
                        color: TYPE_COLORS[type] ?? '#94a3b8',
                      }}
                    >
                      {type}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

      </div>
    </div>
  );
}
