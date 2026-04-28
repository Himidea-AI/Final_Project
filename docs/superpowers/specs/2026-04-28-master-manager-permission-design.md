# Master/Manager 권한 분리 + Master Oversight + 회원가입 자동 로그인 — Design Spec

**Date**: 2026-04-28
**Author**: 강민 (PM + Frontend Lead)
**Status**: Draft → User Review

---

## 1. Context (왜 이 변경이 필요한가)

### 1-1. 신고된 버그
- **manager 계정 로그인 후 우상단 헤더 아이콘(Folder/User/Settings) 을 누르면 매번 `/simulator` 페이지로 튕김** (사용자가 직접 신고)
- 사용자: "어떤 아이콘을 눌러도 simulate 로 간다"

### 1-2. Root Cause (확정)
1. `GlobalNav.tsx:97-102` 에 manager/master 분기 없이 4개 아이콘이 모두 master 전용 path (`/hq?tab=...`) 로 navigate
2. `App.tsx:4419` `<Route path="/hq" element={<ProtectedRoute requireRole="master">>` 가 manager 진입 차단
3. `ProtectedRoute.tsx:30` 가 manager 라면 `<Navigate to="/simulator" />` 로 fallback redirect
4. 결과: 어떤 manager 도 우상단 헤더 클릭 → 무한 simulate cycle

### 1-3. 부수 발견
- **회원가입 후 자동 로그인 안 됨**: `SignupForm.tsx:174` 가 `auth.login()` 호출하지 않고 `onSuccess()` 만 호출 → 사용자가 별도로 다시 로그인해야 함
- **Master Oversight 가 backend 만 됨**: `simulation_history_service.py:91` 권한 분기는 완전 구현 (master = 본인 + 워크스페이스 매니저들 시뮬), 그러나 SELECT 절에 `manager_id` 가 빠져 있고 frontend HistoryCard 도 매니저 식별 표시 없음

### 1-4. 페르소나 결정 (브레인스토밍 결과)
- **A**: 팀장(master) ↔ 팀원(manager) 수직 위계
- **(ii) Master Oversight**: manager 는 본인 시뮬만 / master 는 본인 + 자기 워크스페이스 매니저들 시뮬 모두

---

## 2. Out of Scope (이번 사이클 제외)

- (iii) 양방향 의뢰 워크플로우 (assignments 테이블, 발송/검수 UI, 알림) — Future Work 섹션 참고
- 매니저별 필터/그룹핑 토글 in HistoryFilter — MVP 다음 cycle
- master 의 출점 파이프라인 칸반 실 데이터 연동 — 별도 cycle
- 알림 시스템 (notifications 테이블, polling/SSE) — 별도 cycle

---

## 3. 변경 영역

### 3-1. 라우트 권한 (manager 가 `/hq` 진입 가능)

**파일**: `frontend/src/App.tsx:4419`

```tsx
// Before
<Route path="/hq" element={<ProtectedRoute requireRole="master"><HQCommandCenter /></ProtectedRoute>} />

// After
<Route path="/hq" element={<ProtectedRoute><HQCommandCenter /></ProtectedRoute>} />
```

근거:
- HQCommandCenter 내부 분기(`HQCommandCenter.tsx:65-67`) 가 master/manager 갈래 담당
- ManagerWorkspace (`HQCommandCenter.tsx:2096-2107`) 가 이미 fallback 코드 보유: `tabFromUrl && ['workspace', 'history', 'mypage'].includes(tabFromUrl) ? tabFromUrl : 'workspace'` — manager 가 URL `?tab=team` 직접 입력해도 자동으로 workspace 로 fallback. 신규 코드 추가 불필요.

### 3-2. GlobalNav 헤더 manager 분기 (헤더 4개 거울 + path 갈래)

**파일**: `frontend/src/components/GlobalNav.tsx:115-137` `handleItemClick`

| 아이콘 | master path | manager path |
|---|---|---|
| Folder | `/hq?tab=pipeline` | `/hq?tab=workspace` (의뢰 placeholder 포함) |
| User | `/hq?tab=history` | `/hq?tab=history` (본인 시뮬만) |
| Settings | `/hq?tab=mypage` | `/hq?tab=mypage` |
| Bell | drop (mock + 매니저 승인 알림) | drop (의뢰 placeholder + manager 본인 알림) |

```ts
const isManager = user?.role === 'manager';

if (type === 'folder') {
  setOpenDropdown(null);
  nav(isManager ? '/hq?tab=workspace' : '/hq?tab=pipeline');
} else if (type === 'settings') {
  setOpenDropdown(null);
  nav('/hq?tab=mypage');
} else if (type === 'user') {
  setOpenDropdown(null);
  nav('/hq?tab=history');
}
// bell drop 그대로
```

(설계 일관성: 동일한 4 아이콘, 동일한 path scheme, manager 시 적절한 ManagerMenuId 매핑)

### 3-3. Master Oversight UI 노출 (Full)

**Backend** (`backend/src/services/simulation_history_service.py:123-135`):

```sql
-- Before
SELECT id, client_name, district, brand_name, business_type,
       ai_verdict_summary, market_entry_signal, created_at
FROM simulation_history
WHERE {where_sql}

-- After
SELECT sh.id, sh.client_name, sh.district, sh.brand_name, sh.business_type,
       sh.ai_verdict_summary, sh.market_entry_signal, sh.created_at,
       sh.manager_id, mu.contact_name AS manager_name
FROM simulation_history sh
LEFT JOIN manager_users mu ON mu.id = sh.manager_id
WHERE {where_sql_prefixed_with_sh}
```

권한 분기(line 88-94)는 그대로. WHERE 절의 `manager_id` 컬럼 참조에 `sh.` prefix 추가만.

**Backend Schema** (`backend/src/schemas/simulation_history.py`):

```python
class SimulationHistoryListItem(BaseModel):
    id: int
    manager_id: UUID
    manager_name: Optional[str] = None  # 신규 — master 시 카드에 "by 매니저명" 표시용
    client_name: str
    # ... 기존 필드
```

**Frontend** (`frontend/src/components/SimulationHistory/HistoryCard.tsx`):

- `useAuth` 로 `user?.role === 'master'` 일 때 카드 헤더에 "by {manager_name}" 배지 (디자인: `text-[10px] font-bold text-stone-500` + 본인 시뮬은 "내 시뮬" 또는 미표시)
- manager 본인이 보면 자기 것만 오니 배지 불필요

**Frontend Types** (`frontend/src/types/simulationHistory.ts`):

```ts
export interface SimulationHistoryListItem {
  id: number;
  manager_id: string;
  manager_name?: string | null;
  // ... 기존
}
```

### 3-4. 회원가입 자동 로그인

**Backend** (`backend/src/services/auth.py` signup 함수 + `backend/src/main.py` `/auth/signup` 라우트):

회원가입 INSERT 후 `create_access_token(user_id=str(new_id), role="master", email=email)` 발급해서 응답 dict 에 `access_token` 추가. Manager signup (`/auth/manager/signup`) 도 동일 처리 (role="manager").

```python
# main.py /auth/signup 라우트 응답 직전
result["access_token"] = create_access_token(
    user_id=str(created["user"]["id"]),
    role="master",  # 또는 "manager"
    email=created["user"]["email"],
)
```

**Frontend** (`frontend/src/pages/JoinUs/components/SignupForm.tsx:172-177`):

```ts
import { useAuth } from '../../../auth/AuthContext';

// ... handleSubmit 내부
if (data.status === 'success') {
  if (data.access_token && data.user) {
    auth.login(data.user, data.brand ?? null, data.access_token);
  }
  onSuccess();
}
```

ManagerSignupForm 도 동일 패턴 적용.

`JoinUsPage` Success 화면 → "SPOTTER 시작하기" 클릭 시 이미 `auth.isLoggedIn === true` → `transitionTo('intro')` 후 즉시 `/simulator` 또는 `/hq` 자연스럽게.

---

## 4. 변경 파일 목록 (총 9개)

### Frontend (6)
1. `frontend/src/App.tsx` — ProtectedRoute requireRole 제거 (1줄)
2. `frontend/src/components/GlobalNav.tsx` — handleItemClick manager 분기 (~10줄)
3. `frontend/src/pages/JoinUs/components/SignupForm.tsx` — auth.login 호출 추가
4. `frontend/src/pages/JoinUs/components/ManagerSignupForm.tsx` — 동일 패턴 적용
5. `frontend/src/components/SimulationHistory/HistoryCard.tsx` — by 매니저명 배지
6. `frontend/src/types/simulationHistory.ts` — manager_name 필드

### Backend (3, B2 수지니 영역 합의 가정)
7. `backend/src/services/simulation_history_service.py` — SELECT 에 manager_id + JOIN manager_users
8. `backend/src/schemas/simulation_history.py` — `manager_name` 필드 추가
9. `backend/src/services/auth.py` + `backend/src/main.py` — signup access_token 발급 (master + manager 둘 다)

---

## 5. 검증 시나리오 (강민 직접)

1. **manager 신규 가입 → 자동 로그인 → /simulator 직행** (현재는 별도 로그인 필요)
2. **manager 우상단 헤더 4 아이콘 모두 정상 동작** (현재는 모두 /simulator 무한 cycle)
3. **manager → /hq?tab=workspace** 진입 시 의뢰 placeholder + 시뮬 이력 정상
4. **manager 가 만든 시뮬 → master 로그인 → master HQ history 에 "by 매니저명" 배지 표시**
5. **manager → manager history 진입 시 본인 시뮬만 (다른 매니저 시뮬 안 보임)**
6. **master URL 직접 `/hq?tab=team` → MasterCommandCenter 정상**
7. **manager URL 직접 `/hq?tab=team` → ManagerWorkspace 의 fallback (workspace 또는 history)** — 이미 ManagerMenuId 가 'team' 거부

DB 직접 검증 (선택): `SELECT id, email, role FROM users WHERE email = '신규가입이메일';` + `manager_users` 동일 확인.

---

## 6. 리스크 / 트레이드오프

- **의뢰 placeholder 영구 노출** — 사용자 결정 (a) 사이클 OK. 향후 (iii) 진짜 구현 시 자리 보존
- **manager URL 직접 `?tab=team` 입력** — ManagerWorkspace 가 ManagerMenuId 만 인식 → 자동 fallback. **신규 코드 불필요** (이미 `HQCommandCenter.tsx:2096-2107` 에 fallback 있음)
- **HistoryCard 디자인 일관성** — 방금 통일한 stone/indigo 토큰 (`text-[10px] font-bold text-stone-500` 등) 그대로 적용
- **backend 합의** — closure_rate 추가 사이클(2026-04-27) 과 동일한 패턴. 수지니 합의 받은 가정으로 진행. 합의 미확보 시 backend 변경분 분리 PR 가능

---

## 7. Future Work (이번 사이클 외)

### 7-1. 의뢰 시스템 (iii) 본격 구현

별도 DB 불필요, 기존 PostgreSQL 안에 신규 테이블:

| 테이블 | 컬럼 | 역할 |
|---|---|---|
| `assignments` (신규) | `id, master_id (FK users), manager_id (FK manager_users), district, business_type, brand_hint, status, due_date, notes, created_at, updated_at` | 의뢰 발송·상태 트래킹 |
| `simulation_history` (기존) | `+ assignment_id (FK assignments, nullable)` 한 컬럼 추가 | manager 가 의뢰 받아 실행한 시뮬을 의뢰와 매핑 |
| `notifications` (선택) | `id, user_id, type, payload, read_at, created_at` | 의뢰 도착·완료 알림 |

**status 값**: `pending → in_progress → submitted → reviewed → archived`

**네이밍**: CLAUDE.md DB 규칙상 서비스 기능 테이블이라 접두사 없이 `assignments` (`seoul_*`/`mapo_*`/`master_*` 접두사는 데이터 테이블용).

**알림 전달**: MVP 면 polling (5초 간격 GET `/api/notifications/unread`) 으로 충분, 본격적이면 SSE/WebSocket. 별도 브레인스토밍 권장.

**UI 신규 작업**:
- master HQ 에 "의뢰 발송" 모달 (manager 선택 + 동/업종 입력)
- ManagerWorkspaceView 의뢰 placeholder → 실 데이터 카드 리스트 (현재 빈 껍데기 자리 그대로 활용)
- 의뢰 ↔ 시뮬 결과 양방향 링크
- 상태 전환 액션 (manager: 시작/제출, master: 검수/반려)

### 7-2. master HQ 출점 파이프라인 칸반 실 데이터

(현재 placeholder, `simulation_history.assignment_id` + `assignments.status` 결합으로 구현 가능)

### 7-3. HistoryFilter 매니저별 필터/그룹핑 토글

(이번 사이클 미포함, master 가 매니저별 활동 비교 시 유용)

---

## 8. Open Questions

(브레인스토밍 단계에서 모두 해소됨)

---

## 9. References

- 브레인스토밍 결정 누적: A(팀장↔팀원) / (ii)Master Oversight + 의뢰 placeholder / (a)cycle 작게 / (c)헤더 거울 / 매니저 착륙지 `/simulator` / (b)Full Oversight 포함 / (a)자동 로그인 포함
- 메모리: `project_jwt_zombie_pattern.md`, `feedback_runtime_verification.md`, `feedback_agents_md.md`
- 직전 사이클 (디자인 토큰 통일): `project_dashboard_11_charts.md`
