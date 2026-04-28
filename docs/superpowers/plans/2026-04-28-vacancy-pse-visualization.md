# Vacancy_PSE 시각화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** vacancy_pse 의 trajectory + visits + chats 데이터를 frontend AbmPersonaMap (dev 브랜치) 에 연결 — 사용자가 공실 spot 클릭 시 1000ag 마포 시각화 도달.

**Architecture:** backend 4 endpoint 신규 (job_id cache + threading 비동기 + polling) + frontend AbmPersonaMap 의 `mode="vacancy"` prop 추가 (기존 컴포넌트 확장). dev 인프라 (`AbmPersonaMap.tsx` 2146 줄, `mapo_geo.json`, 카카오맵 SDK) 활용.

**Tech Stack:** Python (FastAPI, threading.Thread), TypeScript/React (Vitest), 카카오맵 SDK.

**Spec:** `docs/superpowers/specs/2026-04-28-vacancy-pse-visualization-design.md` (commit b9a78a3)

**User git policy:** 사용자 메모리 "git commit/push 사전 확인 필수" — 각 commit 전 사용자 확인. ruff check + format 필수.

**중요 사전 사항**:
- dev 브랜치는 본 branch 기준 25 commit ahead
- AbmPersonaMap.tsx (2146 줄) 는 dev 에만 존재 → 본 plan 시작 전 **dev 에서 frontend 컴포넌트 cherry-pick 또는 dev merge** 필요
- 사용자 결정: A1 단독 frontend 작업 (강민 의존 X)

---

## File Structure

**신규 파일** (backend):
- `backend/tests/test_vacancy_evaluation_async.py` — cache + 비동기 + TTL 단위 테스트

**수정 파일** (backend):
- `backend/src/services/vacancy_evaluation_service.py` — `vacancy_pse_cache`, `run_vacancy_pse_async`, `cleanup_expired_cache` 신규 함수
- `backend/src/api/vacancy_evaluation.py` — 4 endpoint 신규 + 기존 `/single` 에 `collect_trajectory`, `dump_visits` 인자 추가

**수정 파일** (frontend, dev cherry-pick 후):
- `frontend/src/components/AbmPersonaMap.tsx` — `mode` prop 추가 + vacancy 모드 fetch 분기
- `frontend/src/components/VacancySpotMarker.tsx` — 신규 (펄스 효과)
- `frontend/src/components/VacancyStatsPanel.tsx` — 신규 (사이드 패널)

---

## Task 1: backend cache + 비동기 인프라

**Files:**
- Modify: `backend/src/services/vacancy_evaluation_service.py` (파일 끝에 추가)
- Test: `backend/tests/test_vacancy_evaluation_async.py` (신규)

- [ ] **Step 1.1: 단위 테스트 작성**

```python
# backend/tests/test_vacancy_evaluation_async.py
"""vacancy_pse 비동기 실행 + cache 단위 테스트."""

import time
from unittest.mock import patch

import pytest

from src.services.vacancy_evaluation_service import (
    cleanup_expired_cache,
    run_vacancy_pse_async,
    vacancy_pse_cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    vacancy_pse_cache.clear()
    yield
    vacancy_pse_cache.clear()


def test_run_async_returns_job_id():
    """run_vacancy_pse_async 즉시 job_id 반환 (시뮬은 background)."""
    spot = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}
    with patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse") as mock_pse:
        mock_pse.return_value = {"pse_summary": {"revenue_per_day": {"mean": 0}}}
        job_id = run_vacancy_pse_async(spot, "카페")
    assert isinstance(job_id, str)
    assert len(job_id) >= 16  # uuid
    assert job_id in vacancy_pse_cache


def test_async_status_running_then_done():
    """비동기 시작 시 'running', 시뮬 완료 후 'done'."""
    spot = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}
    with patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse") as mock_pse:
        mock_pse.return_value = {"pse_summary": {}, "narrative": "test"}
        job_id = run_vacancy_pse_async(spot, "카페")

    # max 5초 대기
    for _ in range(50):
        if vacancy_pse_cache[job_id]["status"] == "done":
            break
        time.sleep(0.1)

    assert vacancy_pse_cache[job_id]["status"] == "done"
    assert vacancy_pse_cache[job_id]["result"] is not None


def test_async_failed_on_exception():
    """vacancy_pse 예외 시 status='failed' + error message."""
    spot = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}
    with patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse") as mock_pse:
        mock_pse.side_effect = ValueError("test error")
        job_id = run_vacancy_pse_async(spot, "카페")

    for _ in range(50):
        if vacancy_pse_cache[job_id]["status"] == "failed":
            break
        time.sleep(0.1)

    assert vacancy_pse_cache[job_id]["status"] == "failed"
    assert "test error" in vacancy_pse_cache[job_id]["error"]


def test_cleanup_expired():
    """1시간 경과 job 제거."""
    vacancy_pse_cache["old_job"] = {"started_at": time.time() - 4000, "status": "done"}
    vacancy_pse_cache["new_job"] = {"started_at": time.time(), "status": "done"}
    cleanup_expired_cache(ttl_seconds=3600)
    assert "old_job" not in vacancy_pse_cache
    assert "new_job" in vacancy_pse_cache


def test_run_async_passes_collect_trajectory():
    """collect_trajectory=True / dump_visits=True 인자가 vacancy_pse 에 전달."""
    spot = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}
    with patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse") as mock_pse:
        mock_pse.return_value = {"pse_summary": {}}
        run_vacancy_pse_async(
            spot, "카페", collect_trajectory=True, dump_visits=True,
        )
        time.sleep(0.5)
        _, kwargs = mock_pse.call_args
        assert kwargs.get("collect_trajectory") is True
        assert kwargs.get("dump_visits") is True
```

- [ ] **Step 1.2: 테스트 실행 → fail 확인**

```bash
cd "/c/Users/804/Documents/final project"
python -m pytest backend/tests/test_vacancy_evaluation_async.py -v
```
Expected: FAIL with `ImportError: cannot import name 'run_vacancy_pse_async'`

- [ ] **Step 1.3: 비동기 인프라 구현**

`backend/src/services/vacancy_evaluation_service.py` 끝에 추가:

```python
import threading
import time
import uuid

# In-memory cache (TTL 1시간)
vacancy_pse_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()


def run_vacancy_pse_async(
    spot: dict,
    category: str,
    brand_name: str | None = None,
    n_seeds: int = 5,
    days: int = 1,
    with_cannibalization: bool = False,
    popularity_boost: float | None = None,
    collect_trajectory: bool = False,
    dump_visits: bool = False,
    use_dialog_templates: bool = True,
) -> str:
    """vacancy_pse 비동기 실행. job_id 즉시 반환, 결과는 cache 에 저장.

    Returns:
        uuid4 형식의 job_id. status/trajectory/visits/stores/chats 조회 시 사용.
    """
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

            menu_items = None
            if brand_name:
                from src.services import brand_menu_loader
                try:
                    menu_items = brand_menu_loader.load_brand_menu_items(brand_name)
                except (brand_menu_loader.BrandNotFoundError, brand_menu_loader.BrandMenuEmptyError) as e:
                    logger.warning(f"[async] brand menu fallback: {e}")

            result = evaluate_vacancy_pse(
                vacancy_spot=spot,
                category=category,
                n_seeds=n_seeds,
                days=days,
                with_cannibalization=with_cannibalization,
                popularity_boost=popularity_boost or 5.0,
                collect_trajectory=collect_trajectory,
                dump_visits=dump_visits,
                use_dialog_templates=use_dialog_templates,
                menu_items=menu_items,
            )
            with _cache_lock:
                vacancy_pse_cache[job_id]["status"] = "done"
                vacancy_pse_cache[job_id]["result"] = result
        except Exception as e:
            logger.exception(f"[async] vacancy_pse failed: job_id={job_id}")
            with _cache_lock:
                vacancy_pse_cache[job_id]["status"] = "failed"
                vacancy_pse_cache[job_id]["error"] = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return job_id


def cleanup_expired_cache(ttl_seconds: int = 3600) -> int:
    """만료된 job (TTL 초과) 제거. 주기적 호출 권장.

    Returns:
        제거된 job 수.
    """
    now = time.time()
    with _cache_lock:
        expired = [k for k, v in vacancy_pse_cache.items() if now - v["started_at"] > ttl_seconds]
        for k in expired:
            del vacancy_pse_cache[k]
    return len(expired)
```

- [ ] **Step 1.4: 테스트 실행 → pass 확인**

```bash
python -m pytest backend/tests/test_vacancy_evaluation_async.py -v
```
Expected: 5 tests PASS

- [ ] **Step 1.5: ruff + commit**

```bash
ruff check --fix backend/src/services/vacancy_evaluation_service.py backend/tests/test_vacancy_evaluation_async.py
ruff format backend/src/services/vacancy_evaluation_service.py backend/tests/test_vacancy_evaluation_async.py
```

사용자 확인 후:
```bash
git add backend/src/services/vacancy_evaluation_service.py backend/tests/test_vacancy_evaluation_async.py
git commit -m "feat(A1): vacancy_pse 비동기 실행 + in-memory cache (TTL 1h)"
```

---

## Task 2: 4 신규 endpoint (status / trajectory / visits / stores / chats)

**Files:**
- Modify: `backend/src/api/vacancy_evaluation.py` (4 endpoint 추가 + `/single` 인자 추가)
- Test: `backend/tests/test_vacancy_endpoints_visualization.py` (신규)

- [ ] **Step 2.1: 단위 테스트 작성**

```python
# backend/tests/test_vacancy_endpoints_visualization.py
"""4 신규 endpoint + /single 의 collect_trajectory 인자 테스트."""

import time

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.vacancy_evaluation_service import vacancy_pse_cache

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache():
    vacancy_pse_cache.clear()
    yield
    vacancy_pse_cache.clear()


def test_status_404_for_unknown_job():
    r = client.get("/vacancy-evaluation/nonexistent_uuid/status")
    assert r.status_code == 404


def test_status_running_then_done():
    """job 등록 후 status 조회."""
    vacancy_pse_cache["test_job"] = {
        "status": "running", "started_at": time.time(), "result": None, "error": None,
    }
    r = client.get("/vacancy-evaluation/test_job/status")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


def test_trajectory_returns_list():
    """job done 시 trajectory list 반환."""
    vacancy_pse_cache["test_job"] = {
        "status": "done",
        "started_at": time.time(),
        "result": {
            "trajectory": [{"agent_id": 1, "hour": 7, "lat": 37.55, "lon": 126.92, "dong": "서교동"}],
            "visits_events": [],
            "pse_summary": {},
        },
        "error": None,
    }
    r = client.get("/vacancy-evaluation/test_job/trajectory")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["trajectory"], list)
    assert body["trajectory"][0]["agent_id"] == 1


def test_visits_returns_events():
    vacancy_pse_cache["test_job"] = {
        "status": "done",
        "started_at": time.time(),
        "result": {
            "trajectory": [],
            "visits_events": [{"agent_id": 1, "store_id": "vacancy_0_서교동", "hour": 13, "spend": 5000}],
            "pse_summary": {},
        },
        "error": None,
    }
    r = client.get("/vacancy-evaluation/test_job/visits")
    assert r.status_code == 200
    assert r.json()["visits_events"][0]["spend"] == 5000


def test_running_job_returns_409():
    """아직 running 인 job 의 trajectory 호출 → 409 Conflict."""
    vacancy_pse_cache["test_job"] = {
        "status": "running", "started_at": time.time(), "result": None, "error": None,
    }
    r = client.get("/vacancy-evaluation/test_job/trajectory")
    assert r.status_code == 409


def test_failed_job_returns_500():
    vacancy_pse_cache["test_job"] = {
        "status": "failed", "started_at": time.time(), "result": None, "error": "test error",
    }
    r = client.get("/vacancy-evaluation/test_job/trajectory")
    assert r.status_code == 500
    assert "test error" in r.json()["detail"]
```

- [ ] **Step 2.2: 테스트 실행 → fail 확인**

```bash
python -m pytest backend/tests/test_vacancy_endpoints_visualization.py -v
```
Expected: FAIL with 404 (endpoint 미존재)

- [ ] **Step 2.3: 4 endpoint 구현**

`backend/src/api/vacancy_evaluation.py` 끝에 추가:

```python
from fastapi import HTTPException
from src.services.vacancy_evaluation_service import vacancy_pse_cache


@router.get("/{job_id}/status")
def get_job_status(job_id: str) -> dict:
    """Job 상태 조회 — running / done / failed."""
    job = vacancy_pse_cache.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "elapsed_seconds": int(__import__("time").time() - job["started_at"]),
        "error": job.get("error"),
    }


def _require_done_job(job_id: str) -> dict:
    job = vacancy_pse_cache.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    if job["status"] == "running":
        raise HTTPException(status_code=409, detail="job still running")
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "unknown error"))
    return job["result"]


@router.get("/{job_id}/trajectory")
def get_job_trajectory(job_id: str) -> dict:
    """trajectory list — agent 시간대별 위치 (collect_trajectory=True 시만)."""
    result = _require_done_job(job_id)
    return {
        "job_id": job_id,
        "status": "done",
        "trajectory": result.get("trajectory") or [],
        "n_agents": result.get("pse_summary", {}).get("visits_per_day", {}).get("n", 0),
    }


@router.get("/{job_id}/visits")
def get_job_visits(job_id: str) -> dict:
    """visits_events list — vacancy 매장 방문 (dump_visits=True 시만)."""
    result = _require_done_job(job_id)
    return {
        "job_id": job_id,
        "visits_events": result.get("visits_events") or [],
        "vacancy_id": result.get("vacancy_spot", {}).get("dong"),
    }


@router.get("/{job_id}/stores")
def get_job_stores(job_id: str) -> dict:
    """vacancy + 주변 매장 좌표 + 매출 (per_seed 의 매장 정보)."""
    result = _require_done_job(job_id)
    return {
        "job_id": job_id,
        "vacancy_spot": result.get("vacancy_spot", {}),
        "stores": result.get("stores_info", []),  # vacancy_pse 의 결과 stores 정보 (필요 시 추가 dump)
    }


@router.get("/{job_id}/chats")
def get_job_chats(job_id: str) -> dict:
    """archetype 별 자연어 대화 (Mode B template — visits_events 의 dialog 필드)."""
    result = _require_done_job(job_id)
    chats = []
    for ev in result.get("visits_events") or []:
        if "dialog" in ev:
            chats.append({
                "agent_id": ev["agent_id"],
                "hour": ev["hour"],
                "text": ev["dialog"],
            })
    return {
        "job_id": job_id,
        "chats": chats,
    }
```

- [ ] **Step 2.4: 기존 `/single` 에 인자 추가 (선택)**

```python
class VacancyEvaluateRequest(BaseModel):
    spot: VacancySpotIn
    category: str = ...
    n_seeds: int = 5
    days: int = 1
    with_cannibalization: bool = False
    popularity_boost: float | None = None
    collect_trajectory: bool = False    # ← 추가
    dump_visits: bool = False            # ← 추가
    async_mode: bool = False             # ← 추가, True 시 즉시 job_id 반환
```

`/single` POST handler 의 `async_mode=True` 시 `run_vacancy_pse_async` 호출 + job_id 반환:

```python
@router.post("/single")
def evaluate_single(req: VacancyEvaluateRequest):
    if req.async_mode:
        from src.services.vacancy_evaluation_service import run_vacancy_pse_async
        job_id = run_vacancy_pse_async(
            spot=req.spot.model_dump(),
            category=req.category,
            n_seeds=req.n_seeds,
            days=req.days,
            with_cannibalization=req.with_cannibalization,
            popularity_boost=req.popularity_boost,
            collect_trajectory=req.collect_trajectory,
            dump_visits=req.dump_visits,
        )
        return {"job_id": job_id, "status": "running"}
    # 기존 동기 path 그대로
    ...
```

- [ ] **Step 2.5: 테스트 실행 → pass 확인**

```bash
python -m pytest backend/tests/test_vacancy_endpoints_visualization.py -v
```
Expected: 6 tests PASS

회귀 확인:
```bash
python -m pytest backend/tests/ -k "vacancy" -v
```
Expected: 기존 vacancy 테스트 + 새 테스트 모두 통과

- [ ] **Step 2.6: ruff + commit**

```bash
ruff check --fix backend/src/api/vacancy_evaluation.py backend/tests/test_vacancy_endpoints_visualization.py
ruff format backend/src/api/vacancy_evaluation.py backend/tests/test_vacancy_endpoints_visualization.py
```

사용자 확인 후:
```bash
git add backend/src/api/vacancy_evaluation.py backend/tests/test_vacancy_endpoints_visualization.py
git commit -m "feat(A1): vacancy-evaluation 4 신규 endpoint (status/trajectory/visits/stores/chats)"
```

---

## Task 3: dev merge 또는 frontend 컴포넌트 cherry-pick

**Files:**
- 본 branch + dev 의 `frontend/` 디렉토리

> **사용자 결정 필요**: 본 branch 를 dev 에 merge 할지, 또는 dev 의 frontend 컴포넌트만 cherry-pick 할지.

- [ ] **Step 3.1: dev 변경 사항 확인**

```bash
cd "/c/Users/804/Documents/final project"
git fetch origin
git log --oneline origin/dev ^HEAD | head -30
git diff --stat HEAD origin/dev -- frontend/
```

- [ ] **Step 3.2: dev merge (권장 path)**

사용자 확인 후:
```bash
git merge origin/dev
# conflict 있으면 해결 후
git commit -m "merge: origin/dev — frontend AbmPersonaMap + simulator UI 통합"
```

대안: cherry-pick (특정 frontend commit 만):
```bash
git checkout origin/dev -- frontend/src/components/AbmPersonaMap.tsx
git checkout origin/dev -- frontend/src/components/AgentMapVisualizer.tsx
git checkout origin/dev -- frontend/src/assets/mapo_geo.json
git add frontend/
git commit -m "chore(A1): cherry-pick frontend 시각화 컴포넌트 (dev)"
```

- [ ] **Step 3.3: frontend dependencies 설치**

```bash
cd frontend
npm install
```

- [ ] **Step 3.4: frontend dev 환경 작동 확인**

```bash
cd frontend
npm run dev
```

브라우저에서 기존 `AbmPersonaMap` 페이지 작동 확인 (회귀 X).

---

## Task 4: AbmPersonaMap.tsx 의 mode prop 추가

**Files:**
- Modify: `frontend/src/components/AbmPersonaMap.tsx`

> **사용자 manual 작업** — frontend 사용자 본인 작업 영역. 본 task 는 가이드 outline 만 제공.

- [ ] **Step 4.1: AbmPersonaMap props interface 확장**

`frontend/src/components/AbmPersonaMap.tsx:89` 근처 (`AbmPersonaMapProps` 인터페이스):

```typescript
export interface AbmPersonaMapProps {
  // ... 기존 props ...
  mode?: 'general' | 'vacancy';   // ← 추가, default 'general'
  vacancyJobId?: string;          // ← mode='vacancy' 시 필요
  vacancySpot?: { dong: string; lat: number; lng: number };  // ← spot 강조용
}
```

- [ ] **Step 4.2: vacancy 모드 fetch 분기**

기존 `useEffect` 의 `fetch('/api/mapo/spots*')` 위치 (line 521 등) 에 mode 분기:

```typescript
useEffect(() => {
  if (mode === 'vacancy' && vacancyJobId) {
    // 4 endpoint 동시 fetch
    Promise.all([
      fetch(`/vacancy-evaluation/${vacancyJobId}/trajectory`).then(r => r.json()),
      fetch(`/vacancy-evaluation/${vacancyJobId}/visits`).then(r => r.json()),
      fetch(`/vacancy-evaluation/${vacancyJobId}/stores`).then(r => r.json()),
      fetch(`/vacancy-evaluation/${vacancyJobId}/chats`).then(r => r.json()),
    ]).then(([traj, visits, stores, chats]) => {
      setTrajectory(traj.trajectory);
      setVisits(visits.visits_events);
      setStores(stores.stores);
      setChats(chats.chats);
    });
  } else {
    // 기존 general 모드 fetch — /api/mapo/spots*
    fetch(`/api/mapo/spots-all?per_dong=3`)...
  }
}, [mode, vacancyJobId, targetDistrict]);
```

- [ ] **Step 4.3: 회귀 테스트 작성**

`frontend/src/components/__tests__/AbmPersonaMap.vacancy.test.tsx` (신규):

```typescript
import { render, screen } from '@testing-library/react';
import AbmPersonaMap from '../AbmPersonaMap';

describe('AbmPersonaMap', () => {
  it('renders default mode (general) without vacancyJobId', () => {
    render(<AbmPersonaMap targetDistrict="서교동" />);
    expect(screen.getByRole('region')).toBeInTheDocument();
  });

  it('renders vacancy mode with job_id', () => {
    render(<AbmPersonaMap mode="vacancy" vacancyJobId="test_uuid" />);
    expect(screen.getByRole('region')).toBeInTheDocument();
  });
});
```

- [ ] **Step 4.4: frontend 회귀 테스트 + ruff + prettier + commit**

```bash
cd frontend
npx prettier --write src/components/AbmPersonaMap.tsx
npx vitest run src/components/__tests__/AbmPersonaMap.vacancy.test.tsx
```

사용자 확인 후:
```bash
git add frontend/src/components/AbmPersonaMap.tsx frontend/src/components/__tests__/
git commit -m "feat(A1): AbmPersonaMap 에 mode='vacancy' prop 추가"
```

---

## Task 5: VacancySpotMarker 컴포넌트 (펄스 효과)

**Files:**
- Create: `frontend/src/components/VacancySpotMarker.tsx`

- [ ] **Step 5.1: VacancySpotMarker 구현**

```typescript
// frontend/src/components/VacancySpotMarker.tsx
import { useEffect, useRef } from 'react';

interface VacancySpotMarkerProps {
  map: any;  // 카카오맵 인스턴스
  lat: number;
  lng: number;
  radiusM?: number;  // default 500m
}

/** vacancy 매장 위치 강조 — 빨간 펄스 + 반경 원. */
export default function VacancySpotMarker({ map, lat, lng, radiusM = 500 }: VacancySpotMarkerProps) {
  const markerRef = useRef<any>(null);
  const circleRef = useRef<any>(null);

  useEffect(() => {
    if (!map || typeof window === 'undefined' || !(window as any).kakao) return;
    const kakao = (window as any).kakao;

    const position = new kakao.maps.LatLng(lat, lng);

    // 펄스 마커 (CSS 애니메이션)
    const content = `
      <div style="
        width: 24px; height: 24px;
        background: #E45756;
        border: 3px solid white;
        border-radius: 50%;
        animation: pulse 1.5s infinite;
        box-shadow: 0 0 8px rgba(228, 87, 86, 0.8);
      "></div>
      <style>
        @keyframes pulse {
          0% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.3); opacity: 0.6; }
          100% { transform: scale(1); opacity: 1; }
        }
      </style>
    `;
    markerRef.current = new kakao.maps.CustomOverlay({
      position, content, yAnchor: 0.5, xAnchor: 0.5,
    });
    markerRef.current.setMap(map);

    // 반경 500m 원
    circleRef.current = new kakao.maps.Circle({
      center: position,
      radius: radiusM,
      strokeWeight: 2,
      strokeColor: '#E45756',
      strokeOpacity: 0.6,
      strokeStyle: 'dashed',
      fillColor: '#E45756',
      fillOpacity: 0.05,
    });
    circleRef.current.setMap(map);

    return () => {
      markerRef.current?.setMap(null);
      circleRef.current?.setMap(null);
    };
  }, [map, lat, lng, radiusM]);

  return null;
}
```

- [ ] **Step 5.2: AbmPersonaMap 에서 사용**

```typescript
// AbmPersonaMap.tsx 의 render 부분
import VacancySpotMarker from './VacancySpotMarker';

{mode === 'vacancy' && vacancySpot && map && (
  <VacancySpotMarker map={map} lat={vacancySpot.lat} lng={vacancySpot.lng} />
)}
```

- [ ] **Step 5.3: prettier + commit**

```bash
cd frontend
npx prettier --write src/components/VacancySpotMarker.tsx src/components/AbmPersonaMap.tsx
```

사용자 확인 후:
```bash
git add frontend/src/components/VacancySpotMarker.tsx frontend/src/components/AbmPersonaMap.tsx
git commit -m "feat(A1): VacancySpotMarker — vacancy spot 펄스 마커 + 반경 500m 원"
```

---

## Task 6: VacancyStatsPanel 사이드 패널

**Files:**
- Create: `frontend/src/components/VacancyStatsPanel.tsx`

- [ ] **Step 6.1: VacancyStatsPanel 구현**

```typescript
// frontend/src/components/VacancyStatsPanel.tsx
interface PseSummary {
  visits_per_day: { mean: number; ci95: number };
  revenue_per_day: { mean: number; ci95: number };
  vacancy_vs_avg_visits_ratio: { mean: number; ci95: number };
  cannibalization_pct?: { mean: number; ci95: number };
  dong_net_growth_pct?: { mean: number; ci95: number };
}

interface VacancyStatsPanelProps {
  summary: PseSummary | null;
  vacancySpot: { dong: string; category: string };
  loading?: boolean;
}

export default function VacancyStatsPanel({ summary, vacancySpot, loading }: VacancyStatsPanelProps) {
  if (loading || !summary) {
    return (
      <div className="vacancy-stats-panel">
        <h3>{vacancySpot.dong} {vacancySpot.category} 평가</h3>
        <p>시뮬 진행 중...</p>
      </div>
    );
  }

  const visitsPerQuarter = summary.visits_per_day.mean * 90;
  const revenuePerQuarter = summary.revenue_per_day.mean * 90;
  const revenuePerYear = summary.revenue_per_day.mean * 365;

  return (
    <div className="vacancy-stats-panel" style={{ padding: 16, background: '#f8f9fa', borderRadius: 8 }}>
      <h3>{vacancySpot.dong} {vacancySpot.category} 평가</h3>
      <ul style={{ listStyle: 'none', padding: 0 }}>
        <li>📅 일평균 방문: {summary.visits_per_day.mean.toFixed(1)} ± {summary.visits_per_day.ci95.toFixed(1)} 명</li>
        <li>📅 일평균 매출: {(summary.revenue_per_day.mean / 10000).toFixed(0)} ± {(summary.revenue_per_day.ci95 / 10000).toFixed(0)} 만원</li>
        <li>📊 분기 추정 방문: {visitsPerQuarter.toFixed(0)} 명</li>
        <li>💰 분기 추정 매출: {(revenuePerQuarter / 1e8).toFixed(2)} 억원</li>
        <li>💰 연 추정 매출: {(revenuePerYear / 1e8).toFixed(2)} 억원</li>
        <li>⚖️ 동 평균 대비: {summary.vacancy_vs_avg_visits_ratio.mean.toFixed(1)} ± {summary.vacancy_vs_avg_visits_ratio.ci95.toFixed(1)} 배</li>
        {summary.cannibalization_pct && (
          <li>🔻 카니발 (반경 500m): {summary.cannibalization_pct.mean.toFixed(1)} ± {summary.cannibalization_pct.ci95.toFixed(1)}%</li>
        )}
        {summary.dong_net_growth_pct && (
          <li>📈 동 시장 성장: {summary.dong_net_growth_pct.mean.toFixed(2)} ± {summary.dong_net_growth_pct.ci95.toFixed(2)}%</li>
        )}
      </ul>
    </div>
  );
}
```

- [ ] **Step 6.2: AbmPersonaMap 에서 사이드 패널 추가**

```typescript
// AbmPersonaMap.tsx 의 layout 안
import VacancyStatsPanel from './VacancyStatsPanel';

{mode === 'vacancy' && (
  <VacancyStatsPanel summary={pseSummary} vacancySpot={...} loading={!pseSummary} />
)}
```

- [ ] **Step 6.3: prettier + commit**

```bash
cd frontend
npx prettier --write src/components/VacancyStatsPanel.tsx src/components/AbmPersonaMap.tsx
```

사용자 확인 후:
```bash
git add frontend/src/components/VacancyStatsPanel.tsx frontend/src/components/AbmPersonaMap.tsx
git commit -m "feat(A1): VacancyStatsPanel — 매출/방문 통계 사이드 패널"
```

---

## Task 7: 통합 e2e 검증

**Files:** 없음 (실행만)

- [ ] **Step 7.1: backend dev server 시작**

```bash
cd backend
uvicorn src.main:app --reload --port 8001
```

- [ ] **Step 7.2: frontend dev server 시작**

```bash
cd frontend
npm run dev
```

- [ ] **Step 7.3: vacancy_pse 시뮬 실행 + job_id 발급**

브라우저 또는 curl 로:
```bash
curl -X POST http://localhost:8001/vacancy-evaluation/single \
  -H "Content-Type: application/json" \
  -d '{
    "spot": {"dong": "서교동", "lat": 37.5544, "lon": 126.9220},
    "category": "카페",
    "n_seeds": 1,
    "days": 1,
    "collect_trajectory": true,
    "dump_visits": true,
    "async_mode": true
  }'
# Expected: {"job_id": "...", "status": "running"}
```

- [ ] **Step 7.4: status polling**

```bash
curl http://localhost:8001/vacancy-evaluation/{job_id}/status
# 5~10분 후 status="done" 확인
```

- [ ] **Step 7.5: frontend 시각화 확인**

브라우저에서 `http://localhost:5173/?vacancyJobId={job_id}` 같은 query param 또는 컴포넌트 prop 으로 시각화 페이지 진입.

확인 사항:
- 1000ag dot 시간대별 표시
- vacancy spot 빨간 펄스 마커 + 반경 500m 원
- 시간 슬라이더 7시→24시 진행
- VacancyStatsPanel 의 매출/방문 통계 표시

- [ ] **Step 7.6: 사용자 manual 검증 + 결과 보고**

스크린샷 또는 짧은 영상 (옵션) 으로 시각화 흐름 검증.

---

## Self-Review

**Spec coverage check** (spec 섹션별):
- 섹션 5 (아키텍처) → Task 1, 2, 4 ✅
- 섹션 6 (컴포넌트) → Task 1~6 ✅
- 섹션 7 (데이터 흐름) → Task 1, 2 ✅
- 섹션 8 (UI/UX 흐름) → Task 4, 5, 6 ✅
- 섹션 9 (오류 처리) → Task 2 (404/409/500) ✅
- 섹션 10 (테스트) → Task 1, 2 backend 테스트, Task 4 frontend 테스트 ✅
- 섹션 14 (구현 순서 10 step) → Task 1~7 ✅
- 섹션 15 (합격 기준) → Task 7 사용자 manual 검증 ✅

**Placeholder scan**: 모든 step 에 구체 코드/명령. TBD/TODO 없음. ✅

**Type consistency**: `vacancy_pse_cache: dict[str, dict]`, `job_id: str`, `mode: 'general' | 'vacancy'`, `VacancySpotMarkerProps` 명명 일관. ✅

**중요 사전 사항**: Task 3 의 dev merge 가 필수. 사용자 확인 후 진행.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-28-vacancy-pse-visualization.md`. 7 task × 평균 4~6 step.

**Backend tasks (1, 2, 7)**: Subagent-driven 가능.
**Frontend tasks (4, 5, 6)**: 사용자 manual 작업 권장 (frontend 본인 영역, dev 인프라 활용).
**Task 3 (dev merge)**: 사용자 결정 필요.

Two execution options:

**1. Subagent-Driven (recommended for backend)** - Task 1, 2 만 subagent dispatch, Task 4~6 사용자 manual.

**2. Inline + Manual mix** - 현재 세션 batch.

Which approach?
