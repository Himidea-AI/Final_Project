import { useEffect, useRef, useState, useCallback } from 'react';
import { Activity, Play } from 'lucide-react';

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
  // External 전용 — 차량/지하철 진입 애니메이션
  entryStartX: number;
  entryStartY: number;
  entryDuration: number; // 초기 waitTicks 값 (진행률 계산용)
  entryMode: 'subway' | 'car';
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

// OSRM 공개 도보 라우팅 API (OpenStreetMap 기반, CORS OK)
async function fetchWalkingRoute(
  fromLat: number,
  fromLng: number,
  toLat: number,
  toLng: number,
  signal?: AbortSignal,
): Promise<[number, number][]> {
  try {
    const url = `https://router.project-osrm.org/route/v1/foot/${fromLng},${fromLat};${toLng},${toLat}?overview=full&geometries=geojson`;
    const r = await fetch(url, { signal });
    if (!r.ok) throw new Error('OSRM fetch failed');
    const data = await r.json();
    const coords = data?.routes?.[0]?.geometry?.coordinates;
    if (!Array.isArray(coords)) throw new Error('No route geometry');
    // OSRM: [lng, lat] → [lat, lng]로 변환
    return coords.map((c: [number, number]) => [c[1], c[0]]);
  } catch (e: any) {
    if (e?.name === 'AbortError') throw e;
    // 실패 시 직선 fallback — 시작/끝 2점만
    return [
      [fromLat, fromLng],
      [toLat, toLng],
    ];
  }
}

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

// 지하철 차량 — 진행 방향으로 회전한 실루엣 (본체 + 창문 2개 + 앞유리)
function drawSubwayCar(ctx: CanvasRenderingContext2D, cx: number, cy: number, heading: number) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(heading);
  // 본체 — cyan 계열
  ctx.fillStyle = '#0891B2';
  ctx.strokeStyle = '#67E8F9';
  ctx.lineWidth = 1;
  const w = 22;
  const h = 10;
  ctx.beginPath();
  roundedRect(ctx, -w / 2, -h / 2, w, h, 3);
  ctx.fill();
  ctx.stroke();
  // 창문 2개 — 흰색
  ctx.fillStyle = '#ECFEFF';
  ctx.fillRect(-w / 2 + 4, -h / 2 + 2, 5, h - 4);
  ctx.fillRect(-w / 2 + 11, -h / 2 + 2, 5, h - 4);
  // 앞유리 — 진행 방향 쪽 밝게
  ctx.fillStyle = '#FDE68A';
  ctx.fillRect(w / 2 - 3, -h / 2 + 2, 2, h - 4);
  // 바퀴 2개 — 어두운 원
  ctx.fillStyle = '#1F2937';
  ctx.beginPath();
  ctx.arc(-w / 2 + 5, h / 2 + 1, 1.8, 0, Math.PI * 2);
  ctx.arc(w / 2 - 5, h / 2 + 1, 1.8, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

// 지하철역 픽토그램 — 이중 원 + 중앙 T 심볼 (국제 지하철 표준 스타일)
function drawSubwayStation(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  ringColor: string,
  lineWidth: number,
) {
  const outerR = 15;
  const innerR = 11;
  // 바깥 채움 (배경)
  ctx.fillStyle = '#ECFEFF';
  ctx.beginPath();
  ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
  ctx.fill();
  // 바깥 테두리
  ctx.strokeStyle = ringColor;
  ctx.lineWidth = lineWidth;
  ctx.beginPath();
  ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
  ctx.stroke();
  // 안쪽 얇은 원
  ctx.strokeStyle = '#0891B2';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
  ctx.stroke();
  // T 심볼 (둥근 선)
  ctx.strokeStyle = '#0F172A';
  ctx.lineWidth = 2.4;
  ctx.lineCap = 'round';
  ctx.beginPath();
  // 가로 획
  ctx.moveTo(cx - 5.5, cy - 4.5);
  ctx.lineTo(cx + 5.5, cy - 4.5);
  // 세로 획
  ctx.moveTo(cx, cy - 4.5);
  ctx.lineTo(cx, cy + 5.2);
  ctx.stroke();
  ctx.lineCap = 'butt';
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

// 택시/자가용 — 진행 방향으로 회전한 실루엣 (본체 + 앞유리 + 루프사인 + 바퀴)
function drawTaxi(ctx: CanvasRenderingContext2D, cx: number, cy: number, heading: number) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(heading);
  // 본체 — amber 계열
  ctx.fillStyle = '#B45309';
  ctx.strokeStyle = '#FDE68A';
  ctx.lineWidth = 1;
  const w = 16;
  const h = 8;
  ctx.beginPath();
  roundedRect(ctx, -w / 2, -h / 2, w, h, 2);
  ctx.fill();
  ctx.stroke();
  // 앞유리 (진행 방향)
  ctx.fillStyle = '#FEF3C7';
  ctx.fillRect(1, -h / 2 + 1.5, 5, h - 3);
  // 루프사인 — 택시 표식
  ctx.fillStyle = '#FBBF24';
  ctx.fillRect(-2, -h / 2 - 2, 4, 2);
  // 바퀴 2개
  ctx.fillStyle = '#111827';
  ctx.beginPath();
  ctx.arc(-w / 2 + 3, h / 2, 1.6, 0, Math.PI * 2);
  ctx.arc(w / 2 - 3, h / 2, 1.6, 0, Math.PI * 2);
  ctx.fill();
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
}: AbmPersonaMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const personasRef = useRef<Persona[]>([]);
  const nodePixelsRef = useRef<PixelCoord[]>([]);
  const rafRef = useRef<number>(0);
  const tickRef = useRef(0);
  // OSRM 도보 경로 캐시 — key: "fromIdx-toIdx", value: [[lat,lng],...]
  const routeCacheRef = useRef<Record<string, [number, number][]>>({});
  const [routesLoaded, setRoutesLoaded] = useState(false);

  // 결제 이펙트 (ring pulse + ₩ 텍스트) — tick 기반 애니메이션
  const paymentEffectsRef = useRef<{ nodeIdx: number; amount: number; startTick: number }[]>([]);
  // 결제 bounce 아이콘 (₩ 원 튀어오름) — 36 tick (0.6초) 선행 애니메이션
  const paymentBouncesRef = useRef<{ nodeIdx: number; startTick: number }[]>([]);
  // 스팟별 통계 (실시간 누적) — draw 루프에서 집계
  const spotStatsRef = useRef<{ visits: number; revenue: number; currentAgents: number }[]>([]);
  // External 스폰 이펙트 (역 출구 cyan pulse) — 지하철/버스 도착 연출
  const spawnEffectsRef = useRef<{ x: number; y: number; startTick: number }[]>([]);
  // 실제 ABM trajectory — 에이전트별 시간순 경로 (백엔드 실시뮬 결과).
  // agent_id → [{absHour, lat, lon, role}, ...] (시간 순 정렬). 보간해서 부드럽게 이동.
  const trajectoryPathsRef = useRef<
    Map<number, { absHour: number; lat: number; lon: number; role: string }[]>
  >(new Map());
  const trajectoryMinHourRef = useRef(0);
  const trajectoryMaxHourRef = useRef(0);

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
      { absHour: number; lat: number; lon: number; role: string }[]
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
      byAgent.get(aid)!.push({
        absHour,
        lat: Number(e.lat),
        lon: Number(e.lon),
        role: String(e.role || 'resident'),
      });
    }
    // 각 에이전트 경로를 absHour 기준 정렬
    byAgent.forEach((path) => path.sort((a, b) => a.absHour - b.absHour));
    trajectoryPathsRef.current = byAgent;
    trajectoryMinHourRef.current = isFinite(minHour) ? minHour : 0;
    trajectoryMaxHourRef.current = isFinite(maxHour) ? maxHour : 0;
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

    // mode='general' (default) — 기존 동작 유지 (회귀 X)
    // 마포구 전체 유동인구 시각화 — 16개 동의 지하철역 + 대표 상점 POI 를 routine 노드로 사용.
    // 공실(vacancySpots) 은 "비어있는 부동산" 이라 에이전트 목적지로 부적절 → focusSpot 으로 별도 표시만.
    let cancelled = false;
    setSpotsLoading(true);
    fetch(`/api/mapo/spots-all?per_dong=3`)
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
  }, [mode, vacancyJobId, targetDistrict]);

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

    const W = canvas.width;
    const H = canvas.height;

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

      // External 차량 진입 시작점 — 허브에서 가장 가까운 canvas edge
      let entryStartX = sx;
      let entryStartY = sy;
      let entryMode: 'subway' | 'car' = 'subway';
      let initialWait = isExternal
        ? Math.floor(randomBetween(60, 180))
        : Math.floor(randomBetween(0, 180));
      if (isExternal) {
        const hubNode = storeNodes[sourceIdx];
        const isSubwayHub = !!hubNode && (hubNode.id.startsWith('subway-') || hubNode.tier === 'S');
        entryMode = isSubwayHub ? 'subway' : 'car';
        // 허브에서 가장 가까운 edge 방향 (직선거리)
        const distTop = sy;
        const distBot = H - sy;
        const distLeft = sx;
        const distRight = W - sx;
        const minD = Math.min(distTop, distBot, distLeft, distRight);
        if (minD === distTop) {
          entryStartX = sx + randomBetween(-40, 40);
          entryStartY = -20;
        } else if (minD === distBot) {
          entryStartX = sx + randomBetween(-40, 40);
          entryStartY = H + 20;
        } else if (minD === distLeft) {
          entryStartX = -20;
          entryStartY = sy + randomBetween(-40, 40);
        } else {
          entryStartX = W + 20;
          entryStartY = sy + randomBetween(-40, 40);
        }
      }

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
        entryStartX,
        entryStartY,
        entryDuration: initialWait,
        entryMode,
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

  // OSRM 도보 경로 prefetch — 노드 변경 시 pairwise 경로 로드
  // M-1: 빠른 동 전환 시 이전 fetch 취소 (AbortController)
  useEffect(() => {
    if (KAKAO_KEY_MISSING) return;
    if (storeNodes.length < 2) return;
    let cancelled = false;
    const controller = new AbortController();
    setRoutesLoaded(false);
    (async () => {
      const newCache: Record<string, [number, number][]> = {};
      const nodes = storeNodes;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = 0; j < nodes.length; j++) {
          if (i === j) continue;
          const key = `${i}-${j}`;
          try {
            const path = await fetchWalkingRoute(
              nodes[i].lat,
              nodes[i].lng,
              nodes[j].lat,
              nodes[j].lng,
              controller.signal,
            );
            newCache[key] = path;
          } catch (e: any) {
            if (e?.name === 'AbortError' || cancelled) return;
            // fallback — 직선
            newCache[key] = [
              [nodes[i].lat, nodes[i].lng],
              [nodes[j].lat, nodes[j].lng],
            ];
          }
          if (cancelled) return;
          // Rate limit 회피 — 150ms 간격
          await new Promise((r) => setTimeout(r, 150));
        }
      }
      if (!cancelled) {
        routeCacheRef.current = newCache;
        setRoutesLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [storeNodes]);

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
              p.entryStartX = p.x;
              p.entryStartY = p.y;
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

      // C-2: storeNodes/nodePixels 개수 불일치 시 해당 프레임 skip
      // (동 전환 직후 storeNodes는 교체되었지만 persona/nodePixels는 300ms 뒤 갱신)
      if (storeNodes.length !== nodePixelsRef.current.length) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

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

      // 현재 체류 중 에이전트 집계 (waitTicks > 0 = 매장 이용 중)
      spotStatsRef.current.forEach((s) => {
        s.currentAgents = 0;
      });
      personasRef.current.forEach((p) => {
        if (p.waitTicks > 0 && spotStatsRef.current[p.targetIdx]) {
          spotStatsRef.current[p.targetIdx].currentAgents++;
        }
      });

      // focusSpot 있으면 routine 노드(지하철·상점)는 전부 시각 숨김 → focusSpot 만 "신규 매장" 마커로 별도 렌더.
      // 없으면 routine 노드 전부 렌더 (마포 전체 POI 맵).
      const hideRoutineNodes = !!focusSpot;

      // 상권 노드 그리기 — 스팟 유형별 픽토그램 (지하철=T심볼 이중원 / 상점=집모양)
      nodes.forEach((np, idx) => {
        const node = storeNodes[idx];
        if (!node) return;
        if (hideRoutineNodes) return;

        // 스팟 유형 분기 — 백엔드 id/tier 기반
        const isSubway = node.id.startsWith('subway-') || node.tier === 'S';

        // 최근 30 tick 이내 결제 여부 (테두리만 gold 강조)
        const recentPay = paymentEffectsRef.current.some(
          (e) => e.nodeIdx === idx && tickRef.current - e.startTick < 30,
        );

        if (isSubway) {
          // 지하철역: 이중 원 + T 심볼 (15px 반경)
          const ringColor = recentPay ? '#FBBF24' : '#0891B2';
          const lineWidth = recentPay ? 3 : 2;
          drawSubwayStation(ctx, np.x, np.y, ringColor, lineWidth);
        } else {
          // 상점: 집 모양 (26×22)
          const ringColor = recentPay ? '#FBBF24' : 'rgba(255,255,255,0.8)';
          const lineWidth = recentPay ? 2.5 : 1.5;
          drawStoreHouse(ctx, np.x, np.y, node.tier, ringColor, lineWidth);
        }

        // 라벨 — 11px + 반투명 박스 (가독성)
        const labelY = np.y + (isSubway ? 15 : 11) + 14;
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
          ctx.fillStyle = isSubway ? '#67E8F9' : node.tier === 'A' ? '#A5B4FC' : '#D1D5DB';
          ctx.font = 'bold 9px monospace';
          ctx.fillText(`Tier ${node.tier}`, np.x, labelY + 11);
        }

        // 현재 체류자 배지 (우상단)
        if (stats && stats.currentAgents > 0) {
          const badgeOffset = isSubway ? 13 : 12;
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
          // 실시간 2초 = 가상 1시간 (60fps 기준 120 tick/hour)
          const ticksPerHour = 120;
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

          let drawn = 0;
          trajectoryPathsRef.current.forEach((path) => {
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
            const t = span > 0 ? Math.min(1, Math.max(0, (virtualHour - prev.absHour) / span)) : 0;
            const lat = prev.lat + (next.lat - prev.lat) * t;
            const lon = prev.lon + (next.lon - prev.lon) * t;
            const latLng = new kakao.maps.LatLng(lat, lon);
            const pix = proj.containerPointFromCoords(latLng);
            if (pix.x < 0 || pix.y < 0 || pix.x > W || pix.y > H) return;
            ctx.fillStyle = roleColor[prev.role] || '#E5E7EB';
            ctx.beginPath();
            ctx.arc(pix.x, pix.y, 3, 0, Math.PI * 2);
            ctx.fill();
            drawn++;
          });

          // 좌상단 타임스탬프 배지
          const hourLabel = `ABM ${String(displayHour % 24).padStart(2, '0')}:00 · 실데이터 ${drawn}명`;
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

      // 결제 bounce 아이콘 (gold 원 + ₩) — 36 tick 선행 애니메이션
      // focusSpot 있을 땐 routine 노드가 숨겨져 있으므로 ₩ 이펙트도 숨김 (허공 표시 방지)
      paymentBouncesRef.current = paymentBouncesRef.current.filter((e) => {
        const age = tickRef.current - e.startTick;
        if (age > 36) return false;
        if (hideRoutineNodes) return true;
        const np = nodes[e.nodeIdx];
        if (!np) return true;
        drawPaymentBounce(ctx, np.x, np.y - 14, age);
        return true;
      });

      // 결제 이펙트 렌더링 — ring pulse (0~60 tick) + ₩금액 텍스트 (36~126 tick)
      paymentEffectsRef.current = paymentEffectsRef.current.filter((e) => {
        const age = tickRef.current - e.startTick;
        if (age > 130) return false;
        if (hideRoutineNodes) return true;
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

      // 페르소나 이동 — OSRM 실제 도로 waypoint 따라 걷기 (+ wobble / ease)
      // trajectory 실데이터 있으면 합성 persona 렌더 skip (실데이터 점으로 대체)
      const useRealTrajectory = trajectoryPathsRef.current.size > 0;
      const map = mapInstanceRef.current;
      const kakao = (window as any).kakao ?? null;

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

            // 실제 도로 경로 캐시 lookup
            const key = `${p.sourceIdx}-${p.targetIdx}`;
            const latlngs = routeCacheRef.current[key];
            if (latlngs && latlngs.length >= 2 && kakao && map) {
              const proj = map.getProjection();
              p.waypoints = latlngs.map(([la, lo]) => {
                const pix = proj.containerPointFromCoords(new kakao.maps.LatLng(la, lo));
                return { x: pix.x, y: pix.y };
              });
              // 시작점을 현재 위치로 override (끊김 방지)
              p.waypoints[0] = { x: p.x, y: p.y };
              p.waypointIdx = 0;
              p.segmentProgress = 0;
            } else {
              // Fallback bezier
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
            // 개인별 좌/우 편향 — 전 경로 내내 유지 (한 도로 위 여러 에이전트가 나란히 걷지 않음)
            const lateralX = wobPerpX * p.lateralOffset;
            const lateralY = wobPerpY * p.lateralOffset;
            // 개인별 걸음걸이 진폭
            const wob = p.wobbleAmp * Math.sin(tickRef.current * 0.22 + p.wobblePhase);
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

        // External + 진입 중 (waitTicks > 0 + hasSpawned 전) = 차량/지하철 애니메이션
        if (isExternal && !p.hasSpawned && p.waitTicks > 0 && p.entryDuration > 0) {
          const progress = 1 - p.waitTicks / p.entryDuration;
          const vx = p.entryStartX + (p.x - p.entryStartX) * progress;
          const vy = p.entryStartY + (p.y - p.entryStartY) * progress;
          const heading = Math.atan2(p.y - p.entryStartY, p.x - p.entryStartX);
          // 이동 경로 trail
          ctx.strokeStyle =
            p.entryMode === 'subway'
              ? `rgba(6, 182, 212, ${0.25 + progress * 0.25})`
              : `rgba(251, 191, 36, ${0.2 + progress * 0.2})`;
          ctx.lineWidth = p.entryMode === 'subway' ? 2.5 : 1.5;
          ctx.setLineDash(p.entryMode === 'subway' ? [6, 4] : [4, 2]);
          ctx.beginPath();
          ctx.moveTo(p.entryStartX, p.entryStartY);
          ctx.lineTo(vx, vy);
          ctx.stroke();
          ctx.setLineDash([]);
          // 차량 벡터 드로잉 (이모티콘 대신 Canvas 도형)
          if (p.entryMode === 'subway') {
            drawSubwayCar(ctx, vx, vy, heading);
          } else {
            drawTaxi(ctx, vx, vy, heading);
          }
          return; // skip normal circle render
        }

        // 꼬리(Trail) 갱신 — 움직일 때만 push (정지/매장 체류 중엔 누적 방지)
        if (p.waitTicks <= 0) {
          // age 증가
          for (let ti = 0; ti < p.trail.length; ti++) {
            p.trail[ti].age++;
          }
          // 매 3 tick마다 현재 위치 snapshot
          if (tickRef.current % 3 === 0) {
            p.trail.unshift({ x: p.x, y: p.y, age: 0 });
            if (p.trail.length > 8) p.trail.pop();
          }
        }

        // 기본 반경 — spend 기반 (5~13)
        const baseR = 5 + Math.min(8, Math.sqrt(p.spend / 3000));
        // Tier별 크기 배율 + 테두리 두께 (색 아닌 크기/두께로 표현)
        const tierScale = p.tier === 'S' ? 1.2 : p.tier === 'A' ? 1.0 : 0.85;
        const tierLine = p.tier === 'S' ? 2.5 : p.tier === 'A' ? 1.8 : 1.2;
        const r = baseR * tierScale;
        const actionColor = ACTION_COLOR[p.action];

        // Trail 렌더 — action 색 (external은 cyan), age 높을수록 작고 투명하게
        const trailColor = isExternal ? '#06B6D4' : actionColor;
        for (const pt of p.trail) {
          const tAge = pt.age;
          if (tAge > 24) continue;
          const tAlpha = Math.max(0, 0.5 * (1 - tAge / 24));
          const tR = Math.max(1.2, 3 - (tAge / 24) * 1.5);
          ctx.globalAlpha = tAlpha;
          ctx.fillStyle = trailColor;
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, tR, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = 1;

        // External — 본체 뒤쪽 영구 cyan radial halo (반경 × 2.2)
        if (isExternal) {
          const haloR = r * 2.2;
          const extGrad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, haloR);
          extGrad.addColorStop(0, 'rgba(6, 182, 212, 0.35)');
          extGrad.addColorStop(1, 'rgba(6, 182, 212, 0)');
          ctx.fillStyle = extGrad;
          ctx.beginPath();
          ctx.arc(p.x, p.y, haloR, 0, Math.PI * 2);
          ctx.fill();
        }

        // Action 별 분기 렌더링
        // rest: globalAlpha 0.4 + 회색 채움
        // work: 채움 없음 + 초록 테두리만
        // visit/move: Action 색 채움 + 흰색 테두리 (tierLine 두께)
        if (p.action === 'rest') {
          ctx.globalAlpha = 0.4;
          ctx.fillStyle = '#6b7280';
          ctx.beginPath();
          ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
          ctx.fill();
          ctx.globalAlpha = 1;
          ctx.strokeStyle = '#FFFFFF';
          ctx.lineWidth = tierLine;
          ctx.beginPath();
          ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
          ctx.stroke();
        } else if (p.action === 'work') {
          // 채움 없이 초록 테두리만 (2px 고정) — 근무 outline-only
          ctx.strokeStyle = '#54A24B';
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
          ctx.stroke();
          // tier 크기 강조용 살짝 두꺼운 흰색 얇은 바깥 링 (S만)
          if (p.tier === 'S') {
            ctx.strokeStyle = '#FFFFFF';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(p.x, p.y, r + 2, 0, Math.PI * 2);
            ctx.stroke();
          }
        } else {
          // visit / move
          ctx.fillStyle = actionColor + 'dd';
          ctx.beginPath();
          ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = '#FFFFFF';
          ctx.lineWidth = tierLine;
          ctx.stroke();
        }

        // 방향성 화살표 tip — 이동 중이고 trail 2개 이상일 때만
        if (p.action === 'move' && p.trail.length >= 2) {
          const prev = p.trail[1]; // 직전 위치
          const dx = p.x - prev.x;
          const dy = p.y - prev.y;
          const len = Math.hypot(dx, dy);
          if (len > 0.5) {
            const heading = Math.atan2(dy, dx);
            const tipDist = r + 4;
            const tipX = p.x + Math.cos(heading) * tipDist;
            const tipY = p.y + Math.sin(heading) * tipDist;
            ctx.save();
            ctx.translate(tipX, tipY);
            ctx.rotate(heading);
            ctx.fillStyle = actionColor;
            ctx.beginPath();
            ctx.moveTo(4, 0);
            ctx.lineTo(-3, 3);
            ctx.lineTo(-3, -3);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
          }
        }
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
            {!KAKAO_KEY_MISSING && storeNodes.length >= 2 && (
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  routesLoaded
                    ? 'text-emerald-400 border-emerald-500/40'
                    : 'text-amber-400 border-amber-500/40 animate-pulse'
                }`}
                title="OSRM 도보 경로 프리로드 상태"
              >
                {routesLoaded ? '도로 경로 OK' : '경로 로딩...'}
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
    </div>
  );
}
