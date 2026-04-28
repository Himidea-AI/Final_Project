# Vacancy-Evaluation API 명세서

작성: A1 (찬영) — 2026-04-28
Branch: IM3-243-dong-fk-followup
Base URL: `http://localhost:8001` (dev), `https://<prod-host>` (운영)
Tag: `vacancy-evaluation`

---

## 0. 자동 OpenAPI / Swagger UI

FastAPI 가 자동 생성하는 명세 — 실시간 schema 확인:

| URL | 용도 |
|---|---|
| `http://localhost:8001/docs` | Swagger UI (interactive) |
| `http://localhost:8001/redoc` | ReDoc (read-only) |
| `http://localhost:8001/openapi.json` | OpenAPI 3.0 raw JSON |

→ 본 명세서는 사람이 읽는 요약 + frontend 통합 가이드. 실제 schema 는 `/openapi.json` 우선.

## 1. Endpoint 일람 (8개)

| # | Method | Path | 용도 |
|---|---|---|---|
| 1 | POST | `/vacancy-evaluation/single` | 단일 vacancy 평가 (동기 or 비동기) |
| 2 | POST | `/vacancy-evaluation/batch` | 여러 vacancy 평가 + 순위 |
| 3 | GET | `/vacancy-evaluation/health` | 모듈 ping |
| 4 | GET | `/vacancy-evaluation/{job_id}/status` | **신규** — Job 상태 조회 |
| 5 | GET | `/vacancy-evaluation/{job_id}/trajectory` | **신규** — agent 시간대별 위치 |
| 6 | GET | `/vacancy-evaluation/{job_id}/visits` | **신규** — vacancy 방문 이벤트 |
| 7 | GET | `/vacancy-evaluation/{job_id}/stores` | **신규** — 매장 좌표/매출 |
| 8 | GET | `/vacancy-evaluation/{job_id}/chats` | **신규** — 자연어 대화 (Mode B) |

## 2. Common — 공통 schema

### 2.1 VacancySpotIn
```typescript
{
  dong: string;         // 마포 행정동명 (예: "서교동")
  lat: number;          // 위도 (37.5 ~ 37.6)
  lon: number;          // 경도 (126.85 ~ 126.97)
  id?: number;          // 네이버 부동산 매물 id (선택)
  listing_count?: number;  // 해당 좌표 매물 수 (선택)
}
```

### 2.2 ALLOWED_CATEGORIES
`"음식점" | "카페" | "주점" | "편의점" | "기타"`

### 2.3 PseSummary (트랙 측정)
```typescript
{
  visits_per_day: { mean: number; std: number; ci95: number; min: number; max: number; n: number };
  revenue_per_day: { mean: number; std: number; ci95: number; min: number; max: number; n: number };
  occupancy: { mean: number; ci95: number; ... };
  vacancy_vs_avg_visits_ratio: { mean: number; ci95: number; ... };
  vacancy_vs_avg_revenue_ratio: { mean: number; ci95: number; ... };
  cannibalization_pct?: { mean: number; ci95: number; ... };
  synergy_pct?: { mean: number; ci95: number; ... };
  dong_net_growth_pct?: { mean: number; ci95: number; ... };
  visits_per_quarter: { mean: number; ci95: number };
  visits_per_year: { mean: number; ci95: number };
  revenue_per_quarter: { mean: number; ci95: number };
  revenue_per_year: { mean: number; ci95: number };
}
```

---

## 3. POST /vacancy-evaluation/single

단일 vacancy 평가. **`async_mode` 로 동기/비동기 선택**.

### Request Body
```typescript
{
  spot: VacancySpotIn;
  category: string;                   // ALLOWED_CATEGORIES 중 하나
  n_seeds?: number;                   // PSE N (default 5, 시각화 default 1)
  days?: number;                      // 시뮬 일수 (default 1, max 7)
  with_cannibalization?: boolean;     // 카니발 측정 (default false)
  popularity_boost?: number | null;   // 신규 매장 인지도 (default 5.0, 시각화 권장 20.0)
  collect_trajectory?: boolean;       // 시각화 trajectory dump (default false)
  dump_visits?: boolean;              // 방문 이벤트 dump (default false)
  async_mode?: boolean;               // true 시 즉시 job_id 반환 (default false)
  agents?: number;                    // agent 수 (default 5000, plan #2 일관)
}
```

### Response (동기, `async_mode=false`, default)
- 5~10분 대기 후 `VacancyResult` 반환
- HTTP timeout 위험 — client timeout ≥ 600s 권장
```typescript
{
  vacancy_spot: VacancySpotIn;
  category: string;
  n_seeds: number;
  days: number;
  popularity_boost: number;
  with_cannibalization: boolean;
  per_seed: Array<{...}>;
  pse_summary: PseSummary;
  narrative: string;                  // 사람 가독 형식
  trajectory?: Array<{...}> | null;   // collect_trajectory=true 시
  visits_events?: Array<{...}> | null; // dump_visits=true 시
}
```

### Response (비동기, `async_mode=true`)
- 즉시 반환 (1초 안)
```typescript
{
  job_id: string;     // UUID4
  status: "running";
}
```
→ 이후 GET `/{job_id}/status` polling 후 4 endpoint fetch.

### Error
- `400 Bad Request` — invalid category, lat/lon 범위 초과
- `500 Internal Server Error` — 시뮬 예외 (동기 모드)

### 예시 (curl)
```bash
# 동기 (기존 사용 방식)
curl -X POST http://localhost:8001/vacancy-evaluation/single \
  -H "Content-Type: application/json" \
  --max-time 600 \
  -d '{
    "spot": {"dong": "서교동", "lat": 37.5544, "lon": 126.9220},
    "category": "카페",
    "n_seeds": 5,
    "days": 1,
    "with_cannibalization": false,
    "popularity_boost": 5.0
  }'

# 비동기 (시각화 모드 — 시각화 시뮬에 권장)
curl -X POST http://localhost:8001/vacancy-evaluation/single \
  -H "Content-Type: application/json" \
  -d '{
    "spot": {"dong": "서교동", "lat": 37.5544, "lon": 126.9220},
    "category": "카페",
    "n_seeds": 1,
    "days": 1,
    "popularity_boost": 20.0,
    "agents": 5000,
    "collect_trajectory": true,
    "dump_visits": true,
    "async_mode": true
  }'
# Response: {"job_id": "abc-uuid", "status": "running"}
```

---

## 4. POST /vacancy-evaluation/batch

여러 vacancy 일괄 평가 + 순위 산출 (district_ranking 노드 출력 직접 적용).

### Request Body
```typescript
{
  vacancy_spots: VacancySpotIn[];
  category: string;
  top_n?: number;                     // 평가할 상위 공실 수 (default 5)
  n_seeds?: number;
  with_cannibalization?: boolean;
  pre_filter_score?: number[];        // vacancy_spots 와 같은 길이, 사전 필터 점수
  brand_name?: string | null;         // 모든 spot 에 공통 적용
}
```

### Response
```typescript
{
  rankings: Array<{
    rank: number;
    spot: VacancySpotIn;
    narrative: string;
    pse_summary: PseSummary;
    score: number;                    // visits_per_day mean (정렬 키)
  }>;
}
```

### 예시
```bash
curl -X POST http://localhost:8001/vacancy-evaluation/batch \
  -H "Content-Type: application/json" \
  --max-time 1800 \
  -d '{
    "vacancy_spots": [
      {"dong": "서교동", "lat": 37.5544, "lon": 126.9220},
      {"dong": "망원1동", "lat": 37.5573, "lon": 126.9050}
    ],
    "category": "카페",
    "top_n": 5,
    "brand_name": "이디야"
  }'
```

---

## 5. GET /vacancy-evaluation/health

모듈 ping. 의존성 (DB, vacancy_pse 모듈) 확인.

### Response
```typescript
{ "status": "ok" }
```

---

## 6. GET /vacancy-evaluation/{job_id}/status (신규)

비동기 시뮬 진행 상태 조회.

### Path Params
- `job_id: string` (POST `/single async_mode=true` 의 응답에서 받은 UUID)

### Response
```typescript
{
  job_id: string;
  status: "running" | "done" | "failed";
  elapsed_seconds: number;       // 시뮬 시작부터 경과 (초)
  error?: string | null;          // status="failed" 시 error message
}
```

### Error
- `404 Not Found` — job_id 가 cache 에 없음 (TTL 1시간 만료 또는 미존재)

### 예시
```bash
curl http://localhost:8001/vacancy-evaluation/abc-uuid/status
# {"job_id": "abc-uuid", "status": "running", "elapsed_seconds": 120, "error": null}
```

### Polling 권장 패턴 (frontend)
```typescript
async function pollStatus(jobId: string, intervalMs = 3000): Promise<void> {
  while (true) {
    const r = await fetch(`/vacancy-evaluation/${jobId}/status`);
    if (!r.ok) throw new Error(`status fetch failed: ${r.status}`);
    const data = await r.json();
    if (data.status === 'done') return;
    if (data.status === 'failed') throw new Error(data.error);
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
}
```

---

## 7. GET /vacancy-evaluation/{job_id}/trajectory (신규)

Agent 의 시간대별 위치 (시각화용). `collect_trajectory=true` 로 시뮬 시작한 경우만 데이터 있음.

### Response
```typescript
{
  job_id: string;
  status: "done";
  trajectory: Array<{
    agent_id: number;
    hour: number;          // 0~23 또는 시뮬 step
    lat: number;
    lon: number;
    dong?: string;
    tier?: "S" | "A" | "B";
    action?: "visit" | "move" | "work" | "rest";
  }>;
  n_agents: number;        // 표본 size (default 5000 of 옵션 — sampling 한 N 만 dump)
}
```

### Error
- `404 Not Found` — job_id 미존재
- `409 Conflict` — job 아직 running (status 먼저 확인 권장)
- `500 Internal Server Error` — job 실패

### 예시
```bash
curl http://localhost:8001/vacancy-evaluation/abc-uuid/trajectory
```

### Payload 크기 주의
- 5000ag × 18 시간 × 평균 dump rate ≈ 30,000~90,000 row
- gzip 후 약 1~3 MB
- frontend lazy load 또는 시간대별 pagination 권장

---

## 8. GET /vacancy-evaluation/{job_id}/visits (신규)

vacancy 매장에 들어온 방문 이벤트. `dump_visits=true` 시.

### Response
```typescript
{
  job_id: string;
  visits_events: Array<{
    seed: number;
    agent_id: number;
    store_id: string;        // "vacancy_0_서교동" 같은 vacancy ID
    hour: number;
    spend: number;           // 결제 금액 (원)
    category?: string;
    dialog?: string;          // Mode B template 자연어 (옵션)
  }>;
  vacancy_id: string;        // 분석 대상 vacancy 매장 ID
}
```

### 예시
```bash
curl http://localhost:8001/vacancy-evaluation/abc-uuid/visits
```

---

## 9. GET /vacancy-evaluation/{job_id}/stores (신규)

vacancy + 주변 매장 좌표/매출. 지도 표시용.

### Response
```typescript
{
  job_id: string;
  vacancy_spot: {
    dong: string;
    lat: number;
    lon: number;
    category: string;
  };
  stores: Array<{
    store_id: string;
    name: string;
    dong: string;
    category: string;
    lat: number;
    lon: number;
    revenue_today: number;
    visits_today: number;
    popularity_boost: number;
    is_vacancy: boolean;
  }>;
}
```

### 예시
```bash
curl http://localhost:8001/vacancy-evaluation/abc-uuid/stores
```

---

## 10. GET /vacancy-evaluation/{job_id}/chats (신규)

archetype 별 자연어 대화 (Mode B template, dialog_templates.py 의 600 한국어 문장).

### Response
```typescript
{
  job_id: string;
  chats: Array<{
    agent_id: number;
    archetype?: string;     // "creative_freelancer" | "office_worker" | ...
    hour: number;
    text: string;            // 한국어 짧은 문장 ("오늘 작업할 카페 어디로 가지" 등)
  }>;
}
```

### 예시
```bash
curl http://localhost:8001/vacancy-evaluation/abc-uuid/chats
```

---

## 11. Frontend 통합 흐름 (AbmPersonaMap mode='vacancy')

```typescript
// 1. POST /single async_mode=true → job_id
const r = await fetch('/vacancy-evaluation/single', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    spot: { dong: '서교동', lat: 37.5544, lon: 126.9220 },
    category: '카페',
    n_seeds: 1, days: 1,
    popularity_boost: 20.0,
    agents: 5000,
    collect_trajectory: true,
    dump_visits: true,
    async_mode: true,
  }),
});
const { job_id } = await r.json();

// 2. polling 3초 간격
await pollStatus(job_id);  // 위 6장 코드

// 3. 4 endpoint 동시 fetch
const [traj, visits, stores, chats] = await Promise.all([
  fetch(`/vacancy-evaluation/${job_id}/trajectory`).then(r => r.json()),
  fetch(`/vacancy-evaluation/${job_id}/visits`).then(r => r.json()),
  fetch(`/vacancy-evaluation/${job_id}/stores`).then(r => r.json()),
  fetch(`/vacancy-evaluation/${job_id}/chats`).then(r => r.json()),
]);

// 4. AbmPersonaMap 컴포넌트 props 로 전달
<AbmPersonaMap
  mode="vacancy"
  vacancyJobId={job_id}
  vacancySpot={{ dong: '서교동', lat: 37.5544, lng: 126.9220 }}
  vacancyPseSummary={stores.pse_summary}  // 옵션
/>
```

---

## 12. Cache 정책 (서버 측)

- **In-memory dict** (`vacancy_pse_cache`): 현재 process 만, multi-worker 시 cache miss 가능
- **TTL**: **1시간** — `cleanup_expired_cache()` 주기적 호출 권장
- **동시 job 제한**: 명시적 limit X (시뮬 자체가 ~5~10분 걸려 자연 제한)
- **운영 시 Redis 권장** (future spec)

---

## 13. 시간 / 비용

| 작업 | 시간 | 비용 |
|---|---|---|
| `POST /single` 동기 (5000ag, N=5, days=1) | ~5~10분 | $0 (mock 강제) |
| `POST /single` 비동기 시각화 (5000ag, N=1, days=1) | ~3~5분 (background) | $0 |
| 4 GET endpoint | ~10~50ms | $0 |
| status polling 3초 간격 | ~10ms × 60 (~3분) | $0 |

→ 시각화 1회 평가 = ~5분 + 즉시 표시 (총 5~10분).

---

## 14. 에러 처리 권장

### Frontend 에러 토스트
```typescript
try {
  const job_id = await startSimulation(...);
  await pollStatus(job_id);
  // ...
} catch (e) {
  if (e.message.includes('failed')) {
    toast.error('시뮬 실패 — 다시 시도');
  } else if (e.message.includes('404')) {
    toast.error('결과 만료 — 재시뮬 필요');
  } else {
    toast.error('오류: ' + e.message);
  }
}
```

### Backend timeout 권장
- 동기 `POST /single`: **600초 (10분)**
- 비동기 status polling: 30분 cap
- 4 GET endpoint: 60초

---

## 15. CORS 설정 (frontend dev)

`backend/src/main.py` 의 `CORSMiddleware` 가 `localhost:5173` (Vite dev) 허용 확인:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 16. 변경 로그

| 날짜 | 작성자 | 변경 |
|---|---|---|
| 2026-04-28 | A1 (찬영) | 초기 작성 — 4 신규 endpoint (status/trajectory/visits/stores/chats) + 기존 single/batch/health 정리 + frontend 통합 흐름 |

---

## 17. 참고

- 본 plan: `docs/superpowers/plans/2026-04-28-vacancy-pse-visualization.md`
- 본 spec: `docs/superpowers/specs/2026-04-28-vacancy-pse-visualization-design.md`
- Backend 코드:
  - `backend/src/api/vacancy_evaluation.py` — 8 endpoint
  - `backend/src/services/vacancy_evaluation_service.py` — `vacancy_pse_cache`, `run_vacancy_pse_async`
- Frontend 코드:
  - `frontend/src/components/AbmPersonaMap.tsx` — `mode="vacancy"` prop
  - `frontend/src/components/VacancySpotMarker.tsx`
  - `frontend/src/components/VacancyStatsPanel.tsx`
- 자동 OpenAPI: `http://localhost:8001/docs`
