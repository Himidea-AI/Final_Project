/**
 * DashboardPanelView — VS 비교 모드용 압축 대시보드 패널 (App.tsx에서 추출).
 * 하단 보조 컴포넌트 4종(StatCard, SortHeader, TableRow, InsightCard)도 동봉.
 * simResult.districtRankings / simResult.comparison에서 dongName 매칭으로 실데이터 렌더.
 */

import React from 'react';
import {
  ChevronRight,
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  ThumbsUp,
  ThumbsDown,
  TrendingUp,
  TrendingDown,
  MapPin,
  Scale,
  Users,
} from 'lucide-react';
import { useToast } from '../Toast';
import type { SimResult } from '../../viewmodels/simResult';
import { formatKrw } from '../SimulationResult/dashboard/utils/formatters';

export function StatCard({
  title,
  value,
  trend,
  trendUp,
  icon,
  sparkline,
  onClick,
  subtitle,
}: {
  title: string;
  value: string;
  trend: string;
  trendUp: boolean;
  icon: React.ReactElement;
  sparkline: string;
  onClick?: () => void;
  subtitle?: string;
}) {
  return (
    <div
      onClick={onClick}
      className="bg-card border border-border p-6 rounded-xl flex flex-col justify-between gap-3 group cursor-pointer hover:border-primary hover:shadow-[0_0_20px_rgba(0,44,209,0.2)] transition-all min-h-[130px]"
    >
      <div className="flex justify-between items-start">
        <p className="text-muted-foreground text-xs font-medium">{title}</p>
        <div className="flex items-center gap-1.5">
          {subtitle && (
            <span className="text-[0.5625rem] text-muted-foreground opacity-50 font-mono">
              {subtitle}
            </span>
          )}
          <div className="text-muted-foreground opacity-50 group-hover:opacity-100 group-hover:text-primary transition-colors">
            {React.cloneElement(icon, {
              className: 'w-4 h-4',
            } as React.HTMLAttributes<HTMLElement>)}
          </div>
        </div>
      </div>
      <div>
        <h3 className="text-xl md:text-2xl font-black text-foreground tracking-tight mb-1">
          {value}
        </h3>
        <div className="flex items-center justify-between">
          <span
            className={`text-[0.625rem] font-bold flex items-center gap-0.5 ${trendUp ? 'text-success' : 'text-danger'}`}
          >
            {trendUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}{' '}
            {trend}
          </span>
          <svg
            viewBox="0 0 100 30"
            className="w-12 h-4 overflow-visible opacity-50 group-hover:opacity-100 transition-opacity"
          >
            <path
              d={sparkline}
              fill="none"
              stroke={trendUp ? 'var(--success)' : 'var(--danger)'}
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   SortHeader — 정렬 가능한 테이블 컬럼 헤더
   ═══════════════════════════════════════════════════════ */
export function SortHeader({
  label,
  sortField,
  sortKey,
  sortDir,
  onSort,
}: {
  label: string;
  sortField: string;
  sortKey: string | null;
  sortDir: 'asc' | 'desc';
  onSort: (key: string) => void;
}) {
  const isActive = sortKey === sortField;
  return (
    <span
      onClick={() => onSort(sortField)}
      className={`inline-flex items-center gap-1 cursor-pointer transition-colors select-none ${
        isActive ? 'text-primary' : 'hover:text-foreground'
      }`}
    >
      {label}
      {isActive ? (
        sortDir === 'asc' ? (
          <ChevronUp className="w-3 h-3 text-primary" />
        ) : (
          <ChevronDown className="w-3 h-3 text-primary" />
        )
      ) : (
        <ChevronsUpDown className="w-3 h-3 opacity-60" />
      )}
    </span>
  );
}

export function TableRow({
  icon,
  col1,
  col2,
  col3,
  status,
  expanded,
  onToggle,
  density = 'standard',
}: {
  icon: React.ReactNode;
  col1: string;
  col2: string;
  col3: string;
  status: string;
  index?: number;
  expanded?: boolean;
  onToggle?: () => void;
  density?: 'comfortable' | 'standard' | 'compact';
}) {
  const getStatusColor = (s: string) => {
    if (s === 'Safe') return 'bg-success/10 text-success border-success/20';
    if (s === 'Warning') return 'bg-primary/10 text-primary border-primary/20';
    if (s.includes('개월')) return 'bg-primary/10 text-primary border-primary/20';
    return 'bg-card text-muted-foreground border-border';
  };
  const dc =
    density === 'compact'
      ? 'py-1.5 px-3 text-[0.625rem]'
      : density === 'comfortable'
        ? 'py-4 px-3 text-sm'
        : 'py-3 px-3 text-xs';
  const statusSize = density === 'compact' ? 'text-[0.5625rem]' : 'text-[0.625rem]';
  return (
    <>
      <tr
        onClick={onToggle}
        className={`cursor-pointer transition-colors group ${
          expanded ? 'bg-primary/[0.06]' : 'hover:bg-muted/50'
        }`}
      >
        <td className={`${dc} pl-5 font-medium text-foreground`}>
          <span className="inline-flex items-center gap-2">
            <ChevronRight
              size={12}
              className={`text-muted-foreground transition-transform duration-300 ${
                expanded ? 'rotate-90 text-primary' : ''
              }`}
            />
            <span className="text-muted-foreground group-hover:text-primary transition-colors">
              {icon}
            </span>
            {col1}
          </span>
        </td>
        <td className={`${dc} text-muted-foreground font-mono`}>{col2}</td>
        <td className={`${dc} font-mono font-bold text-foreground`}>{col3}</td>
        <td className={dc}>
          <span
            className={`px-2 py-0.5 ${statusSize} font-bold rounded-full border whitespace-nowrap ${getStatusColor(status)}`}
          >
            {status}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-card">
          <td colSpan={4} className="p-5 border-l-2 border-primary">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* 1. Mini Map — 상권 겹침 (Venn) */}
              <div className="flex flex-col gap-2">
                <span className="text-[0.625rem] font-mono uppercase tracking-wider text-muted-foreground">
                  상권 겹침
                </span>
                <div className="bg-card rounded-lg border border-border p-3 flex items-center justify-center">
                  <svg viewBox="0 0 120 70" className="w-full max-w-[160px] h-16">
                    <circle
                      cx="42"
                      cy="35"
                      r="22"
                      fill="rgba(0,44,209,0.2)"
                      stroke="var(--primary)"
                      strokeWidth="1.5"
                    />
                    <circle
                      cx="78"
                      cy="35"
                      r="22"
                      fill="rgba(244,63,94,0.2)"
                      stroke="var(--danger)"
                      strokeWidth="1.5"
                    />
                    <text
                      x="42"
                      y="38"
                      fontSize="6"
                      fill="var(--primary)"
                      textAnchor="middle"
                      fontWeight="bold"
                    >
                      신규
                    </text>
                    <text
                      x="78"
                      y="38"
                      fontSize="6"
                      fill="var(--danger)"
                      textAnchor="middle"
                      fontWeight="bold"
                    >
                      기존
                    </text>
                    <text
                      x="60"
                      y="38"
                      fontSize="5"
                      fill="var(--foreground)"
                      textAnchor="middle"
                      opacity="0.6"
                    >
                      ∩
                    </text>
                  </svg>
                </div>
              </div>

              {/* 2. 시간대별 영향도 — 실데이터 필드 미정의 (DistrictComparison/MarketReport에 없음).
                  mock %값 노출(거짓 양성) 제거하고 모두 '—' 표시. backend 보강 시 실값 매핑. */}
              <div className="flex flex-col gap-2">
                <span className="text-[0.625rem] font-mono uppercase tracking-wider text-muted-foreground">
                  시간대별 영향도
                </span>
                <div className="bg-card rounded-lg border border-border p-3 flex flex-col gap-1.5 text-[0.625rem] font-mono">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">오전 (06-11)</span>
                    <span className="text-muted-foreground">—</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">점심 (11-14)</span>
                    <span className="text-muted-foreground">—</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">저녁 (17-21)</span>
                    <span className="text-muted-foreground">—</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">심야 (21-02)</span>
                    <span className="text-muted-foreground">—</span>
                  </div>
                </div>
              </div>

              {/* 3. Counterfactual — 실데이터 필드 미정의. mock '+18.4%' 제거하고 '—' 표시. */}
              <div className="flex flex-col gap-2">
                <span className="text-[0.625rem] font-mono uppercase tracking-wider text-muted-foreground">
                  Counterfactual
                </span>
                <div className="bg-card rounded-lg border border-border p-3 flex-1 flex flex-col justify-center gap-1">
                  <p className="text-[0.625rem] text-muted-foreground leading-relaxed">
                    이 매장이 없었다면
                  </p>
                  <p className="text-lg font-black text-muted-foreground font-mono leading-none">
                    —
                  </p>
                  <p className="text-[0.5625rem] text-muted-foreground">월 매출 추가 예상</p>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function InsightCard({
  icon,
  title,
  desc,
  severity = 'advisory',
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  severity?: 'critical' | 'advisory' | 'opportunity';
  onClick?: () => void;
}) {
  const { showToast } = useToast();
  const severityStyle = {
    critical: { dot: 'bg-danger', label: 'CRITICAL' },
    advisory: { dot: 'bg-primary', label: 'ADVISORY' },
    opportunity: { dot: 'bg-success', label: 'OPPORTUNITY' },
  }[severity];

  return (
    <div
      onClick={onClick}
      className="flex flex-col gap-2 p-3 rounded-lg bg-card border border-border cursor-pointer hover:border-primary hover:bg-primary/[0.05] transition-all group"
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 mt-0.5">{icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h4 className="text-foreground font-bold text-xs">{title}</h4>
            <span className="inline-flex items-center gap-1 shrink-0">
              <span className={`w-1.5 h-1.5 rounded-full ${severityStyle.dot}`} />
              <span className="text-[0.5rem] font-mono uppercase tracking-wider text-muted-foreground">
                {severityStyle.label}
              </span>
            </span>
          </div>
          <p className="text-muted-foreground text-[0.625rem] leading-relaxed">{desc}</p>
        </div>
      </div>

      {/* Feedback buttons */}
      <div className="flex justify-end gap-1 pt-1 -mb-0.5 -mr-0.5 opacity-50 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => {
            e.stopPropagation();
            showToast('success', '소중한 피드백이 전달되었습니다. AI 학습에 반영됩니다.');
          }}
          className="p-1 rounded hover:bg-primary/10 hover:text-primary text-muted-foreground transition-colors"
          aria-label="유용함"
        >
          <ThumbsUp className="w-3 h-3" />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            showToast('info', '소중한 피드백이 전달되었습니다. AI 학습에 반영됩니다.');
          }}
          className="p-1 rounded hover:bg-danger/10 hover:text-danger text-muted-foreground transition-colors"
          aria-label="유용하지 않음"
        >
          <ThumbsDown className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   DashboardPanelView — VS 비교 모드용 압축 대시보드 패널
   simResult.districtRankings / simResult.comparison에서 dongName 매칭으로 실데이터 렌더.
   매칭 없으면 '—' 또는 '데이터 없음' 폴백 표시. isVariantB는 색상 구분용만 유지.
   ═══════════════════════════════════════════════════════ */
function DashboardPanelView({
  districtName,
  isVariantB,
  popData,
  dongName,
  accentOverride,
  panelIndex = 0,
  simResult,
}: {
  districtName: string;
  isVariantB: boolean;
  popData?: any;
  dongName?: string;
  accentOverride?: string;
  panelIndex?: number;
  simResult?: SimResult | null;
}) {
  // 실데이터 조회 — districtRankings / comparison에서 dongName 매칭
  const dongRanking = simResult?.districtRankings?.find((r) => r.district === dongName);
  const dongComparison = simResult?.comparison?.find((c) => c.district === dongName);
  const hasRealData = !!dongRanking || !!dongComparison;

  // §3.7 (api-contract) 준수 — 실데이터 없으면 '—' 표시. mock fallback 일체 금지.
  // 비교 모드에서 winner 외 동은 backend ML 결과(closure_rate/bep_quarters/comparison)가
  // 비어있어 거짓 양성 위험이 컸음 (`'₩ 32,400,000'` 등 hardcoded 노출).

  // Revenue — comparison.revenue (만원 단위 → 원 환산 후 formatKrw)
  const revenueNum = dongComparison?.revenue;
  const revenue = typeof revenueNum === 'number' ? `₩ ${formatKrw(revenueNum * 10000)}` : '—';

  // Score — districtRankings.score
  const scoreNum =
    typeof dongRanking?.score === 'number' ? Math.round(dongRanking.score as number) : null;
  const score = scoreNum != null ? `${scoreNum} / 100` : '—';

  const dongPop = popData?.dong_details?.find((d: any) => d.dong_name === dongName);
  const traffic = dongPop ? `${dongPop.daily_total.toLocaleString()} 명` : '—';

  // Closure rate (폐업률) — districtRankings.closure_rate (0~1 fraction → %)
  const closureRateNum =
    typeof dongRanking?.closure_rate === 'number' ? (dongRanking.closure_rate as number) : null;
  const risk = closureRateNum != null ? `${(closureRateNum * 100).toFixed(1)}%` : '—';

  // DistrictComparison 타입엔 growth/score-trend 명시 필드 없음 → 항상 '—'
  // (mock 분기 제거 — hasRealData 분기 없이 통일).
  const revenueTrend = '—';
  const scoreTrend = '—';

  // Radar — winner_district 일치 + market_report 7지표 모두 실값일 때만 그림.
  // 하나라도 null이면 차트 자체 비활성(거짓 0 채움 금지). 백엔드가 scouting_results 미실행 시 null을 보냄.
  const isWinner = !!dongName && dongName === simResult?.winnerDistrict;
  const realRadar = (() => {
    const mr = simResult?.marketReport;
    if (!isWinner || !mr) return null;
    const survivalToClosure = mr.survival_rate != null ? 100 - mr.survival_rate : null;
    const v = [
      mr.floating_population,
      mr.rent_index,
      mr.competition_intensity,
      mr.estimated_revenue,
      survivalToClosure,
      mr.growth_potential,
      mr.accessibility,
    ];
    return v.every((x) => x != null) ? (v as number[]) : null;
  })();
  const radarValues: number[] = realRadar ?? [];
  const radarLabels = ['유동인구', '임대료', '경쟁강도', '매출추정', '폐업률', '성장성', '접근성'];
  const colorMap = ['text-warning', 'text-success', 'text-primary', 'text-danger'];
  const badgeColorMap = [
    'bg-warning/10 text-warning border-warning/20',
    'bg-success/10 text-success border-success/20',
    'bg-primary/10 text-primary border-primary/20',
    'bg-danger/10 text-danger border-danger/20',
  ];
  const panelLabels = ['기준', '비교 A', '비교 B', '비교 C'];
  const accentColor = accentOverride || colorMap[panelIndex] || 'text-warning';
  const badgeColor = badgeColorMap[panelIndex] || badgeColorMap[0];

  // 레이더 차트 좌표 계산
  const radarPoints = radarValues
    .map((v, i) => {
      const angle = (Math.PI * 2 * i) / 7 - Math.PI / 2;
      const r = (v / 100) * 70;
      return `${100 + r * Math.cos(angle)},${100 + r * Math.sin(angle)}`;
    })
    .join(' ');

  // AI 인사이트 — 실데이터 있으면 dongName + 실수치 기반 동적 문장, 없으면 empty state
  // 2026-04-27: DistrictRanking이 bep_quarters(분기)로 마이그레이션됨
  const bepQuarters =
    typeof dongRanking?.bep_quarters === 'number' ? (dongRanking.bep_quarters as number) : null;
  const insights: { icon: JSX.Element; text: string }[] =
    hasRealData && dongRanking
      ? [
          {
            icon: <TrendingUp className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />,
            text:
              scoreNum != null
                ? `${dongName}의 종합 점수는 ${scoreNum}점으로 마포 평균 대비 ${
                    scoreNum >= 75 ? '상위권' : scoreNum >= 55 ? '중위권' : '하위권'
                  }입니다.`
                : `${dongName}의 분석 점수가 집계되지 않았습니다.`,
          },
          {
            icon: <Scale className="w-3.5 h-3.5 text-danger shrink-0 mt-0.5" />,
            text:
              closureRateNum != null
                ? `폐업률 ${(closureRateNum * 100).toFixed(1)}% — ${
                    closureRateNum > 0.3
                      ? '높은 리스크'
                      : closureRateNum > 0.15
                        ? '중간 리스크'
                        : '낮은 리스크'
                  } 권역입니다.`
                : `폐업률 데이터가 부족합니다.`,
          },
          {
            icon: <Users className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />,
            text:
              bepQuarters != null
                ? `손익분기까지 약 ${bepQuarters}분기 소요 예상.`
                : `손익분기 예측 데이터가 부족합니다.`,
          },
        ]
      : [
          {
            icon: <TrendingUp className="w-3.5 h-3.5 text-muted-foreground shrink-0 mt-0.5" />,
            text: `${dongName ?? '선택한 동'}에 대한 분석 데이터가 아직 없습니다.`,
          },
          {
            icon: <Scale className="w-3.5 h-3.5 text-muted-foreground shrink-0 mt-0.5" />,
            text: '시뮬레이션 실행 후 다시 확인해주세요.',
          },
          {
            icon: <Users className="w-3.5 h-3.5 text-muted-foreground shrink-0 mt-0.5" />,
            text: '각 동은 districtRankings에서 매칭됩니다.',
          },
        ];

  // winner 패널 시각 강조 — DistrictRankings의 indigo 톤(메모리 project_persona_pivot 본부 영업팀)
  // 톤 재사용. 외곽선/링/glow로 추천 동임을 즉시 인지하게 한다.
  const winnerWrapCls = isWinner
    ? 'ring-1 ring-primary/30 shadow-[0_0_20px_rgba(0,44,209,0.15)] rounded-xl'
    : '';
  const winnerBadgeCls = isWinner ? 'bg-primary/20 text-primary border-primary/30' : badgeColor;
  const winnerLabel = isWinner ? '추천 1위' : panelLabels[panelIndex];

  return (
    <div
      className={`flex flex-col gap-4 w-full animate-in fade-in zoom-in-95 duration-500 ${winnerWrapCls}`}
    >
      {/* 구역 타이틀 — winner면 indigo 외곽선으로 강조 */}
      <div
        className={`bg-card rounded-xl p-3 flex items-center justify-between border ${
          isWinner ? 'border-primary/40' : 'border-border'
        }`}
      >
        <div className="flex items-center gap-2">
          <MapPin className={`w-4 h-4 ${isWinner ? 'text-primary' : accentColor}`} />
          <span className="font-bold text-foreground text-sm">{districtName}</span>
        </div>
        <span className={`px-2 py-0.5 text-[0.625rem] font-bold rounded border ${winnerBadgeCls}`}>
          {winnerLabel}
        </span>
      </div>

      {/* 4 Stats Cards */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-[0.625rem] text-muted-foreground mb-1">예상 월 매출</p>
          <p className="text-lg font-black text-foreground">{revenue}</p>
          {/* trend는 DistrictComparison에 명시 필드 없음 → 항상 '—' + 중립 회색. */}
          <p className="text-[0.625rem] mt-1 text-muted-foreground">{revenueTrend}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-[0.625rem] text-muted-foreground mb-1">상권 매력도</p>
          <p className="text-lg font-black text-foreground">{score}</p>
          <p className="text-[0.625rem] mt-1 text-muted-foreground">{scoreTrend}</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-[0.625rem] text-muted-foreground mb-1">일 유동인구</p>
          <p className="text-lg font-black text-foreground">{traffic}</p>
          <p className="text-[0.625rem] mt-1 text-muted-foreground">
            {dongPop ? `피크 ${dongPop.peak_hour}시 · ${popData?.date}` : 'KT 통신망 기준'}
          </p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-[0.625rem] text-muted-foreground mb-1">카니발리제이션</p>
          <p className="text-lg font-black text-foreground">{risk}</p>
          {/* 위험 등급 — 실데이터(closureRateNum) 기반. mock '주의/안전 권역' 제거. */}
          <p
            className={`text-[0.625rem] mt-1 ${
              closureRateNum == null
                ? 'text-muted-foreground'
                : closureRateNum > 0.3
                  ? 'text-danger'
                  : closureRateNum > 0.15
                    ? 'text-warning'
                    : 'text-success'
            }`}
          >
            {closureRateNum == null
              ? '—'
              : closureRateNum > 0.3
                ? '높은 리스크'
                : closureRateNum > 0.15
                  ? '중간 리스크'
                  : '낮은 리스크'}
          </p>
        </div>
      </div>

      {/* 레이더 차트 */}
      <div className="bg-card border border-border rounded-xl p-5 flex flex-col items-center">
        <h3 className="text-xs font-bold text-foreground mb-3 self-start">7대 지표 분석</h3>
        <div className="relative w-[200px] h-[200px]">
          {radarValues.length === 0 && (
            <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg border border-dashed border-border bg-card/60 backdrop-blur-[2px]">
              <div className="text-center px-3">
                <div className="mx-auto mb-1 h-5 w-5 animate-pulse rounded-full bg-muted" />
                <div className="text-[0.6875rem] font-semibold text-foreground">구현 예정</div>
                <div className="mt-0.5 text-[0.5625rem] text-muted-foreground">
                  market_report · {dongName || '해당 동'} 대기
                </div>
              </div>
            </div>
          )}
          <svg viewBox="0 0 200 200" className="w-full h-full overflow-visible">
            {[20, 40, 60, 80].map((r) => (
              <polygon
                key={r}
                points={Array.from({ length: 7 }, (_, i) => {
                  const a = (Math.PI * 2 * i) / 7 - Math.PI / 2;
                  return `${100 + r * 0.7 * Math.cos(a)},${100 + r * 0.7 * Math.sin(a)}`;
                }).join(' ')}
                fill="none"
                stroke="var(--border)"
                strokeWidth="0.5"
              />
            ))}
            <polygon
              points={radarPoints}
              fill={isVariantB ? 'rgba(16,185,129,0.15)' : 'rgba(0,44,209,0.15)'}
              stroke={isVariantB ? 'var(--success)' : 'var(--primary)'}
              strokeWidth="2"
            />
            {radarValues.map((v, i) => {
              const angle = (Math.PI * 2 * i) / 7 - Math.PI / 2;
              const r = (v / 100) * 70;
              return (
                <circle
                  key={i}
                  cx={100 + r * Math.cos(angle)}
                  cy={100 + r * Math.sin(angle)}
                  r="3"
                  fill={isVariantB ? 'var(--success)' : 'var(--primary)'}
                />
              );
            })}
            {radarLabels.map((label, i) => {
              const angle = (Math.PI * 2 * i) / 7 - Math.PI / 2;
              const lx = 100 + 85 * Math.cos(angle);
              const ly = 100 + 85 * Math.sin(angle);
              return (
                <text
                  key={i}
                  x={lx}
                  y={ly}
                  fill="var(--muted-foreground)"
                  fontSize="9"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {label}
                </text>
              );
            })}
          </svg>
        </div>
      </div>

      {/* AI 인사이트 요약 — 실데이터 기반 동적 문장 (동 고정 mock 제거) */}
      <div className="bg-card border border-border rounded-xl p-5">
        <h3 className="text-xs font-bold text-foreground mb-3">AI 인사이트</h3>
        <div className="space-y-2">
          {insights.map((ins, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
              {ins.icon}
              <span>{ins.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default DashboardPanelView;
