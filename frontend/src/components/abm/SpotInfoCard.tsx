/**
 * SpotInfoCard — ABM 시뮬 실행 전 (시나리오 form 상단) 선택 spot 정보 카드.
 *
 * 사용자가 공실 spot 클릭 후 ABM 모드 진입 → 시뮬 실행 누르기 전까지의 대기 시간에
 * spot 컨텍스트 (주소·지하철·매물 수·동 통계·경쟁업체·brand fit) 표시.
 *
 * 모든 데이터 기존 props / 기존 endpoint 에서 조달 (backend 신규 endpoint 0개):
 *   - 주소: Kakao services.Geocoder.coord2Address (frontend SDK)
 *   - 지하철: storeNodes 의 tier='S' 항목 중 focusSpot 기준 haversine 최단
 *   - 매물 수: vacancySpots 매칭
 *   - 동 통계: simResult 에서 추출 후 prop 으로 전달
 *   - 경쟁업체: competitors prop 에서 500m 이내 필터
 *   - brand fit: competitors 카테고리 분포 + businessType heuristic
 */

import { useEffect, useState } from 'react';
import { MapPin, TrainFront, Store, Users, AlertTriangle } from 'lucide-react';
import { useKakaoMap } from '../kakao/useKakaoMap';

interface FocusSpot {
  lat: number;
  lon: number;
  label?: string;
}

interface StoreNodeLike {
  id: string;
  label: string;
  lat: number;
  lng: number;
  tier: string;
}

interface VacancySpotLike {
  id: number | string;
  lat: number;
  lon: number;
  listing_count?: number;
}

interface CompetitorLike {
  id?: string;
  name?: string;
  place_name?: string;
  brand_name?: string;
  lat: number;
  lng?: number;
  lon?: number;
  distance_m?: number;
  is_franchise?: boolean;
  category?: string;
}

export interface SpotDongStats {
  resident_pop?: number | null;
  floating_pop?: number | null;
  closure_rate?: number | null;
}

interface Props {
  focusSpot: FocusSpot;
  /** 부모가 fetch 한 지하철 포함 storeNodes — 없으면 dongName 으로 직접 fetch. */
  storeNodes?: StoreNodeLike[];
  /** focusSpot 의 동 이름 — storeNodes 없을 때 /api/mapo/spots/{dong} fetch 용. */
  dongName?: string | null;
  vacancySpots?: VacancySpotLike[];
  competitors?: CompetitorLike[];
  businessType?: string | null;
  dongStats?: SpotDongStats | null;
  /** vertical(default) = 우측 패널 stack / horizontal = 지도 아래 가로 4분할. */
  layout?: 'vertical' | 'horizontal';
}

interface KakaoCoord2AddressResult {
  road_address?: { address_name?: string } | null;
  address?: { address_name?: string } | null;
}

interface KakaoGeocoder {
  coord2Address: (
    lng: number,
    lat: number,
    cb: (results: KakaoCoord2AddressResult[], status: 'OK' | 'ZERO_RESULT' | 'ERROR') => void,
  ) => void;
}

interface KakaoServices {
  Geocoder: new () => KakaoGeocoder;
}

interface KakaoGlobal {
  maps?: { services?: KakaoServices };
}

const NEARBY_RADIUS_M = 500;

/** Haversine 거리 (m). */
function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6_371_000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/** competitors 카테고리 분포 분석 → brand fit 한 줄 요약. */
function computeBrandFit(
  businessType: string | null | undefined,
  nearbyCompetitors: Array<CompetitorLike & { distance_m: number }>,
): { tone: 'good' | 'warn' | 'danger'; text: string } | null {
  if (!businessType || nearbyCompetitors.length === 0) return null;
  const lowerType = businessType.toLowerCase();
  // 카테고리 토큰 매칭 — businessType 이 'cafe' 면 category 에 'cafe'/'카페' 포함
  const sameCount = nearbyCompetitors.filter((c) => {
    const cat = (c.category ?? '').toLowerCase();
    if (!cat) return false;
    return cat.includes(lowerType) || lowerType.includes(cat);
  }).length;
  const ratio = sameCount / nearbyCompetitors.length;
  if (ratio >= 0.3) {
    return {
      tone: 'danger',
      text: `포화 우려 — 동종 ${sameCount}/${nearbyCompetitors.length}개 (${Math.round(ratio * 100)}%). 차별화 필수.`,
    };
  }
  if (ratio >= 0.1) {
    return {
      tone: 'warn',
      text: `균형 — 동종 ${sameCount}/${nearbyCompetitors.length}개 (${Math.round(ratio * 100)}%). 표준 진입 가능.`,
    };
  }
  return {
    tone: 'good',
    text: `신규 진입 기회 — 동종 ${sameCount}/${nearbyCompetitors.length}개 (${Math.round(ratio * 100)}%). 대체 수요 검증 필요.`,
  };
}

export function SpotInfoCard({
  focusSpot,
  storeNodes,
  dongName,
  vacancySpots = [],
  competitors = [],
  businessType,
  dongStats,
  layout = 'vertical',
}: Props) {
  const { ready: kakaoReady } = useKakaoMap();
  const [address, setAddress] = useState<string | null>(null);
  const [addressLoading, setAddressLoading] = useState(false);
  const [fetchedNodes, setFetchedNodes] = useState<StoreNodeLike[] | null>(null);

  // 지하철 row 용 storeNodes — 부모 prop 우선, 없으면 dongName 으로 fetch.
  // 부모가 competitors 모드일 때 storeNodes 가 경쟁업체 좌표로 덮어써져
  // tier='S' 가 비므로 보조 fetch 필요.
  useEffect(() => {
    if (storeNodes && storeNodes.some((n) => n.tier === 'S')) {
      setFetchedNodes(null);
      return;
    }
    if (!dongName) return;
    let cancelled = false;
    fetch(`/api/mapo/spots/${encodeURIComponent(dongName)}?limit=4`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`spots ${r.status}`))))
      .then((data: { spots?: StoreNodeLike[] }) => {
        if (cancelled) return;
        if (Array.isArray(data.spots)) setFetchedNodes(data.spots);
      })
      .catch(() => {
        /* noop — 지하철 row 만 숨김 */
      });
    return () => {
      cancelled = true;
    };
  }, [dongName, storeNodes]);

  const effectiveNodes: StoreNodeLike[] =
    storeNodes && storeNodes.some((n) => n.tier === 'S') ? storeNodes : (fetchedNodes ?? []);

  // Kakao reverse geocode — focusSpot 변경 시 재요청.
  useEffect(() => {
    if (!kakaoReady) return;
    setAddress(null);
    setAddressLoading(true);
    const w = window as unknown as { kakao?: KakaoGlobal };
    const services = w.kakao?.maps?.services;
    if (!services?.Geocoder) {
      setAddressLoading(false);
      return;
    }
    const geocoder = new services.Geocoder();
    geocoder.coord2Address(focusSpot.lon, focusSpot.lat, (results, status) => {
      setAddressLoading(false);
      if (status !== 'OK' || !results.length) return;
      const first = results[0];
      const addr = first.road_address?.address_name || first.address?.address_name;
      if (addr) setAddress(addr);
    });
  }, [kakaoReady, focusSpot.lat, focusSpot.lon]);

  // 가장 가까운 지하철 — effectiveNodes 중 tier='S' 만.
  const subwayRow = (() => {
    const subways = effectiveNodes.filter((n) => n.tier === 'S');
    if (subways.length === 0) return null;
    let best = subways[0];
    let bestDist = haversineMeters(focusSpot.lat, focusSpot.lon, best.lat, best.lng);
    for (const n of subways.slice(1)) {
      const d = haversineMeters(focusSpot.lat, focusSpot.lon, n.lat, n.lng);
      if (d < bestDist) {
        bestDist = d;
        best = n;
      }
    }
    return { label: best.label, distanceM: Math.round(bestDist) };
  })();

  // listing_count 매칭 — focusSpot 좌표 ±0.0001 (~10m).
  const listingCount = (() => {
    const match = vacancySpots.find(
      (s) => Math.abs(s.lat - focusSpot.lat) < 1e-4 && Math.abs(s.lon - focusSpot.lon) < 1e-4,
    );
    return match?.listing_count ?? null;
  })();

  // 주변 경쟁업체 — 500m 이내 distance 오름차순 top 5.
  const nearbyCompetitors = competitors
    .map((c) => {
      const lng = c.lng ?? c.lon;
      if (typeof lng !== 'number') return null;
      const d = haversineMeters(focusSpot.lat, focusSpot.lon, c.lat, lng);
      return { ...c, distance_m: d };
    })
    .filter(
      (c): c is CompetitorLike & { distance_m: number } =>
        c !== null && c.distance_m <= NEARBY_RADIUS_M,
    )
    .sort((a, b) => a.distance_m - b.distance_m);

  const top5Competitors = nearbyCompetitors.slice(0, 5);
  const brandFit = computeBrandFit(businessType, nearbyCompetitors);

  // 동 통계 표시 여부 — 적어도 1개 값 존재해야 섹션 노출.
  const hasDongStats =
    dongStats &&
    (dongStats.resident_pop != null ||
      dongStats.floating_pop != null ||
      dongStats.closure_rate != null);

  if (layout === 'horizontal') {
    return (
      <div className="w-full h-full grid grid-cols-4 gap-2 overflow-y-auto">
        {/* Col 1: 헤더 + 주소 + 지하철 */}
        <div className="flex flex-col gap-2 rounded-xl border border-primary/20 bg-white p-3 min-w-0 text-stone-900">
          <div className="flex items-start justify-between gap-2">
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="text-[8.5px] font-black text-primary uppercase tracking-[0.25em]">
                선택 SPOT
              </span>
              <h4 className="text-sm font-black text-foreground tracking-tight leading-tight truncate">
                {focusSpot.label || '공실 후보'}
              </h4>
            </div>
            <MapPin className="h-3.5 w-3.5 shrink-0 text-primary" />
          </div>
          <div className="flex flex-col gap-0.5 min-w-0">
            <span className="text-[8.5px] font-black text-stone-500 uppercase tracking-widest">
              주소
            </span>
            <span className="text-[10px] text-stone-900 tracking-tight leading-snug break-keep line-clamp-2">
              {address ??
                (addressLoading
                  ? '주소 조회 중…'
                  : `${focusSpot.lat.toFixed(5)}, ${focusSpot.lon.toFixed(5)}`)}
            </span>
          </div>
          {subwayRow && (
            <div className="flex items-start gap-1.5 mt-auto">
              <TrainFront className="mt-0.5 h-3 w-3 shrink-0 text-cyan-600" />
              <div className="flex flex-col min-w-0">
                <span className="text-[8.5px] font-black text-stone-500 uppercase tracking-widest">
                  지하철
                </span>
                <span className="text-[10px] text-stone-900 tracking-tight truncate">
                  {subwayRow.label}{' '}
                  <span className="font-mono tabular-nums text-cyan-700">
                    · {subwayRow.distanceM}m
                  </span>
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Col 2: 동 통계 + listing_count */}
        <div className="flex flex-col gap-2 rounded-xl border border-emerald-500/30 bg-white p-3 min-w-0 text-stone-900">
          <div className="flex items-center gap-1.5">
            <Users className="h-3 w-3 text-emerald-600" />
            <span className="text-[8.5px] font-black text-emerald-700 uppercase tracking-widest">
              동 통계
            </span>
          </div>
          {hasDongStats ? (
            <div className="flex flex-col gap-0.5 text-[10px] text-stone-900">
              {dongStats?.resident_pop != null && (
                <div className="flex justify-between gap-2">
                  <span className="text-stone-500 truncate">주거</span>
                  <span className="font-mono tabular-nums font-bold">
                    {dongStats.resident_pop.toLocaleString()}
                  </span>
                </div>
              )}
              {dongStats?.floating_pop != null && (
                <div className="flex justify-between gap-2">
                  <span className="text-stone-500 truncate">유동</span>
                  <span className="font-mono tabular-nums font-bold">
                    {dongStats.floating_pop.toLocaleString()}
                  </span>
                </div>
              )}
              {dongStats?.closure_rate != null && (
                <div className="flex justify-between gap-2">
                  <span className="text-stone-500 truncate">폐업률</span>
                  <span className="font-mono tabular-nums font-bold text-rose-600">
                    {(dongStats.closure_rate * 100).toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
          ) : (
            <p className="text-[9.5px] text-stone-400 italic">통계 미제공</p>
          )}
          {listingCount != null && listingCount > 0 && (
            <div className="flex items-center gap-1.5 mt-auto pt-1 border-t border-stone-200">
              <Store className="h-3 w-3 shrink-0 text-amber-600" />
              <span className="text-[10px] text-stone-900 tracking-tight">
                매물 <span className="font-black text-amber-700 tabular-nums">{listingCount}</span>
                건
              </span>
            </div>
          )}
        </div>

        {/* Col 3: 경쟁업체 top 5 */}
        <div className="flex flex-col gap-1.5 rounded-xl border border-stone-300 bg-white p-3 min-w-0 text-stone-900">
          <div className="flex items-center justify-between">
            <span className="text-[8.5px] font-black text-stone-500 uppercase tracking-widest">
              500m 경쟁/자사
            </span>
            <span className="text-[8.5px] font-mono text-stone-500 tabular-nums">
              {nearbyCompetitors.length}
            </span>
          </div>
          {top5Competitors.length === 0 ? (
            <p className="text-[9.5px] text-stone-400 italic">없음</p>
          ) : (
            <ul className="flex flex-col gap-0.5">
              {top5Competitors.map((c, i) => {
                const name = c.place_name || c.name || c.brand_name || '경쟁업체';
                const isOwn = c.is_franchise && c.category === 'own_brand';
                return (
                  <li
                    key={c.id ?? `${name}-${i}`}
                    className="flex items-center justify-between gap-2 px-1.5 py-0.5 rounded"
                  >
                    <span className="text-[9.5px] font-bold text-stone-900 tracking-tight truncate">
                      {name}
                      {isOwn && (
                        <span className="ml-1 text-[8px] font-mono text-primary uppercase">
                          [자]
                        </span>
                      )}
                    </span>
                    <span className="shrink-0 text-[9px] font-mono tabular-nums text-cyan-700">
                      {Math.round(c.distance_m)}m
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Col 4: Brand fit */}
        <div
          className={`flex flex-col gap-2 rounded-xl border p-3 min-w-0 bg-white ${
            brandFit?.tone === 'danger'
              ? 'border-rose-500/40'
              : brandFit?.tone === 'warn'
                ? 'border-amber-500/40'
                : brandFit?.tone === 'good'
                  ? 'border-emerald-500/40'
                  : 'border-stone-300'
          }`}
        >
          <div className="flex items-center gap-1.5">
            <AlertTriangle
              className={`h-3 w-3 ${
                brandFit?.tone === 'danger'
                  ? 'text-rose-600'
                  : brandFit?.tone === 'warn'
                    ? 'text-amber-600'
                    : brandFit?.tone === 'good'
                      ? 'text-emerald-600'
                      : 'text-stone-500'
              }`}
            />
            <span className="text-[8.5px] font-black uppercase tracking-widest text-stone-500">
              Brand Fit
            </span>
          </div>
          <p
            className={`text-[10px] tracking-tight leading-snug ${
              brandFit?.tone === 'danger'
                ? 'text-rose-700'
                : brandFit?.tone === 'warn'
                  ? 'text-amber-700'
                  : brandFit?.tone === 'good'
                    ? 'text-emerald-700'
                    : 'text-stone-400 italic'
            }`}
          >
            {brandFit?.text ?? '업종/경쟁업체 정보 부족 — fit 계산 불가'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full box-glass rounded-2xl p-5 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1 min-w-0">
          <span className="text-[9px] font-black text-primary uppercase tracking-[0.3em]">
            선택 SPOT
          </span>
          <h4 className="text-base font-black text-foreground tracking-tight leading-tight truncate">
            {focusSpot.label || '공실 후보'}
          </h4>
        </div>
        <div className="shrink-0 px-2 py-1 rounded-md border border-primary/30 bg-primary/10">
          <MapPin className="h-3.5 w-3.5 text-primary" />
        </div>
      </div>

      {/* 주소 */}
      <div className="flex items-start gap-2 text-[11px]">
        <MapPin className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="text-[9px] font-black text-muted-foreground uppercase tracking-widest">
            주소
          </span>
          <span className="text-foreground tracking-tight leading-snug break-keep">
            {address ??
              (addressLoading
                ? '주소 조회 중…'
                : `${focusSpot.lat.toFixed(5)}, ${focusSpot.lon.toFixed(5)}`)}
          </span>
        </div>
      </div>

      {/* 가장 가까운 지하철 */}
      {subwayRow && (
        <div className="flex items-start gap-2 text-[11px]">
          <TrainFront className="mt-0.5 h-3 w-3 shrink-0 text-cyan-400" />
          <div className="flex flex-col gap-0.5 min-w-0">
            <span className="text-[9px] font-black text-muted-foreground uppercase tracking-widest">
              가장 가까운 지하철
            </span>
            <span className="text-foreground tracking-tight">
              {subwayRow.label}{' '}
              <span className="font-mono tabular-nums text-cyan-300/90">
                · {subwayRow.distanceM}m
              </span>
            </span>
          </div>
        </div>
      )}

      {/* listing_count */}
      {listingCount != null && listingCount > 0 && (
        <div className="flex items-start gap-2 text-[11px]">
          <Store className="mt-0.5 h-3 w-3 shrink-0 text-amber-400" />
          <div className="flex flex-col gap-0.5">
            <span className="text-[9px] font-black text-muted-foreground uppercase tracking-widest">
              인근 매물
            </span>
            <span className="text-foreground tracking-tight">
              <span className="font-black text-amber-300 tabular-nums">{listingCount}</span>건
              조회됨
            </span>
          </div>
        </div>
      )}

      {/* 동 통계 */}
      {hasDongStats && (
        <div className="flex flex-col gap-1.5 rounded-lg border border-stone-800 bg-stone-950/40 p-2.5">
          <div className="flex items-center gap-1.5">
            <Users className="h-3 w-3 text-emerald-400" />
            <span className="text-[9px] font-black text-emerald-300 uppercase tracking-widest">
              동 통계
            </span>
          </div>
          <div className="flex flex-col gap-0.5 text-[10.5px] text-foreground">
            {dongStats?.resident_pop != null && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">주거 인구</span>
                <span className="font-mono tabular-nums font-bold">
                  {dongStats.resident_pop.toLocaleString()}명
                </span>
              </div>
            )}
            {dongStats?.floating_pop != null && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">유동 인구</span>
                <span className="font-mono tabular-nums font-bold">
                  {dongStats.floating_pop.toLocaleString()}명
                </span>
              </div>
            )}
            {dongStats?.closure_rate != null && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">최근 폐업률</span>
                <span className="font-mono tabular-nums font-bold text-rose-300">
                  {(dongStats.closure_rate * 100).toFixed(1)}%
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 주변 경쟁업체 */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[9px] font-black text-muted-foreground uppercase tracking-widest">
            500m 내 경쟁/자사
          </span>
          <span className="text-[9px] font-mono text-muted-foreground tabular-nums">
            {nearbyCompetitors.length}개
          </span>
        </div>
        {top5Competitors.length === 0 ? (
          <p className="text-[10.5px] text-muted-foreground italic">
            반경 500m 내 등록 경쟁업체 없음
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {top5Competitors.map((c, i) => {
              const name = c.place_name || c.name || c.brand_name || '경쟁업체';
              const isOwn = c.is_franchise && c.category === 'own_brand';
              return (
                <li
                  key={c.id ?? `${name}-${i}`}
                  className="flex items-center justify-between gap-2 rounded-md border border-stone-800 bg-stone-950/30 px-2 py-1.5"
                >
                  <div className="flex flex-col min-w-0">
                    <span className="text-[10.5px] font-bold text-foreground tracking-tight truncate">
                      {name}
                      {isOwn && (
                        <span className="ml-1.5 text-[8.5px] font-mono text-primary uppercase">
                          [자사]
                        </span>
                      )}
                    </span>
                    {c.category && !isOwn && (
                      <span className="text-[9px] text-muted-foreground tracking-tight truncate">
                        {c.category}
                      </span>
                    )}
                  </div>
                  <span className="shrink-0 text-[10px] font-mono tabular-nums text-cyan-300/90">
                    {Math.round(c.distance_m)}m
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Brand fit */}
      {brandFit && (
        <div
          className={`flex items-start gap-2 rounded-lg border px-2.5 py-2 text-[10.5px] tracking-tight leading-snug ${
            brandFit.tone === 'danger'
              ? 'border-rose-500/30 bg-rose-500/[0.06] text-rose-200'
              : brandFit.tone === 'warn'
                ? 'border-amber-500/30 bg-amber-500/[0.06] text-amber-200'
                : 'border-emerald-500/30 bg-emerald-500/[0.06] text-emerald-200'
          }`}
        >
          <AlertTriangle
            className={`mt-0.5 h-3 w-3 shrink-0 ${
              brandFit.tone === 'danger'
                ? 'text-rose-400'
                : brandFit.tone === 'warn'
                  ? 'text-amber-400'
                  : 'text-emerald-400'
            }`}
          />
          <span>{brandFit.text}</span>
        </div>
      )}
    </div>
  );
}

export default SpotInfoCard;
