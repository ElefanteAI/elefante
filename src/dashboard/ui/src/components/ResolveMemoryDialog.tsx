import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Loader2,
  LockKeyhole,
  RotateCcw,
  X,
} from 'lucide-react';
import { useDashboardStore } from '@/store';
import type {
  MemoryNode,
  ResolveApplyResponse,
  ResolvePlan,
  ResolveTerminalStatus,
} from '@/types';

interface ResolveMemoryDialogProps {
  memory: MemoryNode;
  conflictMemories: MemoryNode[];
}

const STATUS_COPY: Record<ResolveTerminalStatus, {
  label: string;
  detail: string;
  classes: string;
}> = {
  VERIFIED_COMPLETE: {
    label: 'Verified complete',
    detail: 'The correction was applied and the postconditions were verified.',
    classes: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200',
  },
  FAILED_NO_CHANGE: {
    label: 'Failed — no change',
    detail: 'No state change was verified by the control service.',
    classes: 'border-amber-500/40 bg-amber-500/10 text-amber-200',
  },
  FAILED_ROLLED_BACK: {
    label: 'Failed — rolled back',
    detail: 'The prior state was restored after the correction could not complete.',
    classes: 'border-amber-500/40 bg-amber-500/10 text-amber-200',
  },
  NEEDS_HUMAN: {
    label: 'Needs human review',
    detail: 'Inspect the receipt and re-plan before trying again.',
    classes: 'border-amber-500/40 bg-amber-500/10 text-amber-200',
  },
  UNSAFE: {
    label: 'Recovery required',
    detail: 'The operation is unsafe to retry automatically.',
    classes: 'border-red-500/50 bg-red-500/10 text-red-200',
  },
};

function memoryTitle(memory: MemoryNode): string {
  return String(
    memory.properties?.title ||
      memory.properties?.summary ||
      memory.name ||
      `Memory ${memory.id.slice(0, 8)}`,
  );
}

function memoryPreview(memory: MemoryNode): string {
  const content = String(memory.properties?.content || memory.description || '');
  return content.length > 150 ? `${content.slice(0, 150)}…` : content;
}

function formatPlanValue(value: string | null | undefined): string {
  if (!value) return 'Not supplied';
  return value.replace(/[_-]/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function isProtected(memory: MemoryNode | undefined): boolean {
  return Boolean(
    memory?.properties?.user_locked === true ||
      String(memory?.properties?.retention_policy || '').toLowerCase() === 'permanent',
  );
}

function protectedReasons(memory: MemoryNode | undefined): string[] {
  if (!memory) return [];
  const reasons: string[] = [];
  if (memory.properties?.user_locked === true) reasons.push('user locked');
  if (String(memory.properties?.retention_policy || '').toLowerCase() === 'permanent') {
    reasons.push('permanent retention');
  }
  return reasons;
}

function ResolveReceipt({ response }: { response: ResolveApplyResponse }) {
  const status = response.resolution_status;
  const receipt = response.receipt;
  if (!status) return null;
  const statusCopy = STATUS_COPY[status];

  return (
    <div className="space-y-3" aria-live="assertive">
      <div className={`rounded-lg border px-4 py-3 ${statusCopy.classes}`}>
        <div className="flex items-start gap-2">
          {status === 'VERIFIED_COMPLETE' ? <CheckCircle2 size={18} className="mt-0.5 flex-shrink-0" /> : <AlertTriangle size={18} className="mt-0.5 flex-shrink-0" />}
          <div>
            <div className="text-sm font-semibold">{statusCopy.label}</div>
            <p className="mt-1 text-xs leading-relaxed opacity-90">{statusCopy.detail}</p>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-slate-700/60 bg-slate-950/40 px-4 py-3">
        <div className="text-[10px] uppercase tracking-widest text-slate-500">Terminal receipt</div>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <ReceiptValue label="Status" value={status} />
          <ReceiptValue label="Changed" value={receipt?.changed === undefined ? 'Not reported' : receipt.changed ? 'Yes' : 'No'} />
          <ReceiptValue label="Rollback" value={receipt?.rollback || 'Not reported'} />
          <ReceiptValue label="Operation" value={receipt?.operation_id || 'Not reported'} mono />
        </div>
        {receipt?.error_codes && receipt.error_codes.length > 0 && (
          <div className="mt-3 border-t border-slate-800/80 pt-2 text-xs">
            <span className="text-slate-500">Codes: </span>
            <span className="text-slate-300">{receipt.error_codes.join(', ')}</span>
          </div>
        )}
        {receipt?.checks && receipt.checks.length > 0 && (
          <div className="mt-3 space-y-1 border-t border-slate-800/80 pt-2">
            <div className="text-[10px] uppercase tracking-widest text-slate-500">Verification checks</div>
            {receipt.checks.map((check, index) => (
              <div key={`${check.name}-${index}`} className="flex items-center justify-between gap-3 text-xs">
                <span className="truncate text-slate-400">{check.name}</span>
                <span className={check.passed ? 'text-emerald-300' : 'text-red-300'}>{check.passed ? 'passed' : 'failed'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ReceiptValue({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="text-slate-600">{label}</div>
      <div className={`truncate text-slate-300 ${mono ? 'elefante-mono text-[10px]' : ''}`}>{value}</div>
    </div>
  );
}

export function ResolveMemoryDialog({ memory, conflictMemories }: ResolveMemoryDialogProps) {
  const controlEnabled = useDashboardStore((state) => state.controlEnabled);
  const requestResolvePlan = useDashboardStore((state) => state.requestResolvePlan);
  const applyResolvePlan = useDashboardStore((state) => state.applyResolvePlan);
  const refreshSnapshot = useDashboardStore((state) => state.refreshSnapshot);
  const isResolvePlanning = useDashboardStore((state) => state.isResolvePlanning);
  const isResolveApplying = useDashboardStore((state) => state.isResolveApplying);
  const resolveError = useDashboardStore((state) => state.resolveError);
  const clearResolveError = useDashboardStore((state) => state.clearResolveError);

  const [isOpen, setIsOpen] = useState(false);
  const [peerId, setPeerId] = useState('');
  const [winnerId, setWinnerId] = useState('');
  const [reason, setReason] = useState('');
  const [verificationQuestion, setVerificationQuestion] = useState('');
  const [protectedConfirmed, setProtectedConfirmed] = useState(false);
  const [plan, setPlan] = useState<ResolvePlan | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [applyResponse, setApplyResponse] = useState<ResolveApplyResponse | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const peerSelectRef = useRef<HTMLSelectElement>(null);

  const selectedPeer = conflictMemories.find((candidate) => candidate.id === peerId);
  const losingMemory = winnerId
    ? winnerId === memory.id
      ? selectedPeer
      : memory
    : undefined;
  const losingMemoryIsProtected = isProtected(losingMemory);
  const canRequestPlan = Boolean(
    peerId &&
      selectedPeer &&
      winnerId &&
      (winnerId === memory.id || winnerId === selectedPeer.id) &&
      reason.trim() &&
      verificationQuestion.trim() &&
      (!losingMemoryIsProtected || protectedConfirmed),
  );

  useEffect(() => {
    if (!isOpen) return;
    setPeerId('');
    setWinnerId('');
    setReason('');
    setVerificationQuestion('');
    setProtectedConfirmed(false);
    setPlan(null);
    setPlanId(null);
    setApplyResponse(null);
    setLocalError(null);
    clearResolveError();
    window.requestAnimationFrame(() => peerSelectRef.current?.focus());
  }, [clearResolveError, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        setIsOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown, true);
    return () => document.removeEventListener('keydown', handleKeyDown, true);
  }, [isOpen]);

  if (conflictMemories.length === 0) return null;

  const openDialog = () => {
    setIsOpen(true);
  };

  const handlePlan = async (event: React.FormEvent) => {
    event.preventDefault();
    setLocalError(null);
    if (!peerId || !selectedPeer) {
      setLocalError('Choose the conflict peer to inspect.');
      return;
    }
    if (!winnerId) {
      setLocalError('Choose the authoritative winner.');
      return;
    }
    if (!reason.trim()) {
      setLocalError('Enter a short audit reason.');
      return;
    }
    if (!verificationQuestion.trim()) {
      setLocalError('Enter a likely future Recall question.');
      return;
    }
    if (losingMemoryIsProtected && !protectedConfirmed) {
      setLocalError('Confirm the protected losing memory before requesting a plan.');
      return;
    }

    const response = await requestResolvePlan(
      memory.id,
      selectedPeer.id,
      winnerId,
      losingMemoryIsProtected && protectedConfirmed,
    );
    if (!response.success || !response.plan) {
      setLocalError(response.error || resolveError || 'The correction plan could not be created.');
      return;
    }
    setPlan(response.plan);
    setPlanId(response.plan_id);
    setApplyResponse(null);
    setLocalError(null);
  };

  const handleApply = async () => {
    if (!planId || !plan?.applicable) return;
    setLocalError(null);
    const response = await applyResolvePlan(planId, reason.trim(), verificationQuestion.trim());
    if (!response.resolution_status) {
      setLocalError(response.error || resolveError || 'The control service returned no terminal result.');
      return;
    }
    setApplyResponse(response);
  };

  const closeDialog = () => setIsOpen(false);
  const resolution = plan?.resolution;
  const winner = resolution?.winner_memory_id === memory.id
    ? memory
    : resolution?.winner_memory_id === selectedPeer?.id
      ? selectedPeer
      : undefined;
  const loser = resolution?.loser_memory_id === memory.id
    ? memory
    : resolution?.loser_memory_id === selectedPeer?.id
      ? selectedPeer
      : undefined;

  return (
    <>
      <div className="mt-4 rounded-lg border border-amber-500/25 bg-amber-500/5 px-3 py-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-amber-200">Verified Resolve</div>
            <p className="mt-1 text-xs leading-relaxed text-slate-400">
              Inspect the conflict, choose authority, and review a no-write plan before any correction.
            </p>
          </div>
          <LockKeyhole size={15} className="mt-0.5 flex-shrink-0 text-amber-300" aria-hidden="true" />
        </div>
        {controlEnabled ? (
          <button
            type="button"
            onClick={openDialog}
            className="mt-3 inline-flex items-center gap-2 rounded-md border border-amber-400/35 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-100 transition-colors hover:bg-amber-500/20"
          >
            Open correction flow
            <ArrowRight size={13} />
          </button>
        ) : (
          <div className="mt-2 text-[11px] text-slate-500">Read-only mode — reopen this dashboard through Elefante to manage conflicts.</div>
        )}
      </div>

      {isOpen && typeof document !== 'undefined' && createPortal((
        <div
          className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeDialog();
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="resolve-dialog-title"
            className="flex max-h-[92vh] w-full max-w-xl flex-col overflow-hidden rounded-xl border border-amber-500/30 bg-slate-950 shadow-2xl"
          >
            <div className="flex items-start justify-between gap-3 border-b border-slate-700/70 bg-slate-900/95 px-5 py-4">
              <div>
                <div className="text-[10px] uppercase tracking-[0.2em] text-amber-300">Home Verified Resolve</div>
                <h3 id="resolve-dialog-title" className="mt-1 text-base font-semibold text-slate-100">Correct one conflict</h3>
                <p className="mt-1 text-xs text-slate-500">No memory is changed until you confirm the inspected plan.</p>
              </div>
              <button
                type="button"
                onClick={closeDialog}
                className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
                aria-label="Close correction flow"
              >
                <X size={18} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-4">
              {applyResponse ? (
                <div className="space-y-3">
                  <ResolveReceipt response={applyResponse} />
                  {applyResponse.resolution_status === 'VERIFIED_COMPLETE' ||
                  applyResponse.resolution_status === 'FAILED_ROLLED_BACK' ? (
                    <button
                      type="button"
                      onClick={() => {
                        setIsOpen(false);
                        void refreshSnapshot();
                      }}
                      className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-slate-600 bg-slate-800/80 px-3 py-2.5 text-xs font-semibold text-slate-100 transition-colors hover:bg-slate-700"
                    >
                      <RotateCcw size={13} />
                      Close and reload snapshot
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={closeDialog}
                      className="inline-flex w-full items-center justify-center rounded-md border border-slate-700 bg-slate-900 px-3 py-2.5 text-xs font-semibold text-slate-200 transition-colors hover:bg-slate-800"
                    >
                      Close receipt
                    </button>
                  )}
                </div>
              ) : plan ? (
                <div className="space-y-4">
                  <div className="rounded-lg border border-cyan-500/25 bg-cyan-500/5 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-xs font-semibold uppercase tracking-wider text-cyan-200">Inspect impact</div>
                      <span className={`rounded px-2 py-0.5 text-[10px] uppercase tracking-wider ${plan.applicable ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}>
                        {plan.applicable ? 'Plan ready' : 'Blocked'}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-slate-300">{plan.reason}</p>
                    {plan.reason_code && (
                      <div className="mt-2 text-[10px] uppercase tracking-wider text-slate-500">Reason code: {formatPlanValue(plan.reason_code)}</div>
                    )}
                  </div>

                  <div className="rounded-lg border border-slate-700/60 bg-slate-900/60 px-4 py-3">
                    <div className="text-[10px] uppercase tracking-widest text-slate-500">Proposed impact</div>
                    <div className="mt-3 space-y-2 text-xs">
                      <ImpactRow label="Action" value={formatPlanValue(resolution?.action)} />
                      <ImpactRow label="Authoritative winner" value={winner ? memoryTitle(winner) : formatPlanValue(resolution?.winner_memory_id)} />
                      <ImpactRow label="Losing memory" value={loser ? memoryTitle(loser) : formatPlanValue(resolution?.loser_memory_id)} />
                      <ImpactRow label="Assessment" value={formatPlanValue(resolution?.assessment)} />
                    </div>
                  </div>

                  {plan.applicable && planId ? (
                    <div className="rounded-lg border border-amber-500/35 bg-amber-500/5 px-4 py-3">
                      <div className="text-sm font-semibold text-amber-100">Confirm correction</div>
                      <p className="mt-1 text-xs leading-relaxed text-slate-400">
                        This is the explicit final step. The selected plan ticket is single-use.
                      </p>
                      <button
                        type="button"
                        onClick={handleApply}
                        disabled={isResolveApplying}
                        aria-busy={isResolveApplying}
                        className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-md bg-amber-500/85 px-3 py-2.5 text-xs font-semibold text-slate-950 transition-colors hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {isResolveApplying ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                        {isResolveApplying ? 'Applying and verifying…' : 'Confirm & apply'}
                      </button>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-slate-700/60 bg-slate-900/50 px-4 py-3 text-xs text-slate-400">
                      No apply action is available for this plan. Return to the form to adjust the selected memories.
                    </div>
                  )}

                  {localError && <InlineError message={localError} />}

                  <button
                    type="button"
                    onClick={() => {
                      setPlan(null);
                      setPlanId(null);
                      setLocalError(null);
                    }}
                    disabled={isResolveApplying}
                    className="inline-flex items-center gap-2 text-xs text-slate-400 transition-colors hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <RotateCcw size={13} />
                    Edit and request a new plan
                  </button>
                </div>
              ) : (
                <form onSubmit={handlePlan} className="space-y-4">
                  <div>
                    <label htmlFor="resolve-peer" className="mb-1.5 block text-xs font-medium text-slate-300">Conflict peer</label>
                    <select
                      ref={peerSelectRef}
                      id="resolve-peer"
                      value={peerId}
                      onChange={(event) => {
                        setPeerId(event.target.value);
                        setWinnerId('');
                        setProtectedConfirmed(false);
                      }}
                      disabled={isResolvePlanning}
                      className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 focus:border-amber-400/60 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <option value="">Choose a memory…</option>
                      {conflictMemories.map((candidate) => (
                        <option key={candidate.id} value={candidate.id}>{memoryTitle(candidate)}</option>
                      ))}
                    </select>
                  </div>

                  <fieldset disabled={isResolvePlanning}>
                    <legend className="mb-2 text-xs font-medium text-slate-300">Authoritative winner</legend>
                    <div className="space-y-2">
                      {[memory, ...(selectedPeer ? [selectedPeer] : [])].map((candidate) => (
                        <label key={candidate.id} className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-3 transition-colors ${winnerId === candidate.id ? 'border-amber-400/50 bg-amber-500/10' : 'border-slate-700/60 bg-slate-900/50 hover:border-slate-600'}`}>
                          <input
                            type="radio"
                            name="resolve-winner"
                            value={candidate.id}
                            checked={winnerId === candidate.id}
                            onChange={(event) => {
                              setWinnerId(event.target.value);
                              setProtectedConfirmed(false);
                            }}
                            className="mt-1 accent-amber-400"
                          />
                          <span className="min-w-0">
                            <span className="block text-xs font-medium text-slate-200">{memoryTitle(candidate)}</span>
                            <span className="mt-1 block text-xs leading-relaxed text-slate-500">{memoryPreview(candidate) || 'No content preview'}</span>
                          </span>
                        </label>
                      ))}
                    </div>
                  </fieldset>

                  {losingMemoryIsProtected && (
                    <div className="rounded-lg border border-amber-500/45 bg-amber-500/10 px-3 py-3">
                      <div className="flex items-start gap-2">
                        <LockKeyhole size={15} className="mt-0.5 flex-shrink-0 text-amber-300" />
                        <div>
                          <div className="text-xs font-semibold text-amber-100">Protected losing memory</div>
                          <p className="mt-1 text-xs leading-relaxed text-slate-400">
                            The selected losing memory is {protectedReasons(losingMemory).join(' and ')}. Explicit confirmation is required before requesting a plan.
                          </p>
                        </div>
                      </div>
                      <label className="mt-3 flex cursor-pointer items-start gap-2 text-xs text-amber-100">
                        <input
                          type="checkbox"
                          checked={protectedConfirmed}
                          onChange={(event) => setProtectedConfirmed(event.target.checked)}
                          className="mt-0.5 accent-amber-400"
                        />
                        <span>I understand this correction may supersede a protected memory.</span>
                      </label>
                    </div>
                  )}

                  <div>
                    <label htmlFor="resolve-reason" className="mb-1.5 block text-xs font-medium text-slate-300">Audit reason</label>
                    <textarea
                      id="resolve-reason"
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                      maxLength={240}
                      rows={2}
                      disabled={isResolvePlanning}
                      placeholder="Why is this memory authoritative?"
                      className="w-full resize-y rounded-md border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:border-amber-400/60 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                    />
                    <div className="mt-1 text-right text-[10px] text-slate-600">{reason.length}/240</div>
                  </div>

                  <div>
                    <label htmlFor="resolve-question" className="mb-1.5 block text-xs font-medium text-slate-300">Likely future Recall question</label>
                    <textarea
                      id="resolve-question"
                      value={verificationQuestion}
                      onChange={(event) => setVerificationQuestion(event.target.value)}
                      maxLength={240}
                      rows={2}
                      disabled={isResolvePlanning}
                      placeholder="What might you ask later to verify this correction?"
                      className="w-full resize-y rounded-md border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:border-amber-400/60 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                    />
                    <div className="mt-1 text-right text-[10px] text-slate-600">{verificationQuestion.length}/240</div>
                  </div>

                  {(localError || resolveError) && <InlineError message={localError || resolveError || ''} />}

                  <button
                    type="submit"
                    disabled={isResolvePlanning || !canRequestPlan}
                    aria-busy={isResolvePlanning}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-amber-400/40 bg-amber-500/15 px-3 py-2.5 text-xs font-semibold text-amber-100 transition-colors hover:bg-amber-500/25 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    {isResolvePlanning ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
                    {isResolvePlanning ? 'Inspecting plan…' : 'Request plan'}
                  </button>
                </form>
              )}
            </div>

            {applyResponse && (
              <div className="flex items-center justify-between gap-3 border-t border-slate-700/70 bg-slate-900/70 px-5 py-3">
                <div className="text-[11px] text-slate-500">Terminal result is based on the returned resolution status.</div>
                <button
                  type="button"
                  onClick={closeDialog}
                  className="rounded-md border border-slate-600/70 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-slate-400 hover:text-white"
                >
                  Close
                </button>
              </div>
            )}
          </div>
        </div>
      ), document.body)}
    </>
  );
}

function ImpactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-800/60 pb-2 last:border-0 last:pb-0">
      <span className="text-slate-500">{label}</span>
      <span className="max-w-[68%] text-right text-slate-200">{value}</span>
    </div>
  );
}

function InlineError({ message }: { message: string }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-md border border-red-500/35 bg-red-500/10 px-3 py-2.5 text-xs leading-relaxed text-red-200">
      <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
      <span>{message}</span>
    </div>
  );
}
