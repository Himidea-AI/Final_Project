import { useMemo } from 'react';
import type { SimulationOutput } from '../../../types';
import { useAuth } from '../../../auth/AuthContext';
import { getDongCount, getGuFromDong } from '../../../data/seoulRegions';
import { useSimulationStore } from '../../../stores/simulationStore';
import { SectionLabel } from '../shared/SectionLabel';
import { MarketMap, haversineM, type Competitor, type RankingEntry } from './MarketMap';

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
        place_url: s.place_url ?? null,
        phone: s.phone ?? null,
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
      place_url: typeof s.place_url === 'string' ? s.place_url : null,
      phone: typeof s.phone === 'string' ? s.phone : null,
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

interface VacancySpotRaw {
  id?: number | string;
  lat?: unknown;
  lon?: unknown;
  dong_name?: unknown;
  listing_count?: unknown;
  // winner_district spot 한정으로 backend district_ranking._score_winner_spots 가 채움.
  score?: unknown;
  subway_distance_m?: unknown;
  competitor_count_500m?: unknown;
}

interface BestVacancy {
  lat: number;
  lng: number;
  listingCount: number;
  dongName: string;
  score: number | null;
  subwayDistanceM: number | null;
  competitorCount500m: number | null;
}

// 추천 동(winner_district) 내 공실 중 score 상위 4개 spot 반환.
// 기준: backend 가 spot 단위 score 를 부여한 경우(0~100, 경쟁밀도 0.45 + 지하철 접근성 0.35 + 매물 활성도 0.20 가중합).
// score 가 없으면 listing_count 최대 fallback (구버전 응답 호환).
// 1순위가 펄싱 핀 + 반경원 중심. 2~4순위는 번호 라벨 핀으로 비교 표시.
function buildBestVacancies(simResult: SimulationOutput): BestVacancy[] {
  const sim = simResult as SimulationOutput & Record<string, unknown>;
  const winner = (sim.winner_district ?? sim.target_district) as string | undefined;
  if (!winner) return [];
  const spots = (sim.vacancy_spots as VacancySpotRaw[] | undefined) ?? [];
  const sorted = spots
    .filter((s) => s.dong_name === winner)
    .filter(
      (s) =>
        typeof s.lat === 'number' &&
        typeof s.lon === 'number' &&
        Number.isFinite(s.lat) &&
        Number.isFinite(s.lon),
    )
    .map((s) => ({
      lat: s.lat as number,
      lng: s.lon as number,
      listingCount: typeof s.listing_count === 'number' ? s.listing_count : 0,
      dongName: String(s.dong_name),
      score: typeof s.score === 'number' ? s.score : null,
      subwayDistanceM: typeof s.subway_distance_m === 'number' ? s.subway_distance_m : null,
      competitorCount500m:
        typeof s.competitor_count_500m === 'number' ? s.competitor_count_500m : null,
    }))
    .sort((a, b) => {
      const sa = a.score ?? Number.NEGATIVE_INFINITY;
      const sb = b.score ?? Number.NEGATIVE_INFINITY;
      if (sa !== sb) return sb - sa;
      return b.listingCount - a.listingCount;
    });
  // 근접 중복 제거 — 같은 매물군이 다른 row 로 들어와 1·2·3위가 동일 좌표인 케이스 방어.
  // 50m 이내는 동일 spot 으로 보고 상위 score 만 유지 → 화면에서 #1 펄싱핀에 #2·#3 핀이
  // 가려지는 회귀 차단 (사용자 보고: "공실 #1 과 #4만 보인다").
  const DEDUP_RADIUS_M = 50;
  const deduped: BestVacancy[] = [];
  for (const cand of sorted) {
    const tooClose = deduped.some(
      (kept) => haversineM(kept.lat, kept.lng, cand.lat, cand.lng) <= DEDUP_RADIUS_M,
    );
    if (!tooClose) deduped.push(cand);
    if (deduped.length >= 4) break;
  }
  return deduped;
}

export function MapSection({ simResult }: Props) {
  // Memoize 대상: buildCompetitors/buildRankings/buildCenter가 매 렌더마다 새 배열 참조를 만들면
  // MarketMap useEffect deps가 매번 바뀌어 지도·choropleth가 무한 재초기화된다.
  const competitors = useMemo(() => buildCompetitors(simResult), [simResult]);
  const rankings = useMemo(() => buildRankings(simResult), [simResult]);
  const fallbackCenter = useMemo(() => buildCenter(simResult), [simResult]);
  const bestVacancies = useMemo(() => buildBestVacancies(simResult), [simResult]);
  const bestVacancy = bestVacancies[0] ?? null;
  // 핀/반경/TARGET 좌표 = 추천 동 내 best 공실 1순위 (있으면) → 없으면 동 대표좌표 fallback
  const center = bestVacancy ? { lat: bestVacancy.lat, lng: bestVacancy.lng } : fallbackCenter;
  // 자사 매장 좌표 (winner+top3 4동 안) — 로고 마커 + 영업구역 반경 원 표시용.
  const sameBrandLocations = useMemo(() => simResult.same_brand_locations ?? [], [simResult]);
  // 사용자 입력 영업구역 거리 — store.params 에서 직접 (응답에 echo 안 됨).
  const territoryRadiusM = useSimulationStore((s) => s.params?.territory_radius_m);

  const { brand: authBrand, user } = useAuth();
  // 사용자 입력 commercial_radius — backend 응답에 echo 안 되므로 store.params 에서 직접.
  const userRadius = useSimulationStore((s) => s.params?.commercial_radius);
  const sim = simResult as SimulationOutput & Record<string, any>;
  const district = sim.winner_district ?? sim.target_district ?? '—';
  // 회원가입 시 사업자등록번호로 받은 브랜드명 → user.company_name → fallback 순.
  // simResult.brand_name 은 백엔드가 시뮬 응답에 채울 수 있으니 우선시.
  const brand = sim.brand_name ?? authBrand?.brand_name ?? user?.company_name ?? '브랜드 미지정';
  const businessType = sim.business_type ?? sim.biz_type ?? '—';
  const address = sim.target_address ?? '—';

  const effectiveRadius = userRadius ?? 500;
  const totalCompetitors = competitors.length;
  // within 판정 = 화면 핀 좌표(center) 기준 haversine. 백엔드 distance_m 은 source 동 centroid
  // 기준이라 핀 위치와 정합 안 됨 → MarketMap 마커 색·legend 카운트 일치시킴.
  const withinCompetitors = competitors.filter(
    (c) => haversineM(center.lat, center.lng, c.lat, c.lng) <= effectiveRadius,
  ).length;

  const compIntel = simResult.competitor_intel as Record<string, unknown> | null | undefined;
  const saturation =
    (compIntel?.['competition_500m'] as { saturation_level?: string } | undefined)
      ?.saturation_level ?? null;

  // 시뮬 대상 구/동 개수 동적 — winner 또는 target 동에서 구 추출 (확장성: 25구 도입 시 자동 반영).
  const currentGu = getGuFromDong(sim.winner_district ?? sim.target_district);
  const currentDongCount = getDongCount(currentGu);

  return (
    <section>
      {/* 헤더 row — SectionLabel + Target 요약 박스 가로 배치 (lg+), 모바일은 stack. */}
      <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <SectionLabel
          label="MARKET MAP"
          subtitle={`${currentGu ?? '서울'} ${currentDongCount}동 choropleth · 경쟁점 분포`}
        />
        {/* Target 요약 박스 — 지도 밖 일반 박스 (이전 좌상단 overlay 에서 이동). */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-border bg-card px-4 py-2.5">
          <div className="flex items-center gap-2">
            <span className="text-[0.625rem] font-black uppercase tracking-widest text-muted-foreground">
              Target
            </span>
            <span className="text-sm font-semibold text-foreground">{brand}</span>
            <span className="text-xs text-muted-foreground">· {businessType}</span>
          </div>
          <div className="flex items-center gap-2 border-l border-border pl-4">
            <span className="text-xs font-bold text-primary">{district}</span>
            {address !== '—' && (
              <span className="text-[0.6875rem] text-muted-foreground">· {address}</span>
            )}
            <span className="font-mono text-[0.625rem] text-muted-foreground">
              · {center.lat.toFixed(5)}, {center.lng.toFixed(5)}
            </span>
          </div>
        </div>
      </div>
      <div className="relative overflow-hidden rounded-lg border border-border">
        <MarketMap
          center={center}
          competitors={competitors}
          rankings={rankings}
          radius={effectiveRadius}
          winnerDistrict={simResult.winner_district}
          height={520}
          targetSpot={bestVacancy ? { lat: bestVacancy.lat, lng: bestVacancy.lng } : null}
          targetSpots={bestVacancies.map((v) => ({ lat: v.lat, lng: v.lng }))}
          sameBrandLocations={sameBrandLocations}
          territoryRadiusM={territoryRadiusM ?? null}
          userBrand={brand}
        />

        {/* Layer 6 — 좌하단 범례 패널 */}
        <div className="absolute bottom-4 left-4 z-10 rounded-lg border border-border bg-card/75 p-3 backdrop-blur-xl">
          <div className="mb-2 text-[0.625rem] uppercase tracking-widest text-muted-foreground">
            Legend
          </div>
          <div className="space-y-1.5 text-xs text-foreground">
            <div className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full border border-primary/80 bg-primary/20" />
              <span>
                반경 {effectiveRadius.toLocaleString()}m · 내부{' '}
                <span className="font-mono text-primary">{withinCompetitors}</span> / 총{' '}
                <span className="font-mono text-foreground">{totalCompetitors}</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span
                style={{
                  width: 0,
                  height: 0,
                  borderLeft: '6px solid transparent',
                  borderRight: '6px solid transparent',
                  borderBottom: '11px solid var(--danger)',
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
                  borderBottom: '9px solid var(--danger)',
                  opacity: 0.45,
                  display: 'inline-block',
                }}
              />
              <span>외부 경쟁점</span>
            </div>
            {saturation && (
              <div className="pt-1 text-[0.625rem] text-muted-foreground">포화도: {saturation}</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
