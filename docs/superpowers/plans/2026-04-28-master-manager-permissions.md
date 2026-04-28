# Master/Manager Permission + Oversight + Auto-Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** manager 가 우상단 헤더 아이콘 클릭 시 `/simulator` 무한 cycle 버그를 해결하고, master 가 팀원 시뮬을 모니터링할 수 있게 하며, 회원가입 직후 자동 로그인을 적용한다.

**Architecture:** ProtectedRoute 의 master 전용 분기를 풀어 manager 도 `/hq` 에 접근하게 하고 (HQCommandCenter 내부 분기 활용), GlobalNav handleItemClick 을 manager 분기로 갈래낸다. backend 권한 분기는 이미 완료 상태라 SELECT JOIN + 응답 스키마 1필드 + UI 배지만 추가하면 (ii) Master Oversight 가 즉시 충족된다. signup 라우트 두 개에 login 동일 패턴 access_token 발급을 더해 자동 로그인 처리.

**Tech Stack:** React 18 + TypeScript + Vite (frontend), FastAPI + Pydantic v2 + SQLAlchemy + PostgreSQL (backend), pytest (backend tests), JWT HS256 (auth)

**Spec:** `docs/superpowers/specs/2026-04-28-master-manager-permission-design.md`

**Branch:** 권장 신규 브랜치 `feature/master-manager-permissions` (현재 `feature/demographic-depth-agent` 와 분리). 사용자 결정 필요.

**Commit Policy:** 메모리 `feedback_commit_policy.md` 에 따라 사용자 명시 승인 시만 커밋. 각 task 의 Step "Commit" 은 commit 메시지 초안만 준비하고 사용자 신호 받기.

---

## File Structure

### Backend (3 files)
- `backend/src/schemas/simulation_history.py` — `manager_name: Optional[str]` 필드 추가 (Pydantic 응답 스키마)
- `backend/src/services/simulation_history_service.py` — `list_history` 의 SELECT 절에 `sh.manager_id, mu.contact_name AS manager_name` + `LEFT JOIN manager_users mu` 추가, WHERE/SELECT 컬럼명에 `sh.` prefix
- `backend/src/main.py` — `/auth/signup` (line 790-798) + `/auth/manager/signup` (line 881+) 라우트에 access_token 발급 (login 라우트 line 819-825 동일 패턴)

### Frontend (6 files)
- `frontend/src/types/simulationHistory.ts` — `manager_name?: string | null` 필드 추가
- `frontend/src/components/SimulationHistory/HistoryCard.tsx` — `useAuth` 추가, master 시 카드 메타 영역에 "by 매니저명" 배지
- `frontend/src/App.tsx:4419` — `<ProtectedRoute requireRole="master">` → `<ProtectedRoute>` (1줄)
- `frontend/src/components/GlobalNav.tsx:115-137` — `handleItemClick` 안에 `isManager` 분기 + Folder path 갈래
- `frontend/src/pages/JoinUs/components/SignupForm.tsx:172-177` — `useAuth` import + `auth.login(...)` 호출
- `frontend/src/pages/JoinUs/components/ManagerSignupForm.tsx:138~` — 동일 패턴

### Backend Tests (1 file)
- `backend/tests/test_simulation_history_service.py` — `list_history` master role 시 응답에 `manager_name` 포함되는지 검증 (mock-based)

---

## Task Order Rationale

Backend 가 Frontend 응답 의존성 → backend 먼저. signup 변경은 독립적이라 마지막. UI 변경 (라우트/헤더) 은 빈번한 시각 검증 필요해서 frontend 는 작은 단위로 분리.

순서: 1→2→3 (backend oversight) / 4→5 (frontend types+card) / 6→7 (frontend route+nav) / 8→9 (auto-login) / 10 (정합성) / 11 (브라우저)

---

## Tasks

### Task 1: Backend — schema 에 `manager_name` 필드 추가

**Files:**
- Modify: `backend/src/schemas/simulation_history.py` (line 47-53 부근 `SimulationHistoryListItem`)

- [ ] **Step 1: 현재 스키마 확인**

Read: `backend/src/schemas/simulation_history.py:40-65` 구간. `SimulationHistoryListItem` (응답 dict 의 `items[]` 항목용 모델) 위치 확인.

- [ ] **Step 2: `manager_id` 와 `manager_name` 두 필드 추가**

**중요 (2026-04-28 발견)**: `SimulationHistoryListItem` 클래스에 원래 `manager_id` 필드 자체가 없었음. frontend HistoryCard 가 `item.manager_id !== user?.id` 로 본인 시뮬 분기 (Task 5) 하려면 두 필드 모두 필요.

`SimulationHistoryListItem` 클래스 안 (`id: int` 다음 줄) 에 두 줄 추가:

```python
class SimulationHistoryListItem(BaseModel):
    id: int
    manager_id: UUID  # Task 2 list_history SELECT 가 sh.manager_id 노출 → frontend 본인/타인 분기용
    manager_name: Optional[str] = None  # master 시 "by 매니저명" 표시용. 본인 시뮬은 None
    client_name: str
    # ... 기존 필드 그대로
```

`from typing import Optional` 과 `from uuid import UUID` import 가 이미 있는지 확인하고 없으면 상단에 추가. SimulationHistoryDetail 가 ListItem 을 상속하면 detail 도 자동 포함됨 — Detail 의 redundant `manager_id: UUID` 라인 제거 가능 (cleanup, 동작 동일).

- [ ] **Step 3: ruff 검증**

Run:
```bash
cd /c/mapo-franchise-simulator
ruff check backend/src/schemas/simulation_history.py
ruff format backend/src/schemas/simulation_history.py
```

Expected: `All checks passed!` + `1 file left unchanged` 또는 `1 file reformatted`

- [ ] **Step 4: Commit (사용자 승인 후)**

```bash
git add backend/src/schemas/simulation_history.py
git commit -m "feat(api): SimulationHistoryListItem 에 manager_name 필드 추가

master 가 자기 워크스페이스 매니저 시뮬을 카드에서 식별할 수 있도록
응답 스키마에 manager_name Optional 필드 추가. SELECT JOIN 추가는 별 커밋.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Backend — `list_history` SELECT 에 manager_name JOIN

**Files:**
- Modify: `backend/src/services/simulation_history_service.py:88-135` (`list_history` 함수)

- [ ] **Step 1: 현재 SQL 확인**

Read: `backend/src/services/simulation_history_service.py:80-145`. 핵심:
- line 91: master 권한 분기 `manager_id = :manager_id OR manager_id IN (SELECT id FROM manager_users WHERE owner_id = :manager_id)`
- line 94: manager 본인만 `manager_id = :manager_id`
- line 123-134: SELECT/FROM 절 (현재 `manager_id` 미선택)

- [ ] **Step 2: WHERE 절의 `manager_id` 컬럼 참조에 `sh.` prefix 추가**

JOIN 추가하면 ambiguous column 발생 위험. `where = [...]` 안의 `manager_id` 를 `sh.manager_id` 로 교체:

```python
if role == "master":
    where = [
        "(sh.manager_id = :manager_id OR sh.manager_id IN (SELECT id FROM manager_users WHERE owner_id = :manager_id))"
    ]
else:
    where = ["sh.manager_id = :manager_id"]
```

(client_name 등 다른 컬럼은 simulation_history 에만 있어 prefix 불필요)

- [ ] **Step 3: SELECT/FROM 변경**

line 123-134 의 SELECT 블록을 다음으로 교체:

```python
rows = conn.execute(
    text(
        f"""
        SELECT sh.id, sh.client_name, sh.district, sh.brand_name, sh.business_type,
               sh.ai_verdict_summary, sh.market_entry_signal, sh.created_at,
               sh.manager_id, mu.contact_name AS manager_name
        FROM simulation_history sh
        LEFT JOIN manager_users mu ON mu.id = sh.manager_id
        WHERE {where_sql}
        ORDER BY sh.{order_sql}
        LIMIT :limit OFFSET :offset
        """
    ),
    params,
).fetchall()
```

ORDER BY 의 `created_at` 도 `sh.` prefix 필요 (`sh.{order_sql}`). 또는 order_sql 자체를 `sh.created_at DESC` 로 직접 갱신:

```python
order_sql = "sh.created_at DESC" if sort == "created_at_desc" else "sh.client_name ASC"
```

후자 (order_sql 갱신) 가 더 명시적.

- [ ] **Step 4: COUNT 쿼리도 prefix 점검**

line 118-121 의 COUNT 쿼리:

```python
total = conn.execute(
    text(f"SELECT COUNT(*) FROM simulation_history sh WHERE {where_sql}"),
    params,
).scalar_one()
```

`FROM simulation_history sh` 별칭 추가 (where_sql 이 sh. 사용하므로).

- [ ] **Step 5: 응답 dict 변환 부분 점검**

line 137~ (return 부분) 의 `items` 리스트 만드는 코드에서 row 의 `manager_name` 을 dict 에 포함시키는지 확인. 만약 `dict(row._mapping)` 패턴이면 자동 포함, `[r.id, r.client_name, ...]` 패턴이면 명시 추가 필요. 현재 코드 확인 후:

```python
"items": [dict(r._mapping) for r in rows]
```

또는 명시:

```python
"items": [
    {
        "id": r.id,
        "manager_id": r.manager_id,
        "manager_name": r.manager_name,
        "client_name": r.client_name,
        # ... 기존
    }
    for r in rows
]
```

- [ ] **Step 6: ruff 검증**

```bash
cd /c/mapo-franchise-simulator
ruff check backend/src/services/simulation_history_service.py
ruff format backend/src/services/simulation_history_service.py
```

- [ ] **Step 7: Commit (승인 후)**

```bash
git add backend/src/services/simulation_history_service.py
git commit -m "feat(api): list_history 가 manager_name 을 응답에 포함

LEFT JOIN manager_users → master 가 카드에서 어느 매니저가 만든 시뮬인지
바로 식별 가능. WHERE/SELECT 컬럼 ambiguity 방지를 위해 sh./mu. alias 사용.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Backend — `list_history` mock test 추가

**Files:**
- Create: `backend/tests/test_simulation_history_service.py`

- [ ] **Step 1: failing test 작성**

```python
"""simulation_history_service.list_history 응답 검증.

master role 시 LEFT JOIN manager_users 가 결과에 포함되는지를 mock-based 로 확인.
실 DB 의존 0 — sqlalchemy execute 결과를 직접 mock.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.services import simulation_history_service as svc


def _make_row(**kwargs):
    """sqlalchemy Row mock — _mapping 속성 + attribute 접근 둘 다 가능."""
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    row._mapping = kwargs
    return row


def test_list_history_master_includes_manager_name():
    """master 호출 시 응답 items 에 manager_name 필드가 포함된다."""
    master_id = uuid4()
    sample_row = _make_row(
        id=1,
        manager_id=uuid4(),
        manager_name="홍길동",
        client_name="강남 카페",
        district="역삼동",
        brand_name="스타벅스",
        business_type="카페",
        ai_verdict_summary="positive",
        market_entry_signal="green",
        created_at="2026-04-28T10:00:00",
    )

    fake_conn = MagicMock()
    fake_conn.execute.return_value.scalar_one.return_value = 1
    fake_conn.execute.return_value.fetchall.return_value = [sample_row]

    fake_engine = MagicMock()
    fake_engine.connect.return_value.__enter__.return_value = fake_conn

    with patch.object(svc, "get_sync_engine", return_value=fake_engine):
        result = svc.list_history(
            manager_id=master_id,
            role="master",
            owner_id=None,
            client_name=None,
            from_date=None,
            to_date=None,
            page=1,
            size=20,
            sort="created_at_desc",
        )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["manager_name"] == "홍길동"
    assert item["client_name"] == "강남 카페"


def test_list_history_manager_only_self():
    """manager 호출 시 WHERE 절에 sh.manager_id = :manager_id 단일 조건만."""
    manager_id = uuid4()

    fake_conn = MagicMock()
    fake_conn.execute.return_value.scalar_one.return_value = 0
    fake_conn.execute.return_value.fetchall.return_value = []

    fake_engine = MagicMock()
    fake_engine.connect.return_value.__enter__.return_value = fake_conn

    with patch.object(svc, "get_sync_engine", return_value=fake_engine):
        svc.list_history(
            manager_id=manager_id,
            role="manager",
            owner_id=None,
            client_name=None,
            from_date=None,
            to_date=None,
            page=1,
            size=20,
            sort="created_at_desc",
        )

    # SELECT 호출 2번 (COUNT + main). 둘 다 sh.manager_id = :manager_id 포함, OR 분기 미포함.
    sql_calls = [str(c.args[0]) for c in fake_conn.execute.call_args_list]
    main_sql = next(s for s in sql_calls if "LEFT JOIN" in s)
    assert "sh.manager_id = :manager_id" in main_sql
    assert "owner_id = :manager_id" not in main_sql  # master 분기 미적용
```

- [ ] **Step 2: 실 fail 확인 (Task 2 완료 전 RUN, Task 2 후 PASS 예상)**

```bash
cd /c/mapo-franchise-simulator/backend
python -m pytest tests/test_simulation_history_service.py -v
```

Expected (Task 2 미적용 시): `manager_name` KeyError / SELECT 에 LEFT JOIN 없음.
Expected (Task 2 적용 후): `2 passed`.

- [ ] **Step 3: ruff 검증**

```bash
ruff check backend/tests/test_simulation_history_service.py
ruff format backend/tests/test_simulation_history_service.py
```

- [ ] **Step 4: Commit (승인 후)**

```bash
git add backend/tests/test_simulation_history_service.py
git commit -m "test(api): list_history mock test — master manager_name 포함 + manager 격리 검증

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Frontend — `simulationHistory.ts` 에 `manager_name` 타입 추가

**Files:**
- Modify: `frontend/src/types/simulationHistory.ts`

- [ ] **Step 1: 현재 타입 확인**

Read: `frontend/src/types/simulationHistory.ts`. `SimulationHistoryItem` 또는 `SimulationHistoryListItem` 인터페이스 위치 확인.

- [ ] **Step 2: `manager_id` + `manager_name` 두 필드 추가**

**중요 (2026-04-28 발견)**: 현재 `SimulationHistoryItem` 에는 `manager_id` 자체가 없음 (Detail 만 보유). backend `SimulationHistoryListItem` 변경에 맞춰 frontend Item 에도 두 필드 모두 추가.

```ts
export interface SimulationHistoryItem {
  id: number;
  manager_id: string;  // backend SimulationHistoryListItem.manager_id 와 동기화 — frontend HistoryCard 본인/타인 분기용
  manager_name?: string | null;  // master 시 "by 매니저명" 표시용. 본인 시뮬은 null
  client_name: string;
  // ... 기존
}
```

`SimulationHistoryDetail extends SimulationHistoryItem` 이므로 Detail 의 redundant `manager_id: string` 라인 제거 가능 (cleanup, 동작 동일).

- [ ] **Step 3: tsc 검증**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
```

Expected: EXIT=0 (HistoryCard 가 아직 manager_name 안 쓰므로 에러 없음)

- [ ] **Step 4: prettier**

```bash
npx prettier --write src/types/simulationHistory.ts
```

- [ ] **Step 5: Commit (승인 후)**

```bash
git add frontend/src/types/simulationHistory.ts
git commit -m "feat(types): SimulationHistoryItem 에 manager_name optional 필드 추가

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Frontend — `HistoryCard` 에 "by 매니저명" 배지

**Files:**
- Modify: `frontend/src/components/SimulationHistory/HistoryCard.tsx` (line 90-99 부근 메타 영역)

- [ ] **Step 1: useAuth import 추가**

상단 import 블록에:

```ts
import { useAuth } from '../../auth/AuthContext';
```

- [ ] **Step 2: 컴포넌트 안에서 isMaster 변수 + 배지 렌더**

`HistoryCard` 함수 시작 부분 (line 56 부근, `const signalKey = ...` 직전) 에 추가:

```ts
const { user } = useAuth();
const isMaster = user?.role === 'master';
const showManagerBadge = isMaster && item.manager_name && item.manager_id !== user?.id;
```

(본인 시뮬 — manager_id 가 본인이면 배지 미표시)

- [ ] **Step 3: 배지 렌더 위치 — 메타 영역 (line 90-95 부근) 옆에 추가**

`<span className="ml-1 rounded bg-stone-900/60 px-1.5 py-0.5 text-[10px] font-mono text-indigo-400">{docId}</span>` 다음 줄에:

```tsx
{showManagerBadge && (
  <span className="ml-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-bold text-cyan-300">
    by {item.manager_name}
  </span>
)}
```

색상은 기존 디자인 토큰 (cyan = TCN/팀원 시멘틱) 일관 사용.

- [ ] **Step 4: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationHistory/HistoryCard.tsx
```

Expected: EXIT=0

- [ ] **Step 5: Commit (승인 후)**

```bash
git add frontend/src/components/SimulationHistory/HistoryCard.tsx
git commit -m "feat(history): master 시 카드에 'by 매니저명' 배지 추가

본인 시뮬은 미표시 (manager_id === user.id). 디자인 토큰 cyan 사용 (팀원 시멘틱).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Frontend — `App.tsx` ProtectedRoute requireRole 제거

**Files:**
- Modify: `frontend/src/App.tsx:4418-4422` (`/hq` Route)

- [ ] **Step 1: 현재 라우트 정의 확인**

Read: `frontend/src/App.tsx:4418-4422`

```tsx
<Route
  path="/hq"
  element={
    <ProtectedRoute requireRole="master">
      <HQCommandCenter />
    </ProtectedRoute>
  }
/>
```

- [ ] **Step 2: requireRole 제거**

```tsx
<Route
  path="/hq"
  element={
    <ProtectedRoute>
      <HQCommandCenter />
    </ProtectedRoute>
  }
/>
```

근거: HQCommandCenter 내부 분기 (`HQCommandCenter.tsx:65-67`) 가 `user?.role === 'manager'` 시 ManagerWorkspace 자동 렌더, master 면 MasterCommandCenter. ManagerWorkspace 자체에 fallback (`HQCommandCenter.tsx:2096-2107`) 있어 manager 가 `?tab=team` 등 master 메뉴 입력 시 안전 처리.

- [ ] **Step 3: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/App.tsx
```

- [ ] **Step 4: Commit (승인 후)**

```bash
git add frontend/src/App.tsx
git commit -m "fix(route): /hq 의 requireRole=master 제거 — manager 진입 허용

HQCommandCenter 내부에서 user.role 분기로 ManagerWorkspace 자동 렌더.
GlobalNav 우상단 아이콘 무한 simulate cycle 의 root cause 해결.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Frontend — `GlobalNav.tsx` handleItemClick manager 분기

**Files:**
- Modify: `frontend/src/components/GlobalNav.tsx:115-137` (`handleItemClick`)

- [ ] **Step 1: 현재 함수 확인**

Read: `frontend/src/components/GlobalNav.tsx:115-137`

```ts
const handleItemClick = (index: number, type: NavItemType) => {
  if (!isLoggedIn) {
    nav('/login');
    return;
  }
  setActiveIndex(index);
  if (type === 'folder') {
    setOpenDropdown(null);
    nav('/hq?tab=pipeline');
  } else if (type === 'settings') {
    setOpenDropdown(null);
    nav('/hq?tab=mypage');
  } else if (type === 'bell') {
    setOpenDropdown(openDropdown === 'bell' ? null : 'bell');
  } else if (type === 'user') {
    setOpenDropdown(null);
    nav('/hq?tab=history');
  }
};
```

- [ ] **Step 2: isManager 변수 + Folder path 갈래**

`const handleItemClick = ...` 안에 `setActiveIndex(index);` 다음 줄에 추가:

```ts
const isManager = user?.role === 'manager';
```

그리고 Folder 분기 변경 (User/Settings 는 master/manager 동일 path 라 변경 없음):

```ts
if (type === 'folder') {
  setOpenDropdown(null);
  nav(isManager ? '/hq?tab=workspace' : '/hq?tab=pipeline');
}
```

전체 함수 최종 형태:

```ts
const handleItemClick = (index: number, type: NavItemType) => {
  if (!isLoggedIn) {
    nav('/login');
    return;
  }

  setActiveIndex(index);
  const isManager = user?.role === 'manager';

  if (type === 'folder') {
    setOpenDropdown(null);
    nav(isManager ? '/hq?tab=workspace' : '/hq?tab=pipeline');
  } else if (type === 'settings') {
    setOpenDropdown(null);
    nav('/hq?tab=mypage');
  } else if (type === 'bell') {
    setOpenDropdown(openDropdown === 'bell' ? null : 'bell');
  } else if (type === 'user') {
    setOpenDropdown(null);
    nav('/hq?tab=history');
  }
};
```

- [ ] **Step 3: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/GlobalNav.tsx
```

- [ ] **Step 4: Commit (승인 후)**

```bash
git add frontend/src/components/GlobalNav.tsx
git commit -m "feat(nav): GlobalNav handleItemClick manager 분기 — Folder=workspace

manager 가 Folder 클릭 시 /hq?tab=pipeline 대신 /hq?tab=workspace (의뢰 placeholder + 본인 시뮬).
User/Settings 는 ManagerWorkspace 가 동일 path 처리하므로 분기 불필요.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Backend — signup 라우트 두 개에 access_token 발급

**Files:**
- Modify: `backend/src/main.py:790-798` (`/auth/signup`)
- Modify: `backend/src/main.py:881-...` (`/auth/manager/signup`)

- [ ] **Step 1: master signup 라우트 변경**

`backend/src/main.py:790-798` 의 signup 함수를 다음으로 교체:

```python
@app.post("/auth/signup")
async def signup(req: SignupRequest):
    """회원가입 — 사업자 검증 + 브랜드 매핑 + DB 저장 + JWT 발급."""
    from src.services.jwt_auth import create_access_token  # 지역 import (login 패턴 동일)

    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await auth.signup(req.model_dump())
        if result.get("status") == "success" and result.get("user"):
            u = result["user"]
            result["access_token"] = create_access_token(
                user_id=str(u["id"]),
                role="master",
                email=u.get("email", req.email),
            )
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 2: manager signup 라우트 변경**

`backend/src/main.py:881~` 의 manager_signup 함수도 동일 패턴으로 변경 (role="manager" 차이만):

```python
@app.post("/auth/manager/signup")
async def manager_signup(req: ManagerSignupRequest):
    """매니저 회원가입 — 초대코드로 팀장 기업정보 자동 상속 + JWT 발급."""
    from src.services.jwt_auth import create_access_token

    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await auth.manager_signup(req.model_dump())  # 또는 실 함수명 확인
        if result.get("status") == "success" and result.get("user"):
            u = result["user"]
            result["access_token"] = create_access_token(
                user_id=str(u["id"]),
                role="manager",
                email=u.get("email", req.email),
            )
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

(실 manager_signup 함수명/시그니처 코드에서 한 번 더 확인)

- [ ] **Step 3: ruff 검증**

```bash
cd /c/mapo-franchise-simulator
ruff check backend/src/main.py
ruff format backend/src/main.py
```

E402 경고 18개 (기존 langchain import 순서 이슈) 는 무시. 신규 에러 없는지만 확인.

- [ ] **Step 4: Commit (승인 후)**

```bash
git add backend/src/main.py
git commit -m "feat(auth): signup 라우트 두 개에 JWT access_token 발급

회원가입 직후 자동 로그인 가능. login 라우트(line 819-825)와 동일 패턴.
master signup → role='master', manager signup → role='manager'.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Frontend — `SignupForm.tsx` 자동 로그인 호출

**Files:**
- Modify: `frontend/src/pages/JoinUs/components/SignupForm.tsx:172-177` (handleSubmit success 분기)

- [ ] **Step 1: useAuth import 추가**

상단 import 블록에:

```ts
import { useAuth } from '../../../auth/AuthContext';
```

- [ ] **Step 2: 컴포넌트 안에서 auth 변수 + login 호출**

`export default function SignupForm(...)` 안 첫 줄에 추가:

```ts
const auth = useAuth();
```

handleSubmit 의 success 분기 (line 172-177) 변경:

```ts
const data = await res.json();
if (data.status === 'success') {
  if (data.access_token && data.user) {
    auth.login(data.user, data.brand ?? null, data.access_token);
  }
  onSuccess();
} else {
  setSubmitError(data.message || '가입 중 오류가 발생했습니다.');
}
```

- [ ] **Step 3: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/pages/JoinUs/components/SignupForm.tsx
```

- [ ] **Step 4: Commit (승인 후)**

```bash
git add frontend/src/pages/JoinUs/components/SignupForm.tsx
git commit -m "feat(signup): 회원가입 직후 auth.login 자동 호출

backend signup 응답의 access_token + user + brand 를 즉시 AuthContext에 저장.
사용자가 별도로 다시 로그인할 필요 없음. JoinUsPage Success 화면 → 'SPOTTER 시작하기' 시
이미 로그인 상태로 /simulator 또는 /hq 자연스럽게 이동.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Frontend — `ManagerSignupForm.tsx` 자동 로그인 호출

**Files:**
- Modify: `frontend/src/pages/JoinUs/components/ManagerSignupForm.tsx:138~` (handleSubmit success 분기)

- [ ] **Step 1: useAuth import + auth 변수**

상단 import:
```ts
import { useAuth } from '../../../auth/AuthContext';
```

`export default function ManagerSignupForm(...)` 안 첫 줄:
```ts
const auth = useAuth();
```

- [ ] **Step 2: handleSubmit success 분기 변경**

line 138~ fetch 응답 처리 부분 (`if (data.status === 'success') ...`) 에 SignupForm 과 동일 패턴 적용:

```ts
const data = await res.json();
if (data.status === 'success') {
  if (data.access_token && data.user) {
    // 매니저는 brand 없음 — null 명시
    auth.login(
      { ...data.user, role: 'manager', plan: data.user.plan ?? '' },
      null,
      data.access_token
    );
  }
  onSuccess();
} else {
  setSubmitError(data.message || '가입 중 오류가 발생했습니다.');
}
```

(매니저는 `loginWithFallback` 의 manager 분기 line 178-184 패턴과 동일하게 role/plan 명시)

- [ ] **Step 3: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/pages/JoinUs/components/ManagerSignupForm.tsx
```

- [ ] **Step 4: Commit (승인 후)**

```bash
git add frontend/src/pages/JoinUs/components/ManagerSignupForm.tsx
git commit -m "feat(signup): manager 회원가입 직후 auth.login 자동 호출

SignupForm 과 동일 패턴. manager는 brand=null + role/plan 명시.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: 정합성 검증 (전체 tsc + prettier + ruff)

**Files:** (검증만, 변경 없음)

- [ ] **Step 1: Frontend tsc**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
```

Expected: EXIT=0

- [ ] **Step 2: Frontend prettier 일괄**

```bash
npx prettier --write src/types/simulationHistory.ts \
  src/components/SimulationHistory/HistoryCard.tsx \
  src/App.tsx \
  src/components/GlobalNav.tsx \
  src/pages/JoinUs/components/SignupForm.tsx \
  src/pages/JoinUs/components/ManagerSignupForm.tsx
```

- [ ] **Step 3: Backend ruff**

```bash
cd /c/mapo-franchise-simulator
ruff check backend/src/schemas/simulation_history.py \
  backend/src/services/simulation_history_service.py \
  backend/src/main.py \
  backend/tests/test_simulation_history_service.py
ruff format backend/src/schemas/simulation_history.py \
  backend/src/services/simulation_history_service.py \
  backend/src/main.py \
  backend/tests/test_simulation_history_service.py
```

기존 E402 경고 18개 (langchain import 순서) 는 무시. 신규 에러 0이 목표.

- [ ] **Step 4: Backend pytest**

```bash
cd /c/mapo-franchise-simulator/backend
python -m pytest tests/test_simulation_history_service.py -v
```

Expected: `2 passed`

- [ ] **Step 5: 추가 commit 불필요**

이전 task 들의 prettier/ruff 가 이미 적용됐다면 추가 변경 0. 변경 발생 시 묶어 commit:

```bash
git status
# 변경 있으면:
git add -u
git commit -m "chore: prettier/ruff 일괄 정합 적용

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: 강민 브라우저 검증 (메모리 `feedback_runtime_verification.md`)

**Files:** (코드 변경 없음, 사용자 직접)

- [ ] **시나리오 1**: master 신규 가입 → 자동 로그인 → `/hq` 또는 회원가입 직후 진입한 화면 확인

- [ ] **시나리오 2**: manager 신규 가입 (초대코드 사용) → 자동 로그인 → `/simulator` 직행

- [ ] **시나리오 3**: manager 우상단 헤더 4 아이콘 모두 클릭 → 무한 simulate cycle 사라짐 확인 (Folder=workspace, User=history, Settings=mypage, Bell=드롭다운)

- [ ] **시나리오 4**: manager `/hq?tab=workspace` 진입 → 의뢰 placeholder + 본인 시뮬 이력 정상 렌더

- [ ] **시나리오 5**: manager 가 시뮬 1개 실행/저장 → master 로그인 → master HQ history 메뉴 진입 → 해당 시뮬에 "by {manager 이름}" cyan 배지 표시 확인

- [ ] **시나리오 6**: manager 가 다른 manager 시뮬 못 본다 — manager 본인 history 진입 시 본인 것만 (백엔드 권한 분기 검증)

- [ ] **시나리오 7**: master URL 직접 `/hq?tab=team` → MasterCommandCenter 정상 / manager URL 직접 `/hq?tab=team` → ManagerWorkspace 가 'workspace' 로 fallback

- [ ] **DB 검증 (선택)**: psql 또는 DBeaver 로 신규 가입자 INSERT 확인:

```sql
SELECT id, email, contact_name, created_at FROM users ORDER BY created_at DESC LIMIT 3;
SELECT id, email, contact_name, created_at FROM manager_users ORDER BY created_at DESC LIMIT 3;
```

---

## Verification Summary

전체 변경:
- Frontend: 6 파일 / +30~50 줄
- Backend: 3 파일 / +20~30 줄
- Backend tests: 1 파일 신규 / +60줄
- 총 11 commit (사용자 승인 누적)

검증:
- tsc EXIT=0 / prettier 적용 / ruff check 신규 에러 0 / pytest 2 passed
- 강민 브라우저 7 시나리오 + DB 직접 확인

---

## Spec Self-Review

**1. Spec coverage:** spec 의 변경 영역 4 (라우트/GlobalNav/Oversight/자동로그인) 모두 task 1-10 에 매핑 ✅
**2. Placeholder scan:** "TBD"/"TODO"/"적절한 에러 처리" 등 0 ✅
**3. Type consistency:** `manager_name` 이 backend (snake_case) + frontend (snake_case 그대로) 일치, ClosureRiskSignal 등 다른 영역 침범 0 ✅
**4. Ambiguity:** ManagerWorkspace fallback 코드 위치 (line 2096-2107) 명시, signup 라우트 line 명시, SQL prefix 정확 ✅

---

## References

- Spec: `docs/superpowers/specs/2026-04-28-master-manager-permission-design.md`
- 디자인 토큰: `project_dashboard_11_charts.md` (cyan 배지 일관성)
- AGENTS.md (담당 영역): backend = B2 수지니, 강민 합의 받은 가정
- CLAUDE.md (포매팅): ruff check --fix && ruff format / npx prettier --write
- 메모리: feedback_commit_policy / feedback_runtime_verification / project_jwt_zombie_pattern
