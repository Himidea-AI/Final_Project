/**
 * Shared agent definitions — 8 LangGraph 에이전트 메타.
 * 2026-04-28 H7 — TabbedDashboard 삭제 시 InsightTab/HistoryDashboardView가 공통 참조하도록 분리.
 */

import {
  BarChart3,
  BrainCircuit,
  TrendingUp,
  Users,
  PieChart,
  ShieldAlert,
  AlertTriangle,
  Layers,
  type LucideIcon,
} from 'lucide-react';

export interface AgentDef {
  id: string;
  name: string;
  icon: LucideIcon;
  color: string;
  /** 컨테이너 보더 색 (아이콘 컬러에 맞춘 정적 Tailwind 클래스). 시인성 강조용. */
  borderCls: string;
  /** 아이콘 박스 배경 (정적 Tailwind 클래스 — JIT가 빌드에 포함시키도록 동적 보간 금지). */
  iconBgCls: string;
  desc: string;
}

export const AGENTS_LIST: AgentDef[] = [
  {
    id: 'market',
    name: '시장 분석',
    icon: BarChart3,
    color: 'text-primary',
    borderCls: 'border-primary/30 hover:border-primary/70',
    iconBgCls: 'bg-primary/10 border-primary/30',
    desc: 'market_analyst',
  },
  {
    id: 'population',
    name: '유동 인구',
    icon: Users,
    color: 'text-success',
    borderCls: 'border-success/30 hover:border-success/70',
    iconBgCls: 'bg-success/10 border-success/30',
    desc: 'population_analyst',
  },
  {
    id: 'demographic',
    name: '인구 심층',
    icon: PieChart,
    color: 'text-primary',
    borderCls: 'border-primary/30 hover:border-primary/70',
    iconBgCls: 'bg-primary/10 border-primary/30',
    desc: 'demographic_depth',
  },
  {
    id: 'competitor',
    name: '경쟁 분석',
    icon: ShieldAlert,
    color: 'text-warning',
    borderCls: 'border-warning/30 hover:border-warning/70',
    iconBgCls: 'bg-warning/10 border-warning/30',
    desc: 'competitor_intel',
  },
  {
    id: 'legal',
    name: '법률 리스크',
    icon: AlertTriangle,
    color: 'text-danger',
    borderCls: 'border-danger/30 hover:border-danger/70',
    iconBgCls: 'bg-danger/10 border-danger/30',
    desc: 'legal_agent',
  },
  {
    id: 'trend',
    name: '트렌드 예측',
    icon: TrendingUp,
    color: 'text-primary',
    borderCls: 'border-primary/30 hover:border-primary/70',
    iconBgCls: 'bg-primary/10 border-primary/30',
    desc: 'trend_forecaster',
  },
  {
    id: 'ranking',
    name: '입지 랭킹',
    icon: Layers,
    color: 'text-primary',
    borderCls: 'border-primary/30 hover:border-primary/70',
    iconBgCls: 'bg-primary/10 border-primary/30',
    desc: 'district_ranking',
  },
  {
    id: 'synthesis',
    name: '종합 전략',
    icon: BrainCircuit,
    color: 'text-white',
    borderCls: 'border-border/40 hover:border-border/80',
    iconBgCls: 'bg-muted/5 border-border/40',
    desc: 'synthesis_agent',
  },
];
