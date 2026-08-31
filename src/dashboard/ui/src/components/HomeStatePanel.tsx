import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Archive,
  Bot,
  Brain,
  FolderKanban,
  LifeBuoy,
  Loader2,
  PencilLine,
  RefreshCw,
  SearchCheck,
  ShieldCheck,
} from 'lucide-react';
import { HomeMemoryDialog } from '@/components/HomeMemoryDialog';
import { useDashboardStore } from '@/store';
import type { RecoveryHealth, RecoveryHealthState, Tab } from '@/types';

type HomeState = RecoveryHealthState | 'SETUP_REQUIRED' | 'CHECKING';

const STATE_LABELS: Record<HomeState, string> = {
  READY: 'Ready',
  SETUP_REQUIRED: 'Setup required',
  NEEDS_ATTENTION: 'Needs attention',
  RECOVERY_REQUIRED: 'Recovery required',
  UNSUPPORTED: 'Unsupported',
  CHECKING: 'Checking',
};

const NEXT_ACTION_LABELS: Record<string, string> = {
  none: 'No action needed',
  back_up_now: 'Back up now',
  repair: 'Repair Elefante',
  restore: 'Restore a verified backup',
  create_support_report: 'Create a support report',
  use_supported_setup: 'Use the supported setup',
};

function formatEvidenceTime(value: string | null | undefined): string {
  if (!value) return 'Not verified';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Verified';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function stateTone(state: HomeState): string {
  if (state === 'READY') return 'border-emerald-400/50 text-emerald-300';
  if (state === 'RECOVERY_REQUIRED') return 'border-red-400/60 text-red-300';
  if (state === 'UNSUPPORTED') return 'border-red-300/50 text-red-200';
  if (state === 'CHECKING') return 'border-cyan-400/50 text-cyan-300';
  return 'border-amber-300/50 text-amber-200';
}

function EvidenceCell({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="min-w-0 border border-slate-800 bg-slate-950/65 p-3.5">
      <div className="flex items-center gap-2 text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.12em]">
        {icon}
        <span>{label}</span>
      </div>
      <strong className="mt-2 block truncate text-sm font-medium text-slate-100" title={value}>{value}</strong>
      <span className="mt-1 block truncate text-[10px] text-slate-500" title={detail}>{detail}</span>
    </div>
  );
}

function ActionEntry({
  title,
  description,
  buttonLabel,
  icon,
  busy = false,
  onClick,
}: {
  title: string;
  description: string;
  buttonLabel: string;
  icon: React.ReactNode;
  busy?: boolean;
  onClick: () => void;
}) {
  return (
    <article className="flex min-h-[172px] flex-col border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-center gap-2 text-cyan-300">
        {icon}
        <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
      </div>
      <p className="mt-3 flex-1 text-[11px] leading-relaxed text-slate-500">{description}</p>
      <button
        type="button"
        onClick={onClick}
        disabled={busy}
        className="mt-4 inline-flex min-h-10 items-center justify-center gap-2 border border-slate-700 px-3 py-2 text-[10px] text-slate-300 transition-colors hover:border-cyan-400/60 hover:text-white disabled:cursor-wait disabled:opacity-60"
      >
        {busy && <Loader2 size={13} className="animate-spin" aria-hidden="true" />}
        {buttonLabel}
      </button>
    </article>
  );
}

export function HomeStatePanel() {
  const controlConnecting = useDashboardStore((state) => state.controlConnecting);
  const controlSessionError = useDashboardStore((state) => state.controlSessionError);
  const controlEnabled = useDashboardStore((state) => state.controlEnabled);
  const controlToken = useDashboardStore((state) => state.controlToken);
  const activeProjectId = useDashboardStore((state) => state.activeProjectId);
  const initializeControlSession = useDashboardStore((state) => state.initializeControlSession);
  const registry = useDashboardStore((state) => state.projectRegistry);
  const requestRecoveryPlan = useDashboardStore((state) => state.requestRecoveryPlan);
  const setActiveTab = useDashboardStore((state) => state.setActiveTab);
  const [health, setHealth] = useState<RecoveryHealth | null>(null);
  const [checking, setChecking] = useState(false);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [memoryDialog, setMemoryDialog] = useState<'remember' | 'recall' | null>(null);
  const checkedToken = useRef<string | null>(null);

  const activeProjects = useMemo(
    () => (registry?.projects ?? []).filter(
      (project) => project.active && project.root_status !== 'missing',
    ),
    [registry],
  );
  const activeProject = useMemo(() => {
    const bound = activeProjects.find((project) => project.project_id === activeProjectId);
    if (bound) return bound;
    return activeProjects.length === 1 ? activeProjects[0] : null;
  }, [activeProjectId, activeProjects]);

  const checkHealth = useCallback(async () => {
    if (!controlEnabled) {
      setHealth(null);
      setHealthError('The local Elefante service is unavailable. Reload Home or repair Elefante.');
      return;
    }
    setChecking(true);
    setHealthError(null);
    const result = await requestRecoveryPlan('health');
    if (result.success && result.health) {
      setHealth(result.health);
    } else {
      setHealth(null);
      setHealthError(result.error || 'Elefante could not verify the current product state.');
    }
    setChecking(false);
  }, [controlEnabled, requestRecoveryPlan]);

  useEffect(() => {
    if (!controlEnabled || !controlToken || checkedToken.current === controlToken) return;
    checkedToken.current = controlToken;
    void checkHealth();
  }, [checkHealth, controlEnabled, controlToken]);

  const projectBound = Boolean(
    activeProject
      && activeProjectId === activeProject.project_id,
  );
  const projectReady = Boolean(
    registry
      && registry.status === 'ready'
      && registry.mode === 'strict'
      && projectBound,
  );
  let productState: HomeState = 'CHECKING';
  let stateSummary = 'Elefante is checking the local runtime, agent, Recall path, project, and backup.';
  if (controlConnecting) {
    productState = 'CHECKING';
    stateSummary = 'Elefante is connecting this local Home page to the local service.';
  } else if (!controlEnabled) {
    productState = 'NEEDS_ATTENTION';
    stateSummary = controlSessionError
      || 'The local snapshot is available, but the Elefante service is not responding.';
  } else if (
    registry?.status === 'ready'
    && registry.mode === 'strict'
    && activeProjects.length > 0
    && !projectBound
  ) {
    productState = 'NEEDS_ATTENTION';
    stateSummary = activeProjects.length === 1
      ? `Continue with ${activeProjects[0].name} for this Home session.`
      : 'Choose the active project for this Home session.';
  } else if (!projectReady) {
    productState = 'SETUP_REQUIRED';
    stateSummary = registry?.mode === 'compatibility'
      ? 'Your existing memory is safe. Open Projects to choose the project boundary and review older unassigned memories before enabling isolation.'
      : activeProjects.length > 1
        ? 'Open Home from the active agent workspace so Elefante can identify one project.'
        : 'Register and activate one project before Remember or Recall.';
  } else if (health) {
    productState = health.state;
    stateSummary = health.summary;
  } else if (healthError) {
    productState = 'NEEDS_ATTENTION';
    stateSummary = healthError;
  }

  const agentLabel = health?.connected_agents.length
    ? health.connected_agents.join(', ')
    : 'Not verified';
  const recallCheck = health?.checks.find((check) => check.name === 'recall_path');
  const recallLabel = recallCheck?.passed ? 'Verified' : 'Not verified';
  const projectLabel = activeProject?.name ?? 'Not resolved';
  const projectDetail = activeProject
    ? activeProjectId === activeProject.project_id
      ? 'Bound to this Home session'
      : 'Registered; choose for this Home session'
    : activeProjects.length > 1
      ? `${activeProjects.length} active projects; current context required`
      : 'Project setup required';

  const showProjectChooser = Boolean(
    controlEnabled
      && registry?.status === 'ready'
      && registry.mode === 'strict'
      && activeProjects.length > 0
      && !projectBound,
  );
  const showProjectSetupGuide = productState === 'SETUP_REQUIRED' && controlEnabled;

  let nextActionLabel = showProjectChooser
    ? 'Choose project'
    : controlEnabled
      ? 'Open Projects'
      : 'Reload Home';
  let nextActionTab: Tab = 'projects';
  if (projectReady && health && health.next_action !== 'none') {
    nextActionLabel = NEXT_ACTION_LABELS[health.next_action]
      || health.next_action.replace(/_/g, ' ');
    nextActionTab = 'recover';
  }
  const showNextAction = productState !== 'READY' && productState !== 'CHECKING';

  return (
    <section className="elefante-panel border-t-2 border-t-cyan-400/60 px-5 py-5 md:px-7 md:py-6" aria-labelledby="home-state-title">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="max-w-3xl">
          <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.2em]">Elefante Home</div>
          <div className="mt-3 flex items-center gap-3">
            {productState === 'READY'
              ? <ShieldCheck size={25} className="shrink-0 text-emerald-300" aria-hidden="true" />
              : productState === 'CHECKING'
                ? <Loader2 size={25} className="shrink-0 animate-spin text-cyan-300" aria-hidden="true" />
                : <AlertTriangle size={25} className="shrink-0 text-amber-200" aria-hidden="true" />}
            <div>
              <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.13em]">Current product state</div>
              <h1 id="home-state-title" className="mt-1 text-3xl font-medium tracking-[-0.035em] text-slate-100">
                {STATE_LABELS[productState]}
              </h1>
            </div>
          </div>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-400" aria-live="polite">{stateSummary}</p>
        </div>

        <div className={`w-full border bg-slate-950/70 p-4 xl:max-w-sm ${stateTone(productState)}`}>
          <div className="text-[9px] elefante-mono uppercase tracking-[0.14em]">
            {showNextAction ? 'One safe next action' : 'Readiness'}
          </div>
          <strong className="mt-2 block text-sm text-slate-100">
            {showNextAction ? nextActionLabel : productState === 'READY' ? 'No action needed' : 'Verification in progress'}
          </strong>
          {showNextAction && controlEnabled && !showProjectChooser && (
            <button
              type="button"
              onClick={() => setActiveTab(nextActionTab)}
              className="mt-4 min-h-11 border border-current px-4 py-2 text-xs hover:bg-white/5"
            >
              {nextActionLabel}
            </button>
          )}
          {showNextAction && showProjectChooser && (
            <p className="mt-3 text-[10px] leading-relaxed text-slate-500">Select one of your active projects below.</p>
          )}
          {showNextAction && !controlEnabled && !controlConnecting && (
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-4 min-h-11 border border-current px-4 py-2 text-xs hover:bg-white/5"
            >
              Reload Home
            </button>
          )}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <EvidenceCell
          label="Connected agent"
          value={agentLabel}
          detail={health ? `Checked ${formatEvidenceTime(health.checked_at)}` : 'Awaiting local health proof'}
          icon={<Bot size={13} aria-hidden="true" />}
        />
        <EvidenceCell
          label="Active project"
          value={projectLabel}
          detail={projectDetail}
          icon={<FolderKanban size={13} aria-hidden="true" />}
        />
        <EvidenceCell
          label="Last verified Recall"
          value={recallLabel}
          detail={formatEvidenceTime(health?.recall_verified_at)}
          icon={<SearchCheck size={13} aria-hidden="true" />}
        />
        <EvidenceCell
          label="Last verified backup"
          value={health?.valid_backups ? `${health.valid_backups} available` : 'Not verified'}
          detail={formatEvidenceTime(health?.latest_verified_backup_at)}
          icon={<Archive size={13} aria-hidden="true" />}
        />
      </div>

      {showProjectChooser && (
        <section
          className="mt-6 border border-cyan-400/35 bg-slate-950/45 p-5"
          aria-labelledby="project-choice-title"
        >
          <p className="text-[9px] text-cyan-400 elefante-mono uppercase tracking-[0.18em]">Current context</p>
          <h2 id="project-choice-title" className="mt-2 text-xl font-semibold text-slate-100">
            Choose the project for this Home session.
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            Home will bind Remember, Recall, Correct, and Recover to one active registered project. No project files are scanned or changed.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            {activeProjects.map((project) => (
              <button
                key={project.project_id}
                type="button"
                disabled={controlConnecting}
                onClick={() => void initializeControlSession(project.project_id)}
                className="min-h-11 border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:border-cyan-400/60 hover:text-white disabled:cursor-wait disabled:opacity-60"
              >
                {project.name}
              </button>
            ))}
          </div>
        </section>
      )}

      {showProjectSetupGuide && (
        <section
          className="mt-6 border border-cyan-400/35 bg-slate-950/45 p-5"
          aria-labelledby="first-run-guide-title"
        >
          <p className="text-[9px] text-cyan-400 elefante-mono uppercase tracking-[0.18em]">First run</p>
          <h2 id="first-run-guide-title" className="mt-2 text-xl font-semibold text-slate-100">
            Set the boundary before adding memory.
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            Elefante does not ingest every session by default. Choose the folders that define each body of work, keep only durable governed knowledge, then verify Recall and backup.
          </p>
          <div className="mt-5 grid gap-4 lg:grid-cols-3">
            <div className="border border-slate-800 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-400">1. Choose folders</p>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Register specific project folders—not your home, the Documents folder itself, or Elefante&apos;s data folder. Elefante uses the folder as scope and does not scan its files.
              </p>
              <button
                type="button"
                className="mt-4 inline-flex min-h-10 items-center justify-center border border-slate-700 px-3 py-2 text-[10px] text-slate-300 transition-colors hover:border-cyan-400/60 hover:text-white"
                onClick={() => setActiveTab('projects')}
              >
                Open Projects
              </button>
            </div>
            <div className="border border-slate-800 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-400">2. Choose memories</p>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Remember decisions, constraints, preferences, facts, and lessons. Never store passwords, API keys, access tokens, hidden reasoning, or full transcripts as durable memories.
              </p>
            </div>
            <div className="border border-slate-800 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-400">3. Verify continuity</p>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                Remember one real decision, test it in a later project question, and keep a verified backup before treating setup as complete.
              </p>
              <button
                type="button"
                className="mt-4 inline-flex min-h-10 items-center justify-center border border-slate-700 px-3 py-2 text-[10px] text-slate-300 transition-colors hover:border-cyan-400/60 hover:text-white"
                onClick={() => setActiveTab('recover')}
              >
                Open Recover
              </button>
            </div>
          </div>
        </section>
      )}

      <div className="mt-7">
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.15em]">Four customer actions</div>
            <h2 className="mt-2 text-lg font-medium text-slate-100">Continue without operating the engine.</h2>
          </div>
          <button
            type="button"
            onClick={() => void checkHealth()}
            disabled={checking || !controlEnabled}
            aria-label="Refresh product state"
            className="inline-flex min-h-10 items-center gap-2 border border-slate-700 px-3 py-2 text-[10px] text-slate-400 hover:border-cyan-400/60 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <RefreshCw size={13} className={checking ? 'animate-spin' : ''} aria-hidden="true" />
            Refresh state
          </button>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <ActionEntry
            title="Remember"
            description="Preserve one decision, constraint, preference, or lesson for the active project. Use Home when the agent is unavailable."
            buttonLabel="Remember here"
            icon={<Brain size={17} aria-hidden="true" />}
            onClick={() => setMemoryDialog('remember')}
          />
          <ActionEntry
            title="Test Recall"
            description="Ask one real project question and prove which governed memories Recall selects without returning their content to Home."
            buttonLabel="Ask a Recall question"
            icon={<SearchCheck size={17} aria-hidden="true" />}
            onClick={() => setMemoryDialog('recall')}
          />
          <ActionEntry
            title="Correct"
            description="Inspect, edit, replace, resolve, archive, restore, or permanently delete governed knowledge."
            buttonLabel="Open memories"
            icon={<PencilLine size={17} aria-hidden="true" />}
            onClick={() => setActiveTab('memories')}
          />
          <ActionEntry
            title="Recover"
            description="Check health, create or restore a verified backup, and make a privacy-safe support report."
            buttonLabel="Open Recover"
            icon={<LifeBuoy size={17} aria-hidden="true" />}
            onClick={() => setActiveTab('recover')}
          />
        </div>

      </div>
      {memoryDialog && (
        <HomeMemoryDialog
          mode={memoryDialog}
          onClose={() => setMemoryDialog(null)}
        />
      )}
    </section>
  );
}
