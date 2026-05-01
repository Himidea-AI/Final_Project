import {
  TrendingUp,
  Users,
  ShieldAlert,
  Target,
  Brain,
  UserSearch,
  LineChart as LineChartIcon,
  Crosshair,
  Route,
  type LucideIcon,
} from 'lucide-react';
import type { AgentAttribution, AgentId, AgentKind } from '../../../types';
import { humanizeGrade } from '../dashboard/utils/formatters';

const AGENT_ICONS: Record<AgentId, LucideIcon> = {
  market_analyst: TrendingUp,
  population_analyst: Users,
  legal: ShieldAlert,
  district_ranking: Target,
  inflow: Route,
  synthesis: Brain,
  demographic_depth: UserSearch,
  trend_forecaster: LineChartIcon,
  competitor_intel: Crosshair,
};

const AGENT_COLORS: Record<AgentId, string> = {
  market_analyst: 'text-primary',
  population_analyst: 'text-success',
  legal: 'text-danger',
  district_ranking: 'text-primary',
  inflow: 'text-success',
  synthesis: 'text-primary',
  demographic_depth: 'text-primary',
  trend_forecaster: 'text-primary',
  competitor_intel: 'text-warning',
};

const KIND_BADGE: Record<AgentKind, string> = {
  LLM: 'bg-primary/10 text-primary',
  Python: 'bg-success/10 text-success',
  Hybrid: 'bg-primary/10 text-primary',
  RAG: 'bg-danger/10 text-danger',
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
        className="flex w-full items-center gap-2 rounded-md border border-border bg-card p-2 text-left hover:bg-muted transition-colors"
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-card border border-border">
          <Icon className={`h-4 w-4 ${color}`} strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-foreground truncate">
              {attribution.display_name}
            </span>
            <span className={`shrink-0 rounded px-1.5 py-0.5 text-[0.625rem] font-mono ${kindCls}`}>
              {attribution.kind}
            </span>
          </div>
          <p className="text-xs text-muted-foreground truncate">
            {humanizeGrade(attribution.verdict)}
          </p>
        </div>
      </button>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-muted border border-border">
          <Icon className={`h-7 w-7 ${color}`} strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-foreground">{attribution.display_name}</h3>
            <span className={`rounded px-1.5 py-0.5 text-[0.625rem] font-mono ${kindCls}`}>
              {attribution.kind}
            </span>
          </div>
          <p className="mt-2 text-sm font-semibold text-foreground leading-snug">
            {humanizeGrade(attribution.verdict)}
          </p>
          <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
            {humanizeGrade(attribution.reasoning)}
          </p>
        </div>
      </div>
      {attribution.sources.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {attribution.sources.map((s) => (
            <span
              key={s}
              className="rounded bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground"
            >
              {s}
            </span>
          ))}
        </div>
      )}
      {attribution.confidence != null && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-[0.625rem] text-muted-foreground">
            <span>신뢰도</span>
            <span>{(attribution.confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="mt-1 h-1 rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${attribution.confidence * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
