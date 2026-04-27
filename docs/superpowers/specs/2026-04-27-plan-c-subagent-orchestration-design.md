# Plan C Sub-agent Orchestration Design

**작성**: 2026-04-27 · **작성자**: C1 강민 + Claude Opus 4.7
**브랜치**: `feature/demographic-depth-agent`
**선행 문서**: `C:\Users\chlrk\.claude\plans\snug-beaming-truffle.md` (이번 세션 결정 기록)

---

## Context

Plan C(옵션 패널 UI/UX 고도화 — P1 font-mono + P2 border 통일 + P3 시각 무게 + 한국어 톤)를 단일 메인 컨텍스트에서 일괄 처리하면 **디테일 작업의 분야 차이로 인한 컨텍스트 오염**이 우려됨.

오염 시나리오:
- 숫자 정렬(P1) 작업 중 인접한 layout className을 무심코 수정
- border 톤 통일(P2) 작업 중 한국어 톤(SectionLabel props)을 같이 변경하다 다른 영역까지 흐트러뜨림
- 시각 무게(P3) 작업 중 기존 input 컴포넌트 props를 의도치 않게 변경

→ **분야별 전문 에이전트로 분할 + 순차 위임 + 매 라운드 git diff 검증 게이트**로 오염을 git 레이어에서 차단하는 것이 본 설계의 의도.

---

## 결정 사항 (brainstorming 결과)

| 결정 | 선택 | 사유 |
|---|---|---|
| **분할 단위** | B — 3 에이전트 (P1 / P2+P3 / 한국어 톤) | P2/P3 같은 영역 편집이라 묶음, 분야 분리 효과 큼 |
| **실행 순서** | C — P1 → P2+P3 → 한국어 톤 | 컴포넌트 내부(P1) → 외곽 wrapper(P2+P3) → copy(톤). 자연스러운 안→밖 흐름 |
| **사용자 게이트** | A — 매 라운드 후 강민 시각 확인 | 다음 라운드 시작 전 검증 = 누적 오염 차단 |

---

## 전체 흐름

```
brainstorming → spec → writing-plans (현재 위치)

Round 1: Agent #1 (P1 — 숫자 정렬)
  ↓ 메인: tsc/build 검증 + git diff 영역 검증 + commit + push
  ↓ 강민: dev hard reload → 시각 확인 → 승인 신호

Round 2: Agent #2 (P2+P3 — border + 시각 무게)
  ↓ 동일 검증 + commit + push
  ↓ 강민: 시각 확인 → 승인

Round 3: Agent #3 (한국어 톤 — SectionLabel props)
  ↓ 동일 검증 + commit + push
  ↓ 강민: 최종 시각 확인

PR: feature/demographic-depth-agent에 3 commit 누적
    (PR #125 머지 후 누적분 16 + 신규 3 = 19 commit ahead of dev)
    Plan C 완료 시점에 강민 결정으로 새 PR 생성 → dev 머지
```

**격리 핵심**: 각 에이전트는 깨끗한 컨텍스트로 시작. 이전 에이전트 결과는 직접 메시지가 아닌 **git에 적용된 코드 상태로만** 전달됨.

---

## 에이전트별 사양

### Agent #1 — P1 숫자 정렬
- **분야**: typography 정밀도 (font-mono / tabular-nums)
- **영향 파일**:
  - `frontend/src/components/ui/HybridSliderInput.tsx` — 숫자 input
  - `frontend/src/App.tsx` — 숫자 표시 영역 grep 후 누락 일괄 적용
- **작업 디테일**:
  1. `HybridSliderInput.tsx`의 숫자 input className에 `font-mono tabular-nums` 추가
  2. `App.tsx` grep으로 숫자 표시 영역 점검:
     - `{number.toLocaleString(...)}`, `{value.toFixed(...)}`, `₩`/`%`/`분기`/`명`/`m`/`평` 단위 표시
     - 한국어 텍스트 안 숫자(예: "약 20초 소요")는 적용 X — 숫자 단독 표시만
- **검증 기준**:
  - tsc/build 통과
  - 슬라이더 움직일 때 자릿수 흔들림 X
- **절대 금지**:
  - layout className 변경
  - border/색감 변경
  - copy 변경
  - state hook 변경

### Agent #2 — P2+P3 layout 정밀화
- **분야**: visual hierarchy (border 톤 + 시각 무게 균일화)
- **영향 파일**: `frontend/src/App.tsx` 좌측 패널 안만 (line ~1430~1865)
- **작업 디테일**:
  - **P2 — border 통일**:
    - 좌측 패널 안 `border-[#3a3633]` → `border-white/5`
    - 시뮬 결과 패널의 `border-stone-800/40, /60`은 **그대로 유지** (영역 분리 의도)
    - Core 박스 `border-indigo-500/20` 강조 그대로
  - **P3 — 시각 무게 균일화**:
    - 객단가 button group을 슬라이더와 같은 박스 패턴으로 wrap:
      ```tsx
      <div className="px-4 py-3 rounded-lg border border-white/5 bg-[#1e1b18]/40">
        <label>...</label>
        <div className="grid grid-cols-2 gap-1.5 mt-2">{PRICE_RANGES.map(...)}</div>
      </div>
      ```
    - 시간대 button group 동일 패턴
    - 가중치 토글은 이미 박스 형태(이전 commit `d90cbe2`) — 동일 톤 확인
- **검증 기준**:
  - tsc/build 통과
  - Operating Constraints 섹션 안 모든 입력 cell이 비슷한 height + 동일 border 톤
- **절대 금지**:
  - HybridSliderInput.tsx 내부 변경 (P1이 이미 적용)
  - 입력 컴포넌트 props/state/onClick 변경
  - SectionLabel 사용처 변경 (Agent #3 영역)
  - 한국어 copy 변경

### Agent #3 — SectionLabel 톤 한국어
- **분야**: copy / i18n
- **영향 파일**: `frontend/src/App.tsx` (SectionLabel 호출부 3곳)
- **작업 디테일**:
  ```tsx
  // Before:
  <SectionLabel icon={MapPin} title="Core Parameters" sub="필수 분석 대상" />
  <SectionLabel icon={Sliders} title="Operating Constraints" sub="입지·운영·재무 조건" />
  <SectionLabel icon={UserCheck} title="Target Audience" sub="타겟 고객 프로필" />

  // After:
  <SectionLabel icon={MapPin} title="핵심 파라미터" sub="Core Parameters · 필수 항목" />
  <SectionLabel icon={Sliders} title="운영 조건" sub="Operating Constraints · 입지·재무" />
  <SectionLabel icon={UserCheck} title="타겟 고객" sub="Target Audience · 페르소나" />
  ```
  - `SectionLabel.tsx` 컴포넌트 자체는 변경 없음 — props만
- **검증 기준**: tsc/build 통과
- **절대 금지**: 다른 영역 일체 X (가장 작은 작업 = 가장 좁은 영역 격리)

---

## 역할 분담

| 역할 | 책임 | 권한 |
|---|---|---|
| **에이전트** | 코드 변경 + tsc + build + prettier 실행 + 보고 | 파일 편집만. **git commit/push 금지** |
| **메인 (Claude)** | 사양 작성 → 위임 → git diff 검증 → commit + push → 강민 브리핑 → 다음 라운드 결정 | git 작업, 라운드 흐름 통제 |
| **강민** | 매 라운드 후 dev 시각 확인 → 승인 또는 수정 요청 | 최종 승인 게이트 |

### 메인 검증 체크리스트 (각 라운드)
1. `git diff --stat` — **사양에 명시된 파일만 변경**됐는지 확인 (외부 영역 손댐 = 거절)
2. `git diff` 일부 샘플링 — 의도된 변경인지 (예: P1에서 layout className 같이 바뀌었으면 X)
3. tsc/build 결과 직접 재확인 (에이전트 보고 신뢰하되 재검증)
4. 이상 없으면 commit + push
5. 강민에게 commit hash + 변경 요약 + dev 검증 부탁 메시지

### 에이전트 보고 형식 (필수)
```
- 변경 파일 목록 + 각 라인 변화
- tsc/build 통과 여부
- 사양 외 변경 (있으면 사유 명시)
- 우려/보존사항
```

### 라운드 간 컨텍스트 전달
- **에이전트 → 다음 에이전트**: 직접 메시지 X (격리 핵심)
- **공통 입력**: git 상태 (= 이전 commit이 적용된 코드)
- 메인이 사양 작성 시 "이전 라운드는 git에 적용됨, 그 위에서 작업"이라고 명시

### 거절 → 재시작 흐름
에이전트가 사양 외 영역 손대거나 빌드 깨짐 시:
1. 메인이 git diff로 발견
2. 변경 사항 `git checkout HEAD -- <files>` 로 되돌림
3. 사양에 "절대 손대지 말 것" 항목 강조해서 재위임

---

## Commit 구조

```
[Round 1] feat(simulator): P1 — font-mono / tabular-nums 일관 적용
[Round 2] feat(simulator): P2+P3 — border 톤 통일 + 시각 무게 균일화
[Round 3] feat(simulator): SectionLabel 톤 한국어 전환
```

- 단일 브랜치 다커밋 관례 (메모리 `feedback_agent_branch_convention`)
- 각 commit 메시지에 변경 영역 + tsc/build 통과 명시
- Co-Authored-By Claude Opus 4.7 footer 포함

## PR 처리
- 현재 `feature/demographic-depth-agent` = origin/dev 대비 16 commit ahead (PR #125 머지 후 누적)
- 이번 3 commit 추가 → 19 commit ahead
- Plan C 완료 시점에 강민 결정으로 새 PR 생성 → dev 머지 (번호는 GitHub 자동 부여)

---

## 검증

각 라운드 후 통과 기준:
- [ ] `cd frontend && npx tsc --noEmit` — 0 error
- [ ] `cd frontend && npm run build` — 통과
- [ ] `git diff --stat` — 사양 명시 파일만 변경
- [ ] 강민 dev 서버 hard reload 후 시각 확인 OK

전체 완료 기준:
- [ ] 3 라운드 모두 강민 승인
- [ ] tsc + build 최종 통과
- [ ] 외부 사용처(다른 페이지/컴포넌트)에 회귀 없음

---

## 핵심 원칙 (이번 세션 정착, 본 spec에서도 적용)

1. **거짓 양성 = 법적·신뢰 리스크** — 입력 컴포넌트 본질 변경 금지
2. **단일 브랜치 다커밋** — 새 PR 분리 제안 금지
3. **런타임 검증은 강민 직접** — 매 라운드 dev 서버 시각 확인 필수
4. **페르소나 필터** — 본부 영업팀장 기준 (터미널 톤/9px 미만 폰트/Stepper 거부)
5. **git 레이어 격리** — 에이전트 간 컨텍스트 공유는 git 상태로만, 직접 메시지 X
