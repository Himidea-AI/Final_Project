/**
 * TabbedDashboard — SPOTTER v4.2 대시보드 리디자인
 *
 * 구조: Compact Sticky Header + 4 탭 (종합 요약 / 상권 분석 / 매출 예측 / AI 분석 근거)
 * 원칙: Bento Grid, Contextual AI Attribution, LangGraph 기반 8대 멀티 에이전트 시스템
 */

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart3,
  BrainCircuit,
  MapPin,
  TrendingUp,
  Users,
  PieChart,
  ShieldAlert,
  AlertTriangle,
  Layers,
  Activity,
  Scale,
  Radar,
  type LucideIcon,
} from 'lucide-react';
import type { SimulationOutput } from '../../../types';
import { formatDocumentId } from '../../../types/simulationHistory';
import { TabButton } from './shared/TabButton';
import { DetailModal, type DetailModalContent } from './shared/DetailModal';
import { GradeCard } from './shared/GradeCard';
import { KpiMiniGrid, type KpiItem } from './shared/KpiMiniGrid';
import { NarrativeText } from './shared/NarrativeText';
import { SummaryTab } from './tabs/SummaryTab';
import { MarketTab } from './tabs/MarketTab';
import { AbmTab } from './tabs/AbmTab';
import { DemographicTab } from './tabs/DemographicTab';
import { FinancialTab } from './tabs/FinancialTab';
import { ForecastTab } from './tabs/ForecastTab';
import { LegalTab } from './tabs/LegalTab';
import { InsightTab } from './tabs/InsightTab';
import { getGrade } from '../../../constants/decisionThresholds';
import { formatKrw, formatScore } from './utils/formatters';

const TABS = {
  SUMMARY: 'summary',
  MARKET: 'market',
  ABM: 'abm',
  DEMOGRAPHIC: 'demographic',
  FINANCIAL: 'financial',
  FORECAST: 'forecast',
  LEGAL: 'legal',
  INSIGHT: 'insight',
} as const;

type TabKey = (typeof TABS)[keyof typeof TABS];

// 탭 순서 규칙: 첫 = 요약, 끝 = AI 분석근거 (고정). 중간 흐름:
// 상권(지리) → ABM(공실 시뮬) → 인구(사람) → 재무(돈) → 예측(미래) → 법률(규제)
const TAB_ORDER: TabKey[] = [
  TABS.SUMMARY,
  TABS.MARKET,
  TABS.ABM,
  TABS.DEMOGRAPHIC,
  TABS.FINANCIAL,
  TABS.FORECAST,
  TABS.LEGAL,
  TABS.INSIGHT,
];

interface AgentDef {
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

interface TabbedDashboardProps {
  simResult: SimulationOutput | null;
  /** ABM /simulate-abm POST 호출에 필요 (없으면 기본 'cafe') */
  businessType?: string | null;
  /** 상위 SimulatorDashboard 헤더의 기존 버튼을 사용하므로, 이 props들은 호환성 유지용 (옵셔널). */
  onExportPdf?: () => void;
  onExportXlsx?: () => void;
  onSaveClick?: () => void;
  savedHistoryId?: number | null;
  /** 상단 Hero 브랜드명 (user.company_name) */
  brandName: string;
}

export function TabbedDashboard({
  simResult,
  savedHistoryId = null,
  brandName,
  businessType = null,
}: TabbedDashboardProps) {
  // URL ?tab= deep link sync — 새로고침 / 공유 링크 지원
  const [searchParams, setSearchParams] = useSearchParams();
  const urlTab = searchParams.get('tab') as TabKey | null;
  const [activeTab, setActiveTab] = useState<TabKey>(
    urlTab && TAB_ORDER.includes(urlTab) ? urlTab : TABS.SUMMARY,
  );

  const handleTabChange = (id: string) => {
    const tab = id as TabKey;
    setActiveTab(tab);
    // ?tab=forecast 같이 쿼리 업데이트 (history 누적 X)
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', tab);
        return next;
      },
      { replace: true },
    );
  };

  // URL 쿼리 외부 변경 감지 (뒤로가기 등)
  useEffect(() => {
    if (urlTab && TAB_ORDER.includes(urlTab) && urlTab !== activeTab) {
      setActiveTab(urlTab);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlTab]);

  // Compact Sticky Header — 스크롤 감지
  // SimulatorDashboard는 window가 아니라 내부 overflow-y-auto 컨테이너(dashboardRef)에서 스크롤.
  // 루트 ref 기준으로 스크롤 부모를 자동 탐색해 그 element의 scroll event 구독.
  const rootRef = useRef<HTMLDivElement>(null);
  const [isScrolled, setIsScrolled] = useState(false);
  useEffect(() => {
    const findScrollParent = (el: HTMLElement | null): HTMLElement | Window => {
      let cur = el?.parentElement ?? null;
      while (cur) {
        const overflowY = window.getComputedStyle(cur).overflowY;
        if (overflowY === 'auto' || overflowY === 'scroll') return cur;
        cur = cur.parentElement;
      }
      return window;
    };
    const scrollSrc = findScrollParent(rootRef.current);
    const getScrollTop = () =>
      scrollSrc === window ? window.scrollY : (scrollSrc as HTMLElement).scrollTop;
    const onScroll = () => setIsScrolled(getScrollTop() > 50);
    // 초기 상태 체크 — 히스토리 복귀 시 이미 스크롤된 상태일 수 있음
    onScroll();
    (scrollSrc as HTMLElement | Window).addEventListener('scroll', onScroll, { passive: true });
    return () => {
      (scrollSrc as HTMLElement | Window).removeEventListener('scroll', onScroll);
    };
  }, []);

  // 상세 모달
  const [modalContent, setModalContent] = useState<DetailModalContent | null>(null);
  const openModal = (content: DetailModalContent) => setModalContent(content);

  // 실데이터 기반 헤더 정보 조립
  const ci = simResult?.competitor_intel as Record<string, any> | null | undefined;
  const winnerDistrict = simResult?.winner_district || simResult?.target_district || '—';
  const documentId = formatDocumentId(savedHistoryId);

  // GRADE 매핑
  const gradeInfo = getGrade(simResult?.analysis_metrics?.district_grade);
  const synthAttr = simResult?.agent_attributions?.find((a) => a.id === 'synthesis');
  const confidencePct =
    synthAttr?.confidence != null ? Math.round(synthAttr.confidence * 100) : null;

  // Narrative subtitle (final_recommendation 80자 trim)
  const narrative =
    simResult?.final_report?.final_recommendation?.slice(0, 140) ??
    simResult?.ai_recommendation?.slice(0, 140) ??
    null;

  // KPI 4 mini grid — delta 없음, 실데이터만
  const kpiItems: KpiItem[] = (() => {
    if (!simResult) return [];
    const qp = simResult.quarterly_projection ?? [];
    const monthlyRev =
      simResult.final_report?.profit_simulation?.monthly_revenue ??
      (qp[0]?.revenue ? Math.round(qp[0].revenue / 3) : null);
    const compIntensity = simResult.market_report?.competition_intensity;
    const comp500 = ci?.competition_500m?.count ?? null;
    // 실데이터 원칙: legal_risks 자체가 null/undefined면 "법률 분석 미실행"
    // 빈 배열 []은 "분석 완료 + 리스크 없음"으로 구분 (B1 status 필드 도입 전 임시 가정)
    const legalAnalyzed = Array.isArray(simResult.legal_risks);
    const legalRisks = simResult.legal_risks ?? [];
    const dangerLegalCount = legalRisks.filter(
      (r) => String(r.risk_level).toUpperCase() === 'HIGH' || r.risk_level === 'danger',
    ).length;
    const totalLegal = legalRisks.length;

    return [
      {
        label: '예상 월매출',
        value: monthlyRev != null ? `₩${formatKrw(monthlyRev)}` : '—',
        sub: 'profit_simulation',
        spark: qp.map((q) => q.revenue),
      },
      {
        label: '유동인구 점수',
        value:
          simResult.market_report?.floating_population != null
            ? `${formatScore(simResult.market_report.floating_population)}/100`
            : '—',
        sub: `${winnerDistrict} · 동 기준`,
        // 0~100 정규화된 floating_population을 그대로 progress bar에 사용. tagColor 미지정 → cyan
        score: simResult.market_report?.floating_population ?? null,
        bullet: {
          actual: simResult.market_report?.floating_population ?? null,
          target: 70,
          max: 100,
          thresholds: [40, 70] as [number, number],
        },
      },
      {
        label: '경쟁 강도',
        value: compIntensity != null ? `${formatScore(compIntensity)}/100` : '—',
        tag:
          compIntensity != null
            ? compIntensity >= 70
              ? 'HIGH'
              : compIntensity >= 40
                ? 'MID'
                : 'LOW'
            : undefined,
        // 데이터 없음 → stone(중립). 이전엔 기본 'emerald'(안전색)로 거짓 안전 신호 유발.
        tagColor:
          compIntensity == null
            ? ('stone' as const)
            : compIntensity >= 70
              ? ('rose' as const)
              : compIntensity >= 40
                ? ('amber' as const)
                : ('emerald' as const),
        sub: comp500 != null ? `500m 내 ${comp500}개` : undefined,
        score: compIntensity ?? null,
      },
      {
        label: '법률 리스크',
        // legal_risks 자체가 null이면 "분석 미실행". 빈 배열과 구분.
        value: !legalAnalyzed ? '—' : totalLegal === 0 ? '0건' : `${dangerLegalCount}건`,
        tag: !legalAnalyzed ? '미분석' : dangerLegalCount > 0 ? 'DANGER' : 'SAFE',
        tagColor: !legalAnalyzed
          ? ('stone' as const)
          : dangerLegalCount > 0
            ? ('rose' as const)
            : ('emerald' as const),
        sub: legalAnalyzed ? `${totalLegal}항목 중` : 'legal agent 대기',
        // 위험 비율 — 분석 안 됐거나 항목 0개면 null (0/0 = NaN 회피)
        score:
          !legalAnalyzed || totalLegal === 0
            ? null
            : Math.round((dangerLegalCount / totalLegal) * 100),
      },
    ];
  })();

  const today = new Date().toISOString().slice(0, 10);
  const agentCount = simResult?.agent_attributions?.length ?? 0;

  if (!simResult) return null;

  return (
    <div
      ref={rootRef}
      className="min-h-screen bg-[#0C0B0A] text-stone-200 font-sans selection:bg-indigo-500/30 relative"
    >
      {/* 도트-그리드 텍스쳐 — 전체 배경의 정보 밀도 감 상승 (opacity 3%) */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.035]"
        aria-hidden="true"
        style={{
          backgroundImage: 'radial-gradient(#ffffff 1px, transparent 0)',
          backgroundSize: '24px 24px',
        }}
      />
      {/* ════════════════ STICKY HEADER (v4.3 리디자인) ════════════════ */}
      {/* top-24 md:top-28: 글로벌 header(App.tsx:4490, fixed top-0 h-24, z-50) 바로 아래에 붙도록 보정.
           top-0이면 글로벌 header에 위쪽 96px이 가려지고, 두 header 배경(반투명)의 색차로
           "틈"이 보였음. SimulatorDashboard 컨테이너 padding-top과도 일관(pt-24 md:pt-28). */}
      <header
        className={`sticky top-24 md:top-28 z-40 bg-[#0C0B0A]/90 backdrop-blur-2xl border-b border-stone-800/40 transition-all duration-500 ${
          isScrolled ? 'py-3 shadow-2xl' : 'py-8'
        }`}
      >
        <div className="mx-auto max-w-[1728px] px-8">
          {/* ── 상단: 타이틀 + GRADE 카드 ── */}
          <div className="flex justify-between items-start gap-6">
            <div className="flex flex-col text-left flex-1 min-w-0">
              {/* 메타 브레드크럼 — cyan 시그니처 dot로 SPOTTER 브랜드 식별 */}
              <div className="flex items-center gap-3 text-[10px] font-black text-stone-500 tracking-[0.25em] mb-3 uppercase">
                <span className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.8)]" />
                  <span className="text-stone-300">SPOTTER</span>
                </span>
                <span className="w-1 h-1 rounded-full bg-stone-700" />
                <span>Simulation Result</span>
                <span className="w-1 h-1 rounded-full bg-stone-700" />
                <span className="text-stone-400 tabular-nums">{today}</span>
                <span className="w-1 h-1 rounded-full bg-stone-700" />
                <span className="text-stone-400 tabular-nums">{documentId}</span>
              </div>

              {/* 메인 타이틀 — text-4xl (스크롤 시 축소) */}
              <div className="flex flex-wrap items-center gap-4 mb-2">
                <h1
                  className={`font-black text-stone-100 tracking-tighter transition-all ${
                    isScrolled ? 'text-xl' : 'text-4xl'
                  }`}
                >
                  {brandName || '미지정 브랜드'}
                </h1>
                {!isScrolled && (
                  <div className="flex items-center gap-2 text-stone-400 text-lg font-medium">
                    {simResult.target_district && (
                      <>
                        <span className="w-1 h-1 rounded-full bg-stone-700" />
                        <span>{winnerDistrict}</span>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Narrative subtitle — 숫자·퍼센트 cyan 하이라이트 */}
              {!isScrolled && narrative && (
                <NarrativeText
                  text={narrative}
                  className="text-sm text-stone-500 max-w-2xl leading-relaxed mt-1 font-medium"
                />
              )}
            </div>

            {/* 우측: GRADE 카드 (스크롤 시 숨김) */}
            {!isScrolled && (
              <GradeCard
                letter={gradeInfo.letter}
                color={gradeInfo.color}
                confidencePct={confidencePct}
              />
            )}
          </div>

          {/* ── KPI 4 Mini Grid (스크롤 시 숨김) ── */}
          <AnimatePresence>
            {!isScrolled && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
              >
                <KpiMiniGrid items={kpiItems} />
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Agents 배지 (정사각 8개) + 카운트 ── */}
          <AnimatePresence>
            {!isScrolled && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-8 pt-6 border-t border-stone-800/40 flex items-center gap-6"
              >
                <div className="text-[10px] font-black text-stone-500 uppercase tracking-[0.2em] shrink-0">
                  Agents · <span className="text-cyan-400 tabular-nums">{agentCount}</span>
                  <span className="text-stone-600">/8</span>
                </div>
                <div className="flex gap-2 overflow-x-auto scrollbar-hide">
                  {AGENTS_LIST.map((agent) => {
                    const AgentIcon = agent.icon;
                    return (
                      <button
                        key={agent.id}
                        type="button"
                        onClick={() => handleTabChange(TABS.INSIGHT)}
                        title={`${agent.name} · ${agent.desc}`}
                        className={`w-9 h-9 rounded-xl bg-stone-900/60 border-2 ${agent.borderCls} flex items-center justify-center group hover:bg-stone-900 transition-all shrink-0 shadow-inner`}
                      >
                        <AgentIcon
                          size={14}
                          className={`${agent.color} opacity-60 group-hover:opacity-100 transition-opacity`}
                        />
                      </button>
                    );
                  })}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* 탭 네비게이션 (7개) */}
          <nav className="flex mt-6 border-t border-stone-800/30 pt-2 overflow-x-auto scrollbar-hide">
            <TabButton
              id={TABS.SUMMARY}
              label="요약"
              icon={BarChart3}
              active={activeTab === TABS.SUMMARY}
              onClick={handleTabChange}
            />
            <TabButton
              id={TABS.MARKET}
              label="상권·위치"
              icon={MapPin}
              active={activeTab === TABS.MARKET}
              onClick={handleTabChange}
            />
            <TabButton
              id={TABS.ABM}
              label="ABM"
              icon={Radar}
              active={activeTab === TABS.ABM}
              onClick={handleTabChange}
            />
            <TabButton
              id={TABS.DEMOGRAPHIC}
              label="인구·고객"
              icon={Users}
              active={activeTab === TABS.DEMOGRAPHIC}
              onClick={handleTabChange}
            />
            <TabButton
              id={TABS.FINANCIAL}
              label="재무·수익성"
              icon={Activity}
              active={activeTab === TABS.FINANCIAL}
              onClick={handleTabChange}
            />
            <TabButton
              id={TABS.FORECAST}
              label="예측"
              icon={TrendingUp}
              active={activeTab === TABS.FORECAST}
              onClick={handleTabChange}
            />
            <TabButton
              id={TABS.LEGAL}
              label="법률·규제"
              icon={Scale}
              active={activeTab === TABS.LEGAL}
              onClick={handleTabChange}
            />
            <TabButton
              id={TABS.INSIGHT}
              label="AI 분석 근거"
              icon={BrainCircuit}
              active={activeTab === TABS.INSIGHT}
              onClick={handleTabChange}
            />
          </nav>
        </div>
      </header>

      {/* ════════════════ MAIN CONTENT ════════════════ */}
      <main className="mx-auto max-w-[1728px] px-8 py-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === TABS.SUMMARY && (
              <SummaryTab simResult={simResult} openModal={openModal} />
            )}
            {activeTab === TABS.MARKET && <MarketTab simResult={simResult} openModal={openModal} />}
            {activeTab === TABS.ABM && (
              <AbmTab simResult={simResult} brandName={brandName} businessType={businessType} />
            )}
            {activeTab === TABS.DEMOGRAPHIC && <DemographicTab simResult={simResult} />}
            {activeTab === TABS.FINANCIAL && <FinancialTab simResult={simResult} />}
            {activeTab === TABS.FORECAST && (
              <ForecastTab simResult={simResult} openModal={openModal} />
            )}
            {activeTab === TABS.LEGAL && <LegalTab simResult={simResult} openModal={openModal} />}
            {activeTab === TABS.INSIGHT && (
              <InsightTab simResult={simResult} openModal={openModal} />
            )}
          </motion.div>
        </AnimatePresence>
      </main>

      {/* ════════════════ DETAIL MODAL ════════════════ */}
      <DetailModal modalContent={modalContent} onClose={() => setModalContent(null)} />
    </div>
  );
}
