import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Brain, ShieldAlert, LineChart, Target, MapPin, Users } from 'lucide-react';

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
  type?: 'candidate' | 'vacancy';
  listingCount?: number;
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

// 백엔드 `backend/src/agents/nodes/` 5개 노드와 일치
const AGENTS = [
  { id: 'market', name: 'Market Analyst', icon: <LineChart />, color: '#818cf8' },
  { id: 'population', name: 'Population Analyst', icon: <Users />, color: '#10b981' },
  { id: 'supervisor', name: 'Supervisor Node', icon: <Brain />, color: '#f59e0b' },
  { id: 'legal', name: 'Legal Analyst', icon: <ShieldAlert />, color: '#f43f5e' },
  { id: 'strategy', name: 'Strategy Synthesizer', icon: <Target />, color: '#06b6d4' },
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
  const agentRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const [mapLoaded, setMapLoaded] = useState(false);
  const [targetPixels, setTargetPixels] = useState<Record<string | number, PixelCoord>>({});
  const [competitorPixels, setCompetitorPixels] = useState<Record<string | number, PixelCoord>>({});
  const [agentPixels, setAgentPixels] = useState<Record<string, PixelCoord>>({});
  const [showLasers, setShowLasers] = useState(false);

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

    const newAgentPixels: Record<string, PixelCoord> = {};
    AGENTS.forEach((agent) => {
      const agentEl = agentRefs.current[agent.id];
      if (agentEl) {
        const rect = agentEl.getBoundingClientRect();
        newAgentPixels[agent.id] = {
          x: rect.left - containerRect.left + rect.width / 2,
          y: rect.top - containerRect.top - 10,
        };
      }
    });
    setAgentPixels(newAgentPixels);
  }, [IS_MOCK_MODE, locations, competitors]);

  useEffect(() => {
    let cleanupFn = () => {};
    const handleResize = () => updateCoordinates();

    if (IS_MOCK_MODE) {
      setMapLoaded(true);
      const timer = setTimeout(() => {
        updateCoordinates();
        setShowLasers(true);
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
          setShowLasers(true);
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

  return (
    <div
      className="w-full bg-[#1e1b18] rounded-2xl border border-[#3a3633] overflow-hidden relative shadow-2xl flex flex-col"
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
        <div className="absolute inset-0 z-0 bg-[#050505] overflow-hidden pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                'linear-gradient(rgba(129, 140, 248, 0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(129, 140, 248, 0.15) 1px, transparent 1px)',
              backgroundSize: '50px 50px',
              transform: 'perspective(500px) rotateX(60deg) scale(2) translateY(-100px)',
              transformOrigin: 'top center',
            }}
          />
          <div className="absolute top-[40%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] border border-[#818cf8]/20 rounded-full animate-[spin_10s_linear_infinite]" />
          <div className="absolute top-[40%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[450px] h-[450px] border border-[#818cf8]/10 rounded-full animate-[spin_15s_linear_infinite_reverse]" />
          <div className="absolute top-4 left-4 font-mono text-[10px] text-[#818cf8] opacity-50 tracking-widest">
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
                className="absolute z-30 flex items-center justify-center w-8 h-8 rounded-full bg-[#06b6d4] border-2 border-[#22d3ee] text-[#0f172a] text-xs font-black shadow-[0_0_14px_rgba(6,182,212,0.8)] transition-all duration-200 pointer-events-auto cursor-pointer hover:scale-125 hover:bg-[#22d3ee] disabled:cursor-default disabled:opacity-60"
                style={{
                  left: pixel.x,
                  top: pixel.y,
                  transform: 'translate(-50%, -50%)',
                }}
              >
                {vacancyNumber}
                <span className="absolute inline-flex h-full w-full rounded-full bg-[#22d3ee] opacity-40 animate-ping" />
              </button>
            );
          }

          // candidate 기존 핀
          const pinColor = '#818cf8';
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
              <div className="bg-[#1e1b18] border text-[#e2e8f0] px-2 py-0.5 rounded text-[9px] font-bold mb-1 border-[#818cf8] shadow-[0_0_10px_rgba(129,140,248,0.5)]">
                {loc.name}
              </div>
              <MapPin className="w-6 h-6" style={{ color: pinColor, fill: `${pinColor}33` }} />
              <div className="w-2 h-2 rounded-full animate-ping absolute bottom-1 bg-[#818cf8]" />
            </div>
          );
        })}

      {/* 경쟁업체 핀 */}
      {mapLoaded &&
        competitors.map((comp) => {
          const pixel = competitorPixels[comp.id];
          if (!pixel) return null;
          const isFranchise = comp.is_franchise;
          const pinColor = isFranchise ? '#f43f5e' : '#f97316';
          const borderClass = isFranchise
            ? 'border-[#f43f5e] shadow-[0_0_8px_rgba(244,63,94,0.5)]'
            : 'border-[#f97316] shadow-[0_0_8px_rgba(249,115,22,0.4)]';
          const distLabel = comp.distance_m != null ? ` ${Math.round(comp.distance_m)}m` : '';
          return (
            <div
              key={`comp-${comp.id}`}
              className="absolute z-20 flex flex-col items-center pointer-events-none transition-all duration-300"
              style={{
                left: pixel.x,
                top: pixel.y,
                transform: 'translate(-50%, -100%)',
              }}
            >
              <div
                className={`bg-[#1e1b18] border text-[10px] font-bold mb-0.5 px-2 py-0.5 rounded max-w-[120px] truncate ${borderClass}`}
                style={{ color: pinColor }}
                title={comp.name}
              >
                {comp.name}
                {distLabel && (
                  <span className="ml-1 text-[8px] text-[#9ca3af] font-normal">{distLabel}</span>
                )}
              </div>
              <svg width="18" height="18" viewBox="0 0 18 18">
                <polygon
                  points="9,2 16,16 2,16"
                  fill={`${pinColor}33`}
                  stroke={pinColor}
                  strokeWidth="1.5"
                />
              </svg>
              <span
                className="text-[7px] font-mono mt-0.5 px-1 rounded"
                style={{ color: pinColor, background: `${pinColor}22` }}
              >
                {isFranchise ? '프랜차이즈' : '개인점'}
              </span>
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

        {showLasers &&
          AGENTS.map((agent, idx) => {
            const start = agentPixels[agent.id];
            const dynamicTargetId = locations[idx % locations.length]?.id;
            const end = dynamicTargetId !== undefined ? targetPixels[dynamicTargetId] : undefined;
            if (!start || !end) return null;

            const controlY = Math.min(start.y, end.y) - 150;
            const pathD = `M ${start.x} ${start.y} Q ${(start.x + end.x) / 2} ${controlY} ${end.x} ${end.y}`;

            return (
              <g key={`laser-${agent.id}`}>
                <path
                  d={pathD}
                  fill="none"
                  stroke={agent.color}
                  strokeWidth="4"
                  opacity="0.3"
                  filter="url(#glow)"
                />
                <path
                  d={pathD}
                  fill="none"
                  stroke={agent.color}
                  strokeWidth="2"
                  strokeDasharray="10 15"
                  className="animate-[dash_20s_linear_infinite]"
                />
                <circle r="3" fill="#fff" filter="url(#glow)">
                  <animateMotion
                    dur={`${2 + Math.random()}s`}
                    repeatCount="indefinite"
                    path={pathD}
                  />
                </circle>
              </g>
            );
          })}
      </svg>

      <div className="absolute bottom-6 left-0 w-full flex justify-center gap-6 md:gap-12 z-40 px-4">
        {AGENTS.map((agent) => (
          <div
            key={agent.id}
            ref={(el) => {
              agentRefs.current[agent.id] = el;
            }}
            className="flex flex-col items-center group cursor-pointer"
          >
            <div className="w-1.5 h-1.5 rounded-full bg-white mb-1 shadow-[0_0_8px_#fff]" />
            <div
              className="w-12 h-12 md:w-16 md:h-16 rounded-2xl bg-[#1e1b18]/90 backdrop-blur-md border border-[#3a3633] flex items-center justify-center shadow-xl transition-all duration-300 group-hover:-translate-y-2 group-hover:border-[var(--agent-color)]"
              style={{ ['--agent-color' as string]: agent.color } as React.CSSProperties}
            >
              {React.cloneElement(
                agent.icon as React.ReactElement<{
                  className?: string;
                  color?: string;
                }>,
                {
                  className: 'w-6 h-6 md:w-8 md:h-8',
                  color: agent.color,
                },
              )}
            </div>
            <span className="mt-3 text-[10px] md:text-xs font-mono font-bold text-[#9ca3af] group-hover:text-white transition-colors bg-[#1e1b18]/80 px-2 py-1 rounded border border-[#3a3633]/50">
              {agent.name}
            </span>
          </div>
        ))}
      </div>

      {/* 범례 */}
      <div className="absolute top-3 left-3 z-40 bg-[#0d1117]/80 backdrop-blur-sm border border-[#3a3633] rounded-lg p-2.5 flex flex-col gap-1.5">
        <p className="text-[8px] font-mono text-[#6b7280] uppercase tracking-wider mb-0.5">
          Legend
        </p>
        <div className="flex items-center gap-1.5">
          <MapPin className="w-3 h-3" style={{ color: '#818cf8' }} />
          <span className="text-[9px] text-[#9ca3af]">출점 후보지</span>
        </div>
        <div className="flex items-center gap-1.5">
          <MapPin className="w-3 h-3" style={{ color: '#10b981' }} />
          <span className="text-[9px] text-[#9ca3af]">공실 매물</span>
        </div>
        {competitors.length > 0 && (
          <>
            <div className="flex items-center gap-1.5">
              <svg width="10" height="10" viewBox="0 0 18 18">
                <polygon
                  points="9,2 16,16 2,16"
                  fill="#f43f5e33"
                  stroke="#f43f5e"
                  strokeWidth="2"
                />
              </svg>
              <span className="text-[9px] text-[#9ca3af]">경쟁 프랜차이즈</span>
            </div>
            <div className="flex items-center gap-1.5">
              <svg width="10" height="10" viewBox="0 0 18 18">
                <polygon
                  points="9,2 16,16 2,16"
                  fill="#f9731633"
                  stroke="#f97316"
                  strokeWidth="2"
                />
              </svg>
              <span className="text-[9px] text-[#9ca3af]">경쟁 개인점</span>
            </div>
            <div className="mt-0.5 pt-1 border-t border-[#3a3633]">
              <span className="text-[8px] font-mono text-[#6b7280]">
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
