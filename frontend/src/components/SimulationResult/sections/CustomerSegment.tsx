import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';

interface Props {
  simResult: SimulationOutput;
}

const AGE_KEYS: { key: string; label: string }[] = [
  { key: 'age_10_ratio', label: '10대' },
  { key: 'age_20_ratio', label: '20대' },
  { key: 'age_30_ratio', label: '30대' },
  { key: 'age_40_ratio', label: '40대' },
  { key: 'age_50_ratio', label: '50대' },
  { key: 'age_60_above_ratio', label: '60대+' },
];

const GENDER_KEYS: { key: string; label: string }[] = [
  { key: 'male_ratio', label: '남성' },
  { key: 'female_ratio', label: '여성' },
];

const TIME_KEYS: { key: string; label: string }[] = [
  { key: 'time_00_06_ratio', label: '심야 (00-06)' },
  { key: 'time_06_11_ratio', label: '오전 (06-11)' },
  { key: 'time_11_14_ratio', label: '점심 (11-14)' },
  { key: 'time_14_17_ratio', label: '오후 (14-17)' },
  { key: 'time_17_21_ratio', label: '저녁 (17-21)' },
  { key: 'time_21_24_ratio', label: '야간 (21-24)' },
];

const DAY_KEYS: { key: string; label: string }[] = [
  { key: 'weekday_ratio', label: '평일' },
  { key: 'weekend_ratio', label: '주말' },
];

function formatKrw(won: number | null | undefined): string {
  if (won == null || !Number.isFinite(won)) return '—';
  if (won >= 1_0000_0000) return `${(won / 1_0000_0000).toFixed(2)}억`;
  if (won >= 1_0000)
    return `${(won / 1_0000).toLocaleString('ko-KR', { maximumFractionDigits: 0 })}만`;
  return won.toLocaleString('ko-KR');
}

function formatPct(ratio: number | null | undefined): string {
  if (ratio == null || !Number.isFinite(ratio)) return '—';
  return `${(ratio * 100).toFixed(2)}%`;
}

export function CustomerSegment({ simResult }: Props) {
  const seg = simResult.customer_segment;

  if (!seg) {
    return (
      <section>
        <SectionLabel label="TARGET CUSTOMER" subtitle="타겟 고객 매출 분석" />
        <div className="rounded-lg border border-dashed border-stone-700 bg-stone-900/40 p-10 text-center">
          <div className="mx-auto mb-2 h-8 w-8 animate-pulse rounded-full bg-stone-700" />
          <div className="text-sm text-stone-400">타겟 프로필 데이터 없음</div>
          <div className="mt-1 text-xs text-stone-500">
            시뮬레이션 입력에 타겟 고객 프로필을 지정하면 세그먼트별 예상매출이 표시됩니다
          </div>
        </div>
      </section>
    );
  }

  const dim = seg.dimension_ratios ?? {};
  const hasMonthly = seg.total_sales_ref != null && seg.total_sales_ref > 0;

  return (
    <section>
      <SectionLabel label="TARGET CUSTOMER" subtitle="타겟 고객 매출 분석" />
      <div className="rounded-lg border border-stone-700 bg-stone-800 p-6">
        {seg.profile_summary && (
          <div className="mb-5 flex items-start gap-3">
            <div className="rounded-md border border-indigo-500/30 bg-indigo-500/5 px-3 py-1 text-xs font-semibold text-indigo-400">
              프로필
            </div>
            <p className="text-sm leading-relaxed text-stone-200">{seg.profile_summary}</p>
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-4">
          <KpiCard
            label="세그먼트 비율"
            value={formatPct(seg.segment_ratio)}
            hint="월매출 중 타겟 고객 비율"
            accent="text-indigo-400"
          />
          {hasMonthly ? (
            <>
              <KpiCard
                label="타겟 예상매출"
                value={formatKrw(seg.segment_sales)}
                unit="원"
                hint="타겟 프로필 대응 매출"
                accent="text-emerald-400"
              />
              <KpiCard
                label="식별 매출"
                value={formatKrw(seg.identified_sales)}
                unit="원"
                hint="카드 결제 기준 확인 가능 매출"
                accent="text-cyan-400"
              />
              <KpiCard
                label="참조 월매출"
                value={formatKrw(seg.total_sales_ref)}
                unit="원"
                hint="시뮬레이션 입력값"
                accent="text-stone-200"
              />
            </>
          ) : (
            <div className="md:col-span-3 rounded-md border border-dashed border-stone-700 bg-stone-900/40 p-4 text-center text-xs text-stone-500">
              월매출 입력 시 금액 예측이 표시됩니다 (현재: 비율만 제공)
            </div>
          )}
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <RatioBarChart title="연령대 분포" items={AGE_KEYS} ratios={dim} />
          <RatioBarChart title="성별 분포" items={GENDER_KEYS} ratios={dim} />
          <RatioBarChart title="시간대 분포" items={TIME_KEYS} ratios={dim} />
          <RatioBarChart title="요일 분포" items={DAY_KEYS} ratios={dim} />
        </div>
      </div>
    </section>
  );
}

interface KpiCardProps {
  label: string;
  value: string;
  unit?: string;
  hint?: string;
  accent: string;
}

function KpiCard({ label, value, unit, hint, accent }: KpiCardProps) {
  return (
    <div className="rounded-md border border-stone-700 bg-stone-900/60 p-4">
      <div className="text-xs text-stone-400">{label}</div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className={`text-xl font-bold ${accent}`}>{value}</span>
        {unit && <span className="text-xs text-stone-500">{unit}</span>}
      </div>
      {hint && <div className="mt-1 text-[10px] text-stone-500">{hint}</div>}
    </div>
  );
}

interface RatioBarChartProps {
  title: string;
  items: { key: string; label: string }[];
  ratios: Record<string, number>;
}

function RatioBarChart({ title, items, ratios }: RatioBarChartProps) {
  const maxRatio = Math.max(
    0.01,
    ...items.map((it) => {
      const v = ratios[it.key];
      return typeof v === 'number' && Number.isFinite(v) ? v : 0;
    }),
  );

  return (
    <div className="rounded-md border border-stone-700 bg-stone-900/60 p-4">
      <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-stone-400">
        {title}
      </div>
      <div className="space-y-2">
        {items.map((it) => {
          const raw = ratios[it.key];
          const v = typeof raw === 'number' && Number.isFinite(raw) ? raw : 0;
          const width = Math.min(100, Math.round((v / maxRatio) * 100));
          return (
            <div key={it.key} className="flex items-center gap-2">
              <div className="w-20 shrink-0 text-xs text-stone-300">{it.label}</div>
              <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-stone-800">
                <div
                  className="h-full rounded-full bg-indigo-500/80"
                  style={{ width: `${width}%` }}
                />
              </div>
              <div className="w-14 shrink-0 text-right text-xs font-mono text-stone-400">
                {(v * 100).toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
