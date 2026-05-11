/**
 * IndustryClosureTrendCard — 동 + 업종 폐업률 추세 (분기별 8개)
 *
 * 데이터: competitor_intel.industry_closure_trend
 *   { samples: [{quarter, closure_rate, ...}], current_closure_rate, historical_avg, trend }
 * 디자인: KPI(현재/평균) + 추세 배지 + Sparkline
 * Best practice: 추세 라벨(improving/worsening) 색상 시멘틱 + 분기 시계열 미니 차트
 *
 * 다른 패널과 혼동 방지: 재무 시뮬 탭의 ClosureRatePanel ("과거 폐업률") 은
 *   동 단위 4분기 (전 업종 통합) 데이터라 본 카드 (동+업종 8분기 실측) 와 값이 다를 수 있음.
 *   카드 우측 ℹ️ 툴팁으로 사용자 안내.
 */

import { Activity, Info } from 'lucide-react';
import { Sparkline } from './Sparkline';

interface Sample {
  quarter?: string | number;
  closure_rate?: number | null;
  store_count?: number | null;
  open_count?: number | null;
  close_count?: number | null;
  franchise_count?: number | null;
  [k: string]: unknown;
}

interface Props {
  trend?:
    | {
        samples?: Sample[];
        current_closure_rate?: number | null;
        historical_avg?: number | null;
        trend?: string;
      }
    | null
    | undefined;
  /** 분석 기준 동 (예: '망원1동') — 라벨 prefix. 미지정 시 동 prefix 생략. */
  dongName?: string | null;
  /** 분석 업종 라벨 (예: '커피') — 라벨 prefix. 미지정 시 업종 prefix 생략. */
  industryLabel?: string | null;
}

const TREND_LABEL: Record<string, { label: string; color: string; bg: string }> = {
  improving: {
    label: '개선 중',
    color: 'text-success',
    bg: 'bg-success/10 border-success/30',
  },
  worsening: {
    label: '악화 중',
    color: 'text-danger',
    bg: 'bg-danger/10 border-danger/30',
  },
  stable: {
    label: '안정',
    color: 'text-foreground',
    bg: 'bg-muted/30 border-border/40',
  },
  unknown: {
    label: '데이터 부족',
    color: 'text-muted-foreground',
    bg: 'bg-card/30 border-border/40',
  },
};

export function IndustryClosureTrendCard({ trend, dongName, industryLabel }: Props) {
  if (!trend || !trend.samples || trend.samples.length === 0) {
    return null;
  }

  const samples = trend.samples;
  const numericSamples = samples
    .map((s) => (typeof s.closure_rate === 'number' ? s.closure_rate : null))
    .filter((v): v is number => v != null);

  const cur = trend.current_closure_rate;
  const avg = trend.historical_avg;
  const tinfo = TREND_LABEL[trend.trend ?? 'unknown'] ?? TREND_LABEL.unknown;

  // store_quarterly.closure_rate 는 이미 percent 단위(4 = 4%) — 추가 *100 금지
  const fmtPct = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(2)}%`);

  // 라벨 prefix — 동/업종 prop 있을 때만 노출 (없으면 기존 라벨 유지).
  const titleParts: string[] = [];
  if (dongName) titleParts.push(dongName);
  if (industryLabel) titleParts.push(industryLabel);
  const titlePrefix = titleParts.length > 0 ? `${titleParts.join(' · ')} ` : '';

  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-muted-foreground" />
          <span className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
            {titlePrefix}폐업률 추세
          </span>
          <span className="text-[0.5625rem] font-bold text-muted-foreground normal-case tracking-normal">
            8 분기 실측
          </span>
          {/* 혼동 방지 ℹ️ 툴팁 — 재무시뮬 탭의 동 전체 4분기 폐업률과 다른 데이터임을 안내. */}
          <span className="group relative inline-flex">
            <Info
              size={12}
              className="text-muted-foreground/60 hover:text-muted-foreground cursor-help"
            />
            <span
              role="tooltip"
              className="pointer-events-none absolute left-1/2 top-full z-20 mt-1 w-64 -translate-x-1/2 rounded-lg border border-border bg-card/95 p-2 text-[0.625rem] font-normal normal-case tracking-normal text-foreground opacity-0 shadow-lg backdrop-blur transition-opacity group-hover:opacity-100"
            >
              <span className="font-bold text-foreground">{titlePrefix || '동 + 업종 '}</span>
              분기별 실측 폐업률 (store_quarterly DB).
              <br />
              재무 시뮬 탭의 <span className="font-bold">"과거 폐업률"</span> (동 전체 4분기 통합)
              과 단위·기간이 달라 값이 다를 수 있습니다.
            </span>
          </span>
        </div>
        <span
          className={`text-[0.625rem] font-black px-2 py-0.5 rounded-full border ${tinfo.color} ${tinfo.bg} uppercase tracking-widest`}
        >
          {tinfo.label}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        {/* 퐁당퐁당 룰: outer card(white) ↔ inner secondary(cool gray). */}
        <div className="rounded-lg border border-border bg-secondary p-3">
          <div className="text-[0.5625rem] font-black uppercase tracking-widest text-muted-foreground mb-1">
            현재 분기
          </div>
          <div className="text-xl font-black tabular-nums text-foreground tracking-tighter">
            {fmtPct(cur)}
          </div>
        </div>
        <div className="rounded-lg border border-border bg-secondary p-3">
          <div className="text-[0.5625rem] font-black uppercase tracking-widest text-muted-foreground mb-1">
            과거 평균
          </div>
          <div className="text-xl font-black tabular-nums text-foreground tracking-tighter">
            {fmtPct(avg)}
          </div>
        </div>
      </div>

      <div className="h-12">
        {numericSamples.length > 1 ? (
          <Sparkline data={numericSamples} height={48} />
        ) : (
          <span className="text-[0.5625rem] text-muted-foreground">시계열 데이터 부족</span>
        )}
      </div>

      {/* 출처 표기 — 재무시뮬 ClosureRatePanel 과 데이터 source 가 다름을 명시. */}
      <p className="mt-3 text-[0.5625rem] leading-relaxed text-muted-foreground">
        ※ 출처: store_quarterly DB (분기별 실측, 업종별 필터). 재무 시뮬 탭 "과거 폐업률" (동 전체
        4분기) 과 다를 수 있음.
      </p>
    </div>
  );
}
