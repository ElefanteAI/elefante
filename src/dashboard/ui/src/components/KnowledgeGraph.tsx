import { useEffect, useMemo, useState } from 'react';
import { useDashboardStore } from '@/store';
import { edgeEndpoints, type GraphEdge, type MemoryNode } from '@/types';

const CAUSAL_LABELS = new Set([
  'CHALLENGED_BY',
  'CONTRADICTS',
  'CORRECTED_BY',
  'SUPERSEDED_BY',
  'LED_TO',
  'DEPENDS_ON',
  'ENABLES',
  'GUARDED_BY',
  'GUARDS',
  'ENFORCES',
  'ENFORCED_BY',
  'GOVERNS',
]);

const GUARD_LABELS = new Set([
  'GUARDED_BY',
  'GUARDS',
  'ENFORCES',
  'ENFORCED_BY',
  'GOVERNS',
]);

interface TrailEdge {
  source: string;
  target: string;
  label: string;
  type: string;
  similarity?: number;
}

interface DecisionTrail {
  id: string;
  title: string;
  topic: string;
  nodes: MemoryNode[];
  edges: TrailEdge[];
  decisionId: string;
}

function cleanTitle(value: string) {
  const withoutPrefix = value.replace(/^\[[\w]+\]\s*/, '');
  return withoutPrefix.split(' :: ').pop() || withoutPrefix;
}

function memoryTitle(memory: MemoryNode) {
  return cleanTitle(memory.properties?.title || memory.name || memory.id);
}

function memoryScore(memory: MemoryNode) {
  return Number(memory.properties?.score) || 0;
}

function relationshipText(label: string) {
  return label.toLowerCase().replace(/_/g, ' ');
}

function relationshipForMemory(edge: TrailEdge, memoryId: string) {
  if (edge.source === memoryId) return relationshipText(edge.label);
  const inverse: Record<string, string> = {
    CHALLENGED_BY: 'challenges',
    CONTRADICTS: 'contradicts',
    CORRECTED_BY: 'corrects',
    SUPERSEDED_BY: 'supersedes',
    LED_TO: 'resulted from',
    DEPENDS_ON: 'supports',
    ENABLES: 'enabled by',
    GUARDED_BY: 'safeguards',
    GUARDS: 'guarded by',
    ENFORCES: 'enforced by',
    ENFORCED_BY: 'enforces',
    GOVERNS: 'governed by',
  };
  return inverse[edge.label] || 'connected from';
}

function roleFor(memory: MemoryNode) {
  const status = String(memory.properties?.status || '').toLowerCase();
  const type = String(memory.properties?.memory_type || '').toLowerCase();

  if (memory.properties?.deprecated || status === 'superseded') {
    return { label: 'Old assumption', color: '#c96f5d' };
  }
  if (type === 'decision') return { label: 'Decision', color: '#dfbb72' };
  if (type === 'fact' || type === 'insight') {
    return { label: 'Evidence', color: type === 'fact' ? '#c8894d' : '#718d74' };
  }
  if (type === 'directive' || type === 'specification') {
    return { label: type === 'directive' ? 'Directive' : 'Specification', color: '#8ea889' };
  }
  return { label: type || 'Memory', color: '#b99473' };
}

function orderTrailNodes(nodes: MemoryNode[], edges: TrailEdge[]) {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const indegree = new Map(nodes.map((node) => [node.id, 0]));
  const outgoing = new Map<string, string[]>();

  edges.forEach((edge) => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) return;
    indegree.set(edge.target, (indegree.get(edge.target) || 0) + 1);
    outgoing.set(edge.source, [...(outgoing.get(edge.source) || []), edge.target]);
  });

  const queue = nodes
    .filter((node) => (indegree.get(node.id) || 0) === 0)
    .sort((a, b) => memoryScore(b) - memoryScore(a));
  const ordered: MemoryNode[] = [];
  const visited = new Set<string>();

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (visited.has(current.id)) continue;
    visited.add(current.id);
    ordered.push(current);

    (outgoing.get(current.id) || []).forEach((targetId) => {
      const nextIndegree = (indegree.get(targetId) || 0) - 1;
      indegree.set(targetId, nextIndegree);
      if (nextIndegree === 0) {
        const target = nodes.find((node) => node.id === targetId);
        if (target) queue.push(target);
      }
    });
  }

  nodes
    .filter((node) => !visited.has(node.id))
    .sort((a, b) => memoryScore(b) - memoryScore(a))
    .forEach((node) => ordered.push(node));

  return ordered;
}

function deriveDecisionTrails(memories: MemoryNode[], snapshotEdges: GraphEdge[]) {
  const memoryMap = new Map(memories.map((memory) => [memory.id, memory]));
  const trailEdges: TrailEdge[] = snapshotEdges
    .map((edge) => {
      const { source, target } = edgeEndpoints(edge);
      return {
        source,
        target,
        label: edge.label || edge.type || 'RELATES_TO',
        type: edge.type || 'graph',
        similarity: edge.similarity,
      };
    })
    .filter((edge) => {
      if (!memoryMap.has(edge.source) || !memoryMap.has(edge.target)) return false;
      return edge.type !== 'semantic' && CAUSAL_LABELS.has(edge.label);
    });

  const adjacency = new Map<string, Set<string>>();
  trailEdges.forEach((edge) => {
    adjacency.set(edge.source, new Set([...(adjacency.get(edge.source) || []), edge.target]));
    adjacency.set(edge.target, new Set([...(adjacency.get(edge.target) || []), edge.source]));
  });

  const visited = new Set<string>();
  const trails: DecisionTrail[] = [];

  adjacency.forEach((_neighbors, startId) => {
    if (visited.has(startId)) return;
    const queue = [startId];
    const componentIds: string[] = [];

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (visited.has(current)) continue;
      visited.add(current);
      componentIds.push(current);
      (adjacency.get(current) || []).forEach((neighbor) => {
        if (!visited.has(neighbor)) queue.push(neighbor);
      });
    }

    const componentSet = new Set(componentIds);
    const componentEdges = trailEdges.filter(
      (edge) => componentSet.has(edge.source) && componentSet.has(edge.target),
    );
    const componentNodes = componentIds
      .map((id) => memoryMap.get(id))
      .filter((node): node is MemoryNode => Boolean(node));
    const orderedNodes = orderTrailNodes(componentNodes, componentEdges);
    const decision =
      orderedNodes
        .filter((node) => node.properties?.memory_type === 'decision')
        .sort((a, b) => memoryScore(b) - memoryScore(a))[0] ||
      [...orderedNodes].sort((a, b) => memoryScore(b) - memoryScore(a))[0];

    trails.push({
      id: componentIds.sort().join('|'),
      title: memoryTitle(decision),
      topic: decision.properties?.topic || 'Connected memory',
      nodes: orderedNodes,
      edges: componentEdges,
      decisionId: decision.id,
    });
  });

  return trails.sort((a, b) => {
    const decisionDelta =
      Number(b.nodes.some((node) => node.properties?.memory_type === 'decision')) -
      Number(a.nodes.some((node) => node.properties?.memory_type === 'decision'));
    if (decisionDelta !== 0) return decisionDelta;
    const edgeDelta = b.edges.length - a.edges.length;
    if (edgeDelta !== 0) return edgeDelta;
    return memoryScore(
      b.nodes.find((node) => node.id === b.decisionId) || b.nodes[0],
    ) - memoryScore(
      a.nodes.find((node) => node.id === a.decisionId) || a.nodes[0],
    );
  });
}

export function KnowledgeGraph() {
  const getMemoryNodes = useDashboardStore((state) => state.getMemoryNodes);
  const snapshotEdges = useDashboardStore((state) => state.snapshot?.edges || []);
  const setInspectedMemoryId = useDashboardStore((state) => state.setInspectedMemoryId);
  const setActiveTab = useDashboardStore((state) => state.setActiveTab);
  const memories = getMemoryNodes();

  const trails = useMemo(
    () => deriveDecisionTrails(memories, snapshotEdges),
    [memories, snapshotEdges],
  );
  const [selectedTrailId, setSelectedTrailId] = useState('');
  const [selectedMemoryId, setSelectedMemoryId] = useState('');

  const selectedTrail =
    trails.find((trail) => trail.id === selectedTrailId) || trails[0] || null;
  const selectedMemory =
    selectedTrail?.nodes.find((node) => node.id === selectedMemoryId) ||
    selectedTrail?.nodes.find((node) => node.id === selectedTrail.decisionId) ||
    selectedTrail?.nodes[0] ||
    null;

  useEffect(() => {
    if (!selectedTrail) return;
    if (!selectedTrail.nodes.some((node) => node.id === selectedMemoryId)) {
      setSelectedMemoryId(selectedTrail.decisionId);
    }
  }, [selectedMemoryId, selectedTrail]);

  const semanticBridgeCount = useMemo(
    () =>
      snapshotEdges.filter((edge) => {
        if (edge.type !== 'semantic') return false;
        const { source, target } = edgeEndpoints(edge);
        return memories.some((memory) => memory.id === source) &&
          memories.some((memory) => memory.id === target);
      }).length,
    [memories, snapshotEdges],
  );
  const retiredCount = memories.filter(
    (memory) =>
      memory.properties?.deprecated ||
      String(memory.properties?.status || '').toLowerCase() === 'superseded',
  ).length;
  const guardCount = trails.reduce(
    (total, trail) =>
      total + trail.edges.filter((edge) => GUARD_LABELS.has(edge.label)).length,
    0,
  );

  if (memories.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        No memories to visualise
      </div>
    );
  }

  if (!selectedTrail || !selectedMemory) {
    return (
      <div className="flex h-full items-center justify-center px-8 text-center">
        <div className="max-w-lg">
          <div className="elefante-mono mb-3 text-[10px] uppercase tracking-[0.24em] text-cyan-500">
            No decision trails yet
          </div>
          <p className="text-sm leading-6 text-slate-400">
            Connect explicit evidence, decisions, and safeguards to preserve a
            represented decision trail.
          </p>
        </div>
      </div>
    );
  }

  const selectedRole = roleFor(selectedMemory);
  const selectedRelationships = selectedTrail.edges.filter(
    (edge) =>
      edge.source === selectedMemory.id || edge.target === selectedMemory.id,
  );

  return (
    <div className="h-full min-h-0 overflow-y-auto bg-slate-950 lg:flex lg:flex-col lg:overflow-hidden">
      <div className="grid grid-cols-[1fr_auto] border-b border-slate-700 px-6 py-4 lg:shrink-0">
        <div>
          <div className="elefante-mono mb-1 text-[10px] uppercase tracking-[0.24em] text-cyan-500">
            Decision graph
          </div>
          <h2 className="text-lg font-medium tracking-[-0.02em] text-slate-100">
            Trace one represented decision.
          </h2>
        </div>
        <div className="hidden items-end gap-7 pb-0.5 text-right md:flex">
          <div>
            <strong className="block text-base font-medium text-slate-100">{trails.length}</strong>
            <span className="elefante-mono text-[9px] uppercase tracking-[0.16em] text-slate-500">
              grounded trails
            </span>
          </div>
          <div>
            <strong className="block text-base font-medium text-red-400">{retiredCount}</strong>
            <span className="elefante-mono text-[9px] uppercase tracking-[0.16em] text-slate-500">
              old assumptions
            </span>
          </div>
          <div>
            <strong className="block text-base font-medium text-emerald-400">{guardCount}</strong>
            <span className="elefante-mono text-[9px] uppercase tracking-[0.16em] text-slate-500">
              safeguard links
            </span>
          </div>
          <div>
            <strong className="block text-base font-medium text-violet-400">{semanticBridgeCount}</strong>
            <span className="elefante-mono text-[9px] uppercase tracking-[0.16em] text-slate-500">
              topic bridges
            </span>
          </div>
        </div>
      </div>

      <div className="lg:grid lg:min-h-0 lg:flex-1 lg:grid-cols-[286px_minmax(0,1fr)]">
        <aside className="border-b border-slate-700 lg:min-h-0 lg:overflow-y-auto lg:border-b-0 lg:border-r">
          <div className="elefante-mono border-b border-slate-800 px-5 py-3 text-[9px] uppercase tracking-[0.2em] text-slate-500">
            Preserved reasoning
          </div>
          {trails.map((trail, index) => {
            const active = trail.id === selectedTrail.id;
            return (
              <button
                key={trail.id}
                onClick={() => {
                  setSelectedTrailId(trail.id);
                  setSelectedMemoryId(trail.decisionId);
                }}
                className={`block w-full border-b border-slate-800 px-5 py-4 text-left transition-colors ${
                  active
                    ? 'bg-cyan-500/10 shadow-[inset_2px_0_0_#c8894d]'
                    : 'hover:bg-slate-100/5'
                }`}
              >
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="elefante-mono text-[9px] uppercase tracking-[0.18em] text-cyan-500">
                    {String(index + 1).padStart(2, '0')} · {trail.topic}
                  </span>
                  <span className="elefante-mono text-[9px] text-slate-500">
                    {trail.nodes.length}M / {trail.edges.length}L
                  </span>
                </div>
                <strong className={`block text-[13px] font-medium leading-5 ${
                  active ? 'text-slate-100' : 'text-slate-400'
                }`}>
                  {trail.title}
                </strong>
              </button>
            );
          })}
        </aside>

        <section className="lg:min-h-0 lg:overflow-y-auto">
          <div className="border-b border-slate-700 px-5 py-5 sm:px-7">
            <div className="mb-4 flex items-start justify-between gap-6">
              <div>
                <div className="elefante-mono mb-1 text-[9px] uppercase tracking-[0.2em] text-slate-500">
                  {selectedTrail.topic} · {selectedTrail.edges.length} explicit relationships
                </div>
                <h3 className="max-w-2xl text-xl font-medium tracking-[-0.025em] text-slate-100">
                  {selectedTrail.title}
                </h3>
              </div>
              <span className="elefante-mono shrink-0 border border-amber-400/30 px-2 py-1 text-[9px] uppercase tracking-[0.16em] text-amber-400">
                stored links
              </span>
            </div>

            <div className="flex items-stretch gap-4 overflow-x-auto pb-2">
              {selectedTrail.nodes.map((memory, index) => {
                const role = roleFor(memory);
                const active = memory.id === selectedMemory.id;

                return (
                    <button
                      key={memory.id}
                      onClick={() => setSelectedMemoryId(memory.id)}
                      className={`w-[160px] shrink-0 border px-4 py-4 text-left transition-all 2xl:w-[178px] ${
                        active
                          ? 'border-slate-100 bg-slate-100/5'
                          : 'border-slate-700 bg-slate-900 hover:border-slate-500'
                      }`}
                    >
                      <div className="mb-5 flex items-center justify-between">
                        <span
                          className="elefante-mono text-[9px] uppercase tracking-[0.17em]"
                          style={{ color: role.color }}
                        >
                          {String(index + 1).padStart(2, '0')} · {role.label}
                        </span>
                        <span className="elefante-mono text-[10px] text-slate-500">
                          {memoryScore(memory)}
                        </span>
                      </div>
                      <strong className="block text-[13px] font-medium leading-[1.45] text-slate-100">
                        {memoryTitle(memory)}
                      </strong>
                    </button>
                );
              })}
            </div>

            <ul aria-label="Stored relationships" className="mt-4 space-y-2">
              {selectedTrail.edges.map((edge) => {
                const source = selectedTrail.nodes.find((node) => node.id === edge.source)!;
                const target = selectedTrail.nodes.find((node) => node.id === edge.target)!;
                return (
                  <li
                    key={`${edge.source}-${edge.target}-${edge.label}`}
                    data-source={edge.source}
                    data-target={edge.target}
                    data-relationship={edge.label}
                    className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 border-t border-slate-800 pt-2 text-[11px] leading-4"
                  >
                    <button
                      onClick={() => setSelectedMemoryId(source.id)}
                      className="text-left text-slate-400 hover:text-cyan-500"
                    >
                      {memoryTitle(source)}
                    </button>
                    <span className="elefante-mono max-w-[90px] text-center text-[9px] text-violet-400">
                      {relationshipText(edge.label)} →
                    </span>
                    <button
                      onClick={() => setSelectedMemoryId(target.id)}
                      className="text-left text-slate-400 hover:text-cyan-500"
                    >
                      {memoryTitle(target)}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_280px]">
            <div className="px-5 py-5 sm:px-7">
              <div className="mb-3 flex items-center gap-3">
                <span
                  className="elefante-mono text-[9px] uppercase tracking-[0.18em]"
                  style={{ color: selectedRole.color }}
                >
                  {selectedRole.label}
                </span>
                <span className="h-px w-8 bg-slate-700" />
                <span className="elefante-mono text-[9px] uppercase tracking-[0.16em] text-slate-500">
                  {selectedMemory.properties?.status || 'current'}
                </span>
              </div>
              <h4 className="mb-2 text-base font-medium text-slate-100">
                {memoryTitle(selectedMemory)}
              </h4>
              <p className="max-w-3xl text-[13px] leading-6 text-slate-400">
                {selectedMemory.description || selectedMemory.properties?.summary}
              </p>
              <div className="mt-4 border-l border-cyan-500/40 pl-3">
                <span className="elefante-mono block text-[8px] uppercase tracking-[0.18em] text-slate-500">
                  Grounded in
                </span>
                <strong className="mt-1 block text-[11px] font-medium text-cyan-500">
                  {selectedMemory.properties?.evidence || selectedMemory.properties?.source}
                </strong>
              </div>
            </div>

            <div className="border-t border-slate-700 px-5 py-5 xl:border-l xl:border-t-0">
              <div className="elefante-mono mb-3 text-[9px] uppercase tracking-[0.18em] text-slate-500">
                What it changes
              </div>
              <div className="space-y-2">
                {selectedRelationships.map((edge) => {
                  const peerId = edge.source === selectedMemory.id ? edge.target : edge.source;
                  const peer = selectedTrail.nodes.find((node) => node.id === peerId);
                  return (
                    <button
                      key={`${edge.source}-${edge.target}-${edge.label}`}
                      onClick={() => peer && setSelectedMemoryId(peer.id)}
                      className="block w-full border-t border-slate-800 pt-2 text-left"
                    >
                      <span className="elefante-mono block text-[8px] uppercase tracking-[0.16em] text-violet-400">
                        {relationshipForMemory(edge, selectedMemory.id)}
                      </span>
                      <strong className="mt-1 block text-[11px] font-medium leading-4 text-slate-400">
                        {peer ? memoryTitle(peer) : peerId}
                      </strong>
                    </button>
                  );
                })}
              </div>
              <button
                onClick={() => {
                  setInspectedMemoryId(selectedMemory.id);
                  setActiveTab('memories');
                }}
                className="elefante-mono mt-5 border-b border-cyan-500 pb-1 text-[9px] uppercase tracking-[0.16em] text-cyan-500 hover:text-amber-400"
              >
                Open complete memory →
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
