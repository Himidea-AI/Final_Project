import { useEffect, useRef, useState, useCallback } from 'react';
import { MapPin } from 'lucide-react';

declare global {
  interface Window {
    // 카카오맵 SDK 런타임 객체. 공식 타입 패키지를 쓰지 않아 unknown으로 선언.
    kakao: unknown;
  }
}

export interface LocationData {
  id: string | number;
  name: string;
  lat: number;
  lng: number;
  type?: 'candidate' | 'vacancy' | 'recommended';
  listingCount?: number;
  /** 신규 추천 에이전트 출력 — score/reason 있으면 마커 강조 + tooltip. */
  score?: number;
  reason?: string;
}

export interface CompetitorPin {
  id: string | number;
  name: string;
  lat: number;
  lng: number;
  distance_m?: number;
  is_franchise?: boolean;
  category?: string;
}

export interface AgentMapVisualizerProps {
  locations?: LocationData[];
  competitors?: CompetitorPin[];
  height?: string | number;
  onSpotClick?: (loc: LocationData) => void;
}

interface PixelCoord {
  x: number;
  y: number;
}

const DEFAULT_LOCATIONS: LocationData[] = [
  { id: 1, name: '연남파크 A급', lat: 37.562, lng: 126.923 },
  { id: 2, name: '동진시장 B급', lat: 37.5645, lng: 126.9255 },
  { id: 3, name: '망원역 C급', lat: 37.5565, lng: 126.9065 },
  { id: 4, name: '홍대메인 S급', lat: 37.5575, lng: 126.9245 },
  { id: 5, name: '합정카페거리', lat: 37.5495, lng: 126.9185 },
];

export default function AgentMapVisualizer({
  locations = DEFAULT_LOCATIONS,
  competitors = [],
  height = '600px',
  onSpotClick,
}: AgentMapVisualizerProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapInstanceRef = useRef<any>(null);

  const [mapLoaded, setMapLoaded] = useState(false);
  const [targetPixels, setTargetPixels] = useState<Record<string | number, PixelCoord>>({});
  const [competitorPixels, setCompetitorPixels] = useState<Record<string | number, PixelCoord>>({});
  // 사용자 피드백 (2026-05-04): 라벨 항상 표시는 산만. 클릭 시만 popup 표시.
  // popup 안에 가게명 + 가장 가까운 공실 spot 까지 거리 (m) + 비교 반경 원 표시.
  const [selectedCompetitorId, setSelectedCompetitorId] = useState<string | number | null>(null);
  // 비교 반경 (m) — 사용자 조절. 클릭한 경쟁업체의 가장 가까운 공실 spot 주변에 원 그림.
  const [comparisonRadius, setComparisonRadius] = useState<number>(500);
  // Kakao Circle 인스턴스 ref — selected 변경 시 destroy + 재생성.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const radiusCircleRef = useRef<any>(null);

  const KAKAO_MAP_API_KEY: string = import.meta.env?.VITE_KAKAO_MAP_API_KEY || '';
  const IS_MOCK_MODE = !KAKAO_MAP_API_KEY || KAKAO_MAP_API_KEY.includes('YOUR');

  const updateCoordinates = useCallback(() => {
    if (!mapContainerRef.current) return;
    const containerRect = mapContainerRef.current.getBoundingClientRect();
    const newTargetPixels: Record<string | number, PixelCoord> = {};
    const newCompetitorPixels: Record<string | number, PixelCoord> = {};

    if (IS_MOCK_MODE) {
      const w = containerRect.width;
      const h = containerRect.height;
      const mockPositions: PixelCoord[] = [
        { x: w * 0.4, y: h * 0.35 },
        { x: w * 0.7, y: h * 0.25 },
        { x: w * 0.2, y: h * 0.5 },
        { x: w * 0.55, y: h * 0.45 },
        { x: w * 0.8, y: h * 0.55 },
      ];
      locations.forEach((loc, idx) => {
        newTargetPixels[loc.id] = mockPositions[idx % mockPositions.length];
      });
      // mock 경쟁업체: candidate 핀들 주변에 분산 배치
      const compMockBase = [
        { x: w * 0.32, y: h * 0.28 },
        { x: w * 0.62, y: h * 0.42 },
        { x: w * 0.48, y: h * 0.58 },
        { x: w * 0.75, y: h * 0.38 },
        { x: w * 0.25, y: h * 0.65 },
        { x: w * 0.58, y: h * 0.22 },
        { x: w * 0.35, y: h * 0.72 },
      ];
      competitors.forEach((comp, idx) => {
        const base = compMockBase[idx % compMockBase.length];
        newCompetitorPixels[comp.id] = {
          x: base.x + (idx > compMockBase.length ? 15 : 0),
          y: base.y + (idx > compMockBase.length ? 10 : 0),
        };
      });
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const map = mapInstanceRef.current as any;
      if (!map) return;
      const proj = map.getProjection();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const kakao = (window as any).kakao;
      locations.forEach((loc) => {
        const position = new kakao.maps.LatLng(loc.lat, loc.lng);
        const pixel = proj.containerPointFromCoords(position);
        newTargetPixels[loc.id] = { x: pixel.x, y: pixel.y };
      });
      competitors.forEach((comp) => {
        const position = new kakao.maps.LatLng(comp.lat, comp.lng);
        const pixel = proj.containerPointFromCoords(position);
        newCompetitorPixels[comp.id] = { x: pixel.x, y: pixel.y };
      });
    }
    setTargetPixels(newTargetPixels);
    setCompetitorPixels(newCompetitorPixels);
  }, [IS_MOCK_MODE, locations, competitors]);

  useEffect(() => {
    let cleanupFn = () => {};
    const handleResize = () => updateCoordinates();

    if (IS_MOCK_MODE) {
      setMapLoaded(true);
      const timer = setTimeout(() => {
        updateCoordinates();
      }, 500);
      window.addEventListener('resize', handleResize);
      cleanupFn = () => {
        clearTimeout(timer);
        window.removeEventListener('resize', handleResize);
      };
    } else {
      const initRealMap = () => {
        if (!mapContainerRef.current) return;
        const centerLat =
          locations.length > 0
            ? locations.reduce((sum, l) => sum + l.lat, 0) / locations.length
            : 37.558;
        const centerLng =
          locations.length > 0
            ? locations.reduce((sum, l) => sum + l.lng, 0) / locations.length
            : 126.919;

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const kakao = (window as any).kakao;
        const centerPosition = new kakao.maps.LatLng(centerLat, centerLng);
        const map = new kakao.maps.Map(mapContainerRef.current, {
          center: centerPosition,
          level: 5,
          disableDoubleClickZoom: true,
        });
        mapInstanceRef.current = map;
        setMapLoaded(true);

        kakao.maps.event.addListener(map, 'idle', updateCoordinates);
        kakao.maps.event.addListener(map, 'zoom_changed', updateCoordinates);
        window.addEventListener('resize', handleResize);

        const timer = setTimeout(() => {
          updateCoordinates();
        }, 500);

        cleanupFn = () => {
          clearTimeout(timer);
          window.removeEventListener('resize', handleResize);
        };
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const kakao = (window as any).kakao;
      if (kakao && kakao.maps) {
        initRealMap();
      } else {
        const script = document.createElement('script');
        script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_MAP_API_KEY}&autoload=false`;
        document.head.appendChild(script);
        script.onload = () =>
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (window as any).kakao.maps.load(initRealMap);

        cleanupFn = () => {
          if (document.head.contains(script)) document.head.removeChild(script);
          window.removeEventListener('resize', handleResize);
        };
      }
    }

    return () => cleanupFn();
  }, [IS_MOCK_MODE, KAKAO_MAP_API_KEY, locations, updateCoordinates]);

  // 선택된 경쟁업체의 가장 가까운 공실 spot 주변 비교 반경 원.
  useEffect(() => {
    // 기존 원 제거.
    if (radiusCircleRef.current) {
      try {
        radiusCircleRef.current.setMap(null);
      } catch {
        /* noop */
      }
      radiusCircleRef.current = null;
    }
    if (IS_MOCK_MODE) return;
    if (selectedCompetitorId === null) return;
    if (!mapInstanceRef.current) return;
    const comp = competitors.find((c) => c.id === selectedCompetitorId);
    if (!comp || !locations || locations.length === 0) return;

    // 가장 가까운 spot 찾기.
    const toRad = (d: number) => (d * Math.PI) / 180;
    const R = 6371000;
    let nearest: LocationData | null = null;
    let nearestDist = Infinity;
    for (const loc of locations) {
      const dLat = toRad(loc.lat - comp.lat);
      const dLng = toRad(loc.lng - comp.lng);
      const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos(toRad(comp.lat)) * Math.cos(toRad(loc.lat)) * Math.sin(dLng / 2) ** 2;
      const d = 2 * R * Math.asin(Math.sqrt(a));
      if (d < nearestDist) {
        nearestDist = d;
        nearest = loc;
      }
    }
    if (!nearest) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const kakao = (window as any).kakao;
    if (!kakao?.maps?.Circle || !kakao?.maps?.LatLng) return;
    const center = new kakao.maps.LatLng(nearest.lat, nearest.lng);
    const circle = new kakao.maps.Circle({
      center,
      radius: comparisonRadius,
      strokeWeight: 2,
      strokeColor: '#002CD1',
      strokeOpacity: 0.6,
      strokeStyle: 'dashed',
      fillColor: '#002CD1',
      fillOpacity: 0.08,
    });
    circle.setMap(mapInstanceRef.current);
    radiusCircleRef.current = circle;
    return () => {
      try {
        circle.setMap(null);
      } catch {
        /* noop */
      }
    };
  }, [selectedCompetitorId, comparisonRadius, competitors, locations, IS_MOCK_MODE]);

  return (
    <div
      className="w-full bg-card rounded-2xl border border-border overflow-hidden relative shadow-2xl flex flex-col"
      style={{ height }}
    >
      <div ref={mapContainerRef} className="absolute inset-0 z-0">
        {!IS_MOCK_MODE && (
          <div
            className="w-full h-full"
            style={{
              filter:
                'invert(100%) hue-rotate(180deg) brightness(85%) contrast(110%) grayscale(30%)',
            }}
          />
        )}
      </div>

      {IS_MOCK_MODE && (
        <div className="absolute inset-0 z-0 bg-background overflow-hidden pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                'linear-gradient(rgba(0, 44, 209, 0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 44, 209, 0.15) 1px, transparent 1px)',
              backgroundSize: '50px 50px',
              transform: 'perspective(500px) rotateX(60deg) scale(2) translateY(-100px)',
              transformOrigin: 'top center',
            }}
          />
          <div className="absolute top-[40%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] border border-primary/20 rounded-full animate-[spin_10s_linear_infinite]" />
          <div className="absolute top-[40%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[450px] h-[450px] border border-primary/10 rounded-full animate-[spin_15s_linear_infinite_reverse]" />
          <div className="absolute top-4 left-4 font-mono text-[0.625rem] text-primary opacity-50 tracking-widest">
            MOCK RADAR MODE ACTIVE // NO API KEY DETECTED
          </div>
        </div>
      )}

      {/* 출점 후보지 핀 (candidate) + 공실 스팟 번호 마커 (vacancy — 클릭 가능) */}
      {mapLoaded &&
        locations.map((loc, idx) => {
          const pixel = targetPixels[loc.id];
          if (!pixel) return null;
          const isVacancy = loc.type === 'vacancy';

          if (isVacancy) {
            // 번호 달린 시안 원형 마커 — 클릭 시 onSpotClick 콜백
            const vacancyNumber = locations
              .slice(0, idx + 1)
              .filter((l) => l.type === 'vacancy').length;
            return (
              <button
                type="button"
                key={`pin-${loc.id}`}
                onClick={() => onSpotClick?.(loc)}
                disabled={!onSpotClick}
                title={`${loc.name}${loc.listingCount ? ` — 공실 ×${loc.listingCount}` : ''} 클릭해서 ABM 시뮬`}
                className="absolute z-30 flex items-center justify-center w-8 h-8 rounded-full bg-decor-cyan border-2 border-decor-cyan text-foreground text-xs font-black shadow-[0_0_14px_rgba(0,224,209,0.8)] transition-transform duration-200 pointer-events-auto cursor-pointer hover:scale-125 hover:bg-decor-cyan disabled:cursor-default disabled:opacity-60"
                style={{
                  left: pixel.x,
                  top: pixel.y,
                  transform: 'translate(-50%, -50%)',
                }}
              >
                {vacancyNumber}
                <span className="absolute inline-flex h-full w-full rounded-full bg-decor-cyan opacity-40 animate-ping" />
              </button>
            );
          }

          // candidate 기존 핀
          const pinColor = 'var(--primary)';
          return (
            <div
              key={`pin-${loc.id}`}
              className="absolute z-20 flex flex-col items-center pointer-events-none transition-all duration-300"
              style={{
                left: pixel.x,
                top: pixel.y,
                transform: 'translate(-50%, -100%)',
              }}
            >
              <div className="bg-card border text-foreground px-2 py-0.5 rounded text-[0.5625rem] font-bold mb-1 border-primary shadow-[0_0_10px_rgba(0,44,209,0.5)]">
                {loc.name}
              </div>
              <MapPin className="w-6 h-6" style={{ color: pinColor, fill: `${pinColor}33` }} />
              <div className="w-2 h-2 rounded-full animate-ping absolute bottom-1 bg-primary" />
            </div>
          );
        })}

      {/* 경쟁업체 핀 — 라벨 hidden, 클릭 시 popup. */}
      {mapLoaded &&
        competitors.map((comp) => {
          const pixel = competitorPixels[comp.id];
          if (!pixel) return null;
          const isFranchise = comp.is_franchise;
          // 사용자 피드백 (2026-05-05): 자사 브랜드만 red, 경쟁업체 (프랜차이즈/개인점) 모두 yellow.
          // own_brand category 는 AbmTab 의 sameBrandLocations 에서 부여.
          const isOwnBrand = comp.category === 'own_brand';
          const pinColor = isOwnBrand ? '#fb565b' : '#ffba00';
          const isSelected = selectedCompetitorId === comp.id;

          // 가장 가까운 공실 spot 까지 거리 (Haversine, m)
          let nearestDist: number | null = null;
          let nearestName: string | null = null;
          if (locations && locations.length > 0) {
            const toRad = (d: number) => (d * Math.PI) / 180;
            const R = 6371000; // m
            for (const loc of locations) {
              const dLat = toRad(loc.lat - comp.lat);
              const dLng = toRad(loc.lng - comp.lng);
              const a =
                Math.sin(dLat / 2) ** 2 +
                Math.cos(toRad(comp.lat)) * Math.cos(toRad(loc.lat)) * Math.sin(dLng / 2) ** 2;
              const d = 2 * R * Math.asin(Math.sqrt(a));
              if (nearestDist === null || d < nearestDist) {
                nearestDist = d;
                nearestName = loc.name;
              }
            }
          }

          return (
            <div
              key={`comp-${comp.id}`}
              className={`absolute flex flex-col items-center ${isSelected ? 'z-[60]' : 'z-20'}`}
              style={{
                left: pixel.x,
                top: pixel.y,
                transform: 'translate(-50%, -100%)',
              }}
            >
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedCompetitorId((cur) => (cur === comp.id ? null : comp.id));
                }}
                className="cursor-pointer hover:scale-125 transition-transform"
                aria-label={`${comp.name} 정보`}
              >
                <svg width="18" height="18" viewBox="0 0 18 18">
                  <polygon
                    points="9,2 16,16 2,16"
                    fill={`${pinColor}33`}
                    stroke={pinColor}
                    strokeWidth="1.5"
                  />
                </svg>
              </button>
              {isSelected && (
                <div
                  className="absolute bottom-full mb-1 z-[60] min-w-[160px] max-w-[240px] rounded-lg border bg-card p-2.5 shadow-xl"
                  style={{ borderColor: pinColor }}
                >
                  <div className="flex items-baseline justify-between gap-2 mb-1.5">
                    <span className="text-[11px] font-black truncate" style={{ color: pinColor }}>
                      {comp.name}
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedCompetitorId(null);
                      }}
                      className="text-[10px] text-muted-foreground hover:text-foreground shrink-0"
                      aria-label="닫기"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="text-[9.5px] text-muted-foreground space-y-0.5">
                    <div>
                      <span className="font-mono">유형:</span>{' '}
                      {isFranchise ? '프랜차이즈' : '개인점'}
                    </div>
                    {comp.category && (
                      <div>
                        <span className="font-mono">업종:</span> {comp.category}
                      </div>
                    )}
                    {nearestDist !== null && (
                      <div>
                        <span className="font-mono">최근접 공실:</span>{' '}
                        <span className="font-bold text-foreground">
                          {Math.round(nearestDist)}m
                        </span>
                        {nearestName ? ` (${nearestName})` : ''}
                      </div>
                    )}
                    {comp.distance_m != null && (
                      <div>
                        <span className="font-mono">중심거리:</span> {Math.round(comp.distance_m)}m
                      </div>
                    )}
                  </div>

                  {/* 비교 반경 slider — 사용자 조절 (100~2000m). 그 spot 주변에 점선 원 그림. */}
                  <div className="mt-2 pt-2 border-t border-border/50">
                    <div className="flex items-center justify-between text-[9px] text-muted-foreground mb-1">
                      <span className="font-mono uppercase tracking-wider">비교 반경</span>
                      <span className="font-bold text-primary tabular-nums">
                        {comparisonRadius}m
                      </span>
                    </div>
                    <input
                      type="range"
                      min={100}
                      max={2000}
                      step={50}
                      value={comparisonRadius}
                      onChange={(e) => setComparisonRadius(Number(e.target.value))}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full h-1.5 accent-primary cursor-pointer"
                      aria-label="비교 반경 조절"
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}

      <svg className="absolute inset-0 w-full h-full z-30 pointer-events-none">
        <defs>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
      </svg>

      {/* 범례 */}
      <div className="absolute top-3 left-3 z-40 bg-background/80 backdrop-blur-sm border border-border rounded-lg p-2.5 flex flex-col gap-1.5">
        <p className="text-[0.5rem] font-mono text-muted-foreground uppercase tracking-wider mb-0.5">
          Legend
        </p>
        <div className="flex items-center gap-1.5">
          <MapPin className="w-3 h-3" style={{ color: 'var(--primary)' }} />
          <span className="text-[0.5625rem] text-muted-foreground">출점 후보지</span>
        </div>
        <div className="flex items-center gap-1.5">
          <MapPin className="w-3 h-3" style={{ color: 'var(--decor-cyan)' }} />
          <span className="text-[0.5625rem] text-muted-foreground">공실 매물</span>
        </div>
        {competitors.length > 0 && (
          <>
            <div className="flex items-center gap-1.5">
              <svg width="10" height="10" viewBox="0 0 18 18">
                <polygon
                  points="9,2 16,16 2,16"
                  fill="#fb565b33"
                  stroke="#fb565b"
                  strokeWidth="2"
                />
              </svg>
              <span className="text-[0.5625rem] text-muted-foreground">자사 매장</span>
            </div>
            <div className="flex items-center gap-1.5">
              <svg width="10" height="10" viewBox="0 0 18 18">
                <polygon
                  points="9,2 16,16 2,16"
                  fill="#ffba0033"
                  stroke="#ffba00"
                  strokeWidth="2"
                />
              </svg>
              <span className="text-[0.5625rem] text-muted-foreground">경쟁업체</span>
            </div>
            <div className="mt-0.5 pt-1 border-t border-border">
              <span className="text-[0.5rem] font-mono text-muted-foreground">
                경쟁 {competitors.length}개 · 500m 반경
              </span>
            </div>
          </>
        )}
      </div>

      <style>{`@keyframes dash { to { stroke-dashoffset: -1000; } }`}</style>
    </div>
  );
}
