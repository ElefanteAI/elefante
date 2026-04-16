// Elefante Dashboard v2.9.0 — Hub-Spoke Knowledge Graph (pure SVG)
import { useMemo, useState, useRef, useLayoutEffect } from 'react';
import { useDashboardStore } from '@/store';
import type { MemoryNode, GraphEdge } from '@/types';

// ── colour palette ─────────────────────────────────────────────────
const TOPIC_COLORS: Record<string, string> = {
  communication:      '#22d3ee',
  workflow:           '#fbbf24',
  'agent-behavior':   '#a78bfa',
  debugging:          '#f87171',
  'coding-standards': '#4ade80',
  architecture:       '#fb923c',
  'tools-environment':'#38bdf8',
  'user-profile':     '#f472b6',
  collaboration:      '#34d399',
  general:            '#64748b',
};

function topicColor(t: string) {
  return TOPIC_COLORS[t.toLowerCase()] ?? '#64748b';
}

function cleanTitle(t: string) {
  const s = t.replace(/^\[[\w]+\]\s*/, '');
  return s.split(' :: ').pop() || s;
}

// ── layout ─────────────────────────────────────────────────────────
interface LayoutNode {
  id:    string;
  x:     number;
  y:     number;
  r:     number;
  color: string;
  label: string;
  kind:  'hub' | 'memory';
  topic: string;
}

interface LayoutEdge {
  x1: number; y1: number;
  x2: number; y2: number;
  color: string;
  isRealEdge?: boolean;
  sourceId?: string;
  targetId?: string;
  label?: string;
}

function buildLayout(
  memories: MemoryNode[],
  snapshotEdges: GraphEdge[],
  W: number,
  H: number,
): { nodes: LayoutNode[]; edges: LayoutEdge[] } {
  // Group memories by topic
  const byTopic = new Map<string, MemoryNode[]>();
  memories.forEach((m) => {
    const t = (m.properties?.topic || 'general').toLowerCase();
    if (!byTopic.has(t)) byTopic.set(t, []);
    byTopic.get(t)!.push(m);
  });

  const topics    = Array.from(byTopic.keys());
  const N         = topics.length;
  const cx        = W / 2;
  const cy        = H / 2;
  const hubR      = Math.min(cx, cy) * 0.48;   // hub ring radius
  const spokLen   = Math.min(W, H) * 0.15;      // memory cluster radius

  const nodes: LayoutNode[] = [];
  const edges: LayoutEdge[] = [];

  topics.forEach((topic, i) => {
    const angle = (i / N) * Math.PI * 2 - Math.PI / 2;
    const hx    = cx + hubR * Math.cos(angle);
    const hy    = cy + hubR * Math.sin(angle);
    const color = topicColor(topic);

    // Hub node
    nodes.push({ id: `hub:${topic}`, x: hx, y: hy, r: 18, color, label: topic, kind: 'hub', topic });

    const mems = byTopic.get(topic)!;
    mems.forEach((m, j) => {
      const score = Number(m.properties?.score) || 5;
      const nr    = Math.max(5, Math.min(10, 4 + score * 0.6));

      let mx: number, my: number;
      if (mems.length === 1) {
        mx = hx + spokLen * 0.6 * Math.cos(angle);
        my = hy + spokLen * 0.6 * Math.sin(angle);
      } else {
        const spread  = Math.min(Math.PI * 0.9, (mems.length - 1) * 0.45);
        const memAngle = angle + (j / (mems.length - 1) - 0.5) * spread;
        mx = hx + spokLen * Math.cos(memAngle);
        my = hy + spokLen * Math.sin(memAngle);
      }

      nodes.push({
        id:    m.id,
        x:     mx,
        y:     my,
        r:     nr,
        color,
        label: cleanTitle(m.properties?.title || m.id.slice(0, 18)),
        kind:  'memory',
        topic,
      });

      // Spoke edge
      edges.push({ x1: hx, y1: hy, x2: mx, y2: my, color });
    });
  });

  // Inter-hub edges: connect adjacent hubs in the ring
  if (topics.length > 1) {
    for (let i = 0; i < topics.length; i++) {
      const a = nodes.find((n) => n.id === `hub:${topics[i]}`)!;
      const b = nodes.find((n) => n.id === `hub:${topics[(i + 1) % topics.length]}`)!;
      edges.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, color: '#334155' });
    }
  }

  // Real semantic/graph edges
  const memMap = new Map(nodes.filter(n => n.kind === 'memory').map(n => [n.id, n]));
  snapshotEdges.forEach(e => {
    const src = memMap.get(e.source);
    const tgt = memMap.get(e.target);
    if (!src || !tgt) return;

    // Filter out weak semantic connections to avoid hairballs
    if (e.type === 'semantic' && (e.similarity || 0) < 0.8) return;

    // Distinguish Graph vs Semantic
    const isGraph = e.type === 'graph' || e.label === 'CO_ACTIVATED';
    const edgeColor = isGraph ? '#a855f7' : '#10b981';

    edges.push({
      x1: src.x, y1: src.y,
      x2: tgt.x, y2: tgt.y,
      color: edgeColor,
      isRealEdge: true,
      sourceId: src.id,
      targetId: tgt.id,
      label: e.label || e.type
    });
  });

  return { nodes, edges };
}

// ── component ──────────────────────────────────────────────────────
export function KnowledgeGraph() {
  const getMemoryNodes  = useDashboardStore((s) => s.getMemoryNodes);
  const snapshotEdges   = useDashboardStore((s) => s.snapshot?.edges || []);
  const setInspectedMemoryId = useDashboardStore((s) => s.setInspectedMemoryId);
  const setActiveTab    = useDashboardStore((s) => s.setActiveTab);
  const memories        = getMemoryNodes();

  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 600, h: 500 });
  const [hovered, setHovered] = useState<string | null>(null);

  useLayoutEffect(() => {
    if (!containerRef.current) return;
    const measure = () => {
      const el = containerRef.current;
      if (!el) return;
      setSize({ w: el.clientWidth || 600, h: el.clientHeight || 500 });
    };
    measure();
    const obs = new ResizeObserver(measure);
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  const { nodes, edges } = useMemo(
    () => buildLayout(memories, snapshotEdges, size.w, size.h),
    [memories, snapshotEdges, size.w, size.h],
  );

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const hov     = hovered ? nodeMap.get(hovered) : null;

  // Connected node IDs when hovering
  const hovConnected = useMemo(() => {
    if (!hovered) return new Set<string>();
    if (hovered.startsWith('hub:')) {
      const topic = hovered.slice(4);
      return new Set(nodes.filter((n) => n.topic === topic).map((n) => n.id));
    }
    const n = nodeMap.get(hovered);
    const connected = new Set<string>();
    if (n) {
      connected.add(`hub:${n.topic}`);
      connected.add(n.id);
      edges.forEach(e => {
        if (e.isRealEdge) {
          if (e.sourceId === n.id && e.targetId) connected.add(e.targetId);
          if (e.targetId === n.id && e.sourceId) connected.add(e.sourceId);
        }
      });
    }
    return connected;
  }, [hovered, nodes, nodeMap, edges]);

  if (memories.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        No memories to visualise
      </div>
    );
  }

  const { w, h } = size;
  const dimmed = hovered !== null;

  return (
    <div ref={containerRef} className="relative w-full h-full" style={{ minHeight: 420 }}>
      <svg width={w} height={h} style={{ display: 'block', overflow: 'visible' }}>

        {/* Edges */}
        <g>
          {edges.map((e, i) => {
            const isHub = e.color === '#334155';
            const isReal = !!e.isRealEdge;
            let strokeWidth = isHub ? 0.8 : 1.2;
            if (isReal) strokeWidth = 1.5;

            let opacity = 0.35;
            if (dimmed) {
              if (isReal && (e.sourceId === hovered || e.targetId === hovered)) {
                opacity = 0.9;
                strokeWidth = 2.5;
              } else {
                opacity = isReal ? 0.05 : (isHub ? 0.05 : 0.08); 
              }
            } else if (isReal) {
              opacity = 0.6;
            } else if (isHub) {
              opacity = 0.15;
            }

            return (
              <line
                key={i}
                x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
                stroke={e.color}
                strokeWidth={strokeWidth}
                opacity={opacity}
              />
            );
          })}
        </g>

        {/* Nodes */}
        {nodes.map((n) => {
          const fade = dimmed && !hovConnected.has(n.id);
          const highlighted = hovered === n.id;
          const isHub = n.kind === 'hub';

          return (
            <g
              key={n.id}
              onMouseEnter={() => setHovered(n.id)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => {
                if (n.kind === 'memory') {
                  setInspectedMemoryId(n.id);
                  setActiveTab('memories');
                }
              }}
              style={{ cursor: n.kind === 'memory' ? 'pointer' : 'default' }}
            >
              {/* Hit target */}
              <circle cx={n.x} cy={n.y} r={n.r + 8} fill="transparent" />

              {/* Hub: diamond-ish ring */}
              {isHub && (
                <circle
                  cx={n.x} cy={n.y} r={n.r + 4}
                  fill="none"
                  stroke={n.color}
                  strokeWidth={1}
                  opacity={fade ? 0.08 : 0.25}
                />
              )}

              <circle
                cx={n.x} cy={n.y}
                r={highlighted ? n.r + 3 : n.r}
                fill={n.color}
                opacity={fade ? 0.08 : (isHub ? 0.9 : 0.75)}
                stroke={highlighted ? '#fff' : 'none'}
                strokeWidth={1.5}
              />

              {/* Hub label always visible (when not faded) */}
              {isHub && !fade && (
                <text
                  x={n.x} y={n.y - n.r - 6}
                  textAnchor="middle"
                  fontSize={9}
                  fontWeight={700}
                  fill={n.color}
                  opacity={0.85}
                  style={{ pointerEvents: 'none', textTransform: 'capitalize' }}
                >
                  {n.label.replace(/-/g, ' ')}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {hov && (
        <div
          className="absolute pointer-events-none bg-slate-900 border border-slate-600/80 rounded-lg px-3 py-2.5 shadow-xl z-20 max-w-[240px]"
          style={{
            left: Math.min(hov.x + 16, w - 256),
            top:  Math.max(hov.y - 36, 8),
          }}
        >
          <div className="font-medium text-slate-200 text-xs leading-relaxed mb-1.5">
            {hov.kind === 'hub'
              ? hov.label.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
              : hov.label}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <span
              className="text-[10px] px-1.5 py-0.5 rounded font-medium capitalize"
              style={{ backgroundColor: `${hov.color}22`, color: hov.color }}
            >
              {hov.kind === 'hub' ? 'topic hub' : hov.topic.replace(/-/g, ' ')}
            </span>
            {hov.kind === 'memory' && (() => {
              const mem = memories.find((m) => m.id === hov.id);
              const type = mem?.properties?.memory_type;
              const score = mem?.properties?.score;
              const TYPE_COLORS: Record<string, string> = {
                fact: '#3b82f6', decision: '#f59e0b',
                preference: '#8b5cf6', insight: '#10b981',
              };
              return (
                <>
                  {type && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded"
                      style={{ backgroundColor: `${TYPE_COLORS[type] ?? '#64748b'}20`, color: TYPE_COLORS[type] ?? '#94a3b8' }}>
                      {type}
                    </span>
                  )}
                  {score != null && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/60 text-cyan-400 font-bold tabular-nums">
                      {score}
                    </span>
                  )}
                </>
              );
            })()}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-3 right-4 flex gap-4 text-[10px] text-slate-500 bg-slate-900/60 p-2 rounded-md border border-slate-700/50 backdrop-blur-sm">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-cyan-400 opacity-90" />
          <span>Hub</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-slate-400 opacity-75" />
          <span>Memory</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-[#a855f7] opacity-80" />
          <span>Graph/Co-Activation Link</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-[#10b981] opacity-80" />
          <span>Semantic Link</span>
        </div>
      </div>
    </div>
  );
}
