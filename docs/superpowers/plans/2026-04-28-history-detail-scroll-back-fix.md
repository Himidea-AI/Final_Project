# History Detail 스크롤 + 뒤로가기 fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** HQ/매니저가 저장된 시뮬레이션 이력(`/dashboard/history/:id`)에 진입할 때 스크롤이 frozen되고 GlobalNav BACK이 intro로 튕기는 두 버그를 fix한다.

**Architecture:** body/html `overflow:hidden` 인라인 스타일 패러다임 안에서 (1) `SimulationHistoryDetail` wrapper에 자체 scroll container 추가, (2) GlobalNav BACK 버튼에 react-router 페이지 분기 추가해 `navigate(-1)` 호출, (3) 미래 회귀 방지를 위해 메모리 정책 추가.

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind CSS v3.4 + react-router-dom

**관련 spec:** `docs/superpowers/specs/2026-04-28-history-detail-scroll-back-fix-design.md`

---

## File Structure

| 파일 | 작업 | 책임 |
|---|---|---|
| `frontend/src/pages/SimulationHistoryDetail.tsx` | Modify (1줄) | 페이지 wrapper에 자체 scroll container 부여 |
| `frontend/src/App.tsx` | Modify (~10줄) | GlobalNav BACK 버튼에 react-router 페이지 분기 추가 |
| `~/.claude/projects/C--mapo-franchise-simulator/memory/feedback_react_router_scroll_container.md` | Create | 신규 react-router 페이지 wrapper 정책 |
| `~/.claude/projects/C--mapo-franchise-simulator/memory/MEMORY.md` | Modify (1줄) | 메모리 인덱스에 새 항목 추가 |

---

## Task 1: SimulationHistoryDetail wrapper에 scroll container 추가

**Files:**
- Modify: `frontend/src/pages/SimulationHistoryDetail.tsx:91`

**배경**: 현재 wrapper는 `min-h-screen pb-16`만 있어 body/html `overflow:hidden` 환경에서 자체 스크롤이 막힘. `h-screen overflow-y-auto` 추가로 자체 scroll container 부여.

- [ ] **Step 1: 변경 대상 파일 read**

Run:
```
Read frontend/src/pages/SimulationHistoryDetail.tsx (offset 88, limit 8)
```
Expected: line 91에 `<div className="min-h-screen bg-[#0C0B0A] pb-16 text-stone-100">` 확인

- [ ] **Step 2: wrapper className 변경**

Edit `frontend/src/pages/SimulationHistoryDetail.tsx`:

```tsx
// Before
    <div className="min-h-screen bg-[#0C0B0A] pb-16 text-stone-100">

// After
    <div className="h-screen overflow-y-auto custom-scrollbar bg-[#0C0B0A] pb-16 text-stone-100">
```

- [ ] **Step 3: TypeScript 검증**

Run (frontend cwd):
```
cd C:/mapo-franchise-simulator/frontend && npx tsc --noEmit
```
Expected: 에러 0건

- [ ] **Step 4: Prettier 검증**

Run:
```
cd C:/mapo-franchise-simulator/frontend && npx prettier --write src/pages/SimulationHistoryDetail.tsx
```
Expected: 변경 없음 (`unchanged`) 또는 1ms 단위 reformat

- [ ] **Step 5: 사용자 검증 부탁 (commit 보류)**

검증 항목 (강민 직접 — 메모리 `feedback_runtime_verification`):
1. 매니저 계정으로 시뮬 실행 + 저장 → 시뮬 history 누적
2. HQ 계정 로그인 → HQ 페이지 → 매니저 이력 클릭 → `/dashboard/history/:id` 진입
3. 마우스 휠/트랙패드/키보드 화살표로 dashboard 컨텐츠 스크롤 확인
4. 짧은 시뮬(viewport 안에 fit)부터 긴 시뮬(여러 탭 + KPI + 차트)까지 모두 스크롤 정상

**Commit 정책**: 메모리 `feedback_commit_policy` — 사용자 명시 요청 시에만 commit. 검증 완료 후 사용자가 "commit"이라 요청하면 진행.

---

## Task 2: GlobalNav BACK 버튼에 react-router 페이지 분기 추가

**Files:**
- Modify: `frontend/src/App.tsx:4624` 부근 (GlobalNav BACK onClick)

**배경**: 현재 BACK 버튼은 `scene === 'simulator' && reportState === 'result'` 분기에만 `window.history.back()` 호출. react-router 페이지(`/dashboard/*`, `/hq*`)에서는 `transitionTo('intro')`로 강제 이동되는 버그. `useNavigate`/`useLocation`은 App.tsx:47에 이미 import + line 4232-4233에 instantiated되어 있으니 그대로 사용.

- [ ] **Step 1: 현재 BACK 버튼 onClick 정확한 코드 read**

Run:
```
Read frontend/src/App.tsx (offset 4620, limit 25)
```
Expected: line 4624 부근 `onClick={() => { ... transitionTo(scene === 'simulator' ? 'accordion' : 'intro'); }}` 확인

- [ ] **Step 2: useNavigate/useLocation 변수 scope 확인**

Run:
```
Read frontend/src/App.tsx (offset 4225, limit 15)
```
Expected: line 4232-4233에 `const navigate = useNavigate(); const location = useLocation();` 정의 확인. line 4624 BACK 버튼이 동일 함수 컴포넌트 scope 안인지 검증.

만약 동일 scope가 아니면 (다른 함수 컴포넌트) → BACK 버튼이 있는 컴포넌트 안에서 useNavigate/useLocation 별도 호출 필요. 이 경우 Step 3 전에 hook 추가.

- [ ] **Step 3: BACK 버튼 onClick 분기 추가**

Edit `frontend/src/App.tsx` (line 4624 부근 onClick 핸들러):

```tsx
// Before
onClick={() => {
  // 시뮬레이터 result 상태 → history.back() 호출 → popstate 리스너가 idle로 복귀
  // (브라우저 뒤로가기와 동일한 코드 경로 → 히스토리 정합성 유지)
  if (scene === 'simulator' && reportState === 'result') {
    window.history.back();
    return;
  }
  transitionTo(scene === 'simulator' ? 'accordion' : 'intro');
}}

// After
onClick={() => {
  // 1. 시뮬레이터 result 상태 — 기존 로직 (popstate로 reportState='idle')
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

- [ ] **Step 4: TypeScript 검증**

Run:
```
cd C:/mapo-franchise-simulator/frontend && npx tsc --noEmit
```
Expected: 에러 0건. `location`, `navigate` 변수가 동일 scope에서 사용 가능해야 함. 만약 `Cannot find name 'location'` / `Cannot find name 'navigate'` 에러 시 Step 2의 scope 검증 단계로 돌아가 BACK 버튼이 있는 컴포넌트에 hook 추가.

- [ ] **Step 5: Prettier 검증**

Run:
```
cd C:/mapo-franchise-simulator/frontend && npx prettier --write src/App.tsx
```
Expected: 변경 미미 또는 unchanged

- [ ] **Step 6: 사용자 검증 부탁 (commit 보류)**

검증 항목:
1. **History detail BACK 정상**: HQ → 매니저 이력 클릭 → `/dashboard/history/:id` 진입 → GlobalNav BACK 버튼 클릭 → HQ history list로 복귀 (intro로 튕김 X)
2. **HQ 페이지 BACK 정상**: `/hq` 진입 → BACK → 이전 페이지(보통 accordion landing) 복귀
3. **시뮬레이터 결과 BACK 회귀 검증**: `/simulator` 페이지 RUN → 결과 화면 → BACK → reportState='idle'로 복귀 (기존 동작 유지)
4. **Intro/accordion/login BACK 회귀**: 각 scene에서 BACK 동작 그대로 (기존 transitionTo 분기 유지)

---

## Task 3: 메모리 정책 추가

**Files:**
- Create: `C:\Users\chlrk\.claude\projects\C--mapo-franchise-simulator\memory\feedback_react_router_scroll_container.md`
- Modify: `C:\Users\chlrk\.claude\projects\C--mapo-franchise-simulator\memory\MEMORY.md`

**배경**: 미래 신규 react-router 페이지 작성 시 동일 버그 회귀 방지를 위해 메모리에 정책 등록. 메모리는 사용자 home 디렉토리이므로 프로젝트 git 대상 아님 — Task 1/2처럼 commit 단계 없음.

- [ ] **Step 1: feedback_react_router_scroll_container.md 신규 작성**

Write `C:\Users\chlrk\.claude\projects\C--mapo-franchise-simulator\memory\feedback_react_router_scroll_container.md`:

```markdown
---
name: react-router 페이지는 자체 scroll container 필수
description: 신규 /dashboard/* /hq* 페이지 작성 시 wrapper에 h-screen overflow-y-auto custom-scrollbar 누락 시 스크롤 frozen 버그
type: feedback
---

신규 react-router 페이지(`/dashboard/*`, `/hq*` 등) 작성 시 page-level wrapper에
`h-screen overflow-y-auto custom-scrollbar`를 명시해야 한다.

**Why:** `index.html`의 `<html>`/`<body>`에 인라인 `style="overflow:hidden;height:100%"`가
적용되어 있어 body 자체 스크롤이 막혀있다. SPOTTER는 SimulatorDashboard처럼
"viewport-locked + 자식 scroll container" 패러다임으로 설계됨. 신규 페이지가
이 정책을 모르고 `min-h-screen` 등으로만 wrapper를 잡으면 컨텐츠가 viewport
초과 시 스크롤이 frozen된다.

**How to apply:** 페이지 컴포넌트의 root div에 `h-screen overflow-y-auto custom-scrollbar`
명시. 사례:
- `SimulationHistoryDetail.tsx` (2026-04-28 fix) — `min-h-screen pb-16` → `h-screen overflow-y-auto custom-scrollbar bg-[#0C0B0A] pb-16`
- 향후 신규 페이지 PR review 시 wrapper className 점검 항목.
```

- [ ] **Step 2: MEMORY.md 인덱스에 한 줄 추가**

Edit `C:\Users\chlrk\.claude\projects\C--mapo-franchise-simulator\memory\MEMORY.md`:

기존 feedback 항목들 사이 적절한 위치(예: `feedback_thorough_audit` 다음)에 한 줄 삽입:

```markdown
- [Feedback: react-router 페이지 자체 scroll container 필수](feedback_react_router_scroll_container.md) — body overflow:hidden 의존, 미적용 시 스크롤 frozen
```

- [ ] **Step 3: 검증**

Run:
```
Read C:\Users\chlrk\.claude\projects\C--mapo-franchise-simulator\memory\feedback_react_router_scroll_container.md
Read C:\Users\chlrk\.claude\projects\C--mapo-franchise-simulator\memory\MEMORY.md (limit 30)
```
Expected:
- 새 메모리 파일에 frontmatter(name/description/type) + 본문(Why/How to apply) 정상
- MEMORY.md에 새 항목 한 줄 추가 확인

(memory 디렉토리는 git 대상 아님 — commit 없음)

---

## Task 4: 통합 회귀 검증 (사용자 직접)

**Files:** (검증만, 코드 변경 없음)

**배경**: Task 1+2가 기존 동작을 깨지 않았는지 + 두 fix가 함께 작동하는지 확인.

- [ ] **Step 1: dev 서버 재시작 (강민 직접 — 메모리 `feedback_runtime_verification`)**

Run:
```
cd C:/mapo-franchise-simulator/frontend && npm run dev
```
또는 기존 dev 서버 HMR로 자동 반영 (wrapper className + onClick 분기는 HMR 잡힘)

- [ ] **Step 2: 양 시나리오 검증**

| 시나리오 | 기대 동작 |
|---|---|
| HQ → 이력 클릭 → history detail | 진입 후 스크롤 정상 (mouse wheel/keyboard 모두) |
| History detail에서 GlobalNav BACK 클릭 | HQ history list로 복귀 (intro 튕김 X) |
| `/hq` 진입 후 BACK | 이전 페이지로 복귀 |
| `/simulator` RUN → 결과 → BACK | reportState='idle'로 복귀 (기존 동작) |
| Intro/accordion/login에서 BACK | 기존 transitionTo 분기 그대로 |

- [ ] **Step 3: DevTools 검증 (선택)**

`/dashboard/history/:id` 진입 후 DevTools Console에서:
```js
document.querySelector('.custom-scrollbar').scrollHeight > document.querySelector('.custom-scrollbar').clientHeight
```
Expected: `true` (스크롤 가능 컨텐츠 존재)

- [ ] **Step 4: 누적 commit 결정**

검증 통과 후 사용자 결정:
- **단일 commit**: Task 1 + 2 묶어서 한 commit
- **2 commit**: Task 1 (스크롤) + Task 2 (BACK) 분리
- **검증 후 추가 fix 발견 시**: 추가 작업 후 commit

메모리 파일은 git 대상 아니므로 별도 처리 없음.

---

## Self-Review

### Spec coverage

| Spec 요구 | Plan task |
|---|---|
| 작업 1 — SimulationHistoryDetail wrapper scroll container | Task 1 ✓ |
| 작업 2 — GlobalNav BACK react-router 분기 | Task 2 ✓ |
| 작업 3 — 메모리 정책 추가 | Task 3 ✓ |
| Verification | Task 1 Step 5, Task 2 Step 6, Task 4 ✓ |
| Memory adherence (commit policy, runtime verification) | 각 Task의 commit/검증 단계에 명시 ✓ |
| 부록 Dead button 점검 (변경 없음) | Plan 범위 외 (사용자 결정 옵션 A) |

### Placeholder scan

- TBD/TODO 없음 ✓
- 모든 step에 exact 명령어 + expected output 명시 ✓
- 변경할 코드는 Before/After 모두 표시 ✓

### Type consistency

- `useLocation`, `useNavigate` 변수명 일관 (Task 2 Step 2/3에서 `location`, `navigate`)
- wrapper className `h-screen overflow-y-auto custom-scrollbar` Task 1과 Task 3 메모리 일관

### 결론

Plan 검증 통과. 즉시 실행 가능.
