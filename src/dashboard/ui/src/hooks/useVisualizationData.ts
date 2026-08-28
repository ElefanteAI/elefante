import { useMemo } from 'react';
import { useDashboardStore } from '@/store';
import { edgeEndpoints, type MemoryNode } from '@/types';

// ── Treemap ──────────────────────────────────────────────
export interface TreemapDatum {
  id: string;
  value: number;
}

export function useTreemapData(): TreemapDatum[] {
  const getMemoryNodes = useDashboardStore((s) => s.getMemoryNodes);
  const memories = getMemoryNodes();
  return useMemo(() => {
    const counts = new Map<string, number>();
    memories.forEach((m) => {
      const topic = m.properties?.topic || 'general';
      counts.set(topic, (counts.get(topic) || 0) + 1);
    });
    return Array.from(counts.entries())
      .map(([id, value]) => ({ id, value }))
      .sort((a, b) => b.value - a.value);
  }, [memories]);
}

// ── Calendar Heatmap ─────────────────────────────────────
export interface CalendarDatum {
  day: string;   // YYYY-MM-DD
  value: number;
}

export function useCalendarData(): CalendarDatum[] {
  const getMemoryNodes = useDashboardStore((s) => s.getMemoryNodes);
  const memories = getMemoryNodes();
  return useMemo(() => {
    const counts = new Map<string, number>();
    memories.forEach((m) => {
      const d = m.created_at?.slice(0, 10); // "YYYY-MM-DD"
      if (d) counts.set(d, (counts.get(d) || 0) + 1);
    });
    return Array.from(counts.entries())
      .map(([day, value]) => ({ day, value }))
      .sort((a, b) => a.day.localeCompare(b.day));
  }, [memories]);
}

// ── Health Score ──────────────────────────────────────────
export interface HealthScore {
  overall: number;           // 0-100
  freshness: number;         // 0-100
  coverage: number;          // 0-100
  connectivity: number;      // 0-100
  usage: number;             // 0-100
  staleCount: number;
  freshCount: number;
  atRiskCount: number;
  orphanCount: number;
  connectedCount: number;
  generalCount: number;
  topicCount: number;
  totalMemories: number;
  totalEdges: number;
  typeBreakdown: Record<string, number>;
  // Usage data
  neverRetrievedCount: number;
  retrievedCount: number;
  avgAccessCount: number;
  maxAccessCount: number;
}

/**
 * Health Score Formula (v2.0.0)
 * 
 * Weights based on user value:
 * - Freshness (30%): Stale knowledge is dangerous
 * - Coverage (30%): Single-topic knowledge is brittle
 * - Usage (20%): Unused memories are dead weight
 * - Connectivity (20%): Orphans miss relationships
 */
export function useHealthScore(): HealthScore {
  const snapshot = useDashboardStore((s) => s.snapshot);
  return useMemo(() => {
    const empty: HealthScore = { 
      overall: 0, freshness: 0, coverage: 0, connectivity: 0, usage: 0,
      staleCount: 0, freshCount: 0, orphanCount: 0, connectedCount: 0,
      atRiskCount: 0,
      generalCount: 0, topicCount: 0, totalMemories: 0, totalEdges: 0,
      typeBreakdown: {},
      neverRetrievedCount: 0, retrievedCount: 0, avgAccessCount: 0, maxAccessCount: 0,
    };
    if (!snapshot) return empty;

    const memories = snapshot.nodes.filter((n): n is MemoryNode => n.type === 'memory');
    const total = memories.length;
    if (total === 0) return empty;

    // 1. Freshness (30%): How recently were memories created/accessed?
    // Note: created_at is inside properties, not at node level
    const now = Date.now();
    const NINETY_DAYS = 90 * 24 * 60 * 60 * 1000;
    let freshSum = 0;
    let staleCount = 0;
    let validDates = 0;
    memories.forEach((m) => {
      // created_at is in properties, not at node level
      const dateStr = m.properties?.created_at || m.created_at;
      if (!dateStr) return;
      const created = new Date(dateStr).getTime();
      // Skip invalid dates (NaN)
      if (isNaN(created)) return;
      validDates++;
      const age = now - created;
      const fresh = Math.max(0, 1 - age / NINETY_DAYS);
      freshSum += fresh;
      if (age > NINETY_DAYS) staleCount++;
    });
    // Use validDates for average, fall back to 0 if no valid dates
    const freshness = validDates > 0 ? Math.round((freshSum / validDates) * 100) : 0;
    const healthSummary = snapshot.stats?.health;
    const hasCanonicalHealth = memories.some((m) => Boolean(m.properties?.health_status));
    const canonicalStaleCount = memories.filter((m) => m.properties?.health_status === 'stale').length;
    const canonicalAtRiskCount = memories.filter((m) => m.properties?.health_status === 'at_risk').length;
    const canonicalOrphanCount = memories.filter((m) => m.properties?.health_status === 'orphan').length;

    // 2. Coverage (30%): Are memories spread across multiple topics (not all "general")?
    const topics = new Map<string, number>();
    memories.forEach((m) => {
      const t = m.properties?.topic || 'general';
      topics.set(t, (topics.get(t) || 0) + 1);
    });
    const nonGeneralCount = total - (topics.get('general') || 0);
    const coverage = Math.round((nonGeneralCount / total) * 100);

    // 3. Connectivity (20%): Do memories have edges?
    const memoryIds = new Set(memories.map((m) => m.id));
    const connectedIds = new Set<string>();
    snapshot.edges.forEach((e) => {
      const { source, target } = edgeEndpoints(e);
      if (memoryIds.has(source)) connectedIds.add(source);
      if (memoryIds.has(target)) connectedIds.add(target);
    });
    const connectivity = Math.round((connectedIds.size / total) * 100);
    const orphanCount = total - connectedIds.size;

    // 4. Type breakdown
    const typeBreakdown: Record<string, number> = {};
    memories.forEach((m) => {
      const t = m.properties?.memory_type || 'unknown';
      typeBreakdown[t] = (typeBreakdown[t] || 0) + 1;
    });

    // 5. Usage (20%): Are memories actually being retrieved by agents?
    let accessSum = 0;
    let maxAccess = 0;
    let computedNeverRetrievedCount = 0;
    memories.forEach((m) => {
      const ac = Number(m.properties?.access_count) || 0;
      accessSum += ac;
      if (ac > maxAccess) maxAccess = ac;
      if (ac === 0) computedNeverRetrievedCount++;
    });
    const usageSummary = snapshot.stats?.usage;
    const hasUsageSummary = Boolean(
      usageSummary &&
      typeof usageSummary.retrieved_memories === 'number' &&
      typeof usageSummary.never_retrieved === 'number'
    );
    const neverRetrievedCount = hasUsageSummary
      ? Math.max(0, Math.min(total, usageSummary!.never_retrieved))
      : computedNeverRetrievedCount;
    const retrievedCount = hasUsageSummary
      ? Math.max(0, Math.min(total, usageSummary!.retrieved_memories))
      : total - neverRetrievedCount;
    const avgAccessCount = hasUsageSummary && typeof usageSummary!.average_access_count === 'number'
      ? usageSummary!.average_access_count
      : total > 0 ? accessSum / total : 0;
    const usageRate = hasUsageSummary && typeof usageSummary!.retrieval_rate === 'number'
      ? usageSummary!.retrieval_rate
      : Math.round((retrievedCount / total) * 100);

    // Weighted overall (v2.0.0: 30/30/20/20)
    const computedOverall = Math.round(freshness * 0.3 + coverage * 0.3 + usageRate * 0.2 + connectivity * 0.2);
    const generalCount = topics.get('general') || 0;

    return { 
      overall: typeof healthSummary?.score === 'number' ? healthSummary.score : computedOverall,
      freshness: typeof healthSummary?.freshness === 'number' ? healthSummary.freshness : freshness,
      coverage: typeof healthSummary?.coverage === 'number' ? healthSummary.coverage : coverage,
      connectivity: typeof healthSummary?.connectivity === 'number' ? healthSummary.connectivity : connectivity,
      usage: typeof healthSummary?.usage === 'number' ? healthSummary.usage : usageRate,
      staleCount: hasCanonicalHealth ? canonicalStaleCount : staleCount,
      freshCount: hasCanonicalHealth ? memories.filter((m) => m.properties?.health_status === 'healthy').length : validDates - staleCount,
      atRiskCount: hasCanonicalHealth ? canonicalAtRiskCount : 0,
      orphanCount: hasCanonicalHealth ? canonicalOrphanCount : orphanCount,
      connectedCount: connectedIds.size,
      generalCount,
      topicCount: topics.size,
      totalMemories: total,
      totalEdges: snapshot.edges.length,
      typeBreakdown,
      neverRetrievedCount,
      retrievedCount,
      avgAccessCount: Math.round(avgAccessCount * 10) / 10,
      maxAccessCount: hasUsageSummary && typeof usageSummary!.max_access_count === 'number'
        ? usageSummary!.max_access_count
        : maxAccess,
    };
  }, [snapshot]);
}

// ── Usage Intelligence ───────────────────────────────────
export interface UsageData {
  neverRetrieved: MemoryNode[];
  mostRetrieved: MemoryNode[];
  avgAccessCount: number;
  retrievalRate: number;
}

export function useUsageData(): UsageData {
  const snapshot = useDashboardStore((s) => s.snapshot);
  return useMemo(() => {
    const empty: UsageData = { neverRetrieved: [], mostRetrieved: [], avgAccessCount: 0, retrievalRate: 0 };
    if (!snapshot) return empty;

    const memories = snapshot.nodes.filter((n): n is MemoryNode => n.type === 'memory');
    if (memories.length === 0) return empty;

    const withAccess = memories.map((m) => ({
      node: m,
      count: Number(m.properties?.access_count) || 0,
    }));

    const neverRetrieved = withAccess.filter((w) => w.count === 0).map((w) => w.node);

    const sorted = [...withAccess].sort((a, b) => b.count - a.count);
    const mostRetrieved = sorted.slice(0, 5).map((w) => w.node);

    const totalAccess = withAccess.reduce((s, w) => s + w.count, 0);
    const usageSummary = snapshot.stats?.usage;
    const avgAccessCount = typeof usageSummary?.average_access_count === 'number'
      ? usageSummary.average_access_count
      : Math.round((totalAccess / memories.length) * 10) / 10;
    const retrievalRate = typeof usageSummary?.retrieval_rate === 'number'
      ? usageSummary.retrieval_rate
      : Math.round(((memories.length - neverRetrieved.length) / memories.length) * 100);

    return { neverRetrieved, mostRetrieved, avgAccessCount, retrievalRate };
  }, [snapshot]);
}
