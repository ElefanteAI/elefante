import { FormEvent, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  CircleSlash2,
  Loader2,
  SearchCheck,
} from 'lucide-react';
import { useDashboardStore } from '@/store';
import type { RecallTestResponse } from '@/types';

function formatVerifiedAt(value: string | undefined): string {
  if (!value) return 'Not verified';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Verified';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function shortId(value: string): string {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
}

function statusCopy(result: RecallTestResponse): {
  label: string;
  summary: string;
  tone: string;
  icon: React.ReactNode;
} {
  if (result.recall_status === 'supplied') {
    return {
      label: 'Bundle supplied',
      summary: 'Governed Recall selected a bounded set of memories for this project question.',
      tone: 'border-emerald-400/45 bg-emerald-950/10',
      icon: <CheckCircle2 size={20} className="text-emerald-300" aria-hidden="true" />,
    };
  }
  if (result.recall_status === 'no_match') {
    return {
      label: 'No match · safe abstention',
      summary: 'Recall ran successfully and supplied no unrelated or ineligible memory.',
      tone: 'border-slate-700 bg-slate-900/35',
      icon: <CircleSlash2 size={20} className="text-slate-400" aria-hidden="true" />,
    };
  }
  if (result.recall_status === 'blocked') {
    return {
      label: 'Delivery blocked',
      summary: 'Recall withheld the bundle because the governed result requires conflict review.',
      tone: 'border-amber-300/45 bg-amber-950/10',
      icon: <AlertTriangle size={20} className="text-amber-200" aria-hidden="true" />,
    };
  }
  return {
    label: 'Recall unavailable',
    summary: result.error || 'The project-scoped Recall path could not be verified.',
    tone: 'border-red-400/45 bg-red-950/10',
    icon: <AlertTriangle size={20} className="text-red-300" aria-hidden="true" />,
  };
}

export function RecallTab() {
  const controlEnabled = useDashboardStore((state) => state.controlEnabled);
  const activeProjectId = useDashboardStore((state) => state.activeProjectId);
  const registry = useDashboardStore((state) => state.projectRegistry);
  const testRecall = useDashboardStore((state) => state.testRecall);
  const isRecallTesting = useDashboardStore((state) => state.isRecallTesting);
  const recallTestError = useDashboardStore((state) => state.recallTestError);
  const clearRecallTestError = useDashboardStore((state) => state.clearRecallTestError);
  const getMemoryNodes = useDashboardStore((state) => state.getMemoryNodes);
  const setActiveTab = useDashboardStore((state) => state.setActiveTab);
  const setInspectedMemoryId = useDashboardStore((state) => state.setInspectedMemoryId);
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<RecallTestResponse | null>(null);

  const activeProject = useMemo(
    () => (registry?.projects ?? []).find(
      (project) => project.project_id === activeProjectId
        && project.active
        && project.root_status !== 'missing',
    ) ?? null,
    [activeProjectId, registry],
  );
  const memoriesById = useMemo(
    () => new Map(getMemoryNodes().map((memory) => [memory.id, memory])),
    [getMemoryNodes],
  );
  const selectedIds = result?.selected_memory_ids ?? [];
  const canRun = controlEnabled && Boolean(activeProject) && Boolean(question.trim());

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const response = await testRecall(question.trim());
    setResult(response);
  };

  const inspectMemory = (memoryId: string) => {
    setInspectedMemoryId(memoryId);
    setActiveTab('memories');
  };

  const copy = result ? statusCopy(result) : null;

  if (!controlEnabled) {
    return (
      <div className="h-full overflow-auto px-5 py-5 md:px-8 md:py-7">
        <div className="mx-auto max-w-[920px]">
          <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.18em]">Recall evidence</div>
          <h1 className="mt-2 text-3xl font-medium tracking-[-0.035em] text-slate-100">Prove what memory Elefante would supply.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-400">
            Recall is where Elefante turns the memory system into task intelligence. It selects a bounded, project-scoped set of governed memories or safely abstains.
          </p>

          <section className="mt-6 border border-slate-800 bg-slate-950/55 p-5">
            <div className="border-l-2 border-amber-300/60 pl-3">
              <strong className="block text-sm font-medium text-slate-100">No Recall evidence yet</strong>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">No operational receipt was returned in this environment, so the dashboard does not claim that Recall ran.</p>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              {[
                ['1 · Confirm project', 'Bind one active registered project so unrelated work cannot enter the result.'],
                ['2 · Ask one question', 'Run one ephemeral, project-scoped Recall check.'],
                ['3 · Inspect the receipt', 'Read status, selected IDs, conflicts, project, and verification time.'],
              ].map(([title, description]) => (
                <div key={title} className="border-l-2 border-slate-700 pl-3">
                  <strong className="block text-xs font-medium text-slate-200">{title}</strong>
                  <span className="mt-1 block text-[10px] leading-relaxed text-slate-500">{description}</span>
                </div>
              ))}
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <button type="button" onClick={() => setActiveTab('projects')} className="min-h-11 border border-slate-700 px-4 text-xs text-slate-200 hover:border-cyan-400/60">Understand project boundaries</button>
              <button type="button" onClick={() => setActiveTab('memories')} className="min-h-11 border border-slate-700 px-4 text-xs text-slate-200 hover:border-cyan-400/60">Inspect available memories</button>
            </div>
          </section>

          <p className="mt-5 text-xs leading-relaxed text-slate-600">
            A Recall receipt proves governed selection ran. It still does not prove answer correctness or task improvement.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto px-5 py-5 md:px-8 md:py-7">
      <div className="mx-auto max-w-[1180px] space-y-5">
        <header className="flex flex-col gap-4 border-b elefante-hairline pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.18em]">Recall Inspector</div>
            <h1 className="mt-2 text-3xl font-medium tracking-[-0.035em] text-slate-100">Test what Elefante supplies for one real question.</h1>
          </div>
          <p className="max-w-lg text-sm leading-relaxed text-slate-500 lg:text-right">
            This is a project-scoped, read-only check. It can supply a bounded memory bundle or abstain; it does not answer the question or grade the result.
          </p>
        </header>

        <section className="grid gap-3 md:grid-cols-3" aria-label="Recall workflow">
          {[
            ['1 · Confirm project', activeProject?.name ?? 'Choose one active project'],
            ['2 · Ask one question', 'The question is ephemeral and not stored here'],
            ['3 · Inspect the receipt', 'Status, selected IDs, conflicts, and time'],
          ].map(([title, description]) => (
            <div key={title} className="border border-slate-800 bg-slate-950/45 p-4">
              <strong className="block text-xs font-medium text-slate-200">{title}</strong>
              <span className="mt-1 block text-[10px] leading-relaxed text-slate-500">{description}</span>
            </div>
          ))}
        </section>

        <section className="elefante-panel grid grid-cols-1 lg:grid-cols-[minmax(0,1.65fr)_minmax(280px,0.7fr)]">
          <form onSubmit={submit} className="p-5 md:p-7 lg:border-r elefante-hairline">
            <label htmlFor="recall-workspace-question" className="text-[10px] text-slate-400 elefante-mono uppercase tracking-[0.12em]">
              Project question
            </label>
            <textarea
              id="recall-workspace-question"
              value={question}
              onChange={(event) => {
                setQuestion(event.target.value);
                setResult(null);
                clearRecallTestError();
              }}
              minLength={1}
              maxLength={1000}
              rows={4}
              required
              placeholder="Example: Which storage decision should guide this task?"
              className="mt-2 w-full resize-y border border-slate-700 bg-slate-900/75 px-4 py-3 text-sm leading-relaxed text-slate-100 outline-none placeholder:text-slate-700 focus:border-cyan-400/70"
            />
            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-[10px] leading-relaxed text-slate-500">
                Ephemeral check · no memory content is returned to Home · no Recall history is created here.
              </p>
              <button
                type="submit"
                disabled={!canRun || isRecallTesting}
                className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 border border-cyan-400/60 bg-cyan-950/20 px-5 text-xs text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isRecallTesting
                  ? <Loader2 size={14} className="animate-spin" aria-hidden="true" />
                  : <SearchCheck size={14} aria-hidden="true" />}
                {isRecallTesting ? 'Checking Recall…' : 'Run Recall Check'}
              </button>
            </div>
            {recallTestError && !result && (
              <p className="mt-4 border border-red-400/40 bg-red-950/10 p-3 text-xs text-red-200" role="alert">
                {recallTestError}
              </p>
            )}
          </form>

          <aside className="bg-slate-950/45 p-5 md:p-7">
            <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">Action scope</div>
            <strong className="mt-2 block text-lg font-medium text-slate-100">
              {activeProject?.name ?? 'No active project bound'}
            </strong>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
              {activeProject
                ? 'Only this project can supply memories for the check.'
                : 'Recall fails closed until this Home session is bound to one active registered project.'}
            </p>
            {!activeProject && (
              <button
                type="button"
                onClick={() => setActiveTab(controlEnabled ? 'projects' : 'overview')}
                className="mt-4 min-h-10 border border-slate-700 px-4 text-xs text-slate-300 hover:border-cyan-400/60"
              >
                {controlEnabled ? 'Open Projects' : 'Return Home'}
              </button>
            )}
          </aside>
        </section>

        {result && copy && (
          <>
          <section className={`border p-5 md:p-7 ${copy.tone}`} aria-live="polite">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 shrink-0">{copy.icon}</div>
              <div>
                <div className="text-[9px] text-slate-500 elefante-mono uppercase tracking-[0.14em]">Current Recall Check</div>
                <h2 className="mt-1 text-xl font-medium text-slate-100">{copy.label}</h2>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{copy.summary}</p>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 border-l border-t elefante-hairline md:grid-cols-4">
              {[
                [String(result.selected_count ?? selectedIds.length), 'selected memories'],
                [String(result.conflict_count ?? 0), 'withheld conflicts'],
                [result.project?.name ?? activeProject?.name ?? 'Unavailable', 'project'],
                [formatVerifiedAt(result.verified_at), 'verified at'],
              ].map(([value, label]) => (
                <div key={label} className="min-h-[82px] border-b border-r elefante-hairline p-3">
                  <strong className="block text-sm font-medium text-slate-100">{value}</strong>
                  <span className="mt-2 block text-[8px] text-slate-600 elefante-mono uppercase tracking-[0.09em]">{label}</span>
                </div>
              ))}
            </div>

            {selectedIds.length > 0 && (
              <div className="mt-5">
                <h3 className="text-[9px] text-slate-500 elefante-mono uppercase tracking-[0.14em]">Selected records</h3>
                <div className="mt-3 grid gap-2 md:grid-cols-3">
                  {selectedIds.map((memoryId) => {
                    const memory = memoriesById.get(memoryId);
                    return (
                      <button
                        key={memoryId}
                        type="button"
                        onClick={() => inspectMemory(memoryId)}
                        className="border border-slate-800 bg-slate-950/65 p-3 text-left hover:border-cyan-400/50"
                      >
                        <strong className="block text-xs font-medium text-slate-100">
                          {memory?.name ?? 'Selected memory'}
                        </strong>
                        <span className="mt-2 block text-[9px] text-slate-600 elefante-mono">{shortId(memoryId)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </section>

          <section className="grid grid-cols-1 gap-4 border-t elefante-hairline pt-5 md:grid-cols-2">
            <div>
              <h2 className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.14em]">What this proves</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                The current governed Recall path ran for one project and returned the status, selected count and IDs, conflict count, and verification time shown above.
              </p>
            </div>
            <div>
              <h2 className="text-[10px] text-slate-500 elefante-mono uppercase tracking-[0.14em]">What it does not prove</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-500">
                Home has no per-signal reasons, withheld IDs, historical trace, answer quality, or task-outcome evidence for this check.
              </p>
            </div>
          </section>
          </>
        )}
      </div>
    </div>
  );
}
