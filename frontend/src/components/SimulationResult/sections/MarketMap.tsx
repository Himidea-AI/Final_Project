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
  place_url?: string | null;
  phone?: string | null;
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
  place_url?: string | null;
  phone?: string | null;
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
  // 사용자 브랜드명 — competitors 중 brand_name 이 매칭되는 항목은 별표(자사) 마커로 분기 렌더.
  // sameBrandLocations 는 winner+top3 4동 안만 수집하므로, 그 외 동의 자사 매장이 competitors 로
  // 들어오는 경우를 커버한다. 정규화 비교(소문자/공백·괄호 제거)로 alias 차이 흡수.
  userBrand?: string | null;
  // 주요 경쟁점 top5 (사이드바 카드와 동일) — 좌표 매칭 시 큰 번호 라벨 + 노란색으로 강조 렌더.
  topCompetitors?: Array<{ place_name: string; lat: number; lng: number; rank: number }>;
}

// 브랜드명 정규화 — "메가엠지씨커피(MEGA MGC COFFEE)" vs "메가엠지씨커피" 같은 변형을 동일 취급.
// 영문 괄호 / 공백 / 흔한 비교용 노이즈 제거. 비교 양쪽에 동일하게 적용.
function normalizeBrand(s: string | null | undefined): string {
  if (!s) return '';
  return s
    .toLowerCase()
    .replace(/\([^)]*\)/g, '') // 괄호+내용 (예: "(MEGA MGC COFFEE)")
    .replace(/[\s\-_·.]/g, '') // 공백/하이픈/언더스코어/middle-dot
    .replace(/\d+$/, '') // 끝 숫자 (FTC 표기: "홍콩반점0410" → "홍콩반점")
    .trim();
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

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// 팝업 wrapper — innerHTML 로 채우고 X 버튼 클릭 시 onClose 호출.
// CustomOverlay 자체엔 close UI 가 없어 직접 추가해야 함. zIndex 는 CustomOverlay 옵션으로 강제.
function buildPopupOverlayContent(innerHtml: string, onClose: () => void): HTMLElement {
  const wrap = document.createElement('div');
  wrap.style.cssText = 'position:relative;transform:translateY(-10px);pointer-events:auto;';
  wrap.innerHTML = `
    <div style="position:relative;">
      ${innerHtml}
      <button type="button" data-popup-close="1" aria-label="닫기"
        style="position:absolute;top:6px;right:6px;width:18px;height:18px;display:flex;align-items:center;justify-content:center;background:rgba(63,63,70,0.9);color:#e4e4e7;border:none;border-radius:9999px;font-size:11px;font-weight:900;cursor:pointer;line-height:1;padding:0;">×</button>
      <div style="position:absolute;left:50%;bottom:-7px;transform:translateX(-50%);width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-top:7px solid rgba(24,24,27,0.95);"></div>
    </div>
  `;
  const btn = wrap.querySelector<HTMLButtonElement>('button[data-popup-close="1"]');
  if (btn) btn.addEventListener('click', onClose);
  return wrap;
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
  // 매장명 표시 — place_url 있으면 카카오맵 새 창 link, 없으면 plain text.
  const nameHtml = c.place_url
    ? `<a href="${escapeHtml(c.place_url)}" target="_blank" rel="noopener noreferrer" style="font-size:13px;font-weight:600;color:#60a5fa;text-decoration:underline;">${escapeHtml(brand)}</a>`
    : `<span style="font-size:13px;font-weight:600;">${escapeHtml(brand)}</span>`;
  // 매장 상세 라인 — 본 매장 place_name (브랜드와 다를 때) + 전화번호.
  const placeNameLine =
    c.place_name && c.place_name !== brand
      ? `<div>매장: <span style="color:#f4f4f5;">${escapeHtml(c.place_name)}</span></div>`
      : '';
  const phoneLine = c.phone
    ? `<div>전화: <a href="tel:${escapeHtml(c.phone)}" style="color:#60a5fa;text-decoration:none;">${escapeHtml(c.phone)}</a></div>`
    : '';
  return `
    <div style="font-family:Pretendard,ui-sans-serif,system-ui;min-width:180px;padding:10px 12px;background:rgba(24,24,27,0.95);color:#e4e4e7;border:1px solid #3f3f46;border-radius:6px;backdrop-filter:blur(8px);">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
        <span style="display:inline-block;width:8px;height:8px;border-radius:9999px;background:${accent};"></span>
        ${nameHtml}
      </div>
      <div style="font-size:11px;color:#a1a1aa;line-height:1.6;">
        ${placeNameLine}
        <div>거리: <span style="color:#f4f4f5;">${formatDistance(distM)}</span></div>
        <div>반경: <span style="color:${within ? '#fbbf24' : '#a1a1aa'};">${within ? '내부' : '외부'}</span></div>
        <div>일매출 추정: <span style="color:#f4f4f5;">${formatKrwWan(c.daily_revenue)}</span></div>
        ${phoneLine}
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
  userBrand = null,
  topCompetitors = [],
}: MarketMapProps) {
  const { ready, error, kakao } = useKakaoMap();
  const containerRef = useRef<HTMLDivElement>(null);
  const overlayLayersRef = useRef<Array<{ setMap: (m: unknown) => void }>>([]);
  // 팝업 — 기존 Kakao InfoWindow 는 다른 CustomOverlay(펄싱 핀/번호 핀) 에 가려지는 이슈가 있어
  // CustomOverlay (zIndex 100) 로 통일. close 는 X 버튼 클릭 또는 다른 마커 클릭 시.
  const popupRef = useRef<{ setMap: (m: unknown) => void } | null>(null);
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
    if (popupRef.current) {
      popupRef.current.setMap(null);
      popupRef.current = null;
    }

    // 핀/반경원 좌표 우선순위:
    //   1) targetSpot (추천 동 내 best 공실 — listing_count 최대) — 가장 정확
    //   2) winner polygon geometric centroid (GeoJSON 기반) — 동 중심점 fallback
    //   3) center prop (DONG_COORDS 하드코딩) — 최후 안전장치
    const fallbackCenter = new maps.LatLng(center.lat, center.lng);
    const buildCenterLayers = (latLng: unknown) => {
      // 1위 반경원 — fill 살짝 (0.05) 으로 영역 인지 + 마커 시각성 둘 다 보존.
      const circle = new maps.Circle({
        center: latLng,
        radius,
        strokeWeight: 2.5,
        strokeColor: '#ff0070',
        strokeOpacity: 0.9,
        strokeStyle: 'dash',
        fillColor: '#ff0070',
        fillOpacity: 0.05,
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
        let winnerCentroid: { lat: number; lng: number } | null = null;
        geo.features.forEach((f) => {
          const dong = f.properties.dong_name;
          const isWinner = dong === winnerDistrict;
          // 사용자 요청: winner(1위) 만 색칠. 다른 동은 점수 있어도 중립 회색 처리.
          const fillColor = isWinner ? '#ffde00' : '#27272a';
          const fillOpacity = isWinner ? 0.35 : 0.08;
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
    // within 판정 = 4 spot 중 어느 하나라도 radius 안이면 내부 (사용자 요청).
    // targetSpots 비어있으면 단일 spot1 좌표만 사용 (구버전 호환).
    const allSpots: { lat: number; lng: number }[] =
      targetSpots && targetSpots.length > 0
        ? targetSpots
        : [{ lat: withinCenterLat, lng: withinCenterLng }];
    const normalizedUserBrand = normalizeBrand(userBrand);
    // sameBrandLocations 와 중복으로 그려지는 자사 매장 좌표 제거용 set (key=lat,lng 4자리).
    const sameBrandPosKeys = new Set(
      sameBrandLocations.map((s) => `${s.lat.toFixed(5)},${s.lng.toFixed(5)}`),
    );
    // 주요 경쟁점 top5 매칭용 — 좌표(소수4자리) 기준 rank lookup.
    const topCompetitorRankByPos = new Map<string, number>();
    topCompetitors.forEach((tc) => {
      if (typeof tc.lat !== 'number' || typeof tc.lng !== 'number') return;
      topCompetitorRankByPos.set(`${tc.lat.toFixed(4)},${tc.lng.toFixed(4)}`, tc.rank);
    });

    // 팝업 열기/닫기 헬퍼 — InfoWindow 대체. zIndex=100 강제로 항상 최상단.
    const openPopup = (pos: unknown, innerHtml: string) => {
      if (popupRef.current) popupRef.current.setMap(null);
      const closeFn = () => {
        if (popupRef.current) {
          popupRef.current.setMap(null);
          popupRef.current = null;
        }
      };
      const content = buildPopupOverlayContent(innerHtml, closeFn);
      const overlay = new maps.CustomOverlay({
        position: pos,
        content,
        xAnchor: 0.5,
        yAnchor: 1.0,
        zIndex: 100,
      });
      overlay.setMap(mapInstance);
      popupRef.current = overlay;
    };

    competitors.forEach((c) => {
      if (typeof c.lat !== 'number' || typeof c.lng !== 'number') return;
      // 자사 브랜드 매칭 — competitors 안에 자사 매장이 들어와 있으면 별표 마커로 분기.
      // sameBrandLocations 와 좌표 중복 시 skip (이미 Layer 3 에서 그려짐).
      const isSelfBrand =
        normalizedUserBrand.length > 0 && normalizeBrand(c.brand_name) === normalizedUserBrand;
      const posKey = `${c.lat.toFixed(5)},${c.lng.toFixed(5)}`;
      if (isSelfBrand && sameBrandPosKeys.has(posKey)) return;

      // 4 spot 중 최단거리 — 하나라도 radius 안이면 within.
      const minDistFromAnySpot = Math.min(
        ...allSpots.map((sp) => haversineM(sp.lat, sp.lng, c.lat, c.lng)),
      );
      const within = minDistFromAnySpot <= radius;
      const pos = new maps.LatLng(c.lat, c.lng);
      // 주요 경쟁점 top5 매칭 — 사이드바 카드와 동일 좌표면 큰 번호 라벨로 강조.
      const top5Rank = topCompetitorRankByPos.get(`${c.lat.toFixed(4)},${c.lng.toFixed(4)}`);
      const isTop5 = top5Rank != null && top5Rank >= 1 && top5Rank <= 5;

      const dot = document.createElement('div');
      if (isSelfBrand) {
        // 자사 매장 별표 — Layer 3 sameBrand 마커와 동일 디자인.
        dot.style.cssText =
          'position:relative;width:24px;height:24px;display:flex;align-items:center;justify-content:center;background:#fbbf24;border:2px solid #ffffff;border-radius:9999px;box-shadow:0 0 8px rgba(251,191,36,0.6);font-size:12px;font-weight:900;color:#1c1917;cursor:pointer;';
        dot.innerHTML = '★';
        dot.title = `${c.brand_name || '자사매장'} · ${c.place_name}`;
      } else {
        // 빨간 삼각형 — 반경 안 진한, 밖 흐린. top5 여부와 무관하게 항상 그려짐
        // (top5 는 이 위에 별도 번호 동그라미 overlay 로 추가 표시 — 매장 누락 X).
        dot.style.cssText = within
          ? 'width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:11px solid #ef4444;filter:drop-shadow(0 0 3px rgba(239,68,68,0.7));cursor:pointer;'
          : 'width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:9px solid #ef4444;opacity:0.45;cursor:pointer;';
        dot.title = isTop5 ? `주요 경쟁점 ${top5Rank}위 — ${c.place_name}` : c.place_name;
      }

      dot.addEventListener('click', (ev) => {
        ev.stopPropagation();
        openPopup(pos, buildCompetitorInfoHtml(c, radius, withinCenterLat, withinCenterLng));
      });

      const overlay = new maps.CustomOverlay({
        position: pos,
        content: dot,
        xAnchor: 0.5,
        yAnchor: 0.5,
        zIndex: isSelfBrand ? 4 : 2,
      });
      overlay.setMap(mapInstance);
      overlayLayersRef.current.push(overlay);

      // top5 별도 번호 라벨 — 빨간 삼각형 위에 약간 떠있게 표시 (매장은 빨간 삼각형으로 그대로).
      // 노란 뱃지 자체도 클릭 가능 — 같은 경쟁점 정보 popup 열림.
      // 회귀 fix(2026-05-06): 이전 'pointer-events:none' 으로 클릭 차단되던 문제 제거.
      if (isTop5 && !isSelfBrand) {
        const badge = document.createElement('div');
        badge.style.cssText =
          'position:relative;width:20px;height:20px;display:flex;align-items:center;justify-content:center;background:#facc15;border:2px solid #ffffff;border-radius:9999px;box-shadow:0 0 8px rgba(250,204,21,0.8);font-size:11px;font-weight:900;color:#1c1917;cursor:pointer;';
        badge.innerHTML = String(top5Rank);
        badge.title = `주요 경쟁점 ${top5Rank}위 — ${c.place_name}`;
        badge.addEventListener('click', (ev) => {
          ev.stopPropagation();
          openPopup(pos, buildCompetitorInfoHtml(c, radius, withinCenterLat, withinCenterLng));
        });
        const badgeOverlay = new maps.CustomOverlay({
          position: pos,
          content: badge,
          xAnchor: 0.5,
          yAnchor: 1.6, // 빨간 삼각형 위쪽으로 띄움 — 삼각형이 그대로 보임
          zIndex: 6,
        });
        badgeOverlay.setMap(mapInstance);
        overlayLayersRef.current.push(badgeOverlay);
      }
    });

    // Layer 3 — 자사 매장 마커 (로고 아이콘 별표 only — 영업구역 점선 원은 사용자 요구로 제거)
    // DEBUG: 별표 안 뜨는 이슈 추적 — sameBrandLocations props 검사
    console.log(
      '[MarketMap Layer 3] sameBrandLocations:',
      sameBrandLocations.length,
      'items',
      sameBrandLocations,
    );
    sameBrandLocations.forEach((s) => {
      if (typeof s.lat !== 'number' || typeof s.lng !== 'number') {
        console.warn('[MarketMap Layer 3] skip — bad lat/lng:', s);
        return;
      }
      const pos = new maps.LatLng(s.lat, s.lng);
      // 로고 아이콘 마커 — 금색 동그라미 + 작은 펄스 (자사 매장 표시).
      const logo = document.createElement('div');
      // DEBUG: 별표 안 보이는 이슈 — 디자인 강화 (크기↑ + 강한 그림자 + 외곽선 추가).
      logo.style.cssText =
        'position:relative;width:36px;height:36px;display:flex;align-items:center;justify-content:center;background:#fbbf24;border:3px solid #ffffff;border-radius:9999px;box-shadow:0 0 16px rgba(251,191,36,0.95),0 0 4px rgba(0,0,0,0.5);font-size:18px;font-weight:900;color:#1c1917;cursor:pointer;outline:2px solid #f59e0b;outline-offset:1px;';
      logo.innerHTML = '★';
      logo.title = `${s.brand_name || '자사매장'} · ${s.place_name}`;
      logo.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const brandName = s.brand_name || '자사매장';
        // place_url 있으면 매장명을 카카오맵 link 로. 없으면 plain text.
        const nameHtml = s.place_url
          ? `<a href="${escapeHtml(s.place_url)}" target="_blank" rel="noopener noreferrer" style="font-size:13px;font-weight:600;color:#fbbf24;text-decoration:underline;">${escapeHtml(brandName)}</a>`
          : `<span style="font-size:13px;font-weight:600;">${escapeHtml(brandName)}</span>`;
        const placeNameHtml = s.place_url
          ? `<a href="${escapeHtml(s.place_url)}" target="_blank" rel="noopener noreferrer" style="color:#60a5fa;text-decoration:underline;">${escapeHtml(s.place_name)}</a>`
          : escapeHtml(s.place_name);
        const phoneHtml = s.phone
          ? `<div>전화: <a href="tel:${escapeHtml(s.phone)}" style="color:#60a5fa;text-decoration:none;">${escapeHtml(s.phone)}</a></div>`
          : '';
        const innerHtml = `<div style="font-family:Pretendard,ui-sans-serif,system-ui;min-width:180px;padding:10px 12px;background:rgba(24,24,27,0.95);color:#e4e4e7;border:1px solid #fbbf24;border-radius:6px;backdrop-filter:blur(8px);">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
            <span style="display:inline-block;width:8px;height:8px;border-radius:9999px;background:#fbbf24;"></span>
            ${nameHtml}
          </div>
          <div style="font-size:11px;color:#a1a1aa;line-height:1.6;">
            <div>${placeNameHtml}</div>
            <div>${escapeHtml(s.dong_name || '')} ${escapeHtml(s.address || '')}</div>
            ${phoneHtml}
          </div>
        </div>`;
        openPopup(pos, innerHtml);
      });
      const sameBrandOverlay = new maps.CustomOverlay({
        position: pos,
        content: logo,
        xAnchor: 0.5,
        yAnchor: 0.5,
        zIndex: 100, // DEBUG: 가시성 강화 (4 → 100)
      });
      sameBrandOverlay.setMap(mapInstance);
      overlayLayersRef.current.push(sameBrandOverlay);
      // eslint-disable-next-line no-console
      console.log(
        '[MarketMap Layer 3] ★ overlay placed:',
        s.place_name,
        'lat=',
        s.lat,
        'lng=',
        s.lng,
      );
    });

    // Layer 4 — 추천 spot 2~4위 번호 라벨 핀 + 1위와 동일한 핫핑크 반경 원.
    // 1위는 buildCenterLayers 가 그림 (펄싱 핀 + 반경원). 2~4위도 비교용으로 동일 반경원 표시.
    targetSpots.slice(1, 4).forEach((sp, idx) => {
      const rank = idx + 2; // 2위부터 시작
      const spotPos = new maps.LatLng(sp.lat, sp.lng);
      // 반경 원 — 1위와 동일 디자인(핫핑크 dashed). fill 제거 (마커 시각성 보존).
      const spotCircle = new maps.Circle({
        center: spotPos,
        radius,
        strokeWeight: 2,
        strokeColor: '#ff0070',
        strokeOpacity: 0.6,
        strokeStyle: 'shortdash',
        fillColor: '#ff0070',
        fillOpacity: 0,
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
      if (popupRef.current) {
        popupRef.current.setMap(null);
        popupRef.current = null;
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
    userBrand,
    topCompetitors,
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
