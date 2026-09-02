import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  Archive,
  Brain,
  Database,
  FolderKanban,
  LifeBuoy,
  SearchCheck,
  Waypoints,
} from 'lucide-react';
import { HomeMemoryDialog } from '@/components/HomeMemoryDialog';
import { useDashboardStore } from '@/store';
import type { MemoryNode, RecoveryHealth, Tab } from '@/types';

function needsReview(memory: MemoryNode): boolean {
  const health = String(memory.properties?.health_status || '').toLowerCase();
  const status = String(memory.properties?.status || '').toLowerCase();
  return Boolean(
    (health && health !== 'healthy')
      || memory.properties?.archived
      || memory.properties?.deprecated
      || ['contradictory', 'redundant', 'superseded'].includes(status),
  );
}

function humanState(value: string): string {
  return value
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/^./, (letter) => letter.toUpperCase());
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
      <strong className="mt-2 block text-sm font-medium text-slate-100">{value}</strong>
      <span className="mt-1 block text-[10px] leading-relaxed text-slate-500">{detail}</span>
    </div>
  );
}

function JobLane({
  eyebrow,
  title,
  description,
  status,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  status: string;
  children: React.ReactNode;
}) {
  return (
    <article className="flex min-h-[230px] flex-col border border-slate-800 bg-slate-950/55 p-5">
      <div className="text-[9px] text-cyan-400 elefante-mono uppercase tracking-[0.15em]">{eyebrow}</div>
      <h3 className="mt-2 text-lg font-medium text-slate-100">{title}</h3>
      <p className="mt-2 flex-1 text-xs leading-relaxed text-slate-500">{description}</p>
      <div className="mt-4 border-l-2 border-slate-700 pl-3 text-[10px] leading-relaxed text-slate-400">{status}</div>
      <div className="mt-4 flex flex-wrap gap-2">{children}</div>
    </article>
  );
}

const laneButton = 'min-h-10 border border-slate-700 px-3 text-[10px] text-slate-200 hover:border-cyan-400/60 hover:text-white';

export function HomeStatePanel() {
  const snapshot = useDashboardStore((state) => state.snapshot);
  const controlEnabled = useDashboardStore((state) => state.controlEnabled);
  const controlConnecting = useDashboardStore((state) => state.controlConnecting);
  const controlToken = useDashboardStore((state) => state.controlToken);
  const activeProjectId = useDashboardStore((state) => state.activeProjectId);
  const registry = useDashboardStore((state) => state.projectRegistry);
  const requestRecoveryPlan = useDashboardStore((state) => state.requestRecoveryPlan);
  const setActiveTab = useDashboardStore((state) => state.setActiveTab);
  const setMemoryWorkspaceView = useDashboardStore((state) => state.setMemoryWorkspaceView);
  const [health, setHealth] = useState<RecoveryHealth | null>(null);
  const [memoryDialog, setMemoryDialog] = useState<'remember' | null>(null);
  const checkedToken = useRef<string | null>(null);

  const memories = useMemo(
    () => (snapshot?.nodes ?? []).filter((node): node is MemoryNode => node.type === 'memory'),
    [snapshot],
  );
  const reviewCount = useMemo(() => memories.filter(needsReview).length, [memories]);
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
  const projectReady = Boolean(
    controlEnabled
      && registry?.status === 'ready'
      && registry.mode === 'strict'
      && activeProject
      && activeProject.project_id === activeProjectId,
  );

  const checkHealth = useCallback(async () => {
    if (!controlEnabled) return;
    const result = await requestRecoveryPlan('health');
    setHealth(result.success && result.health ? result.health : null);
  }, [controlEnabled, requestRecoveryPlan]);

  useEffect(() => {
    if (!controlEnabled || !controlToken || checkedToken.current === controlToken) return;
    checkedToken.current = controlToken;
    void checkHealth();
  }, [checkHealth, controlEnabled, controlToken]);

  const contextLabel = snapshot?.snapshot_context?.mode === 'showcase'
    ? 'Example workspace'
    : 'Local memory snapshot';
  const operationalLabel = controlEnabled
    ? 'Controls connected'
    : controlConnecting
      ? 'Checking operational session'
      : 'No operational receipt in this environment';
  const projectLabel = activeProject?.name || 'Not needed for global inspection';
  const recoveryLabel = health ? humanState(health.state) : 'Not checked';

  let nextAction: {
    label: string;
    reason: string;
    tab: Tab;
    memoryView?: 'library' | 'review';
  } = {
    label: 'Browse Memory Intelligence',
    reason: 'Start with the complete memory inventory and its direct review signals.',
    tab: 'memories',
    memoryView: 'library',
  };
  if (reviewCount > 0) {
    nextAction = {
      label: `Review ${reviewCount} direct signal${reviewCount === 1 ? '' : 's'}`,
      reason: 'Inspection is warranted; correction is not implied.',
      tab: 'memories',
      memoryView: 'review',
    };
  } else if (controlEnabled && !projectReady) {
    nextAction = {
      label: 'Set the task boundary',
      reason: 'Global inspection works now. A project is required only for task-scoped Recall and changes.',
      tab: 'projects',
    };
  } else if (projectReady) {
    nextAction = {
      label: 'Test Recall for one task',
      reason: 'Inspect exactly which governed memories Elefante selects before trusting task guidance.',
      tab: 'recall',
    };
  }

  const openMemoryWorkspace = (view: 'library' | 'review') => {
    setMemoryWorkspaceView(view);
    setActiveTab('memories');
  };

  const continueToNext = () => {
    if (nextAction.memoryView) {
      setMemoryWorkspaceView(nextAction.memoryView);
    }
    setActiveTab(nextAction.tab);
  };

  return (
    <section className="elefante-panel border-t-2 border-t-cyan-400/60 px-5 py-5 md:px-7 md:py-6" aria-labelledby="elefante-purpose-title">
      <div className="grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
        <div>
          <div className="text-[10px] text-cyan-400 elefante-mono uppercase tracking-[0.2em]">Elefante control room</div>
          <h1 id="elefante-purpose-title" className="mt-3 text-[clamp(2rem,4vw,3.5rem)] font-medium leading-[1.02] tracking-[-0.045em] text-slate-100">
            Make memory useful for the next task.
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-slate-400">
            Elefante selects governed decisions, constraints, preferences, facts, and lessons for the task at hand. This dashboard lets advanced users understand, improve, and protect that memory system.
          </p>
          <div className="mt-4 flex flex-wrap gap-2 text-[9px] elefante-mono uppercase tracking-[0.12em]">
            <span className="border border-cyan-400/35 px-2.5 py-1.5 text-cyan-200">{contextLabel}</span>
            <span className={`border px-2.5 py-1.5 ${controlEnabled ? 'border-emerald-400/35 text-emerald-300' : 'border-slate-700 text-slate-500'}`}>
              {operationalLabel}
            </span>
          </div>
        </div>

        <aside className="border border-cyan-400/35 bg-cyan-950/10 p-5">
          <div className="text-[9px] text-cyan-300 elefante-mono uppercase tracking-[0.14em]">Recommended next</div>
          <strong className="mt-2 block text-lg font-medium text-slate-100">{nextAction.label}</strong>
          <p className="mt-2 text-xs leading-relaxed text-slate-500">{nextAction.reason}</p>
          <button type="button" onClick={continueToNext} className="mt-4 min-h-11 border border-cyan-300/60 px-4 text-xs text-cyan-100 hover:bg-cyan-300/10">
            Continue
          </button>
        </aside>
      </div>

      <div className="mt-6 text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.15em]">Current evidence</div>
      <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <EvidenceCell label="Memory corpus" value={`${memories.length} memories`} detail="Directly represented in this snapshot" icon={<Database size={13} aria-hidden="true" />} />
        <EvidenceCell label="Review queue" value={`${reviewCount} direct signals`} detail="Health or lifecycle evidence; not a truth grade" icon={<Activity size={13} aria-hidden="true" />} />
        <EvidenceCell label="Task boundary" value={projectLabel} detail="Required for task-scoped Recall and changes—not global inspection" icon={<FolderKanban size={13} aria-hidden="true" />} />
        <EvidenceCell label="Recovery evidence" value={recoveryLabel} detail={health ? `Checked ${health.checked_at}` : 'Run Recover before making a readiness claim'} icon={<Archive size={13} aria-hidden="true" />} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <JobLane
          eyebrow="1 · Global understanding"
          title="Understand the memory system"
          description="Inspect every represented memory, direct review signal, topic, stored vitality value, and explicit relationship. No project is required."
          status="Available from the current snapshot. Missing relationships and task relevance are never inferred."
        >
          <button type="button" onClick={() => openMemoryWorkspace('library')} className={laneButton}>Memory Intelligence</button>
          <button type="button" onClick={() => setActiveTab('explore')} className={laneButton}><Waypoints size={12} className="mr-1 inline" />Connections</button>
        </JobLane>

        <JobLane
          eyebrow="2 · Task intelligence"
          title="Improve what Elefante supplies"
          description="Remember durable guidance—never secrets or full transcripts. Test what Recall selects for one real task, then correct only when evidence justifies a change."
          status={projectReady
            ? `Ready for verified actions in ${activeProject?.name}.`
            : 'A live project context is required for receipts; the workflow and evidence contract remain inspectable.'}
        >
          {projectReady && (
            <button type="button" onClick={() => setMemoryDialog('remember')} className={laneButton}><Brain size={12} className="mr-1 inline" />Remember</button>
          )}
          <button type="button" onClick={() => setActiveTab('recall')} className={laneButton}><SearchCheck size={12} className="mr-1 inline" />Recall</button>
          <button type="button" onClick={() => openMemoryWorkspace('library')} className={laneButton}>Correct</button>
        </JobLane>

        <JobLane
          eyebrow="3 · Continuity"
          title="Protect and recover"
          description="Check product health, create verified backups, restore with rollback protection, and build a privacy-safe support report."
          status={health
            ? `Latest health receipt: ${humanState(health.state)}.`
            : 'No recovery evidence yet. Capability is not readiness until a check returns a receipt.'}
        >
          <button type="button" onClick={() => setActiveTab('recover')} className={laneButton}><LifeBuoy size={12} className="mr-1 inline" />Recover</button>
        </JobLane>
      </div>

      <details className="mt-5 border border-slate-800 bg-slate-950/45">
        <summary className="cursor-pointer px-4 py-3 text-xs font-medium text-slate-300 hover:text-white">Evidence standard for Remember, Recall, Correct, and Recover</summary>
        <div className="grid gap-4 border-t elefante-hairline p-4 md:grid-cols-4">
          {[
            ['Remember', 'Verified write receipt plus a clean Recall postcondition.'],
            ['Recall', 'Terminal status, project, selected IDs, conflicts, and verification time.'],
            ['Correct', 'Reviewed plan, terminal receipt, postconditions, and rollback result when needed.'],
            ['Recover', 'Timestamped health or verified backup / restore receipt.'],
          ].map(([title, description]) => (
            <div key={title} className="border-l-2 border-slate-700 pl-3">
              <strong className="block text-xs font-medium text-slate-200">{title}</strong>
              <span className="mt-1 block text-[10px] leading-relaxed text-slate-500">{description}</span>
            </div>
          ))}
        </div>
      </details>

      {memoryDialog && (
        <HomeMemoryDialog mode={memoryDialog} onClose={() => setMemoryDialog(null)} />
      )}
    </section>
  );
}
