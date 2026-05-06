import { useMemo } from 'react';
import { AlertTriangle } from 'lucide-react';
import type { SimulationOutput } from '../../../types';
import { useAuth } from '../../../auth/AuthContext';
import { getDongCount, getGuFromDong } from '../../../data/seoulRegions';
import { useSimulationStore } from '../../../stores/simulationStore';
import { SectionLabel } from '../shared/SectionLabel';
import { MarketMap, haversineM, type Competitor, type RankingEntry } from './MarketMap';

interface Props {
  simResult: SimulationOutput;
  // 주요 경쟁점 top5 — 사이드바 카드와 동일. MarketMap 에서 큰 번호 라벨로 강조.
  // lat/lng 가 없는 항목은 내부에서 필터.
  topCompetitors?: Array<{
    place_name?: string | null;
    lat?: number | null;
    lng?: number | null;
  }>;
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
  // all_competitor_locations (winner+top3 4동, 1.5km 검색) + competitor_intel.samples (분석 동 500m)
  // 두 소스 통합 → place_name + 좌표 기준 dedup → 최대 200개.
  // 사용자 보고 "컴포즈커피 망원시장점이 카드엔 있는데 지도엔 없다" → samples 만 가진 매장 누락 차단.
  const compIntel = simResult.competitor_intel as Record<string, unknown> | null | undefined;
  const competition = compIntel?.['competition_500m'] as
    | { samples?: Array<Record<string, unknown>> }
    | undefined;
  const samplesRaw = competition?.samples ?? [];

  if (simResult.all_competitor_locations?.length) {
    const merged: Competitor[] = simResult.all_competitor_locations
      .filter((s) => typeof s.lat === 'number' && typeof s.lng === 'number')
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
    // samples 추가 (all_competitor_locations 에 없는 매장 union)
    for (const s of samplesRaw) {
      const lat = typeof s.lat === 'number' ? s.lat : null;
      const lng =
        typeof s.lng === 'number' ? s.lng : typeof s.lon === 'number' ? (s.lon as number) : null;
      if (lat == null || lng == null) continue;
      merged.push({
        place_name: String(s.place_name ?? '경쟁점'),
        lat,
        lng,
        distance_m: typeof s.distance_m === 'number' ? s.distance_m : undefined,
        is_franchise: Boolean(s.is_franchise),
        brand_name: typeof s.brand_name === 'string' ? s.brand_name : null,
        daily_revenue: null,
        place_url: typeof s.place_url === 'string' ? s.place_url : null,
        phone: typeof s.phone === 'string' ? s.phone : null,
      });
    }
    // dedup — place_name + 좌표(소수 5자리) 동일하면 동일 매장으로 판단
    const seen = new Set<string>();
    const deduped: Competitor[] = [];
    for (const c of merged) {
      const key = `${c.place_name}_${c.lat.toFixed(5)}_${c.lng.toFixed(5)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      deduped.push(c);
      if (deduped.length >= 200) break;
    }
    return deduped;
  }
  // all_competitor_locations 없으면 samples 만 사용 (구버전 응답 호환)
  const list = samplesRaw;
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

// 추천 동(winner_district + top3) 내 공실 중 score 상위 4개 spot 반환.
// 기준: winner 동 spot 우선 (backend 가 score 부여) → 부족 시 top3 동 spot 으로 채움 (listing_count 정렬).
// 2026-05-06: winner 동 spot 0건이거나 부족할 때 1~4위 자리 비는 회귀 차단.
//   사용자 보고 "망원2동(winner) 매물 0건이라 spot 1위만 보임" → top3 spot 으로 4개 채움.
// 1순위가 펄싱 핀 + 반경원 중심. 2~4순위는 번호 라벨 핀으로 비교 표시.
function buildBestVacancies(simResult: SimulationOutput): BestVacancy[] {
  const sim = simResult as SimulationOutput & Record<string, unknown>;
  const winner = (sim.winner_district ?? sim.target_district) as string | undefined;
  if (!winner) return [];
  const top3 = Array.isArray(sim.top_3_candidates)
    ? (sim.top_3_candidates as string[]).filter((d): d is string => typeof d === 'string')
    : [];
  const spots = (sim.vacancy_spots as VacancySpotRaw[] | undefined) ?? [];

  const toCandidate = (s: VacancySpotRaw) => ({
    lat: s.lat as number,
    lng: s.lon as number,
    listingCount: typeof s.listing_count === 'number' ? s.listing_count : 0,
    dongName: String(s.dong_name),
    score: typeof s.score === 'number' ? s.score : null,
    subwayDistanceM: typeof s.subway_distance_m === 'number' ? s.subway_distance_m : null,
    competitorCount500m:
      typeof s.competitor_count_500m === 'number' ? s.competitor_count_500m : null,
  });

  const validSpots = spots.filter(
    (s) =>
      typeof s.lat === 'number' &&
      typeof s.lon === 'number' &&
      Number.isFinite(s.lat) &&
      Number.isFinite(s.lon),
  );

  // 1순위 후보군: winner 동 spot (backend score 부여됨)
  const winnerSorted = validSpots
    .filter((s) => s.dong_name === winner)
    .map(toCandidate)
    .sort((a, b) => {
      const sa = a.score ?? Number.NEGATIVE_INFINITY;
      const sb = b.score ?? Number.NEGATIVE_INFINITY;
      if (sa !== sb) return sb - sa;
      return b.listingCount - a.listingCount;
    });

  // 2순위 후보군: top3 동 spot (score 없음, listing_count 정렬)
  const top3Set = new Set(top3);
  const top3Sorted = validSpots
    .filter((s) => top3Set.has(String(s.dong_name)) && s.dong_name !== winner)
    .map(toCandidate)
    .sort((a, b) => b.listingCount - a.listingCount);

  // winner 부족분만큼 top3 동 spot 으로 채움
  const merged = [...winnerSorted, ...top3Sorted];

  // 근접 중복 제거 — 50m 이내는 동일 spot 으로 보고 상위 우선 유지.
  const DEDUP_RADIUS_M = 50;
  const deduped: BestVacancy[] = [];
  for (const cand of merged) {
    const tooClose = deduped.some(
      (kept) => haversineM(kept.lat, kept.lng, cand.lat, cand.lng) <= DEDUP_RADIUS_M,
    );
    if (!tooClose) deduped.push(cand);
    if (deduped.length >= 4) break;
  }
  return deduped;
}

export function MapSection({ simResult, topCompetitors }: Props) {
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
  // topCompetitors → MarketMap 형식 (rank 부여) 변환. lat/lng 둘 다 number 필수.
  const topCompetitorsForMap = useMemo(
    () =>
      (topCompetitors ?? [])
        .filter(
          (t): t is { place_name?: string | null; lat: number; lng: number } =>
            typeof t.lat === 'number' && typeof t.lng === 'number',
        )
        .slice(0, 5)
        .map((t, idx) => ({
          place_name: t.place_name ?? '경쟁점',
          lat: t.lat,
          lng: t.lng,
          rank: idx + 1,
        })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [topCompetitors],
  );
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
  // within 판정 = 4 spot 중 최단거리 ≤ radius 면 내부 (MarketMap 의 within 분기와 동일).
  // bestVacancies 4개 좌표 union → 어느 하나라도 반경 안이면 내부.
  const _withinSpots = bestVacancies.length > 0 ? bestVacancies : [center];
  const withinCompetitors = competitors.filter((c) => {
    const minDist = Math.min(..._withinSpots.map((sp) => haversineM(sp.lat, sp.lng, c.lat, c.lng)));
    return minDist <= effectiveRadius;
  }).length;

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
        {/* winner != spot 1위 동 케이스 안내 — 큰 배너로 강조.
            bestVacancy.dongName !== winner 일 때만 표시. */}
        {bestVacancy && bestVacancy.dongName !== district && district !== '—' && (
          <div className="rounded-2xl border-2 border-warning bg-warning/15 p-4 shadow-[0_0_24px_rgba(251,191,36,0.25)]">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-6 w-6 shrink-0 text-warning" />
              <div className="flex-1 space-y-2">
                <div className="text-sm font-black uppercase tracking-widest text-warning">
                  추천 입지 안내 — 매물 자동 보정
                </div>
                <div className="text-sm font-bold leading-relaxed text-foreground">
                  종합 점수 1순위 추천 동{' '}
                  <span className="rounded bg-primary/15 px-1.5 py-0.5 font-black text-primary">
                    {district}
                  </span>
                  에 <span className="font-black text-warning">실제 임대 매물이 없어</span>, 인접
                  후보 동{' '}
                  <span className="rounded bg-primary/15 px-1.5 py-0.5 font-black text-primary">
                    {bestVacancy.dongName}
                  </span>
                  의 매물 중 최적 위치를 공실 spot 1위로 자동 추천합니다.
                </div>
                <div className="text-xs leading-relaxed text-muted-foreground">
                  ▸ 분석 결과(반경 500m 동일업종, 평균 거리, 경쟁 강도, 임대료 인덱스), 주요 경쟁점,
                  동 한눈에 — 모두{' '}
                  <span className="font-bold text-foreground">{bestVacancy.dongName}</span> 기준으로
                  도출됩니다.
                </div>
              </div>
            </div>
          </div>
        )}
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
          topCompetitors={topCompetitorsForMap}
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
            {topCompetitorsForMap.length > 0 && (
              <div className="flex items-center gap-2">
                <span
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: '9999px',
                    background: '#facc15',
                    border: '2px solid #ffffff',
                    boxShadow: '0 0 6px rgba(250,204,21,0.7)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 9,
                    fontWeight: 900,
                    color: '#1c1917',
                  }}
                >
                  1
                </span>
                <span>주요 경쟁점 (1~5위)</span>
              </div>
            )}
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
