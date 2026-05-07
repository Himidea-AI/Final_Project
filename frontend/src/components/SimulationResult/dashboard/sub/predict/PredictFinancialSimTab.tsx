/**
 * PredictFinancialSimTab — 예측·재무 시뮬레이션
 * 2026-04-28 IA 재구조 — FinancialTab 분해.
 * BEP 누적이익 + 과거 12개월 폐업률 + LightGBM/TCN 폐업위험도 + 생존률 KPI.
 */

import { useState } from 'react';
import { Activity, History, ShieldAlert, TrendingUp } from 'lucide-react';
import type { ClosureRate, ClosureRisk, SimulationOutput } from '../../../../../types';
import { formatKrw, formatPct } from '../../utils/formatters';
import { sortByRanking } from '../../utils/rankSort';
import { BepCumulativeProfitChart } from '../../charts/BepCumulativeProfitChart';
import { ClosureRatePanel } from '../../charts/ClosureRatePanel';
import { ClosureRiskDetailModal } from '../../charts/ClosureRiskDetailModal';
import { ClosureRiskPanel } from '../../charts/ClosureRiskPanel';
import { SERIES_COLORS } from '../../../QuarterlyProjectionChart';

// 동 chip 활성 시 텍스트 색 — 1~3위는 어두운 배경 위 흰 글씨,
// 4번째(sunshine-yellow) 만 밝은 배경이라 검정. QuarterlyStatStrip 과 동일 정책.
const ACTIVE_TEXT_BY_INDEX = ['#ffffff', '#ffffff', '#ffffff', 'var(--color-text-black)'] as const;

interface Props {
  simResult: SimulationOutput;
}

// district_predictions[].bep dict 의 부분 타입 (백엔드는 Record<string, unknown> 으로 반환)
type QuarterlySimRow = {
  revenue?: number;
  quarterly_total_cost?: number;
  quarterly_profit?: number;
};
type BepDict = {
  quarterly_simulation?: QuarterlySimRow[];
  bep_quarters?: number | null;
};

export function PredictFinancialSimTab({ simResult }: Props) {
  // M6 (2026-04-29): district_predictions 기반 멀티 동 시리즈.
  // is_excluded_combo 동은 제외. 비어있으면 단일 동(quarterly_projection) fallback.
  // ranking 정렬 (winner→4위) 로 SERIES_COLORS[idx] = Deep Blue Sequential 4-tier 매핑 정합.
  const dpredicts = sortByRanking(
    (simResult.district_predictions ?? []).filter((p) => !p.is_excluded_combo),
    simResult,
  );

  // 2026-05-04 패널 KPI 4분기 평균으로 전환 + LLM/랭킹 fallback 제거.
  // 데이터 소스: district_predictions[selected].bep.quarterly_simulation 의 첫 4분기 평균.
  //   - 1년 사이클 평균이라 계절성에 휘둘리지 않음
  //   - 매출-운영비=영업이익 / 마진=영업이익/매출 등식이 같은 4개 row 에서 산출되어 자동 성립
  //   - top-level bep_quarters 와 동일 base (quarterly_per_store ≈ 4분기 평균)
  // ML 실측 없으면 솔직하게 '—' 표시. LLM(final_report.profit_simulation) 의존 제거 —
  // synthesis.py 가 winner 1동 기준 종합 서술이라 chip 클릭에 반응 못 했음.
  const defaultDistrict =
    dpredicts.find((p) => p.district === simResult.winner_district)?.district ??
    dpredicts[0]?.district ??
    simResult.winner_district ??
    '단일';
  const [selectedDistrict, setSelectedDistrict] = useState<string>(defaultDistrict);
  const selectedPred =
    dpredicts.find((p) => p.district === selectedDistrict) ??
    dpredicts.find((p) => p.district === simResult.winner_district) ??
    dpredicts[0];
  const currentDistrict = selectedPred?.district ?? defaultDistrict;
  const bepObj = (selectedPred?.bep as BepDict | null | undefined) ?? null;

  // 폐업위험도 "분석 상세" 모달 — 동별 카드 우하단 버튼 클릭 시 해당 동 데이터로 오픈.
  const [detailDistrict, setDetailDistrict] = useState<string | null>(null);
  const detailPred = detailDistrict
    ? (dpredicts.find((p) => p.district === detailDistrict) ?? null)
    : null;

  // 첫 4분기(=1년 사이클) 평균 산출. quarterly_simulation 은 백엔드
  // bep.simulate_quarterly 결과로 N분기(BEP 도달까지) 들어옴. 첫 4개만 슬라이스.
  const sim4 = (bepObj?.quarterly_simulation ?? []).slice(0, 4);
  const avg =
    sim4.length > 0
      ? {
          revenue: sim4.reduce((s, r) => s + (r.revenue ?? 0), 0) / sim4.length,
          cost: sim4.reduce((s, r) => s + (r.quarterly_total_cost ?? 0), 0) / sim4.length,
          profit: sim4.reduce((s, r) => s + (r.quarterly_profit ?? 0), 0) / sim4.length,
        }
      : null;

  const quarterlyRev = avg?.revenue ?? null;
  const quarterlyCost = avg?.cost ?? null;
  const quarterlyProfit = avg?.profit ?? null;
  const margin =
    quarterlyRev != null && quarterlyRev > 0 && quarterlyProfit != null
      ? quarterlyProfit / quarterlyRev
      : null;
  const dataSource: 'ml' | 'none' = avg != null ? 'ml' : 'none';
  const bepQuarters = bepObj?.bep_quarters ?? null;
  const bepSeries =
    dpredicts.length > 0
      ? dpredicts.map((p) => ({
          district: p.district,
          projection: p.quarterly_projection ?? [],
        }))
      : [
          {
            district: simResult.winner_district ?? '단일',
            projection: simResult.quarterly_projection ?? [],
          },
        ];
  const hasAnyProjection = bepSeries.some((s) => s.projection.length > 0);

  return (
    <div className="space-y-6">
      {/* 좌:우 = 6:4 (투자 회수 곡선 시각 anchor 우위, 상세 수익성 KPI 박스 보조).
          hasAnyProjection==false 시 우측 패널만 풀 폭. lg 미만 (mobile/tablet) 세로 stack. */}
      {hasAnyProjection ? (
        <div className="grid grid-cols-1 items-stretch gap-6 lg:grid-cols-[6fr_4fr]">
          <div className="rounded-3xl border border-border bg-card p-8">
            <div className="mb-8 flex items-start justify-between gap-6">
              <h3 className="flex items-center gap-3 text-left text-xl font-black italic leading-none tracking-tight text-foreground">
                <TrendingUp className="text-primary" /> 투자 회수 곡선
              </h3>
            </div>
            <BepCumulativeProfitChart series={bepSeries} />
          </div>
          <ProfitSimulationPanelFull
            quarterlyRev={quarterlyRev}
            quarterlyCost={quarterlyCost}
            quarterlyProfit={quarterlyProfit}
            margin={margin}
            bepQuarters={bepQuarters}
            district={currentDistrict}
            dataSource={dataSource}
            availableDistricts={dpredicts.map((p) => p.district)}
            onSelectDistrict={setSelectedDistrict}
          />
        </div>
      ) : (
        <ProfitSimulationPanelFull
          quarterlyRev={quarterlyRev}
          quarterlyCost={quarterlyCost}
          quarterlyProfit={quarterlyProfit}
          margin={margin}
          bepQuarters={bepQuarters}
          district={currentDistrict}
          dataSource={dataSource}
          availableDistricts={dpredicts.map((p) => p.district)}
          onSelectDistrict={setSelectedDistrict}
        />
      )}

      {dpredicts.length > 0 ? (
        <>
          <div className="rounded-3xl border border-border bg-card p-8">
            <div className="mb-8 flex items-start justify-between gap-6">
              <h3 className="flex items-center gap-3 text-left text-xl font-black italic leading-none tracking-tight text-foreground">
                <History className="text-primary" /> 동별 최근 4분기 폐업률 추이
              </h3>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {dpredicts.map((p, idx) => (
                <ClosureRatePanel
                  key={p.district}
                  district={p.district}
                  rate={p.closure_rate as ClosureRate | null}
                  color={SERIES_COLORS[idx % SERIES_COLORS.length]}
                />
              ))}
            </div>
          </div>
          <div className="rounded-3xl border border-border bg-card p-8">
            <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
              <h3 className="flex items-center gap-3 text-left text-xl font-black italic leading-none tracking-tight text-foreground">
                <ShieldAlert className="text-primary" /> 동별 폐업위험도
              </h3>
            </div>
            {/* 1~4동 통일 카드 그리드. 각 카드는 BulletChart(0~100 점수) + 합본 자연어 요약
                + 위험 신호 TOP 3 + "분석 상세" 모달 트리거. ML 모델명/기여 피처 같은 ML 용어
                는 카드에서 모두 제거. 깊은 분석은 모달에서 "과거 데이터 분석 / 최근 추세 분석"
                두 관점으로 노출 (ClosureRiskDetailModal). */}
            <div
              className={`grid grid-cols-1 gap-4 ${
                dpredicts.length === 2
                  ? 'sm:grid-cols-2'
                  : dpredicts.length === 3
                    ? 'sm:grid-cols-2 lg:grid-cols-3'
                    : dpredicts.length >= 4
                      ? 'sm:grid-cols-2 lg:grid-cols-4'
                      : ''
              }`}
            >
              {dpredicts.map((p, idx) => (
                <ClosureRiskPanel
                  key={p.district}
                  closure={p.closure_risk as ClosureRisk | null}
                  district={p.district}
                  onOpenDetail={() => setDetailDistrict(p.district)}
                  seriesColor={SERIES_COLORS[idx % SERIES_COLORS.length]}
                />
              ))}
            </div>
          </div>
        </>
      ) : (
        <>
          <ClosureRatePanel rate={simResult.closure_rate} />
          <ClosureRiskPanel closure={simResult.closure_risk} />
        </>
      )}

      {/* 동별 폐업위험도 카드의 "분석 상세" 버튼으로 트리거. 닫으면 detailDistrict=null. */}
      <ClosureRiskDetailModal
        open={detailDistrict != null}
        district={detailPred?.district ?? ''}
        closure={(detailPred?.closure_risk as ClosureRisk | null) ?? null}
        onClose={() => setDetailDistrict(null)}
      />
    </div>
  );
}

interface ProfitPanelProps {
  quarterlyRev: number | null | undefined;
  quarterlyCost: number | null | undefined;
  quarterlyProfit: number | null | undefined;
  margin: number | null | undefined;
  bepQuarters: number | null | undefined;
  district: string;
  dataSource: 'ml' | 'none';
  availableDistricts?: string[];
  onSelectDistrict?: (d: string) => void;
}

function ProfitSimulationPanelFull({
  quarterlyRev,
  quarterlyCost,
  quarterlyProfit,
  margin,
  bepQuarters,
  district,
  dataSource,
  availableDistricts,
  onSelectDistrict,
}: ProfitPanelProps) {
  const rows = [
    { label: '분기 추정 매출', val: quarterlyRev, accent: 'text-foreground' },
    { label: '분기 운영비 (총계)', val: quarterlyCost, accent: 'text-muted-foreground' },
  ];
  // 데이터 출처 배지 — ML 실측 only. LLM fallback 제거(2026-05-04) 로 'llm' 케이스 없음.
  const sourceBadge =
    dataSource === 'ml'
      ? { label: 'ML 실측', cls: 'border-success/30 bg-success/10 text-success' }
      : { label: '데이터 없음', cls: 'border-border bg-secondary text-muted-foreground' };
  return (
    <div className="rounded-3xl border border-border bg-card p-8">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3 className="flex items-center gap-3 text-left text-xl font-black italic leading-none tracking-tight text-foreground">
            <Activity className="text-primary" /> 상세 수익성 시뮬레이션
          </h3>
          <p className="text-[0.6875rem] font-bold text-muted-foreground">
            기준 동: <span className="text-foreground">{district}</span> · 분기 단위
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={`rounded-full border px-2 py-0.5 text-[0.5625rem] font-black uppercase tracking-widest ${sourceBadge.cls}`}
          >
            {sourceBadge.label}
          </div>
          {margin != null && (
            <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[0.6875rem] font-black tabular-nums text-primary">
              마진 {formatPct(margin)}
            </div>
          )}
          {bepQuarters != null && (
            <div className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[0.6875rem] font-black tabular-nums text-primary">
              BEP {bepQuarters}분기
            </div>
          )}
        </div>
      </div>

      {/* 동 선택 chip — 4동 비교 시뮬에서 다른 동의 수익성 보고 싶을 때 클릭. 단일 동이면 미노출.
          활성 chip 색은 BEP 누적수익 그래프/QuarterlyStatStrip 과 동일 SERIES_COLORS[idx]
          를 inline style 로 주입. dpredicts 배열 순서를 그대로 쓰므로 그래프 라인 색과 자동 매칭. */}
      {availableDistricts && availableDistricts.length > 1 && onSelectDistrict && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {availableDistricts.map((d, idx) => {
            const active = d === district;
            const color = SERIES_COLORS[idx % SERIES_COLORS.length];
            const textColor = ACTIVE_TEXT_BY_INDEX[idx % ACTIVE_TEXT_BY_INDEX.length];
            return (
              <button
                key={d}
                type="button"
                onClick={() => onSelectDistrict(d)}
                style={
                  active
                    ? { backgroundColor: color, borderColor: color, color: textColor }
                    : undefined
                }
                className={`rounded-full border px-3 py-1 text-[0.6875rem] font-bold tabular-nums transition ${
                  active
                    ? ''
                    : 'border-border bg-secondary text-muted-foreground hover:border-primary/40 hover:text-foreground'
                }`}
              >
                {d}
              </button>
            );
          })}
        </div>
      )}

      {bepQuarters != null && (
        <p className="mb-4 text-[0.625rem] text-muted-foreground leading-relaxed">
          ※ 인건비 미포함 기준입니다. 실제 BEP는 운영 인원에 따라 길어질 수 있습니다.
        </p>
      )}

      <div className="space-y-3">
        {rows.map((item) => (
          <div
            key={item.label}
            className="flex justify-between items-end border-b border-border/50 pb-3"
          >
            <span className="text-xs font-bold text-muted-foreground">{item.label}</span>
            <span className={`text-lg font-black tabular-nums ${item.accent}`}>
              {item.val != null ? `₩${formatKrw(item.val)}` : '—'}
            </span>
          </div>
        ))}
        <div className="flex justify-between items-center pt-2">
          <span className="text-sm font-black text-primary tracking-tighter">
            예상 분기 영업이익
          </span>
          <span className="text-3xl font-black text-primary tabular-nums tracking-tighter">
            {quarterlyProfit != null ? `₩${formatKrw(quarterlyProfit)}` : '—'}
          </span>
        </div>
      </div>
    </div>
  );
}
