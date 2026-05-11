/**
 * AgentCard — LangGraph 9 에이전트 attribution 카드.
 *
 * 2026-05-04 (강민): lucide-react 아이콘 → 자체 페르소나 PNG 9개로 교체.
 *  - 백엔드 agent_id 9개 ↔ frontend/src/assets/agents/*.png 1:1 매핑
 *  - AGENT_COLORS (text-primary 등) 는 badge/strong text 강조용으로 그대로 유지
 *  - compact (9×9) / full (14×14) 두 size 모두 png 적용
 */
import competitorIcon from '../../../assets/agents/competitor.png';
import demographicIcon from '../../../assets/agents/demographic.png';
import inflowIcon from '../../../assets/agents/inflow.png';
import legalIcon from '../../../assets/agents/legal.png';
import marketIcon from '../../../assets/agents/market.png';
import populationIcon from '../../../assets/agents/population.png';
import rankingIcon from '../../../assets/agents/ranking.png';
import synthesisIcon from '../../../assets/agents/synthesis.png';
import trendIcon from '../../../assets/agents/trend.png';
import type { AgentAttribution, AgentId, AgentKind } from '../../../types';
import { humanizeGrade } from '../dashboard/utils/formatters';

/** 9 에이전트 페르소나 PNG (URL 문자열). 백엔드 agent_id 와 1:1. */
const AGENT_ICONS: Record<AgentId, string> = {
  market_analyst: marketIcon,
  population_analyst: populationIcon,
  legal: legalIcon,
  district_ranking: rankingIcon,
  inflow: inflowIcon,
  synthesis: synthesisIcon,
  demographic_depth: demographicIcon,
  trend_forecaster: trendIcon,
  competitor_intel: competitorIcon,
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
  const iconSrc = AGENT_ICONS[attribution.id];
  const accentColor = AGENT_COLORS[attribution.id];
  const kindCls = KIND_BADGE[attribution.kind];

  if (size === 'compact') {
    return (
      <button
        type="button"
        onClick={onExpand}
        className="flex w-full items-center gap-2 rounded-md border border-border bg-card p-2 text-left hover:bg-muted transition-colors"
      >
        {iconSrc ? (
          <img
            src={iconSrc}
            alt={attribution.display_name}
            className="h-9 w-9 shrink-0 object-contain"
            loading="lazy"
          />
        ) : null}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-semibold truncate ${accentColor}`}>
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
        {iconSrc ? (
          <img
            src={iconSrc}
            alt={attribution.display_name}
            className="h-14 w-14 shrink-0 object-contain"
            loading="lazy"
          />
        ) : null}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className={`text-sm font-semibold ${accentColor}`}>{attribution.display_name}</h3>
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
