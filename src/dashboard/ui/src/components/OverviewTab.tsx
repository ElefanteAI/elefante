// Elefante Dashboard v2.5.2 - Overview Tab
// Meaningful metrics that explain memory health for AI agent behavior
import { useHealthScore, useUsageData } from '@/hooks/useVisualizationData';
import type { HealthScore } from '@/hooks/useVisualizationData';
import { useDashboardStore } from '@/store';
import { TopicTreemap } from '@/components/TopicTreemap';
import { ActivityFeed } from '@/components/ActivityFeed';
import { HealthGauge } from '@/components/HealthGauge';

function getHealthDiagnosis(health: HealthScore) {
  const issues: string[] = [];
  const recommendations: string[] = [];
  let status: 'healthy' | 'warning' | 'critical' = 'healthy';

  // Freshness analysis — include actual counts
  if (health.freshness < 20) {
    issues.push(`${health.staleCount} of ${health.totalMemories} memories are over 90 days old`);
    recommendations.push('Archive stale memories or add fresh ones to keep knowledge current');
    status = 'critical';
  } else if (health.freshness < 50) {
    issues.push(`${health.staleCount} memories are aging — freshness at ${health.freshness}%`);
    recommendations.push('Add more recent memories to improve freshness score');
    if (status === 'healthy') status = 'warning';
  }

  // Coverage analysis — the key issue, with real numbers
  if (health.coverage < 15) {
    issues.push(`${health.generalCount} of ${health.totalMemories} memories (${100 - health.coverage}%) are uncategorized "general" topic`);
    recommendations.push('Assign specific topics (coding, debugging, architecture) when saving memories');
    recommendations.push('Re-tag existing "general" memories with meaningful topics');
    status = 'critical';
  } else if (health.coverage < 40) {
    issues.push(`${health.generalCount} memories still tagged as "general" — search will be noisy`);
    recommendations.push('Add specific topics to memories for better retrieval precision');
    if (status === 'healthy') status = 'warning';
  }

  // Connectivity analysis
  if (health.connectivity < 10) {
    issues.push(`${health.orphanCount} of ${health.totalMemories} memories have zero graph connections`);
    recommendations.push('Link related memories with elefante-GraphConnect to build knowledge connections');
    if (status === 'healthy') status = 'warning';
  }

  // Usage analysis
  if (health.neverRetrievedCount > health.totalMemories * 0.5) {
    issues.push(`${health.neverRetrievedCount} of ${health.totalMemories} memories have never been retrieved by an agent`);
    recommendations.push('Review unused memories — archive or improve their content for better retrieval');
    if (status === 'healthy') status = 'warning';
  } else if (health.neverRetrievedCount > health.totalMemories * 0.3) {
    issues.push(`${health.neverRetrievedCount} memories have never been retrieved`);
    recommendations.push('Consider archiving unused memories to reduce noise');
    if (status === 'healthy') status = 'warning';
  }

  return { issues, recommendations, status };
}

function getAgentImpact(health: HealthScore) {
  const impacts: { text: string; severity: 'critical' | 'warning' }[] = [];

  if (health.coverage < 15) {
    impacts.push({ text: 'Searches return too many irrelevant memories — agent cannot filter by topic', severity: 'critical' });
    impacts.push({ text: 'Agent may repeat past mistakes because relevant learnings are buried in noise', severity: 'critical' });
  } else if (health.coverage < 40) {
    impacts.push({ text: 'Topic filtering is partially effective — some searches will be noisy', severity: 'warning' });
  }

  if (health.freshness < 30) {
    impacts.push({ text: 'Agent relies on outdated knowledge — may suggest obsolete solutions', severity: health.freshness < 15 ? 'critical' : 'warning' });
  }

  if (health.connectivity < 10) {
    impacts.push({ text: 'Cannot traverse related concepts — misses connections between ideas', severity: 'warning' });
  }

  if (health.usage < 50) {
    impacts.push({ text: `${health.neverRetrievedCount} memories are never surfaced — potential dead weight in search`, severity: 'warning' });
  }

  return impacts;
}

// ── Stat Pill ────────────────────────────────────────────
function StatPill({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5 px-3 py-2">
      <span className="text-lg font-semibold text-slate-200 tabular-nums">{value}</span>
      <span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
      {sub && <span className="text-[10px] text-slate-600">{sub}</span>}
    </div>
  );
}

// ── Metric Card ──────────────────────────────────────────
function MetricCard({ label, weight, value, detail, bar }: {
  label: string;
  weight: string;
  value: number;
  detail: string;
  bar: { color: string; hint: string };
}) {
  return (
    <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs uppercase tracking-wider text-slate-400">{label}</div>
        <div className="text-[10px] text-slate-600">{weight}</div>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-semibold text-slate-200 tabular-nums">{value}%</span>
        <span className="text-xs text-slate-500">{detail}</span>
      </div>
      <div className="mt-2.5 h-1.5 bg-slate-700/80 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${bar.color}`}
          style={{ width: `${Math.max(2, value)}%` }}
        />
      </div>
      <div className="mt-1.5 text-[11px] text-slate-500">{bar.hint}</div>
    </div>
  );
}

export function OverviewTab() {
  const health = useHealthScore();
  const usageData = useUsageData();
  const isLoading = useDashboardStore((s) => s.isLoading);
  const getTopics = useDashboardStore((s) => s.getTopics);
  const topics = getTopics();

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-4 gap-4">
          {[1,2,3,4].map(i => (
            <div key={i} className="bg-slate-800/60 rounded-xl p-6 animate-pulse">
              <div className="h-4 bg-slate-700 rounded w-20 mb-2" />
              <div className="h-8 bg-slate-700 rounded w-16" />
            </div>
          ))}
        </div>
        <div className="h-64 bg-slate-800/60 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (health.totalMemories === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-4">🧠</div>
          <h2 className="text-xl font-semibold text-slate-200 mb-2">No memories yet</h2>
          <p className="text-slate-400 text-sm">
            Add your first memory via your IDE or MCP tool.
            Memories will appear here once created.
          </p>
        </div>
      </div>
    );
  }

  const diagnosis = getHealthDiagnosis(health);
  const agentImpact = getAgentImpact(health);
  const typeEntries = Object.entries(health.typeBreakdown).sort((a, b) => b[1] - a[1]);

  return (
    <div className="p-6 overflow-auto h-full">
      <div className="max-w-6xl mx-auto space-y-5">

        {/* ── Row 1: Health Gauge + Diagnosis ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">

          {/* Health Gauge */}
          <div className={`lg:col-span-4 bg-slate-800/60 border rounded-xl p-5 flex flex-col items-center justify-center gap-3 ${
            diagnosis.status === 'healthy' ? 'border-emerald-500/20' :
            diagnosis.status === 'warning' ? 'border-amber-500/20' : 'border-red-500/20'
          }`}>
            <div className="text-xs uppercase tracking-wider text-slate-500">Memory Health</div>
            <HealthGauge score={health.overall} status={diagnosis.status} />
            {/* Score breakdown */}
            <div className="w-full border-t border-slate-700/40 pt-3 mt-1">
              <div className="text-[10px] uppercase tracking-wider text-slate-600 mb-2 text-center">Score Breakdown</div>
              <div className="space-y-1.5">
                {[
                  { label: 'Freshness', val: health.freshness, w: 30 },
                  { label: 'Coverage', val: health.coverage, w: 30 },
                  { label: 'Usage', val: health.usage, w: 20 },
                  { label: 'Connectivity', val: health.connectivity, w: 20 },
                ].map((m) => (
                  <div key={m.label} className="flex items-center gap-2 text-[11px]">
                    <span className="w-20 text-slate-500">{m.label}</span>
                    <div className="flex-1 h-1 bg-slate-700/60 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          m.val >= 50 ? 'bg-emerald-500/70' : m.val >= 25 ? 'bg-amber-500/70' : 'bg-red-500/70'
                        }`}
                        style={{ width: `${Math.max(2, m.val)}%` }}
                      />
                    </div>
                    <span className="w-14 text-right text-slate-500 tabular-nums">
                      {m.val}% × .{m.w}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Diagnosis + Agent Impact */}
          <div className="lg:col-span-8 flex flex-col gap-4">
            {/* Diagnosis Panel */}
            <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 flex-1">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">
                {diagnosis.status === 'critical' ? '⚠️ Issues Detected' : 
                 diagnosis.status === 'warning' ? '⚡ Areas for Improvement' : '✅ Memory System Status'}
              </h3>
              {diagnosis.issues.length > 0 ? (
                <ul className="space-y-1.5 mb-3">
                  {diagnosis.issues.map((issue, i) => (
                    <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                      <span className={`mt-0.5 ${diagnosis.status === 'critical' ? 'text-red-400' : 'text-amber-400'}`}>•</span>
                      {issue}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-emerald-400/90 mb-3">All memory health metrics are within healthy ranges.</p>
              )}
              
              {diagnosis.recommendations.length > 0 && (
                <div className="border-t border-slate-700/40 pt-3">
                  <h4 className="text-[10px] uppercase tracking-wider text-slate-600 mb-1.5">Recommended Actions</h4>
                  <ul className="space-y-1">
                    {diagnosis.recommendations.map((rec, i) => (
                      <li key={i} className="text-xs text-cyan-400/90 flex items-start gap-2">
                        <span className="text-cyan-600 mt-0.5">→</span>
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Agent Impact — only when issues exist */}
            {agentImpact.length > 0 && (
              <div className="bg-slate-900/40 border border-slate-700/30 rounded-xl p-4">
                <h3 className="text-xs font-semibold text-slate-400 mb-2.5 uppercase tracking-wider">Impact on Agent Behavior</h3>
                <ul className="space-y-1.5">
                  {agentImpact.map((impact, i) => (
                    <li key={i} className="text-sm text-slate-400 flex items-start gap-2">
                      <span className={impact.severity === 'critical' ? 'text-red-400' : 'text-amber-400'}>•</span>
                      {impact.text}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        {/* ── Row 2: Quick Stats Bar ── */}
        <div className="bg-slate-800/40 border border-slate-700/40 rounded-xl flex items-center justify-around divide-x divide-slate-700/30 overflow-x-auto">
          <StatPill label="Memories" value={health.totalMemories} />
          <StatPill label="Topics" value={health.topicCount} />
          <StatPill label="Edges" value={health.totalEdges} />
          <StatPill label="Fresh" value={health.freshCount} sub={`of ${health.totalMemories}`} />
          <StatPill label="Retrieved" value={health.retrievedCount} sub={`of ${health.totalMemories}`} />
          <StatPill label="Connected" value={health.connectedCount} sub={`of ${health.totalMemories}`} />
          {typeEntries.length > 0 && typeEntries.slice(0, 3).map(([type, count]) => (
            <StatPill key={type} label={type} value={count} />
          ))}
        </div>

        {/* ── Row 3: Metric Cards ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Freshness"
            weight="30% weight"
            value={health.freshness}
            detail={`${health.freshCount} fresh · ${health.staleCount} stale`}
            bar={{
              color: health.freshness >= 50 ? 'bg-emerald-400' : health.freshness >= 25 ? 'bg-amber-400' : 'bg-red-400',
              hint: health.freshness >= 50 ? 'Recent memories available for context' :
                    health.freshness >= 25 ? 'Mix of old and new — consider archiving stale' : 'Most memories are over 90 days old',
            }}
          />
          <MetricCard
            label="Topic Coverage"
            weight="30% weight"
            value={health.coverage}
            detail={`${health.generalCount} general · ${health.topicCount} topics`}
            bar={{
              color: health.coverage >= 40 ? 'bg-emerald-400' : health.coverage >= 15 ? 'bg-amber-400' : 'bg-red-400',
              hint: health.coverage >= 40 ? 'Well-categorized for precise retrieval' :
                    health.coverage >= 15 ? 'Many memories lack specific topics' : `${health.generalCount} uncategorized — agent cannot filter`,
            }}
          />
          <MetricCard
            label="Usage"
            weight="20% weight"
            value={health.usage}
            detail={`${health.retrievedCount} used · ${health.neverRetrievedCount} unused`}
            bar={{
              color: health.usage >= 60 ? 'bg-emerald-400' : health.usage >= 30 ? 'bg-amber-400' : 'bg-red-400',
              hint: health.usage >= 60 ? 'Most memories are actively retrieved by agents' :
                    health.usage >= 30 ? 'Many memories never retrieved — potential dead weight' : 'Most memories are unused by agents',
            }}
          />
          <MetricCard
            label="Connectivity"
            weight="20% weight"
            value={health.connectivity}
            detail={`${health.connectedCount} linked · ${health.orphanCount} orphans`}
            bar={{
              color: health.connectivity >= 30 ? 'bg-emerald-400' : health.connectivity >= 10 ? 'bg-amber-400' : 'bg-red-400',
              hint: health.connectivity >= 30 ? 'Rich knowledge graph for traversal' :
                    health.connectivity >= 10 ? 'Some connections — room to grow' : 'Memories are isolated nodes',
            }}
          />
        </div>

        {/* ── Row 4: Usage Intelligence ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Most Retrieved */}
          <div className="lg:col-span-6 bg-slate-800/60 border border-slate-700/60 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-700/60 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-300">Most Retrieved</h3>
              <span className="text-xs text-slate-500">by agents</span>
            </div>
            <div className="divide-y divide-slate-700/30">
              {usageData.mostRetrieved.map((m) => (
                <div key={m.id} className="px-4 py-2.5 flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-lg font-semibold text-emerald-400 tabular-nums w-8 text-right shrink-0">
                      {m.properties?.access_count ?? 0}
                    </span>
                    <span className="text-sm text-slate-300 truncate">
                      {m.properties?.title || m.properties?.content?.slice(0, 50) || 'Untitled'}
                    </span>
                  </div>
                  <span className="px-2 py-0.5 bg-slate-700/50 text-slate-400 rounded text-[10px] shrink-0 ml-2">
                    {m.properties?.topic || 'general'}
                  </span>
                </div>
              ))}
              {usageData.mostRetrieved.length === 0 && (
                <div className="px-4 py-6 text-center text-sm text-slate-500">No usage data yet</div>
              )}
            </div>
          </div>

          {/* Never Retrieved */}
          <div className="lg:col-span-6 bg-slate-800/60 border border-slate-700/60 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-700/60 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-300">Never Retrieved</h3>
              <span className="text-xs text-slate-500">
                {usageData.neverRetrieved.length} memories
              </span>
            </div>
            <div className="divide-y divide-slate-700/30">
              {usageData.neverRetrieved.slice(0, 5).map((m) => (
                <div key={m.id} className="px-4 py-2.5 flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-lg font-semibold text-red-400/70 tabular-nums w-8 text-right shrink-0">0</span>
                    <span className="text-sm text-slate-400 truncate">
                      {m.properties?.title || m.properties?.content?.slice(0, 50) || 'Untitled'}
                    </span>
                  </div>
                  <span className="px-2 py-0.5 bg-slate-700/50 text-slate-500 rounded text-[10px] shrink-0 ml-2">
                    {m.properties?.topic || 'general'}
                  </span>
                </div>
              ))}
              {usageData.neverRetrieved.length === 0 && (
                <div className="px-4 py-6 text-center text-sm text-emerald-400/70">All memories have been retrieved at least once</div>
              )}
              {usageData.neverRetrieved.length > 5 && (
                <div className="px-4 py-2 text-center text-xs text-slate-600">
                  +{usageData.neverRetrieved.length - 5} more unused memories
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Row 5: Treemap + Activity Feed ── */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <div className="lg:col-span-3 bg-slate-800/60 border border-slate-700/60 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-700/60 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-300">
                Topic Distribution
              </h3>
              <span className="text-xs text-slate-500">
                {health.totalMemories} memories · {topics.length} topics
              </span>
            </div>
            <div className="h-80">
              <TopicTreemap />
            </div>
          </div>

          <div className="lg:col-span-2 bg-slate-800/60 border border-slate-700/60 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-700/60">
              <h3 className="text-sm font-semibold text-slate-300">Recent Activity</h3>
            </div>
            <div className="h-80 overflow-y-auto">
              <ActivityFeed />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
