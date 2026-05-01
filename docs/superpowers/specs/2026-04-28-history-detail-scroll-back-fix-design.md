# SPOTTER History Detail — 스크롤 frozen + 뒤로가기 무반응 fix

작성일: 2026-04-28
관련 브랜치: `feature/demographic-depth-agent`

## Context

매니저가 시뮬레이션을 저장(`simulation_history` 테이블에 영구화)한 후, HQ 또는 매니저 본인이 그 이력을 클릭해 결과 화면(`/dashboard/history/:id` → `SimulationHistoryDetail`)에 진입하면 두 가지 버그가 발생한다:

1. **스크롤이 아예 작동하지 않음** — 마우스 휠/트랙패드/키보드 모두 무반응. body 자체가 frozen
2. **GlobalNav BACK 버튼이 의도대로 작동하지 않음** — 이전 페이지(보통 HQ history list)로 돌아가지 않고 intro 화면으로 튕김

근본 원인:
- **스크롤**: `index.html`의 `<html>`/`<body>`에 인라인 `style="overflow:hidden;height:100%"`가 적용되어 있어, body 자체 스크롤이 막혀있고 자식 wrapper의 `overflow-y-auto`에 의존하는 구조. `SimulationHistoryDetail.tsx`의 wrapper는 `min-h-screen pb-16`로 자체 scroll container 미보유 — 컨텐츠가 viewport 초과 시 스크롤 불가능.
- **뒤로가기**: `GlobalNav` BACK 버튼(App.tsx:4624)이 `scene === 'simulator' && reportState === 'result'` 분기에서만 `window.history.back()` 호출. react-router 페이지(`/dashboard/*`)에서는 `transitionTo('intro')`로 강제 이동.

본부 영업팀(메모리 `project_persona_pivot`)이 매니저 시뮬 이력을 검토할 때 컨텐츠를 못 보고 BACK도 의도대로 안 먹는 상태 — 신뢰 저하 + 업무 차단.

## Approach

### 작업 1 — SimulationHistoryDetail wrapper에 scroll container 추가

**파일**: `frontend/src/pages/SimulationHistoryDetail.tsx`

변경 (line 91 wrapper):
```tsx
// Before
<div className="min-h-screen bg-[#0C0B0A] pb-16 text-stone-100">

// After
<div className="h-screen overflow-y-auto custom-scrollbar bg-[#0C0B0A] pb-16 text-stone-100">
```

이유: body/html `overflow:hidden` 인라인 스타일에 의존하는 SPOTTER 패러다임에서, 신규 react-router 페이지는 자체 scroll container 필수. `h-screen` (= 100vh)로 고정 높이 + `overflow-y-auto`로 컨텐츠 초과 시 자연 스크롤. `custom-scrollbar` 클래스 재사용으로 다른 페이지(SimulatorDashboard)와 시각 일관.

### 작업 2 — GlobalNav BACK 버튼에 react-router 페이지 분기 추가

**파일**: `frontend/src/App.tsx` (line 4624 부근)

변경:
```tsx
onClick={() => {
  // 1. simulator 결과 화면 — 기존 로직 유지 (popstate로 reportState='idle')
  if (scene === 'simulator' && reportState === 'result') {
    window.history.back();
    return;
  }
  // 2. react-router 페이지(/dashboard/*, /hq, /hq/*) — 직전 페이지로 복귀
  if (
    location.pathname.startsWith('/dashboard/') ||
    location.pathname === '/hq' ||
    location.pathname.startsWith('/hq/')
  ) {
    navigate(-1);
    return;
  }
  // 3. scene-based fallback (intro/accordion/login)
  transitionTo(scene === 'simulator' ? 'accordion' : 'intro');
}}
```

`useLocation`/`useNavigate` hook은 react-router-dom에서 import (이미 사용 중인 곳 있으면 재사용, 없으면 추가).

### 작업 3 — 메모리 정책 추가

**파일**: `~/.claude/projects/C--mapo-franchise-simulator/memory/feedback_react_router_scroll_container.md` (신규)

내용:
- 신규 react-router 페이지(`/dashboard/*`, `/hq*` 등) 작성 시 wrapper에 `h-screen overflow-y-auto custom-scrollbar` 필수
- 이유: `index.html`의 body/html `overflow:hidden` 인라인 스타일 의존. 미적용 시 컨텐츠 길어졌을 때 스크롤 frozen 버그
- 사례: 2026-04-28 SimulationHistoryDetail 사례 (`min-h-screen pb-16` 만으로는 안 됨)
- How to apply: 페이지 컴포넌트 root div에 `h-screen overflow-y-auto custom-scrollbar` 명시

`MEMORY.md` index에 한 줄 추가:
```
- [Feedback: react-router 페이지는 자체 scroll container 필수](feedback_react_router_scroll_container.md) — body overflow:hidden 의존 패턴
```

### 변경하지 않는 것

- `index.html`의 body/html `overflow:hidden` 인라인 스타일 (정공법 시 fullscreen scene 패턴 깨질 위험 — Explore agent 결과 회귀 면적 큼)
- `App.tsx:4354`의 root wrapper `w-screen h-screen overflow-hidden` (같은 이유)
- Dead/placeholder 버튼 7건 + disabled 2건 (사용자 결정: 옵션 A — 그대로 유지. 영업적 의미 + 미래 구현 시점 보존). 점검 결과는 부록 참조

## Critical Files

| 파일 | 변경 분량 |
|---|---|
| `frontend/src/pages/SimulationHistoryDetail.tsx` | 1줄 (wrapper className) |
| `frontend/src/App.tsx` | ~10줄 (BACK 분기 추가 + import 점검) |
| `~/.claude/projects/.../memory/feedback_react_router_scroll_container.md` | 신규 |
| `~/.claude/projects/.../memory/MEMORY.md` | 1줄 추가 |

## Verification

런타임 검증 (강민 직접 — 메모리 `feedback_runtime_verification`):

1. **frontend dev 서버 재시작** (HMR로 잡힐 가능성도 있지만 wrapper 변경이라 보수적 재시작)

2. **스크롤 fix 검증**:
   - 매니저 계정으로 시뮬 실행 + 저장 → 시뮬 history 누적
   - HQ 계정 로그인 → HQ 페이지 → 매니저 이력 클릭 → `/dashboard/history/:id` 진입
   - 마우스 휠/트랙패드/키보드 화살표로 dashboard 컨텐츠 스크롤 확인
   - 짧은 시뮬(viewport 안에 fit)부터 긴 시뮬(여러 탭 + KPI + 차트)까지 모두 스크롤 정상

3. **뒤로가기 fix 검증**:
   - HQ → 매니저 이력 클릭 → `/dashboard/history/:id` 진입
   - GlobalNav BACK 버튼 클릭 → HQ history list로 복귀 (intro로 튕김 X)
   - 매니저 본인이 자기 이력 진입 시도 동일하게 BACK 정상 작동
   - `/hq` 페이지에서도 BACK 정상 작동 (이전 페이지로 복귀)

4. **회귀 검증** — 기존 동작 깨지지 않았는지:
   - `/simulator` 페이지에서 RUN → 결과 화면 → BACK 버튼 → reportState='idle'로 복귀 (기존 동작)
   - intro / accordion / login 화면에서 BACK 동작 (기존 그대로)
   - SimulatorDashboard 자체 스크롤 정상 (자체 scroll container 보유)

## 부록 — Dead Button 점검 결과 (옵션 A로 유지, 미래 cycle 참고용)

전수 점검 결과 7건 명백한 placeholder + 2건 disabled. 사용자 결정으로 변경 없이 toast 안내 유지(영업적 의미 + 미래 구현 시점 보존).

| 파일 | 라벨 | 처리 의도 |
|---|---|---|
| `App.tsx:2056` | "과거 데이터 조회" | 준비 중 toast |
| `CommandPalette.tsx:109` | "테마 전환" | 준비 중 toast |
| `CommandPalette.tsx:121` | "로그아웃" (Cmd+K) | 우측 상단 메뉴 안내 (대체 경로 있음) |
| `GlobalNav.tsx:314` | "알림 센터 전체 보기" | 준비 중 toast |
| `LoginPage.tsx:237` | "비밀번호 찾기" | 준비 중 toast |
| `HQCommandCenter.tsx:1588` | "결제 수단 관리" | 정식 오픈 후 (영업적 의미 보존) |
| `HQCommandCenter.tsx:1681` | "플랜 문의하기" | 정식 오픈 후 (영업적 의미 보존) |
| `HQCommandCenter.tsx:1552` | "AI 모델 업데이트 적용 (Phase 2)" | disabled (Phase 2 명시) |
| `ManagerDetail.tsx:78` | "history" 탭 | `historyAvailable=false` 시 disabled |

## Memory Adherence

- `feedback_thorough_audit` — 두 증상의 진단 + 영향 범위 전수 검증 (Explore 3 agents 병렬)
- `feedback_runtime_verification` — 강민 직접 검증 ✓
- `feedback_commit_policy` — commit은 사용자 명시 요청 시에만 ✓
- `project_api_null_policy` — 데이터 없을 때 default 금지 (이번 작업과 직접 관련 없지만 dead button 부록은 placeholder 정직성 정책 일관)
