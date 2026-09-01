import { useMemo } from 'react';
import { useDashboardStore } from '@/store';
import type { MemoryNode } from '@/types';

const TOPIC_PALETTE: Record<string, { bg: string; border: string; text: string }> = {
  'runtime authority':      { bg: 'rgba(200,137,77,0.08)', border: '#c8894d', text: '#d9a66e' },
  'trust boundary':         { bg: 'rgba(223,187,114,0.08)', border: '#dfbb72', text: '#dfbb72' },
  'retrieval intelligence': { bg: 'rgba(142,168,137,0.08)', border: '#8ea889', text: '#9db599' },
  'memory governance':      { bg: 'rgba(201,111,93,0.08)', border: '#c96f5d', text: '#d88a78' },
  storage:                   { bg: 'rgba(226,176,110,0.08)', border: '#e2b06e', text: '#e2b06e' },
  'host continuity':        { bg: 'rgba(185,148,115,0.08)', border: '#b99473', text: '#c8a381' },
  recovery:                 { bg: 'rgba(113,141,116,0.08)', border: '#718d74', text: '#8ea889' },
  'development process':    { bg: 'rgba(163,106,66,0.08)', border: '#a36a42', text: '#bd8050' },
  communication:      { bg: 'rgba(200,137,77,0.08)', border: '#c8894d', text: '#d9a66e' },
  workflow:           { bg: 'rgba(223,187,114,0.08)', border: '#dfbb72', text: '#dfbb72' },
  'agent-behavior':   { bg: 'rgba(182,119,68,0.08)', border: '#b67744', text: '#c98d59' },
  debugging:          { bg: 'rgba(201,111,93,0.08)', border: '#c96f5d', text: '#d88a78' },
  'coding-standards': { bg: 'rgba(142,168,137,0.08)', border: '#8ea889', text: '#9db599' },
  architecture:       { bg: 'rgba(226,176,110,0.08)', border: '#e2b06e', text: '#e2b06e' },
  'tools-environment':{ bg: 'rgba(163,106,66,0.08)', border: '#a36a42', text: '#bd8050' },
  'user-profile':     { bg: 'rgba(185,148,115,0.08)', border: '#b99473', text: '#c8a381' },
  collaboration:      { bg: 'rgba(113,141,116,0.08)', border: '#718d74', text: '#8ea889' },
  general:            { bg: 'rgba(111,103,91,0.08)', border: '#6f675b', text: '#b5aa98' },
};

const TYPE_COLORS: Record<string, string> = {
  fact: '#c8894d', decision: '#dfbb72',
  preference: '#b99473', insight: '#718d74',
  note: '#6f675b', conversation: '#b5aa98',
};

function cleanTitle(title: string): string {
  const withoutTag = title.replace(/^\[[\w]+\]\s*/, '');
  const parts = withoutTag.split(' :: ');
  return parts[parts.length - 1] || withoutTag;
}

function toLabel(topic: string): string {
  return topic.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function TopicTreemap() {
  const getMemoryNodes = useDashboardStore((s) => s.getMemoryNodes);
  const memories = getMemoryNodes();

  const groups = useMemo(() => {
    const map = new Map<string, MemoryNode[]>();
    memories.forEach((m) => {
      const t = (m.properties?.topic || 'general').toLowerCase();
      if (!map.has(t)) map.set(t, []);
      map.get(t)!.push(m);
    });
    return Array.from(map.entries())
      .map(([topic, mems]) => {
        const types: Record<string, number> = {};
        let scoreSum = 0;
        mems.forEach((m) => {
          const t = m.properties?.memory_type || 'other';
          types[t] = (types[t] || 0) + 1;
          scoreSum += Number(m.properties?.score) || 0;
        });
        return {
          topic,
          memories: mems,
          types,
          avgScore: mems.length > 0 ? Math.round(scoreSum / mems.length) : 0,
        };
      })
      .sort((a, b) => b.memories.length - a.memories.length);
  }, [memories]);

  if (groups.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        No topic data available
      </div>
    );
  }

  return (
    <div className="p-5 overflow-auto h-full">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 max-w-5xl mx-auto">
        {groups.map(({ topic, memories: mems, types, avgScore }) => {
          const palette = TOPIC_PALETTE[topic] ?? TOPIC_PALETTE['general'];
          const topMems = [...mems]
            .sort((a, b) => (Number(b.properties?.score) || 0) - (Number(a.properties?.score) || 0))
            .slice(0, 4);

          return (
            <div
              key={topic}
              className="rounded-xl border p-4 flex flex-col gap-3 hover:brightness-110 transition-all"
              style={{ background: palette.bg, borderColor: palette.border + '40' }}
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-sm font-bold tracking-tight" style={{ color: palette.text }}>
                    {toLabel(topic)}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">avg vitality {avgScore}</div>
                </div>
                <div className="text-2xl font-black tabular-nums shrink-0"
                  style={{ color: palette.text, opacity: 0.35 }}>
                  {mems.length}
                </div>
              </div>

              {/* Type breakdown pills */}
              <div className="flex flex-wrap gap-1">
                {Object.entries(types)
                  .sort((a, b) => b[1] - a[1])
                  .map(([type, count]) => (
                    <span
                      key={type}
                      className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                      style={{
                        backgroundColor: `${TYPE_COLORS[type] ?? '#64748b'}20`,
                        color: TYPE_COLORS[type] ?? '#94a3b8',
                      }}
                    >
                      {type}{count > 1 && <span className="opacity-50 ml-0.5">×{count}</span>}
                    </span>
                  ))}
              </div>

              <div className="h-px opacity-15" style={{ backgroundColor: palette.border }} />

              {/* Top memories */}
              <ul className="space-y-2">
                {topMems.map((m) => (
                  <li key={m.id} className="flex items-start gap-2">
                    <div className="mt-[5px] w-1.5 h-1.5 rounded-full shrink-0 opacity-50"
                      style={{ backgroundColor: palette.border }} />
                    <span className="text-xs text-slate-300 leading-relaxed line-clamp-2">
                      {cleanTitle(m.properties?.title || m.id.slice(0, 20))}
                    </span>
                  </li>
                ))}
                {mems.length > 4 && (
                  <li className="text-[10px] text-slate-600 pl-3.5">+{mems.length - 4} more</li>
                )}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
