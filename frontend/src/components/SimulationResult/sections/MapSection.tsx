import { useMemo } from 'react';
import type { SimulationOutput } from '../../../types';
import { SectionLabel } from '../shared/SectionLabel';
import { MarketMap, type Competitor, type RankingEntry } from './MarketMap';

interface Props {
  simResult: SimulationOutput;
}

const DEFAULT_MAPO_CENTER = { lat: 37.5558, lng: 126.9193 };

const DONG_COORDS: Record<string, { lat: number; lng: number }> = {
  아현동: { lat: 37.5502, lng: 126.9594 },
  공덕동: { lat: 37.543, lng: 126.9519 },
  도화동: { lat: 37.5393, lng: 126.9457 },
  용강동: { lat: 37.5382, lng: 126.9383 },
  대흥동: { lat: 37.548, lng: 126.9437 },
  염리동: { lat: 37.5523, lng: 126.9474 },
  신수동: { lat: 37.5453, lng: 126.9361 },
  서강동: { lat: 37.5493, lng: 126.9347 },
  서교동: { lat: 37.5565, lng: 126.9239 },
  합정동: { lat: 37.5497, lng: 126.9143 },
  망원1동: { lat: 37.5558, lng: 126.9059 },
  망원2동: { lat: 37.5531, lng: 126.9021 },
  연남동: { lat: 37.5617, lng: 126.9226 },
  성산1동: { lat: 37.5663, lng: 126.9069 },
  성산2동: { lat: 37.5706, lng: 126.9111 },
  상암동: { lat: 37.5789, lng: 126.8899 },
};

function buildCompetitors(simResult: SimulationOutput): Competitor[] {
  // all_competitor_locations (winner+top3 멀티동) 우선, fallback은 winner 단일 동
  if (simResult.all_competitor_locations?.length) {
    return simResult.all_competitor_locations
      .filter((s) => typeof s.lat === 'number' && typeof s.lng === 'number')
      .slice(0, 200)
      .map((s) => ({
        place_name: s.place_name ?? '경쟁점',
        lat: s.lat,
        lng: s.lng,
        distance_m: s.distance_m,
        is_franchise: s.is_franchise ?? false,
        brand_name: s.brand_name ?? null,
        daily_revenue: null,
      }));
  }
  const compIntel = simResult.competitor_intel as Record<string, unknown> | null | undefined;
  const competition = compIntel?.['competition_500m'] as
    | { samples?: Array<Record<string, unknown>> }
    | undefined;
  const list = competition?.samples ?? [];
  return list
    .filter(
      (s) => typeof s.lat === 'number' && (typeof s.lng === 'number' || typeof s.lon === 'number'),
    )
    .slice(0, 100)
    .map((s) => ({
      place_name: String(s.place_name ?? '경쟁점'),
      lat: Number(s.lat),
      lng: Number(s.lng ?? s.lon),
      distance_m: typeof s.distance_m === 'number' ? s.distance_m : undefined,
      is_franchise: Boolean(s.is_franchise),
      brand_name: typeof s.brand_name === 'string' ? s.brand_name : null,
      daily_revenue:
        typeof s.daily_revenue === 'number'
          ? s.daily_revenue
          : typeof s.est_daily_revenue === 'number'
            ? s.est_daily_revenue
            : null,
    }));
}

function buildRankings(simResult: SimulationOutput): RankingEntry[] {
  return (simResult.district_rankings ?? []).map((r) => ({
    district: r.district,
    score: r.score,
    closure_rate: r.closure_rate,
  }));
}

function buildCenter(simResult: SimulationOutput): { lat: number; lng: number } {
  // winner_district 좌표 우선 → competitor_intel.target_coords → 기본 마포 중심
  const sim = simResult as SimulationOutput & Record<string, unknown>;
  const winner = (sim.winner_district ?? sim.target_district) as string | undefined;
  if (winner && DONG_COORDS[winner]) return DONG_COORDS[winner];
  const compIntel = simResult.competitor_intel as Record<string, unknown> | null | undefined;
  const target = compIntel?.['target_coords'] as { lat?: unknown; lng?: unknown } | undefined;
  if (target && typeof target.lat === 'number' && typeof target.lng === 'number') {
    return { lat: target.lat, lng: target.lng };
  }
  return DEFAULT_MAPO_CENTER;
}

export function MapSection({ simResult }: Props) {
  // Memoize 대상: buildCompetitors/buildRankings/buildCenter가 매 렌더마다 새 배열 참조를 만들면
  // MarketMap useEffect deps가 매번 바뀌어 지도·choropleth가 무한 재초기화된다.
  const competitors = useMemo(() => buildCompetitors(simResult), [simResult]);
  const rankings = useMemo(() => buildRankings(simResult), [simResult]);
  const center = useMemo(() => buildCenter(simResult), [simResult]);

  const sim = simResult as SimulationOutput & Record<string, any>;
  const district = sim.winner_district ?? sim.target_district ?? '—';
  const brand = sim.brand_name ?? '브랜드 미지정';
  const businessType = sim.business_type ?? sim.biz_type ?? '—';
  const address = sim.target_address ?? '—';

  const totalCompetitors = competitors.length;
  const withinCompetitors = competitors.filter(
    (c) => (c.distance_m ?? Number.POSITIVE_INFINITY) <= 500,
  ).length;

  const compIntel = simResult.competitor_intel as Record<string, unknown> | null | undefined;
  const saturation =
    (compIntel?.['competition_500m'] as { saturation_level?: string } | undefined)
      ?.saturation_level ?? null;

  return (
    <section>
      <SectionLabel label="MARKET MAP" subtitle="마포 16동 choropleth · 경쟁점 분포" />
      <div className="relative overflow-hidden rounded-lg border border-zinc-700">
        <MarketMap
          center={center}
          competitors={competitors}
          rankings={rankings}
          radius={500}
          winnerDistrict={simResult.winner_district}
          height={520}
        />

        {/* Layer 5 — 좌상단 타겟 요약 패널 */}
        <div className="absolute left-4 top-4 z-10 max-w-xs rounded-lg border border-zinc-700 bg-zinc-900/75 p-4 backdrop-blur-xl">
          <div className="text-[10px] uppercase tracking-widest text-zinc-400">Target</div>
          <div className="mt-1 text-sm font-semibold text-zinc-100">{brand}</div>
          <div className="mt-0.5 text-xs text-zinc-400">{businessType}</div>
          <div className="mt-2 border-t border-zinc-700/60 pt-2">
            <div className="text-xs text-amber-400">{district}</div>
            {address !== '—' && <div className="mt-0.5 text-[11px] text-zinc-500">{address}</div>}
            <div className="mt-1 font-mono text-[10px] text-zinc-500">
              {center.lat.toFixed(5)}, {center.lng.toFixed(5)}
            </div>
          </div>
        </div>

        {/* Layer 6 — 좌하단 범례 패널 */}
        <div className="absolute bottom-4 left-4 z-10 rounded-lg border border-zinc-700 bg-zinc-900/75 p-3 backdrop-blur-xl">
          <div className="mb-2 text-[10px] uppercase tracking-widest text-zinc-400">Legend</div>
          <div className="space-y-1.5 text-xs text-zinc-300">
            <div className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full border border-amber-400/80 bg-amber-500/20" />
              <span>
                반경 500m · 내부{' '}
                <span className="font-mono text-amber-400">{withinCompetitors}</span> / 총{' '}
                <span className="font-mono text-zinc-100">{totalCompetitors}</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span
                style={{
                  width: 0,
                  height: 0,
                  borderLeft: '6px solid transparent',
                  borderRight: '6px solid transparent',
                  borderBottom: '11px solid #ef4444',
                  display: 'inline-block',
                }}
              />
              <span>반경 내 경쟁점</span>
            </div>
            <div className="flex items-center gap-2">
              <span
                style={{
                  width: 0,
                  height: 0,
                  borderLeft: '5px solid transparent',
                  borderRight: '5px solid transparent',
                  borderBottom: '9px solid #ef4444',
                  opacity: 0.45,
                  display: 'inline-block',
                }}
              />
              <span>외부 경쟁점</span>
            </div>
            {saturation && (
              <div className="pt-1 text-[10px] text-zinc-500">포화도: {saturation}</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
