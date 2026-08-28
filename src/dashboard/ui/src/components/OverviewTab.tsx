import { useMemo } from 'react';
import { useHealthScore } from '@/hooks/useVisualizationData';
import { SessionIntelligencePanel } from '@/components/SessionIntelligencePanel';
import { useDashboardStore } from '@/store';
import { edgeEndpoints, type GraphEdge, type MemoryNode } from '@/types';

type BriefingStep = {
  node: MemoryNode;
  label: string;
  tone: 'clay' | 'copper' | 'brass' | 'sage';
};

const EDGE_LABELS = {
  evidence: new Set(['LED_TO', 'SUPERSEDED_BY', 'CORRECTED_BY']),
  assumption: new Set(['CHALLENGED_BY', 'CONTRADICTS']),
  guard: new Set(['GUARDED_BY', 'GUARDS', 'ENFORCED_BY']),
};

const TYPE_LABELS: Record<string, string> = {
  directive: 'Constraint',
  specification: 'Architecture',
  decision: 'Decision',
  insight: 'Insight',
  preference: 'Preference',
  fact: 'Fact',
  note: 'Note',
  conversation: 'Conversation',
};

function asMemory(node: unknown): node is MemoryNode {
  return Boolean(node && typeof node === 'object' && (node as MemoryNode).type === 'memory');
}

function scoreOf(node: MemoryNode): number {
  return Number(node.properties?.score) || 0;
}

function accessCountOf(node: MemoryNode): number {
  return Number(node.properties?.access_count) || 0;
}

function isCurrent(node: MemoryNode): boolean {
  const status = String(node.properties?.status || '').toLowerCase();
  return !node.properties?.archived
    && !node.properties?.deprecated
    && !['redundant', 'contradictory', 'superseded'].includes(status);
}

function chooseFeatured(memories: MemoryNode[]): MemoryNode | null {
  const ranked = [...memories].sort((a, b) => {
    const typeA = a.properties?.memory_type === 'decision' ? 1 : 0;
    const typeB = b.properties?.memory_type === 'decision' ? 1 : 0;
    if (typeA !== typeB) return typeB - typeA;
    if (isCurrent(a) !== isCurrent(b)) return isCurrent(b) ? 1 : -1;
    if (scoreOf(a) !== scoreOf(b)) return scoreOf(b) - scoreOf(a);
    return accessCountOf(b) - accessCountOf(a);
  });
  return ranked[0] ?? null;
}

function normalizedLabel(edge: GraphEdge): string {
  return String(edge.label || edge.type || '').trim().toUpperCase();
}

function deriveBriefingSteps(
  featured: MemoryNode,
  memories: MemoryNode[],
  edges: GraphEdge[],
): { steps: BriefingStep[]; isEvolution: boolean } {
  const byId = new Map(memories.map((memory) => [memory.id, memory]));
  const normalized = edges.map((edge) => ({ edge, ...edgeEndpoints(edge) }));

  const evidenceEdge = normalized.find(({ target, edge }) =>
    target === featured.id && EDGE_LABELS.evidence.has(normalizedLabel(edge)),
  );
  const evidence = evidenceEdge ? byId.get(evidenceEdge.source) : undefined;

  const assumptionEdge = evidence
    ? normalized.find(({ target, edge }) =>
        target === evidence.id && EDGE_LABELS.assumption.has(normalizedLabel(edge)),
      )
    : undefined;
  const assumption = assumptionEdge ? byId.get(assumptionEdge.source) : undefined;

  const guardEdge = normalized.find(({ source, edge }) =>
    source === featured.id && EDGE_LABELS.guard.has(normalizedLabel(edge)),
  );
  const guard = guardEdge ? byId.get(guardEdge.target) : undefined;

  if (assumption && evidence && guard) {
    return {
      isEvolution: true,
      steps: [
        { node: assumption, label: 'Old assumption', tone: 'clay' },
        { node: evidence, label: 'Evidence', tone: 'copper' },
        { node: featured, label: 'Decision', tone: 'brass' },
        { node: guard, label: 'Enforced guard', tone: 'sage' },
      ],
    };
  }

  const relatedIds = new Set<string>();
  normalized.forEach(({ source, target }) => {
    if (source === featured.id && byId.has(target)) relatedIds.add(target);
    if (target === featured.id && byId.has(source)) relatedIds.add(source);
  });

  const related = [...relatedIds]
    .map((id) => byId.get(id))
    .filter(asMemory)
    .sort((a, b) => scoreOf(b) - scoreOf(a))
    .slice(0, 3);

  const fallback = related.length >= 2
    ? related
    : memories
        .filter((memory) => memory.id !== featured.id && isCurrent(memory))
        .sort((a, b) => scoreOf(b) - scoreOf(a))
        .slice(0, 3);

  const nodes = [featured, ...fallback].slice(0, 4);
  const tones: BriefingStep['tone'][] = ['brass', 'copper', 'sage', 'copper'];
  return {
    isEvolution: false,
    steps: nodes.map((node, index) => ({
      node,
      label: index === 0 ? 'Current decision' : TYPE_LABELS[node.properties?.memory_type] || 'Related memory',
      tone: tones[index],
    })),
  };
}

function countLinks(memoryId: string, edges: GraphEdge[]): number {
  return edges.reduce((count, edge) => {
    const { source, target } = edgeEndpoints(edge);
    return count + (source === memoryId || target === memoryId ? 1 : 0);
  }, 0);
}

function supportingMemories(memories: MemoryNode[], featuredId: string): MemoryNode[] {
  const preferredTypes = ['directive', 'specification', 'decision'];
  const selected: MemoryNode[] = [];
  preferredTypes.forEach((type) => {
    const match = memories
      .filter((memory) =>
        memory.id !== featuredId
        && memory.properties?.memory_type === type
        && isCurrent(memory),
      )
      .sort((a, b) => scoreOf(b) - scoreOf(a))[0];
    if (match) selected.push(match);
  });
  return selected;
}

function MemoryStep({
  step,
  index,
  onInspect,
}: {
  step: BriefingStep;
  index: number;
  onInspect: (id: string) => void;
}) {
  const toneClasses = {
    clay: 'border-red-400 text-red-300',
    copper: 'border-cyan-500 text-cyan-400',
    brass: 'border-amber-300 text-amber-300',
    sage: 'border-emerald-400 text-emerald-300',
  };

  return (
    <button
      type="button"
      onClick={() => onInspect(step.node.id)}
      className={`group min-w-0 text-left bg-slate-900/80 border-t-2 border-b border-b-slate-800 px-4 py-4 transition-colors hover:bg-slate-800/70 ${toneClasses[step.tone]}`}
    >
      <div className="flex justify-between gap-3 text-[9px] elefante-mono uppercase tracking-[0.12em]">
        <span>{String(index + 1).padStart(2, '0')} · {step.label}</span>
        <span>{scoreOf(step.node)}</span>
      </div>
      <h3 className="min-h-[44px] mt-3 text-[15px] leading-snug font-semibold text-slate-100 group-hover:text-white">
        {step.node.name}
      </h3>
      <p className="mt-2 text-[11px] leading-relaxed text-slate-600 max-h-[49px] overflow-hidden">
        {step.node.description}
      </p>
    </button>
  );
}

export function OverviewTab() {
  const snapshot = useDashboardStore((state) => state.snapshot);
  const getMemoryNodes = useDashboardStore((state) => state.getMemoryNodes);
  const memories = getMemoryNodes();
  const setInspectedMemoryId = useDashboardStore((state) => state.setInspectedMemoryId);
  const setActiveTab = useDashboardStore((state) => state.setActiveTab);
  const health = useHealthScore();
  const inspectMemory = (id: string) => {
    setInspectedMemoryId(id);
    setActiveTab('memories');
  };

  const featured = useMemo(() => chooseFeatured(memories), [memories]);
  const briefing = useMemo(
    () => featured && snapshot
      ? deriveBriefingSteps(featured, memories, snapshot.edges)
      : { steps: [], isEvolution: false },
    [featured, memories, snapshot],
  );
  const carry = useMemo(
    () => featured ? supportingMemories(memories, featured.id) : [],
    [featured, memories],
  );

  if (!snapshot || !featured) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="max-w-lg border-t border-cyan-500/60 pt-5">
          <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.18em]">Continuity briefing</div>
          <h2 className="mt-3 text-2xl font-medium text-slate-100">No durable memory is available yet.</h2>
          <p className="mt-3 text-sm leading-relaxed text-slate-500">
            Add a decision, preference, constraint, or insight through an Elefante-connected agent. The briefing will show what deserves to shape the next answer.
          </p>
        </div>
      </div>
    );
  }

  const status = isCurrent(featured) ? 'Current' : String(featured.properties?.status || 'Review');
  const evidence = featured.properties?.evidence
    || featured.properties?.source
    || 'redacted snapshot';
  const reviewCount = memories.filter((memory) => {
    const healthStatus = String(memory.properties?.health_status || '').toLowerCase();
    if (healthStatus) return healthStatus !== 'healthy';
    const memoryStatus = String(memory.properties?.status || '').toLowerCase();
    return memory.properties?.deprecated
      || memory.properties?.archived
      || ['contradictory', 'redundant', 'superseded'].includes(memoryStatus);
  }).length;
  const sourceLabel = evidence === 'sqlite' ? 'Configured SQLite vector store' : String(evidence);

  return (
    <div className="h-full overflow-auto px-5 py-5 md:px-8 md:py-6">
      <div className="max-w-[1540px] mx-auto min-h-full flex flex-col gap-5">
        <section className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
          <div>
            <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.2em]">
              Continuity briefing / 01
            </div>
            <h1 className="mt-2 text-[clamp(2rem,3.2vw,3.35rem)] leading-[1.02] font-medium tracking-[-0.045em] text-slate-100">
              The decisions shaping<br className="hidden sm:block" /> your next answer.
            </h1>
          </div>
          <p className="max-w-[430px] text-sm leading-relaxed text-slate-500 lg:text-right">
            Elefante shows what changed, why the current truth won, and which guard keeps compatible agents aligned.
          </p>
        </section>

        <section className="elefante-panel grid grid-cols-1 xl:grid-cols-[minmax(0,1.95fr)_minmax(320px,0.72fr)]">
          <article className="min-w-0 px-5 py-5 md:px-7 md:py-6 xl:border-r elefante-hairline">
            <div className="flex items-start justify-between gap-6">
              <div className="min-w-0">
                <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.14em]">
                  {briefing.isEvolution ? 'Featured decision thread' : 'Current memory briefing'}
                </div>
                <h2 className="mt-3 text-2xl md:text-[32px] leading-tight font-medium tracking-[-0.035em] text-slate-100">
                  {featured.name}
                </h2>
                <p className="max-w-4xl mt-2 text-sm leading-relaxed text-slate-500">
                  {featured.description}
                </p>
              </div>
              <div className="flex-none text-right">
                <strong className="block text-3xl text-slate-100 elefante-mono tracking-[-0.06em]">
                  {scoreOf(featured)}
                </strong>
                <span className="text-[8px] text-slate-600 elefante-mono uppercase tracking-[0.13em]">
                  live memory score
                </span>
              </div>
            </div>

            <div className="relative grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mt-8 xl:mt-24">
              {briefing.steps.map((step, index) => (
                <MemoryStep
                  key={step.node.id}
                  step={step}
                  index={index}
                  onInspect={inspectMemory}
                />
              ))}
            </div>
          </article>

          <aside className="px-5 py-5 md:px-6 md:py-6 bg-slate-950/55">
            <h3 className="text-[10px] text-slate-500 elefante-mono uppercase tracking-[0.16em]">
              Why this memory endures
            </h3>
            <div className="grid grid-cols-2 mt-5 border-t border-l elefante-hairline">
              {[
                [TYPE_LABELS[featured.properties?.memory_type] || featured.properties?.memory_type || 'Memory', 'durable memory type'],
                [`${accessCountOf(featured)}×`, 'retrieved by agents'],
                [countLinks(featured.id, snapshot.edges), 'knowledge links'],
                [status, 'memory state'],
              ].map(([value, label]) => (
                <div key={label} className="min-h-[82px] p-3 border-r border-b elefante-hairline">
                  <strong className="block text-xl font-medium text-slate-100">{value}</strong>
                  <span className="block mt-2 text-[8px] leading-relaxed text-slate-600 elefante-mono uppercase tracking-[0.09em]">
                    {label}
                  </span>
                </div>
              ))}
            </div>

            <div className="mt-5 pt-4 border-t elefante-hairline">
              <span className="block text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.1em]">Grounded in</span>
              <strong className="block mt-2 text-xs leading-relaxed font-normal text-slate-400">{sourceLabel}</strong>
            </div>

            <p className="mt-5 pl-4 py-1 border-l-2 border-cyan-500 text-[13px] leading-relaxed text-slate-200">
              This briefing preserves the decision and the evidence that made it current.
            </p>
          </aside>
        </section>

        <section className="grid grid-cols-1 xl:grid-cols-[1.65fr_1fr] gap-5 pb-2">
          <div className="border-t elefante-hairline pt-4">
            <h3 className="text-[9px] text-slate-500 elefante-mono uppercase tracking-[0.16em]">
              What compatible agents carry forward
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 md:gap-8 mt-4">
              {carry.map((memory) => (
                <button
                  key={memory.id}
                  type="button"
                  onClick={() => inspectMemory(memory.id)}
                  className="min-w-0 text-left group"
                >
                  <span className="text-[9px] text-cyan-400 elefante-mono uppercase tracking-[0.11em]">
                    {TYPE_LABELS[memory.properties?.memory_type] || memory.properties?.memory_type}
                  </span>
                  <strong className="block mt-1.5 text-sm font-medium text-slate-200 group-hover:text-white">
                    {memory.name}
                  </strong>
                  <span className="block mt-1 text-[11px] leading-relaxed text-slate-600 max-h-[32px] overflow-hidden">
                    {memory.description}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="border-t elefante-hairline pt-4">
            <h3 className="text-[9px] text-slate-500 elefante-mono uppercase tracking-[0.16em]">
              Knowledge pulse
            </h3>
            <div className="mt-4 flex items-baseline justify-between border-b elefante-hairline pb-3">
              <span className="text-[8px] text-slate-600 elefante-mono uppercase tracking-[0.1em]">Local health score</span>
              <strong className="text-2xl text-slate-100 elefante-mono tracking-[-0.06em]">{health.overall}%</strong>
            </div>
            <div className="grid grid-cols-4 mt-4">
              {[
                [health.totalMemories, 'memories'],
                [`${health.usage}%`, 'used'],
                [`${health.connectivity}%`, 'connected'],
                [String(reviewCount).padStart(2, '0'), 'need review'],
              ].map(([value, label], index) => (
                <div key={label} className={`px-3 ${index === 0 ? 'pl-0' : 'border-l elefante-hairline'}`}>
                  <strong className="block text-2xl text-slate-100 elefante-mono tracking-[-0.06em]">{value}</strong>
                  <span className="text-[8px] text-slate-600 elefante-mono uppercase tracking-[0.08em]">{label}</span>
                </div>
              ))}
            </div>
            <p className="mt-4 text-[11px] leading-relaxed text-slate-500">
              {health.neverRetrievedCount} {health.neverRetrievedCount === 1 ? 'memory has' : 'memories have'} no recorded retrievals; the most-used memory has {health.maxAccessCount} recorded uses.
            </p>
            <p className="mt-4 text-[11px] leading-relaxed text-slate-500">
              Snapshot metrics describe this local memory system. They are not performance or customer claims.
            </p>
          </div>
          <SessionIntelligencePanel />
        </section>
      </div>
    </div>
  );
}
