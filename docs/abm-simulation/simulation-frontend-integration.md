# 마포 ABM 시뮬레이션 - 프론트엔드 통합 가이드

> A1이 백엔드 API를 제공하고, 프론트엔드 담당자는 이 문서의 샘플 코드를 `frontend/src/` 에 옮겨 붙여서 통합합니다. 본 문서는 **참고용 샘플**만 포함하며, 실제 `frontend/` 디렉토리는 A1이 수정하지 않습니다.

---

## 1. 백엔드 API (`/api/simulation/*`)

백엔드에 이미 추가됨 (`backend/src/api/simulation.py`, `main.py include_router`).

| 메서드 | 경로 | 반환 |
|--------|------|------|
| GET | `/api/simulation/list` | 저장된 시나리오 목록 + 메타 |
| GET | `/api/simulation/{name}` | 메타 + top_stores + sample_stories |
| GET | `/api/simulation/{name}/trajectory` | 에이전트 위치 리스트 |
| GET | `/api/simulation/{name}/stores` | 매장 좌표/카테고리/매출 |
| GET | `/api/simulation/{name}/visits` | 방문 이벤트 |
| GET | `/api/simulation/{name}/chats` | 원시어 DSL 대화 메시지 |
| GET | `/api/simulation/{name}/friends` | 친구 네트워크 (엣지 리스트) |

### 응답 예시

```bash
curl http://localhost:8001/api/simulation/list
```
```json
{
  "scenarios": [
    {
      "name": "small_openai",
      "days": 1,
      "total_decisions": 1013,
      "tier_s_calls": 54,
      "tier_a_calls": 196,
      "estimated_cost_usd": 0.0196,
      "in_progress": false,
      "progress_pct": 1.0,
      "has_trajectory": true,
      "has_visits": true,
      "has_chats": true,
      "has_friends": true,
      "has_stores": true
    }
  ]
}
```

---

## 2. 프론트엔드 의존성 설치 (참고)

```bash
cd frontend
npm i react-leaflet leaflet-timedimension
# leaflet 은 이미 package.json 에 있음
```

TypeScript 타입:
```bash
npm i -D @types/leaflet
```

---

## 3. 샘플 코드

### 3.1 API 클라이언트 (`frontend/src/api/simulation.ts`)

```ts
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8001";

export type ScenarioMeta = {
  name: string;
  days: number;
  total_decisions: number;
  tier_s_calls: number;
  tier_a_calls: number;
  estimated_cost_usd: number;
  in_progress: boolean;
  progress_pct: number;
  has_trajectory: boolean;
  has_visits: boolean;
  has_chats: boolean;
  has_friends: boolean;
  has_stores: boolean;
};

export type TrajectoryPoint = {
  agent_id: number;
  day: number;
  hour: number;
  dong: string;
  action: "visit" | "move" | "work" | "rest";
  tier: "S" | "A" | "B";
  role: string;
  lat: number;
  lon: number;
};

export type StoreRow = {
  store_id: number;
  name: string;
  dong: string;
  category: "카페" | "음식점" | "주점" | "편의점" | "기타";
  lat: number;
  lon: number;
  revenue_today: number;
  visits_today: number;
};

export type VisitEvent = {
  agent_id: number;
  day: number;
  hour: number;
  store_id: number;
  store_name: string;
  store_category: string;
  store_lat: number;
  store_lon: number;
  spend: number;
};

export type ChatMessage = {
  day: number;
  hour: number;
  sender_id: number;
  receiver_id: number;
  verb: "INV" | "ACC" | "DEC" | "PROMO" | "INFO";
  args: Record<string, string>;
  encoded: string;
  sender_lat: number;
  sender_lon: number;
  receiver_lat: number;
  receiver_lon: number;
};

export type FriendEdge = {
  a: number;
  b: number;
  a_lat: number;
  a_lon: number;
  b_lat: number;
  b_lon: number;
  a_dong: string;
  b_dong: string;
};

export const simApi = {
  list: () => axios.get<{ scenarios: ScenarioMeta[] }>(`${API_BASE}/api/simulation/list`).then(r => r.data.scenarios),
  meta: (name: string) => axios.get(`${API_BASE}/api/simulation/${name}`).then(r => r.data),
  trajectory: (name: string) => axios.get<TrajectoryPoint[]>(`${API_BASE}/api/simulation/${name}/trajectory`).then(r => r.data),
  stores: (name: string) => axios.get<StoreRow[]>(`${API_BASE}/api/simulation/${name}/stores`).then(r => r.data),
  visits: (name: string) => axios.get<VisitEvent[]>(`${API_BASE}/api/simulation/${name}/visits`).then(r => r.data),
  chats: (name: string) => axios.get<ChatMessage[]>(`${API_BASE}/api/simulation/${name}/chats`).then(r => r.data),
  friends: (name: string) => axios.get<FriendEdge[]>(`${API_BASE}/api/simulation/${name}/friends`).then(r => r.data),
};
```

### 3.2 zustand 스토어 (`frontend/src/stores/simulationStore.ts`)

```ts
import { create } from "zustand";
import { simApi, ScenarioMeta } from "../api/simulation";

interface SimState {
  scenarios: ScenarioMeta[];
  selected: string | null;
  currentHour: number;
  loading: boolean;

  fetchScenarios: () => Promise<void>;
  select: (name: string) => void;
  setHour: (h: number) => void;
}

export const useSimulationStore = create<SimState>((set) => ({
  scenarios: [],
  selected: null,
  currentHour: 12,
  loading: false,

  fetchScenarios: async () => {
    set({ loading: true });
    const scenarios = await simApi.list();
    set({ scenarios, loading: false, selected: scenarios[0]?.name ?? null });
  },
  select: (name) => set({ selected: name }),
  setHour: (h) => set({ currentHour: h }),
}));
```

### 3.3 메인 지도 컴포넌트 (`frontend/src/components/simulation/SimulationMap.tsx`)

```tsx
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, LayersControl } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";  // 또는 useEffect 훅 직접
import { simApi, TrajectoryPoint, StoreRow } from "../../api/simulation";
import { useSimulationStore } from "../../stores/simulationStore";
import "leaflet/dist/leaflet.css";

const MAPO_CENTER: [number, number] = [37.558, 126.911];
const CATEGORY_COLOR: Record<string, string> = {
  "카페": "#FF8C42",
  "음식점": "#C7243A",
  "주점": "#6A4C93",
  "편의점": "#2E86AB",
  "기타": "#888",
};
const ACTION_COLOR: Record<string, string> = {
  visit: "#E45756",
  move: "#4C78A8",
  work: "#54A24B",
  rest: "#B0B0B0",
};

export function SimulationMap() {
  const { selected, currentHour } = useSimulationStore();
  if (!selected) return <div>시나리오를 선택하세요</div>;

  // React Query 권장 (캐싱), 없으면 useEffect + useState
  const { data: trajectory = [] } = useQuery({
    queryKey: ["trajectory", selected],
    queryFn: () => simApi.trajectory(selected),
  });
  const { data: stores = [] } = useQuery({
    queryKey: ["stores", selected],
    queryFn: () => simApi.stores(selected),
  });
  const { data: visits = [] } = useQuery({
    queryKey: ["visits", selected],
    queryFn: () => simApi.visits(selected),
  });
  const { data: chats = [] } = useQuery({
    queryKey: ["chats", selected],
    queryFn: () => simApi.chats(selected),
  });
  const { data: friends = [] } = useQuery({
    queryKey: ["friends", selected],
    queryFn: () => simApi.friends(selected),
  });

  // 현재 시간 프레임 에이전트만
  const currentAgents = trajectory.filter(p => p.hour === currentHour);

  return (
    <MapContainer center={MAPO_CENTER} zoom={13} style={{ height: "720px", width: "100%" }}>
      <TileLayer
        url="https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png"
        attribution="© CartoDB"
      />

      <LayersControl position="topright">
        {/* 매장 레이어 */}
        <LayersControl.Overlay checked name={`🏪 매장 (${stores.length})`}>
          <>
            {stores.map(s => (
              <CircleMarker
                key={`store-${s.store_id}`}
                center={[s.lat, s.lon]}
                radius={Math.min(12, 3 + Math.sqrt(s.revenue_today / 30000))}
                pathOptions={{
                  color: CATEGORY_COLOR[s.category] ?? "#999",
                  fillOpacity: 0.65,
                  weight: 1,
                }}
              >
                <Popup>
                  <b>{s.name}</b><br />
                  {s.dong} · {s.category}<br />
                  방문 {s.visits_today}회 · {s.revenue_today.toLocaleString()}원
                </Popup>
              </CircleMarker>
            ))}
          </>
        </LayersControl.Overlay>

        {/* 친구 네트워크 */}
        <LayersControl.Overlay name={`👥 친구 (${friends.length})`}>
          <>
            {friends.map((e, i) => (
              <Polyline
                key={`fr-${i}`}
                positions={[[e.a_lat, e.a_lon], [e.b_lat, e.b_lon]]}
                pathOptions={{ color: "#888", weight: 1, opacity: 0.25 }}
              />
            ))}
          </>
        </LayersControl.Overlay>

        {/* 대화 메시지 */}
        <LayersControl.Overlay name={`💬 대화 (${chats.length})`}>
          <>
            {chats.filter(c => c.hour <= currentHour).map((c, i) => (
              <Polyline
                key={`chat-${i}`}
                positions={[[c.sender_lat, c.sender_lon], [c.receiver_lat, c.receiver_lon]]}
                pathOptions={{ color: "#E67E22", weight: 2, opacity: 0.5, dashArray: "5,5" }}
              >
                <Popup>#{c.sender_id} → #{c.receiver_id}: {c.encoded}</Popup>
              </Polyline>
            ))}
          </>
        </LayersControl.Overlay>

        {/* 방문 이벤트 */}
        <LayersControl.Overlay name={`🛒 방문 (${visits.length})`}>
          <>
            {visits.filter(v => v.hour <= currentHour).map((v, i) => (
              <CircleMarker
                key={`v-${i}`}
                center={[v.store_lat, v.store_lon]}
                radius={6}
                pathOptions={{ color: "#C7243A", fillOpacity: 0.8 }}
              >
                <Popup>#{v.agent_id} → {v.store_name}<br/>{v.spend.toLocaleString()}원</Popup>
              </CircleMarker>
            ))}
          </>
        </LayersControl.Overlay>
      </LayersControl>

      {/* 현재 시간 에이전트 위치 (가장 위 레이어) */}
      {currentAgents.map((p, i) => (
        <CircleMarker
          key={`agent-${p.agent_id}-${i}`}
          center={[p.lat, p.lon]}
          radius={8}
          pathOptions={{
            color: "#fff",
            fillColor: ACTION_COLOR[p.action] ?? "#888",
            fillOpacity: 0.95,
            weight: 1.5,
          }}
        >
          <Popup>
            #{p.agent_id} · {p.tier}/{p.role}<br />
            {p.dong} · {p.action}
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
```

### 3.4 시간 슬라이더 (`frontend/src/components/simulation/TimeSlider.tsx`)

```tsx
import { useSimulationStore } from "../../stores/simulationStore";

export function TimeSlider() {
  const { currentHour, setHour } = useSimulationStore();
  return (
    <div className="flex items-center gap-3 p-3 bg-white rounded shadow">
      <span className="font-bold">{currentHour}시</span>
      <input
        type="range"
        min={6}
        max={25}
        value={currentHour}
        onChange={(e) => setHour(+e.target.value)}
        className="flex-1"
      />
      <button onClick={() => setHour(Math.max(6, currentHour - 1))}>◀</button>
      <button onClick={() => setHour(Math.min(25, currentHour + 1))}>▶</button>
    </div>
  );
}
```

### 3.5 페이지 조립 (`frontend/src/pages/SimulationPage.tsx`)

```tsx
import { useEffect } from "react";
import { SimulationMap } from "../components/simulation/SimulationMap";
import { TimeSlider } from "../components/simulation/TimeSlider";
import { useSimulationStore } from "../stores/simulationStore";

export default function SimulationPage() {
  const { scenarios, selected, select, fetchScenarios } = useSimulationStore();

  useEffect(() => { fetchScenarios(); }, [fetchScenarios]);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">마포구 에이전트 시뮬레이션</h1>

      <div className="mb-4">
        <select
          value={selected ?? ""}
          onChange={e => select(e.target.value)}
          className="border rounded px-3 py-1"
        >
          {scenarios.map(s => (
            <option key={s.name} value={s.name}>
              {s.name} — {s.total_decisions.toLocaleString()} 결정, {s.in_progress ? "진행중" : "완료"}
            </option>
          ))}
        </select>
      </div>

      <SimulationMap />

      <div className="mt-4">
        <TimeSlider />
      </div>
    </div>
  );
}
```

### 3.6 라우터 등록 (예시)

```tsx
// frontend/src/App.tsx 의 Routes 내부에 추가
<Route path="/simulation" element={<SimulationPage />} />
```

---

## 4. CORS 설정

백엔드 `main.py` 의 `_cors_origins` 에 이미 `http://localhost:3000` 포함됨. 프로덕션 도메인 추가 시 `CORS_ORIGINS` 환경변수 수정.

---

## 5. 현재 API 포트

개발 중 기본 포트는 **8001** (8000은 다른 프로세스 점유 시). `VITE_API_BASE` env로 오버라이드 가능.

```env
# frontend/.env.local
VITE_API_BASE=http://localhost:8001
```

---

## 6. 체크리스트 (프론트 담당자용)

- [ ] `npm i react-leaflet leaflet-timedimension @types/leaflet @tanstack/react-query`
- [ ] `api/simulation.ts` 추가
- [ ] `stores/simulationStore.ts` 추가
- [ ] `components/simulation/` 폴더 생성 + 컴포넌트 3개
- [ ] `pages/SimulationPage.tsx` 추가
- [ ] `App.tsx` 라우터에 등록
- [ ] 메뉴/내비에 "시뮬레이션" 링크 추가
- [ ] CSS: `leaflet/dist/leaflet.css` global import
