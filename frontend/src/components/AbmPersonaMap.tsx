import { useEffect, useRef, useState, useCallback } from 'react';
import { Activity, Play } from 'lucide-react';
import VacancySpotMarker from './VacancySpotMarker';
import VacancyStatsPanel from './VacancyStatsPanel';
import PersonaCard, { type PersonaCardData } from './PersonaCard';

// 스팟 노드 스키마 — 백엔드 /mapo/spots/{dong} 에서 동적 조회 (하드코딩 없음)
interface StoreNode {
  id: string;
  label: string;
  lat: number;
  lng: number;
  tier: string;
}

// 백엔드 응답 대기 중/실패 시 최후 fallback — 마포 중심 1점만 (지도 중심 표시용)
const FALLBACK_CENTER: StoreNode = {
  id: 'mapo-center',
  label: '마포구 중심',
  lat: 37.558,
  lng: 126.919,
  tier: 'S',
};

// 에이전트 Action 색 (채움) — gold(결제)·cyan(external halo)·white(테두리)는 별도
const ACTION_COLOR: Record<string, string> = {
  visit: '#E45756', // Red — 매장 방문(결제)
  move: '#4C78A8', // Blue — 이동 중
  work: '#54A24B', // Green — 근무 (테두리만)
  rest: '#6b7280', // Gray — 휴식 (희미)
};

// Phase 2: 4 거점 floating glassmorphism 카드 — 마포 대표 dong centroid.
// Orion 레퍼런스의 주요 도시 카드(Chicago/Berlin/Sangam-DMC 등) 패턴 재현.
const KEY_DONGS: Array<{ name: string; lat: number; lon: number; color: string }> = [
  { name: 'Hongdae-Ip-Gu', lat: 37.553, lon: 126.918, color: '#f43f5e' }, // 서교동·홍대입구
  { name: 'Sangam-DMC', lat: 37.567, lon: 126.916, color: '#818cf8' }, // 성산동
  { name: 'Gongdeok-Stn', lat: 37.544, lon: 126.953, color: '#f43f5e' }, // 공덕동
  { name: 'Mangwon-Mkt', lat: 37.557, lon: 126.905, color: '#fbbf24' }, // 망원동
];

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
  // Bezier fallback (도로 경로 없을 때)
  mx: number;
  my: number;
  progress: number;
  // 실제 도로 waypoint 따라 걷기
  waypoints: PixelCoord[];
  waypointIdx: number;
  segmentProgress: number;
  speed: number;
  type: 'resident' | 'commuter' | 'visitor' | 'owner' | 'ext_commuter' | 'ext_visitor';
  targetIdx: number;
  sourceIdx: number;
  waitTicks: number;
  tier: 'S' | 'A' | 'B';
  action: 'visit' | 'move' | 'work' | 'rest';
  spend: number;
  wobblePhase: number;
  // 개인화 — 1열 행렬 방지
  lateralOffset: number; // 경로 수직 방향 편향 (-15 ~ +15 px, 경로 내 좌/우 치우침)
  wobbleAmp: number; // 개인별 걸음 흔들림 크기 (0.6 ~ 2.4)
  preferredSpots: number[]; // 이 agent가 선호하는 스팟 인덱스 순서
  dwellMultiplier: number; // 체류 시간 배수 (role별)
  hasSpawned: boolean; // External 에이전트 최초 등장 이펙트 여부
  // External 페이드인 진행률 계산용 — 초기 waitTicks 값
  entryDuration: number;
  // 이동 꼬리 (최대 8개 ring buffer) — 움직일 때만 push
  trail: { x: number; y: number; age: number }[];
}

export interface AbmScenario {
  weather_override: '맑음' | '비' | '눈' | null; // null = 현재날씨
  date_override: string | null; // ISO 날짜 or null
  weekend_force: boolean;
  rent_shock_pct: number; // 0.0 / 0.15 / 0.30 / 0.50
}

// 에이전트(district_ranking 노드) 가 /simulate 응답으로 내려주는 공실 스팟 형태
export interface AgentVacancySpot {
  id: number | string;
  lat: number;
  lon: number;
  dong_name: string;
  listing_count?: number;
}

// vacancy 모드 — pse_summary (vacancy_evaluation /single 결과)
export interface VacancyPseSummary {
  visits_per_day?: { mean: number; ci95: number };
  revenue_per_day?: { mean: number; ci95: number };
  vacancy_vs_avg_visits_ratio?: { mean: number; ci95: number };
  cannibalization_pct?: { mean: number; ci95: number };
  dong_net_growth_pct?: { mean: number; ci95: number };
}

// vacancy 모드에서 강조 표시할 spot
export interface VacancySpotHighlight {
  dong: string;
  lat: number;
  lng: number;
  category?: string;
}

// Tier S 50명만 LLM thought 생성 — backend (Task 1·2·3, 다른 세션) contract.
// Plan: docs/superpowers/plans/2026-04-28-tier-s-llm-thought.md
// 본 컴포넌트는 plan T4·T5 (frontend 풍선 + PersonaCard) 담당.
export interface AbmThought {
  agent_id: number;
  hour: number;
  day: number;
  archetype: string;
  thought: string; // 한국어 ≤ 12자
  lat: number | null; // backend 가 null 가능
  lon: number | null;
}

// 4950 non-Tier-S 에이전트의 시간별 위치 집계 — 히트맵 렌더용.
// backend 가 마포 bbox 를 cols×rows 격자로 나눠 hour 별 셀 카운트 응답.
// hours[absHour] = row-major flat array (length = cols × rows).
export interface AbmDensityGrid {
  bbox: [number, number, number, number]; // [minLat, minLon, maxLat, maxLon]
  cols: number;
  rows: number;
  hours: Record<string, number[]>;
  max_count?: number; // 색 정규화용 (없으면 hour 별 max 동적 계산)
}

export interface AbmPersonaMapProps {
  abmResult: any;
  abmLoading: boolean;
  abmError: string | null;
  onRunSimulation: (scenario: AbmScenario) => void;
  targetDistrict?: string;
  /** 에이전트 5종 평가 결과의 추천 공실 스팟. 있으면 정적 CSV fallback 대신 이걸로 지도에 찍는다. */
  vacancySpots?: AgentVacancySpot[];
  /** 공실 스팟 클릭 시 호출 — 부모가 /api/simulate-abm 을 그 좌표로 트리거한다. */
  onSpotClick?: (spot: AgentVacancySpot) => void;
  /** 결과 오버레이 "← 뒤로" 버튼 클릭 시 호출 — 부모가 abmResult 를 비워 스팟 선택 화면으로 복귀시킨다. */
  onClearResult?: () => void;
  /** 대시보드에서 선택된 스팟 — 있으면 지도에는 이 스팟만 하이라이트, 다른 노드는 agent routine 용으로 숨김. */
  focusSpot?: { lat: number; lon: number; label?: string } | null;
  /** 'general' (default) — 기존 마포 전체 시뮬 / 'vacancy' — vacancy_pse 시각화 모드 */
  mode?: 'general' | 'vacancy';
  /** mode='vacancy' 시 backend job_id (vacancy-evaluation 4 endpoint polling) */
  vacancyJobId?: string;
  /** mode='vacancy' 시 강조 표시할 vacancy spot 좌표/카테고리 */
  vacancySpot?: VacancySpotHighlight;
  /** mode='vacancy' 시 외부에서 직접 pse_summary 주입 (선택, 미주입 시 vacancyJobId 로 fetch) */
  vacancyPseSummary?: VacancyPseSummary | null;
  /**
   * 선택 공실 근처의 경쟁업체 (같은 카테고리). 있으면 spots-all 의 마포 16동
   * 일반 매장 80개 대신 이 경쟁업체들을 storeNodes 로 사용 — agents 가 이쪽으로
   * 방문 → 신규 매장 vs 경쟁사 visit 분포 비교 시각화에 더 의미 있음.
   */
  competitors?: Array<{
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
  }>;
  /**
   * Tier S 50명만 클릭 가능. canvas 클릭 시 5px 이내 Tier S agent 가 있으면 호출.
   * 부모(AbmTab)가 PersonaCard 모달로 연결.
   */
  onPersonaClick?: (agentId: number, thoughts: AbmThought[]) => void;
}

function randomBetween(a: number, b: number) {
  return a + Math.random() * (b - a);
}

function pickType(dist?: Record<string, number>): Persona['type'] {
  // 실 customer_profile_dist 있으면 우선 사용, 없으면 기본 분포 폴백
  if (dist && Object.keys(dist).length > 0) {
    const r = Math.random();
    let cum = 0;
    for (const [role, prob] of Object.entries(dist)) {
      cum += prob;
      if (r < cum) return role as Persona['type'];
    }
  }
  // 기본 분포: 거주40 / 통근10 / 방문5 / 점주5 / 외부통근30 / 외부방문10
  const r = Math.random();
  if (r < 0.4) return 'resident';
  if (r < 0.5) return 'commuter';
  if (r < 0.55) return 'visitor';
  if (r < 0.6) return 'owner';
  if (r < 0.9) return 'ext_commuter';
  return 'ext_visitor';
}

function pickTier(): Persona['tier'] {
  const r = Math.random();
  if (r < 0.05) return 'S';
  if (r < 0.25) return 'A';
  return 'B';
}

// Role별 특성 — 속도/체류/wobble
function roleTraits(type: Persona['type']) {
  switch (type) {
    case 'resident':
      return { speedRange: [1.0, 2.0], dwellMult: 1.0, wobble: [0.8, 1.6] };
    case 'commuter':
      return { speedRange: [1.8, 3.2], dwellMult: 0.7, wobble: [0.6, 1.2] };
    case 'visitor':
      return { speedRange: [1.0, 1.8], dwellMult: 1.5, wobble: [1.0, 2.0] };
    case 'owner':
      return { speedRange: [0.6, 1.2], dwellMult: 3.0, wobble: [0.4, 1.0] };
    case 'ext_commuter':
      return { speedRange: [2.0, 3.5], dwellMult: 0.8, wobble: [0.6, 1.2] };
    case 'ext_visitor':
      return { speedRange: [1.2, 2.2], dwellMult: 1.8, wobble: [1.2, 2.4] };
  }
}

// 에이전트별 선호 스팟 순열 (preferredSpots) — 같은 스팟 순서로 반복되지 않게
function shuffleSpots(nodeCount: number): number[] {
  const arr = Array.from({ length: nodeCount }, (_, i) => i);
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

const KAKAO_API_KEY = (import.meta as any).env?.VITE_KAKAO_MAP_API_KEY || '';
const KAKAO_KEY_MISSING = !KAKAO_API_KEY || KAKAO_API_KEY.includes('YOUR');

// Safari 15 / iOS 15 등 구형 대응 — ctx.roundRect 폴백
function roundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  const maxR = Math.min(r, w / 2, h / 2);
  if (typeof (ctx as any).roundRect === 'function') {
    (ctx as any).roundRect(x, y, w, h, maxR);
    return;
  }
  ctx.moveTo(x + maxR, y);
  ctx.arcTo(x + w, y, x + w, y + h, maxR);
  ctx.arcTo(x + w, y + h, x, y + h, maxR);
  ctx.arcTo(x, y + h, x, y, maxR);
  ctx.arcTo(x, y, x + w, y, maxR);
  ctx.closePath();
}

// 상점 — 집 모양 (지붕 삼각형 + 몸체 사각형)
function drawStoreHouse(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  tier: string,
  ringColor: string,
  lineWidth: number,
) {
  const w = 26;
  const h = 22;
  const roofH = 9;
  const bodyH = h - roofH;
  const left = cx - w / 2;
  const top = cy - h / 2;
  // Tier별 채움 (어두운 계열) + 테두리 (좀 밝은 계열)
  // A: #818CF8 / B: #9CA3AF / 기타(S 이외): 동일
  let fill: string;
  let accent: string;
  if (tier === 'A') {
    fill = '#4F46E5';
    accent = '#818CF8';
  } else if (tier === 'B') {
    fill = '#4B5563';
    accent = '#9CA3AF';
  } else {
    fill = '#4F46E5';
    accent = '#818CF8';
  }
  // 지붕 (삼각형)
  ctx.fillStyle = accent;
  ctx.beginPath();
  ctx.moveTo(cx, top);
  ctx.lineTo(left + w, top + roofH);
  ctx.lineTo(left, top + roofH);
  ctx.closePath();
  ctx.fill();
  // 몸체 (사각형)
  ctx.fillStyle = fill;
  ctx.fillRect(left + 2, top + roofH, w - 4, bodyH);
  // 창문 (작은 사각)
  ctx.fillStyle = accent;
  ctx.fillRect(left + 5, top + roofH + 3, 4, 4);
  ctx.fillRect(left + w - 9, top + roofH + 3, 4, 4);
  // 문 (중앙)
  ctx.fillStyle = '#1F2937';
  ctx.fillRect(cx - 2, top + h - 6, 4, 6);
  // 테두리 (흰색 반투명 또는 gold 강조)
  ctx.strokeStyle = ringColor;
  ctx.lineWidth = lineWidth;
  ctx.beginPath();
  // 지붕 테두리
  ctx.moveTo(cx, top);
  ctx.lineTo(left + w, top + roofH);
  ctx.lineTo(left + w - 2, top + roofH);
  ctx.lineTo(left + w - 2, top + h);
  ctx.lineTo(left + 2, top + h);
  ctx.lineTo(left + 2, top + roofH);
  ctx.lineTo(left, top + roofH);
  ctx.closePath();
  ctx.stroke();
}

// 결제 순간 bounce 아이콘 (gold 원 + ₩ 글자) — 0~36 tick (0.6초 @ 60fps)
function drawPaymentBounce(ctx: CanvasRenderingContext2D, cx: number, baseY: number, age: number) {
  const dur = 36;
  if (age < 0 || age > dur) return;
  const t = age / dur;
  // bounce: 위로 튀었다가 내려옴 (sin)
  const bounceH = 18;
  const offsetY = -Math.sin(t * Math.PI) * bounceH;
  const alpha = t < 0.8 ? 1 : 1 - (t - 0.8) / 0.2;
  const cy = baseY + offsetY;
  ctx.save();
  ctx.globalAlpha = alpha;
  // 그림자
  ctx.fillStyle = 'rgba(0,0,0,0.35)';
  ctx.beginPath();
  ctx.arc(cx, baseY + 2, 4 * (1 - Math.abs(offsetY) / bounceH) + 2, 0, Math.PI * 2);
  ctx.fill();
  // gold 원
  ctx.fillStyle = '#FBBF24';
  ctx.strokeStyle = '#B45309';
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.arc(cx, cy, 6, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  // ₩ 글자
  ctx.fillStyle = '#111827';
  ctx.font = 'bold 8px monospace';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('\u20A9', cx, cy + 0.5);
  ctx.textBaseline = 'alphabetic';
  ctx.restore();
}

export default function AbmPersonaMap({
  abmResult,
  abmLoading,
  abmError,
  onRunSimulation,
  targetDistrict = '서교동',
  vacancySpots,
  onSpotClick,
  onClearResult,
  focusSpot,
  mode = 'general',
  vacancyJobId,
  vacancySpot,
  vacancyPseSummary = null,
  competitors,
  onPersonaClick,
}: AbmPersonaMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const personasRef = useRef<Persona[]>([]);
  const nodePixelsRef = useRef<PixelCoord[]>([]);
  const rafRef = useRef<number>(0);
  const tickRef = useRef(0);

  // 결제 이펙트 (ring pulse + ₩ 텍스트) — tick 기반 애니메이션
  const paymentEffectsRef = useRef<{ nodeIdx: number; amount: number; startTick: number }[]>([]);
  // 결제 bounce 아이콘 (₩ 원 튀어오름) — 36 tick (0.6초) 선행 애니메이션
  const paymentBouncesRef = useRef<{ nodeIdx: number; startTick: number }[]>([]);
  // 스팟별 통계 (실시간 누적) — draw 루프에서 집계
  const spotStatsRef = useRef<{ visits: number; revenue: number; currentAgents: number }[]>([]);
  // External 스폰 이펙트 (역 출구 cyan pulse) — 지하철/버스 도착 연출
  const spawnEffectsRef = useRef<{ x: number; y: number; startTick: number }[]>([]);
  // 실제 ABM trajectory — 에이전트별 시간순 경로 (백엔드 실시뮬 결과).
  // agent_id → [{absHour, lat, lon, role, action}, ...] (시간 순 정렬). 보간해서 부드럽게 이동.
  // action: 'rest'|'visit'|'work'|'move' — backend 가 행동 라벨 함께 전달 (미응답 시 'move').
  const trajectoryPathsRef = useRef<
    Map<number, { absHour: number; lat: number; lon: number; role: string; action: string }[]>
  >(new Map());
  const trajectoryMinHourRef = useRef(0);
  const trajectoryMaxHourRef = useRef(0);

  // Tier S thoughts — agent_id 별 hour-keyed Map. trajectory 모드에서 풍선 표시용.
  // tierSIdsRef = thoughts 에 등장한 agent_id Set (Tier S 마커용 — 별도 필드 불필요).
  const thoughtsByAgentRef = useRef<Map<number, Map<number, AbmThought>>>(new Map());
  const tierSIdsRef = useRef<Set<number>>(new Set());
  // 4950 non-Tier-S 히트맵 격자 — hour 별 cell 카운트 (backend density_grid).
  const densityGridRef = useRef<AbmDensityGrid | null>(null);
  // 헥사 격자 — 마포 polygon 안의 hex 좌표 + density cell 매핑 (pan/zoom 시 재계산).
  // 매 프레임 projection 호출 비용 회피 (2000+ hex × 60fps = 너무 비쌈).
  const hexGridRef = useRef<{ x: number; y: number; dr: number; dc: number }[]>([]);
  // Mapo 16 dong polygon (lat/lon) — public/mapo-dong.geo.json fetch.
  const mapoPolygonsRef = useRef<{ name: string; ring: [number, number][] }[]>([]);
  // Mapo polygon — pixel space cache (pan/zoom 시 재투영). 외부 dark mask 그릴 때 사용.
  const mapoPolyPixelsRef = useRef<{ x: number; y: number }[][]>([]);
  // dong 이름 라벨용 — centroid lat/lon → 픽셀 (pan/zoom 시 갱신).
  const [dongLabels, setDongLabels] = useState<Array<{ name: string; x: number; y: number }>>([]);
  // Phase 2: 4 거점 floating 카드 픽셀 좌표 — pan/zoom 시 갱신.
  const [keyDongPx, setKeyDongPx] = useState<Array<{ x: number; y: number }>>([]);
  // Phase 2: hover hit-test 결과 — 마우스 근처 hex 의 density 정보. 우하단 카드 표시용.
  const [hoveredHex, setHoveredHex] = useState<{
    x: number;
    y: number;
    intensity: number;
    count: number;
  } | null>(null);
  // Tier S agent_id → 현재 프레임 화면 픽셀 — 클릭 hit-test 용. forEach 안에서 매 프레임 업데이트.
  const tierSPixelsRef = useRef<Map<number, { x: number; y: number }>>(new Map());
  // 현재 displayHour — 클릭 핸들러가 PersonaCard 에 전달.
  const currentDisplayHourRef = useRef<number>(0);
  // 선택된 Tier S 페르소나 카드 (모달).
  const [selectedPersona, setSelectedPersona] = useState<PersonaCardData | null>(null);

  const [mapLoaded, setMapLoaded] = useState(false);
  // Kakao 맵 이벤트 리스너가 항상 최신 함수 참조하도록 (stale closure 방지)
  const updateNodePixelsRef = useRef<() => void>(() => {});
  const recomputeNodePixelsRef = useRef<() => void>(() => {});
  // 드래그/줌 중엔 canvas 렌더 skip (이전 픽셀 좌표에 잔상 방지)
  const isMapMovingRef = useRef(false);
  const [simTick, setSimTick] = useState(0);

  // 시나리오 선택 state (GameMaster 파라미터)
  const [scenario, setScenario] = useState<AbmScenario>({
    weather_override: null,
    date_override: null,
    weekend_force: false,
    rent_shock_pct: 0.0,
  });

  // 마포 polygon GeoJSON load (1회) — public/mapo-dong.geo.json 16 동.
  // hex 마스킹(폴리곤 내부만) + dong 라벨 표시에 사용.
  useEffect(() => {
    fetch('/mapo-dong.geo.json')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((geo) => {
        if (!geo?.features) return;
        const polys = geo.features.map((f: any) => ({
          name: String(f?.properties?.dong_name ?? ''),
          ring: (f?.geometry?.coordinates?.[0] ?? []) as [number, number][],
        }));
        mapoPolygonsRef.current = polys.filter(
          (p: any) => p.name && Array.isArray(p.ring) && p.ring.length >= 3,
        );
        // 폴리곤 변경 → hex 격자 + dong 라벨 재계산.
        recomputeNodePixelsRef.current?.();
      })
      .catch((e) => console.warn('[ABM] mapo-dong.geo.json fetch 실패:', e));
  }, []);

  // 시뮬에서 받은 실제 에이전트 수로 점박이 개수 맞춤 (기본 100)
  const N_PERSONAS = abmResult?.n_personas ?? abmResult?.n_agents ?? 100;

  // targetDistrict에 맞는 노드 세트.
  // 우선순위:
  //   1) props.vacancySpots (에이전트 5종 평가 결과, district_ranking 노드 → /simulate 응답)
  //   2) 백엔드 /api/mapo/spots/{dong} (정적 CSV fallback, 시뮬 전 단계)
  //   3) FALLBACK_CENTER (네트워크/데이터 실패 시 마포 중심점)
  const [storeNodes, setStoreNodes] = useState<StoreNode[]>([FALLBACK_CENTER]);
  const [spotsLoading, setSpotsLoading] = useState(false);

  // abmResult에서 받은 customer_profile_dist를 ref로 유지 (pickType에 전달)
  const customerProfileDistRef = useRef<Record<string, number> | undefined>(undefined);

  // vacancy 모드 — 4 endpoint fetch 결과 (mode='vacancy' 시만 사용)
  const [vacancyTrajectory, setVacancyTrajectory] = useState<any[]>([]);
  const [vacancyVisits, setVacancyVisits] = useState<any[]>([]);
  const [vacancyStores, setVacancyStores] = useState<any[]>([]);
  const [vacancyChats, setVacancyChats] = useState<any[]>([]);
  const [vacancySummary, setVacancySummary] = useState<VacancyPseSummary | null>(vacancyPseSummary);
  const [vacancyFetching, setVacancyFetching] = useState(false);
  const [vacancyFetchError, setVacancyFetchError] = useState<string | null>(null);

  // abmResult.trajectory 파싱 — 시간별 위치 스냅샷 맵 구성 (실제 ABM 결과 오버레이용)
  useEffect(() => {
    const tr = abmResult?.trajectory;
    trajectoryPathsRef.current = new Map();
    trajectoryMinHourRef.current = 0;
    trajectoryMaxHourRef.current = 0;
    if (!Array.isArray(tr) || tr.length === 0) return;

    // agent 별로 시간순 경로 구성 → 보간 대상
    const byAgent = new Map<
      number,
      { absHour: number; lat: number; lon: number; role: string; action: string }[]
    >();
    let minHour = Infinity;
    let maxHour = -Infinity;
    for (const e of tr) {
      if (typeof e?.lat !== 'number' || typeof e?.lon !== 'number') continue;
      const absHour = (Number(e.day) || 0) * 24 + (Number(e.hour) || 0);
      minHour = Math.min(minHour, absHour);
      maxHour = Math.max(maxHour, absHour);
      const aid = Number(e.agent_id) || 0;
      if (!byAgent.has(aid)) byAgent.set(aid, []);
      // action 미응답 시 'move' default. backend Task 추가되면 실값 ('rest'|'visit'|'work'|'move').
      byAgent.get(aid)!.push({
        absHour,
        lat: Number(e.lat),
        lon: Number(e.lon),
        role: String(e.role || 'resident'),
        action: String(e.action || 'move'),
      });
    }
    // 각 에이전트 경로를 absHour 기준 정렬
    byAgent.forEach((path) => path.sort((a, b) => a.absHour - b.absHour));
    trajectoryPathsRef.current = byAgent;
    trajectoryMinHourRef.current = isFinite(minHour) ? minHour : 0;
    trajectoryMaxHourRef.current = isFinite(maxHour) ? maxHour : 0;
  }, [abmResult]);

  // abmResult.thoughts 파싱 — Tier S 50명 LLM thought (다른 세션 backend 작업).
  // 미수신 시 빈 Map → 기존 동작 그대로 (graceful degradation).
  useEffect(() => {
    const ths = abmResult?.thoughts;
    thoughtsByAgentRef.current = new Map();
    tierSIdsRef.current = new Set();
    if (!Array.isArray(ths) || ths.length === 0) return;
    for (const t of ths) {
      if (typeof t?.agent_id !== 'number') continue;
      const aid = Number(t.agent_id);
      const absHour = (Number(t.day) || 0) * 24 + (Number(t.hour) || 0);
      if (!thoughtsByAgentRef.current.has(aid)) {
        thoughtsByAgentRef.current.set(aid, new Map());
      }
      thoughtsByAgentRef.current.get(aid)!.set(absHour, {
        agent_id: aid,
        hour: Number(t.hour) || 0,
        day: Number(t.day) || 0,
        archetype: String(t.archetype || ''),
        thought: String(t.thought || '').slice(0, 12),
        lat: typeof t.lat === 'number' ? t.lat : null,
        lon: typeof t.lon === 'number' ? t.lon : null,
      });
      tierSIdsRef.current.add(aid);
    }
  }, [abmResult]);

  // 히트맵 grid 구성 — 우선순위:
  //   1) backend abmResult.density_grid (정식 contract) — 5000 agents 전체 카운트
  //   2) 폴백: trajectory 데이터(300 sample) 를 마포 bbox × 30×30 격자에 hour 별 binning
  // backend 미구현 시 frontend 가 직접 derive 해서 히트맵 표시.
  useEffect(() => {
    const dg = abmResult?.density_grid;
    // (1) backend 가 정식 density_grid 보내주면 그걸 사용
    if (
      dg &&
      Array.isArray(dg.bbox) &&
      dg.bbox.length === 4 &&
      typeof dg.cols === 'number' &&
      typeof dg.rows === 'number' &&
      typeof dg.hours === 'object'
    ) {
      densityGridRef.current = {
        bbox: dg.bbox as [number, number, number, number],
        cols: dg.cols,
        rows: dg.rows,
        hours: dg.hours,
        max_count: typeof dg.max_count === 'number' ? dg.max_count : undefined,
      };
      recomputeNodePixelsRef.current?.();
      return;
    }

    // (2) Fallback: trajectory entries 로 격자 binning.
    const tr = abmResult?.trajectory;
    if (!Array.isArray(tr) || tr.length === 0) {
      densityGridRef.current = null;
      return;
    }
    // 마포구 bbox (대략) — 실제 trajectory min/max 로 동적 결정 가능하지만 고정이 안정적.
    // 마포 동 centroid 범위: lat 37.539~37.575, lon 126.892~126.951 → 약간 padding.
    const minLat = 37.535;
    const maxLat = 37.58;
    const minLon = 126.888;
    const maxLon = 126.955;
    // 격자 80×64 (셀 ~75m × ~70m) — backend density_grid 와 동일 해상도.
    const cols = 80;
    const rows = 64;
    const dLat = (maxLat - minLat) / rows;
    const dLon = (maxLon - minLon) / cols;
    const hours: Record<string, number[]> = {};
    let maxCount = 0;
    for (const e of tr) {
      const lat = Number(e?.lat);
      const lon = Number(e?.lon);
      if (!isFinite(lat) || !isFinite(lon)) continue;
      const absHour = (Number(e.day) || 0) * 24 + (Number(e.hour) || 0);
      const r = Math.floor((maxLat - lat) / dLat);
      const c = Math.floor((lon - minLon) / dLon);
      if (r < 0 || r >= rows || c < 0 || c >= cols) continue; // 마포 밖 skip
      const key = String(absHour);
      let arr = hours[key];
      if (!arr) {
        arr = new Array(cols * rows).fill(0);
        hours[key] = arr;
      }
      const idx = r * cols + c;
      arr[idx] += 1;
      if (arr[idx] > maxCount) maxCount = arr[idx];
    }
    if (Object.keys(hours).length === 0) {
      densityGridRef.current = null;
      return;
    }
    densityGridRef.current = {
      bbox: [minLat, minLon, maxLat, maxLon],
      cols,
      rows,
      hours,
      max_count: maxCount,
    };
    // density_grid 갱신 → hex 격자 재계산 (recomputeNodePixels 가 hex 도 생성).
    recomputeNodePixelsRef.current?.();
  }, [abmResult]);

  useEffect(() => {
    // mode='vacancy' 분기 — vacancy_pse 4 endpoint 동시 fetch.
    // 공실 시각화 모드는 마포 16동 전체 spots 로드를 건너뛰고
    // /vacancy-evaluation/{job_id}/{trajectory,visits,stores,chats} 을 polling.
    if (mode === 'vacancy') {
      if (!vacancyJobId) {
        // job_id 미지정 → 빈 상태 유지 (회귀 X)
        setVacancyTrajectory([]);
        setVacancyVisits([]);
        setVacancyStores([]);
        setVacancyChats([]);
        setSpotsLoading(false);
        return;
      }
      let cancelled = false;
      setVacancyFetching(true);
      setVacancyFetchError(null);
      Promise.all([
        fetch(`/vacancy-evaluation/${vacancyJobId}/trajectory`).then((r) =>
          r.ok ? r.json() : Promise.reject(new Error(`trajectory ${r.status}`)),
        ),
        fetch(`/vacancy-evaluation/${vacancyJobId}/visits`).then((r) =>
          r.ok ? r.json() : Promise.reject(new Error(`visits ${r.status}`)),
        ),
        fetch(`/vacancy-evaluation/${vacancyJobId}/stores`).then((r) =>
          r.ok ? r.json() : Promise.reject(new Error(`stores ${r.status}`)),
        ),
        fetch(`/vacancy-evaluation/${vacancyJobId}/chats`).then((r) =>
          r.ok ? r.json() : Promise.reject(new Error(`chats ${r.status}`)),
        ),
      ])
        .then(([traj, visits, stores, chats]) => {
          if (cancelled) return;
          setVacancyTrajectory(traj?.trajectory ?? []);
          setVacancyVisits(visits?.visits_events ?? []);
          setVacancyStores(stores?.stores ?? []);
          setVacancyChats(chats?.chats ?? []);
          // pse_summary 가 endpoint 응답에 실려 오면 자동 동기화 (외부 prop 미주입 시).
          // 응답 위치는 backend 설계에 따라 stores/visits/trajectory 어느 쪽이든 가능 → 우선순위 폴백.
          const inferredSummary: VacancyPseSummary | null =
            stores?.pse_summary ??
            stores?.vacancy_spot?.pse_summary ??
            visits?.pse_summary ??
            traj?.pse_summary ??
            null;
          if (inferredSummary && !vacancyPseSummary) {
            setVacancySummary(inferredSummary);
          }
          setVacancyFetching(false);
        })
        .catch((e: Error) => {
          if (cancelled) return;
          setVacancyFetchError(e.message || 'vacancy fetch failed');
          setVacancyFetching(false);
        });
      return () => {
        cancelled = true;
      };
    }

    // mode='general' (default).
    // 우선순위: competitors prop (선택 공실 근처 동일 카테고리 매장) → spots-all → /mapo/spots/{dong}.
    // competitors 가 있으면 마포 전역 80 spot 대신 경쟁사 좌표를 storeNodes 로 사용 →
    // 5000 agents 가 그 매장들에 visit 하는 모습이 의미 있는 "신규 vs 경쟁" 분포 시각화가 됨.
    let cancelled = false;
    setSpotsLoading(true);
    if (Array.isArray(competitors) && competitors.length > 0) {
      const compNodes: StoreNode[] = competitors
        .filter(
          (c) =>
            typeof c.lat === 'number' && (typeof c.lng === 'number' || typeof c.lon === 'number'),
        )
        .slice(0, 60)
        .map((c, i) => ({
          id: c.id ?? `comp-${i}`,
          label: (c.name || c.place_name || c.brand_name || '경쟁업체').slice(0, 18),
          lat: c.lat as number,
          lng: (c.lng ?? c.lon) as number,
          tier: c.is_franchise ? 'A' : 'B',
        }));
      setStoreNodes(compNodes.length > 0 ? compNodes : [FALLBACK_CENTER]);
      setSpotsLoading(false);
      return () => {
        cancelled = true;
      };
    }
    fetch(`/api/mapo/spots-all?per_dong=5`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`spots-all ${r.status}`))))
      .then((data: { spots?: StoreNode[] }) => {
        if (cancelled) return;
        const list = Array.isArray(data.spots) && data.spots.length > 0 ? data.spots : null;
        setStoreNodes(list ?? [FALLBACK_CENTER]);
        setSpotsLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        // fallback — 기존 단일 동 엔드포인트
        fetch(`/api/mapo/spots/${encodeURIComponent(targetDistrict)}?limit=16`)
          .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`spots ${r.status}`))))
          .then((d: { spots?: StoreNode[] }) => {
            if (cancelled) return;
            const list = Array.isArray(d.spots) && d.spots.length > 0 ? d.spots : null;
            setStoreNodes(list ?? [FALLBACK_CENTER]);
            setSpotsLoading(false);
          })
          .catch(() => {
            if (cancelled) return;
            setStoreNodes([FALLBACK_CENTER]);
            setSpotsLoading(false);
          });
      });
    return () => {
      cancelled = true;
    };
  }, [mode, vacancyJobId, targetDistrict, competitors]);

  // mode='vacancy' 시 외부에서 prop 으로 주입된 pse_summary 동기화
  useEffect(() => {
    if (mode === 'vacancy') {
      setVacancySummary(vacancyPseSummary);
    }
  }, [mode, vacancyPseSummary]);

  // 노드 픽셀만 재계산 — 맵 zoom/pan 시마다 호출 (에이전트 유지)
  const recomputeNodePixels = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const map = mapInstanceRef.current;
    if (!map) return;
    const proj = map.getProjection();
    const kakao = (window as any).kakao;
    if (!kakao?.maps?.LatLng) return;
    nodePixelsRef.current = storeNodes.map((node) => {
      const latLng = new kakao.maps.LatLng(node.lat, node.lng);
      const pixel = proj.containerPointFromCoords(latLng);
      return { x: pixel.x, y: pixel.y };
    });

    // 헥사 격자 hex 중심 픽셀 + density cell 매핑 — pan/zoom 변할 때만 재계산.
    // hex size 8px (셀 ~14px wide), 1100~1300개 hex (마포 bbox 한정).
    const dg = densityGridRef.current;
    if (dg && dg.cols > 0 && dg.rows > 0) {
      const [minLat, minLon, maxLat, maxLon] = dg.bbox;
      const topLeft = proj.containerPointFromCoords(new kakao.maps.LatLng(maxLat, minLon));
      const bottomRight = proj.containerPointFromCoords(new kakao.maps.LatLng(minLat, maxLon));
      const HEX_SIZE = 8; // hex 외접원 반지름 (px)
      const xStep = HEX_SIZE * Math.sqrt(3); // 가로 간격
      const yStep = HEX_SIZE * 1.5; // 세로 간격
      const dLatPx = bottomRight.y - topLeft.y;
      const dLonPx = bottomRight.x - topLeft.x;
      const cols = Math.ceil(dLonPx / xStep) + 1;
      const rows = Math.ceil(dLatPx / yStep) + 1;
      // pointInPolygon — ray casting (lat/lon 공간).
      const polys = mapoPolygonsRef.current;
      const inMapo = (lat: number, lon: number): boolean => {
        if (polys.length === 0) return true; // geo 미로드 시 마스킹 X (전체 통과)
        for (const p of polys) {
          const ring = p.ring;
          let inside = false;
          for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            const xi = ring[i][0], // lon
              yi = ring[i][1]; // lat
            const xj = ring[j][0],
              yj = ring[j][1];
            const intersect =
              yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
            if (intersect) inside = !inside;
          }
          if (inside) return true; // 어느 한 dong polygon 안이면 마포 안.
        }
        return false;
      };
      const newGrid: { x: number; y: number; dr: number; dc: number }[] = [];
      for (let rr = 0; rr < rows; rr++) {
        for (let cc = 0; cc < cols; cc++) {
          const offsetX = rr % 2 === 0 ? 0 : xStep / 2;
          const px = topLeft.x + cc * xStep + offsetX;
          const py = topLeft.y + rr * yStep;
          // pixel → lat/lon 역산: 선형 보간 (Kakao map 단거리 근사 OK)
          const latRatio = (py - topLeft.y) / (dLatPx || 1);
          const lonRatio = (px - topLeft.x) / (dLonPx || 1);
          const hexLat = maxLat - latRatio * (maxLat - minLat);
          const hexLon = minLon + lonRatio * (maxLon - minLon);
          // density cell index
          const dr = Math.floor(((maxLat - hexLat) / (maxLat - minLat)) * dg.rows);
          const dc = Math.floor(((hexLon - minLon) / (maxLon - minLon)) * dg.cols);
          if (dr < 0 || dr >= dg.rows || dc < 0 || dc >= dg.cols) continue;
          // 마포 polygon 안에 있는 hex 만 (한강·외부 자동 컷).
          if (!inMapo(hexLat, hexLon)) continue;
          newGrid.push({ x: px, y: py, dr, dc });
        }
      }
      hexGridRef.current = newGrid;
    } else {
      hexGridRef.current = [];
    }

    // dong 16 centroid 픽셀 — 라벨 표시용. polygon 평균.
    const polys = mapoPolygonsRef.current;
    if (polys.length > 0) {
      setDongLabels(
        polys.map((p) => {
          const lons = p.ring.map((c) => c[0]);
          const lats = p.ring.map((c) => c[1]);
          const cLon = lons.reduce((a, b) => a + b, 0) / lons.length;
          const cLat = lats.reduce((a, b) => a + b, 0) / lats.length;
          const pix = proj.containerPointFromCoords(new kakao.maps.LatLng(cLat, cLon));
          return { name: p.name, x: pix.x, y: pix.y };
        }),
      );
      // 외부 dark mask 용 — 16 polygon 의 ring 을 픽셀로 캐싱.
      mapoPolyPixelsRef.current = polys.map((p) =>
        p.ring.map(([lon, lat]) => {
          const px = proj.containerPointFromCoords(new kakao.maps.LatLng(lat, lon));
          return { x: px.x, y: px.y };
        }),
      );
    } else {
      setDongLabels([]);
      mapoPolyPixelsRef.current = [];
    }

    // Phase 2: 4 거점 카드 픽셀 좌표 — pan/zoom 변할 때마다 갱신.
    setKeyDongPx(
      KEY_DONGS.map((d) => {
        const pix = proj.containerPointFromCoords(new kakao.maps.LatLng(d.lat, d.lon));
        return { x: pix.x, y: pix.y };
      }),
    );
  }, [storeNodes]);

  // 페르소나 전체 초기화 — 동 변경 or 최초 로드 시만
  const updateNodePixels = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    recomputeNodePixels();

    // 노드 픽셀 아직 준비 안됐으면 persona 초기화 skip (다음 호출에서 시도)
    if (nodePixelsRef.current.length === 0) {
      return;
    }

    // C-3: 노드가 2개 미만이면 에이전트 시뮬레이션 자체를 시작하지 않음
    if (storeNodes.length < 2) {
      personasRef.current = [];
      spotStatsRef.current = storeNodes.map(() => ({
        visits: 0,
        revenue: 0,
        currentAgents: 0,
      }));
      paymentEffectsRef.current = [];
      paymentBouncesRef.current = [];
      spawnEffectsRef.current = [];
      return;
    }

    // customer_profile_dist 반영 (pickType에 전달)
    const dist = customerProfileDistRef.current;

    // 페르소나 위치 초기화 — 개인화된 경로/속도/체류/선호
    const transitHubIdxs = storeNodes
      .map((n, idx) => ({ idx, id: n.id, tier: n.tier }))
      .filter(({ id, tier }) => id.startsWith('subway-') || tier === 'S')
      .map(({ idx }) => idx);
    personasRef.current = Array.from({ length: N_PERSONAS }, (_, i) => {
      const type = pickType(dist);
      const traits = roleTraits(type);
      const isExternal = type === 'ext_commuter' || type === 'ext_visitor';
      const preferred = shuffleSpots(nodePixelsRef.current.length);

      let nodeIdx: number;
      let sourceIdx: number;
      // 시작 위치 — External은 지하철역/교통 허브, 일반은 스팟 근처
      let sx: number;
      let sy: number;
      if (isExternal) {
        const hubIdx =
          transitHubIdxs.length > 0
            ? transitHubIdxs[Math.floor(Math.random() * transitHubIdxs.length)]
            : Math.floor(Math.random() * nodePixelsRef.current.length);
        const hubPix = nodePixelsRef.current[hubIdx];
        sx = hubPix.x + randomBetween(-15, 15);
        sy = hubPix.y + randomBetween(-15, 15);
        sourceIdx = hubIdx;
        const targetCandidates = preferred.filter((p) => p !== hubIdx);
        nodeIdx = targetCandidates.length > 0 ? targetCandidates[0] : preferred[0];
      } else {
        nodeIdx = preferred[0];
        const np = nodePixelsRef.current[nodeIdx];
        sx = np.x + randomBetween(-30, 30);
        sy = np.y + randomBetween(-30, 30);
        sourceIdx = nodeIdx;
      }

      const targetNode = nodePixelsRef.current[nodeIdx];

      // External 은 60~180 tick(1~3초) 페이드인 후 cyan ripple 등장. 일반 에이전트는 즉시 활동.
      const initialWait = isExternal
        ? Math.floor(randomBetween(60, 180))
        : Math.floor(randomBetween(0, 180));

      return {
        id: i,
        x: sx,
        y: sy,
        tx: targetNode.x,
        ty: targetNode.y,
        mx: sx,
        my: sy,
        progress: 1,
        waypoints: [] as PixelCoord[],
        waypointIdx: 0,
        segmentProgress: 0,
        speed: randomBetween(traits.speedRange[0], traits.speedRange[1]),
        type,
        targetIdx: nodeIdx,
        sourceIdx,
        waitTicks: initialWait,
        tier: pickTier(),
        action: 'rest',
        spend: randomBetween(0, 30000),
        wobblePhase: Math.random() * Math.PI * 2,
        lateralOffset: (Math.random() < 0.5 ? -1 : 1) * randomBetween(2, 14),
        wobbleAmp: randomBetween(traits.wobble[0], traits.wobble[1]),
        preferredSpots: preferred,
        dwellMultiplier: traits.dwellMult,
        hasSpawned: false,
        entryDuration: initialWait,
        trail: [],
      };
    });
    // 스팟 통계 초기화
    spotStatsRef.current = storeNodes.map(() => ({
      visits: 0,
      revenue: 0,
      currentAgents: 0,
    }));
    paymentEffectsRef.current = [];
    paymentBouncesRef.current = [];

    spawnEffectsRef.current = [];
  }, [storeNodes, N_PERSONAS]);

  // OSRM prefetch 제거 (2026-04-28) — 합성 ambient persona 만 쓰던 캐시.
  // 결과 모드(trajectory)는 OSRM 미사용, Tier S 50/heatmap 4950 도 미사용.
  // 합성 persona 는 bezier fallback (waypoints.length<2 분기) 으로 자동 회귀.

  // KakaoMap 초기화
  useEffect(() => {
    if (KAKAO_KEY_MISSING) return;

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

      // Zoom/Pan 시작 전 — 현재 에이전트 위치 lat/lng snapshot 저장
      let snapshots: { id: number; lat: number; lng: number }[] = [];
      const takeSnapshot = () => {
        isMapMovingRef.current = true;
        const proj = map.getProjection();
        snapshots = personasRef.current.map((p) => {
          const latLng = proj.coordsFromContainerPoint(new kakao.maps.Point(p.x, p.y));
          return { id: p.id, lat: latLng.getLat(), lng: latLng.getLng() };
        });
        // 줌/드래그 시작 시 잔상 trail 전부 초기화 (이전 픽셀 좌표 의미 상실)
        personasRef.current.forEach((p) => {
          p.trail = [];
        });
        paymentEffectsRef.current = [];
        paymentBouncesRef.current = [];
        spawnEffectsRef.current = [];
      };

      // Zoom/Pan 완료 시 — lat/lng → 새 픽셀로 에이전트 좌표 재변환
      const remapAgents = () => {
        const proj = map.getProjection();
        if (snapshots.length > 0) {
          for (const snap of snapshots) {
            const p = personasRef.current.find((pp) => pp.id === snap.id);
            if (p) {
              const newPx = proj.containerPointFromCoords(
                new kakao.maps.LatLng(snap.lat, snap.lng),
              );
              p.x = newPx.x;
              p.y = newPx.y;
              // 파생 픽셀 좌표 전부 초기화 — 다음 사이클에 재계산
              p.waypoints = [];
              p.waypointIdx = 0;
              p.segmentProgress = 0;
              p.progress = 1;
              p.mx = p.x;
              p.my = p.y;
            }
          }
          snapshots = [];
        }
        paymentEffectsRef.current = [];
        paymentBouncesRef.current = [];
        spawnEffectsRef.current = [];
        recomputeNodePixelsRef.current();
        isMapMovingRef.current = false;
      };

      // Phase 2: hover — hex 위 마우스 → 가까운 hex 의 density 표시.
      // throttle: 50ms 간격 (rAF 대신 setTimeout 으로 단순화).
      let _hoverTimer: number | null = null;
      kakao.maps.event.addListener(map, 'mousemove', (mouseEvent: any) => {
        if (_hoverTimer != null) return;
        _hoverTimer = window.setTimeout(() => {
          _hoverTimer = null;
          const dg = densityGridRef.current;
          const hexes = hexGridRef.current;
          if (!dg || hexes.length === 0) {
            setHoveredHex(null);
            return;
          }
          const proj2 = map.getProjection?.();
          if (!proj2 || !mouseEvent?.latLng) return;
          const mPx = proj2.containerPointFromCoords(mouseEvent.latLng);
          // 가장 가까운 hex (HEX_SIZE=8 의 1.5배 = 12px 안)
          const HOVER_R2 = 12 * 12;
          let bestIdx = -1;
          let bestD2 = HOVER_R2;
          for (let i = 0; i < hexes.length; i++) {
            const dx = hexes[i].x - mPx.x;
            const dy = hexes[i].y - mPx.y;
            const d2 = dx * dx + dy * dy;
            if (d2 < bestD2) {
              bestD2 = d2;
              bestIdx = i;
            }
          }
          if (bestIdx < 0) {
            setHoveredHex(null);
            return;
          }
          const hex = hexes[bestIdx];
          const hourKey = String(currentDisplayHourRef.current);
          const cells = dg.hours[hourKey];
          if (!Array.isArray(cells)) {
            setHoveredHex(null);
            return;
          }
          const v = cells[hex.dr * dg.cols + hex.dc] ?? 0;
          const maxC = dg.max_count || 1;
          setHoveredHex({
            x: hex.x,
            y: hex.y,
            intensity: v / maxC,
            count: v,
          });
        }, 50);
      });
      kakao.maps.event.addListener(map, 'mouseout', () => {
        setHoveredHex(null);
      });

      kakao.maps.event.addListener(map, 'zoom_start', takeSnapshot);
      kakao.maps.event.addListener(map, 'dragstart', takeSnapshot);
      kakao.maps.event.addListener(map, 'idle', () => {
        if (snapshots.length > 0) {
          remapAgents();
        } else {
          recomputeNodePixelsRef.current();
          isMapMovingRef.current = false;
        }
      });

      // Tier S 클릭 hit-test — Kakao map 'click' 이벤트로 latLng 받아 픽셀 변환 후
      // tierSPixelsRef 를 18px 이내 검색. 일치 agent 있으면 PersonaCard 모달 오픈.
      // (canvas 가 pointer-events:none 이라 직접 onClick 못 씀 → map 이벤트 사용)
      kakao.maps.event.addListener(map, 'click', (mouseEvent: any) => {
        // 디버그 — click 이 도달하는지 확인 (사용자 보고: "안 눌려").
        // 빠른 dot 클릭 가능하게 hit 반경 8 → 18px 로 확대.
        const tsCount = tierSPixelsRef.current.size;
        const tCount = thoughtsByAgentRef.current.size;

        console.log(
          `[ABM click] tierSPixels=${tsCount} thoughts=${tCount} latLng=`,
          mouseEvent?.latLng?.getLat?.()?.toFixed?.(5),
          mouseEvent?.latLng?.getLng?.()?.toFixed?.(5),
        );
        if (tsCount === 0) {
          console.warn(
            '[ABM click] Tier S dot 없음 — backend 가 thoughts 응답을 안 줬거나, ' +
              'enable_llm_thought=false, 또는 backend 재시작 필요. ' +
              '시뮬 결과 화면 좌상단 배지에 "⭐50" 표시되는지 확인.',
          );
          return;
        }
        const proj = map.getProjection?.();
        if (!proj || !mouseEvent?.latLng) return;
        const clickPx = proj.containerPointFromCoords(mouseEvent.latLng);
        const HIT_R2 = 18 * 18; // 18px 이내 hit — 빠른 dot 클릭 마진
        let bestAid: number | null = null;
        let bestD2 = HIT_R2;
        tierSPixelsRef.current.forEach((pix, aid) => {
          const dx = pix.x - clickPx.x;
          const dy = pix.y - clickPx.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < bestD2) {
            bestD2 = d2;
            bestAid = aid;
          }
        });
        if (bestAid === null) {
          // 가장 가까운 dot 거리도 함께 표시 (debug)
          let nearestD = Infinity;
          tierSPixelsRef.current.forEach((pix) => {
            const d = Math.hypot(pix.x - clickPx.x, pix.y - clickPx.y);
            if (d < nearestD) nearestD = d;
          });

          console.log(
            `[ABM click] miss — 가장 가까운 Tier S dot ${nearestD.toFixed(1)}px (hit 임계 18px)`,
          );
          return;
        }
        const aid: number = bestAid;

        console.log(`[ABM click] HIT agent#${aid}, distance=${Math.sqrt(bestD2).toFixed(1)}px`);
        const thoughts = Array.from(thoughtsByAgentRef.current.get(aid)?.values() ?? []);
        // 부모 콜백 우선 (있으면 부모가 모달 표시), 없으면 내부 PersonaCard 사용.
        if (onPersonaClick) {
          onPersonaClick(aid, thoughts);
          return;
        }
        const archetype = thoughts[0]?.archetype || '';
        const path = trajectoryPathsRef.current.get(aid);
        const role = path && path[0] ? path[0].role : undefined;
        setSelectedPersona({
          agentId: aid,
          archetype,
          thoughts,
          role,
        });
      });
    };

    if (!(window as any).kakao?.maps) {
      const script = document.createElement('script');
      script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_API_KEY}&autoload=false`;
      script.onload = () => (window as any).kakao.maps.load(tryInit);
      document.head.appendChild(script);
    } else {
      tryInit();
    }
    // 맵 초기화는 mount 시 1회만 — 함수 변경에 따른 재초기화 방지
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 함수 ref 최신화 (storeNodes 변경 시 새 함수 참조 유지)
  useEffect(() => {
    updateNodePixelsRef.current = updateNodePixels;
    recomputeNodePixelsRef.current = recomputeNodePixels;
  }, [updateNodePixels, recomputeNodePixels]);

  // mapLoaded 후 픽셀 계산 — 맵 초기화 완료 타이밍 확보용 300ms 지연
  useEffect(() => {
    if (!mapLoaded) return;
    const t = setTimeout(() => updateNodePixels(), 300);
    return () => clearTimeout(t);
  }, [mapLoaded, updateNodePixels]);

  // 캔버스 리사이즈 — persona 재생성 없이 노드 픽셀만 재계산
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(() => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
      recomputeNodePixels();
    });
    ro.observe(canvas);
    canvas.width = canvas.offsetWidth || 800;
    canvas.height = canvas.offsetHeight || 600;
    return () => ro.disconnect();
  }, [recomputeNodePixels]);

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

      // 맵 drag/zoom 중엔 아무것도 그리지 않음 (이전 픽셀 잔상 방지)
      if (isMapMovingRef.current) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      // ─── Mapo 외부 dark mask (Orion 레퍼런스 스타일) ───────────────────────
      // canvas 전체 dark fill - 16 dong polygon 구멍 (even-odd fill rule).
      // 마포 안만 카카오맵 보이고, 외부(한강·외부 구) 는 dim 처리.
      const polyPixels = mapoPolyPixelsRef.current;
      if (polyPixels.length > 0) {
        ctx.save();
        ctx.beginPath();
        // 외곽 사각형 (시계방향)
        ctx.moveTo(0, 0);
        ctx.lineTo(W, 0);
        ctx.lineTo(W, H);
        ctx.lineTo(0, H);
        ctx.closePath();
        // 16 dong polygon — even-odd 로 자동 hole 처리.
        for (const ring of polyPixels) {
          if (ring.length < 3) continue;
          ctx.moveTo(ring[0].x, ring[0].y);
          for (let i = 1; i < ring.length; i++) ctx.lineTo(ring[i].x, ring[i].y);
          ctx.closePath();
        }
        ctx.fillStyle = 'rgba(7, 7, 9, 0.78)';
        ctx.fill('evenodd');
        ctx.restore();
      }

      // C-2: storeNodes/nodePixels 개수 불일치 시 해당 프레임 skip
      // (동 전환 직후 storeNodes는 교체되었지만 persona/nodePixels는 300ms 뒤 갱신)
      if (storeNodes.length !== nodePixelsRef.current.length) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      const nodes = nodePixelsRef.current;

      // focusSpot 픽셀 좌표 — 노드 필터(주변 가게만) + persona proximity 두 곳에서 사용.
      // draw 한 번에 1회 계산 (Kakao projection 호출 비용 회피).
      let focusPx: { x: number; y: number } | null = null;
      if (focusSpot && mapInstanceRef.current) {
        const kakao = (window as any).kakao;
        const proj = mapInstanceRef.current.getProjection?.();
        if (proj && kakao?.maps?.LatLng) {
          const latLng = new kakao.maps.LatLng(focusSpot.lat, focusSpot.lon);
          const px = proj.containerPointFromCoords(latLng);
          focusPx = { x: px.x, y: px.y };
        }
      }
      const FOCUS_R2 = 35 * 35; // persona 강조용 35px (squared)
      // 공실스팟 주변 가게만 표시 — focusSpot 있을 때 반경 NEAR_RADIUS_PX 밖 노드는 숨김.
      // 250px ≈ 마포 줌레벨 6 기준 ~600m. 사용자: "공실스팟 주변의 가게만 보여줘"
      const NEAR_RADIUS_PX = 250;
      const NEAR_R2 = NEAR_RADIUS_PX * NEAR_RADIUS_PX;

      // 현재 체류 중 에이전트 집계 (waitTicks > 0 = 매장 이용 중)
      spotStatsRef.current.forEach((s) => {
        s.currentAgents = 0;
      });
      personasRef.current.forEach((p) => {
        if (p.waitTicks > 0 && spotStatsRef.current[p.targetIdx]) {
          spotStatsRef.current[p.targetIdx].currentAgents++;
        }
      });

      // 상권 노드 그리기 — 상점만(지하철역 제외) + focusSpot 반경 내만.
      // 사용자 피드백: 노드 간 파란 연결선 제거, 지하철 픽토그램 제거, 멀리 있는 가게 숨김.
      nodes.forEach((np, idx) => {
        const node = storeNodes[idx];
        if (!node) return;

        // 지하철역(tier S 또는 id 'subway-' 접두) 은 마커/라벨 모두 숨김.
        // 단, 에이전트 routine 의 hub idx 로는 여전히 사용 (sourceIdx).
        const isSubway = node.id.startsWith('subway-') || node.tier === 'S';
        if (isSubway) return;

        // focusSpot 있으면 반경 NEAR_RADIUS_PX 밖 노드는 숨김 — "주변 가게만" 의도.
        if (focusPx) {
          const dxN = np.x - focusPx.x;
          const dyN = np.y - focusPx.y;
          if (dxN * dxN + dyN * dyN > NEAR_R2) return;
        }

        // 최근 30 tick 이내 결제 여부 (테두리만 gold 강조)
        const recentPay = paymentEffectsRef.current.some(
          (e) => e.nodeIdx === idx && tickRef.current - e.startTick < 30,
        );

        // 경쟁업체(comp_ 접두) 는 작은 dot — 사용자 피드백: 집모양 너무 큼.
        // 일반 마포 상점 / 공실 후보는 그대로 집 모양 유지.
        const isCompetitor = node.id.startsWith('comp_');
        if (isCompetitor) {
          // 작은 4px dot — 보라 (vacancy 빨강과 구분)
          const dotColor = recentPay ? '#FBBF24' : '#A78BFA';
          ctx.save();
          ctx.shadowColor = 'rgba(167, 139, 250, 0.85)';
          ctx.shadowBlur = 6;
          ctx.fillStyle = dotColor;
          ctx.beginPath();
          ctx.arc(np.x, np.y, 4, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
          ctx.strokeStyle = 'rgba(255,255,255,0.85)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(np.x, np.y, 4, 0, Math.PI * 2);
          ctx.stroke();
          // 라벨 생략 (경쟁업체 다수면 산만 → 호버 시만 적정)
          return;
        }

        // 상점: 집 모양 (26×22)
        const ringColor = recentPay ? '#FBBF24' : 'rgba(255,255,255,0.8)';
        const lineWidth = recentPay ? 2.5 : 1.5;
        drawStoreHouse(ctx, np.x, np.y, node.tier, ringColor, lineWidth);

        // 라벨 — 11px + 반투명 박스 (가독성). 상점만 표시되므로 offset 11px 고정.
        const labelY = np.y + 11 + 14;
        ctx.font = 'bold 11px monospace';
        ctx.textAlign = 'center';
        const textW = ctx.measureText(node.label).width;
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        ctx.beginPath();
        roundedRect(ctx, np.x - textW / 2 - 3, labelY - 10, textW + 6, 14, 3);
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.fillText(node.label, np.x, labelY);

        // 스팟 통계 (누적 매출 · 체류자)
        const stats = spotStatsRef.current[idx];
        if (stats && stats.revenue > 0) {
          // 누적 매출 (gold — 결제 관련만 gold 사용 OK)
          ctx.fillStyle = '#FBBF24';
          ctx.font = 'bold 9px monospace';
          ctx.fillText(
            `\u20A9${Math.round(stats.revenue / 1000)}K \u00B7 ${stats.visits}\u4EF6`,
            np.x,
            labelY + 11,
          );
        } else {
          ctx.fillStyle = node.tier === 'A' ? '#A5B4FC' : '#D1D5DB';
          ctx.font = 'bold 9px monospace';
          ctx.fillText(`Tier ${node.tier}`, np.x, labelY + 11);
        }

        // 현재 체류자 배지 (우상단)
        if (stats && stats.currentAgents > 0) {
          const badgeOffset = 12;
          const bx = np.x + badgeOffset;
          const by = np.y - badgeOffset;
          ctx.fillStyle = '#10B981';
          ctx.beginPath();
          ctx.arc(bx, by, 8, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#000';
          ctx.font = 'bold 9px monospace';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(String(stats.currentAgents), bx, by + 0.5);
          ctx.textBaseline = 'alphabetic';
        }
      });

      // 실제 ABM trajectory — 에이전트별 시간순 경로를 tick 단위로 보간하여 부드럽게 이동 재생
      if (trajectoryPathsRef.current.size > 0 && mapInstanceRef.current) {
        const proj = mapInstanceRef.current.getProjection?.();
        const kakao = (window as any).kakao;
        if (proj && kakao?.maps?.LatLng) {
          // 실시간 4초 = 가상 1시간 (60fps 기준 240 tick/hour).
          // 사용자 피드백: 2초/hour 너무 빠름 → 4초/hour 절반 속도. 하루 전체 ~64초 재생.
          const ticksPerHour = 240;
          const minH = trajectoryMinHourRef.current;
          const maxH = trajectoryMaxHourRef.current;
          const totalHours = Math.max(1, maxH - minH + 1);
          const cycleTicks = totalHours * ticksPerHour;
          // 가상 시간(소수점 포함) — minH 기점 virtualHour ∈ [minH, maxH + 1)
          const phase = (tickRef.current % cycleTicks) / ticksPerHour;
          const virtualHour = minH + phase;
          const displayHour = Math.floor(virtualHour);

          const roleColor: Record<string, string> = {
            resident: '#34D399',
            commuter: '#60A5FA',
            visitor: '#F472B6',
            owner: '#FBBF24',
            ext_commuter: '#22D3EE',
            ext_visitor: '#A78BFA',
          };

          // ─── 히트맵 layer — 헥사 격자 + 네온 글로우 (Orion 스타일 ref) ─────
          // 사용자 피드백: Kakao 위에 hex 가 묻혀 잘 안 보임 → 마포 bbox 다크 오버레이 + source-over.
          // 색 스펙트럼: 어두운 indigo (cool/zero) → indigo → rose (hot).
          // intensity > 0.55 hex 는 네온 글로우 + 카운트 텍스트.
          const dg = densityGridRef.current;
          const hexes = hexGridRef.current;
          if (dg && hexes.length > 0) {
            const hourKey = String(displayHour);
            const cells = dg.hours[hourKey];
            if (Array.isArray(cells) && cells.length === dg.cols * dg.rows) {
              let maxC = dg.max_count ?? 0;
              if (!maxC) {
                for (let i = 0; i < cells.length; i++) if (cells[i] > maxC) maxC = cells[i];
              }
              if (maxC > 0) {
                const HEX_SIZE = 8;
                const hexPath = new Path2D();
                for (let i = 0; i < 6; i++) {
                  const ang = (Math.PI / 3) * i + Math.PI / 6;
                  const px = HEX_SIZE * Math.cos(ang);
                  const py = HEX_SIZE * Math.sin(ang);
                  if (i === 0) hexPath.moveTo(px, py);
                  else hexPath.lineTo(px, py);
                }
                hexPath.closePath();

                // 사용자 피드백: 검은 박스 제거 → bbox 다크 오버레이 삭제. hex 자체 명도 ↑.

                // ② 1차 패스 — ALL hex 그리기 (v=0도 dim 색). source-over 라 카카오 위 선명.
                ctx.save();
                const hotIndices: number[] = [];
                for (let h = 0; h < hexes.length; h++) {
                  const hex = hexes[h];
                  if (
                    hex.x < -HEX_SIZE ||
                    hex.x > W + HEX_SIZE ||
                    hex.y < -HEX_SIZE ||
                    hex.y > H + HEX_SIZE
                  )
                    continue;
                  const v = cells[hex.dr * dg.cols + hex.dc] ?? 0;
                  const intensity = v / maxC; // 0~1
                  let r: number, g: number, b: number, alpha: number;
                  if (v <= 0) {
                    // dim 베이스 hex — 마포 모자이크 윤곽 표시
                    r = 30;
                    g = 27;
                    b = 30;
                    alpha = 0.5;
                  } else {
                    // 색 보간: indigo #818cf8 → rose #f43f5e
                    r = Math.round(129 + (244 - 129) * intensity);
                    g = Math.round(140 + (63 - 140) * intensity);
                    b = Math.round(248 + (94 - 248) * intensity);
                    alpha = 0.55 + 0.4 * intensity; // 0.55 ~ 0.95
                  }
                  ctx.fillStyle = `rgba(${r},${g},${b},${alpha.toFixed(2)})`;
                  ctx.translate(hex.x, hex.y);
                  ctx.fill(hexPath);
                  // hex 외곽선 — 격자 선명도
                  ctx.strokeStyle = 'rgba(0,0,0,0.5)';
                  ctx.lineWidth = 0.6;
                  ctx.stroke(hexPath);
                  ctx.translate(-hex.x, -hex.y);
                  if (intensity > 0.55) hotIndices.push(h);
                }
                ctx.restore();

                // ③ 2차 패스 — hot hex 네온 글로우 + 카운트 텍스트
                if (hotIndices.length > 0) {
                  ctx.save();
                  ctx.shadowColor = 'rgba(244, 63, 94, 0.95)';
                  ctx.shadowBlur = 16;
                  for (const h of hotIndices) {
                    const hex = hexes[h];
                    ctx.fillStyle = 'rgba(244, 63, 94, 0.55)';
                    ctx.translate(hex.x, hex.y);
                    ctx.fill(hexPath);
                    ctx.translate(-hex.x, -hex.y);
                  }
                  ctx.restore();

                  // 카운트 텍스트 — 가장 hot 한 상위 8개 hex 에만 (산만함 방지)
                  // intensity 내림차순 정렬해서 top N
                  const topHot = hotIndices
                    .slice()
                    .sort((a, b) => {
                      const va = cells[hexes[a].dr * dg.cols + hexes[a].dc] ?? 0;
                      const vb = cells[hexes[b].dr * dg.cols + hexes[b].dc] ?? 0;
                      return vb - va;
                    })
                    .slice(0, 8);
                  ctx.save();
                  ctx.font = 'bold 10px monospace';
                  ctx.textAlign = 'center';
                  ctx.textBaseline = 'middle';
                  ctx.fillStyle = '#FEF3C7';
                  ctx.strokeStyle = 'rgba(0,0,0,0.85)';
                  ctx.lineWidth = 2.5;
                  for (const h of topHot) {
                    const hex = hexes[h];
                    const v = cells[hex.dr * dg.cols + hex.dc] ?? 0;
                    const txt = String(v);
                    ctx.strokeText(txt, hex.x, hex.y);
                    ctx.fillText(txt, hex.x, hex.y);
                  }
                  ctx.textBaseline = 'alphabetic';
                  ctx.restore();
                }
              }
            }
          }

          let drawn = 0;
          let tierSDrawn = 0;
          tierSPixelsRef.current = new Map();
          // 자유 드리프트 진폭 — 서울 위도에서 1e-5 ≈ 0.85m. 1.8e-4 ≈ ~16m wandering 반경.
          // 사용자 피드백: "앞뒤로" 보이지 말고 "이리저리" wandering 으로.
          // 1축 perpendicular wobble (직선 양옆 진동) → lat/lon 독립 2축 Lissajous 드리프트.
          const DRIFT_LATLON = 1.8e-4;

          // 마포 polygon hit-test (사용자 피드백: agent 가 hex 안에서만 움직이도록).
          // mapoPolygonsRef 가 비어있으면 마스킹 skip (geo 미로드 시 fallback).
          const mapoPolys = mapoPolygonsRef.current;
          const inMapoLatLon = (lat: number, lon: number): boolean => {
            if (mapoPolys.length === 0) return true;
            for (const p of mapoPolys) {
              const ring = p.ring;
              let inside = false;
              for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
                const xi = ring[i][0],
                  yi = ring[i][1];
                const xj = ring[j][0],
                  yj = ring[j][1];
                const intersect =
                  yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
                if (intersect) inside = !inside;
              }
              if (inside) return true;
            }
            return false;
          };

          trajectoryPathsRef.current.forEach((path, agentId) => {
            if (path.length === 0) return;
            // virtualHour 를 둘러싼 두 waypoint 찾기 (binary search 대신 경로가 짧으므로 linear)
            let prev = path[0];
            let next = path[path.length - 1];
            for (let i = 0; i < path.length - 1; i++) {
              if (path[i].absHour <= virtualHour && path[i + 1].absHour > virtualHour) {
                prev = path[i];
                next = path[i + 1];
                break;
              }
            }
            if (virtualHour <= path[0].absHour) {
              prev = next = path[0];
            } else if (virtualHour >= path[path.length - 1].absHour) {
              prev = next = path[path.length - 1];
            }
            const span = next.absHour - prev.absHour;
            const tRaw =
              span > 0 ? Math.min(1, Math.max(0, (virtualHour - prev.absHour) / span)) : 0;
            // smoothstep ease-in-out — 시간 경계에서 직선 보간 snap 제거.
            const t = tRaw * tRaw * (3 - 2 * tRaw);
            const dLat = next.lat - prev.lat;
            const dLon = next.lon - prev.lon;
            // 개인별 자유 드리프트 — golden-ratio 시드로 phase 분산.
            // lat / lon 독립적으로 다른 주기 sin → 직선 A→B 와 무관한 Lissajous wandering.
            // 같은 hour 정지(span=0) 도 dot 이 한 자리 안에서 흐물흐물 떠도는 효과.
            const seed = (agentId * 0.6180339887) % 1;
            const seed2 = (agentId * 0.7548776662) % 1;
            const tau = Math.PI * 2;
            // 행동 분기 — backend action 필드 (rest/visit/work/move). drift 진폭/색/펄스 차별화.
            // - rest: 정지(드리프트 X) + 회색 dim → "집에서 쉼"
            // - visit: 매장 좌표 펄스 + 빨강 → "방문 결제"
            // - work: 정적 + 초록 steady → "근무"
            // - move: 풀 wandering drift + role 색 → "이동"
            const action = prev.action || 'move';
            // 드리프트 스케일 — rest/work 는 거의 정지, visit 은 작게 떨림, move 는 풀 wander.
            const driftScale =
              action === 'rest' ? 0.05 : action === 'work' ? 0.08 : action === 'visit' ? 0.25 : 1.0;
            // lat 축 — 주기 ~1.4 hour (실시간 ~5.6초). 너무 빠르지 않게 느리게.
            const driftLat = Math.sin(virtualHour * 0.7 + seed * tau) * DRIFT_LATLON * driftScale;
            // lon 축 — 주기 ~2.2 hour. lat 과 frequency 비 무리수 → 반복 X.
            const driftLon =
              Math.cos(virtualHour * 0.45 + seed2 * tau) * DRIFT_LATLON * 1.15 * driftScale;
            // 짧은 ripple — 걸음걸이 미세 흔들림 (~3m, 0.85 hour 주기 → 실시간 ~3.4초)
            const ripple =
              Math.sin(virtualHour * 2.35 + seed * 13) * DRIFT_LATLON * 0.18 * driftScale;
            const lat = prev.lat + dLat * t + driftLat;
            const lon = prev.lon + dLon * t + driftLon + ripple;
            // 마포 polygon 밖이면 dot 안 그림 — agent 가 hex 격자 안에서만 보이도록.
            if (!inMapoLatLon(lat, lon)) return;
            const latLng = new kakao.maps.LatLng(lat, lon);
            const pix = proj.containerPointFromCoords(latLng);
            if (pix.x < -10 || pix.y < -10 || pix.x > W + 10 || pix.y > H + 10) return;

            // action 별 색·alpha — role 색이 base, action 으로 modulate.
            let fill = roleColor[prev.role] || '#E5E7EB';
            let alpha = 1;
            if (action === 'rest') {
              fill = '#9CA3AF'; // gray — 휴식
              alpha = 0.45;
            } else if (action === 'visit') {
              fill = '#E45756'; // red — 매장 방문/결제
              alpha = 1;
            } else if (action === 'work') {
              fill = '#54A24B'; // green — 근무 (정적)
              alpha = 0.85;
            }

            const isTierS = tierSIdsRef.current.has(agentId);
            // 사용자 요청: Tier S 50명만 dot 표시. 나머지(4950 → trajectory 250샘플) 는 히트맵으로만 표현.
            // (heatmap layer 가 위에서 5000 전체 집계 표현)
            if (!isTierS) return;

            ctx.globalAlpha = alpha;
            // Tier S — 노란 테두리 + 큰 dot. 풍선은 forEach 후 별도 패스로 그림 (Z-order).
            tierSPixelsRef.current.set(agentId, { x: pix.x, y: pix.y });
            ctx.fillStyle = fill;
            ctx.beginPath();
            ctx.arc(pix.x, pix.y, 3.2, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#FCD34D'; // 노란 테두리 — Tier S 식별
            ctx.lineWidth = 1.6;
            ctx.beginPath();
            ctx.arc(pix.x, pix.y, 4.2, 0, Math.PI * 2);
            ctx.stroke();
            tierSDrawn++;
            ctx.globalAlpha = 1;
            drawn++;
          });

          // Tier S 풍선 layer — 별도 패스로 dot 위에 그려서 가독성 보장.
          // T4 Step 3: fade in/out (3 tick spawn, 15 tick fade out at end of hour).
          // 매 hour 경계마다 새 thought 가 시작 → tickInHour 0~3 fade-in, 마지막 15 tick fade-out.
          if (tierSPixelsRef.current.size > 0 && thoughtsByAgentRef.current.size > 0) {
            const tickInHour = Math.floor((virtualHour - displayHour) * ticksPerHour);
            const FADE_IN = 3;
            const FADE_OUT_START = ticksPerHour - 15;
            let bubbleAlpha = 1;
            if (tickInHour < FADE_IN) bubbleAlpha = tickInHour / FADE_IN;
            else if (tickInHour >= FADE_OUT_START)
              bubbleAlpha = Math.max(0, 1 - (tickInHour - FADE_OUT_START) / 15);

            if (bubbleAlpha > 0.02) {
              ctx.font = 'bold 11px "Apple SD Gothic Neo", monospace';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              tierSPixelsRef.current.forEach((pix, aid) => {
                const th = thoughtsByAgentRef.current.get(aid)?.get(displayHour);
                if (!th || !th.thought) return;
                const text = th.thought;
                const tw = ctx.measureText(text).width;
                const bx = pix.x;
                const by = pix.y - 18;
                const padX = 6;
                const padY = 4;
                ctx.globalAlpha = bubbleAlpha;
                // 말풍선 박스
                ctx.fillStyle = 'rgba(15,23,42,0.88)';
                ctx.beginPath();
                roundedRect(ctx, bx - tw / 2 - padX, by - 8 - padY, tw + padX * 2, 16 + padY, 5);
                ctx.fill();
                ctx.strokeStyle = '#FCD34D';
                ctx.lineWidth = 1;
                ctx.beginPath();
                roundedRect(ctx, bx - tw / 2 - padX, by - 8 - padY, tw + padX * 2, 16 + padY, 5);
                ctx.stroke();
                // 꼬리
                ctx.fillStyle = 'rgba(15,23,42,0.88)';
                ctx.beginPath();
                ctx.moveTo(bx - 3, by + 4);
                ctx.lineTo(bx + 3, by + 4);
                ctx.lineTo(bx, by + 9);
                ctx.closePath();
                ctx.fill();
                // 텍스트
                ctx.fillStyle = '#FEF3C7';
                ctx.fillText(text, bx, by);
              });
              ctx.globalAlpha = 1;
              ctx.textBaseline = 'alphabetic';
            }
          }

          // displayHour ref 갱신 — 클릭 hit-test 시 PersonaCard 에 전달.
          currentDisplayHourRef.current = displayHour;

          // 좌상단 타임스탬프 배지 — Tier S 활성 시 별도 표시
          const tierSLabel = tierSDrawn > 0 ? ` · ⭐${tierSDrawn}` : '';
          const hourLabel = `ABM ${String(displayHour % 24).padStart(2, '0')}:00 · 실데이터 ${drawn}명${tierSLabel}`;
          ctx.font = 'bold 11px monospace';
          ctx.textAlign = 'left';
          ctx.fillStyle = 'rgba(15,23,42,0.85)';
          const tw2 = ctx.measureText(hourLabel).width;
          roundedRect(ctx, 8, 8, tw2 + 14, 20, 4);
          ctx.fill();
          ctx.fillStyle = '#86EFAC';
          ctx.fillText(hourLabel, 15, 22);
        }
      }

      // focusSpot 별도 렌더 — 선택된 스팟을 "신규 매장" 마커로 단 하나만 표시
      if (focusSpot && mapInstanceRef.current) {
        const proj = mapInstanceRef.current.getProjection?.();
        const kakao = (window as any).kakao;
        if (proj && kakao?.maps?.LatLng) {
          const latLng = new kakao.maps.LatLng(focusSpot.lat, focusSpot.lon);
          const pix = proj.containerPointFromCoords(latLng);
          const fx = pix.x;
          const fy = pix.y;
          // 외곽 링 (cyan 펄스)
          const pulse = 1 + 0.15 * Math.sin(tickRef.current * 0.1);
          ctx.strokeStyle = 'rgba(34,211,238,0.85)';
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.arc(fx, fy, 18 * pulse, 0, Math.PI * 2);
          ctx.stroke();
          // 신규 매장 = green house
          drawStoreHouse(ctx, fx, fy, 'S', '#10B981', 2.5);
          // 라벨
          const label = `NEW · ${focusSpot.label ?? '선택 스팟'}`;
          ctx.font = 'bold 11px monospace';
          ctx.textAlign = 'center';
          const tw = ctx.measureText(label).width;
          ctx.fillStyle = 'rgba(16,185,129,0.92)';
          roundedRect(ctx, fx - tw / 2 - 4, fy + 18, tw + 8, 15, 4);
          ctx.fill();
          ctx.fillStyle = '#0f172a';
          ctx.fillText(label, fx, fy + 29);
        }
      }

      // 결제 bounce 아이콘 (gold 원 + ₩) — 36 tick 선행 애니메이션.
      // focusSpot 모드: 다른 80개 매장의 결제 이펙트는 시각이 너무 산만 → 전부 비활성화.
      // 선택 공실의 visit/결제는 별도 focusSpot 펄스 + 통계 패널로 표시.
      if (focusSpot) {
        paymentBouncesRef.current = [];
        paymentEffectsRef.current = [];
      }
      paymentBouncesRef.current = paymentBouncesRef.current.filter((e) => {
        const age = tickRef.current - e.startTick;
        if (age > 36) return false;
        const np = nodes[e.nodeIdx];
        if (!np) return true;
        drawPaymentBounce(ctx, np.x, np.y - 14, age);
        return true;
      });

      // 결제 이펙트 렌더링 — ring pulse (0~60 tick) + ₩금액 텍스트 (36~126 tick)
      paymentEffectsRef.current = paymentEffectsRef.current.filter((e) => {
        const age = tickRef.current - e.startTick;
        if (age > 130) return false;
        const np = nodes[e.nodeIdx];
        if (!np) return true;

        // 1) Ring pulse (0~60 tick) — 반경 확장 + 투명화
        if (age < 60) {
          const t = age / 60;
          const ringR = 14 + t * 50;
          const ringAlpha = (1 - t) * 0.7;
          ctx.strokeStyle = `rgba(251, 191, 36, ${ringAlpha})`;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(np.x, np.y, ringR, 0, Math.PI * 2);
          ctx.stroke();
        }

        // 2) ₩금액 텍스트 (36~126 tick) — bounce 사라진 뒤 위로 떠오르며 페이드아웃
        const textAge = age - 36;
        if (textAge >= 0 && textAge < 90) {
          const t = textAge / 90;
          const textY = np.y - 22 - t * 30;
          const textAlpha = t < 0.7 ? 1 : 1 - (t - 0.7) / 0.3;
          ctx.fillStyle = `rgba(251, 191, 36, ${textAlpha})`;
          ctx.strokeStyle = `rgba(0, 0, 0, ${textAlpha * 0.6})`;
          ctx.lineWidth = 2;
          ctx.font = 'bold 13px monospace';
          ctx.textAlign = 'center';
          const label = `+\u20A9${e.amount.toLocaleString()}`;
          ctx.strokeText(label, np.x, textY);
          ctx.fillText(label, np.x, textY);
        }
        return true;
      });

      // 페르소나 이동 — bezier fallback (OSRM 캐시 제거 2026-04-28)
      // trajectory 실데이터 있으면 합성 persona 렌더 skip (실데이터 점으로 대체)
      const useRealTrajectory = trajectoryPathsRef.current.size > 0;

      // focusPx / FOCUS_R2 는 draw 시작부에서 hoisted (노드 필터 + persona proximity 공유).

      personasRef.current.forEach((p) => {
        if (nodes.length < 2) return;
        if (useRealTrajectory) return; // 합성 persona 숨김 — 실데이터만 표시

        // C-2: 인덱스 모듈러 클램프 — storeNodes가 줄었을 때 OOB 방지
        if (p.targetIdx >= nodes.length) p.targetIdx = p.targetIdx % nodes.length;
        if (p.sourceIdx >= nodes.length) p.sourceIdx = p.sourceIdx % nodes.length;

        if (p.waitTicks > 0) {
          p.waitTicks--;
          p.action = p.waitTicks > 60 ? 'visit' : p.type === 'owner' ? 'work' : 'rest';
          if (p.waitTicks === 0) {
            // External 에이전트 첫 등장 시 cyan pulse ripple (지하철 도착 연출)
            if (!p.hasSpawned && (p.type === 'ext_commuter' || p.type === 'ext_visitor')) {
              spawnEffectsRef.current.push({
                x: p.x,
                y: p.y,
                startTick: tickRef.current,
              });
              p.hasSpawned = true;
            }
            // 선호 스팟 순열에서 다음 목적지 (개인별 루틴) + 30% 확률로 랜덤
            let nextIdx: number;
            if (Math.random() < 0.3) {
              nextIdx = Math.floor(Math.random() * nodes.length);
            } else {
              // preferredSpots 순환하며 이전 타깃 아닌 것 선택 (노드 감소 시 필터링)
              const validPrefs = p.preferredSpots.filter((idx) => idx < nodes.length);
              if (validPrefs.length === 0) {
                nextIdx = Math.floor(Math.random() * nodes.length);
              } else {
                const curPrefPos = validPrefs.indexOf(p.targetIdx);
                nextIdx = validPrefs[(curPrefPos + 1) % validPrefs.length];
              }
            }
            // C-2: 모듈러 클램프 + OOB fallback
            nextIdx = ((nextIdx % nodes.length) + nodes.length) % nodes.length;
            if (nextIdx === p.targetIdx) nextIdx = (nextIdx + 1) % nodes.length;
            if (!nodes[nextIdx]) return;
            p.sourceIdx = p.targetIdx;
            p.targetIdx = nextIdx;
            // 개인별 랜덤 도착 오프셋 (매번 다른 위치로 접근)
            p.tx = nodes[nextIdx].x + randomBetween(-25, 25);
            p.ty = nodes[nextIdx].y + randomBetween(-25, 25);

            // C-2: waypoint 생성 전 source/target 인덱스 범위 재확인
            if (!nodes[p.sourceIdx] || !nodes[p.targetIdx]) return;

            // OSRM 캐시 제거됨 — 합성 persona 는 항상 bezier fallback.
            {
              p.waypoints = [];
              const sx = p.x;
              const sy = p.y;
              const segDx = p.tx - sx;
              const segDy = p.ty - sy;
              const segLen = Math.hypot(segDx, segDy) || 1;
              const perpX = -segDy / segLen;
              const perpY = segDx / segLen;
              const offset = randomBetween(0.15, 0.35) * segLen * (Math.random() < 0.5 ? 1 : -1);
              p.mx = (sx + p.tx) / 2 + perpX * offset;
              p.my = (sy + p.ty) / 2 + perpY * offset;
              p.progress = 0;
            }
            p.action = 'move';
          }
        } else if (p.waypoints.length >= 2) {
          // 실제 도로 waypoint 따라 걷기
          const cur = p.waypoints[p.waypointIdx];
          const nxt = p.waypoints[p.waypointIdx + 1];
          if (!nxt) {
            p.waitTicks = Math.floor(randomBetween(60, 200) * p.dwellMultiplier);
            const payAmt = randomBetween(3000, 15000);
            p.spend += payAmt;
            // 결제 이펙트 등록
            paymentEffectsRef.current.push({
              nodeIdx: p.targetIdx,
              amount: Math.round(payAmt),
              startTick: tickRef.current,
            });
            paymentBouncesRef.current.push({
              nodeIdx: p.targetIdx,
              startTick: tickRef.current,
            });
            const stats = spotStatsRef.current[p.targetIdx];
            if (stats) {
              stats.visits++;
              stats.revenue += payAmt;
            }
            return;
          }
          const segDx = nxt.x - cur.x;
          const segDy = nxt.y - cur.y;
          const segLen = Math.hypot(segDx, segDy) || 1;

          const remainingSegments = p.waypoints.length - p.waypointIdx - 1;
          const speedFactor = remainingSegments <= 1 ? 0.6 + p.segmentProgress * 0.4 : 1.0;
          p.segmentProgress += (p.speed * speedFactor) / segLen;

          if (p.segmentProgress >= 1) {
            p.waypointIdx++;
            p.segmentProgress = 0;
            if (p.waypointIdx >= p.waypoints.length - 1) {
              p.x = p.waypoints[p.waypoints.length - 1].x;
              p.y = p.waypoints[p.waypoints.length - 1].y;
              p.waitTicks = Math.floor(randomBetween(60, 200) * p.dwellMultiplier);
              const payAmt = randomBetween(3000, 15000);
              p.spend += payAmt;
              paymentEffectsRef.current.push({
                nodeIdx: p.targetIdx,
                amount: Math.round(payAmt),
                startTick: tickRef.current,
              });
              paymentBouncesRef.current.push({
                nodeIdx: p.targetIdx,
                startTick: tickRef.current,
              });
              const stats = spotStatsRef.current[p.targetIdx];
              if (stats) {
                stats.visits++;
                stats.revenue += payAmt;
              }
              return;
            }
          } else {
            const baseX = cur.x + segDx * p.segmentProgress;
            const baseY = cur.y + segDy * p.segmentProgress;
            // 세그먼트 수직 단위 벡터 (lateral 편향 + wobble 방향 공통)
            const wobPerpX = -segDy / segLen;
            const wobPerpY = segDx / segLen;
            // lateral breath — 50초 주기로 좌/우 편향이 유기적으로 부풀었다 줄었다 (직선 보간 깨기).
            const lateralBreath =
              1 + 0.45 * Math.sin(tickRef.current * 0.011 + p.wobblePhase * 0.5);
            const lateralX = wobPerpX * p.lateralOffset * lateralBreath;
            const lateralY = wobPerpY * p.lateralOffset * lateralBreath;
            // 두 주기 합성 — 빠른 걸음걸이 + 느린 흐름. 사용자 피드백: 직선·로봇 같음 → 유기적으로.
            const wobFast = p.wobbleAmp * Math.sin(tickRef.current * 0.22 + p.wobblePhase);
            const wobSlow =
              p.wobbleAmp * 0.8 * Math.sin(tickRef.current * 0.055 + p.wobblePhase * 1.7);
            const wob = wobFast + wobSlow;
            p.x = baseX + lateralX + wobPerpX * wob;
            p.y = baseY + lateralY + wobPerpY * wob;
          }
          p.action = 'move';
        } else {
          // Fallback bezier (경로 없을 때)
          const sx = p.x;
          const sy = p.y;
          const totalApproxLen =
            Math.hypot(p.mx - sx, p.my - sy) + Math.hypot(p.tx - p.mx, p.ty - p.my);
          p.progress = Math.min(1, p.progress + p.speed / Math.max(totalApproxLen, 1));
          const t = p.progress;
          const it = 1 - t;
          p.x = it * it * sx + 2 * it * t * p.mx + t * t * p.tx;
          p.y = it * it * sy + 2 * it * t * p.my + t * t * p.ty;
          p.action = 'move';
          if (p.progress >= 1) {
            p.waitTicks = Math.floor(randomBetween(60, 200) * p.dwellMultiplier);
            const payAmt = randomBetween(3000, 15000);
            p.spend += payAmt;
            paymentEffectsRef.current.push({
              nodeIdx: p.targetIdx,
              amount: Math.round(payAmt),
              startTick: tickRef.current,
            });
            paymentBouncesRef.current.push({
              nodeIdx: p.targetIdx,
              startTick: tickRef.current,
            });
            const stats = spotStatsRef.current[p.targetIdx];
            if (stats) {
              stats.visits++;
              stats.revenue += payAmt;
            }
          }
        }

        const isExternal = p.type === 'ext_commuter' || p.type === 'ext_visitor';

        // External 진입 페이드인 — 차량/지하철 애니메이션 제거 (사용자 피드백: 거슬림).
        // 도착(waitTicks=0) 시점의 cyan ripple 만 유지.
        if (isExternal && !p.hasSpawned && p.waitTicks > 0 && p.entryDuration > 0) {
          const progress = 1 - p.waitTicks / p.entryDuration;
          ctx.globalAlpha = 0.2 + 0.8 * progress;
          ctx.fillStyle = ACTION_COLOR.move;
          const fadeR = 0.8 + progress * 1.2;
          ctx.beginPath();
          ctx.arc(p.x, p.y, fadeR, 0, Math.PI * 2);
          ctx.fill();
          ctx.globalAlpha = 1;
          return;
        }

        // Trail / 화살표 tip / external halo 모두 비활성화 — 5000 agents 성능 + 시각 단순화.
        // (사용자 피드백: 너무 복잡 → dot 만 깔끔히)
        void isExternal;

        // 기본 반경 — 더 작게 (1.0 ~ 2.5). focusSpot 근처 dot 은 1.6× 확대.
        const baseR = 1.0 + Math.min(1.5, Math.sqrt(p.spend / 16000));
        const tierScale = p.tier === 'S' ? 1.3 : p.tier === 'A' ? 1.0 : 0.8;
        let r = baseR * tierScale;

        // focusSpot proximity — 35px 이내 dot 만 빨강 + 사이즈 ↑.
        // 다른 80개 매장에서의 visit 빨간색은 산만 → 일반 색으로 통합.
        let isNearFocus = false;
        if (focusPx) {
          const dxF = p.x - focusPx.x;
          const dyF = p.y - focusPx.y;
          if (dxF * dxF + dyF * dyF < FOCUS_R2) {
            isNearFocus = true;
            r = r * 1.6;
          }
        }

        // Action 별 fill-only 렌더링
        if (isNearFocus) {
          ctx.globalAlpha = 1;
          ctx.fillStyle = ACTION_COLOR.visit; // 빨강 — focusSpot 근처 dot 강조
        } else if (p.action === 'rest') {
          ctx.globalAlpha = 0.4;
          ctx.fillStyle = '#6b7280';
        } else if (p.action === 'work') {
          ctx.globalAlpha = 0.85;
          ctx.fillStyle = '#54A24B';
        } else if (p.action === 'visit') {
          // focusSpot 모드 시 다른 매장 visit 은 단조 색 (빨강 산만 회피)
          ctx.globalAlpha = focusSpot ? 0.7 : 1;
          ctx.fillStyle = focusSpot ? ACTION_COLOR.move : ACTION_COLOR.visit;
        } else {
          ctx.globalAlpha = 1;
          ctx.fillStyle = ACTION_COLOR.move;
        }
        // viewport culling — 화면 밖 dot 은 그리기 skip (5000 forEach 비용 절감).
        // 위치 업데이트는 위에서 이미 끝났으므로 fill 만 안 하면 됨.
        if (p.x < -10 || p.x > W + 10 || p.y < -10 || p.y > H + 10) {
          ctx.globalAlpha = 1;
          return;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      });

      // External 스폰 이펙트 (cyan ripple) — age 0~60 tick
      spawnEffectsRef.current = spawnEffectsRef.current.filter((e) => {
        const age = tickRef.current - e.startTick;
        if (age > 60) return false;
        const t = age / 60;
        // 이중 ring 확장
        for (let k = 0; k < 2; k++) {
          const offset = k * 20;
          const ringR = 6 + t * 55 - offset * (1 - t);
          if (ringR < 0) continue;
          const ringAlpha = (1 - t) * 0.6;
          ctx.strokeStyle = `rgba(6, 182, 212, ${ringAlpha})`;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(e.x, e.y, ringR, 0, Math.PI * 2);
          ctx.stroke();
        }
        return true;
      });

      tickRef.current++;
      if (tickRef.current % 60 === 0) setSimTick((t) => t + 1);

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, [mapLoaded, storeNodes]);

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
            {spotsLoading && (
              <span
                className="text-[10px] font-mono px-2 py-0.5 rounded border text-amber-400 border-amber-500/40 animate-pulse"
                title="행정동 스팟 좌표 로딩 중"
              >
                스팟 로딩...
              </span>
            )}
            {mode === 'vacancy' && (
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  vacancyFetchError
                    ? 'text-rose-400 border-rose-500/40'
                    : vacancyFetching
                      ? 'text-amber-400 border-amber-500/40 animate-pulse'
                      : 'text-violet-300 border-violet-500/40'
                }`}
                title={
                  vacancyFetchError
                    ? `vacancy fetch error: ${vacancyFetchError}`
                    : `vacancy ${vacancyTrajectory.length} traj / ${vacancyVisits.length} visits / ${vacancyStores.length} stores / ${vacancyChats.length} chats${vacancySummary?.visits_per_day ? ' · summary OK' : ''}`
                }
              >
                {vacancyFetchError
                  ? 'VACANCY ERR'
                  : vacancyFetching
                    ? 'VACANCY 로딩...'
                    : 'VACANCY MODE'}
              </span>
            )}
            <span className="text-[10px] text-[#6b7280] font-mono tracking-widest uppercase">
              {mode === 'vacancy' && vacancySpot
                ? `VACANCY PSE · ${vacancySpot.dong}${vacancySpot.category ? ' · ' + vacancySpot.category : ''}`
                : `MAPO BEHAVIORAL SIM · ${targetDistrict}`}
            </span>
          </div>
        </div>

        {/* 맵 + 캔버스 오버레이 레이어 */}
        <div className="flex-1 relative">
          {/* KakaoMap 베이스 레이어 */}
          <div ref={mapContainerRef} className="absolute inset-0" />
          {/* S-2: API 키 없으면 mock 대신 안내 UI로 명시 */}
          {KAKAO_KEY_MISSING && (
            <div className="absolute inset-0 bg-[#1a2535]/95 z-30 flex flex-col items-center justify-center gap-3 p-6 text-center">
              <p className="text-sm font-bold text-amber-300">카카오맵 API 키가 필요합니다</p>
              <p className="text-xs text-[#9ca3af] font-mono leading-relaxed max-w-md">
                .env 에{' '}
                <code className="text-emerald-300">VITE_KAKAO_MAP_API_KEY=&lt;your_key&gt;</code>{' '}
                설정 후 개발 서버를 재시작하세요. 키 없이 mock 모드로는 도보/교통/결제 시각화가
                동작하지 않습니다.
              </p>
            </div>
          )}
          {/* C-3: 스팟 로딩 실패 (1개 이하) — 에이전트 시뮬 비활성 안내 */}
          {!KAKAO_KEY_MISSING && !spotsLoading && storeNodes.length < 2 && (
            <div className="absolute inset-0 bg-[#1a2535]/60 z-30 flex flex-col items-center justify-center gap-3 p-6 text-center pointer-events-none">
              <p className="text-sm font-bold text-amber-300">지도 스팟 로딩 실패</p>
              <p className="text-xs text-[#9ca3af] font-mono leading-relaxed max-w-md">
                {targetDistrict}의 스팟 정보를 불러오지 못했습니다. 에이전트 시뮬레이션이
                비활성화됩니다.
              </p>
              <button
                onClick={() => {
                  setSpotsLoading(true);
                  fetch(`/api/mapo/spots/${encodeURIComponent(targetDistrict)}?limit=4`)
                    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`spots ${r.status}`))))
                    .then((data: { spots?: StoreNode[] }) => {
                      const list =
                        Array.isArray(data.spots) && data.spots.length > 0 ? data.spots : null;
                      setStoreNodes(list ?? [FALLBACK_CENTER]);
                      setSpotsLoading(false);
                    })
                    .catch(() => {
                      setStoreNodes([FALLBACK_CENTER]);
                      setSpotsLoading(false);
                    });
                }}
                className="pointer-events-auto px-3 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/50 text-emerald-300 rounded text-xs font-bold"
              >
                다시 시도
              </button>
            </div>
          )}

          {/* 투명 캔버스 오버레이 — 페르소나 + 노드 (맵 드래그/줌 이벤트는 통과) */}
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full"
            style={{ zIndex: 10, pointerEvents: 'none' }}
          />

          {/* 16 행정동 이름 라벨 — Mapo polygon centroid 위치. */}
          {dongLabels.length > 0 &&
            dongLabels.map((d) => (
              <div
                key={`dong-${d.name}`}
                className="absolute pointer-events-none select-none"
                style={{
                  left: d.x,
                  top: d.y,
                  transform: 'translate(-50%, -50%)',
                  zIndex: 25,
                }}
              >
                <span
                  className="text-[10px] font-black tracking-tight text-white/90 drop-shadow-[0_1px_2px_rgba(0,0,0,0.95)]"
                  style={{
                    textShadow:
                      '0 0 4px rgba(0,0,0,0.95), 0 0 2px rgba(0,0,0,1), 1px 1px 0 rgba(0,0,0,0.8)',
                  }}
                >
                  {d.name}
                </span>
              </div>
            ))}

          {/* Phase 2: 4 거점 floating glassmorphism 카드 (Orion ref). */}
          {keyDongPx.length === KEY_DONGS.length &&
            trajectoryPathsRef.current.size > 0 &&
            keyDongPx.map((pix, idx) => {
              const d = KEY_DONGS[idx];
              // 해당 거점 dong 셀의 density 합 — 시각적으로 visit 카운트 느낌.
              const dg = densityGridRef.current;
              let count = 0;
              if (dg) {
                const [minLat, minLon, maxLat, maxLon] = dg.bbox;
                const dr = Math.floor(((maxLat - d.lat) / (maxLat - minLat)) * dg.rows);
                const dc = Math.floor(((d.lon - minLon) / (maxLon - minLon)) * dg.cols);
                const hourKey = String(currentDisplayHourRef.current);
                const cells = dg.hours[hourKey];
                if (Array.isArray(cells) && dr >= 0 && dr < dg.rows && dc >= 0 && dc < dg.cols) {
                  // 근방 3×3 합산 — 단일 셀 노이즈 완화.
                  for (let rr = Math.max(0, dr - 1); rr <= Math.min(dg.rows - 1, dr + 1); rr++) {
                    for (let cc = Math.max(0, dc - 1); cc <= Math.min(dg.cols - 1, dc + 1); cc++) {
                      count += cells[rr * dg.cols + cc] ?? 0;
                    }
                  }
                }
              }
              return (
                <div
                  key={d.name}
                  className="absolute pointer-events-none"
                  style={{
                    left: pix.x,
                    top: pix.y,
                    transform: 'translate(-50%, calc(-100% - 14px))',
                    zIndex: 30,
                  }}
                >
                  {/* 카드와 hex 잇는 line */}
                  <div
                    className="absolute left-1/2 top-full w-px"
                    style={{
                      height: 14,
                      background: `linear-gradient(to bottom, ${d.color}88, transparent)`,
                      transform: 'translateX(-50%)',
                    }}
                  />
                  <div className="bg-[#111113]/85 backdrop-blur-xl border border-white/10 rounded-2xl px-3 py-2 shadow-2xl flex items-center gap-2 whitespace-nowrap">
                    <div
                      className="w-2.5 h-2.5 rounded-full shrink-0 shadow-[0_0_8px_currentColor]"
                      style={{ backgroundColor: d.color, color: d.color }}
                    />
                    <div className="flex flex-col items-start leading-tight">
                      <span className="text-[8.5px] font-black text-white/55 uppercase tracking-widest">
                        {d.name}
                      </span>
                      <span className="text-xs font-black text-white italic tabular-nums tracking-tighter">
                        {count.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}

          {/* Phase 2: hover 시 우하단 active node 카드. */}
          {hoveredHex && trajectoryPathsRef.current.size > 0 && (
            <div className="absolute bottom-4 right-4 z-30 pointer-events-none">
              <div className="w-56 bg-black/80 backdrop-blur-2xl border border-white/10 rounded-3xl p-5 shadow-[0_30px_60px_rgba(0,0,0,0.8)]">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                  <span className="text-[9px] font-black text-stone-400 uppercase tracking-widest">
                    Active Node Analysis
                  </span>
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-end">
                    <span className="text-[10px] font-bold text-stone-500 uppercase">Density</span>
                    <span className="text-xl font-black text-white italic tabular-nums">
                      {(hoveredHex.intensity * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full h-1 bg-stone-900 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-rose-500 shadow-[0_0_10px_#f43f5e]"
                      style={{ width: `${(hoveredHex.intensity * 100).toFixed(0)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] font-bold uppercase">
                    <span className="text-stone-600">Agents</span>
                    <span className="text-white font-black tabular-nums">
                      {hoveredHex.count.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* mode='vacancy' + vacancySpot — 빨간 펄스 마커 + 반경 500m 원 */}
          {mode === 'vacancy' && vacancySpot && mapLoaded && mapInstanceRef.current && (
            <VacancySpotMarker
              map={mapInstanceRef.current}
              lat={vacancySpot.lat}
              lng={vacancySpot.lng}
            />
          )}

          {/* mode='vacancy' — 우측 상단 사이드 패널 (매출/방문 통계) */}
          {mode === 'vacancy' && vacancySpot && (
            <div className="absolute top-4 right-4 z-20">
              <VacancyStatsPanel
                summary={vacancySummary}
                vacancySpot={vacancySpot}
                loading={vacancyFetching || (!vacancySummary && !vacancyFetchError)}
              />
            </div>
          )}

          {/* 하단 — 결과 통계 or 실행 버튼 */}
          <div className="absolute bottom-4 left-0 right-0 px-4 z-20 flex flex-col items-center gap-3">
            {abmResult ? (
              <div className="w-full max-w-2xl flex flex-col gap-2">
                {/* 메인 지표 4칸 */}
                <div className="bg-[#0d1117]/90 backdrop-blur-sm border border-emerald-500/30 rounded-xl p-3 grid grid-cols-4 gap-3">
                  <div className="text-center">
                    <p className="text-[9px] font-mono text-[#6b7280] uppercase mb-0.5">일 방문</p>
                    <p className="text-lg font-black text-emerald-300">
                      {abmResult.daily_visits_mean?.toLocaleString() ?? '-'}
                      <span className="text-[10px] text-[#6b7280] ml-0.5">회</span>
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
                      {abmResult.peak_hours && abmResult.peak_hours.length > 0
                        ? abmResult.peak_hours
                            .slice(0, 3)
                            .map((h: any) => `${h}시`)
                            .join('·')
                        : '-'}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-[9px] font-mono text-[#6b7280] uppercase mb-0.5">에이전트</p>
                    <p className="text-lg font-black text-emerald-300">
                      {abmResult.n_personas ?? '-'}
                      <span className="text-[10px] text-[#6b7280] ml-0.5">명</span>
                    </p>
                    <p className="text-[9px] text-[#6b7280]">LLM 11회</p>
                  </div>
                </div>

                {/* 페르소나 분포 (customer_profile_dist) */}
                {abmResult.customer_profile_dist &&
                  Object.keys(abmResult.customer_profile_dist).length > 0 && (
                    <div className="bg-[#0d1117]/90 backdrop-blur-sm border border-[#3a3633] rounded-xl p-3">
                      <p className="text-[9px] font-mono text-[#6b7280] uppercase mb-2">
                        페르소나 방문 분포
                      </p>
                      <div className="flex gap-1.5 items-end h-10">
                        {Object.entries(abmResult.customer_profile_dist as Record<string, number>)
                          .sort((a, b) => b[1] - a[1])
                          .map(([role, ratio]) => {
                            const pct = Math.round(ratio * 100);
                            const label =
                              role === 'resident'
                                ? '거주'
                                : role === 'commuter'
                                  ? '통근'
                                  : role === 'visitor'
                                    ? '방문'
                                    : role === 'owner'
                                      ? '점주'
                                      : role === 'ext_commuter'
                                        ? '외부통근'
                                        : role === 'ext_visitor'
                                          ? '외부방문'
                                          : role;
                            return (
                              <div key={role} className="flex-1 flex flex-col items-center gap-0.5">
                                <span className="text-[9px] font-bold text-emerald-300">
                                  {pct}%
                                </span>
                                <div
                                  className="w-full bg-emerald-500/40 rounded-sm transition-all"
                                  style={{ height: `${Math.max(4, pct * 0.8)}px` }}
                                />
                                <span className="text-[8px] text-[#6b7280]">{label}</span>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  )}

                {/* 신규 매장 진입 시 잠식 효과 */}
                {abmResult.cannibalization && abmResult.cannibalization.target_dong && (
                  <div className="bg-[#0d1117]/90 backdrop-blur-sm border border-rose-500/30 rounded-xl p-3 flex items-center gap-3">
                    <div>
                      <p className="text-[9px] font-mono text-rose-400 uppercase mb-0.5">
                        기존 매장 잠식 (반경 {abmResult.cannibalization.cannibalize_radius_m}m)
                      </p>
                      <p className="text-[11px] text-[#9ca3af]">
                        <span className="text-rose-300 font-bold">
                          {abmResult.cannibalization.target_dong}
                        </span>{' '}
                        내 영향권 매장{' '}
                        <span className="text-rose-300 font-bold">
                          {abmResult.cannibalization.affected_stores}
                        </span>
                        개 · 예상 매출 감소{' '}
                        <span className="text-rose-300 font-bold">
                          {abmResult.cannibalization.estimated_impact_pct}%
                        </span>
                      </p>
                    </div>
                  </div>
                )}
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
                        className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all border flex items-center gap-1.5 ${
                          scenario.weather_override === w
                            ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-300'
                            : 'border-[#3a3633] text-[#6b7280] hover:text-[#9ca3af] hover:border-[#4a4643]'
                        }`}
                      >
                        {w === null ? (
                          '현재날씨'
                        ) : w === '맑음' ? (
                          <>
                            <svg
                              width="18"
                              height="14"
                              viewBox="0 0 18 14"
                              aria-hidden="true"
                              className="shrink-0"
                            >
                              <circle cx="9" cy="7" r="3.2" fill="#FBBF24" />
                              <g stroke="#FBBF24" strokeWidth="1.3" strokeLinecap="round">
                                <line x1="9" y1="1" x2="9" y2="2.6" />
                                <line x1="9" y1="11.4" x2="9" y2="13" />
                                <line x1="1" y1="7" x2="2.6" y2="7" />
                                <line x1="15.4" y1="7" x2="17" y2="7" />
                                <line x1="3" y1="1.5" x2="4.2" y2="2.7" />
                                <line x1="13.8" y1="11.3" x2="15" y2="12.5" />
                                <line x1="3" y1="12.5" x2="4.2" y2="11.3" />
                                <line x1="13.8" y1="2.7" x2="15" y2="1.5" />
                              </g>
                            </svg>
                            맑음
                          </>
                        ) : w === '비' ? (
                          <>
                            <svg
                              width="20"
                              height="14"
                              viewBox="0 0 20 14"
                              aria-hidden="true"
                              className="shrink-0"
                            >
                              <path
                                d="M4.5 7.5 a3 3 0 0 1 0.3 -5.9 a4 4 0 0 1 7.6 0.4 a2.8 2.8 0 0 1 3.6 4.5 a2.5 2.5 0 0 1 -1.8 0.7 Z"
                                fill="#9CA3AF"
                                stroke="#D1D5DB"
                                strokeWidth="0.7"
                              />
                              <g stroke="#60A5FA" strokeWidth="1.3" strokeLinecap="round">
                                <line x1="6" y1="9.5" x2="5" y2="12.5" />
                                <line x1="10" y1="9.5" x2="9" y2="12.5" />
                                <line x1="14" y1="9.5" x2="13" y2="12.5" />
                              </g>
                            </svg>
                            비
                          </>
                        ) : (
                          <>
                            <svg
                              width="16"
                              height="14"
                              viewBox="0 0 16 14"
                              aria-hidden="true"
                              className="shrink-0"
                            >
                              <g
                                stroke="#BFDBFE"
                                strokeWidth="1.2"
                                strokeLinecap="round"
                                fill="none"
                              >
                                <line x1="8" y1="1.5" x2="8" y2="12.5" />
                                <line x1="2.7" y1="4" x2="13.3" y2="10" />
                                <line x1="2.7" y1="10" x2="13.3" y2="4" />
                                <line x1="6" y1="2.5" x2="8" y2="3.5" />
                                <line x1="10" y1="2.5" x2="8" y2="3.5" />
                                <line x1="6" y1="11.5" x2="8" y2="10.5" />
                                <line x1="10" y1="11.5" x2="8" y2="10.5" />
                              </g>
                              <circle cx="8" cy="7" r="1.2" fill="#E0F2FE" />
                            </svg>
                            눈
                          </>
                        )}
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

          {/* 공실 스팟 선택 패널 — vacancySpots 받았을 때만 표시 + 결과 없을 때만 */}
          {Array.isArray(vacancySpots) &&
            vacancySpots.length > 0 &&
            !abmResult?.new_store_visit_share_pct && (
              <div className="absolute top-3 right-3 max-w-[260px] bg-[#0d1117]/95 backdrop-blur-sm border border-emerald-500/40 rounded-lg p-3 z-20 shadow-[0_0_20px_rgba(52,211,153,0.15)]">
                <p className="text-[10px] font-mono text-emerald-400 mb-2 uppercase tracking-wider">
                  공실 스팟 ({vacancySpots.length})
                </p>
                <p className="text-[10px] text-[#6b7280] mb-2 leading-relaxed">
                  스팟 클릭 → 그 위치에서 ABM 시뮬 실행
                </p>
                <div className="flex flex-col gap-1.5 max-h-[280px] overflow-y-auto">
                  {[...vacancySpots]
                    .sort((a, b) => (b.listing_count ?? 0) - (a.listing_count ?? 0))
                    .slice(0, 8)
                    .map((spot, idx) => {
                      const isTarget = spot.dong_name === targetDistrict;
                      return (
                        <button
                          key={`spot-${spot.id}`}
                          onClick={() => onSpotClick?.(spot)}
                          disabled={abmLoading || !onSpotClick}
                          className={`text-left px-2 py-1.5 rounded text-[11px] border transition-all ${
                            isTarget
                              ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/20'
                              : 'bg-[#1a1815]/60 border-[#3a3633] text-[#9ca3af] hover:border-[#4a4643]'
                          } ${abmLoading ? 'opacity-50 cursor-wait' : 'cursor-pointer'}`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold">
                              {idx + 1}. {spot.dong_name}
                            </span>
                            <span className="text-[9px] font-mono text-[#6b7280]">
                              {spot.listing_count ?? 0}건
                            </span>
                          </div>
                          <div className="text-[9px] text-[#6b7280] mt-0.5 font-mono">
                            {spot.lat.toFixed(4)}, {spot.lon.toFixed(4)}
                          </div>
                        </button>
                      );
                    })}
                </div>
              </div>
            )}

          {/* 시뮬 결과 오버레이 — new_store_visit_share_pct 가 있을 때 (스팟 클릭 시뮬 후) */}
          {abmResult &&
            (abmResult.new_store_visit_share_pct > 0 || abmResult.new_store_visits > 0) && (
              <div className="absolute top-3 right-3 w-[300px] bg-[#0d1117]/95 backdrop-blur-md border border-emerald-500/60 rounded-lg p-4 z-30 shadow-[0_0_30px_rgba(52,211,153,0.25)]">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-[10px] font-mono text-emerald-400 uppercase tracking-wider">
                    스팟 시뮬 결과
                    {abmResult.cached && (
                      <span className="ml-1.5 text-[8px] text-cyan-400 normal-case">(cached)</span>
                    )}
                  </p>
                  <button
                    onClick={() => onClearResult?.()}
                    className="text-[10px] px-2 py-1 rounded border border-[#3a3633] text-[#9ca3af] hover:text-white hover:border-emerald-500/60 transition-all"
                  >
                    ← 뒤로
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2 mb-3">
                  <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-2">
                    <p className="text-[9px] text-emerald-300 mb-1">방문 점유율</p>
                    <p className="text-lg font-bold text-emerald-200">
                      {abmResult.new_store_visit_share_pct?.toFixed(2) ?? '0.00'}%
                    </p>
                    <p className="text-[8px] text-[#6b7280] mt-0.5">마포 전체 방문 중</p>
                  </div>
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded p-2">
                    <p className="text-[9px] text-amber-300 mb-1">일 매출</p>
                    <p className="text-lg font-bold text-amber-200">
                      {Math.round(abmResult.new_store_revenue ?? 0).toLocaleString()}원
                    </p>
                    <p className="text-[8px] text-[#6b7280] mt-0.5">
                      방문 {abmResult.new_store_visits ?? 0}회
                    </p>
                  </div>
                </div>
                <div className="text-[10px] text-[#9ca3af] border-t border-[#3a3633] pt-2 leading-relaxed">
                  <p className="mb-1">
                    <span className="text-[#6b7280]">대상 동:</span>{' '}
                    <span className="text-[#e5e7eb] font-bold">{targetDistrict}</span>
                  </p>
                  <p className="mb-1">
                    <span className="text-[#6b7280]">전체 일 매출:</span>{' '}
                    <span className="text-[#e5e7eb]">
                      {Math.round(abmResult.total_daily_revenue ?? 0).toLocaleString()}원
                    </span>
                  </p>
                  <p>
                    <span className="text-[#6b7280]">월 추정:</span>{' '}
                    <span className="text-[#e5e7eb]">
                      {Math.round(abmResult.monthly_revenue_estimate ?? 0).toLocaleString()}원
                    </span>
                  </p>
                </div>
              </div>
            )}

          {/* Narrator 요약 — 결과 오버레이 활성 시에는 숨김 */}
          {abmResult?.narrator_summary && !abmResult?.new_store_visit_share_pct && (
            <div className="absolute top-3 right-3 max-w-xs bg-[#0d1117]/90 backdrop-blur-sm border border-[#3a3633] rounded-lg p-3 z-20">
              <p className="text-[10px] font-mono text-emerald-400 mb-1 uppercase tracking-wider">
                Narrator
              </p>
              <p className="text-[11px] text-[#9ca3af] leading-relaxed">
                {abmResult.narrator_summary}
              </p>
            </div>
          )}

          {/* 통합 범례 — 스팟 / Action / Tier / External (4섹션 한 박스) */}
          <div className="absolute top-3 left-3 bg-[#0d1117]/80 backdrop-blur-sm border border-[#3a3633] rounded-lg p-2.5 z-20 w-[200px]">
            <p className="text-[9px] font-mono text-emerald-400 mb-1.5 uppercase tracking-wider">
              Legend
            </p>
            {/* 섹션 1 — 스팟 */}
            <p className="text-[8px] font-mono text-[#6b7280] mb-1">SPOT</p>
            <div className="flex flex-col gap-1 mb-2 text-[10px]">
              <div className="flex items-center gap-2">
                {/* 지하철역 이중원 + T */}
                <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
                  <circle cx="10" cy="10" r="9" fill="#ECFEFF" stroke="#0891B2" strokeWidth="1.8" />
                  <circle cx="10" cy="10" r="6.5" fill="none" stroke="#0891B2" strokeWidth="0.8" />
                  <path
                    d="M 6.5 7.3 H 13.5 M 10 7.3 V 13.2"
                    stroke="#0F172A"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
                <span className="text-[#9ca3af]">지하철역</span>
              </div>
              <div className="flex items-center gap-2">
                {/* 상점 집 모양 */}
                <svg width="22" height="20" viewBox="0 0 22 20" aria-hidden="true">
                  <polygon points="11,2 20,9 2,9" fill="#818CF8" />
                  <rect x="3" y="9" width="16" height="9" fill="#4F46E5" />
                  <rect x="6" y="11" width="3" height="3" fill="#818CF8" />
                  <rect x="13" y="11" width="3" height="3" fill="#818CF8" />
                  <rect x="9" y="14" width="4" height="4" fill="#1F2937" />
                </svg>
                <span className="text-[#9ca3af]">상점</span>
              </div>
            </div>
            <div className="border-t border-[#3a3633] my-1.5" />

            {/* 섹션 2 — Action */}
            <p className="text-[8px] font-mono text-[#6b7280] mb-1">AGENT ACTION</p>
            <div className="grid grid-cols-2 gap-x-2 gap-y-1 mb-2 text-[9px]">
              <span className="flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                  <circle cx="6" cy="6" r="5" fill="#E45756" stroke="#FFFFFF" strokeWidth="1.5" />
                </svg>
                <span className="text-[#fca5a5]">방문</span>
              </span>
              <span className="flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                  <circle cx="6" cy="6" r="5" fill="#4C78A8" stroke="#FFFFFF" strokeWidth="1.5" />
                </svg>
                <span className="text-[#93c5fd]">이동</span>
              </span>
              <span className="flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                  <circle cx="6" cy="6" r="4.5" fill="none" stroke="#54A24B" strokeWidth="2" />
                </svg>
                <span className="text-[#86efac]">근무</span>
              </span>
              <span className="flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                  <circle cx="6" cy="6" r="5" fill="#6b7280" fillOpacity="0.4" />
                </svg>
                <span className="text-[#9ca3af]">휴식</span>
              </span>
            </div>
            <div className="border-t border-[#3a3633] my-1.5" />

            {/* 섹션 3 — Tier (크기로 표현) */}
            <p className="text-[8px] font-mono text-[#6b7280] mb-1">TIER (크기)</p>
            <div className="flex items-center gap-3 mb-2 text-[9px]">
              <span className="flex items-center gap-1">
                <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                  <circle cx="8" cy="8" r="7" fill="#4C78A8" stroke="#FFFFFF" strokeWidth="2.5" />
                </svg>
                <span className="text-white">S</span>
              </span>
              <span className="flex items-center gap-1">
                <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                  <circle cx="7" cy="7" r="6" fill="#4C78A8" stroke="#FFFFFF" strokeWidth="1.8" />
                </svg>
                <span className="text-white">A</span>
              </span>
              <span className="flex items-center gap-1">
                <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                  <circle cx="6" cy="6" r="5" fill="#4C78A8" stroke="#FFFFFF" strokeWidth="1.2" />
                </svg>
                <span className="text-white">B</span>
              </span>
            </div>
            <div className="border-t border-[#3a3633] my-1.5" />

            {/* 섹션 4 — External */}
            <p className="text-[8px] font-mono text-[#6b7280] mb-1">EXTERNAL</p>
            <div className="flex items-center gap-2 text-[9px]">
              <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
                <defs>
                  <radialGradient id="extHalo" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="#06B6D4" stopOpacity="0.55" />
                    <stop offset="100%" stopColor="#06B6D4" stopOpacity="0" />
                  </radialGradient>
                </defs>
                <circle cx="11" cy="11" r="10" fill="url(#extHalo)" />
                <circle cx="11" cy="11" r="4.5" fill="#4C78A8" stroke="#FFFFFF" strokeWidth="1.5" />
              </svg>
              <span className="text-cyan-300">외부 유입 (cyan halo)</span>
            </div>
            <p className="text-[8px] text-[#6b7280] mt-1.5 leading-tight">
              크기 = 누적 지출 · 결제 시 gold 링/텍스트
            </p>
          </div>
        </div>
      </div>

      {/* Tier S 페르소나 카드 모달 — Tier S dot 클릭 시 표시 (plan T5).
          onPersonaClick prop 가 있으면 부모가 모달 처리하므로 여기 렌더 X. */}
      {selectedPersona && !onPersonaClick && (
        <PersonaCard
          data={selectedPersona}
          onClose={() => setSelectedPersona(null)}
          currentHour={currentDisplayHourRef.current % 24}
        />
      )}
    </div>
  );
}
