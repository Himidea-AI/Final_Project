# Vacancy_PSE 시각화 — Design

작성: A1 (찬영) — 2026-04-28
Branch: IM3-243-dong-fk-followup → dev merge 후 새 branch (또는 본 branch)
Status: Design (사용자 검토 대기)
Predecessors:
- `2026-04-27-brand-menu-vacancy-pse-validation-design.md` (commit 65fbb80, plan execution `ba47e27` 종료)
- `2026-04-27-vacancy-pse-production-ready-design.md` (commit 4ea574c, plan execution `c5535be` — V1A r=0.95 학계 천장 도달)

---

## 1. 개요 (한 줄 요약)

본 plan #1 의 vacancy_pse `collect_trajectory`/`dump_visits` 인터페이스 + dev 브랜치의 `AbmPersonaMap.tsx` 기존 인프라를 통합 — **사용자가 공실 spot 클릭 → 1000ag 가 마포 지도 위 dot 으로 움직이며 spot 방문 흐름 시각화 + 시간 슬라이더 + 매출/방문 통계** 까지 도달.

## 2. 사용자 Vision (직전 brainstorm 명시)

> "사장님이 공실 spot 클릭 → 1000 에이전트가 마포구 지도 위에 점으로 표시되며 시간대별 동선 진행 → spot 위치 강조 (붉은 표시) → 시간 슬라이더로 7시→8시→... 진행 → spot 들어오는 방문객 trail 시각화 → 시뮬 끝나면 매출/방문 통계 + 동선 replay."

## 3. Context — 이미 작동 중 인프라 (활용 가능)

### 3.1 Backend (본 branch + dev)

- `backend/src/simulation/vacancy_pse.py` — **`collect_trajectory: bool`, `dump_visits: bool` 인자 이미 정의됨** (commit 085b5e8)
- `backend/src/api/vacancy_evaluation.py` — REST API 3개 (`/single`, `/batch`, `/health`) 작동
- `backend/src/api/simulation.py` — 일반 시뮬용 7개 endpoint (`/api/simulation/*`) 패턴 (참고 source)
- `vacancy_pse` 의 결과: `result["trajectory"]: list[dict]`, `result["visits_events"]: list[dict]` (옵션 활성 시)

### 3.2 Frontend (dev 브랜치, origin/dev 25 commit ahead)

- `frontend/src/components/AbmPersonaMap.tsx` — **1000ag persona 시각화 (visit 빨강/move 파랑/work 녹색/rest 회색, Tier S/A/B + waypoints, 카카오맵 SDK)**
- `frontend/src/components/AgentMapVisualizer.tsx` — 카카오맵 + spot/competitor pin
- `frontend/src/assets/mapo_geo.json` — 마포 GeoJSON
- `frontend/src/components/simulation/SpotterAgentWorkflow.tsx` — LangGraph 5-노드 워크플로우 시각화

### 3.3 사용자 vision 의 95% 가 이미 인프라에 존재

- 1000ag dot 시각화 ✅
- visit/move/work/rest 색깔 ✅
- 카카오맵 + 마포 GeoJSON ✅
- 자연어 대화 (Mode B template, `dialog_templates.py`) ✅

→ **본 spec = 기존 인프라 + vacancy_pse 결과 연결만**. 새 컴포넌트 신규 작성 X.

## 4. 결정 기록

| 항목 | 선택 | 이유 |
|---|---|---|
| Spec scope | **옵션 C — 인프라 + 기존 컴포넌트 vacancy 모드** | 사용자 본인 frontend 작업 가능 (직전 결정), 강민 의존 X, 3~4일 |
| Backend 새 endpoint | **4개 신규** (`/{job_id}/{trajectory,visits,stores,chats}`) | `/api/simulation/*` 패턴 follow, 재사용 가능 |
| job_id cache | **in-memory dict** (TTL 1시간) | 단순, Redis 도입은 future spec (운영 단계) |
| AbmPersonaMap 수정 | **`mode` prop 추가** (`"general"` \| `"vacancy"`) | 기존 컴포넌트 확장만, 신규 작성 X |
| 비동기 처리 | **간단한 background 큐** (Python threading) | vacancy_pse 5~10분 → polling. 운영 큐 (Celery 등) 는 future |
| 자연어 대화 | **Mode B template (한국어 600 문장)** 그대로 활용 | LLM 비용 0, 본 plan #1 의 dialog_templates 재사용 |
| 시간 슬라이더 | **7시~24시 18 step** | vacancy_pse 의 days=1 default + collect_trajectory 시 시간대별 dump |
| 사용자 작업 영역 | **A1 단독 (backend + frontend 모두)** | AGENTS.md 의 frontend = C1 강민 but 사용자 본인 작업 OK 명시 |

## 5. 아키텍처

```
[사용자 GUI]
  brand 선택 + 공실 spot 클릭
        │
        ▼
POST /vacancy-evaluation/single
  → vacancy_pse(collect_trajectory=True, dump_visits=True, ...)
  → 5~10분 시뮬 (background thread)
  → 결과 cache + job_id 반환
        │
        ▼ (polling 3초 간격)
GET /vacancy-evaluation/{job_id}/status → "running" / "done" / "failed"
        │
        ▼ ("done" 시 4 endpoint 호출)
GET .../trajectory  → 1000ag × 시간대별 위치 (dump_size 조절 가능)
GET .../visits      → vacancy 매장 visit 이벤트
GET .../stores      → 마포 매장 좌표 + 매출
GET .../chats       → archetype 별 한국어 대화 (Mode B template)
        │
        ▼
[AbmPersonaMap mode="vacancy"]
  - 카카오맵 + 마포 GeoJSON
  - 1000ag dot (visit/move/work/rest 색깔)
  - vacancy spot 강조 (빨간 펄스)
  - 시간 슬라이더 7~24시
  - 사이드 패널: 매출/방문 통계 + 동 평균 대비 + 카니발
  - 클릭 한 ag 위 말풍선 (Mode B 자연어)
```

## 6. 컴포넌트

| 컴포넌트 | 위치 | 신규/수정 | 책임 |
|---|---|---|---|
| **`POST /vacancy-evaluation/single`** | `backend/src/api/vacancy_evaluation.py` | **수정** | 인자에 `collect_trajectory: bool = False`, `dump_visits: bool = False` 추가, vacancy_pse 호출, job_id cache 등록 |
| **`GET /vacancy-evaluation/{job_id}/status`** | 같음 | **신규** | "running" / "done" / "failed" + progress |
| **`GET /vacancy-evaluation/{job_id}/trajectory`** | 같음 | **신규** | trajectory list (sample_size 조절 가능, default 300) |
| **`GET /vacancy-evaluation/{job_id}/visits`** | 같음 | **신규** | visits_events list |
| **`GET /vacancy-evaluation/{job_id}/stores`** | 같음 | **신규** | vacancy + 주변 매장 좌표 + 매출 |
| **`GET /vacancy-evaluation/{job_id}/chats`** | 같음 | **신규** | archetype 별 자연어 대화 (dialog_templates 활용) |
| **`vacancy_pse_cache: dict[str, dict]`** | `backend/src/services/vacancy_evaluation_service.py` | **신규** | in-memory dict, TTL 1시간, threading.Lock |
| **`run_vacancy_pse_async(...)`** | 같음 | **신규** | threading.Thread 로 vacancy_pse 실행 + cache 저장 |
| **`AbmPersonaMap.tsx` 의 `mode` prop** | `frontend/src/components/AbmPersonaMap.tsx` | **수정** | `mode="general"` (default, 기존) + `mode="vacancy"` (새) |
| **VacancySpotMarker** (AbmPersonaMap 내) | 같음 | **신규** (작은 추가) | vacancy spot 빨간 펄스 marker, 반경 500m 강조 |
| **VacancyStatsPanel** | `frontend/src/components/VacancyStatsPanel.tsx` | **신규** | 매출/방문 통계 + 동 평균 대비 + 카니발 + zero-sum 분석 |

### 6.1 책임 경계

- backend API endpoint — vacancy_pse 결과 cache 조회만, 시뮬 직접 호출 X
- frontend `AbmPersonaMap` 의 vacancy 모드 — backend 4 endpoint polling + 표시만, 시뮬 호출 X
- `VacancyStatsPanel` — vacancy_pse 결과 narrative + numbers 표시만, 별도 logic X

## 7. 데이터 흐름

### 7.1 비동기 시뮬 처리

```python
# backend/src/services/vacancy_evaluation_service.py

import threading
import uuid
import time

vacancy_pse_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()

def run_vacancy_pse_async(
    spot, category, brand_name=None, n_seeds=5, days=1,
    collect_trajectory=True, dump_visits=True,
) -> str:
    """vacancy_pse 비동기 실행. job_id 즉시 반환, 결과는 cache 에 저장."""
    job_id = str(uuid.uuid4())
    with _cache_lock:
        vacancy_pse_cache[job_id] = {
            "status": "running",
            "started_at": time.time(),
            "result": None,
            "error": None,
        }

    def _run():
        try:
            from src.simulation.vacancy_pse import evaluate_vacancy_pse
            menu_items = brand_menu_loader.load_brand_menu_items(brand_name) if brand_name else None
            result = evaluate_vacancy_pse(
                spot, category, n_seeds=n_seeds, days=days,
                collect_trajectory=collect_trajectory,
                dump_visits=dump_visits,
                menu_items=menu_items,
                with_cannibalization=True,
            )
            with _cache_lock:
                vacancy_pse_cache[job_id]["status"] = "done"
                vacancy_pse_cache[job_id]["result"] = result
        except Exception as e:
            with _cache_lock:
                vacancy_pse_cache[job_id]["status"] = "failed"
                vacancy_pse_cache[job_id]["error"] = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return job_id

def cleanup_expired_cache(ttl_seconds: int = 3600) -> None:
    """만료된 job (1시간 경과) 제거. 주기적 호출 권장."""
    now = time.time()
    with _cache_lock:
        expired = [k for k, v in vacancy_pse_cache.items() if now - v["started_at"] > ttl_seconds]
        for k in expired:
            del vacancy_pse_cache[k]
```

### 7.2 4 endpoint 응답 schema

```python
# GET /vacancy-evaluation/{job_id}/trajectory
# Response:
{
    "job_id": "uuid",
    "status": "done",
    "trajectory": [
        {"agent_id": 1, "hour": 7, "lat": 37.55, "lon": 126.92, "dong": "서교동", "tier": "S", "action": "move"},
        ...
    ],
    "n_agents": 1000,
    "n_hours": 18,
}

# GET .../visits
{
    "job_id": "uuid",
    "visits_events": [
        {"agent_id": 1, "store_id": "vacancy_0_서교동", "hour": 13, "spend": 5000, "category": "카페"},
        ...
    ],
    "vacancy_id": "vacancy_0_서교동",
}

# GET .../stores
{
    "job_id": "uuid",
    "vacancy_spot": {"dong": "서교동", "lat": 37.5544, "lon": 126.9220, "category": "카페"},
    "stores": [
        {"store_id": "abc", "lat": 37.55, "lon": 126.92, "category": "카페", "revenue_today": 250000, "popularity_boost": 1.0, "is_vacancy": false},
        ...
    ],
}

# GET .../chats
{
    "job_id": "uuid",
    "chats": [
        {"agent_id": 1, "archetype": "office_worker", "hour": 12, "text": "오늘은 한식 가자"},
        ...
    ],
}
```

## 8. UI/UX 흐름

```
[Step 1] 사용자: brand 선택 + 공실 spot 클릭
   POST /vacancy-evaluation/single (collect_trajectory=True, dump_visits=True)
   → job_id 반환 + 로딩 표시

[Step 2] Polling (3초 간격)
   GET /vacancy-evaluation/{job_id}/status
   → "running" 동안 progress bar (예: "시뮬 중 30%...")
   → "done" 시 [Step 3]

[Step 3] 4 endpoint 동시 fetch
   trajectory + visits + stores + chats

[Step 4] AbmPersonaMap (mode="vacancy") 렌더
   - 카카오맵 + 마포 GeoJSON
   - vacancy spot 빨간 펄스 마커 (반경 500m 원)
   - 1000ag dot 시간대별 (visit/move/work/rest 색깔)
   - 시간 슬라이더 7시 (default)

[Step 5] 시간 진행 (auto play 또는 manual)
   - drag → 7시 → 24시
   - 12시: 점심 시간 — 음식점 visit 폭증
   - 19시: 저녁 — 주점 visit
   - vacancy spot 들어오는 ag 의 trail (5초 fade)

[Step 6] 사이드 패널
   - 분기 추정 매출 1.6 ± 0.2억
   - 동 평균 대비 65배
   - 카니발 (반경 500m): -3.2 ± 158%
   - 동 시장 성장: +1.41 ± 3.5%

[Step 7] 클릭 한 ag → 말풍선
   - "오늘 작업할 카페 어디로 가지" (Mode B template)
```

## 9. 오류 처리

| 오류 | 처리 |
|---|---|
| 시뮬 실패 (vacancy_pse 예외) | status="failed" + error message → frontend 에러 토스트 |
| job_id 만료 (TTL 1시간) | 404 + "결과 만료, 재시뮬 필요" 안내 |
| polling timeout (30분) | frontend 에서 재시도 또는 cancel |
| cache size 폭주 | TTL cleanup + 동시 job 수 제한 (기본 5) |
| AbmPersonaMap 의 trajectory 데이터 누락 | fallback general 모드 또는 빈 지도 + warning |

## 10. 테스트

### 10.1 Backend

- `backend/tests/test_vacancy_evaluation_async.py` — `run_vacancy_pse_async`, cache, status, TTL cleanup 단위 테스트 (~6 test, mock 기반)
- `backend/tests/test_vacancy_endpoints_visualization.py` — 4 endpoint 통합 테스트 (mock cache)
- 회귀: 기존 `/vacancy-evaluation/single` API 영향 X (`collect_trajectory` default False)

### 10.2 Frontend

- `frontend/src/components/__tests__/AbmPersonaMap.vacancy.test.tsx` — vacancy 모드 visual rendering test (Vitest + Testing Library)
- 통합: dev 환경에서 실제 backend → frontend e2e (Playwright optional)

## 11. Limitations & Future Work

### 11.1 본 spec 의 한계

1. **In-memory cache** — 단일 process 만, multi-worker 운영 시 cache miss 가능. 운영은 Redis 도입 필요 (future spec).
2. **threading 비동기** — 정식 task queue (Celery/RQ) X. 안정성 한계.
3. **Mode B template 자연어** — 600 문장 반복. 다양성 제한 (LLM 미활성).
4. **trajectory dump size** — 1000ag × 18시간 = 18,000 row/시뮬. payload 크기 ~5MB (gzip 후 ~500KB). pagination 미적용.
5. **시간 단위 1시간** — 더 세밀한 단위 (15분, 5분) 미지원.

### 11.2 Future Work (별도 spec)

- **Redis cache + Celery 큐** (운영 spec)
- **Mode C LLM 활성** (1000명 GPT-4.1 mini, 자연어 다양성 ↑)
- **TCN 보정 결과 시각화** (절대값 합격 표시 + tooltip)
- **op_fit baseline grid 시각화** (학술 발표용 비교)
- **3D 시각화** (deck.gl 등 — high-end 가시화)

## 12. 사전 검증 체크리스트

- [ ] dev 브랜치 의 `AbmPersonaMap.tsx` 의 backend endpoint 호출 패턴 확인 (`/api/simulation/{name}/*` 호출 형식)
- [ ] dev 브랜치 의 카카오맵 SDK key 환경 변수 확인
- [ ] vacancy_pse 의 `collect_trajectory=True` 시 trajectory 데이터 형식 확인 (agent_id, hour, lat, lon, action 모두 dump 되는지)
- [ ] dialog_templates 의 archetype id 8개가 trajectory 의 agent archetype 과 매칭되는지
- [ ] 본 branch 가 dev 와 merge 가능한지 (conflict 사전 점검)

## 13. 변경 영향 / 호환성

| 호출자 | 영향 |
|---|---|
| 기존 `/vacancy-evaluation/single` 호출 (collect_trajectory 없이) | **영향 X** (default False) |
| 기존 `vacancy_pse.evaluate_vacancy_pse(...)` 호출 | 영향 X (default False) |
| 기존 `AbmPersonaMap` 의 일반 시뮬 모드 | 영향 X (`mode="general"` default) |
| 기존 `/api/simulation/*` 7 endpoint | 영향 X (별도 namespace) |

DB 변경: **없음**. 새 테이블/컬럼 X.

## 14. 구현 순서 (writing-plans 단계)

1. backend cache + threading.Thread 비동기 인프라 신규 (`vacancy_evaluation_service.py`)
2. 4 endpoint 신규 (`vacancy_evaluation.py`)
3. backend 회귀 테스트
4. dev merge (또는 본 branch 에 frontend 끌어오기)
5. AbmPersonaMap 의 `mode="vacancy"` prop 추가
6. VacancySpotMarker (펄스 효과)
7. VacancyStatsPanel (사이드 패널)
8. frontend 회귀 테스트
9. 통합 e2e (실제 vacancy_pse 시뮬 → 시각화)
10. 사용자 manual 검증 (사장님 시각 시뮬 흐름)

## 15. 합격 기준 (본 spec 의 done 정의)

- 사용자가 brand 선택 + 공실 spot 클릭 → 5~10분 후 시각화 표시
- 1000ag 시간대별 동선 + 색깔 구분
- vacancy spot 강조 + 매출/방문 통계 사이드 패널
- 시간 슬라이더 7시→24시 자유 진행
- 클릭 한 ag 의 자연어 대화 말풍선 (Mode B template)
- backend 회귀 테스트 통과
- frontend 회귀 테스트 통과

## 16. 학술 / Product 가치

- **사용자 vision 의 진짜 도달** — 본 plan execution 의 1순위 deliverable
- **본 plan #2 의 V1A r=0.95 결과의 시각적 demonstration** — 학술 발표 보조자료
- **사장님 영업 도구** — 가맹본부/사장님이 시각적으로 vacancy 평가 가능
- **시연 가능 product** — 학술 발표 + 투자 유치 + 졸업 발표 자료

## 17. 변경 로그

| 날짜 | 작성자 | 변경 |
|---|---|---|
| 2026-04-28 | A1 (찬영) | 초기 design — 옵션 C (3~4일, A1 단독). 4 backend endpoint + AbmPersonaMap vacancy 모드 + VacancyStatsPanel. dev 인프라 (AbmPersonaMap, AgentMapVisualizer, mapo_geo.json) 활용. |
