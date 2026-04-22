import {
  TrendingUp,
  Users,
  ShieldAlert,
  Target,
  Brain,
  UserSearch,
  LineChart as LineChartIcon,
  Crosshair,
  type LucideIcon,
} from 'lucide-react';
import type { AgentAttribution, AgentId, AgentKind } from '../../../types';

const AGENT_ICONS: Record<AgentId, LucideIcon> = {
  market_analyst: TrendingUp,
  population_analyst: Users,
  legal: ShieldAlert,
  district_ranking: Target,
  synthesis: Brain,
  demographic_depth: UserSearch,
  trend_forecaster: LineChartIcon,
  competitor_intel: Crosshair,
};

const AGENT_COLORS: Record<AgentId, string> = {
  market_analyst: 'text-blue-400',
  population_analyst: 'text-emerald-400',
  legal: 'text-rose-400',
  district_ranking: 'text-sky-400',
  synthesis: 'text-indigo-400',
  demographic_depth: 'text-violet-400',
  trend_forecaster: 'text-cyan-400',
  competitor_intel: 'text-orange-400',
};

const KIND_BADGE: Record<AgentKind, string> = {
  LLM: 'bg-indigo-500/10 text-indigo-500',
  Python: 'bg-emerald-500/10 text-emerald-500',
  Hybrid: 'bg-blue-500/10 text-blue-400',
  RAG: 'bg-rose-500/10 text-rose-400',
};

interface AgentCardProps {
  attribution: AgentAttribution;
  size: 'full' | 'compact';
  onExpand?: () => void;
}

export function AgentCard({ attribution, size, onExpand }: AgentCardProps) {
  const Icon = AGENT_ICONS[attribution.id];
  const color = AGENT_COLORS[attribution.id];
  const kindCls = KIND_BADGE[attribution.kind];

  if (size === 'compact') {
    return (
      <button
        type="button"
        onClick={onExpand}
        className="flex w-full items-center gap-2 rounded-md border border-stone-700 bg-stone-900/50 p-2 text-left hover:bg-stone-800 transition-colors"
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-stone-900/90 border border-white/5">
          <Icon className={`h-4 w-4 ${color}`} strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-stone-100 truncate">
              {attribution.display_name}
            </span>
            <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-mono ${kindCls}`}>
              {attribution.kind}
            </span>
          </div>
          <p className="text-xs text-stone-400 truncate">{attribution.verdict}</p>
        </div>
      </button>
    );
  }

  return (
    <div className="rounded-lg border border-stone-700 bg-stone-800 p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-stone-900/90 border border-white/5">
          <Icon className={`h-7 w-7 ${color}`} strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-stone-100">{attribution.display_name}</h3>
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-mono ${kindCls}`}>
              {attribution.kind}
            </span>
          </div>
          <p className="mt-2 text-sm font-semibold text-stone-100 leading-snug">
            {attribution.verdict}
          </p>
          <p className="mt-2 text-xs text-stone-400 leading-relaxed">{attribution.reasoning}</p>
        </div>
      </div>
      {attribution.sources.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {attribution.sources.map((s) => (
            <span
              key={s}
              className="rounded bg-stone-700 px-2 py-0.5 text-xs font-mono text-stone-400"
            >
              {s}
            </span>
          ))}
        </div>
      )}
      {attribution.confidence != null && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-[10px] text-stone-500">
            <span>신뢰도</span>
            <span>{(attribution.confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="mt-1 h-1 rounded-full bg-stone-700">
            <div
              className="h-full rounded-full bg-indigo-500"
              style={{ width: `${attribution.confidence * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
