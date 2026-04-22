import { useEffect, useRef, useState, useCallback } from 'react';
import { Activity, Play } from 'lucide-react';

// 마포구 16개 행정동별 주변 상권 노드 (실좌표)
// 각 동의 중심 + 반경 ~400m 내 주요 거점으로 구성
const DONG_STORE_NODES: Record<
  string,
  { id: string; label: string; lat: number; lng: number; tier: string }[]
> = {
  서교동: [
    { id: 'hongdae', label: '홍대입구', lat: 37.5575, lng: 126.9245, tier: 'S' },
    { id: 'yeonnam', label: '연남동', lat: 37.562, lng: 126.923, tier: 'A' },
    { id: 'hapjeong', label: '합정역', lat: 37.5495, lng: 126.9185, tier: 'A' },
    { id: 'mangwon', label: '망원동', lat: 37.5565, lng: 126.9065, tier: 'B' },
  ],
  합정동: [
    { id: 'hapjeong', label: '합정역', lat: 37.5495, lng: 126.9185, tier: 'S' },
    { id: 'hongdae', label: '홍대입구', lat: 37.5575, lng: 126.9245, tier: 'A' },
    { id: 'mangwon', label: '망원동', lat: 37.5565, lng: 126.9065, tier: 'B' },
    { id: 'seogyo', label: '서교사거리', lat: 37.5522, lng: 126.9209, tier: 'B' },
  ],
  염리동: [
    { id: 'yeomni_main', label: '염리동 중심', lat: 37.5523, lng: 126.9474, tier: 'B' },
    { id: 'gongdeok', label: '공덕역', lat: 37.5456, lng: 126.9516, tier: 'S' },
    { id: 'mapo', label: '마포역', lat: 37.5441, lng: 126.9517, tier: 'A' },
    { id: 'ahyeon', label: '아현역', lat: 37.555, lng: 126.9572, tier: 'B' },
  ],
  대흥동: [
    { id: 'daeheung_main', label: '대흥동 중심', lat: 37.548, lng: 126.9437, tier: 'B' },
    { id: 'gongdeok', label: '공덕역', lat: 37.5456, lng: 126.9516, tier: 'S' },
    { id: 'mapo', label: '마포역', lat: 37.5441, lng: 126.9517, tier: 'A' },
    { id: 'sinsu', label: '신수동', lat: 37.5453, lng: 126.9361, tier: 'B' },
  ],
  공덕동: [
    { id: 'gongdeok', label: '공덕역', lat: 37.5456, lng: 126.9516, tier: 'S' },
    { id: 'mapo', label: '마포역', lat: 37.5441, lng: 126.9517, tier: 'A' },
    { id: 'ahyeon', label: '아현역', lat: 37.555, lng: 126.9572, tier: 'B' },
    { id: 'dohwa', label: '도화동', lat: 37.5393, lng: 126.9457, tier: 'B' },
  ],
  아현동: [
    { id: 'ahyeon', label: '아현역', lat: 37.555, lng: 126.9572, tier: 'S' },
    { id: 'gongdeok', label: '공덕역', lat: 37.5456, lng: 126.9516, tier: 'A' },
    { id: 'yeomni', label: '염리동', lat: 37.5523, lng: 126.9474, tier: 'B' },
    { id: 'sinchon', label: '신촌역', lat: 37.5554, lng: 126.9379, tier: 'A' },
  ],
  연남동: [
    { id: 'yeonnam', label: '연남동 메인', lat: 37.5617, lng: 126.9226, tier: 'S' },
    { id: 'hongdae', label: '홍대입구', lat: 37.5575, lng: 126.9245, tier: 'S' },
    { id: 'seongsan', label: '성산시장', lat: 37.5663, lng: 126.9069, tier: 'B' },
    { id: 'yeonnam_cafe', label: '경의선숲길', lat: 37.5596, lng: 126.9272, tier: 'A' },
  ],
  망원1동: [
    { id: 'mangwon_market', label: '망원시장', lat: 37.5558, lng: 126.9059, tier: 'S' },
    { id: 'hapjeong', label: '합정역', lat: 37.5495, lng: 126.9185, tier: 'A' },
    { id: 'mangwon2', label: '망원2동', lat: 37.5531, lng: 126.9021, tier: 'B' },
    { id: 'seongsan', label: '성산동', lat: 37.5663, lng: 126.9069, tier: 'B' },
  ],
  망원2동: [
    { id: 'mangwon2_main', label: '망원2동 중심', lat: 37.5531, lng: 126.9021, tier: 'B' },
    { id: 'mangwon_market', label: '망원시장', lat: 37.5558, lng: 126.9059, tier: 'A' },
    { id: 'hapjeong', label: '합정역', lat: 37.5495, lng: 126.9185, tier: 'A' },
    { id: 'sangam', label: '상암DMC', lat: 37.58, lng: 126.898, tier: 'B' },
  ],
  상암동: [
    { id: 'sangam_dmc', label: '상암DMC', lat: 37.58, lng: 126.898, tier: 'S' },
    { id: 'worldcup', label: '월드컵경기장', lat: 37.5686, lng: 126.8973, tier: 'A' },
    { id: 'maebong', label: '매봉산', lat: 37.5829, lng: 126.8891, tier: 'B' },
    { id: 'seongsan', label: '성산동', lat: 37.5663, lng: 126.9069, tier: 'B' },
  ],
  성산1동: [
    { id: 'seongsan1_main', label: '성산1동', lat: 37.5663, lng: 126.9069, tier: 'B' },
    { id: 'worldcup', label: '월드컵공원', lat: 37.5686, lng: 126.8973, tier: 'A' },
    { id: 'yeonnam', label: '연남동', lat: 37.5617, lng: 126.9226, tier: 'A' },
    { id: 'mangwon', label: '망원동', lat: 37.5558, lng: 126.9059, tier: 'B' },
  ],
  성산2동: [
    { id: 'seongsan2_main', label: '성산2동', lat: 37.5706, lng: 126.9111, tier: 'B' },
    { id: 'sangam', label: '상암DMC', lat: 37.58, lng: 126.898, tier: 'A' },
    { id: 'seongsan1', label: '성산1동', lat: 37.5663, lng: 126.9069, tier: 'B' },
    { id: 'worldcup', label: '월드컵경기장', lat: 37.5686, lng: 126.8973, tier: 'A' },
  ],
  신수동: [
    { id: 'sinsu_main', label: '신수동 중심', lat: 37.5453, lng: 126.9361, tier: 'B' },
    { id: 'gongdeok', label: '공덕역', lat: 37.5456, lng: 126.9516, tier: 'A' },
    { id: 'seogyo', label: '서교동', lat: 37.5565, lng: 126.9239, tier: 'B' },
    { id: 'daeheung', label: '대흥동', lat: 37.548, lng: 126.9437, tier: 'B' },
  ],
  서강동: [
    { id: 'seogang_main', label: '서강동 중심', lat: 37.5493, lng: 126.9347, tier: 'B' },
    { id: 'gongdeok', label: '공덕역', lat: 37.5456, lng: 126.9516, tier: 'A' },
    { id: 'sinsu', label: '신수동', lat: 37.5453, lng: 126.9361, tier: 'B' },
    { id: 'seogyo', label: '서교동', lat: 37.5565, lng: 126.9239, tier: 'A' },
  ],
  용강동: [
    { id: 'yonggang_main', label: '용강동 중심', lat: 37.5382, lng: 126.9383, tier: 'B' },
    { id: 'mapo', label: '마포역', lat: 37.5441, lng: 126.9517, tier: 'A' },
    { id: 'gongdeok', label: '공덕역', lat: 37.5456, lng: 126.9516, tier: 'A' },
    { id: 'dohwa', label: '도화동', lat: 37.5393, lng: 126.9457, tier: 'B' },
  ],
  도화동: [
    { id: 'dohwa_main', label: '도화동 중심', lat: 37.5393, lng: 126.9457, tier: 'B' },
    { id: 'mapo', label: '마포역', lat: 37.5441, lng: 126.9517, tier: 'S' },
    { id: 'gongdeok', label: '공덕역', lat: 37.5456, lng: 126.9516, tier: 'A' },
    { id: 'yonggang', label: '용강동', lat: 37.5382, lng: 126.9383, tier: 'B' },
  ],
};

// 기본 fallback (알 수 없는 동)
const DEFAULT_STORE_NODES = [
  { id: 'hongdae', label: '홍대입구', lat: 37.5575, lng: 126.9245, tier: 'S' },
  { id: 'gongdeok', label: '공덕역', lat: 37.5456, lng: 126.9516, tier: 'A' },
  { id: 'sinchon', label: '신촌', lat: 37.5554, lng: 126.9379, tier: 'A' },
  { id: 'mapo', label: '마포역', lat: 37.5441, lng: 126.9517, tier: 'B' },
];

const TIER_COLOR: Record<string, string> = {
  S: '#f59e0b',
  A: '#818cf8',
  B: '#6b7280',
};

const POP_TYPE_COLOR: Record<string, string> = {
  resident: '#10b981',
  commuter: '#818cf8',
  visitor: '#f59e0b',
  owner: '#f43f5e',
};

interface PixelCoord {
  x: number;
  y: number;
}

interface Persona {
  id: number;
  x: number;
  y: number;
  tx: number;
  ty: number;
  speed: number;
  type: 'resident' | 'commuter' | 'visitor' | 'owner';
  targetIdx: number;
  waitTicks: number;
}

export interface AbmScenario {
  weather_override: '맑음' | '비' | '눈' | null; // null = 현재날씨
  date_override: string | null; // ISO 날짜 or null
  weekend_force: boolean;
  rent_shock_pct: number; // 0.0 / 0.15 / 0.30 / 0.50
}

export interface AbmPersonaMapProps {
  abmResult: any;
  abmLoading: boolean;
  abmError: string | null;
  onRunSimulation: (scenario: AbmScenario) => void;
  targetDistrict?: string;
}

function randomBetween(a: number, b: number) {
  return a + Math.random() * (b - a);
}

function pickType(dist?: Record<string, number>): Persona['type'] {
  if (dist && Object.keys(dist).length > 0) {
    const r = Math.random();
    let cum = 0;
    for (const [role, prob] of Object.entries(dist)) {
      cum += prob;
      if (r < cum) return role as Persona['type'];
    }
  }
  const r = Math.random();
  if (r < 0.6) return 'resident';
  if (r < 0.85) return 'commuter';
  if (r < 0.95) return 'visitor';
  return 'owner';
}

const KAKAO_API_KEY = (import.meta as any).env?.VITE_KAKAO_MAP_API_KEY || '';
const IS_MOCK = !KAKAO_API_KEY || KAKAO_API_KEY.includes('YOUR');

export default function AbmPersonaMap({
  abmResult,
  abmLoading,
  abmError,
  onRunSimulation,
  targetDistrict = '서교동',
}: AbmPersonaMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const personasRef = useRef<Persona[]>([]);
  const nodePixelsRef = useRef<PixelCoord[]>([]);
  const rafRef = useRef<number>(0);
  const tickRef = useRef(0);

  const [mapLoaded, setMapLoaded] = useState(false);
  const [simTick, setSimTick] = useState(0);

  // 시나리오 선택 state (GameMaster 파라미터)
  const [scenario, setScenario] = useState<AbmScenario>({
    weather_override: null,
    date_override: null,
    weekend_force: false,
    rent_shock_pct: 0.0,
  });

  const N_PERSONAS = 100;

  // targetDistrict에 맞는 노드 세트 (동별 차별화)
  const storeNodes = DONG_STORE_NODES[targetDistrict] ?? DEFAULT_STORE_NODES;

  // abmResult에서 받은 customer_profile_dist를 ref로 유지
  const customerProfileDistRef = useRef<Record<string, number> | undefined>(undefined);

  // KakaoMap 좌표 → 캔버스 픽셀 변환
  const updateNodePixels = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();

    if (IS_MOCK) {
      // mock: 4개 노드 기준 비율 배치 (노드 수에 맞춰 동적 생성)
      const mockRelBase = [
        { rx: 0.55, ry: 0.45 },
        { rx: 0.42, ry: 0.35 },
        { rx: 0.38, ry: 0.62 },
        { rx: 0.65, ry: 0.7 },
      ];
      nodePixelsRef.current = storeNodes.map((_, i) => {
        const p = mockRelBase[i % mockRelBase.length];
        // 같은 기준점이면 약간 오프셋
        const offset = Math.floor(i / mockRelBase.length) * 0.06;
        return { x: (p.rx + offset) * rect.width, y: (p.ry + offset) * rect.height };
      });
    } else {
      const map = mapInstanceRef.current;
      if (!map) return;
      const proj = map.getProjection();
      const kakao = (window as any).kakao;
      nodePixelsRef.current = storeNodes.map((node) => {
        const latLng = new kakao.maps.LatLng(node.lat, node.lng);
        const pixel = proj.containerPointFromCoords(latLng);
        return { x: pixel.x, y: pixel.y };
      });
    }

    // 페르소나 위치를 새 픽셀 기준으로 초기화 (customer_profile_dist 반영)
    const dist = customerProfileDistRef.current;
    personasRef.current = Array.from({ length: N_PERSONAS }, (_, i) => {
      const nodeIdx = i % nodePixelsRef.current.length;
      const np = nodePixelsRef.current[nodeIdx];
      return {
        id: i,
        x: np.x + randomBetween(-20, 20),
        y: np.y + randomBetween(-20, 20),
        tx: np.x,
        ty: np.y,
        speed: randomBetween(1.2, 3.0),
        type: pickType(dist),
        targetIdx: nodeIdx,
        waitTicks: Math.floor(randomBetween(0, 120)),
      };
    });
  }, [storeNodes]);

  // KakaoMap 초기화
  useEffect(() => {
    if (IS_MOCK) {
      setMapLoaded(true);
      return;
    }

    const tryInit = () => {
      const kakao = (window as any).kakao;
      if (!kakao?.maps?.Map) {
        setTimeout(tryInit, 300);
        return;
      }
      if (!mapContainerRef.current) return;
      const map = new kakao.maps.Map(mapContainerRef.current, {
        center: new kakao.maps.LatLng(37.558, 126.919),
        level: 6,
      });
      mapInstanceRef.current = map;
      setMapLoaded(true);
      kakao.maps.event.addListener(map, 'idle', updateNodePixels);
    };

    if (!(window as any).kakao?.maps) {
      const script = document.createElement('script');
      script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_API_KEY}&autoload=false`;
      script.onload = () => (window as any).kakao.maps.load(tryInit);
      document.head.appendChild(script);
    } else {
      tryInit();
    }
  }, [updateNodePixels]);

  // mapLoaded 후 픽셀 계산
  useEffect(() => {
    if (mapLoaded) {
      setTimeout(updateNodePixels, 300);
    }
  }, [mapLoaded, updateNodePixels]);

  // 캔버스 리사이즈
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(() => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
      updateNodePixels();
    });
    ro.observe(canvas);
    canvas.width = canvas.offsetWidth || 800;
    canvas.height = canvas.offsetHeight || 600;
    return () => ro.disconnect();
  }, [updateNodePixels]);

  // 애니메이션 루프
  useEffect(() => {
    if (!mapLoaded) return;

    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const W = canvas.width;
      const H = canvas.height;

      ctx.clearRect(0, 0, W, H);

      // 노드 간 연결선 (거리 기반)
      const nodes = nodePixelsRef.current;
      ctx.strokeStyle = 'rgba(129,140,248,0.15)';
      ctx.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          if (Math.hypot(dx, dy) < W * 0.28) {
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.stroke();
          }
        }
      }

      // 상권 노드 그리기
      nodes.forEach((np, idx) => {
        const node = storeNodes[idx];
        if (!node) return;
        const r = node.tier === 'S' ? 14 : node.tier === 'A' ? 11 : 9;
        const color = TIER_COLOR[node.tier];

        // glow
        const grad = ctx.createRadialGradient(np.x, np.y, 0, np.x, np.y, r * 2.5);
        grad.addColorStop(0, color + '44');
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(np.x, np.y, r * 2.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = color + 'bb';
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(np.x, np.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 10px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(node.label, np.x, np.y + r + 13);
        ctx.fillStyle = color;
        ctx.font = 'bold 8px monospace';
        ctx.fillText(`Tier ${node.tier}`, np.x, np.y + r + 22);
      });

      // 페르소나 이동 & 그리기
      personasRef.current.forEach((p) => {
        if (nodes.length === 0) return;
        if (p.waitTicks > 0) {
          p.waitTicks--;
          if (p.waitTicks === 0) {
            let nextIdx = Math.floor(Math.random() * nodes.length);
            if (nextIdx === p.targetIdx) nextIdx = (nextIdx + 1) % nodes.length;
            p.targetIdx = nextIdx;
            p.tx = nodes[nextIdx].x + randomBetween(-15, 15);
            p.ty = nodes[nextIdx].y + randomBetween(-15, 15);
          }
        } else {
          const dx = p.tx - p.x;
          const dy = p.ty - p.y;
          const dist = Math.hypot(dx, dy);
          if (dist < 5) {
            p.waitTicks = Math.floor(randomBetween(60, 200));
          } else {
            p.x += (dx / dist) * p.speed;
            p.y += (dy / dist) * p.speed;
          }
        }

        const color = POP_TYPE_COLOR[p.type];
        ctx.fillStyle = color + 'cc';
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
        ctx.fill();
      });

      tickRef.current++;
      if (tickRef.current % 60 === 0) setSimTick((t) => t + 1);

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, [mapLoaded]);

  const elapsedMin = Math.floor(simTick / 4);
  const timeLabel = `${String((Math.floor(elapsedMin / 60) + 8) % 24).padStart(2, '0')}:${String(elapsedMin % 60).padStart(2, '0')}`;

  return (
    <div className="flex-1 w-full h-full min-h-[700px] mt-4 relative animate-in zoom-in-95 fade-in duration-500 flex flex-col pb-6">
      <div className="flex-1 bg-[#1e1b18] border border-[#3a3633] rounded-2xl overflow-hidden shadow-2xl flex flex-col relative">
        {/* 헤더 — AI 에이전트 맵과 동일 스타일 */}
        <div className="h-14 bg-[#171717]/90 backdrop-blur-md border-b border-[#3a3633] flex justify-between items-center px-6 shrink-0 z-10">
          <h3 className="text-sm font-black text-white flex items-center gap-3">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_10px_rgba(52,211,153,0.8)]" />
            ABM 페르소나 행동 시뮬레이션
          </h3>
          <div className="flex items-center gap-4">
            <span className="text-[11px] font-mono text-emerald-400">
              {N_PERSONAS} PERSONAS · {timeLabel}
            </span>
            <span className="text-[10px] text-[#6b7280] font-mono tracking-widest uppercase">
              MAPO BEHAVIORAL SIM · {targetDistrict}
            </span>
          </div>
        </div>

        {/* 맵 + 캔버스 오버레이 레이어 */}
        <div className="flex-1 relative">
          {/* KakaoMap 베이스 레이어 */}
          {IS_MOCK ? (
            <div className="absolute inset-0 bg-[#1a2535]">
              {/* mock 배경 — 도시 그리드 */}
              <svg className="w-full h-full opacity-10" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#818cf8" strokeWidth="0.5" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-[#3a3633] font-mono text-xs">
                  KAKAO MAP (MOCK MODE — set VITE_KAKAO_MAP_API_KEY)
                </span>
              </div>
            </div>
          ) : (
            <div ref={mapContainerRef} className="absolute inset-0" />
          )}

          {/* 투명 캔버스 오버레이 — 페르소나 + 노드 */}
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full pointer-events-none"
            style={{ zIndex: 10 }}
          />

          {/* 범례 */}
          <div className="absolute top-3 left-3 bg-[#0d1117]/80 backdrop-blur-sm border border-[#3a3633] rounded-lg p-2.5 z-20">
            <p className="text-[9px] font-mono text-[#6b7280] uppercase tracking-wider mb-1.5">
              Persona Type
            </p>
            {Object.entries(POP_TYPE_COLOR).map(([type, color]) => (
              <div key={type} className="flex items-center gap-1.5 mb-0.5">
                <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                <span className="text-[9px] font-mono text-[#9ca3af] capitalize">{type}</span>
              </div>
            ))}
            <div className="mt-2 pt-1.5 border-t border-[#3a3633]">
              <p className="text-[9px] font-mono text-[#6b7280] uppercase tracking-wider mb-1">
                Store Tier
              </p>
              {Object.entries(TIER_COLOR).map(([tier, color]) => (
                <div key={tier} className="flex items-center gap-1.5 mb-0.5">
                  <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                  <span className="text-[9px] font-mono text-[#9ca3af]">Tier {tier}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 하단 — 결과 통계 or 실행 버튼 */}
          <div className="absolute bottom-4 left-0 right-0 px-4 z-20 flex flex-col items-center gap-3">
            {abmResult ? (
              <div className="w-full max-w-2xl bg-[#0d1117]/90 backdrop-blur-sm border border-emerald-500/30 rounded-xl p-3 grid grid-cols-4 gap-3">
                <div className="text-center">
                  <p className="text-[9px] font-mono text-[#6b7280] uppercase mb-0.5">일 방문</p>
                  <p className="text-lg font-black text-emerald-300">
                    {abmResult.daily_visits_mean?.toLocaleString() ?? '-'}
                    <span className="text-[10px] text-[#6b7280] ml-0.5">명</span>
                  </p>
                  {abmResult.daily_visits_std > 0 && (
                    <p className="text-[9px] text-[#6b7280]">σ {abmResult.daily_visits_std}</p>
                  )}
                </div>
                <div className="text-center">
                  <p className="text-[9px] font-mono text-[#6b7280] uppercase mb-0.5">
                    월 매출 추정
                  </p>
                  <p className="text-lg font-black text-emerald-300">
                    {abmResult.monthly_revenue_estimate
                      ? `${Math.round(abmResult.monthly_revenue_estimate / 10000)}만`
                      : '-'}
                  </p>
                  <p className="text-[9px] text-[#6b7280]">일매출×25</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] font-mono text-[#6b7280] uppercase mb-0.5">피크</p>
                  <p className="text-sm font-bold text-emerald-300">
                    {abmResult.peak_hours?.[0] ?? '-'}
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] font-mono text-[#6b7280] uppercase mb-0.5">MC</p>
                  <p className="text-lg font-black text-emerald-300">
                    {abmResult.monte_carlo_runs}
                    <span className="text-[10px] text-[#6b7280] ml-0.5">회</span>
                  </p>
                  <p className="text-[9px] text-[#6b7280]">{abmResult.n_personas}명</p>
                </div>
              </div>
            ) : abmLoading ? (
              <div className="bg-[#0d1117]/90 backdrop-blur-sm border border-emerald-500/30 rounded-xl px-6 py-3 flex items-center gap-3">
                <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
                <span className="text-sm text-emerald-300 font-mono">
                  {scenario.weather_override ?? '현재날씨'} ·{' '}
                  {scenario.weekend_force ? '주말' : '평일'} · 임대료 +
                  {Math.round(scenario.rent_shock_pct * 100)}% — 시뮬 실행 중...
                </span>
              </div>
            ) : abmError ? (
              <div className="bg-[#0d1117]/90 backdrop-blur-sm border border-amber-500/30 rounded-xl px-6 py-3">
                <p className="text-sm text-amber-400">{abmError}</p>
              </div>
            ) : (
              /* 시나리오 선택 UI + 실행 버튼 */
              <div className="w-full max-w-2xl bg-[#0d1117]/90 backdrop-blur-sm border border-[#3a3633] rounded-xl p-4 flex flex-col gap-3">
                {/* 날씨 */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-[#6b7280] w-16 shrink-0">날씨</span>
                  <div className="flex gap-1.5">
                    {([null, '맑음', '비', '눈'] as const).map((w) => (
                      <button
                        key={w ?? 'auto'}
                        onClick={() => setScenario((s) => ({ ...s, weather_override: w }))}
                        className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all border ${
                          scenario.weather_override === w
                            ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-300'
                            : 'border-[#3a3633] text-[#6b7280] hover:text-[#9ca3af] hover:border-[#4a4643]'
                        }`}
                      >
                        {w === null
                          ? '현재날씨'
                          : w === '맑음'
                            ? '☀️ 맑음'
                            : w === '비'
                              ? '🌧 비'
                              : '❄️ 눈'}
                      </button>
                    ))}
                  </div>
                </div>
                {/* 요일 */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-[#6b7280] w-16 shrink-0">요일</span>
                  <div className="flex gap-1.5">
                    {[
                      { label: '오늘', weekend_force: false, date: null },
                      { label: '평일', weekend_force: false, date: '2026-04-21' },
                      { label: '주말', weekend_force: true, date: null },
                    ].map((opt) => (
                      <button
                        key={opt.label}
                        onClick={() =>
                          setScenario((s) => ({
                            ...s,
                            weekend_force: opt.weekend_force,
                            date_override: opt.date,
                          }))
                        }
                        className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all border ${
                          scenario.weekend_force === opt.weekend_force &&
                          scenario.date_override === opt.date
                            ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-300'
                            : 'border-[#3a3633] text-[#6b7280] hover:text-[#9ca3af] hover:border-[#4a4643]'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
                {/* 임대료 충격 */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-[#6b7280] w-16 shrink-0">임대료</span>
                  <div className="flex gap-1.5">
                    {[0, 0.15, 0.3, 0.5].map((pct) => (
                      <button
                        key={pct}
                        onClick={() => setScenario((s) => ({ ...s, rent_shock_pct: pct }))}
                        className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all border ${
                          scenario.rent_shock_pct === pct
                            ? pct === 0
                              ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-300'
                              : 'bg-rose-500/20 border-rose-500/60 text-rose-300'
                            : 'border-[#3a3633] text-[#6b7280] hover:text-[#9ca3af] hover:border-[#4a4643]'
                        }`}
                      >
                        {pct === 0 ? '현재' : `+${Math.round(pct * 100)}%`}
                      </button>
                    ))}
                  </div>
                </div>
                {/* 실행 버튼 */}
                <button
                  onClick={() => onRunSimulation(scenario)}
                  className="mt-1 flex items-center justify-center gap-2 py-2.5 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/50 hover:border-emerald-400 text-emerald-300 rounded-lg text-sm font-bold transition-all duration-300 shadow-[0_0_20px_rgba(52,211,153,0.15)]"
                >
                  <Play className="w-4 h-4" />
                  {targetDistrict} · {scenario.weather_override ?? '현재날씨'} ·{' '}
                  {scenario.weekend_force ? '주말' : '평일'} · 임대료 +
                  {Math.round(scenario.rent_shock_pct * 100)}% 시뮬 실행
                </button>
              </div>
            )}
          </div>

          {/* Narrator 요약 */}
          {abmResult?.narrator_summary && (
            <div className="absolute top-3 right-3 max-w-xs bg-[#0d1117]/90 backdrop-blur-sm border border-[#3a3633] rounded-lg p-3 z-20">
              <p className="text-[10px] font-mono text-emerald-400 mb-1 uppercase tracking-wider">
                Narrator
              </p>
              <p className="text-[11px] text-[#9ca3af] leading-relaxed">
                {abmResult.narrator_summary}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
