/**
 * Shared agent definitions — 9 LangGraph 에이전트 메타.
 *
 * 2026-04-28 H7 — TabbedDashboard 삭제 시 InsightTab/HistoryDashboardView가 공통 참조하도록 분리.
 * 2026-05-04 (강민) — lucide LucideIcon → 자체 페르소나 PNG 9개로 교체.
 *   AgentDef.icon (LucideIcon) → AgentDef.iconSrc (png URL).
 *   사용처 (InsightTab / DecisionCard) 가 <img> 로 렌더.
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

export interface AgentDef {
  /** 표시용 id (UI 라우팅 / mapping). 백엔드 agent_id 와 다를 수 있음 (예: market ↔ market_analyst). */
  id: string;
  name: string;
  /** 자체 페르소나 PNG URL. <img src={iconSrc} ... /> 로 렌더. */
  iconSrc: string;
  color: string;
  /** 컨테이너 보더 색 (정적 Tailwind 클래스). */
  borderCls: string;
  /** 아이콘 박스 배경 (정적 Tailwind 클래스 — JIT 빌드 포함을 위해 동적 보간 금지). */
  iconBgCls: string;
  desc: string;
}

export const AGENTS_LIST: AgentDef[] = [
  {
    id: 'market',
    name: '시장 분석',
    iconSrc: marketIcon,
    color: 'text-primary',
    borderCls: 'border-primary/30 hover:border-primary/70',
    iconBgCls: 'bg-primary/10 border-primary/30',
    desc: 'market_analyst',
  },
  {
    id: 'population',
    name: '유동 인구',
    iconSrc: populationIcon,
    color: 'text-success',
    borderCls: 'border-success/30 hover:border-success/70',
    iconBgCls: 'bg-success/10 border-success/30',
    desc: 'population_analyst',
  },
  {
    id: 'demographic',
    name: '인구 심층',
    iconSrc: demographicIcon,
    color: 'text-primary',
    borderCls: 'border-primary/30 hover:border-primary/70',
    iconBgCls: 'bg-primary/10 border-primary/30',
    desc: 'demographic_depth',
  },
  {
    id: 'competitor',
    name: '경쟁 분석',
    iconSrc: competitorIcon,
    color: 'text-warning',
    borderCls: 'border-warning/30 hover:border-warning/70',
    iconBgCls: 'bg-warning/10 border-warning/30',
    desc: 'competitor_intel',
  },
  {
    id: 'legal',
    name: '법률 리스크',
    iconSrc: legalIcon,
    color: 'text-danger',
    borderCls: 'border-danger/30 hover:border-danger/70',
    iconBgCls: 'bg-danger/10 border-danger/30',
    desc: 'legal_agent',
  },
  {
    id: 'trend',
    name: '트렌드 예측',
    iconSrc: trendIcon,
    color: 'text-primary',
    borderCls: 'border-primary/30 hover:border-primary/70',
    iconBgCls: 'bg-primary/10 border-primary/30',
    desc: 'trend_forecaster',
  },
  {
    id: 'ranking',
    name: '입지 랭킹',
    iconSrc: rankingIcon,
    color: 'text-primary',
    borderCls: 'border-primary/30 hover:border-primary/70',
    iconBgCls: 'bg-primary/10 border-primary/30',
    desc: 'district_ranking',
  },
  {
    id: 'inflow',
    name: '접근성',
    iconSrc: inflowIcon,
    color: 'text-success',
    borderCls: 'border-success/30 hover:border-success/70',
    iconBgCls: 'bg-success/10 border-success/30',
    desc: 'inflow (Hansen + E2SFCA)',
  },
  {
    id: 'synthesis',
    name: '종합 전략',
    iconSrc: synthesisIcon,
    color: 'text-foreground',
    borderCls: 'border-border/40 hover:border-border/80',
    iconBgCls: 'bg-muted/5 border-border/40',
    desc: 'synthesis_agent',
  },
];
