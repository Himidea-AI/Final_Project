# 🐛 시뮬레이션 시작 진입점 누락 (Hub Redesign 회귀)

**보고일**: 2026-04-29
**영역**: C1 (frontend, @Knockcha)
**심각도**: 🔴 High — 사용자가 새 시뮬레이션을 시작할 수 없음
**관련 commit**: `f6b8afd` feat(dashboard): Hub Redesign — 3 카드 hub + 라우트 분리 + scroll/back fix

---

## 1. 증상

> "원래 행정동 업종 등등을 선택해서 들어가는 창이 있어야 되는데 그 부분이 누락되었다"

사용자가 시뮬 결과를 본 후 **새로운 시뮬레이션을 시작할 진입점이 없음**.

### 재현 시나리오
1. 사용자 로그인 → `/simulator` 진입
2. 행정동/업종 선택 → RUN SIMULATION
3. 결과 도착 → `/dashboard`로 자동 navigate (Hub Redesign)
4. `/dashboard`에서 3개 카드(예측/분석/ABM) 보임
5. **새 시뮬 시작 시도** → ❌ 진입 경로 없음

---

## 2. 원인 분석

### ⚠️ 결론 — input UI 코드는 살아있음. **누락 아님**.

검증 결과 (`backend의 frontend/src/App.tsx`):

| 항목 | 위치 | 상태 |
|---|---|---|
| 행정동 선택 드롭다운 | `App.tsx:1510-1520` (`selectedDongs.length / MAX_DONGS`) | ✅ 존재 |
| 업종 선택 드롭다운 | `App.tsx:849-850` (`setBusinessType`, `setBusinessTypeOpen`) | ✅ 존재 |
| SIMULATION CONTROLS 좌측 패널 | `App.tsx:1480` (Core/Operating/Target 3섹션) | ✅ 존재 |
| RUN SIMULATION 버튼 | `App.tsx:3982-4005` (`<Play /> RUN SIMULATION`) | ✅ 존재 |

→ commit에서 input UI 자체가 빠진 게 아니라 **렌더링 트리거가 차단된 상태**.

### 🔍 진짜 원인 — 3가지 요인 중첩

#### 원인 ① — input UI가 `reportState === 'result'`일 때 자동 숨김

`frontend/src/App.tsx:1480` (Left panel):
```typescript
className={`lg:col-span-12 rounded-2xl border p-6 transition-all duration-700 ${panel} ${
  reportState === 'result' ? 'hidden' : ''
}`}
```

`frontend/src/App.tsx:3982` (RUN box):
```typescript
className={`rounded-2xl border p-6 transition-all duration-700 ${panel} ${
  reportState === 'result' ? 'hidden' : ''
}`}
```

→ `reportState === 'result'` 조건에서 input panel + RUN 박스가 모두 hidden.

#### 원인 ② — mount-restore가 이전 시뮬 결과 자동 복원

`frontend/src/App.tsx:1299-1306` (`SimulatorDashboard` 마운트 effect):
```typescript
// [R2] 마운트 시 store 에서 복원 — 다른 페이지로 나갔다가 /simulator 복귀 시 결과 유지.
useEffect(() => {
  const s = useSimulationStore.getState();
  if (reportState === 'idle' && s.status === 'done' && s.result) {
    setRawSimResult(s.result);
    setSimResult(toSimResultViewModel(s.result));
    setReportState('result');  // ← 자동으로 result 상태 → input hidden
  }
}, []);
```

→ `/simulator` 진입 시 store에 이전 결과 있으면 **자동으로 `reportState='result'`로 전환** → 원인 ①에 의해 input UI 숨김.

#### 원인 ③ — Hub Redesign 이후 "새 시뮬 시작" 진입점 부재

##### GlobalNav 메뉴 (`frontend/src/components/GlobalNav.tsx:99-104`)
```typescript
const navItems = [
  { type: 'folder', icon: <Folder />, label: '출점 파이프라인' },  // → /hq?tab=pipeline
  { type: 'user', icon: <User />, label: '내 시뮬 이력' },         // → /hq?tab=history
  { type: 'settings', icon: <Settings />, label: '내 정보 관리' },
  { type: 'bell', icon: <Bell />, label: '알림' },
];
```
→ **"새 시뮬 시작" / "Simulator" 메뉴 항목 없음**

##### DashboardHub (`frontend/src/components/SimulationResult/dashboard/DashboardHub.tsx`)
- 3개 HubCard (예측/분석/ABM) — **모두 결과 보기용**
- "새 시뮬", "다시 시작" 버튼 **없음**

##### 자동 navigate 흐름 (commit `f6b8afd` 변경 사항)
```
시뮬 완료 → navigate('/dashboard', replace)
useCompletionToast / FloatingWidget의 navigate 경로: /simulator → /dashboard
popstate effect 제거 (Hub Redesign 흐름 충돌 fix)
```

→ 시뮬 완료 후 사용자가 `/dashboard`에 머물면 **다시 `/simulator`로 돌아갈 명시적 경로 없음**.

---

## 3. 사용자가 시도할 수 있는 우회 경로 (현재 상태)

| 경로 | 가능 여부 | 한계 |
|---|---|---|
| GlobalNav 메뉴 클릭 | ❌ | 메뉴 자체 없음 |
| DashboardHub 버튼 | ❌ | 버튼 없음 |
| URL 직접 입력 `/simulator` | ⚠️ | mount-restore가 이전 결과 자동 복원 → input 여전히 숨김 |
| 브라우저 뒤로가기 | ⚠️ | `/dashboard` → `/simulator` 가능하지만 동일 문제 |
| 로그아웃 후 재로그인 | ⚠️ | store 초기화되지만 매번 비합리 |

---

## 4. 해결 방안 (3가지 옵션, 강민 결정)

### 옵션 A — DashboardHub에 "새 시뮬" 버튼 추가 (가장 간단, 1줄 변경)

**파일**: `frontend/src/components/SimulationResult/dashboard/DashboardHub.tsx`
**위치**: 헤더 우측 (`<header>` 안의 `<div className="text-right">` 옆)

```tsx
import { useNavigate } from 'react-router-dom';
import { useSimulationStore } from '../../../stores/simulationStore';

// header 안에 추가
const navigate = useNavigate();
const dismissResult = useSimulationStore((s) => s.dismissResult);

<button
  onClick={() => {
    dismissResult();
    navigate('/simulator');
  }}
  className="px-4 py-2 rounded-lg bg-indigo-500 text-white text-sm font-bold hover:bg-indigo-600"
>
  + 새 시뮬레이션
</button>
```

**장점**: 가장 빠르고 명확. UX도 자연스러움.

---

### 옵션 B — GlobalNav에 "Simulator" 메뉴 추가

**파일**: `frontend/src/components/GlobalNav.tsx:99-104`

```typescript
const navItems = [
  { type: 'simulator', icon: <Play />, label: '새 시뮬' },  // ← 추가
  { type: 'folder', icon: <Folder />, label: '출점 파이프라인' },
  { type: 'user', icon: <User />, label: '내 시뮬 이력' },
  { type: 'settings', icon: <Settings />, label: '내 정보 관리' },
  { type: 'bell', icon: <Bell />, label: '알림' },
];

// handleItemClick에 분기 추가:
} else if (type === 'simulator') {
  useSimulationStore.getState().dismissResult();
  nav('/simulator');
}
```

**장점**: 어느 페이지에서든 "새 시뮬" 가능. 글로벌 navigation에 노출.
**단점**: 메뉴 5개로 늘어 시각적 혼잡 가능 (강민 디자인 결정).

---

### 옵션 C — `/simulator?new=1` query param 분기 (옵션 A/B의 구현 패턴)

**파일**: `frontend/src/App.tsx:1299-1306`

```typescript
import { useSearchParams } from 'react-router-dom';

const [searchParams] = useSearchParams();

useEffect(() => {
  // ?new=1이면 mount-restore skip + 명시적 reset
  if (searchParams.get('new') === '1') {
    useSimulationStore.getState().dismissResult();
    return;
  }
  
  const s = useSimulationStore.getState();
  if (reportState === 'idle' && s.status === 'done' && s.result) {
    setRawSimResult(s.result);
    setSimResult(toSimResultViewModel(s.result));
    setReportState('result');
  }
}, []);
```

**장점**: 옵션 A/B의 navigate 호출이 `/simulator?new=1`만 하면 됨 (별도 dismissResult 불필요).
**단점**: 단독으로는 진입점 문제 해결 X (옵션 A 또는 B와 함께 적용).

---

## 5. 권장 조합

> **옵션 A + 옵션 C**

1. DashboardHub 헤더에 "새 시뮬" 버튼 추가 → `navigate('/simulator?new=1')`
2. App.tsx mount-restore에 `?new=1` 분기 추가
3. (선택) GlobalNav에도 "새 시뮬" 메뉴 추가 → 어느 페이지에서든 진입 가능

총 변경: **3개 파일, ~15줄**

---

## 6. 영역 / 담당

- **영역**: `frontend/` (C1)
- **담당**: 강민 (@Knockcha)
- **A1(찬영) 직접 수정 불가** — AGENTS.md 영역 룰

---

## 7. 검증 방법

수정 후:

```bash
cd frontend && npm run dev
```

1. `/simulator` 진입 → 시뮬 실행 → 결과 → `/dashboard`로 자동 이동 확인 ✓
2. DashboardHub에서 "새 시뮬" 버튼 클릭
3. `/simulator`로 이동 + input panel 정상 표시 (이전 결과 잔재 없음) ✓
4. 행정동/업종 선택 + RUN → 새 시뮬 정상 실행 ✓

---

## 8. 우선순위 / 일정

- 🔴 **High** — 사용자가 새 시뮬 못 하는 상태
- **권장 처리 시점**: 즉시 (1시간 내, hotfix)
- **비용**: 매우 작음 (3개 파일, ~15줄, 테스트 5분)

---

## 부록: 참고 commit

- `f6b8afd` (2026-04-29 by Knockcha): Hub Redesign — 본 회귀의 직접 원인
- `edd13e2` (2026-04-28): SummaryTab/ForecastTab 삭제
- `17050ca` (2026-04-28): 3그룹 + 11서브탭 IA 재구조

이 시퀀스에서 "결과 보기 흐름"은 잘 정리되었지만 **"다시 시작" 흐름이 누락**됨.
