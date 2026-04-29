import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';

interface Props {
  simResult: SimulationOutput;
}

// scale: 백엔드 원본 단위 → 0~100 렌더 단위 변환 배수. closure_rate 만 0~1 fraction.
const INDICATORS: Array<{
  key: string;
  label: string;
  shortLabel: string;
  color: string;
  scale?: number;
}> = [
  { key: 'floating_population', label: '유동인구', shortLabel: '유동', color: 'bg-sky-500' },
  { key: 'rent_index', label: '임대료 지수', shortLabel: '임대', color: 'bg-indigo-500' },
  { key: 'competition_intensity', label: '경쟁강도', shortLabel: '경쟁', color: 'bg-rose-500' },
  { key: 'estimated_revenue', label: '예상 매출', shortLabel: '매출', color: 'bg-emerald-500' },
  { key: 'survival_rate', label: '생존율', shortLabel: '생존', color: 'bg-violet-500' },
  { key: 'closure_rate', label: '폐업률', shortLabel: '폐업', color: 'bg-pink-500', scale: 100 },
  { key: 'growth_potential', label: '성장 잠재력', shortLabel: '성장', color: 'bg-cyan-500' },
  { key: 'accessibility', label: '접근성', shortLabel: '접근', color: 'bg-blue-500' },
] as const;

// null 시 중립 회색 — 0 fallback 회피(거짓 양성 방지, api-contract §3.7).
function scoreColor(v: number | null): string {
  if (v == null) return 'text-stone-500';
  if (v >= 70) return 'text-emerald-400';
  if (v >= 45) return 'text-amber-400';
  return 'text-rose-400';
}

function scoreBorder(v: number | null): string {
  if (v == null) return 'border-stone-700/50';
  if (v >= 70) return 'border-emerald-500/30';
  if (v >= 45) return 'border-amber-500/30';
  return 'border-rose-500/30';
}

function scoreBg(v: number | null): string {
  if (v == null) return 'bg-stone-800/40';
  if (v >= 70) return 'bg-emerald-500/10';
  if (v >= 45) return 'bg-amber-500/10';
  return 'bg-rose-500/10';
}

function barColor(v: number): string {
  if (v >= 70) return 'bg-emerald-500';
  if (v >= 45) return 'bg-amber-500';
  return 'bg-rose-500';
}

export function IndicatorGrid({ simResult }: Props) {
  const report = simResult.market_report;

  if (!report) {
    return (
      <section>
        <SectionLabel label="INDICATOR GRID" subtitle="8개 핵심 상권 지표" />
        <div className="rounded-lg border border-zinc-700 bg-zinc-800 p-6 text-center text-sm text-zinc-400">
          상권 지표 데이터 없음
        </div>
      </section>
    );
  }

  // null fallback 금지 (api-contract §3.7) — 데이터 없으면 null로 둬서 UI에서 "—"로 명시.
  // closure_rate은 0~1 fraction이라 scale: 100 적용 후 0~100 점수화.
  const values = INDICATORS.map(({ key, label, shortLabel, scale }) => {
    const rawVal = (report as Record<string, unknown>)[key];
    if (typeof rawVal !== 'number' || !Number.isFinite(rawVal)) {
      return { key, label, shortLabel, val: null as number | null };
    }
    const scaled = scale ? rawVal * scale : rawVal;
    return { key, label, shortLabel, val: Math.max(0, Math.min(100, scaled)) };
  });

  // radar — null인 축은 0으로 그리지 않고 polygon에서 제외 (찌그러짐 방지).
  const radarData = values
    .filter((v) => v.val != null)
    .map(({ shortLabel, val }) => ({
      subject: shortLabel,
      value: val,
      fullMark: 100,
    }));

  return (
    <section>
      <SectionLabel label="INDICATOR GRID" subtitle="8개 핵심 상권 지표" />

      <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
        {/* KPI 카드 그리드 — 라벨(truncate) / 큰 숫자(우측 끝부분 미간 회피) / progress bar.
            "/100" 텍스트는 progress bar가 0~100을 시각화하므로 중복 → 제거(좁은 박스 깨짐 방지). */}
        {/* 2×4 가로 박스 — 박스당 폭 2배 확보로 모든 라벨 한 줄에 들어감.
            라벨 좌 / 숫자 우 (justify-between baseline align), bar 아래 풀폭. */}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {values.map(({ key, label, val }) => (
            <div key={key} className={`rounded-lg border p-3 ${scoreBorder(val)} ${scoreBg(val)}`}>
              <div className="flex items-baseline justify-between gap-3">
                <div className="text-[0.6875rem] uppercase tracking-wide text-stone-400">{label}</div>
                <div
                  className={`text-2xl font-bold font-mono tabular-nums leading-none ${scoreColor(val)}`}
                >
                  {val == null ? '—' : Math.round(val)}
                </div>
              </div>
              <div className="mt-2.5 h-1 w-full rounded-full bg-stone-700/50">
                {val != null && (
                  <div
                    className={`h-full rounded-full ${barColor(val)}`}
                    style={{ width: `${val}%` }}
                  />
                )}
              </div>
            </div>
          ))}
        </div>

        {/* 레이더 차트 — w-72(288px) → w-60(240px)로 줄여 좌측 KPI 그리드 공간 확보 */}
        <div className="flex items-center justify-center rounded-lg border border-stone-700 bg-stone-800 p-4 lg:w-60">
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
              <PolarGrid stroke="#44403c" />
              <PolarAngleAxis
                dataKey="subject"
                tick={{ fill: '#a8a29e', fontSize: 10, fontWeight: 600 }}
              />
              <Radar
                dataKey="value"
                stroke="#6366f1"
                fill="#6366f1"
                fillOpacity={0.15}
                strokeWidth={1.5}
              />
              <Tooltip
                contentStyle={{
                  background: 'rgba(24,24,27,0.95)',
                  border: '1px solid #3f3f46',
                  borderRadius: 6,
                  fontSize: 12,
                  color: '#e4e4e7',
                }}
                formatter={(v: number) => [Math.round(v), '점수']}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* AgentCard 3개(market/population/ranking)는 MarketTab의 full-width row로 분리 —
          좁은 컬럼에서 size="full" 카드가 깨지던 문제 해소 (2026-04-28). */}
    </section>
  );
}
