/**
 * TabbedDashboard — SPOTTER v5 대시보드 (3그룹 IA 재구조)
 *
 * 구조: Compact Sticky Header + 3 그룹 (예측 결과 / AI 분석 / ABM 시뮬레이터)
 * 각 그룹 wrapper 가 내부에서 ?sub=... 서브탭 라우팅 담당.
 * 원칙: Bento Grid, Contextual AI Attribution, LangGraph 기반 8대 멀티 에이전트 시스템
 */

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart3,
  BrainCircuit,
  TrendingUp,
  Users,
  PieChart,
  ShieldAlert,
  AlertTriangle,
  Layers,
  Activity,
  type LucideIcon,
} from 'lucide-react';
import type { SimulationOutput, MainTab } from '../../../types';
import { formatDocumentId } from '../../../types/simulationHistory';
import { TabButton } from './shared/TabButton';
import { DetailModal, type DetailModalContent } from './shared/DetailModal';
import { GradeCard } from './shared/GradeCard';
import { KpiMiniGrid, type KpiItem } from './shared/KpiMiniGrid';
import { NarrativeText } from './shared/NarrativeText';
import { PredictGroup } from './groups/PredictGroup';
import { AnalyzeGroup } from './groups/AnalyzeGroup';
import { AbmGroup } from './groups/AbmGroup';
import { getGrade } from '../../../constants/decisionThresholds';
import { formatKrw, formatScore } from './utils/formatters';

const VALID_GROUPS: MainTab[] = ['predict', 'analyze', 'abm'];

const GROUP_TABS: { id: MainTab; label: string; icon: LucideIcon }[] = [
  { id: 'predict', label: '예측 결과', icon: TrendingUp },
  { id: 'analyze', label: 'AI 분석', icon: BrainCircuit },
  { id: 'abm', label: 'ABM 시뮬레이터', icon: Activity },
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
  // URL ?group= deep link sync — 새로고침 / 공유 링크 지원
  // 그룹 전환 시 ?sub= 는 초기화 (각 그룹 wrapper 가 자기 default sub 로 fallback).
  const [searchParams, setSearchParams] = useSearchParams();
  const groupFromUrl = searchParams.get('group') as MainTab | null;
  const activeGroup: MainTab =
    groupFromUrl && VALID_GROUPS.includes(groupFromUrl) ? groupFromUrl : 'predict';

  const setGroup = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('group', id);
    next.delete('sub'); // 그룹 전환 시 sub 초기화
    setSearchParams(next, { replace: true });
  };

  // Compact Sticky Header — 스크롤 감지
  // SimulatorDashboard는 window가 아니라 내부 overflow-y-auto 컨테이너(dashboardRef)에서 스크롤.
  // 루트 ref 기준으로 스크롤 부모를 자동 탐색해 그 element의 scroll event 구독.
  // isScrolled: 50px 초과 시 헤더 축소 (py-8 → py-3, 타이틀 text-4xl → text-xl).
  // isHidden: 200px 초과 + 아래 방향 스크롤 시 헤더 자체를 위로 슬라이드 (콘텐츠 가림 해소).
  //          위로 스크롤 시 즉시 복귀.
  const rootRef = useRef<HTMLDivElement>(null);
  const [isScrolled, setIsScrolled] = useState(false);
  const [isHidden, setIsHidden] = useState(false);
  const lastScrollTop = useRef(0);
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
    const onScroll = () => {
      const top = getScrollTop();
      setIsScrolled(top > 50);
      // hysteresis: HIDE_AT(200) 초과 + 아래로 → hide. SHOW_AT(50) 미만 도달 시에만 show.
      // 중간 영역에서 위로 올려도 hidden 유지 → 사용자가 "맨 꼭대기"까지 가야 다시 등장.
      const HIDE_AT = 200;
      const SHOW_AT = 50;
      if (top > HIDE_AT && top > lastScrollTop.current) {
        setIsHidden(true);
      } else if (top < SHOW_AT) {
        setIsHidden(false);
      }
      lastScrollTop.current = top;
    };
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
  const ci = simResult?.competitor_intel ?? null;
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
      {/* ════════════════ EXCLUDED COMBO MOCK BANNER (Critical #1) ════════════════
           api-contract §3.7 — 본부 영업팀이 mock을 실데이터로 오인하면 법적·신뢰 리스크.
           sticky 밖에 배치 → 페이지 진입 시 1회 인지, 스크롤하면 자연스레 사라짐. */}
      {simResult?.is_excluded_combo === true && (
        <div className="mx-auto max-w-[1728px] px-8 pt-4">
          <div
            role="alert"
            className="bg-rose-500/10 border border-rose-500/30 text-rose-300 px-4 py-2 rounded-lg flex items-center gap-2 text-xs font-medium"
          >
            <AlertTriangle size={14} className="shrink-0" />
            <span>
              이 업종/지역 조합은 학습 데이터 부족으로 mock 결과가 반환됩니다. 실데이터 분석은 다른
              조합으로 시도해주세요.
            </span>
          </div>
        </div>
      )}
      {/* ════════════════ STICKY HEADER (v4.3 리디자인) ════════════════ */}
      {/* 위치: top-24 md:top-28 — 글로벌 header(App.tsx:4490, fixed top-0 h-24, z-50) 바로 아래.
           SimulatorDashboard 컨테이너 padding-top과 일관(pt-24 md:pt-28).
         배경: 불투명 solid (#0C0B0A) — 반투명/blur면 스크롤 시 하단 콘텐츠(지도·차트)가
           sticky 뒤로 비치는 "레이어 누수" 발생. solid로 차단.
         z-50: 글로벌 header와 같은 레벨. SimulatorDashboard 컨테이너(z-40) 위. */}
      <header
        className={`sticky top-24 md:top-28 z-50 bg-[#0C0B0A] border-b border-stone-800/40 ${
          isScrolled ? 'py-3 shadow-2xl' : 'py-8'
        }`}
        style={{
          // transform/opacity는 스크롤 따라가는 fast path (180/150ms),
          // padding/box-shadow는 isScrolled 축소 모션 그대로 (500ms 우아).
          transform: isHidden ? 'translateY(-100%)' : 'translateY(0)',
          opacity: isHidden ? 0 : 1,
          pointerEvents: isHidden ? 'none' : 'auto',
          transition:
            'transform 180ms cubic-bezier(0.4, 0, 0.2, 1), ' +
            'opacity 150ms cubic-bezier(0.4, 0, 0.2, 1), ' +
            'padding 500ms cubic-bezier(0.4, 0, 0.2, 1), ' +
            'box-shadow 500ms cubic-bezier(0.4, 0, 0.2, 1)',
        }}
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
                        onClick={() => {
                          // Agents 배지 클릭 → AI 분석 그룹의 에이전트 근거 서브탭으로 이동
                          const next = new URLSearchParams(searchParams);
                          next.set('group', 'analyze');
                          next.set('sub', 'agent_insight');
                          setSearchParams(next, { replace: true });
                        }}
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

          {/* 탭 네비게이션 (3 그룹) */}
          <nav className="flex gap-3 mt-6 border-t border-stone-800/30 pt-2 overflow-x-auto scrollbar-hide">
            {GROUP_TABS.map((t) => (
              <TabButton
                key={t.id}
                id={t.id}
                label={t.label}
                icon={t.icon}
                active={activeGroup === t.id}
                onClick={setGroup}
              />
            ))}
          </nav>
        </div>
      </header>

      {/* ════════════════ MAIN CONTENT ════════════════ */}
      <main className="mx-auto max-w-[1728px] px-8 py-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeGroup}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.2 }}
          >
            {activeGroup === 'predict' && (
              <PredictGroup simResult={simResult} openModal={openModal} />
            )}
            {activeGroup === 'analyze' && (
              <AnalyzeGroup simResult={simResult} openModal={openModal} />
            )}
            {activeGroup === 'abm' && (
              <AbmGroup simResult={simResult} brandName={brandName} businessType={businessType} />
            )}
          </motion.div>
        </AnimatePresence>
      </main>

      {/* ════════════════ DETAIL MODAL ════════════════ */}
      <DetailModal modalContent={modalContent} onClose={() => setModalContent(null)} />
    </div>
  );
}
