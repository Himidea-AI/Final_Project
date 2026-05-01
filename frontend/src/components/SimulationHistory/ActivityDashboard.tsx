/**
 * ActivityDashboard — 매니저 개인 시뮬 활동성 요약
 *
 * 리서치 #3 아이템. Pipedrive/Salesforce 영업 리더보드 벤치.
 * 팀 전체 리더보드는 백엔드 aggregation 엔드포인트 필요 (B1 영역, Phase 2).
 * 현재는 listSimulationHistory의 본인 범위 데이터를 그대로 집계.
 *
 * SimulationHistoryItem만 사용 (detail 조회 없이 1 API). 매출 같은 상세
 * 메트릭은 포함 안 함 — 개별 시뮬 상세/비교 트레이에서 확인.
 */

import { BarChart3, TrendingUp, MapPin, Activity } from 'lucide-react';
import type { SimulationHistoryItem } from '../../types/simulationHistory';

interface ActivityDashboardProps {
  items: SimulationHistoryItem[];
  total: number;
  isLoading: boolean;
}

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function formatRelative(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffMs = now - then;
  const m = Math.floor(diffMs / 60_000);
  if (m < 1) return '방금 전';
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 전`;
  const days = Math.floor(h / 24);
  if (days < 7) return `${days}일 전`;
  return new Date(iso).toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' });
}

function buildWeeklyBuckets(items: SimulationHistoryItem[]): { week: string; count: number }[] {
  // 최근 8주 (최신 주 → 과거)
  const nowMs = Date.now();
  const weekMs = 7 * 24 * 60 * 60 * 1000;
  const buckets: { week: string; count: number; start: number; end: number }[] = [];
  for (let i = 7; i >= 0; i--) {
    const end = nowMs - i * weekMs;
    const start = end - weekMs;
    buckets.push({
      week: `${new Date(start).getMonth() + 1}/${new Date(start).getDate()}`,
      count: 0,
      start,
      end,
    });
  }
  items.forEach((it) => {
    const t = new Date(it.created_at).getTime();
    const b = buckets.find((x) => t >= x.start && t < x.end);
    if (b) b.count += 1;
  });
  return buckets.map(({ week, count }) => ({ week, count }));
}

function topN(map: Map<string, number>, n: number): { key: string; count: number }[] {
  return Array.from(map.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([key, count]) => ({ key, count }));
}

export function ActivityDashboard({ items, total, isLoading }: ActivityDashboardProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-xl border border-stone-800 bg-stone-900/40"
          />
        ))}
      </div>
    );
  }

  if (items.length === 0) return null;

  const signalCounts = { green: 0, yellow: 0, red: 0, unknown: 0 };
  const districtMap = new Map<string, number>();
  const brandMap = new Map<string, number>();
  items.forEach((it) => {
    const s = it.market_entry_signal;
    if (s === 'green') signalCounts.green++;
    else if (s === 'yellow') signalCounts.yellow++;
    else if (s === 'red') signalCounts.red++;
    else signalCounts.unknown++;
    districtMap.set(it.district, (districtMap.get(it.district) ?? 0) + 1);
    brandMap.set(it.brand_name, (brandMap.get(it.brand_name) ?? 0) + 1);
  });

  const signalTotal =
    signalCounts.green + signalCounts.yellow + signalCounts.red + signalCounts.unknown || 1;
  const greenPct = Math.round((signalCounts.green / signalTotal) * 100);
  const yellowPct = Math.round((signalCounts.yellow / signalTotal) * 100);
  const redPct = 100 - greenPct - yellowPct;

  const weekly = buildWeeklyBuckets(items);
  const maxWeek = Math.max(1, ...weekly.map((w) => w.count));
  const last7Days = items.filter(
    (it) => new Date(it.created_at).getTime() > Date.now() - 7 * 24 * 60 * 60 * 1000,
  ).length;
  const topDistricts = topN(districtMap, 3);
  const topBrands = topN(brandMap, 3);
  const latest = items[0] ?? null;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {/* 총 시뮬 수 */}
        <StatCard
          label="총 시뮬 건수"
          value={total.toLocaleString()}
          sub={`최근 7일 ${last7Days}건`}
          icon={<BarChart3 className="h-4 w-4 text-indigo-400" />}
        />

        {/* Green 비율 */}
        <StatCard
          label="GREEN 비율"
          value={`${greenPct}%`}
          sub={`Y ${yellowPct}% · R ${redPct}%`}
          tone={greenPct >= 50 ? 'good' : greenPct >= 30 ? 'warn' : 'bad'}
          icon={<TrendingUp className="h-4 w-4 text-emerald-400" />}
        />

        {/* Top 동 */}
        <StatCard
          label="최다 분석 동"
          value={topDistricts[0]?.key ?? '—'}
          sub={topDistricts[0] ? `${topDistricts[0].count}건` : '데이터 없음'}
          icon={<MapPin className="h-4 w-4 text-indigo-400" />}
        />

        {/* 최근 활동 */}
        <StatCard
          label="최근 활동"
          value={latest ? formatRelative(latest.created_at) : '—'}
          sub={latest ? `${latest.client_name} · ${latest.district}` : '데이터 없음'}
          icon={<Activity className="h-4 w-4 text-indigo-400" />}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {/* 주간 시뮬 수 스파크 바 */}
        <div className="md:col-span-2 rounded-xl border border-stone-800 bg-stone-900/40 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500">
              최근 8주 주간 시뮬 수
            </span>
            <span className="text-[0.625rem] text-stone-600">
              {startOfDay(new Date(Date.now() - 8 * 7 * 24 * 60 * 60 * 1000)) > 0 ? '' : ''}
              {items.length}건 집계 · peak {maxWeek}
            </span>
          </div>
          <div className="flex h-16 items-end gap-1.5">
            {weekly.map((w, i) => {
              const pct = (w.count / maxWeek) * 100;
              return (
                <div key={i} className="flex flex-1 flex-col items-center justify-end gap-1">
                  <div
                    className="w-full rounded-t bg-indigo-500/80 transition-all"
                    style={{ height: `${pct}%`, minHeight: w.count > 0 ? '4px' : '0' }}
                    title={`${w.week}: ${w.count}건`}
                  />
                  <span className="text-[0.5625rem] font-mono text-stone-600">{w.week}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Top 브랜드 */}
        <div className="rounded-xl border border-stone-800 bg-stone-900/40 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500">
              최다 분석 브랜드
            </span>
          </div>
          <div className="space-y-2">
            {topBrands.length === 0 ? (
              <span className="text-xs text-stone-500">데이터 없음</span>
            ) : (
              topBrands.map((b, i) => (
                <div key={b.key} className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2 text-xs text-stone-300">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-stone-800 text-[0.5625rem] font-mono text-stone-400">
                      {i + 1}
                    </span>
                    <span className="truncate">{b.key}</span>
                  </span>
                  <span className="font-mono text-[0.6875rem] text-indigo-400 tabular-nums">
                    {b.count}건
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  icon,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: React.ReactNode;
  tone?: 'good' | 'warn' | 'bad' | 'neutral';
}) {
  const toneCls =
    tone === 'good'
      ? 'text-emerald-400'
      : tone === 'warn'
        ? 'text-amber-400'
        : tone === 'bad'
          ? 'text-rose-400'
          : 'text-stone-100';
  return (
    <div className="rounded-xl border border-stone-800 bg-stone-900/40 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[0.625rem] font-black uppercase tracking-widest text-stone-500">
          {label}
        </span>
        {icon}
      </div>
      <div className={`text-xl font-black tabular-nums ${toneCls}`}>{value}</div>
      {sub && <div className="mt-1 text-[0.625rem] text-stone-500">{sub}</div>}
    </div>
  );
}
