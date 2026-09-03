import { useDashboardStore } from '@/store';

function compactTokens(value: unknown): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 'UNKNOWN';
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(numeric);
}

function outcomeLabel(value: boolean | null | undefined): string {
  if (value === true) return 'Accepted';
  if (value === false) return 'Rejected';
  return 'UNKNOWN';
}

export function SessionIntelligencePanel() {
  const data = useDashboardStore((state) => state.sessionIntelligence);
  const error = useDashboardStore((state) => state.sessionIntelligenceError);
  if (error) {
    return (
      <section className="border-t elefante-hairline pt-4 xl:col-span-2">
        <h3 className="text-[9px] text-slate-500 elefante-mono uppercase tracking-[0.16em]">
          Session Intelligence · View only
        </h3>
        <p role="alert" className="mt-2 text-xs text-amber-200">
          Session Intelligence snapshot unavailable: {error}
        </p>
      </section>
    );
  }

  if (!data || !data.consent.enabled || !data.signal_card) {
    return (
      <section className="border-t elefante-hairline pt-4 xl:col-span-2">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
          <div>
            <h3 className="text-[9px] text-slate-500 elefante-mono uppercase tracking-[0.16em]">
              Session Intelligence · View only
            </h3>
            <p className="mt-2 text-sm text-slate-300">Off by default.</p>
          </div>
          <p className="max-w-2xl text-[11px] leading-relaxed text-slate-500 md:text-right">
            The dashboard cannot grant consent or ingest usage. Explicit local consent is required before metadata-only provider usage is persisted. Prompts, transcripts, responses, and employee surveillance are outside this surface.
          </p>
        </div>
      </section>
    );
  }

  const card = data.signal_card;
  const actual = card.usage.actual || {};
  const costKnown = card.cost.status === 'known';
  const hypotheses = data.enterprise_report?.hypotheses?.length || 0;
  const values: Array<[string, string]> = [
    [String(card.usage.event_count), 'usage events'],
    [compactTokens(actual.input_tokens), 'actual input tokens'],
    [compactTokens(actual.output_tokens), 'actual output tokens'],
    [costKnown ? `${card.cost.currency || ''} ${card.cost.amount}`.trim() : 'UNKNOWN', 'verified cost'],
    [outcomeLabel(card.accepted_outcome_evidence.accepted), 'causal outcome'],
    [String(hypotheses), 'training hypotheses'],
  ];

  return (
    <section className="border-t elefante-hairline pt-4 xl:col-span-2">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-3">
        <div>
          <h3 className="text-[9px] text-cyan-400 elefante-mono uppercase tracking-[0.16em]">
            Session Intelligence / Signal Card · View only
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">{card.hypothesis}</p>
        </div>
        <span className="text-[8px] text-slate-600 elefante-mono uppercase tracking-[0.1em]">
          provider actual and estimates remain separate
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 mt-4 border-t border-l elefante-hairline">
        {values.map(([value, label]) => (
          <div key={label} className="min-h-[78px] p-3 border-r border-b elefante-hairline">
            <strong className="block text-lg text-slate-100 elefante-mono">{value}</strong>
            <span className="block mt-2 text-[8px] text-slate-600 elefante-mono uppercase tracking-[0.08em]">{label}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-col md:flex-row md:justify-between gap-2 text-[10px] leading-relaxed text-slate-500">
        <span>{card.unknowns.length ? `Unknowns: ${card.unknowns.join(' · ')}` : 'All displayed cost inputs have complete provenance.'}</span>
        <span>Aggregate hypotheses only · no employee ranking · no sensitive-trait inference</span>
      </div>
    </section>
  );
}
