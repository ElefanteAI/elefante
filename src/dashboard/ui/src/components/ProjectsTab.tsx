import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react';
import { FolderOpen, Pencil, Plus, ShieldCheck, Trash2, X } from 'lucide-react';
import { useDashboardStore } from '@/store';
import { ProjectReviewPanel } from '@/components/ProjectReviewPanel';
import type {
  ProjectAction,
  ProjectRegistrySnapshot,
  RegisteredProject,
} from '@/types';

type ProjectDialog =
  | { kind: 'form'; projectId: string | null }
  | { kind: 'remove'; projectId: string }
  | { kind: 'strict' }
  | null;

type ProjectForm = {
  name: string;
  root: string;
  active: boolean;
};

const EMPTY_FORM: ProjectForm = { name: '', root: '', active: true };
const FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[href]',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function projectForm(project: RegisteredProject | undefined): ProjectForm {
  if (!project) return { ...EMPTY_FORM };
  return {
    name: project.name,
    root: project.root,
    active: project.active,
  };
}

function stateLabel(registry: ProjectRegistrySnapshot | null): {
  label: string;
  description: string;
  tone: string;
  invalid: boolean;
} {
  if (!registry) {
    return {
      label: 'Registry unavailable',
      description: 'The current snapshot did not include Project Registry state.',
      tone: 'border-slate-700 text-slate-400',
      invalid: true,
    };
  }
  if (registry.status === 'invalid' || registry.mode === 'invalid') {
    const unavailable = registry.status === 'unavailable';
    return {
      label: unavailable ? 'Needs attention' : 'Invalid',
      description: unavailable
        ? 'The current Home snapshot cannot prove Project Registry state. Changes are disabled.'
        : 'The registry could not be validated. Changes are disabled until it is repaired.',
      tone: 'border-red-400/60 text-red-300',
      invalid: true,
    };
  }
  if (registry.mode === 'strict') {
    return {
      label: 'Strict',
      description: 'New memories require one active registered project. Cross-project delivery is disabled.',
      tone: 'border-amber-300/60 text-amber-300',
      invalid: false,
    };
  }
  return {
    label: 'Compatibility',
    description: 'Existing unscoped memory behavior remains available.',
    tone: 'border-cyan-500/60 text-cyan-400',
    invalid: false,
  };
}

function DialogShell({
  title,
  description,
  dialogRef,
  onClose,
  children,
}: {
  title: string;
  description: string;
  dialogRef: React.RefObject<HTMLDivElement>;
  onClose: () => void;
  children: ReactNode;
}) {
  const titleId = 'projects-dialog-title';
  const descriptionId = 'projects-dialog-description';

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/70 p-3 sm:items-center sm:p-6">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="w-full max-w-xl border border-amber-300/30 bg-slate-950 p-5 shadow-2xl shadow-black/50 sm:p-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[9px] text-amber-300 elefante-mono uppercase tracking-[0.18em]">Home Projects</div>
            <h2 id={titleId} className="mt-2 text-lg font-medium text-slate-100">{title}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="shrink-0 border border-slate-700 p-2 text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-100"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <p id={descriptionId} className="mt-3 text-xs leading-relaxed text-slate-400">{description}</p>
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}

function ProjectRow({
  project,
  canManage,
  isManaging,
  onEdit,
  onToggle,
  onRemove,
}: {
  project: RegisteredProject;
  canManage: boolean;
  isManaging: boolean;
  onEdit: (project: RegisteredProject) => void;
  onToggle: (project: RegisteredProject) => void;
  onRemove: (project: RegisteredProject) => void;
}) {
  const actionDisabled = !canManage || isManaging;
  const activationDisabled = actionDisabled
    || (!project.active && project.root_status === 'missing');
  const toggleLabel = project.active ? `Deactivate ${project.name}` : `Activate ${project.name}`;

  return (
    <article className="flex flex-col gap-4 px-4 py-4 sm:px-5 lg:flex-row lg:items-center lg:justify-between">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="min-w-0 truncate text-sm font-semibold text-slate-100" title={project.name}>
            {project.name}
          </h3>
          <span
            className={
              'border px-2 py-0.5 text-[9px] elefante-mono uppercase tracking-[0.12em] ' +
              (project.active
                ? 'border-emerald-400/40 text-emerald-300'
                : 'border-slate-700 text-slate-500')
            }
          >
            {project.active ? 'Active' : 'Inactive'}
          </span>
          {project.root_status === 'missing' && (
            <span className="border border-red-400/50 px-2 py-0.5 text-[9px] text-red-300 elefante-mono uppercase tracking-[0.12em]">
              Folder missing
            </span>
          )}
        </div>
        <div className="mt-2 flex min-w-0 items-start gap-2 text-[11px] text-slate-400">
          <FolderOpen size={13} className="mt-0.5 shrink-0 text-cyan-500" aria-hidden="true" />
          <code className="min-w-0 break-all leading-relaxed" title={project.root}>{project.root}</code>
        </div>
        <div className="mt-2 text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.1em]" title={project.project_id}>
          Stable ID · {project.project_id.slice(0, 12)}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 sm:flex sm:shrink-0">
        <button
          type="button"
          onClick={() => onEdit(project)}
          disabled={actionDisabled}
          aria-label={`Edit ${project.name} project registration`}
          title={actionDisabled ? 'Management is unavailable in read-only mode' : `Edit ${project.name}`}
          className="inline-flex items-center justify-center gap-1.5 border border-slate-700 px-3 py-2 text-[10px] text-slate-300 transition-colors hover:border-cyan-500/60 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Pencil size={13} aria-hidden="true" />
          <span className="hidden sm:inline">Edit</span>
        </button>
        <button
          type="button"
          onClick={() => onToggle(project)}
          disabled={activationDisabled}
          aria-label={toggleLabel}
          title={project.root_status === 'missing' && !project.active
            ? 'Move the registration to an existing folder before activating it'
            : actionDisabled
              ? 'Management is unavailable in read-only mode'
              : toggleLabel}
          className="inline-flex items-center justify-center gap-1.5 border border-slate-700 px-3 py-2 text-[10px] text-slate-300 transition-colors hover:border-amber-300/60 hover:text-amber-200 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ShieldCheck size={13} aria-hidden="true" />
          <span className="hidden sm:inline">{project.active ? 'Deactivate' : 'Activate'}</span>
        </button>
        <button
          type="button"
          onClick={() => onRemove(project)}
          disabled={actionDisabled}
          aria-label={`Remove ${project.name} registration`}
          title={actionDisabled ? 'Management is unavailable in read-only mode' : `Remove ${project.name} registration`}
          className="inline-flex items-center justify-center gap-1.5 border border-red-400/30 px-3 py-2 text-[10px] text-red-300 transition-colors hover:border-red-300/70 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Trash2 size={13} aria-hidden="true" />
          <span className="hidden sm:inline">Remove</span>
        </button>
      </div>
    </article>
  );
}

export function ProjectsTab() {
  const registry = useDashboardStore((state) => state.projectRegistry);
  const snapshotContext = useDashboardStore((state) => state.snapshot?.snapshot_context);
  const controlEnabled = useDashboardStore((state) => state.controlEnabled);
  const setActiveTab = useDashboardStore((state) => state.setActiveTab);
  const isManaging = useDashboardStore((state) => state.isProjectManaging);
  const projectError = useDashboardStore((state) => state.projectError);
  const projectReview = useDashboardStore((state) => state.projectReview);
  const clearProjectError = useDashboardStore((state) => state.clearProjectError);
  const manageProjects = useDashboardStore((state) => state.manageProjects);
  const [dialog, setDialog] = useState<ProjectDialog>(null);
  const [form, setForm] = useState<ProjectForm>({ ...EMPTY_FORM });
  const [removeAcknowledged, setRemoveAcknowledged] = useState(false);
  const [strictAcknowledged, setStrictAcknowledged] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  const projects = registry?.projects ?? [];
  const activeProjects = projects.filter((project) => project.active);
  const availableActiveProjects = activeProjects.filter(
    (project) => project.root_status !== 'missing',
  );
  const projectFormReady = Boolean(form.name.trim() && form.root.trim());
  const registryState = stateLabel(registry);
  const canManage = controlEnabled && Boolean(registry) && !registryState.invalid;
  const canEnableStrict = canManage
    && registry?.mode === 'compatibility'
    && availableActiveProjects.length > 0
    && projectReview?.scan_complete === true
    && projectReview.total_unscoped === 0;

  useEffect(() => {
    if (!dialog) return undefined;

    const previousFocus = document.activeElement as HTMLElement | null;
    const focusTimer = window.setTimeout(() => {
      const firstFocusable = dialogRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      firstFocusable?.focus();
    }, 0);
    const handleDialogKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        setDialog(null);
        return;
      }
      if (event.key !== 'Tab') return;

      const focusable = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [],
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleDialogKeyDown, true);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', handleDialogKeyDown, true);
      previousFocus?.focus();
    };
  }, [dialog]);

  const openForm = (project?: RegisteredProject) => {
    clearProjectError();
    setForm(projectForm(project));
    setDialog({ kind: 'form', projectId: project?.project_id ?? null });
  };

  const openRemove = (project: RegisteredProject) => {
    clearProjectError();
    setRemoveAcknowledged(false);
    setDialog({ kind: 'remove', projectId: project.project_id });
  };

  const closeDialog = () => {
    if (!isManaging) {
      clearProjectError();
      setDialog(null);
    }
  };

  const submitProjectForm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManage || isManaging || dialog?.kind !== 'form') return;

    const name = form.name.trim();
    const root = form.root.trim();
    const action: ProjectAction = dialog.projectId
      ? { action: 'update', project_id: dialog.projectId, name, root, active: form.active }
      : { action: 'register', name, root };
    const result = await manageProjects(action);
    if (result.success) setDialog(null);
  };

  const toggleProject = async (project: RegisteredProject) => {
    if (!canManage || isManaging) return;
    await manageProjects({ action: 'update', project_id: project.project_id, active: !project.active });
  };

  const removeProject = async () => {
    if (!canManage || isManaging || dialog?.kind !== 'remove' || !removeAcknowledged) return;
    const result = await manageProjects({
      action: 'remove',
      project_id: dialog.projectId,
      confirm: true,
    });
    if (result.success) setDialog(null);
  };

  const enableStrict = async () => {
    if (!canEnableStrict || isManaging || dialog?.kind !== 'strict' || !strictAcknowledged) return;
    const result = await manageProjects({ action: 'set_mode', mode: 'strict', confirm: true });
    if (result.success) setDialog(null);
  };

  if (snapshotContext?.mode === 'showcase') {
    const exampleProject = projects[0];
    return (
      <div className="h-full overflow-auto px-5 py-5 md:px-8 md:py-7">
        <div className="mx-auto max-w-[980px]">
          <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.18em]">Project boundaries</div>
          <h1 className="mt-2 text-3xl font-medium tracking-[-0.035em] text-slate-100">Keep task guidance inside the right work.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-400">
            Projects prevent unrelated work from sharing Recall context. Overall memory inspection does not require a project; task-scoped Remember, Recall, and Correct do.
          </p>

          <section className="mt-6 grid gap-4 lg:grid-cols-[1fr_0.8fr]">
            <div className="border border-slate-800 bg-slate-950/55 p-5">
              <div className="flex items-start gap-3">
                <FolderOpen size={19} className="mt-0.5 text-cyan-300" aria-hidden="true" />
                <div>
                  <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">Example project boundary</div>
                  <h2 className="mt-2 text-lg font-medium text-slate-100">{exampleProject?.name ?? 'Elefante showcase'}</h2>
                  <p className="mt-2 text-xs leading-relaxed text-slate-500">
                    Example scope only · strict isolation represented · cross-project sharing off.
                  </p>
                </div>
              </div>
            </div>
            <div className="border border-slate-800 bg-slate-950/55 p-5">
              <div className="flex items-center gap-2 text-emerald-300">
                <ShieldCheck size={16} aria-hidden="true" />
                <strong className="text-xs font-medium">Why this matters</strong>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-slate-500">
                The active project is the delivery boundary for Remember, Recall, and Correct. Registration does not scan or change project files.
              </p>
            </div>
          </section>

          <div className="mt-5 flex flex-wrap gap-3">
            <button type="button" onClick={() => setActiveTab('memories')} className="min-h-11 border border-slate-700 px-4 text-xs text-slate-200 hover:border-cyan-400/60">
              Browse example memories
            </button>
            <button type="button" onClick={() => setActiveTab('recall')} className="min-h-11 border border-slate-700 px-4 text-xs text-slate-200 hover:border-cyan-400/60">
              See Recall evidence model
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto px-5 py-5 md:px-8 md:py-6">
      <div className="mx-auto flex min-h-full max-w-[1200px] flex-col gap-5">
        <section className="flex flex-col gap-4 border-b elefante-hairline pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.2em]">Projects</div>
            <h1 className="mt-2 text-[clamp(2rem,4vw,3.2rem)] font-medium leading-[1.02] tracking-[-0.045em] text-slate-100">
              Where your knowledge belongs.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-500">
              Review the stable project-to-folder map used for scoped memory. Renaming or moving a registration keeps its identity; removing a registration never deletes project files or memories.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            <span className={`border px-2.5 py-1.5 text-[9px] elefante-mono uppercase tracking-[0.12em] ${registryState.tone}`}>
              {registryState.label}
            </span>
            <span className={`border px-2.5 py-1.5 text-[9px] elefante-mono uppercase tracking-[0.12em] ${controlEnabled ? 'border-amber-300/50 text-amber-300' : 'border-slate-700 text-slate-500'}`}>
              {controlEnabled ? 'Management enabled' : 'Read-only'}
            </span>
            {registry?.mode === 'compatibility' && (
              <button
                type="button"
                onClick={() => {
                  clearProjectError();
                  setStrictAcknowledged(false);
                  setDialog({ kind: 'strict' });
                }}
                disabled={!canEnableStrict || isManaging}
                aria-label="Enable strict project isolation"
                title={availableActiveProjects.length === 0
                  ? 'Register and activate an available project before enabling strict mode'
                  : projectReview?.total_unscoped
                    ? 'Review every unassigned legacy memory before enabling strict mode'
                    : projectReview?.scan_complete !== true
                      ? 'Verify the legacy memory review before enabling strict mode'
                      : 'Enable strict project isolation'}
                className="inline-flex items-center gap-1.5 border border-amber-300/40 px-3 py-1.5 text-[10px] text-amber-200 transition-colors hover:border-amber-200 hover:bg-amber-300/10 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ShieldCheck size={13} aria-hidden="true" />
                Enable strict
              </button>
            )}
            <button
              type="button"
              onClick={() => openForm()}
              disabled={!canManage || isManaging}
              aria-label="Add a project registration"
              title={canManage ? 'Register a project' : 'Management is unavailable in read-only mode'}
              className="inline-flex items-center gap-1.5 border border-cyan-500/50 bg-cyan-500/10 px-3 py-1.5 text-[10px] text-cyan-300 transition-colors hover:border-cyan-300 hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus size={13} aria-hidden="true" />
              Add project
            </button>
          </div>
        </section>

        <section className={`border-l-2 bg-slate-900/45 px-4 py-3 ${registryState.invalid ? 'border-red-400/70' : registry?.mode === 'strict' ? 'border-amber-300/70' : 'border-cyan-500/70'}`}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className={`text-[9px] elefante-mono uppercase tracking-[0.16em] ${registryState.invalid ? 'text-red-300' : 'text-slate-300'}`}>
                Project Registry · {registryState.label}
              </div>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">{registryState.description}</p>
              {registry?.scope_policy === 'isolated' && registry.shared_across_projects === false && (
                <div className="mt-2 text-[9px] text-amber-200 elefante-mono uppercase tracking-[0.12em]">
                  Isolated projects · Sharing off
                </div>
              )}
            </div>
            {!controlEnabled && (
              <span className="max-w-sm text-[10px] leading-relaxed text-slate-600 sm:text-right">
                The local snapshot remains visible, but control is unavailable. Reload Home to manage projects.
              </span>
            )}
          </div>
          {registryState.invalid && registry?.error_code && (
            <div className="mt-2 text-[10px] text-red-300/80 elefante-mono">Registry error · {registry.error_code}</div>
          )}
        </section>

        <section className="grid grid-cols-2 border-l border-t elefante-hairline sm:grid-cols-4">
          <div className="border-b border-r elefante-hairline p-3">
            <div className="text-lg text-slate-100 elefante-mono">{projects.length}</div>
            <div className="mt-1 text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.1em]">Registered</div>
          </div>
          <div className="border-b border-r elefante-hairline p-3">
            <div className="text-lg text-emerald-300 elefante-mono">{activeProjects.length}</div>
            <div className="mt-1 text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.1em]">Active</div>
          </div>
          <div className="border-b border-r elefante-hairline p-3">
            <div className="text-lg text-slate-100 elefante-mono">{registry?.revision ?? '—'}</div>
            <div className="mt-1 text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.1em]">Revision</div>
          </div>
          <div className="border-b border-r elefante-hairline p-3">
            <div className="text-lg text-amber-200 elefante-mono">{projectReview?.total_unscoped ?? '—'}</div>
            <div className="mt-1 text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.1em]">Unassigned</div>
          </div>
        </section>

        {projectError && (
          <div role="alert" className="border border-red-400/40 bg-red-950/30 px-4 py-3 text-xs leading-relaxed text-red-200">
            {projectError}
          </div>
        )}

        <ProjectReviewPanel />

        <section className="elefante-panel overflow-hidden">
          <div className="flex flex-col gap-2 border-b elefante-hairline px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <div>
              <h2 className="text-[10px] text-slate-200 elefante-mono uppercase tracking-[0.16em]">Registered projects</h2>
              <p className="mt-1 text-[11px] text-slate-600">Stable identity follows the registration through a rename or move.</p>
            </div>
            {isManaging && <span className="text-[9px] text-amber-300 elefante-mono uppercase tracking-[0.12em]">Saving…</span>}
          </div>

          {projects.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <FolderOpen size={20} className="mx-auto text-slate-600" aria-hidden="true" />
              <h3 className="mt-3 text-sm font-medium text-slate-300">No project registrations yet.</h3>
              <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed text-slate-600">
                {canManage
                  ? 'Add a project folder to give new memory a stable scope.'
                  : 'Reload Home to reconnect before registering a project.'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-800/80">
              {projects.map((project) => (
                <ProjectRow
                  key={project.project_id}
                  project={project}
                  canManage={canManage}
                  isManaging={isManaging}
                  onEdit={openForm}
                  onToggle={toggleProject}
                  onRemove={openRemove}
                />
              ))}
            </div>
          )}
        </section>

        <p className="pb-2 text-[10px] leading-relaxed text-slate-600">
          Removing a registration only removes Elefante’s mapping. It does not delete files in the project folder or any memories.
          {registry?.mode === 'strict' && ' Strict mode cannot be downgraded from Home.'}
        </p>
      </div>

      {dialog?.kind === 'form' && (
        <DialogShell
          title={dialog.projectId ? 'Rename or move project' : 'Add project'}
          description={dialog.projectId
            ? 'The stable project ID stays the same when you rename or move this registration.'
            : 'Register an existing project folder. The folder must be an absolute, specific directory.'}
          dialogRef={dialogRef}
          onClose={closeDialog}
        >
          <form onSubmit={submitProjectForm} className="space-y-4">
            <div>
              <label htmlFor="project-name" className="block text-[10px] text-slate-400 elefante-mono uppercase tracking-[0.12em]">Project name</label>
              <input
                id="project-name"
                type="text"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                required
                maxLength={100}
                autoComplete="off"
                className="mt-2 w-full border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:border-amber-300/70 focus:outline-none"
                placeholder="e.g. Elefante"
              />
            </div>
            <div>
              <label htmlFor="project-root" className="block text-[10px] text-slate-400 elefante-mono uppercase tracking-[0.12em]">Project root</label>
              <input
                id="project-root"
                type="text"
                value={form.root}
                onChange={(event) => setForm((current) => ({ ...current, root: event.target.value }))}
                required
                maxLength={2048}
                autoComplete="off"
                className="mt-2 w-full border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:border-amber-300/70 focus:outline-none"
                placeholder="/Users/you/Documents/project"
              />
            </div>
            {dialog.projectId && (
              <label className="flex items-start gap-3 border-t border-slate-800 pt-4 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(event) => setForm((current) => ({ ...current, active: event.target.checked }))}
                  className="mt-0.5 h-4 w-4 accent-amber-300"
                />
                <span>
                  <span className="block">Active project</span>
                  <span className="mt-1 block text-[11px] leading-relaxed text-slate-600">Deactivate only when another active project can satisfy strict mode.</span>
                </span>
              </label>
            )}
            <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
              <button type="button" onClick={closeDialog} disabled={isManaging} className="border border-slate-700 px-4 py-2.5 text-xs text-slate-400 hover:border-slate-500 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40">Cancel</button>
              <button type="submit" disabled={!canManage || isManaging || !projectFormReady} className="border border-amber-300/50 bg-amber-300/10 px-4 py-2.5 text-xs text-amber-200 hover:bg-amber-300/20 disabled:cursor-not-allowed disabled:opacity-40">{isManaging ? 'Saving…' : dialog.projectId ? 'Save project' : 'Register project'}</button>
            </div>
          </form>
        </DialogShell>
      )}

      {dialog?.kind === 'remove' && (() => {
        const project = projects.find((candidate) => candidate.project_id === dialog.projectId);
        if (!project) return null;
        return (
          <DialogShell
            title={`Remove ${project.name}?`}
            description="This removes only the Project Registry registration. No project files or memories will be deleted."
            dialogRef={dialogRef}
            onClose={closeDialog}
          >
            <div className="border-l-2 border-red-400/70 bg-red-950/20 px-4 py-3 text-xs leading-relaxed text-red-100">
              <code className="break-all text-[11px] text-red-200/80">{project.root}</code>
              <p className="mt-2">The folder remains on disk, and every memory remains unchanged. You can register this folder again later.</p>
            </div>
            <label className="mt-4 flex items-start gap-3 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={removeAcknowledged}
                onChange={(event) => setRemoveAcknowledged(event.target.checked)}
                className="mt-0.5 h-4 w-4 accent-red-300"
              />
              <span>I understand that this removes the registration only.</span>
            </label>
            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button type="button" onClick={closeDialog} disabled={isManaging} className="border border-slate-700 px-4 py-2.5 text-xs text-slate-400 hover:border-slate-500 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40">Cancel</button>
              <button type="button" onClick={removeProject} disabled={!canManage || isManaging || !removeAcknowledged} className="border border-red-400/50 bg-red-400/10 px-4 py-2.5 text-xs text-red-200 hover:bg-red-400/20 disabled:cursor-not-allowed disabled:opacity-40">{isManaging ? 'Removing…' : 'Remove registration'}</button>
            </div>
          </DialogShell>
        );
      })()}

      {dialog?.kind === 'strict' && (
        <DialogShell
          title="Enable strict project isolation?"
          description="Strict mode is a one-way Home action. It requires at least one active project and makes new memory writes fail closed without a matching project workspace."
          dialogRef={dialogRef}
          onClose={closeDialog}
        >
          <div className="border-l-2 border-amber-300/70 bg-amber-300/5 px-4 py-3 text-xs leading-relaxed text-slate-300">
            <p>{availableActiveProjects.length} active {availableActiveProjects.length === 1 ? 'project is' : 'projects are'} ready for strict mode.</p>
            <p className="mt-2 text-slate-500">The legacy review is complete. No unassigned memory will be silently relabeled, and there is no downgrade control in Home.</p>
          </div>
          <label className="mt-4 flex items-start gap-3 text-xs text-slate-300">
            <input
              type="checkbox"
              checked={strictAcknowledged}
              onChange={(event) => setStrictAcknowledged(event.target.checked)}
              className="mt-0.5 h-4 w-4 accent-amber-300"
            />
            <span>I understand that strict mode requires an active registered project and cannot be downgraded here.</span>
          </label>
          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button type="button" onClick={closeDialog} disabled={isManaging} className="border border-slate-700 px-4 py-2.5 text-xs text-slate-400 hover:border-slate-500 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40">Cancel</button>
            <button type="button" onClick={enableStrict} disabled={!canEnableStrict || isManaging || !strictAcknowledged} className="border border-amber-300/50 bg-amber-300/10 px-4 py-2.5 text-xs text-amber-200 hover:bg-amber-300/20 disabled:cursor-not-allowed disabled:opacity-40">{isManaging ? 'Enabling…' : 'Enable strict mode'}</button>
          </div>
        </DialogShell>
      )}
    </div>
  );
}
