import { useState } from 'react';
import {
  Activity,
  Archive,
  AlertTriangle,
  Check,
  Download,
  FileArchive,
  HardDriveDownload,
  Loader2,
  LockKeyhole,
  PackageCheck,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
  Trash2,
  Wrench,
} from 'lucide-react';
import { useDashboardStore } from '@/store';
import type {
  RecoveryAction,
  RecoveryBackupArchive,
  RecoveryHealth,
  RecoveryPlan,
  RecoveryReceipt,
  RecoveryTerminalStatus,
} from '@/types';

const HEALTH_STATE_LABELS: Record<RecoveryHealth['state'], string> = {
  READY: 'Ready',
  NEEDS_ATTENTION: 'Needs attention',
  RECOVERY_REQUIRED: 'Recovery required',
  UNSUPPORTED: 'Unsupported',
};

const HEALTH_NEXT_ACTION_LABELS: Record<string, string> = {
  none: 'No action needed',
  back_up_now: 'Back up now',
  repair: 'Repair Elefante',
  restore: 'Restore a verified backup',
  create_support_report: 'Create a support report',
  use_supported_setup: 'Use the supported setup',
};

function formatBytes(value: number | undefined): string {
  const bytes = Math.max(0, value ?? 0);
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = bytes / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && size >= 1024; index += 1) {
    size /= 1024;
    unit = units[index];
  }
  return `${size >= 10 ? size.toFixed(0) : size.toFixed(1)} ${unit}`;
}

function statusPresentation(
  status: RecoveryTerminalStatus | 'RUNNING',
  operation?: RecoveryAction,
) {
  const restore = operation === 'restore';
  const supportReport = operation === 'support_report';
  if (status === 'VERIFIED_COMPLETE') {
    return {
      label: restore
        ? 'Restore verified'
        : supportReport
          ? 'Support report verified'
          : 'Backup verified',
      detail: restore
        ? 'Current data was protected first. Restored files, Home, and Recall all passed verification.'
        : supportReport
          ? 'The previewed allowlist was written to one private ZIP, read back, and downloaded locally. Nothing was transmitted.'
          : 'The archive was read back, restored into staging, and both databases passed verification.',
      tone: 'border-emerald-400/50 text-emerald-300',
    };
  }
  if (status === 'FAILED_ROLLED_BACK') {
    return {
      label: restore
        ? 'Previous data restored safely'
        : supportReport
          ? 'Support report rejected safely'
          : 'Backup rejected safely',
      detail: restore
        ? 'A restore check failed, so Elefante put the exact previous data back and verified it.'
        : supportReport
          ? 'Verification failed and the untrusted support ZIP was removed.'
          : 'Verification failed and the untrusted archive was removed.',
      tone: 'border-amber-300/50 text-amber-200',
    };
  }
  if (status === 'RUNNING') {
    return {
      label: 'Operation interrupted or still running',
      detail: 'Reopen Recover and inspect the receipt before starting another lifecycle change.',
      tone: 'border-cyan-400/50 text-cyan-300',
    };
  }
  if (status === 'UNSAFE') {
    return {
      label: 'Recovery required',
      detail: 'Elefante could not prove a safe rollback. Do not retry automatically.',
      tone: 'border-red-400/60 text-red-300',
    };
  }
  return {
    label: status === 'NEEDS_HUMAN' ? 'Plan changed' : 'No data switched',
    detail: 'Elefante did not complete the requested lifecycle change. Inspect the reason before retrying.',
    tone: 'border-amber-300/50 text-amber-200',
  };
}

function PlanSummary({ plan }: { plan: RecoveryPlan }) {
  if (plan.action === 'support_report' && plan.preview) {
    const preview = plan.preview;
    const product = preview.product;
    const environment = preview.environment;
    return (
      <div className="space-y-4">
        <div className="border border-cyan-400/30 bg-cyan-400/5 p-4">
          <div className="text-[9px] text-cyan-300 elefante-mono uppercase tracking-[0.14em]">
            Report preview
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-300">{plan.reason}</p>
          <p className="mt-2 text-[10px] text-slate-500">
            One JSON manifest · approximately {formatBytes(plan.estimated_bytes)} · no transmission
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="border border-slate-800 bg-slate-950/70 p-4">
            <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">Product</div>
            <div className="mt-2 text-sm text-slate-200">
              {product.version || 'Version not recorded'}
            </div>
            <div className="mt-1 text-[10px] text-slate-500">
              {product.release_channel || 'Channel unavailable'} · {preview.readiness.customer_ready === true ? 'customer ready' : 'needs attention'}
            </div>
          </div>
          <div className="border border-slate-800 bg-slate-950/70 p-4">
            <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">Environment</div>
            <div className="mt-2 text-sm text-slate-200">
              {environment.operating_system || 'OS unavailable'} · {environment.architecture || 'architecture unavailable'}
            </div>
            <div className="mt-1 text-[10px] text-slate-500">
              Python {environment.python_version || 'unavailable'}
            </div>
          </div>
          <div className="border border-slate-800 bg-slate-950/70 p-4">
            <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">Connections and backups</div>
            <div className="mt-2 text-sm text-slate-200">
              {preview.agent_connection.verified.length} verified agent connection{preview.agent_connection.verified.length === 1 ? '' : 's'}
            </div>
            <div className="mt-1 text-[10px] text-slate-500">
              {preview.backups.valid} valid backup{preview.backups.valid === 1 ? '' : 's'} · {preview.backups.invalid} invalid
            </div>
          </div>
          <div className="border border-slate-800 bg-slate-950/70 p-4">
            <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">Diagnostic evidence</div>
            <div className="mt-2 text-sm text-slate-200">
              {preview.diagnostic_codes.length} diagnostic code{preview.diagnostic_codes.length === 1 ? '' : 's'}
            </div>
            <div className="mt-1 text-[10px] text-slate-500">
              {preview.operation_receipts.recovery.length} recent lifecycle receipt{preview.operation_receipts.recovery.length === 1 ? '' : 's'}
            </div>
          </div>
        </div>
        {preview.diagnostic_codes.length > 0 && (
          <div className="border border-slate-800 bg-slate-950/70 p-4">
            <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">Codes included</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {preview.diagnostic_codes.map((code) => (
                <code key={code} className="border border-slate-800 px-2 py-1 text-[10px] text-amber-200">{code}</code>
              ))}
            </div>
          </div>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="border border-emerald-400/20 bg-emerald-400/5 p-4">
            <div className="text-[9px] text-emerald-300 elefante-mono uppercase tracking-[0.14em]">Included</div>
            <ul className="mt-3 space-y-2 text-[10px] leading-relaxed text-slate-300">
              {(plan.included || []).map((item) => <li key={item}>· {item}</li>)}
            </ul>
          </div>
          <div className="border border-slate-700 bg-slate-950/70 p-4">
            <div className="text-[9px] text-slate-400 elefante-mono uppercase tracking-[0.14em]">Never included</div>
            <ul className="mt-3 space-y-2 text-[10px] leading-relaxed text-slate-400">
              {(plan.excluded || []).map((item) => <li key={item}>· {item}</li>)}
            </ul>
          </div>
        </div>
      </div>
    );
  }
  const restore = plan.action === 'restore';
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="border border-slate-800 bg-slate-950/70 p-4">
        <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">
          {restore ? 'Backup contents' : 'Current data'}
        </div>
        <div className="mt-2 text-lg text-slate-100">{plan.estimated_files ?? 0} files</div>
        <div className="mt-1 text-xs text-slate-500">Approximately {formatBytes(plan.estimated_bytes)}</div>
      </div>
      <div className="border border-slate-800 bg-slate-950/70 p-4">
        <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">
          {restore ? 'Selected backup' : 'Backup destination'}
        </div>
        <code className="mt-2 block break-all text-xs leading-relaxed text-cyan-300">
          {restore ? plan.archive_name : plan.backup_directory}
        </code>
      </div>
      <div className="border border-slate-800 bg-slate-950/70 p-4 sm:col-span-2">
        <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">What Elefante will do</div>
        <p className="mt-2 text-xs leading-relaxed text-slate-300">{plan.reason}</p>
      </div>
    </div>
  );
}

function HealthPanel({
  health,
  onAction,
}: {
  health: RecoveryHealth;
  onAction: (action: RecoveryAction) => void;
}) {
  const ready = health.state === 'READY';
  const critical = health.state === 'RECOVERY_REQUIRED';
  const availableAction = health.next_action === 'back_up_now'
    ? 'backup'
    : health.next_action === 'restore'
      ? 'restore'
      : health.next_action === 'create_support_report'
        ? 'support_report'
        : null;
  const tone = ready
    ? 'border-emerald-400/50 text-emerald-300'
    : critical
      ? 'border-red-400/60 text-red-300'
      : 'border-amber-300/50 text-amber-200';

  return (
    <div className={`mt-6 border bg-slate-950/70 p-5 ${tone}`} aria-live="polite">
      <div className="flex items-start gap-3">
        {ready
          ? <ShieldCheck size={20} className="mt-0.5 shrink-0" aria-hidden="true" />
          : <AlertTriangle size={20} className="mt-0.5 shrink-0" aria-hidden="true" />}
        <div className="min-w-0 flex-1">
          <div className="text-[9px] elefante-mono uppercase tracking-[0.16em]">Current product state</div>
          <h3 className="mt-2 text-xl font-medium text-slate-100">
            {HEALTH_STATE_LABELS[health.state]}
          </h3>
          <p className="mt-2 text-xs leading-relaxed text-slate-400">{health.summary}</p>
        </div>
      </div>

      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {health.checks.map((check) => (
          <div key={check.name} className="flex items-center gap-2 border border-slate-800 px-3 py-2 text-[10px] text-slate-400">
            {check.passed
              ? <Check size={12} className="shrink-0 text-emerald-300" aria-hidden="true" />
              : <AlertTriangle size={12} className="shrink-0 text-amber-200" aria-hidden="true" />}
            <span>{check.name.replace(/_/g, ' ')}</span>
          </div>
        ))}
      </div>

      <div className="mt-5 border border-slate-800 bg-slate-900/50 p-4">
        <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">One safe next action</div>
        <div className="mt-2 text-sm text-slate-200">
          {HEALTH_NEXT_ACTION_LABELS[health.next_action] || health.next_action.replace(/_/g, ' ')}
        </div>
        {availableAction && (
          <button
            type="button"
            onClick={() => onAction(availableAction)}
            className="mt-4 min-h-11 border border-cyan-400/50 px-4 py-2 text-xs text-cyan-200 hover:border-cyan-300 hover:text-white"
          >
            {HEALTH_NEXT_ACTION_LABELS[health.next_action]}
          </button>
        )}
        {!availableAction && health.next_action !== 'none' && (
          <p className="mt-3 text-[10px] leading-relaxed text-slate-500">
            {health.next_action === 'repair'
              ? 'Open the official package matching this installed build. It repairs product code outside the running app; return here afterward and Check health again.'
              : 'Elefante will not substitute a less safe operation. Use the named action or create a support report.'}
          </p>
        )}
      </div>

      <div className="mt-4 text-[10px] text-slate-500">
        {health.valid_backups} verified backup{health.valid_backups === 1 ? '' : 's'}
        {health.invalid_backups > 0 ? ` · ${health.invalid_backups} invalid excluded` : ''}
      </div>
      <div className="mt-2 text-[10px] text-slate-600">
        Managed backup location · <code className="break-all text-slate-400">{health.backup_directory}</code>
      </div>
    </div>
  );
}

function ReceiptPanel({
  receipt,
  onDownload,
  isDownloading,
}: {
  receipt: RecoveryReceipt;
  onDownload?: () => void;
  isDownloading?: boolean;
}) {
  const presentation = statusPresentation(receipt.status, receipt.operation);
  return (
    <section className={`border bg-slate-950/80 p-5 ${presentation.tone}`} aria-live="polite">
      <div className="flex items-start gap-3">
        {receipt.status === 'VERIFIED_COMPLETE'
          ? <ShieldCheck size={20} className="mt-0.5 shrink-0" aria-hidden="true" />
          : <AlertTriangle size={20} className="mt-0.5 shrink-0" aria-hidden="true" />}
        <div className="min-w-0 flex-1">
          <div className="text-[9px] elefante-mono uppercase tracking-[0.16em]">
            Recover receipt · {receipt.operation || 'operation'}
          </div>
          <h2 className="mt-2 text-lg font-medium text-slate-100">{presentation.label}</h2>
          <p className="mt-2 text-xs leading-relaxed text-slate-400">{presentation.detail}</p>
          {receipt.archive_name && (
            <div className="mt-4 border border-slate-800 bg-slate-900/60 p-3">
              <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">
                {receipt.operation === 'restore'
                  ? 'Restored archive'
                  : receipt.operation === 'support_report'
                    ? 'Private support ZIP'
                    : 'Verified archive'}
              </div>
              <code className="mt-1 block break-all text-xs text-cyan-300">{receipt.archive_name}</code>
              <div className="mt-2 text-[10px] text-slate-500">
                {receipt.files ?? 0} files · {formatBytes(receipt.bytes)}
              </div>
              {receipt.operation === 'support_report' && onDownload && (
                <button
                  type="button"
                  onClick={onDownload}
                  disabled={isDownloading}
                  className="mt-3 inline-flex min-h-10 items-center gap-2 border border-cyan-400/50 px-3 py-2 text-[10px] text-cyan-200 hover:border-cyan-300 hover:text-white disabled:opacity-40"
                >
                  {isDownloading
                    ? <Loader2 size={13} className="animate-spin" aria-hidden="true" />
                    : <Download size={13} aria-hidden="true" />}
                  {isDownloading ? 'Downloading…' : 'Download ZIP again'}
                </button>
              )}
            </div>
          )}
          {receipt.safety_archive_name && (
            <div className="mt-3 border border-emerald-400/20 bg-emerald-400/5 p-3">
              <div className="text-[9px] text-emerald-300 elefante-mono uppercase tracking-[0.14em]">Safety backup created first</div>
              <code className="mt-1 block break-all text-xs text-slate-300">{receipt.safety_archive_name}</code>
            </div>
          )}
          {receipt.checks && receipt.checks.length > 0 && (
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {receipt.checks.map((check) => (
                <div key={check.name} className="flex items-center gap-2 border border-slate-800 px-3 py-2 text-[10px] text-slate-400">
                  {check.passed
                    ? <Check size={12} className="shrink-0 text-emerald-300" aria-hidden="true" />
                    : <AlertTriangle size={12} className="shrink-0 text-red-300" aria-hidden="true" />}
                  <span className="truncate">{check.name.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          )}
          {receipt.next_action && receipt.next_action !== 'none' && (
            <p className="mt-4 text-[10px] text-amber-200">
              Next action: {receipt.next_action.replace(/_/g, ' ')}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function ProductMaintenancePanel({ health }: { health: RecoveryHealth | null }) {
  const packageState = health?.package_maintenance;
  const packageReceipt = packageState?.receipt;
  const repairRecommended = health?.next_action === 'repair';
  const receiptVerified = packageReceipt?.status === 'VERIFIED_COMPLETE';

  const operations = [
    {
      name: 'Repair',
      package: 'Matching package',
      icon: Wrench,
      detail: 'Reinstall owned product files and reconnect supported agents while preserving memories and customer-owned configuration.',
    },
    {
      name: 'Update',
      package: 'Newer package',
      icon: RefreshCcw,
      detail: 'Back up first, switch to verified new code, prove agent Recall, and restore the previous code automatically if verification fails.',
    },
    {
      name: 'Roll back code',
      package: 'Current package',
      icon: RotateCcw,
      detail: 'Return to one retained verified product version when available. Code rollback never claims to reverse memory changes.',
    },
    {
      name: 'Uninstall',
      package: 'Matching package',
      icon: Trash2,
      detail: 'Create a verified backup, remove only unchanged Elefante-owned app connections and code, and preserve memories for reinstall.',
    },
  ];

  return (
    <section className="mt-6 border border-slate-800 bg-slate-900/35 p-5 sm:p-6" aria-labelledby="product-maintenance-title">
      <div className="flex flex-col gap-4 border-b border-slate-800 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <PackageCheck size={20} className="mt-0.5 shrink-0 text-cyan-300" aria-hidden="true" />
          <div>
            <div className="text-[9px] text-cyan-400 elefante-mono uppercase tracking-[0.16em]">Product maintenance</div>
            <h2 id="product-maintenance-title" className="mt-2 text-lg font-medium text-slate-100">One safe package handoff.</h2>
            <p className="mt-2 max-w-3xl text-xs leading-relaxed text-slate-400">
              Home protects data and shows proof. The exact official package changes product code, so the running app never replaces or removes itself.
            </p>
          </div>
        </div>
        <span className={`shrink-0 border px-2.5 py-1.5 text-[9px] elefante-mono uppercase tracking-[0.12em] ${
          repairRecommended ? 'border-amber-300/50 text-amber-200' : 'border-cyan-400/40 text-cyan-300'
        }`}>
          {repairRecommended ? 'Repair recommended' : 'Official package owns code'}
        </span>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {operations.map((operation) => {
          const Icon = operation.icon;
          return (
            <article key={operation.name} className={`border p-4 ${
              repairRecommended && operation.name === 'Repair'
                ? 'border-amber-300/50 bg-amber-300/5'
                : 'border-slate-800 bg-slate-950/55'
            }`}>
              <div className="flex items-start justify-between gap-3">
                <Icon size={17} className="shrink-0 text-slate-300" aria-hidden="true" />
                <span className="text-[8px] text-slate-600 elefante-mono uppercase tracking-[0.12em]">{operation.package}</span>
              </div>
              <h3 className="mt-4 text-sm font-medium text-slate-100">{operation.name}</h3>
              <p className="mt-2 text-[10px] leading-relaxed text-slate-500">{operation.detail}</p>
            </article>
          );
        })}
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="border border-slate-800 bg-slate-950/55 p-4">
          <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">Customer journey</div>
          <ol className="mt-4 grid gap-3 sm:grid-cols-3">
            <li className="border-l-2 border-cyan-400/50 pl-3">
              <span className="text-[9px] text-cyan-300 elefante-mono">01</span>
              <strong className="mt-1 block text-xs text-slate-200">Open the official package</strong>
              <span className="mt-1 block text-[10px] leading-relaxed text-slate-500">Use matching, newer, or current package as labelled above.</span>
            </li>
            <li className="border-l-2 border-cyan-400/50 pl-3">
              <span className="text-[9px] text-cyan-300 elefante-mono">02</span>
              <strong className="mt-1 block text-xs text-slate-200">Review and confirm</strong>
              <span className="mt-1 block text-[10px] leading-relaxed text-slate-500">The package identifies the operation and shows its data effect before changing anything.</span>
            </li>
            <li className="border-l-2 border-emerald-400/50 pl-3">
              <span className="text-[9px] text-emerald-300 elefante-mono">03</span>
              <strong className="mt-1 block text-xs text-slate-200">Return and verify</strong>
              <span className="mt-1 block text-[10px] leading-relaxed text-slate-500">Reopen Home, Check health, and inspect the content-free package receipt.</span>
            </li>
          </ol>
        </div>

        <div className={`border p-4 ${
          packageState?.status === 'invalid'
            ? 'border-red-400/40 bg-red-400/5'
            : receiptVerified
              ? 'border-emerald-400/30 bg-emerald-400/5'
              : 'border-slate-800 bg-slate-950/55'
        }`}>
          <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.14em]">Last package receipt</div>
          {packageReceipt ? (
            <>
              <div className={`mt-3 text-sm ${receiptVerified ? 'text-emerald-200' : 'text-amber-200'}`}>
                {packageReceipt.operation.replace(/_/g, ' ')} · {packageReceipt.status.replace(/_/g, ' ').toLowerCase()}
              </div>
              <div className="mt-2 text-[10px] text-slate-500">
                {packageReceipt.previous_version || 'No prior version'} → {packageReceipt.target_version || 'No target version'}
              </div>
              <div className="mt-3 text-[10px] leading-relaxed text-slate-500">
                {packageReceipt.checks.filter((check) => check.passed).length}/{packageReceipt.checks.length} package checks passed
                {packageReceipt.rollback ? ` · rollback ${packageReceipt.rollback.replace(/_/g, ' ')}` : ''}
              </div>
            </>
          ) : packageState?.status === 'invalid' ? (
            <p className="mt-3 text-xs leading-relaxed text-red-200">The last package receipt could not be trusted. Create a support report before another code change.</p>
          ) : (
            <p className="mt-3 text-xs leading-relaxed text-slate-500">Check health to load the last verified package result. No customer content is included.</p>
          )}
        </div>
      </div>
    </section>
  );
}

export function RecoverTab() {
  const controlEnabled = useDashboardStore((state) => state.controlEnabled);
  const isPlanning = useDashboardStore((state) => state.isRecoveryPlanning);
  const isApplying = useDashboardStore((state) => state.isRecoveryApplying);
  const recoveryError = useDashboardStore((state) => state.recoveryError);
  const history = useDashboardStore((state) => state.recoveryHistory);
  const requestPlan = useDashboardStore((state) => state.requestRecoveryPlan);
  const applyPlan = useDashboardStore((state) => state.applyRecoveryPlan);
  const downloadSupportReport = useDashboardStore((state) => state.downloadSupportReport);
  const clearError = useDashboardStore((state) => state.clearRecoveryError);
  const [action, setAction] = useState<RecoveryAction>('health');
  const [health, setHealth] = useState<RecoveryHealth | null>(null);
  const [plan, setPlan] = useState<RecoveryPlan | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [backups, setBackups] = useState<RecoveryBackupArchive[]>([]);
  const [backupsLoaded, setBackupsLoaded] = useState(false);
  const [selectedArchive, setSelectedArchive] = useState('');
  const [verificationQuestion, setVerificationQuestion] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [receipt, setReceipt] = useState<RecoveryReceipt | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  const resetPlan = () => {
    setHealth(null);
    setPlan(null);
    setPlanId(null);
    setConfirmed(false);
    setReceipt(null);
  };

  const chooseAction = (nextAction: RecoveryAction) => {
    clearError();
    setAction(nextAction);
    setVerificationQuestion('');
    resetPlan();
  };

  const inspectRecovery = async (archiveName?: string) => {
    clearError();
    setConfirmed(false);
    setReceipt(null);
    const result = await requestPlan(action, archiveName);
    if (action === 'health') setHealth(result.health ?? null);
    if (action === 'restore') setBackupsLoaded(true);
    if (result.available_backups) setBackups(result.available_backups);
    setPlan(result.plan ?? null);
    setPlanId(result.plan_id);
  };

  const executeRecovery = async () => {
    if (!planId || !confirmed) return;
    if (action === 'restore' && !verificationQuestion.trim()) return;
    clearError();
    const result = await applyPlan(
      planId,
      action,
      action === 'restore' ? verificationQuestion.trim() : undefined,
    );
    setVerificationQuestion('');
    setReceipt(result.receipt ?? null);
    setPlanId(null);
    setConfirmed(false);
    if (
      action === 'support_report'
      && result.success
      && result.receipt?.archive_name
    ) {
      setIsDownloading(true);
      await downloadSupportReport(result.receipt.archive_name);
      setIsDownloading(false);
    }
  };

  const downloadReceipt = async () => {
    if (!receipt?.archive_name || receipt.operation !== 'support_report') return;
    setIsDownloading(true);
    await downloadSupportReport(receipt.archive_name);
    setIsDownloading(false);
  };

  const validBackups = backups.filter((backup) => backup.valid);
  const invalidBackupCount = backups.length - validBackups.length;
  const busy = isPlanning || isApplying;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
        <header className="flex flex-col gap-5 border-b border-slate-800 pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-[9px] text-amber-300 elefante-mono uppercase tracking-[0.18em]">Home · Recover</div>
            <h1 className="mt-2 text-2xl font-medium text-slate-100">Know the state. Recover with proof.</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
              One trustworthy state, one safe next action, and verified protection before any restore.
            </p>
          </div>
          <div className={`border px-3 py-2 text-[9px] elefante-mono uppercase tracking-[0.12em] ${
            controlEnabled
              ? 'border-emerald-400/40 text-emerald-300'
              : 'border-slate-700 text-slate-500'
          }`}>
            {controlEnabled ? 'Management active' : 'Read-only'}
          </div>
        </header>

        {!controlEnabled && (
          <section className="mt-6 border border-slate-700 bg-slate-900/50 p-5">
            <div className="flex items-start gap-3">
              <LockKeyhole size={18} className="mt-0.5 shrink-0 text-slate-400" aria-hidden="true" />
              <div>
                <h2 className="text-sm font-medium text-slate-200">Recovery controls are locked</h2>
                <p className="mt-2 text-xs leading-relaxed text-slate-500">
                  Reload Home to establish a new short-lived local session. The snapshot remains available if the local service is offline.
                </p>
              </div>
            </div>
          </section>
        )}

        <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4" role="tablist" aria-label="Recover action">
          <button
            type="button"
            role="tab"
            aria-selected={action === 'health'}
            onClick={() => chooseAction('health')}
            disabled={busy}
            className={`min-h-20 border p-4 text-left transition-colors disabled:opacity-40 ${
              action === 'health'
                ? 'border-emerald-400/60 bg-emerald-400/5 text-emerald-200'
                : 'border-slate-800 bg-slate-900/30 text-slate-400 hover:border-slate-600'
            }`}
          >
            <span className="flex items-center gap-2 text-sm"><Activity size={17} />Check health</span>
            <span className="mt-2 block text-[10px] leading-relaxed text-slate-500">See one state and one next action.</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={action === 'backup'}
            onClick={() => chooseAction('backup')}
            disabled={busy}
            className={`min-h-20 border p-4 text-left transition-colors disabled:opacity-40 ${
              action === 'backup'
                ? 'border-cyan-400/60 bg-cyan-400/5 text-cyan-200'
                : 'border-slate-800 bg-slate-900/30 text-slate-400 hover:border-slate-600'
            }`}
          >
            <span className="flex items-center gap-2 text-sm"><HardDriveDownload size={17} />Back up now</span>
            <span className="mt-2 block text-[10px] leading-relaxed text-slate-500">Protect the current memory state.</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={action === 'restore'}
            onClick={() => chooseAction('restore')}
            disabled={busy}
            className={`min-h-20 border p-4 text-left transition-colors disabled:opacity-40 ${
              action === 'restore'
                ? 'border-amber-300/60 bg-amber-300/5 text-amber-200'
                : 'border-slate-800 bg-slate-900/30 text-slate-400 hover:border-slate-600'
            }`}
          >
            <span className="flex items-center gap-2 text-sm"><Archive size={17} />Restore a backup</span>
            <span className="mt-2 block text-[10px] leading-relaxed text-slate-500">Verify, protect current data, then switch.</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={action === 'support_report'}
            onClick={() => chooseAction('support_report')}
            disabled={busy}
            className={`min-h-20 border p-4 text-left transition-colors disabled:opacity-40 ${
              action === 'support_report'
                ? 'border-violet-300/60 bg-violet-300/5 text-violet-200'
                : 'border-slate-800 bg-slate-900/30 text-slate-400 hover:border-slate-600'
            }`}
          >
            <span className="flex items-center gap-2 text-sm"><FileArchive size={17} />Support report</span>
            <span className="mt-2 block text-[10px] leading-relaxed text-slate-500">Preview facts, then download one private ZIP.</span>
          </button>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
          <section className="border border-slate-800 bg-slate-900/35 p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                {action === 'health'
                  ? <Activity size={20} className="mt-0.5 shrink-0 text-emerald-300" aria-hidden="true" />
                  : action === 'backup'
                    ? <HardDriveDownload size={20} className="mt-0.5 shrink-0 text-cyan-300" aria-hidden="true" />
                    : action === 'restore'
                      ? <Archive size={20} className="mt-0.5 shrink-0 text-amber-200" aria-hidden="true" />
                      : <FileArchive size={20} className="mt-0.5 shrink-0 text-violet-200" aria-hidden="true" />}
                <div>
                  <div className="text-[9px] text-cyan-400 elefante-mono uppercase tracking-[0.16em]">Available now</div>
                  <h2 className="mt-2 text-lg font-medium text-slate-100">
                    {action === 'health'
                      ? 'Check product readiness'
                      : action === 'backup'
                        ? 'Create a verified backup'
                        : action === 'restore'
                          ? 'Restore one verified backup'
                          : 'Create a privacy-safe support report'}
                  </h2>
                  <p className="mt-2 text-xs leading-relaxed text-slate-400">
                    {action === 'health'
                      ? 'Elefante checks runtime, agent connection, Recall, and verified backup evidence without reading memory content.'
                      : action === 'backup'
                        ? 'The destination is configured by Elefante. Home cannot redirect durable data to another path.'
                        : action === 'restore'
                          ? 'Only archives in the configured backup location can be selected. Current data is backed up before the switch.'
                          : 'Preview every category first. Elefante creates one local ZIP and never sends it anywhere.'}
                  </p>
                </div>
              </div>
              {action === 'health'
                ? <Activity size={18} className="shrink-0 text-slate-600" aria-hidden="true" />
                : action === 'support_report'
                  ? <FileArchive size={18} className="shrink-0 text-slate-600" aria-hidden="true" />
                  : <Archive size={18} className="shrink-0 text-slate-600" aria-hidden="true" />}
            </div>

            {action === 'health' && !health && (
              <button
                type="button"
                onClick={() => inspectRecovery()}
                disabled={!controlEnabled || busy}
                className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 border border-emerald-400/50 px-4 py-2 text-xs text-emerald-200 transition-colors hover:border-emerald-300 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isPlanning && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                {isPlanning ? 'Checking…' : 'Check health'}
              </button>
            )}

            {action === 'health' && health && (
              <>
                <HealthPanel health={health} onAction={chooseAction} />
                <button
                  type="button"
                  onClick={() => inspectRecovery()}
                  disabled={!controlEnabled || busy}
                  className="mt-4 min-h-11 border border-slate-700 px-4 py-2 text-xs text-slate-400 hover:border-slate-500 hover:text-slate-200 disabled:opacity-40"
                >
                  {isPlanning ? 'Checking…' : 'Check again'}
                </button>
              </>
            )}

            {action === 'backup' && !plan && (
              <button
                type="button"
                onClick={() => inspectRecovery()}
                disabled={!controlEnabled || busy}
                className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 border border-cyan-400/50 px-4 py-2 text-xs text-cyan-200 transition-colors hover:border-cyan-300 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isPlanning && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                {isPlanning ? 'Inspecting…' : 'Inspect backup'}
              </button>
            )}

            {action === 'support_report' && !plan && (
              <button
                type="button"
                onClick={() => inspectRecovery()}
                disabled={!controlEnabled || busy}
                className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 border border-violet-300/50 px-4 py-2 text-xs text-violet-200 transition-colors hover:border-violet-200 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isPlanning && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                {isPlanning ? 'Building safe preview…' : 'Preview support report'}
              </button>
            )}

            {action === 'restore' && !backupsLoaded && !plan && (
              <button
                type="button"
                onClick={() => inspectRecovery()}
                disabled={!controlEnabled || busy}
                className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 border border-amber-300/50 px-4 py-2 text-xs text-amber-200 transition-colors hover:border-amber-200 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isPlanning && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                {isPlanning ? 'Checking configured backups…' : 'Find verified backups'}
              </button>
            )}

            {action === 'restore' && backupsLoaded && backups.length === 0 && !plan && (
              <div className="mt-6 border border-slate-800 bg-slate-950/60 p-4">
                <p className="text-xs leading-relaxed text-slate-400">No configured backup is available yet.</p>
                <button
                  type="button"
                  onClick={() => chooseAction('backup')}
                  disabled={busy}
                  className="mt-4 min-h-11 border border-cyan-400/50 px-4 py-2 text-xs text-cyan-200 disabled:opacity-40"
                >
                  Create a backup first
                </button>
              </div>
            )}

            {action === 'restore' && backups.length > 0 && !plan && (
              <div className="mt-6 border border-slate-800 bg-slate-950/60 p-4">
                <label htmlFor="recover-archive" className="text-[9px] text-slate-500 elefante-mono uppercase tracking-[0.14em]">
                  Backup to restore
                </label>
                <select
                  id="recover-archive"
                  value={selectedArchive}
                  onChange={(event) => setSelectedArchive(event.target.value)}
                  disabled={busy}
                  className="mt-3 min-h-11 w-full border border-slate-700 bg-slate-950 px-3 text-xs text-slate-200 outline-none focus:border-amber-300"
                >
                  <option value="">Choose a verified backup</option>
                  {validBackups.map((backup) => (
                    <option key={backup.archive_name} value={backup.archive_name}>
                      {backup.archive_name} · {backup.files} files · {formatBytes(backup.bytes)}
                    </option>
                  ))}
                </select>
                {invalidBackupCount > 0 && (
                  <p className="mt-2 text-[10px] text-amber-200">
                    {invalidBackupCount} invalid archive{invalidBackupCount === 1 ? '' : 's'} excluded.
                  </p>
                )}
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => inspectRecovery(selectedArchive)}
                    disabled={!selectedArchive || !controlEnabled || busy}
                    className="inline-flex min-h-11 items-center justify-center gap-2 border border-amber-300/50 px-4 py-2 text-xs text-amber-200 transition-colors hover:border-amber-200 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {isPlanning && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                    {isPlanning ? 'Inspecting…' : 'Inspect selected backup'}
                  </button>
                  <button
                    type="button"
                    onClick={() => inspectRecovery()}
                    disabled={!controlEnabled || busy}
                    className="min-h-11 border border-slate-700 px-4 py-2 text-xs text-slate-400 hover:border-slate-500 hover:text-slate-200 disabled:opacity-40"
                  >
                    Refresh list
                  </button>
                </div>
              </div>
            )}

            {plan && (
              <div className="mt-6">
                <PlanSummary plan={plan} />
                {!plan.applicable ? (
                  <div className="mt-4 border border-amber-300/40 bg-amber-300/5 p-4 text-xs leading-relaxed text-amber-200">
                    {plan.reason_code || 'Recover cannot safely apply this operation.'}
                  </div>
                ) : (
                  <>
                    {action === 'restore' && (
                      <div className="mt-5">
                        <label htmlFor="restore-verification" className="text-[9px] text-slate-500 elefante-mono uppercase tracking-[0.14em]">
                          Private Recall check
                        </label>
                        <textarea
                          id="restore-verification"
                          value={verificationQuestion}
                          onChange={(event) => setVerificationQuestion(event.target.value.slice(0, 500))}
                          disabled={isApplying}
                          rows={3}
                          placeholder="Ask a question this backup should answer"
                          className="mt-3 w-full resize-none border border-slate-700 bg-slate-950 p-3 text-xs leading-relaxed text-slate-200 outline-none placeholder:text-slate-600 focus:border-amber-300"
                        />
                        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
                          Used once after restore. The question is not written to the recovery receipt.
                        </p>
                      </div>
                    )}
                    <label className="mt-5 flex cursor-pointer items-start gap-3 border border-slate-800 bg-slate-950/60 p-4 text-xs leading-relaxed text-slate-300">
                      <input
                        type="checkbox"
                        checked={confirmed}
                        onChange={(event) => setConfirmed(event.target.checked)}
                        disabled={!planId || isApplying}
                        className="mt-0.5 h-4 w-4 accent-cyan-400"
                      />
                      <span>
                        {action === 'backup'
                          ? 'I understand Elefante will briefly pause memory writes while it creates and verifies this local backup.'
                          : action === 'restore'
                            ? 'I understand Elefante will create a verified safety backup first, then switch only after staging checks; any failed final check triggers rollback.'
                            : 'I reviewed what is included and excluded. Create one private local ZIP from this preview and download it; do not transmit it.'}
                      </span>
                    </label>
                  </>
                )}
                <div className="mt-4 flex flex-wrap gap-3">
                  {plan.applicable && (
                    <button
                      type="button"
                      onClick={executeRecovery}
                      disabled={
                        !planId
                        || !confirmed
                        || isApplying
                        || (action === 'restore' && !verificationQuestion.trim())
                      }
                      className="inline-flex min-h-11 items-center justify-center gap-2 border border-emerald-400/50 bg-emerald-400/5 px-4 py-2 text-xs text-emerald-200 transition-colors hover:border-emerald-300 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {isApplying && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                      {isApplying
                        ? action === 'restore'
                          ? 'Restoring and verifying…'
                          : action === 'support_report'
                            ? 'Creating and verifying report…'
                            : 'Creating and verifying…'
                        : action === 'restore'
                          ? 'Restore with rollback protection'
                          : action === 'support_report'
                            ? 'Create and download report'
                            : 'Create verified backup'}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      resetPlan();
                      if (action === 'backup' || action === 'support_report') void inspectRecovery();
                    }}
                    disabled={!controlEnabled || busy}
                    className="min-h-11 border border-slate-700 px-4 py-2 text-xs text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-200 disabled:opacity-40"
                  >
                    {action === 'restore' ? 'Choose another backup' : 'Inspect again'}
                  </button>
                </div>
              </div>
            )}

            {recoveryError && (
              <div role="alert" className="mt-5 border border-red-400/40 bg-red-400/5 p-4 text-xs leading-relaxed text-red-200">
                {recoveryError}
              </div>
            )}
          </section>

          <aside className="space-y-6">
            <section className="border border-slate-800 bg-slate-900/35 p-5">
              <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.16em]">Safety boundary</div>
              <div className="mt-4 space-y-3 text-xs">
                <div className="flex items-center justify-between gap-3 text-slate-300">
                  <span>Product health</span><span className="text-emerald-300">Available</span>
                </div>
                <div className="flex items-center justify-between gap-3 text-slate-300">
                  <span>Verified backup</span><span className="text-emerald-300">Available</span>
                </div>
                <div className="flex items-center justify-between gap-3 text-slate-300">
                  <span>Verified data restore</span><span className="text-emerald-300">Available</span>
                </div>
                <div className="flex items-center justify-between gap-3 text-slate-300">
                  <span>Privacy-safe support report</span><span className="text-emerald-300">Available</span>
                </div>
                <div className="flex items-center justify-between gap-3 text-slate-500">
                  <span>Product code changes</span><span>Official package</span>
                </div>
                <div className="flex items-center justify-between gap-3 text-slate-300">
                  <span>Permanent memory deletion</span><span className="text-emerald-300">Correct · verified gate</span>
                </div>
              </div>
            </section>

            <section className="border border-slate-800 bg-slate-900/35 p-5">
              <div className="text-[9px] text-slate-600 elefante-mono uppercase tracking-[0.16em]">Recent receipts</div>
              {history.length === 0 ? (
                <p className="mt-4 text-xs leading-relaxed text-slate-500">Inspect an operation to load bounded recovery history.</p>
              ) : (
                <div className="mt-4 space-y-3">
                  {history.slice(0, 5).map((entry, index) => {
                    const presentation = statusPresentation(entry.status, entry.operation);
                    return (
                      <div key={entry.operation_id || `${entry.status}-${index}`} className="border border-slate-800 p-3">
                        <div className={`text-[10px] ${presentation.tone.split(' ').slice(-1)[0]}`}>{presentation.label}</div>
                        <div className="mt-1 truncate text-[10px] text-slate-600">
                          {entry.archive_name || entry.started_at || 'Content-free lifecycle receipt'}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </aside>
        </div>

        <ProductMaintenancePanel health={health} />

        {receipt && (
          <div className="mt-6">
            <ReceiptPanel
              receipt={receipt}
              onDownload={receipt.operation === 'support_report' ? downloadReceipt : undefined}
              isDownloading={isDownloading}
            />
          </div>
        )}
      </div>
    </div>
  );
}
