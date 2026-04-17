// Elefante Dashboard v2.9.3 - Health Score Ring Gauge

interface HealthGaugeProps {
  score: number;
  status: 'healthy' | 'warning' | 'critical';
  size?: number;
}

const STATUS_COLORS = {
  healthy: { stroke: '#34d399', text: 'text-emerald-400', glow: '#34d39940' },
  warning: { stroke: '#fbbf24', text: 'text-amber-400', glow: '#fbbf2440' },
  critical: { stroke: '#f87171', text: 'text-red-400', glow: '#f8717140' },
};

export function HealthGauge({ score, status, size = 160 }: HealthGaugeProps) {
  const colors = STATUS_COLORS[status];
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.max(0, Math.min(100, score));
  const dashOffset = circumference * (1 - progress / 100);
  const center = size / 2;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background track */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-slate-700/50"
        />
        {/* Progress arc */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={colors.stroke}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          style={{
            filter: `drop-shadow(0 0 6px ${colors.glow})`,
            transition: 'stroke-dashoffset 0.8s ease-out',
          }}
        />
      </svg>
      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-4xl font-bold tabular-nums ${colors.text}`}>{score}%</span>
        <span className={`text-[11px] font-medium mt-0.5 ${colors.text}`}>
          {status === 'healthy' ? 'Healthy' : status === 'warning' ? 'Attention' : 'Critical'}
        </span>
      </div>
    </div>
  );
}
