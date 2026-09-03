import type { SessionIntelligenceCaptureHealth } from '@/types';
import { useDashboardStore } from '@/store';

function compactTokens(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return 'UNKNOWN';
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

function countLabel(value: unknown): string {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) return 'UNKNOWN';
  return String(value);
}

function textLabel(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'UNKNOWN';
  return String(value);
}

function timestampLabel(value: string | null | undefined): string {
  if (typeof value !== 'string' || !value.trim()) return 'UNKNOWN';
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? 'UNKNOWN' : timestamp.toISOString();
}

function scopeLabel(scope: { session_id?: string | null } | null | undefined): string {
  if (!scope || scope.session_id === undefined) return 'UNKNOWN';
  if (scope.session_id === null) return 'All retained sessions';
  return typeof scope.session_id === 'string' && scope.session_id.trim()
    ? 'Selected session'
    : 'UNKNOWN';
}

function CaptureHealth({ capture, details = false }: { capture?: SessionIntelligenceCaptureHealth; details?: boolean }) {
  if (!capture) return null;
  const pendingCount = Number.isFinite(capture.pending_count) && capture.pending_count > 0
    ? capture.pending_count
    : 0;
  const coverage = typeof capture.coverage === 'string' && capture.coverage.trim()
    ? capture.coverage
    : 'UNKNOWN';

  if (details) {
    return <p>Capture health: {capture.state === 'permission_required' ? 'last write lacked permission' : capture.state} · coverage {coverage} · since {timestampLabel(capture.since)}</p>;
  }

  return (
    <div className="space-y-2 text-sm leading-relaxed text-slate-400">
      {capture.state === 'partial' && (
        <p role="alert" className="text-amber-200">
          Usage capture or snapshot refresh failed; displayed totals may be incomplete. Failed: {capture.failed_count} · Dropped: {capture.dropped_count}.
        </p>
      )}
      {capture.state === 'permission_required' && (
        <p role="status" className="text-amber-200">
          A previous usage write lacked permission. Each new call rechecks consent; displayed totals may be incomplete.
        </p>
      )}
      {pendingCount > 0 && (
        <p role="status" className="text-cyan-200">
          Pending MCP usage: {pendingCount} event{pendingCount === 1 ? '' : 's'} awaiting persistence; displayed totals are not current until persisted.
        </p>
      )}
    </div>
  );
}

function outcomeLabel(evidence: {
  accepted: boolean | null | undefined;
  accepted_outcome_status: string;
  evidence_class: string;
}): string {
  if (evidence.evidence_class !== 'causally_evaluated' || evidence.accepted_outcome_status !== 'known') {
    return 'UNKNOWN';
  }
  if (evidence.accepted === true) return 'Accepted';
  if (evidence.accepted === false) return 'Rejected';
  return 'UNKNOWN';
}

export function SessionIntelligencePanel() {
  const data = useDashboardStore((state) => state.sessionIntelligence);
  const error = useDashboardStore((state) => state.sessionIntelligenceError);
  if (error) {
    return (
      <section className="border-t elefante-hairline pt-4 xl:col-span-2">
        <h3 className="text-sm font-medium text-slate-200">
          Session Intelligence · View only
        </h3>
        <p role="alert" className="mt-2 text-sm text-amber-200">
          Usage report unavailable. Try Reload snapshot.
        </p>
        <details className="mt-3 text-sm text-slate-400">
          <summary className="cursor-pointer">Error details</summary>
          <p className="mt-2">Session Intelligence snapshot unavailable: {error}</p>
        </details>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="border-t elefante-hairline pt-4 xl:col-span-2">
        <h3 className="text-sm font-medium text-slate-200">
          Session Intelligence · View only
        </h3>
        <p className="mt-2 text-sm text-slate-300">No usage report loaded. Try Reload snapshot.</p>
      </section>
    );
  }

  if (!data.consent.enabled) {
    return (
      <section className="border-t elefante-hairline pt-4 xl:col-span-2">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
          <div>
            <h3 className="text-sm font-medium text-slate-200">
              Session Intelligence · View only
            </h3>
            <p className="mt-2 text-sm text-slate-300">Collection is off.</p>
          </div>
          <p className="max-w-lg text-sm leading-relaxed text-slate-400 md:text-right">
            Enable local usage permission outside this dashboard.
          </p>
        </div>
        <CaptureHealth capture={data.capture} />
      </section>
    );
  }

  if (!data.signal_card) {
    return (
      <section className="border-t elefante-hairline pt-4 xl:col-span-2">
        <h3 className="text-sm font-medium text-slate-200">
          Session Intelligence · View only
        </h3>
        <p className="mt-2 text-sm text-slate-300">
          No usage report yet.
        </p>
        <CaptureHealth capture={data.capture} />
      </section>
    );
  }

  const card = data.signal_card;
  const actual = card.usage.actual;
  const estimated = card.usage.estimated;
  const costKnown = card.cost.status === 'known';
  const enterpriseReport = data.enterprise_report;
  const hypotheses = enterpriseReport ? enterpriseReport.hypotheses.length : null;
  const providerActual = actual.evidence_class === 'provider_actual'
    && typeof actual.event_count === 'number'
    && actual.event_count > 0;
  const actualCount = countLabel(actual.event_count);
  const pendingCount = data.capture?.pending_count ?? 0;
  const incompleteCapture = data.capture?.state === 'partial'
    || data.capture?.state === 'permission_required'
    || pendingCount > 0;
  const clientLabel = card.scope.client_name === null
    ? 'All observed clients'
    : typeof card.scope.client_name === 'string' && card.scope.client_name.trim()
      ? card.scope.client_name
      : 'UNKNOWN';
  const cost = costKnown ? `${card.cost.currency || ''} ${card.cost.amount}`.trim() : 'UNKNOWN';
  const outcome = outcomeLabel(card.accepted_outcome_evidence);
  const captureLabel = data.capture?.state === 'observing'
    ? 'Recording tool activity'
    : data.capture?.state === 'partial'
      ? 'Incomplete report'
      : data.capture?.state === 'permission_required'
        ? 'Last write lacked permission'
        : data.capture?.state === 'idle'
          ? 'Waiting for activity'
          : 'Saved report';
  const values: Array<[string, string, string]> = [
    [countLabel(card.usage.event_count), 'Recorded events', `${countLabel(estimated.event_count)} estimated · ${actualCount} provider-reported`],
    [costKnown ? cost : 'Unavailable', 'Usage cost', costKnown ? 'From recorded usage and rates' : providerActual ? 'Incomplete usage or rates' : 'Needs provider usage and rates'],
    [outcome === 'UNKNOWN' ? 'Not verified' : outcome, 'Task result', outcome === 'UNKNOWN' ? 'No verified comparison' : 'From a comparable evaluation'],
  ];

  return (
    <section aria-label="Session Intelligence report" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-medium text-slate-100">{captureLabel}</h3>
        <span className="text-xs text-slate-400">View only · Local data</span>
      </div>
      <CaptureHealth capture={data.capture} />
      <p className="text-xs text-slate-400">{scopeLabel(card.scope)} · {clientLabel}</p>
      <div aria-label="Usage summary" className="grid grid-cols-1 sm:grid-cols-3 border-t border-l elefante-hairline">
        {values.map(([value, label, hint]) => (
          <div key={label} className="min-w-0 p-4 border-r border-b elefante-hairline">
            <strong className="block text-xl font-semibold text-slate-100">{value}</strong>
            <span className="block mt-1 text-sm font-medium text-slate-200">{label}</span>
            <p className="mt-2 text-xs leading-relaxed text-slate-400">{hint}</p>
          </div>
        ))}
      </div>
      <details className="border-t elefante-hairline pt-3 text-sm text-slate-300">
        <summary className="cursor-pointer py-1 font-medium text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400">
          Usage details
        </summary>
        <div className="mt-4 space-y-3 break-words text-xs leading-relaxed text-slate-400">
          <div aria-label="Observation counts">
            Observation counts: {countLabel(card.usage.event_count)} combined · {actualCount} actual · {countLabel(estimated.event_count)} estimated
          </div>
          <div className="grid grid-cols-2 gap-3">
            {([
              [providerActual ? compactTokens(actual.input_tokens) : 'UNKNOWN', 'actual input tokens'],
              [providerActual ? compactTokens(actual.output_tokens) : 'UNKNOWN', 'actual output tokens'],
            ] as const).map(([value, label]) => (
              <div key={label}>
                <strong className="block text-base text-slate-100">{value}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>
          <div aria-label="Estimated usage" className="space-y-1">
            <p>Estimated input tokens: {compactTokens(estimated.input_tokens)}</p>
            <p>Estimated output tokens: {compactTokens(estimated.output_tokens)}</p>
            <p>Estimated overhead tokens: {compactTokens(estimated.overhead_tokens)}</p>
          </div>
          <p>Verified cost: {cost} · Causal outcome: {outcome}</p>
          <p>{card.hypothesis}</p>
          <div className="space-y-1">
            <p>Scope: {scopeLabel(card.scope)} · Client: {clientLabel}</p>
            <p>Window: {timestampLabel(card.scope.window_start)} → {timestampLabel(card.scope.window_end)}</p>
            <p>Snapshot generated: {timestampLabel(data.generated_at)}</p>
            <CaptureHealth capture={data.capture} details />
          </div>
          <p>{card.unknowns.length
            ? `Unknowns: ${card.unknowns.join(' · ')}`
            : incompleteCapture
              ? 'Displayed totals are incomplete or pending persistence.'
              : 'All displayed cost inputs have complete provenance.'}</p>
          <p>Reload does not add activity. Estimates are not provider billing.</p>
          <p>Prompts and responses are not saved. No employee ranking or sensitive-trait inference.</p>
        </div>
      </details>
      <details className="border-t elefante-hairline pt-3 text-sm text-slate-300">
        <summary className="cursor-pointer py-1 font-medium text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400">
          Suggestions {hypotheses === null ? '· unavailable' : `(${hypotheses})`}
        </summary>
        <div className="mt-4 space-y-3 text-sm leading-relaxed text-slate-400">
          {!enterpriseReport ? (
            <p>No suggestion report available.</p>
          ) : enterpriseReport.hypotheses.length === 0 ? (
            <p>No suggestions in this report.</p>
          ) : (
            <ul className="space-y-4">
              {enterpriseReport.hypotheses.map((hypothesis, index) => (
                <li key={hypothesis.hypothesis_id || `${hypothesis.aggregate_key}-${index}`}>
                  <p><span className="text-slate-400">Statement:</span> {hypothesis.statement || 'UNKNOWN'}</p>
                  <p className="mt-1 text-xs">
                    <span className="text-slate-400">Basis:</span>{' '}
                    events {countLabel(hypothesis.basis.event_count)} · provider actual {countLabel(hypothesis.basis.actual_event_count)} · estimated {countLabel(hypothesis.basis.estimated_event_count)} · accepted outcome {textLabel(hypothesis.basis.accepted_outcome)}
                  </p>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs">Suggestions to investigate, not proven improvements or model training.</p>
        </div>
      </details>
    </section>
  );
}
