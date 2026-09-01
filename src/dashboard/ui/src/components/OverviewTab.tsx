import { SessionIntelligencePanel } from '@/components/SessionIntelligencePanel';
import { HomeStatePanel } from '@/components/HomeStatePanel';

export function OverviewTab() {
  return (
    <div className="h-full overflow-auto px-5 py-5 md:px-8 md:py-6">
      <div className="mx-auto flex min-h-full max-w-[1320px] flex-col gap-5">
        <HomeStatePanel />

        <details className="border border-slate-800 bg-slate-950/45">
          <summary className="cursor-pointer px-5 py-4 text-xs font-medium text-slate-300 hover:text-white">
            Advanced: Session Intelligence
          </summary>
          <div className="border-t elefante-hairline p-5">
            <SessionIntelligencePanel />
          </div>
        </details>
      </div>
    </div>
  );
}
