import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FolderCheck,
  Loader2,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useDashboardStore } from '@/store';
import type {
  ProjectAssignmentResponse,
  ProjectReviewMemory,
} from '@/types';

const REVIEW_PAGE_SIZE = 25;

function AssignmentDialog({
  memory,
  onClose,
}: {
  memory: ProjectReviewMemory;
  onClose: () => void;
}) {
  const registry = useDashboardStore((state) => state.projectRegistry);
  const activeProjectId = useDashboardStore((state) => state.activeProjectId);
  const assignProjectMemory = useDashboardStore((state) => state.assignProjectMemory);
  const isAssigning = useDashboardStore((state) => state.isProjectAssigning);
  const projectReviewError = useDashboardStore((state) => state.projectReviewError);
  const clearProjectReviewError = useDashboardStore((state) => state.clearProjectReviewError);
  const projects = useMemo(
    () => (registry?.projects ?? []).filter(
      (project) => project.active && project.root_status !== 'missing',
    ),
    [registry],
  );
  const [projectId, setProjectId] = useState(
    projects.some((project) => project.project_id === activeProjectId)
      ? activeProjectId ?? ''
      : projects[0]?.project_id ?? '',
  );
  const [protectedAcknowledged, setProtectedAcknowledged] = useState(false);
  const [result, setResult] = useState<ProjectAssignmentResponse | null>(null);

  useEffect(() => {
    clearProjectReviewError();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isAssigning) onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [clearProjectReviewError, isAssigning, onClose]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!projectId || (memory.protected && !protectedAcknowledged)) return;
    const next = await assignProjectMemory(
      memory.memory_id,
      projectId,
      protectedAcknowledged,
    );
    setResult(next);
  };

  const verified = result?.assignment_status === 'VERIFIED_COMPLETE' && result.success;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/85 px-3 py-6 backdrop-blur-sm sm:items-center sm:py-10"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isAssigning) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-assignment-title"
        className="w-full max-w-xl border border-slate-700 bg-slate-950 shadow-2xl shadow-cyan-950/30"
      >
        <header className="flex items-start justify-between border-b border-slate-800 px-5 py-4 sm:px-6">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 border border-cyan-400/30 p-2 text-cyan-300">
              <FolderCheck size={18} aria-hidden="true" />
            </div>
            <div>
              <div className="text-[9px] text-cyan-400 elefante-mono uppercase tracking-[0.16em]">Legacy project review</div>
              <h2 id="project-assignment-title" className="mt-1 text-xl font-medium text-slate-100">
                Assign this memory
              </h2>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
                You choose the project. Elefante does not infer it from memory text.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isAssigning}
            aria-label="Close project assignment"
            className="min-h-10 min-w-10 border border-slate-800 text-slate-500 hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
          >
            <X size={16} className="mx-auto" aria-hidden="true" />
          </button>
        </header>

        <form onSubmit={submit} className="px-5 py-5 sm:px-6">
          {verified && result.assigned ? (
            <div className="border border-emerald-400/40 bg-emerald-950/10 p-5" role="status">
              <div className="flex items-start gap-3">
                <ShieldCheck size={21} className="mt-0.5 shrink-0 text-emerald-300" aria-hidden="true" />
                <div>
                  <span className="text-[9px] text-emerald-300 elefante-mono uppercase tracking-[0.14em]">Project assignment verified</span>
                  <h3 className="mt-1 text-base font-medium text-slate-100">{result.assigned.title}</h3>
                  <p className="mt-1 text-[11px] text-slate-400">Now isolated in {result.assigned.project.name}</p>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {(result.receipt?.checks ?? []).map((check) => (
                  <div key={check.name} className="flex items-center gap-2 border border-emerald-400/30 px-3 py-2 text-[10px] text-emerald-200">
                    <CheckCircle2 size={13} aria-hidden="true" />
                    <span>{check.name.replace(/_/g, ' ')}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <>
              <div className="border border-slate-800 bg-slate-900/40 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="border border-cyan-400/30 px-2 py-0.5 text-[9px] text-cyan-300 elefante-mono uppercase">{memory.memory_type}</span>
                  <span className="border border-slate-700 px-2 py-0.5 text-[9px] text-slate-500 elefante-mono uppercase">{memory.status}</span>
                  {memory.protected && (
                    <span className="border border-amber-300/40 px-2 py-0.5 text-[9px] text-amber-200 elefante-mono uppercase">Protected</span>
                  )}
                </div>
                <h3 className="mt-3 text-sm font-medium text-slate-100">{memory.title}</h3>
                {memory.summary && <p className="mt-2 text-xs leading-relaxed text-slate-500">{memory.summary}</p>}
              </div>

              <label htmlFor="assignment-project" className="mt-5 block text-[10px] text-slate-400 elefante-mono uppercase tracking-[0.12em]">
                Registered project
              </label>
              <select
                id="assignment-project"
                value={projectId}
                onChange={(event) => {
                  setProjectId(event.target.value);
                  setResult(null);
                  clearProjectReviewError();
                }}
                required
                autoFocus
                className="mt-2 min-h-12 w-full border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400/70"
              >
                {projects.length === 0 && <option value="">No active available project</option>}
                {projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>{project.name}</option>
                ))}
              </select>

              {memory.protected && (
                <label className="mt-4 flex items-start gap-3 border border-amber-300/30 bg-amber-950/10 p-3 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={protectedAcknowledged}
                    onChange={(event) => setProtectedAcknowledged(event.target.checked)}
                    className="mt-0.5 h-4 w-4 accent-amber-300"
                  />
                  <span>
                    <span className="block text-amber-100">Assign this protected memory</span>
                    <span className="mt-1 block text-[11px] leading-relaxed text-slate-500">Its protection remains unchanged; only its declared project is added.</span>
                  </span>
                </label>
              )}

              {projectReviewError && (
                <p className="mt-4 border border-red-400/40 bg-red-950/10 p-3 text-xs text-red-200" role="alert">
                  {projectReviewError}
                </p>
              )}
            </>
          )}

          <div className="mt-5 flex flex-col-reverse gap-2 border-t border-slate-800 pt-4 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={onClose}
              disabled={isAssigning}
              className="min-h-11 border border-slate-800 px-4 text-xs text-slate-500 hover:text-slate-200 disabled:opacity-40"
            >
              {verified ? 'Done' : 'Cancel'}
            </button>
            {!verified && (
              <button
                type="submit"
                disabled={isAssigning || !projectId || (memory.protected && !protectedAcknowledged)}
                className="inline-flex min-h-11 items-center justify-center gap-2 border border-cyan-400/60 bg-cyan-950/20 px-5 text-xs text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isAssigning && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                {isAssigning ? 'Assigning and verifying…' : 'Assign and verify'}
              </button>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}

export function ProjectReviewPanel() {
  const controlEnabled = useDashboardStore((state) => state.controlEnabled);
  const review = useDashboardStore((state) => state.projectReview);
  const error = useDashboardStore((state) => state.projectReviewError);
  const loading = useDashboardStore((state) => state.isProjectReviewLoading);
  const assigning = useDashboardStore((state) => state.isProjectAssigning);
  const fetchProjectReview = useDashboardStore((state) => state.fetchProjectReview);
  const [selected, setSelected] = useState<ProjectReviewMemory | null>(null);

  useEffect(() => {
    if (controlEnabled && review === null && !loading && !error) {
      void fetchProjectReview(0, REVIEW_PAGE_SIZE);
    }
  }, [controlEnabled, error, fetchProjectReview, loading, review]);

  const previousOffset = Math.max(0, (review?.offset ?? 0) - (review?.limit ?? REVIEW_PAGE_SIZE));
  const nextOffset = (review?.offset ?? 0) + (review?.limit ?? REVIEW_PAGE_SIZE);

  return (
    <section className="elefante-panel overflow-hidden" aria-labelledby="project-review-title">
      <div className="flex flex-col gap-3 border-b elefante-hairline px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-5">
        <div>
          <div className="flex items-center gap-2">
            <FolderCheck size={15} className="text-cyan-400" aria-hidden="true" />
            <h2 id="project-review-title" className="text-[10px] text-slate-200 elefante-mono uppercase tracking-[0.16em]">Legacy memory review</h2>
          </div>
          <p className="mt-2 max-w-2xl text-[11px] leading-relaxed text-slate-500">
            Old unassigned memories stay available in compatibility mode until you choose where each belongs. Elefante never guesses from their text.
          </p>
        </div>
        <span className={`shrink-0 border px-2.5 py-1.5 text-[9px] elefante-mono uppercase tracking-[0.12em] ${review?.total_unscoped ? 'border-amber-300/50 text-amber-200' : 'border-emerald-400/40 text-emerald-300'}`}>
          {loading ? 'Checking…' : review ? `${review.total_unscoped} unassigned` : 'Not verified'}
        </span>
      </div>

      {!controlEnabled && (
        <div className="px-5 py-6 text-xs leading-relaxed text-slate-500">
          Reopen Home through Elefante to verify and assign legacy memories.
        </div>
      )}

      {controlEnabled && loading && !review && (
        <div className="flex items-center gap-2 px-5 py-6 text-xs text-slate-500">
          <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          Checking authoritative memory scope…
        </div>
      )}

      {controlEnabled && error && !review && (
        <div className="m-4 border border-red-400/40 bg-red-950/20 p-4 text-xs text-red-200" role="alert">
          <div className="flex items-start gap-2">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
          <button type="button" onClick={() => void fetchProjectReview(0, REVIEW_PAGE_SIZE)} className="mt-3 min-h-10 border border-red-300/40 px-3 text-[10px] hover:border-red-200">Try again</button>
        </div>
      )}

      {review && review.total_unscoped === 0 && (
        <div className="flex items-start gap-3 px-5 py-6">
          <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-300" aria-hidden="true" />
          <div>
            <h3 className="text-sm font-medium text-slate-200">Legacy review complete</h3>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">No fully unassigned memory remains. Strict project isolation can be enabled when the registered project map is ready.</p>
          </div>
        </div>
      )}

      {review && review.memories.length > 0 && (
        <>
          <div className="divide-y divide-slate-800/80">
            {review.memories.map((memory) => (
              <article key={memory.memory_id} className="flex flex-col gap-4 px-4 py-4 sm:px-5 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="border border-cyan-400/30 px-2 py-0.5 text-[9px] text-cyan-300 elefante-mono uppercase">{memory.memory_type}</span>
                    <span className="border border-slate-700 px-2 py-0.5 text-[9px] text-slate-500 elefante-mono uppercase">{memory.status}</span>
                    {memory.protected && <span className="border border-amber-300/40 px-2 py-0.5 text-[9px] text-amber-200 elefante-mono uppercase">Protected</span>}
                  </div>
                  <h3 className="mt-2 text-sm font-medium text-slate-100">{memory.title}</h3>
                  {memory.summary && <p className="mt-1 max-w-3xl text-[11px] leading-relaxed text-slate-500">{memory.summary}</p>}
                </div>
                <button
                  type="button"
                  onClick={() => setSelected(memory)}
                  disabled={assigning}
                  className="min-h-11 shrink-0 border border-cyan-400/50 px-4 text-xs text-cyan-100 hover:bg-cyan-950/20 disabled:opacity-40"
                >
                  Choose project
                </button>
              </article>
            ))}
          </div>
          <div className="flex items-center justify-between gap-3 border-t elefante-hairline px-4 py-3 sm:px-5">
            <button
              type="button"
              onClick={() => void fetchProjectReview(previousOffset, review.limit)}
              disabled={loading || review.offset === 0}
              className="inline-flex min-h-10 items-center gap-2 border border-slate-700 px-3 text-[10px] text-slate-400 disabled:opacity-30"
            >
              <ArrowLeft size={13} aria-hidden="true" /> Previous
            </button>
            <span className="text-[9px] text-slate-600 elefante-mono uppercase">
              {review.offset + 1}–{review.offset + review.returned_count} of {review.total_unscoped}
            </span>
            <button
              type="button"
              onClick={() => void fetchProjectReview(nextOffset, review.limit)}
              disabled={loading || !review.has_more}
              className="inline-flex min-h-10 items-center gap-2 border border-slate-700 px-3 text-[10px] text-slate-400 disabled:opacity-30"
            >
              Next <ArrowRight size={13} aria-hidden="true" />
            </button>
          </div>
        </>
      )}

      {selected && <AssignmentDialog memory={selected} onClose={() => setSelected(null)} />}
    </section>
  );
}
