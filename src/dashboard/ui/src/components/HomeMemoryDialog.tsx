import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  Loader2,
  SearchCheck,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useDashboardStore } from '@/store';
import type {
  KnowledgeKind,
  RecallTestResponse,
  RememberResponse,
} from '@/types';

type DialogMode = 'remember' | 'recall';

const KNOWLEDGE_KINDS: Array<{
  value: KnowledgeKind;
  label: string;
  description: string;
}> = [
  { value: 'decision', label: 'Decision', description: 'A choice later work should follow.' },
  { value: 'constraint', label: 'Constraint', description: 'A boundary later work must respect.' },
  { value: 'preference', label: 'Preference', description: 'A stable way you want work done.' },
  { value: 'lesson', label: 'Lesson', description: 'Something learned that should change later work.' },
];

function ReceiptChecks({ result }: { result: RememberResponse }) {
  const checks = result.receipt?.checks ?? [];
  return (
    <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
      {checks.map((check) => (
        <div
          key={check.name}
          className={`flex items-center gap-2 border px-3 py-2 text-[10px] ${
            check.passed
              ? 'border-emerald-400/30 text-emerald-200'
              : 'border-red-400/40 text-red-200'
          }`}
        >
          {check.passed
            ? <CheckCircle2 size={13} aria-hidden="true" />
            : <AlertTriangle size={13} aria-hidden="true" />}
          <span>{check.name.replace(/_/g, ' ')}</span>
        </div>
      ))}
    </div>
  );
}

export function HomeMemoryDialog({
  mode,
  onClose,
}: {
  mode: DialogMode;
  onClose: () => void;
}) {
  const remember = useDashboardStore((state) => state.remember);
  const keepBothMemories = useDashboardStore((state) => state.keepBothMemories);
  const testRecall = useDashboardStore((state) => state.testRecall);
  const isRemembering = useDashboardStore((state) => state.isRemembering);
  const isRecallTesting = useDashboardStore((state) => state.isRecallTesting);
  const rememberError = useDashboardStore((state) => state.rememberError);
  const recallTestError = useDashboardStore((state) => state.recallTestError);
  const clearRememberError = useDashboardStore((state) => state.clearRememberError);
  const clearRecallTestError = useDashboardStore((state) => state.clearRecallTestError);
  const getMemoryNodes = useDashboardStore((state) => state.getMemoryNodes);
  const setActiveTab = useDashboardStore((state) => state.setActiveTab);
  const setInspectedMemoryId = useDashboardStore((state) => state.setInspectedMemoryId);
  const [knowledgeKind, setKnowledgeKind] = useState<KnowledgeKind>('decision');
  const [content, setContent] = useState('');
  const [question, setQuestion] = useState('');
  const [rememberResult, setRememberResult] = useState<RememberResponse | null>(null);
  const [recallResult, setRecallResult] = useState<RecallTestResponse | null>(null);

  useEffect(() => {
    clearRememberError();
    clearRecallTestError();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [clearRecallTestError, clearRememberError, onClose]);

  const selectedTitles = useMemo(() => {
    const names = new Map(getMemoryNodes().map((memory) => [memory.id, memory.name]));
    return (recallResult?.selected_memory_ids ?? []).map(
      (memoryId) => names.get(memoryId) ?? 'Verified project memory',
    );
  }, [getMemoryNodes, recallResult]);

  const submitRemember = async (event: FormEvent) => {
    event.preventDefault();
    const result = await remember(content.trim(), knowledgeKind, question.trim());
    setRememberResult(result);
  };

  const submitRecall = async (event: FormEvent) => {
    event.preventDefault();
    const result = await testRecall(question.trim());
    setRecallResult(result);
  };

  const keepBoth = async () => {
    if (!rememberResult?.plan_id) return;
    const result = await keepBothMemories(
      rememberResult.plan_id,
      content.trim(),
      question.trim(),
    );
    setRememberResult(result);
  };

  const reviewOverlap = () => {
    const memoryId = rememberResult?.plan?.overlaps[0]?.memory_id;
    if (memoryId) setInspectedMemoryId(memoryId);
    setActiveTab('memories');
    onClose();
  };

  const busy = mode === 'remember' ? isRemembering : isRecallTesting;
  const title = mode === 'remember' ? 'Remember for this project' : 'Test Recall for this project';

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/85 px-3 py-6 backdrop-blur-sm md:items-center md:py-10"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="home-memory-dialog-title"
        className="w-full max-w-2xl border border-slate-700 bg-slate-950 shadow-2xl shadow-cyan-950/30"
      >
        <header className="flex items-start justify-between border-b border-slate-800 px-5 py-4 md:px-6">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 border border-cyan-400/30 p-2 text-cyan-300">
              {mode === 'remember'
                ? <Brain size={18} aria-hidden="true" />
                : <SearchCheck size={18} aria-hidden="true" />}
            </div>
            <div>
              <div className="text-[9px] text-cyan-400 elefante-mono uppercase tracking-[0.16em]">Project-safe customer action</div>
              <h2 id="home-memory-dialog-title" className="mt-1 text-xl font-medium text-slate-100">{title}</h2>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
                {mode === 'remember'
                  ? 'Elefante searches first, writes once, and proves a future Recall.'
                  : 'Elefante runs one scoped question and returns proof, not private memory content.'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="min-h-10 min-w-10 border border-slate-800 text-slate-500 hover:border-slate-600 hover:text-slate-200"
          >
            <X size={16} className="mx-auto" aria-hidden="true" />
          </button>
        </header>

        {mode === 'remember' ? (
          <form onSubmit={submitRemember} className="px-5 py-5 md:px-6">
            {rememberResult?.remember_status !== 'VERIFIED_COMPLETE' ? (
              <>
                <fieldset>
                  <legend className="text-[10px] text-slate-400 elefante-mono uppercase tracking-[0.12em]">What kind of knowledge is this?</legend>
                  <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                    {KNOWLEDGE_KINDS.map((kind) => (
                      <button
                        key={kind.value}
                        type="button"
                        onClick={() => setKnowledgeKind(kind.value)}
                        aria-pressed={knowledgeKind === kind.value}
                        className={`min-h-20 border p-3 text-left transition-colors ${
                          knowledgeKind === kind.value
                            ? 'border-cyan-400/70 bg-cyan-950/20 text-slate-100'
                            : 'border-slate-800 text-slate-500 hover:border-slate-600'
                        }`}
                      >
                        <strong className="block text-xs font-medium">{kind.label}</strong>
                        <span className="mt-1 block text-[9px] leading-snug">{kind.description}</span>
                      </button>
                    ))}
                  </div>
                </fieldset>

                <label className="mt-5 block text-[10px] text-slate-400 elefante-mono uppercase tracking-[0.12em]" htmlFor="remember-content">
                  What should Elefante remember?
                </label>
                <textarea
                  id="remember-content"
                  value={content}
                  onChange={(event) => {
                    setContent(event.target.value);
                    setRememberResult(null);
                  }}
                  minLength={1}
                  maxLength={8000}
                  rows={5}
                  required
                  autoFocus
                  placeholder="Example: Use SQLite for the project index because local recovery is required."
                  className="mt-2 w-full resize-y border border-slate-700 bg-slate-900/80 px-3 py-3 text-sm leading-relaxed text-slate-100 outline-none placeholder:text-slate-700 focus:border-cyan-400/70"
                />

                <label className="mt-4 block text-[10px] text-slate-400 elefante-mono uppercase tracking-[0.12em]" htmlFor="remember-question">
                  How might you ask for this later?
                </label>
                <input
                  id="remember-question"
                  value={question}
                  onChange={(event) => {
                    setQuestion(event.target.value);
                    setRememberResult(null);
                  }}
                  minLength={1}
                  maxLength={1000}
                  required
                  placeholder="Example: What database should the project index use?"
                  className="mt-2 min-h-11 w-full border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-700 focus:border-cyan-400/70"
                />
                <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
                  Elefante saves this as a project-only Recall cue and proves it now.
                </p>
              </>
            ) : null}

            {rememberResult?.remember_status === 'NEEDS_HUMAN' && rememberResult.plan && (
              <div className="mt-5 border border-amber-300/40 bg-amber-950/10 p-4" role="alert">
                <div className="flex items-start gap-3">
                  <AlertTriangle size={17} className="mt-0.5 shrink-0 text-amber-200" aria-hidden="true" />
                  <div>
                    <strong className="text-sm font-medium text-amber-100">Related knowledge already exists</strong>
                    <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{rememberResult.plan.reason}</p>
                  </div>
                </div>
                <div className="mt-3 space-y-2">
                  {rememberResult.plan.overlaps.map((overlap) => (
                    <div key={overlap.memory_id} className="border border-slate-800 bg-slate-950/70 px-3 py-2">
                      <span className="text-[9px] text-amber-300 elefante-mono uppercase">{overlap.relation}</span>
                      <strong className="mt-1 block text-xs font-medium text-slate-200">{overlap.title}</strong>
                    </div>
                  ))}
                </div>
                <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <button type="button" onClick={reviewOverlap} className="min-h-11 border border-slate-700 px-3 text-xs text-slate-300 hover:border-cyan-400/60">
                    Update existing
                  </button>
                  <button type="button" onClick={reviewOverlap} className="min-h-11 border border-slate-700 px-3 text-xs text-slate-300 hover:border-cyan-400/60">
                    Supersede existing
                  </button>
                  <button type="button" onClick={() => void keepBoth()} disabled={busy} className="min-h-11 border border-amber-300/50 px-3 text-xs text-amber-100 hover:bg-amber-950/20 disabled:opacity-50">
                    {busy ? 'Verifying…' : 'Keep both'}
                  </button>
                  <button type="button" onClick={onClose} className="min-h-11 border border-slate-800 px-3 text-xs text-slate-500 hover:text-slate-200">
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {rememberResult?.remember_status === 'VERIFIED_COMPLETE' && rememberResult.remembered && (
              <div className="border border-emerald-400/40 bg-emerald-950/10 p-5" role="status">
                <div className="flex items-start gap-3">
                  <ShieldCheck size={21} className="mt-0.5 shrink-0 text-emerald-300" aria-hidden="true" />
                  <div>
                    <span className="text-[9px] text-emerald-300 elefante-mono uppercase tracking-[0.14em]">Remember verified</span>
                    <h3 className="mt-1 text-base font-medium text-slate-100">{rememberResult.remembered.title}</h3>
                    <p className="mt-1 text-[11px] text-slate-400">
                      {rememberResult.remembered.kind} · {rememberResult.remembered.project.name} · Recall passed
                    </p>
                  </div>
                </div>
                <ReceiptChecks result={rememberResult} />
              </div>
            )}

            {(rememberError || rememberResult?.error) && rememberResult?.remember_status !== 'NEEDS_HUMAN' && (
              <div className="mt-4 border border-red-400/40 bg-red-950/10 p-4 text-red-200" role="alert">
                <strong className="text-sm font-medium">Remember did not complete</strong>
                <p className="mt-1 text-xs leading-relaxed">
                  {rememberResult?.error || rememberError}
                </p>
                {rememberResult?.receipt?.rollback === 'verified' && (
                  <p className="mt-2 text-[10px] text-slate-400">
                    Rollback verified · the attempted memory was removed.
                  </p>
                )}
                {rememberResult?.receipt && <ReceiptChecks result={rememberResult} />}
              </div>
            )}

            <div className="mt-5 flex justify-end gap-2 border-t border-slate-800 pt-4">
              <button type="button" onClick={onClose} className="min-h-11 border border-slate-800 px-4 text-xs text-slate-500 hover:text-slate-200">
                {rememberResult?.remember_status === 'VERIFIED_COMPLETE' ? 'Done' : 'Close'}
              </button>
              {rememberResult?.remember_status !== 'VERIFIED_COMPLETE' && rememberResult?.remember_status !== 'NEEDS_HUMAN' && (
                <button
                  type="submit"
                  disabled={busy || !content.trim() || !question.trim()}
                  className="inline-flex min-h-11 items-center gap-2 border border-cyan-400/60 bg-cyan-950/20 px-5 text-xs text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {busy && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                  Remember and verify
                </button>
              )}
            </div>
          </form>
        ) : (
          <form onSubmit={submitRecall} className="px-5 py-5 md:px-6">
            <label className="block text-[10px] text-slate-400 elefante-mono uppercase tracking-[0.12em]" htmlFor="recall-question">
              Ask one likely project question
            </label>
            <input
              id="recall-question"
              value={question}
              onChange={(event) => {
                setQuestion(event.target.value);
                setRecallResult(null);
              }}
              minLength={1}
              maxLength={1000}
              required
              autoFocus
              placeholder="What decision should guide this work?"
              className="mt-2 min-h-12 w-full border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-700 focus:border-cyan-400/70"
            />

            {recallResult && (
              <div className={`mt-5 border p-4 ${
                recallResult.recall_status === 'supplied'
                  ? 'border-emerald-400/40 bg-emerald-950/10'
                  : recallResult.recall_status === 'no_match'
                    ? 'border-slate-700 bg-slate-900/40'
                    : 'border-amber-300/40 bg-amber-950/10'
              }`} role="status">
                <div className="flex items-start gap-3">
                  {recallResult.recall_status === 'supplied'
                    ? <CheckCircle2 size={18} className="mt-0.5 text-emerald-300" aria-hidden="true" />
                    : <AlertTriangle size={18} className="mt-0.5 text-amber-200" aria-hidden="true" />}
                  <div>
                    <strong className="text-sm font-medium text-slate-100">
                      {recallResult.recall_status === 'supplied'
                        ? `Recall supplied ${recallResult.selected_count ?? selectedTitles.length} project ${selectedTitles.length === 1 ? 'memory' : 'memories'}`
                        : recallResult.recall_status === 'no_match'
                          ? 'No applicable project memory'
                          : recallResult.recall_status === 'blocked'
                            ? 'Recall stopped for conflict review'
                            : 'Recall test unavailable'}
                    </strong>
                    <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
                      {recallResult.recall_status === 'supplied'
                        ? 'The governed Recall path selected these records. Their private content stayed in the agent path.'
                        : recallResult.error || 'Elefante returned no unrelated history.'}
                    </p>
                  </div>
                </div>
                {selectedTitles.length > 0 && (
                  <ul className="mt-3 space-y-2">
                    {selectedTitles.map((memoryTitle, index) => (
                      <li key={`${memoryTitle}-${index}`} className="border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs text-slate-200">
                        {memoryTitle}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {recallTestError && !recallResult && (
              <p className="mt-4 border border-red-400/40 bg-red-950/10 p-3 text-xs text-red-200" role="alert">
                {recallTestError}
              </p>
            )}

            <div className="mt-5 flex justify-end gap-2 border-t border-slate-800 pt-4">
              <button type="button" onClick={onClose} className="min-h-11 border border-slate-800 px-4 text-xs text-slate-500 hover:text-slate-200">
                Close
              </button>
              <button
                type="submit"
                disabled={busy || !question.trim()}
                className="inline-flex min-h-11 items-center gap-2 border border-cyan-400/60 bg-cyan-950/20 px-5 text-xs text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                Test Recall
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
