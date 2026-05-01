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
    color: 'text-blue-400',
    borderCls: 'border-blue-500/30 hover:border-blue-500/70',
    iconBgCls: 'bg-blue-500/10 border-blue-500/30',
    desc: 'market_analyst',
  },
  {
    id: 'population',
    name: '유동 인구',
    icon: Users,
    color: 'text-emerald-400',
    borderCls: 'border-emerald-500/30 hover:border-emerald-500/70',
    iconBgCls: 'bg-emerald-500/10 border-emerald-500/30',
    desc: 'population_analyst',
  },
  {
    id: 'demographic',
    name: '인구 심층',
    icon: PieChart,
    color: 'text-indigo-400',
    borderCls: 'border-indigo-500/30 hover:border-indigo-500/70',
    iconBgCls: 'bg-indigo-500/10 border-indigo-500/30',
    desc: 'demographic_depth',
  },
  {
    id: 'competitor',
    name: '경쟁 분석',
    icon: ShieldAlert,
    color: 'text-amber-400',
    borderCls: 'border-amber-500/30 hover:border-amber-500/70',
    iconBgCls: 'bg-amber-500/10 border-amber-500/30',
    desc: 'competitor_intel',
  },
  {
    id: 'legal',
    name: '법률 리스크',
    icon: AlertTriangle,
    color: 'text-rose-400',
    borderCls: 'border-rose-500/30 hover:border-rose-500/70',
    iconBgCls: 'bg-rose-500/10 border-rose-500/30',
    desc: 'legal_agent',
  },
  {
    id: 'trend',
    name: '트렌드 예측',
    icon: TrendingUp,
    color: 'text-cyan-400',
    borderCls: 'border-cyan-500/30 hover:border-cyan-500/70',
    iconBgCls: 'bg-cyan-500/10 border-cyan-500/30',
    desc: 'trend_forecaster',
  },
  {
    id: 'ranking',
    name: '입지 랭킹',
    icon: Layers,
    color: 'text-violet-400',
    borderCls: 'border-violet-500/30 hover:border-violet-500/70',
    iconBgCls: 'bg-violet-500/10 border-violet-500/30',
    desc: 'district_ranking',
  },
  {
    id: 'synthesis',
    name: '종합 전략',
    icon: BrainCircuit,
    color: 'text-white',
    borderCls: 'border-stone-400/40 hover:border-stone-200/80',
    iconBgCls: 'bg-stone-200/5 border-stone-400/40',
    desc: 'synthesis_agent',
  },
];
