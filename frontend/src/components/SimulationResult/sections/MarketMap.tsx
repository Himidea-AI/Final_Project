import { useEffect, useRef, useState } from 'react';
import { useKakaoMap } from '../../kakao/useKakaoMap';

export interface Competitor {
  place_name: string;
  lat: number;
  lng: number;
  distance_m?: number;
  is_franchise?: boolean;
  brand_name?: string | null;
  daily_revenue?: number | null;
}

export interface RankingEntry {
  district: string;
  score: number;
  closure_rate?: number | null;
}

export interface SameBrandLocation {
  id: string;
  place_name: string;
  brand_name?: string;
  lat: number;
  lng: number;
  dong_name?: string;
  address?: string;
}

export interface MarketMapProps {
  center: { lat: number; lng: number };
  competitors?: Competitor[];
  rankings?: RankingEntry[];
  radius?: number;
  winnerDistrict?: string;
  height?: number | string;
  // 추천 동 내 "가장 적합한 공실" 좌표. 제공 시 폴리곤 centroid 대신 이 좌표에 핀/반경원을 찍는다.
  targetSpot?: { lat: number; lng: number } | null;
  // 추천 spot top1~4 — 1위는 펄싱 핀, 2~4위는 번호 라벨 핀으로 비교 표시.
  targetSpots?: { lat: number; lng: number }[];
  // winner+top3 4동 안 자사 매장 좌표 — 로고 아이콘 마커 표시.
  sameBrandLocations?: SameBrandLocation[];
  // 자사 영업구역 거리(m) — 자사 매장 각각에 점선 원으로 표시. null/미입력 시 원 안 그림.
  territoryRadiusM?: number | null;
}

interface KakaoLatLngInstance {
  getLat: () => number;
  getLng: () => number;
}

interface KakaoMapInstance {
  setCenter: (pos: KakaoLatLngInstance) => void;
  relayout: () => void;
}

interface KakaoMapsNamespace {
  Map: new (el: HTMLElement, opts: { center: unknown; level: number }) => KakaoMapInstance;
  LatLng: new (lat: number, lng: number) => KakaoLatLngInstance;
  Circle: new (opts: {
    center: unknown;
    radius: number;
    strokeWeight: number;
    strokeColor: string;
    strokeOpacity: number;
    strokeStyle: string;
    fillColor: string;
    fillOpacity: number;
  }) => { setMap: (m: unknown) => void };
  Polygon: new (opts: {
    path: unknown[];
    strokeWeight: number;
    strokeColor: string;
    strokeOpacity: number;
    fillColor: string;
    fillOpacity: number;
  }) => { setMap: (m: unknown) => void };
  Polyline: new (opts: {
    path: unknown[];
    strokeWeight: number;
    strokeColor: string;
    strokeOpacity: number;
    strokeStyle: string;
  }) => { setMap: (m: unknown) => void };
  CustomOverlay: new (opts: {
    position: unknown;
    content: HTMLElement | string;
    xAnchor?: number;
    yAnchor?: number;
    zIndex?: number;
  }) => { setMap: (m: unknown) => void };
  InfoWindow: new (opts: {
    position?: unknown;
    content: string | HTMLElement;
    removable?: boolean;
  }) => { open: (map: unknown) => void; close: () => void };
}

function getKakaoMaps(kakao: unknown): KakaoMapsNamespace | null {
  if (!kakao || typeof kakao !== 'object') return null;
  const maps = (kakao as { maps?: KakaoMapsNamespace }).maps;
  return maps ?? null;
}

interface GeoFeature {
  type: 'Feature';
  properties: { dong_name: string };
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] };
}

interface GeoCollection {
  type: 'FeatureCollection';
  features: GeoFeature[];
}

function rankingColor(score: number): string {
  if (score >= 75) return '#10b981';
  if (score >= 55) return '#f59e0b';
  return '#6b7280';
}

function rankingOpacity(score: number): number {
  return Math.max(0.08, Math.min(0.45, score / 220));
}

const PULSE_STYLE_ID = 'mm-pulse-style';
const PULSE_CSS = `
@keyframes mm-pulse {
  0%   { transform: scale(0.6); opacity: 0.9; }
  100% { transform: scale(2.4); opacity: 0; }
}
.mm-pulse-ring {
  position: absolute;
  inset: 0;
  border-radius: 9999px;
  background: rgba(255, 0, 112, 0.55); /* hot-pink — spot pin pulse (12색 팔레트) */
  animation: mm-pulse 2s ease-out infinite;
}
.mm-pulse-ring-delay { animation-delay: 1s; }
`;

function ensurePulseStyle() {
  if (document.getElementById(PULSE_STYLE_ID)) return;
  const el = document.createElement('style');
  el.id = PULSE_STYLE_ID;
  el.textContent = PULSE_CSS;
  document.head.appendChild(el);
}

function buildTargetOverlayContent(): HTMLElement {
  const wrap = document.createElement('div');
  // 1위 펄싱 핀 + "공실 #1 추천" 라벨 (핀 우측에 absolute 로 띄워 영역 확장 X — 주변 경쟁점 마커 가리지 않음).
  wrap.innerHTML = `
    <div style="position:relative;width:28px;height:28px;pointer-events:none;">
      <div class="mm-pulse-ring"></div>
      <div class="mm-pulse-ring mm-pulse-ring-delay"></div>
      <div style="position:absolute;inset:9px;border-radius:9999px;background:#ff0070;border:2px solid #ffffff;box-shadow:0 0 10px rgba(255,0,112,0.8);"></div>
      <div style="position:absolute;top:50%;left:32px;transform:translateY(-50%);padding:2px 6px;background:rgba(24,24,27,0.85);color:#ffffff;border:1px solid #ff0070;border-radius:4px;font-size:9px;font-weight:900;letter-spacing:0.05em;white-space:nowrap;">공실 #1 추천</div>
    </div>
  `;
  return wrap;
}

function formatDistance(m?: number): string {
  if (m == null) return '—';
  if (m < 1000) return `${Math.round(m)}m`;
  return `${(m / 1000).toFixed(2)}km`;
}

// 핀 좌표 기준 within/거리 재계산용. 백엔드 distance_m 은 source 동 centroid 기준이라
// 핀이 best_vacancy spot 으로 이동한 뒤엔 정합 안 됨 → 화면 좌표계로 재계산.
export function haversineM(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function formatKrwWan(v?: number | null): string {
  if (v == null) return '—';
  return `${Math.round(v / 10000).toLocaleString()}만원/일`;
}

function buildCompetitorInfoHtml(
  c: Competitor,
  radius: number,
  centerLat: number,
  centerLng: number,
): string {
  // 거리·within 모두 핀(centerLat/centerLng) 기준 재계산.
  // 백엔드 c.distance_m 은 source 동 centroid 기준이라 핀 위치와 정합 안 됨.
  const distM = haversineM(centerLat, centerLng, c.lat, c.lng);
  const within = distM <= radius;
  const accent = within ? '#f59e0b' : '#71717a';
  const brand = c.brand_name || c.place_name || '경쟁점';
  return `
    <div style="font-family:Pretendard,ui-sans-serif,system-ui;min-width:180px;padding:10px 12px;background:rgba(24,24,27,0.95);color:#e4e4e7;border:1px solid #3f3f46;border-radius:6px;backdrop-filter:blur(8px);">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
        <span style="display:inline-block;width:8px;height:8px;border-radius:9999px;background:${accent};"></span>
        <span style="font-size:13px;font-weight:600;">${brand}</span>
      </div>
      <div style="font-size:11px;color:#a1a1aa;line-height:1.6;">
        <div>거리: <span style="color:#f4f4f5;">${formatDistance(distM)}</span></div>
        <div>반경: <span style="color:${within ? '#fbbf24' : '#a1a1aa'};">${within ? '내부' : '외부'}</span></div>
        <div>일매출 추정: <span style="color:#f4f4f5;">${formatKrwWan(c.daily_revenue)}</span></div>
      </div>
    </div>
  `;
}

export function MarketMap({
  center,
  competitors = [],
  rankings = [],
  radius = 500,
  winnerDistrict,
  height = 520,
  targetSpot = null,
  targetSpots = [],
  sameBrandLocations = [],
  territoryRadiusM = null,
}: MarketMapProps) {
  const { ready, error, kakao } = useKakaoMap();
  const containerRef = useRef<HTMLDivElement>(null);
  const overlayLayersRef = useRef<Array<{ setMap: (m: unknown) => void }>>([]);
  const infoWindowRef = useRef<{ open: (m: unknown) => void; close: () => void } | null>(null);
  const [geoError, setGeoError] = useState<string | null>(null);

  useEffect(() => {
    ensurePulseStyle();
  }, []);

  useEffect(() => {
    if (!ready || !containerRef.current) return;
    const maps = getKakaoMaps(kakao);
    if (!maps) return;

    const mapInstance = new maps.Map(containerRef.current, {
      center: new maps.LatLng(center.lat, center.lng),
      level: 5,
    });

    overlayLayersRef.current.forEach((layer) => layer.setMap(null));
    overlayLayersRef.current = [];
    if (infoWindowRef.current) {
      infoWindowRef.current.close();
      infoWindowRef.current = null;
    }

    // 핀/반경원 좌표 우선순위:
    //   1) targetSpot (추천 동 내 best 공실 — listing_count 최대) — 가장 정확
    //   2) winner polygon geometric centroid (GeoJSON 기반) — 동 중심점 fallback
    //   3) center prop (DONG_COORDS 하드코딩) — 최후 안전장치
    const fallbackCenter = new maps.LatLng(center.lat, center.lng);
    const buildCenterLayers = (latLng: unknown) => {
      const circle = new maps.Circle({
        center: latLng,
        radius,
        strokeWeight: 2.5,
        strokeColor: '#ff0070', // hot-pink — 반경 가시성↑ (pin 과 같은 hue, dash 로 역할 구분)
        strokeOpacity: 0.9,
        strokeStyle: 'dash',
        fillColor: '#ff0070',
        fillOpacity: 0.1,
      });
      circle.setMap(mapInstance);
      overlayLayersRef.current.push(circle);

      const targetOverlay = new maps.CustomOverlay({
        position: latLng,
        content: buildTargetOverlayContent(),
        xAnchor: 0.5,
        yAnchor: 0.5,
        zIndex: 5,
      });
      targetOverlay.setMap(mapInstance);
      overlayLayersRef.current.push(targetOverlay);
    };

    // targetSpot 이 있으면 centroid 계산 결과로 핀을 덮어쓰지 않도록 플래그.
    // choropleth(폴리곤 색칠) 는 그대로 그리고, 핀/반경원만 targetSpot 으로 고정.
    const hasTargetSpot = targetSpot != null;

    // Layer — (bonus) 16동 choropleth + winner centroid 계산
    fetch('/mapo-dong.geo.json')
      .then((r) => {
        if (!r.ok) throw new Error(`GeoJSON fetch ${r.status}`);
        return r.json() as Promise<GeoCollection>;
      })
      .then((geo) => {
        if (!geo.features) {
          buildCenterLayers(
            hasTargetSpot ? new maps.LatLng(targetSpot!.lat, targetSpot!.lng) : fallbackCenter,
          );
          return;
        }
        const rankingMap = new Map(rankings.map((r) => [r.district, r]));
        let winnerCentroid: { lat: number; lng: number } | null = null;
        geo.features.forEach((f) => {
          const dong = f.properties.dong_name;
          const ranking = rankingMap.get(dong);
          const score = ranking?.score;
          const hasScore = typeof score === 'number';
          const isWinner = dong === winnerDistrict;
          // 실데이터 원칙: 랭킹 점수 없으면 빗금/투명 중립색 (기존 50 기본값 제거 — 점수 50 동과 구분)
          // winner = sunshine-yellow (추천 강조, Trophy 와 통일). 12색 팔레트.
          const fillColor = isWinner ? '#ffde00' : hasScore ? rankingColor(score) : '#27272a';
          const fillOpacity = isWinner ? 0.35 : hasScore ? rankingOpacity(score) : 0.08;
          const polygons: number[][][] =
            f.geometry.type === 'MultiPolygon'
              ? (f.geometry.coordinates as number[][][][]).flatMap((p) => p)
              : (f.geometry.coordinates as number[][][]);

          if (isWinner) {
            // winner polygon 의 모든 좌표 평균 = geometric centroid (단순 평균이라
            // 비대칭 모양에선 약간 어긋날 수 있지만 시각상 박스 내부에 항상 위치).
            const allCoords = polygons.flat();
            if (allCoords.length > 0) {
              const lngSum = allCoords.reduce((s, [lng]) => s + lng, 0);
              const latSum = allCoords.reduce((s, [, lat]) => s + lat, 0);
              winnerCentroid = {
                lat: latSum / allCoords.length,
                lng: lngSum / allCoords.length,
              };
            }
          }

          polygons.forEach((ring) => {
            const path = ring.map(([lng, lat]) => new maps.LatLng(lat, lng));
            const poly = new maps.Polygon({
              path,
              strokeWeight: isWinner ? 2 : 1,
              strokeColor: isWinner ? '#ffde00' : '#52525b',
              strokeOpacity: isWinner ? 0.9 : 0.55,
              fillColor,
              fillOpacity,
            });
            poly.setMap(mapInstance);
            overlayLayersRef.current.push(poly);
          });
        });

        const wc = winnerCentroid as { lat: number; lng: number } | null;
        const finalCenter = hasTargetSpot
          ? new maps.LatLng(targetSpot!.lat, targetSpot!.lng)
          : wc
            ? new maps.LatLng(wc.lat, wc.lng)
            : fallbackCenter;
        buildCenterLayers(finalCenter);
      })
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : 'GeoJSON 로드 실패';
        setGeoError(msg);
        buildCenterLayers(
          hasTargetSpot ? new maps.LatLng(targetSpot!.lat, targetSpot!.lng) : fallbackCenter,
        );
      });

    // Layer 2 — 경쟁점 마커 (빨간 삼각형, 반경 내/외 불투명도 구분 + 클릭 InfoWindow)
    // within 판정 좌표 = 화면 핀 위치. targetSpot 우선 → props center fallback.
    // winnerCentroid 는 GeoJSON fetch 비동기라 marker forEach 시점엔 미정 — props center 가 동 중심이라 근사값으로 충분.
    // 백엔드 c.distance_m 은 source 동 centroid 기준이라 핀과 정합 안 됨 → 무시하고 haversineM 으로 재계산.
    const withinCenterLat = targetSpot?.lat ?? center.lat;
    const withinCenterLng = targetSpot?.lng ?? center.lng;
    competitors.forEach((c) => {
      if (typeof c.lat !== 'number' || typeof c.lng !== 'number') return;
      const distFromCenter = haversineM(withinCenterLat, withinCenterLng, c.lat, c.lng);
      const within = distFromCenter <= radius;
      const dot = document.createElement('div');
      dot.style.cssText = within
        ? 'width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:11px solid #ef4444;filter:drop-shadow(0 0 3px rgba(239,68,68,0.7));cursor:pointer;'
        : 'width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:9px solid #ef4444;opacity:0.45;cursor:pointer;';
      dot.title = c.place_name;

      const pos = new maps.LatLng(c.lat, c.lng);
      dot.addEventListener('click', (ev) => {
        ev.stopPropagation();
        if (infoWindowRef.current) infoWindowRef.current.close();
        const iw = new maps.InfoWindow({
          position: pos,
          content: buildCompetitorInfoHtml(c, radius, withinCenterLat, withinCenterLng),
          removable: true,
        });
        iw.open(mapInstance);
        infoWindowRef.current = iw;
      });

      const overlay = new maps.CustomOverlay({
        position: pos,
        content: dot,
        xAnchor: 0.5,
        yAnchor: 0.5,
        zIndex: 2,
      });
      overlay.setMap(mapInstance);
      overlayLayersRef.current.push(overlay);
    });

    // Layer 3 — 자사 매장 마커 (로고 아이콘 별표 only — 영업구역 점선 원은 사용자 요구로 제거)
    sameBrandLocations.forEach((s) => {
      if (typeof s.lat !== 'number' || typeof s.lng !== 'number') return;
      const pos = new maps.LatLng(s.lat, s.lng);
      // 로고 아이콘 마커 — 금색 동그라미 + 작은 펄스 (자사 매장 표시).
      const logo = document.createElement('div');
      logo.style.cssText =
        'position:relative;width:24px;height:24px;display:flex;align-items:center;justify-content:center;background:#fbbf24;border:2px solid #ffffff;border-radius:9999px;box-shadow:0 0 8px rgba(251,191,36,0.6);font-size:12px;font-weight:900;color:#1c1917;cursor:pointer;';
      logo.innerHTML = '★';
      logo.title = `${s.brand_name || '자사매장'} · ${s.place_name}`;
      logo.addEventListener('click', (ev) => {
        ev.stopPropagation();
        if (infoWindowRef.current) infoWindowRef.current.close();
        const iw = new maps.InfoWindow({
          position: pos,
          content: `<div style="font-family:Pretendard,ui-sans-serif,system-ui;min-width:180px;padding:10px 12px;background:rgba(24,24,27,0.95);color:#e4e4e7;border:1px solid #fbbf24;border-radius:6px;backdrop-filter:blur(8px);">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
              <span style="display:inline-block;width:8px;height:8px;border-radius:9999px;background:#fbbf24;"></span>
              <span style="font-size:13px;font-weight:600;">${s.brand_name || '자사매장'}</span>
            </div>
            <div style="font-size:11px;color:#a1a1aa;line-height:1.6;">
              <div>${s.place_name}</div>
              <div>${s.dong_name || ''} ${s.address || ''}</div>
            </div>
          </div>`,
          removable: true,
        });
        iw.open(mapInstance);
        infoWindowRef.current = iw;
      });
      const sameBrandOverlay = new maps.CustomOverlay({
        position: pos,
        content: logo,
        xAnchor: 0.5,
        yAnchor: 0.5,
        zIndex: 4,
      });
      sameBrandOverlay.setMap(mapInstance);
      overlayLayersRef.current.push(sameBrandOverlay);
    });

    // Layer 4 — 추천 spot 2~4위 번호 라벨 핀 + 1위와 동일한 핫핑크 반경 원.
    // 1위는 buildCenterLayers 가 그림 (펄싱 핀 + 반경원). 2~4위도 비교용으로 동일 반경원 표시.
    targetSpots.slice(1, 4).forEach((sp, idx) => {
      const rank = idx + 2; // 2위부터 시작
      const spotPos = new maps.LatLng(sp.lat, sp.lng);
      // 반경 원 — 1위와 동일 디자인(핫핑크 dashed). 4 후보 비교 시각화.
      const spotCircle = new maps.Circle({
        center: spotPos,
        radius,
        strokeWeight: 2,
        strokeColor: '#ff0070',
        strokeOpacity: 0.6,
        strokeStyle: 'shortdash',
        fillColor: '#ff0070',
        fillOpacity: 0.05,
      });
      spotCircle.setMap(mapInstance);
      overlayLayersRef.current.push(spotCircle);
      // 번호 핀 + "공실 #N" 라벨. 핀 우측에 absolute 라벨로 영역 확장 X — 주변 경쟁점 가리지 않음.
      const pin = document.createElement('div');
      pin.style.cssText = 'position:relative;width:22px;height:22px;cursor:default;';
      pin.innerHTML = `
        <div style="width:22px;height:22px;display:flex;align-items:center;justify-content:center;background:#ff0070;border:2px solid #ffffff;border-radius:9999px;box-shadow:0 0 6px rgba(255,0,112,0.6);font-size:11px;font-weight:900;color:#ffffff;">${rank}</div>
        <div style="position:absolute;top:50%;left:26px;transform:translateY(-50%);padding:2px 6px;background:rgba(24,24,27,0.85);color:#ffffff;border:1px solid #ff0070;border-radius:4px;font-size:9px;font-weight:900;letter-spacing:0.05em;white-space:nowrap;pointer-events:none;">공실 #${rank}</div>
      `;
      pin.title = `추천 공실 spot ${rank}순위`;
      const pinOverlay = new maps.CustomOverlay({
        position: spotPos,
        content: pin,
        xAnchor: 0.5,
        yAnchor: 0.5,
        zIndex: 5,
      });
      pinOverlay.setMap(mapInstance);
      overlayLayersRef.current.push(pinOverlay);
    });

    return () => {
      overlayLayersRef.current.forEach((layer) => layer.setMap(null));
      overlayLayersRef.current = [];
      if (infoWindowRef.current) {
        infoWindowRef.current.close();
        infoWindowRef.current = null;
      }
    };
  }, [
    ready,
    kakao,
    center.lat,
    center.lng,
    competitors,
    rankings,
    radius,
    winnerDistrict,
    targetSpot?.lat,
    targetSpot?.lng,
    targetSpots,
    sameBrandLocations,
    territoryRadiusM,
  ]);

  if (error) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-border bg-card p-8 text-center"
        style={{ height }}
      >
        <div>
          <div className="mb-2 text-sm font-semibold text-danger">지도를 불러올 수 없습니다</div>
          <div className="text-xs text-muted-foreground">{error.message}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative" style={{ height }}>
      <div ref={containerRef} className="h-full w-full rounded-lg bg-card" />
      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
          지도를 불러오는 중…
        </div>
      )}
      {geoError && (
        <div className="absolute right-4 top-4 rounded bg-card/80 px-2 py-1 text-[0.625rem] text-danger">
          GeoJSON: {geoError}
        </div>
      )}
    </div>
  );
}
