import { createPortal } from 'react-dom';
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react';
import {
  Archive,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  LockKeyhole,
  Pencil,
  RotateCcw,
  Trash2,
  X,
} from 'lucide-react';
import type {
  CorrectionAction,
  CorrectionApplyResponse,
  CorrectionPlan,
  CorrectionTerminalStatus,
  MemoryNode,
} from '@/types';
import { useDashboardStore } from '@/store';

const FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[href]',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

const STATUS_COPY: Record<CorrectionTerminalStatus, {
  label: string;
  detail: string;
  classes: string;
}> = {
  VERIFIED_COMPLETE: {
    label: 'Verified complete',
    detail: 'The correction was applied and its memory, connections, Home snapshot, and scoped Recall were verified.',
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
    detail: 'Inspect the result and re-plan before trying this correction again.',
    classes: 'border-amber-500/40 bg-amber-500/10 text-amber-200',
  },
  UNSAFE: {
    label: 'Recovery required',
    detail: 'The operation is unsafe to retry automatically. Use the recovery path before making another change.',
    classes: 'border-red-500/50 bg-red-500/10 text-red-200',
  },
};

const ACTIONS: Array<{
  action: CorrectionAction;
  label: string;
  description: string;
  icon: ReactNode;
}> = [
  {
    action: 'edit',
    label: 'Edit',
    description: 'Fix a mistake without changing the meaning.',
    icon: <Pencil size={14} aria-hidden="true" />,
  },
  {
    action: 'replace',
    label: 'Replace',
    description: 'Record a newer version while preserving this history.',
    icon: <ArrowRight size={14} aria-hidden="true" />,
  },
  {
    action: 'archive',
    label: 'Archive',
    description: 'Keep it inspectable but stop it appearing in Recall.',
    icon: <Archive size={14} aria-hidden="true" />,
  },
  {
    action: 'restore',
    label: 'Restore',
    description: 'Make manually archived knowledge available to Recall again.',
    icon: <RotateCcw size={14} aria-hidden="true" />,
  },
  {
    action: 'permanent_delete',
    label: 'Delete permanently',
    description: 'Erase this memory and unshared attachments after a temporary safety backup.',
    icon: <Trash2 size={14} aria-hidden="true" />,
  },
];

function memoryTitle(memory: MemoryNode): string {
  return String(
    memory.properties?.title
      || memory.properties?.summary
      || memory.name
      || `Memory ${memory.id.slice(0, 8)}`,
  );
}

function formatAction(action: CorrectionAction | undefined): string {
  if (!action) return 'Correction';
  if (action === 'permanent_delete') return 'Delete permanently';
  return action.charAt(0).toUpperCase() + action.slice(1).replace(/_/g, ' ');
}

function isProtected(memory: MemoryNode): boolean {
  return Boolean(
    memory.properties?.user_locked === true
      || String(memory.properties?.retention_policy || '').toLowerCase() === 'permanent',
  );
}

function protectedReason(memory: MemoryNode): string {
  const reasons: string[] = [];
  if (memory.properties?.user_locked === true) reasons.push('user locked');
  if (String(memory.properties?.retention_policy || '').toLowerCase() === 'permanent') {
    reasons.push('permanent retention');
  }
  return reasons.join(' and ');
}

function isPlanStale(response: CorrectionApplyResponse): boolean {
  const code = String(response.error_code || '').toUpperCase();
  const receiptCodes = response.receipt?.error_codes || [];
  return code === 'PLAN_STALE'
    || code === 'CONTROL_PLAN_EXPIRED'
    || code === 'CONTROL_PLAN_NOT_FOUND'
    || receiptCodes.some((receiptCode) => {
      const normalized = String(receiptCode).toUpperCase();
      return normalized === 'PLAN_STALE'
        || normalized === 'CONTROL_PLAN_EXPIRED'
        || normalized === 'CONTROL_PLAN_NOT_FOUND';
    });
}

function actionDefinition(action: CorrectionAction | null): typeof ACTIONS[number] | undefined {
  return ACTIONS.find((candidate) => candidate.action === action);
}

function CorrectionReceipt({
  response,
  action,
}: {
  response: CorrectionApplyResponse;
  action: CorrectionAction;
}) {
  const status = response.correction_status;
  const receipt = response.receipt;
  if (!status) return null;
  const statusCopy = STATUS_COPY[status];

  return (
    <div className="space-y-3" aria-live="assertive">
      <div className={`rounded-lg border px-4 py-3 ${statusCopy.classes}`}>
        <div className="flex items-start gap-2">
          {status === 'VERIFIED_COMPLETE'
            ? <CheckCircle2 size={18} className="mt-0.5 flex-shrink-0" aria-hidden="true" />
            : <AlertTriangle size={18} className="mt-0.5 flex-shrink-0" aria-hidden="true" />}
          <div>
            <div className="text-sm font-semibold">{statusCopy.label}</div>
            <p className="mt-1 text-xs leading-relaxed opacity-90">{statusCopy.detail}</p>
          </div>
        </div>
      </div>

      {response.error && <InlineError message={response.error} />}

      <div className="rounded-lg border border-slate-700/60 bg-slate-950/40 px-4 py-3">
        <div className="text-[10px] uppercase tracking-widest text-slate-500">Correction receipt</div>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <ReceiptValue label="Action" value={formatAction(action)} />
          <ReceiptValue label="Result" value={statusCopy.label} />
          <ReceiptValue
            label="Changed"
            value={receipt?.changed === undefined ? 'Not reported' : receipt.changed ? 'Yes' : 'No'}
          />
          <ReceiptValue
            label="Recoverable"
            value={receipt?.recoverable === undefined ? 'Not reported' : receipt.recoverable ? 'Yes' : 'No'}
          />
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
                <span className={check.passed ? 'text-emerald-300' : 'text-red-300'}>
                  {check.passed ? 'passed' : 'failed'}
                </span>
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

export function CorrectionDialog({ memory }: { memory: MemoryNode }) {
  const controlEnabled = useDashboardStore((state) => state.controlEnabled);
  const requestCorrectionPlan = useDashboardStore((state) => state.requestCorrectionPlan);
  const applyCorrectionPlan = useDashboardStore((state) => state.applyCorrectionPlan);
  const refreshSnapshot = useDashboardStore((state) => state.refreshSnapshot);
  const isCorrectionPlanning = useDashboardStore((state) => state.isCorrectionPlanning);
  const isCorrectionApplying = useDashboardStore((state) => state.isCorrectionApplying);
  const correctionError = useDashboardStore((state) => state.correctionError);
  const clearCorrectionError = useDashboardStore((state) => state.clearCorrectionError);

  const [isOpen, setIsOpen] = useState(false);
  const [action, setAction] = useState<CorrectionAction | null>(null);
  const [content, setContent] = useState('');
  const [reason, setReason] = useState('');
  const [verificationQuestion, setVerificationQuestion] = useState('');
  const [protectedConfirmed, setProtectedConfirmed] = useState(false);
  const [permanentConfirmation, setPermanentConfirmation] = useState('');
  const [plan, setPlan] = useState<CorrectionPlan | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [applyResponse, setApplyResponse] = useState<CorrectionApplyResponse | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const firstFocusRef = useRef<HTMLInputElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  const p = memory.properties;
  const lifecycleStatus = String(p.status || '').toLowerCase();
  const archived = p.archived === true || lifecycleStatus === 'archived';
  const superseded = Boolean(p.superseded_by_id) || lifecycleStatus === 'superseded';
  const active = !archived && !p.deprecated && !superseded;
  const manuallyArchived = archived && !superseded;
  const protectedMemory = isProtected(memory);
  const availableActions = active
    ? ACTIONS.filter((candidate) => candidate.action !== 'restore')
    : manuallyArchived
      ? ACTIONS.filter(
          (candidate) => candidate.action === 'restore' || candidate.action === 'permanent_delete',
        )
      : ACTIONS.filter((candidate) => candidate.action === 'permanent_delete');
  const requiresContent = action === 'edit' || action === 'replace';
  const permanentDelete = action === 'permanent_delete';
  const selectedDefinition = actionDefinition(action);
  const busy = isCorrectionPlanning || isCorrectionApplying;

  const resetForAction = useCallback((nextAction: CorrectionAction) => {
    setAction(nextAction);
    setContent(nextAction === 'edit' || nextAction === 'replace' ? String(p.content || '') : '');
    setReason('');
    setVerificationQuestion('');
    setProtectedConfirmed(false);
    setPermanentConfirmation('');
    setPlan(null);
    setPlanId(null);
    setApplyResponse(null);
    setLocalError(null);
    clearCorrectionError();
  }, [clearCorrectionError, p.content]);

  const openAction = (nextAction: CorrectionAction) => {
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    resetForAction(nextAction);
    setIsOpen(true);
  };

  const closeDialog = useCallback(() => {
    if (busy) return;
    setIsOpen(false);
  }, [busy]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const focusTimer = window.requestAnimationFrame(() => firstFocusRef.current?.focus());
    const handleDialogKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        closeDialog();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;

      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((element) => element.getAttribute('aria-hidden') !== 'true');
      if (focusable.length === 0) {
        event.preventDefault();
        dialogRef.current.focus();
        return;
      }
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
      window.cancelAnimationFrame(focusTimer);
      document.removeEventListener('keydown', handleDialogKeyDown, true);
    };
  }, [closeDialog, isOpen]);

  useEffect(() => {
    if (isOpen) return;
    const previousFocus = previousFocusRef.current;
    if (previousFocus && document.contains(previousFocus)) {
      window.requestAnimationFrame(() => previousFocus.focus());
    }
    previousFocusRef.current = null;
  }, [isOpen]);

  const chooseAction = (nextAction: CorrectionAction) => {
    if (busy) return;
    resetForAction(nextAction);
  };

  const handlePlan = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!action) {
      setLocalError('Choose a correction first.');
      return;
    }
    const proposedContent = requiresContent ? content.trim() : undefined;
    if (requiresContent && !proposedContent) {
      setLocalError(`${formatAction(action)} requires corrected knowledge.`);
      return;
    }
    if (!reason.trim()) {
      setLocalError('Enter a short reason for this correction.');
      return;
    }
    if (!verificationQuestion.trim()) {
      setLocalError('Enter a likely future Recall question.');
      return;
    }
    if (protectedMemory && !protectedConfirmed) {
      setLocalError('A protected memory must be acknowledged before inspection.');
      return;
    }

    setLocalError(null);
    const response = await requestCorrectionPlan(
      memory.id,
      action,
      proposedContent,
      protectedMemory && protectedConfirmed,
    );
    if (!response.success || !response.plan) {
      setLocalError(response.error || correctionError || 'The correction plan could not be created.');
      return;
    }
    setPlan(response.plan);
    setPlanId(response.plan_id);
    setApplyResponse(null);
    setLocalError(null);
  };

  const handleApply = async () => {
    if (!planId || !plan?.applicable || !action) return;
    if (permanentDelete && permanentConfirmation !== 'DELETE') {
      setLocalError('Type DELETE exactly to confirm permanent removal.');
      return;
    }
    setLocalError(null);
    const response = await applyCorrectionPlan(
      planId,
      requiresContent ? content.trim() : undefined,
      reason.trim(),
      verificationQuestion.trim(),
      permanentDelete && permanentConfirmation === 'DELETE',
    );
    if (isPlanStale(response)) {
      setPlan(null);
      setPlanId(null);
      setApplyResponse(null);
      setLocalError('The correction plan is no longer current. Inspect the memory again and request a new plan.');
      return;
    }
    if (!response.correction_status) {
      setLocalError(response.error || correctionError || 'The control service returned no terminal correction status.');
      return;
    }
    setApplyResponse(response);
    setLocalError(null);
  };

  const backToInspection = () => {
    if (busy) return;
    setPlan(null);
    setPlanId(null);
    setApplyResponse(null);
    setLocalError(null);
    clearCorrectionError();
  };

  const reloadAfterReceipt = () => {
    setIsOpen(false);
    void refreshSnapshot();
  };

  return (
    <section className="border-b border-slate-800/60 px-5 py-4" aria-labelledby="correct-memory-heading">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div id="correct-memory-heading" className="text-xs font-semibold uppercase tracking-wider text-amber-200">
            Correct this knowledge
          </div>
          <p className="mt-1 max-w-md text-xs leading-relaxed text-slate-500">
            Make a careful change to what Elefante knows without opening the underlying stores.
          </p>
        </div>
        <LockKeyhole size={15} className="mt-0.5 flex-shrink-0 text-amber-300" aria-hidden="true" />
      </div>

      {controlEnabled ? (
        <>
          {availableActions.length > 0 ? (
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {availableActions.map((candidate) => (
                <button
                  key={candidate.action}
                  type="button"
                  onClick={() => openAction(candidate.action)}
                  className="flex min-h-[64px] flex-col items-start justify-center gap-1 rounded-md border border-slate-700/70 bg-slate-900/50 px-3 py-2 text-left transition-colors hover:border-amber-300/50 hover:bg-amber-500/5"
                  aria-label={`${candidate.label} ${memoryTitle(memory)}`}
                >
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                    <span className="text-amber-300">{candidate.icon}</span>
                    {candidate.label}
                  </span>
                  <span className="text-[11px] leading-relaxed text-slate-500">{candidate.description}</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="mt-3 rounded-md border border-slate-700/60 bg-slate-900/50 px-3 py-2.5 text-xs leading-relaxed text-slate-500">
              This knowledge is inactive and cannot be corrected from this view. Inspect its history or paired replacement first.
            </div>
          )}
        </>
      ) : (
        <div className="mt-3 rounded-md border border-slate-700/60 bg-slate-900/50 px-3 py-2.5 text-[11px] leading-relaxed text-slate-500">
          Local control is unavailable — reload Home to manage this knowledge.
        </div>
      )}

      <p className="mt-3 text-[10px] leading-relaxed text-slate-600">
        Permanent deletion uses a temporary verified safety backup. Failure restores it; success destroys it.
      </p>

      {isOpen && action && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[70] flex items-end justify-center bg-black/70 p-3 backdrop-blur-sm sm:items-center sm:p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeDialog();
          }}
        >
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="correction-dialog-title"
            aria-describedby="correction-dialog-description"
            tabIndex={-1}
            className="flex max-h-[92vh] w-full max-w-xl flex-col overflow-hidden rounded-xl border border-amber-500/30 bg-slate-950 shadow-2xl"
          >
            <div className="flex items-start justify-between gap-3 border-b border-slate-700/70 bg-slate-900/95 px-5 py-4">
              <div>
                <div className="text-[10px] uppercase tracking-[0.2em] text-amber-300">Home Correct</div>
                <h2 id="correction-dialog-title" className="mt-1 text-base font-semibold text-slate-100">
                  Correct this knowledge
                </h2>
                <p id="correction-dialog-description" className="mt-1 text-xs text-slate-500">
                  Inspect the proposed change before Elefante applies anything.
                </p>
              </div>
              <button
                type="button"
                onClick={closeDialog}
                disabled={busy}
                className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                aria-label="Close correction dialog"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-4">
              {applyResponse ? (
                <div className="space-y-4">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">7 / Receipt</div>
                  <CorrectionReceipt response={applyResponse} action={action} />
                </div>
              ) : plan ? (
                <div className="space-y-4">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-cyan-300">3 / Preview plan</div>
                  <div className="rounded-lg border border-cyan-500/25 bg-cyan-500/5 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-xs font-semibold uppercase tracking-wider text-cyan-200">Inspect impact</div>
                      <span className={`rounded px-2 py-0.5 text-[10px] uppercase tracking-wider ${plan.applicable ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}>
                        {plan.applicable ? 'Plan ready' : 'Blocked'}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-slate-300">{plan.reason}</p>
                    {plan.reason_code && (
                      <div className="mt-2 text-[10px] uppercase tracking-wider text-slate-500">
                        Reason: {plan.reason_code.replace(/[_-]/g, ' ')}
                      </div>
                    )}
                  </div>

                  <div className="rounded-lg border border-slate-700/60 bg-slate-900/60 px-4 py-3">
                    <div className="text-[10px] uppercase tracking-widest text-slate-500">Proposed impact</div>
                    <div className="mt-3 space-y-2 text-xs">
                      <ImpactRow label="Action" value={formatAction(plan.action)} />
                      <ImpactRow label="Knowledge" value={memoryTitle(memory)} />
                      <ImpactRow label="Project" value={String(p.project || 'Declared project scope')} />
                      <ImpactRow label="Protected" value={plan.protected ? 'Yes — explicit confirmation recorded' : 'No'} />
                      <ImpactRow label="Reversible" value={plan.irreversible ? 'No' : 'Yes if the operation fails'} />
                    </div>
                  </div>

                  {requiresContent && (
                    <div className="rounded-lg border border-slate-700/60 bg-slate-900/50 px-4 py-3">
                      <div className="text-[10px] uppercase tracking-widest text-slate-500">Corrected knowledge</div>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{content}</p>
                    </div>
                  )}

                  {permanentDelete && plan.applicable && (
                    <div className="rounded-lg border border-red-500/45 bg-red-500/10 px-4 py-3">
                      <div className="flex items-start gap-2">
                        <Trash2 size={16} className="mt-0.5 flex-shrink-0 text-red-300" aria-hidden="true" />
                        <div>
                          <div className="text-sm font-semibold text-red-100">This cannot be recovered after success</div>
                          <p className="mt-1 text-xs leading-relaxed text-slate-400">
                            Elefante first verifies a temporary local backup. It restores that backup if deletion fails, and destroys it only after the memory, connections, Home, Recall, and unshared attachments are verified absent.
                          </p>
                        </div>
                      </div>
                      <label htmlFor="permanent-delete-confirmation" className="mt-3 block text-xs font-medium text-red-100">
                        Type DELETE to continue
                      </label>
                      <input
                        id="permanent-delete-confirmation"
                        type="text"
                        value={permanentConfirmation}
                        onChange={(event) => setPermanentConfirmation(event.target.value)}
                        autoComplete="off"
                        spellCheck={false}
                        disabled={busy}
                        className="mt-1.5 w-full rounded-md border border-red-500/40 bg-slate-950 px-3 py-2.5 text-sm text-red-100 focus:border-red-400 focus:outline-none disabled:opacity-50"
                      />
                    </div>
                  )}

                  {plan.applicable && planId ? (
                    <div className="rounded-lg border border-amber-500/35 bg-amber-500/5 px-4 py-3">
                      <div className="text-sm font-semibold text-amber-100">4 / Confirm correction</div>
                      <p className="mt-1 text-xs leading-relaxed text-slate-400">
                        This final confirmation uses a single-use plan ticket. Elefante will verify the store, Home snapshot, and scoped Recall before reporting completion.
                      </p>
                      <button
                        type="button"
                        onClick={handleApply}
                        disabled={busy || (permanentDelete && permanentConfirmation !== 'DELETE')}
                        aria-busy={isCorrectionApplying}
                        className="mt-3 inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-md bg-amber-500/85 px-3 py-2.5 text-xs font-semibold text-slate-950 transition-colors hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {isCorrectionApplying ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
                        {isCorrectionApplying
                          ? 'Applying and verifying…'
                          : permanentDelete
                            ? 'Create safety backup & delete'
                            : 'Confirm & apply'}
                      </button>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-slate-700/60 bg-slate-900/50 px-4 py-3 text-xs leading-relaxed text-slate-400">
                      No apply action is available for this plan. Return to inspection to adjust the correction.
                    </div>
                  )}

                  {localError && <InlineError message={localError} />}

                  <button
                    type="button"
                    onClick={backToInspection}
                    disabled={busy}
                    className="inline-flex min-h-[44px] items-center gap-2 text-xs text-slate-400 transition-colors hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <RotateCcw size={13} aria-hidden="true" />
                    Back to inspection
                  </button>
                </div>
              ) : (
                <form onSubmit={handlePlan} className="space-y-4">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-cyan-300">1–2 / Choose action and inspect</div>

                  <fieldset disabled={busy}>
                    <legend className="mb-2 text-xs font-medium text-slate-300">Choose a correction</legend>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {availableActions.map((candidate) => (
                        <label
                          key={candidate.action}
                          className={`flex min-h-[68px] cursor-pointer items-start gap-3 rounded-lg border px-3 py-3 transition-colors ${action === candidate.action ? 'border-amber-400/50 bg-amber-500/10' : 'border-slate-700/60 bg-slate-900/50 hover:border-slate-600'}`}
                        >
                          <input
                            ref={candidate.action === availableActions[0]?.action ? firstFocusRef : undefined}
                            type="radio"
                            name="correction-action"
                            value={candidate.action}
                            checked={action === candidate.action}
                            onChange={() => chooseAction(candidate.action)}
                            className="mt-1 accent-amber-400"
                          />
                          <span className="min-w-0">
                            <span className="flex items-center gap-1.5 text-xs font-medium text-slate-200">
                              <span className="text-amber-300">{candidate.icon}</span>
                              {candidate.label}
                            </span>
                            <span className="mt-1 block text-xs leading-relaxed text-slate-500">{candidate.description}</span>
                          </span>
                        </label>
                      ))}
                    </div>
                  </fieldset>

                  {requiresContent && (
                    <div>
                      <label htmlFor="correction-content" className="mb-1.5 block text-xs font-medium text-slate-300">
                        Corrected knowledge
                      </label>
                      <textarea
                        id="correction-content"
                        value={content}
                        onChange={(event) => setContent(event.target.value)}
                        maxLength={10000}
                        rows={5}
                        disabled={busy}
                        required
                        aria-describedby="correction-content-help"
                        className="w-full resize-y rounded-md border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:border-amber-400/60 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                      />
                      <div id="correction-content-help" className="mt-1 flex justify-between gap-3 text-[10px] text-slate-600">
                        <span>{formatAction(action)} keeps this knowledge in the selected project.</span>
                        <span>{content.length}/10000</span>
                      </div>
                    </div>
                  )}

                  {protectedMemory && (
                    <div className="rounded-lg border border-amber-500/45 bg-amber-500/10 px-3 py-3">
                      <div className="flex items-start gap-2">
                        <LockKeyhole size={15} className="mt-0.5 flex-shrink-0 text-amber-300" aria-hidden="true" />
                        <div>
                          <div className="text-xs font-semibold text-amber-100">Protected knowledge</div>
                          <p className="mt-1 text-xs leading-relaxed text-slate-400">
                            This memory is {protectedReason(memory)}. Explicit confirmation is required before Elefante can inspect the plan.
                          </p>
                        </div>
                      </div>
                      <label className="mt-3 flex min-h-[44px] cursor-pointer items-start gap-2 py-2 text-xs text-amber-100">
                        <input
                          type="checkbox"
                          checked={protectedConfirmed}
                          onChange={(event) => setProtectedConfirmed(event.target.checked)}
                          disabled={busy}
                          className="mt-1 accent-amber-400"
                        />
                        <span>I understand this is protected and want to inspect this correction.</span>
                      </label>
                    </div>
                  )}

                  <div>
                    <label htmlFor="correction-reason" className="mb-1.5 block text-xs font-medium text-slate-300">Why make this correction?</label>
                    <textarea
                      id="correction-reason"
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                      maxLength={240}
                      rows={2}
                      disabled={busy}
                      required
                      placeholder="Briefly explain what is wrong or changed."
                      className="w-full resize-y rounded-md border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:border-amber-400/60 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                    />
                    <div className="mt-1 text-right text-[10px] text-slate-600">{reason.length}/240</div>
                  </div>

                  <div>
                    <label htmlFor="correction-question" className="mb-1.5 block text-xs font-medium text-slate-300">
                      {permanentDelete ? 'Recall question that currently finds this memory' : 'Likely future Recall question'}
                    </label>
                    <textarea
                      id="correction-question"
                      value={verificationQuestion}
                      onChange={(event) => setVerificationQuestion(event.target.value)}
                      maxLength={240}
                      rows={2}
                      disabled={busy}
                      required
                      placeholder={permanentDelete
                        ? 'What question should no longer retrieve this memory?'
                        : 'What might you ask later to verify this correction?'}
                      className="w-full resize-y rounded-md border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:border-amber-400/60 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                    />
                    <div className="mt-1 text-right text-[10px] text-slate-600">{verificationQuestion.length}/240</div>
                  </div>

                  {(localError || correctionError) && <InlineError message={localError || correctionError || ''} />}

                  <button
                    type="submit"
                    disabled={busy}
                    aria-busy={isCorrectionPlanning}
                    className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-md border border-amber-400/40 bg-amber-500/15 px-3 py-2.5 text-xs font-semibold text-amber-100 transition-colors hover:bg-amber-500/25 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    {isCorrectionPlanning ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <ArrowRight size={14} aria-hidden="true" />}
                    {isCorrectionPlanning ? 'Inspecting plan…' : `Inspect ${selectedDefinition?.label || 'correction'} plan`}
                  </button>
                </form>
              )}
            </div>

            {applyResponse && (
              <div className="flex flex-col gap-2 border-t border-slate-700/70 bg-slate-900/70 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-[11px] text-slate-500">The result is based on the returned correction status.</div>
                {applyResponse.correction_status === 'VERIFIED_COMPLETE'
                || applyResponse.correction_status === 'FAILED_ROLLED_BACK' ? (
                  <button
                    type="button"
                    onClick={reloadAfterReceipt}
                    className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-slate-600 bg-slate-800/80 px-3 py-2.5 text-xs font-semibold text-slate-100 transition-colors hover:bg-slate-700"
                  >
                    <RotateCcw size={13} aria-hidden="true" />
                    Close and reload snapshot
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={closeDialog}
                    className="inline-flex min-h-[44px] items-center justify-center rounded-md border border-slate-700 bg-slate-900 px-3 py-2.5 text-xs font-semibold text-slate-200 transition-colors hover:bg-slate-800"
                  >
                    Close receipt
                  </button>
                )}
              </div>
            )}
          </div>
        </div>,
        document.body,
      )}
    </section>
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
      <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
