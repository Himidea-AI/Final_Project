# 프런트엔드 코드 리뷰 — 2026-05-09

**범위**: `frontend/` (Vite(요즘 표준으로 쓰는 프론트엔드 빌드 도구) + React 18(화면을 컴포넌트 단위로 짜는 프론트엔드 라이브러리) + TypeScript(자바스크립트에 타입 안전성을 더한 언어) + Tailwind(CSS 클래스 유틸리티 프레임워크) + Zustand(React 의 상태 관리 라이브러리. 화면 사이에서 공유하는 데이터를 보관) + Vitest(테스트 자동 실행 도구))

**최고 심각도**: HIGH (CRITICAL 없음) — 즉, "당장 서비스가 멈추는 수준"의 결함은 없지만, "곧 터질 수 있는" 큰 문제는 있음.

---

## 🚨 한 줄 진단

**ABM(에이전트 기반 시뮬레이션) 화면 핵심 데이터가 `any` 타입(타입 검사를 사실상 끔) + ABM API(백엔드 호출) 호출이 JWT(로그인 인증 토큰) 헤더를 우회 + nginx(프론트엔드 정적 파일을 서빙하고 백엔드로 요청을 넘겨주는 웹 서버) 라우팅 1 곳 누락.**

## 비전문가용 요약

- **무엇이 잘 됐나요?** simulationStore(시뮬레이션 결과를 보관하는 데이터 저장소) 의 상태 관리 설계 — 일부 호출이 실패해도 나머지는 살리는 처리, 영원히 로딩 중으로 멈추는 "좀비 상태" 방지, 새로고침 시 진행 상황 자동 복원 — 와 입력 이스케이프(사용자 입력에 섞인 위험한 문자를 무해화), 안전한 리다이렉트(이상한 외부 사이트로 튕기지 않도록 검증) 등 보안 기본기는 잘 갖춰져 있습니다.
- **무엇이 문제인가요?**
  - ABM 결과 화면 데이터가 `any` 타입 → 잘못된 형태의 데이터가 들어와도 TypeScript 가 미리 잡아주지 못함. 화면이 조용히 깨질 수 있음.
  - ABM 호출이 별도 fetch(브라우저 기본 통신 함수) 함수를 써서 인증 토큰(Authorization 헤더, "이 사용자는 로그인된 사람입니다" 라고 알려주는 표식) 이 자동으로 붙지 않음. 백엔드가 로그인 검사를 강화하는 순간 즉시 401(인증 실패) 에러.
  - 폐점 평가 페이지(`/vacancy-evaluation`) 가 개발 환경(dev) 에선 동작하지만 운영 환경(prod) 의 nginx 설정에 누락 → 사용자가 누르면 404(페이지 없음).
  - JWT 가 localStorage(브라우저에 데이터를 저장하는 저장소. JS 로 쉽게 읽을 수 있어 보안에 약함) 에 저장되어 XSS(악의적 스크립트가 사용자 브라우저에서 실행되는 공격) 시 토큰 탈취 가능 (중기적으로 httpOnly cookie(JS 가 읽을 수 없게 보호된 쿠키. 토큰 탈취 방어에 유리) 권장).
- **얼마나 위험한가요?** P1 (1순위 다음 2순위). 백엔드 보안 강화와 동시 작업 필요.
- **얼마나 걸리나요?** 합쳐 1 일.

## 가장 시급한 4 가지

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| H-1 | `src/stores/abmStore.ts:89,102` | `result/displayResult: any` (타입 검사 비활성) | `AbmResult` 인터페이스(데이터 모양 명세) 정의 |
| H-2 | `src/stores/abmStore.ts:245-254` | `fetchWithTimeout` 가 Authorization 헤더(인증 토큰) 안 붙임 | 표준 `apiClient`(인증을 자동 붙여주는 통신 객체) 사용 또는 토큰 수동 주입 |
| H-3 | `frontend/nginx.conf` | `/vacancy-evaluation` 프록시(요청 전달) 규칙 누락 | location 블록(특정 주소 처리 규칙) 추가 |
| H-4 | `src/auth/AuthContext.tsx:91` | JWT 를 localStorage 에 저장 (XSS 시 탈취 가능) | 단기: CSP(어떤 스크립트를 실행 허용할지 지정하는 보안 헤더) / 중기: httpOnly cookie 전환 |

---

## 1. Stack & Build (사용 기술과 빌드 환경)

프런트엔드는 Vite 5 + React 18 + TypeScript 5 기반의 비교적 표준적인 SPA(Single Page Application — 한 페이지에서 화면만 갈아끼우는 방식의 웹앱) 구성입니다. 스타일은 Tailwind 3 와 PostCSS(CSS 를 후처리해주는 도구) 를 사용하고, 상태 관리는 Zustand 의 `persist`(상태를 브라우저 저장소에 저장해 새로고침해도 유지) + `partialize`(저장할 항목만 골라내는 기능) 미들웨어(중간에서 가공해주는 코드) 조합으로 새로고침 복원과 부분 직렬화(필요한 데이터만 저장 형태로 변환) 를 처리합니다. 테스트는 Vitest 와 React Testing Library(컴포넌트 동작을 검증하는 테스트 도구), 린트(코드 스타일·오류 검사) 는 ESLint + Prettier 가 pre-commit 훅(`.githooks/`, 커밋 직전에 자동 실행되는 스크립트) 에서 자동 실행됩니다. 빌드 결과물은 `frontend/dist/` 에 떨어지고 nginx 가 정적 파일을 서빙합니다.

빌드 스크립트(자동화 명령) 와 운영 배포 사이에는 약간의 불일치가 있습니다. `package.json` 의 `build` 스크립트는 `tsc && vite build` 로 정의되어 타입 검사를 거치도록 되어 있지만, 운영용 `frontend/Dockerfile:10` 은 `RUN npx vite build` 만 실행합니다. 즉, `[C2-핫픽스]`(긴급 패치) 주석이 달려 있는 상태로 타입 검사를 건너뛰고 있어 런타임(실제 사용자 화면에서 코드가 실행될 때) 에서야 타입 오류가 드러날 수 있습니다. 별도 deploy 리뷰(R-1) 항목으로 분리해 추적합니다.

| 항목 | 값 | 비고 |
|------|----|----|
| 빌드 도구 | Vite 5 | `frontend/vite.config.ts` |
| 언어 | TypeScript ~5.x | `frontend/tsconfig.json` |
| UI 프레임워크 | React 18 | `frontend/package.json` |
| 스타일 | Tailwind 3 + PostCSS | `frontend/tailwind.config.js` |
| 상태관리 | Zustand (partialize, persist) | `src/stores/` |
| 테스트 | Vitest + RTL | `frontend/vitest.config.ts` |
| 빌드 출력 | `frontend/dist/` → nginx 정적 서빙 | `frontend/Dockerfile` |
| Lint | ESLint + Prettier (pre-commit hook) | `.githooks/` |

---

## 2. 디렉토리 구조 (코드를 어떤 폴더로 나눠뒀는가)

`frontend/src/` 는 도메인(서비스가 다루는 주제 영역) 단위로 합리적으로 나뉘어 있습니다. `api/` 는 FastAPI(파이썬 백엔드 프레임워크) 호출 어댑터(중계 코드) 와 DTO(데이터 전송 객체, 백엔드와 주고받는 데이터의 모양) 매퍼(변환기) 를, `auth/` 는 JWT 와 AuthContext(앱 전역에서 로그인 정보를 공유하는 React 의 데이터 통로) 를, `stores/` 는 Zustand 스토어(시뮬레이션·ABM)를 담당합니다. 정적 데이터(고정된 참조 데이터) 는 `data/seoulRegions.ts` 같은 파일에, 페이지별 prop(컴포넌트에 넘겨주는 입력값) 가공 로직은 `viewmodels/` 에 분리되어 있습니다. 보안 유틸은 `utils/` (safeRedirect — 안전한 페이지 이동, escapeHtml — HTML 위험 문자 무해화 등) 에 모여 있습니다.

아래는 폴더 구조 한눈에 보기입니다.

```
frontend/src/
├── api/            # FastAPI 호출 어댑터 + DTO mapper
├── auth/           # AuthContext, JWT 로컬스토리지 매니징
├── components/     # 공유 UI + SimulationResult 트리
├── constants/      # 상수, 라벨, 색상 토큰
├── contexts/       # React Context 래퍼
├── data/           # seoulRegions.ts 등 정적 데이터
├── hooks/          # useSimulation, usePoller 등
├── pages/          # LoginPage, SignupPage, MarketingPage 등
├── stores/         # zustand store (simulationStore, abmStore)
├── types/          # 도메인 타입 정의
├── utils/          # safeRedirect, escapeHtml, format 헬퍼
└── viewmodels/     # 페이지별 prop 가공
```

다만 `pages/`(페이지 단위) 와 `components/`(부품 단위) 의 경계가 흐려져 있는 부분이 있습니다. 가장 큰 원인은 `App.tsx` 가 라우팅(주소별 화면 전환) 과 폼, 대시보드 컴포넌트 일부까지 직접 들고 있는 god component(한 파일이 너무 많은 책임을 떠안은 비대 컴포넌트) 라는 점입니다. 이 파일은 2,736 줄에 달하며, 본 리뷰에서 가장 시급하지는 않지만 가장 광범위한 리팩터링(동작은 그대로 두고 코드 구조만 정리) 대상입니다.

---

## 3. 라우팅 & 페이지 (URL 별 화면 연결)

진입점(앱이 처음 시작되는 파일) 은 `frontend/src/main.tsx` 에서 `App.tsx` 로 이어지는 단일 트리이며, 라우팅은 React Router DOM(주소에 따라 화면을 바꿔주는 라이브러리) 으로 구성되어 있습니다. 주요 라우트는 인증 흐름(`/login`, `/signup`, `/forgot-password`, `/reset-password`), 대시보드(`/dashboard`, `/dashboard/result/...`), 그리고 lazy(필요할 때만 코드를 늦게 불러오는 방식) 로 분리된 마케팅 페이지(`/marketing/*`) 입니다. 인증 후 리다이렉트(다른 페이지로 자동 이동) 는 `safeRedirect` 유틸을 거쳐 open redirect(공격자가 외부 악성 사이트로 사용자를 튕겨내는 취약점) 를 방어합니다.

라우팅 자체에 큰 문제는 없지만, 운영 환경에서만 드러나는 함정이 하나 있습니다. `vite.config.ts:25-28` 의 dev 프록시(개발 중 백엔드로 요청을 넘겨주는 규칙) 에는 `/vacancy-evaluation` 이 정의되어 있는데 `frontend/nginx.conf` 에는 동일한 location 블록이 누락되어 있어, 개발 환경에서는 정상 동작하던 폐점 평가 페이지가 prod 빌드(운영 배포본) 에서는 404(페이지 없음) 를 반환합니다. 이 문제는 H-8 항목으로 별도 추적합니다.

---

## 4. 상태 관리 (화면들이 공유하는 데이터의 보관·갱신)

상태 관리 영역은 본 리뷰에서 **가장 강점과 약점이 극명하게 갈리는 부분**입니다. 두 스토어(데이터 저장소) 가 같은 패턴을 공유하지 않고, 한쪽은 모범 사례, 다른 쪽은 타입·인증 안전망이 모두 빠진 상태입니다.

### 강점: `src/stores/simulationStore.ts`

시뮬레이션 스토어는 비동기(여러 작업이 동시에 진행되는 처리) 상태 관리의 모범 사례를 잘 따르고 있습니다. 여러 슬라이스(부분 데이터 묶음) 를 병렬로 호출할 때 `Promise.allSettled`(여러 호출 결과를 모두 기다리되 하나가 실패해도 나머지를 살림) 를 써서 일부 실패가 전체를 깨뜨리지 않도록 처리하고, `nextStartedAt()` 으로 monotonic timestamp(절대 뒤로 가지 않는 시각 표식) 를 발급해 늦게 도착한 stale 응답(낡은 응답) 이 최신 상태를 덮어쓰지 못하게 가드(보호) 합니다. 새로고침 복원 시에는 `partialize` 단계에서 `running`(진행 중) 이나 `error` 상태를 강제로 `idle`(대기) 로 복원해 좀비 상태(영원히 로딩 중인 UI)를 방지합니다. 단위 테스트(개별 함수 단위 자동 검증) 도 이 동작들을 약 20 케이스로 커버합니다.

### 약점: `src/stores/abmStore.ts`

ABM(Agent-Based Model — 가상 손님 1000 명을 만들어 행동을 시뮬레이션하는 기능) 스토어는 같은 시기에 만들어졌음에도 안전망이 거의 빠져 있습니다. 가장 큰 문제는 **타입 누락**과 **인증 우회** 두 가지입니다.

#### 왜 중요한가 — 타입 누락 (H-1)

`result: any | null`, `displayResult: any | null` (89, 102 줄) 로 선언되어 있어, 백엔드가 잘못된 모양의 데이터를 보내도 TypeScript 가 검출하지 못합니다 (`any` 는 "어떤 타입이든 허용" 이라는 뜻으로, 사실상 검사 자체를 끄는 효과). 결과 화면은 이 데이터를 직접 바인딩(화면 요소와 데이터를 연결) 하므로, 필드 이름이 한 글자라도 바뀌면 런타임에서 조용히 `undefined`(값이 없음) 가 렌더링됩니다. 게다가 `AbmTab.tsx:92` 에서 `const r = simResult as any`(as any: 타입 검사를 강제로 끄는 TypeScript 문법) 로 다시 한 번 단언하고 있어 컴파일 타임(코드 변환 시점) 안전망이 두 단계로 비활성화되어 있습니다.

**어떻게 고치나** — `AbmResult` 인터페이스(데이터 모양 정의서) 를 `src/types/` 에 정의하고 스토어와 탭 컴포넌트에서 모두 교체합니다. H-1 과 H-9 는 한 묶음으로 처리해야 합니다.

#### 왜 중요한가 — 인증 헤더 우회 (H-2)

`fetchWithTimeout` (245–254 줄) 이 native `fetch`(브라우저가 기본 제공하는 통신 함수) 를 직접 호출합니다. 프로젝트 표준은 Axios(통신 라이브러리) 인스턴스(`src/api/client.ts`) 의 인터셉터(API 호출 직전·직후에 자동으로 끼어드는 코드) 에서 `Authorization: Bearer <token>`(요청에 인증 토큰을 붙이는 표준 방식) 을 자동 주입하는 방식인데, ABM 호출만 이 경로를 우회하고 있습니다. 현재는 백엔드가 JWT 를 강제하지 않아 동작하지만, **백엔드 인증 강화가 머지(코드 통합) 되는 순간 ABM 시뮬레이션이 즉시 401**(인증 실패) 을 반환합니다.

**어떻게 고치나** — `apiClient.post`/`apiClient.get` 으로 교체하거나, 정 timeout(응답 대기 시간 한도) 컨트롤이 필요하면 `Authorization` 헤더를 수동으로 주입한 fetch 래퍼(감싸기 함수) 를 만들어야 합니다.

#### 부수적 약점

폴링(서버에 주기적으로 진행 상황을 물어보는 동작) 관련 코드 338, 342, 557 줄에서 `void get()._pollStatus()` 형태로 fire-and-forget(결과를 기다리지 않고 던져만 두는 호출) 호출을 하고 있어, `setInterval`(일정 간격마다 함수를 반복 실행하는 타이머) 콜백 내부에서 unhandled rejection(처리되지 않은 비동기 오류) 이 발생할 여지가 있습니다. 또한 `partialize` 가 `history` 배열을 직렬화에서 제외해 새로고침 시 히스토리가 사라지는데, 이게 의도라면 코드에 주석이 있어야 하지만 현재는 없습니다. 한편 새로고침 후 진행 중인 ABM 작업의 polling 을 자동 재개하는 `resumePollingIfNeeded` 패턴은 잘 설계되어 있어, 이 부분은 simulationStore 수준으로 격상시킬 가치가 있습니다.

### `src/auth/AuthContext.tsx`

로그인 성공 시 91 줄에서 `localStorage.setItem('spotter_auth', JSON.stringify({user, brand, token}))` 로 JWT 를 평문(암호화되지 않은 그대로의 형태) 으로 저장합니다. 이는 XSS 한 번이면 토큰이 그대로 빠져나갈 수 있는 구조라, 중기적으로는 httpOnly cookie 로 옮기고, 단기적으로는 CSP 헤더로 인라인 스크립트(HTML 안에 직접 박힌 자바스크립트) 실행 표면을 좁히는 것이 권장됩니다. 보조적으로 83–85 줄에서 `_readStoredAuth()` 가 3 회 중복 호출되는 비효율(같은 일을 세 번 반복) 도 있습니다.

---

## 5. API Layer (`src/api/client.ts`) — 백엔드와 통신하는 코드 모음

API(API endpoint — 백엔드가 제공하는 호출 가능한 주소) 레이어는 Axios 인스턴스 + 인터셉터 구조로 잘 잡혀 있습니다. 인터셉터가 `Authorization: Bearer` 를 자동 주입하므로 일반적인 호출은 인증을 신경 쓸 필요가 없습니다. 다만 4 가지 잔존 이슈가 있습니다.

첫째, 51 줄의 `MOCK_WORKSPACE_ID = 'spotter-demo-workspace-01'`(가짜 워크스페이스 식별자) 가 하드코딩(코드 안에 값이 직접 박혀 있음) 되어 있습니다. 이는 데모/테스트 흔적이 운영 코드에 남은 것으로, `import.meta.env.VITE_WORKSPACE_ID`(환경 변수 — 환경별로 외부에서 주입하는 설정값) 로 외부화하는 것이 안전합니다.

둘째, `getOperatedIndustries` (294–297 줄) 가 `try { ... } catch { return [] }`(에러가 나면 빈 배열을 돌려주고 끝) 패턴으로 모든 에러를 빈 배열로 묻어버립니다. 백엔드 `/operated-industries` 가 500(서버 내부 오류) 을 반환해도 사용자에게는 그저 "운영 업종이 없는 화면" 으로 보이게 되어, **버그가 데이터 부재로 위장**됩니다. 이는 백엔드의 `except Exception: pass`(파이썬에서 모든 예외를 무시) 와 정확히 같은 안티패턴(피해야 할 나쁜 관행) 의 프론트 등가입니다. 에러를 상위로 전파하거나 최소한 토스트(화면에 잠깐 떴다 사라지는 알림 메시지)/로깅이 필요합니다.

셋째, `getLivePopulation(): Promise<any>` (259 줄) 처럼 반환 타입(함수가 돌려주는 값의 모양) 이 빠진 함수가 있어 호출부에서 타입 검사가 무력화됩니다.

넷째, 백엔드 raw row(가공 전 원본 한 행 데이터) 를 프론트 도메인 타입으로 변환하는 매퍼 4 종(`mapForeseeDetailToHistoryDetail`, `mapAIDetailToHistoryDetail`, `mapForeseeListItem`, `mapAIListItem` — 436, 491, 541, 557 줄) 의 입력이 모두 `Record<string, any>`(키는 문자열이지만 값은 어떤 타입이든 가능 — 사실상 검사 없음) 입니다. 이 경계는 백엔드와 프론트의 데이터 형태가 처음 만나는 지점이라 가장 타입 안전이 필요한 곳임에도, 현재는 사실상 검증 없이 통과합니다. `RawForeseeRow`, `RawAIRow` 같은 인터페이스를 정의해 매퍼 시그니처(함수의 입출력 명세) 를 좁혀야 합니다(H-5).

---

## 6. 컴포넌트 패턴 (화면 부품을 짜는 방식)

`components/ui/` 에는 Button, FormField(라벨 + 입력 칸 묶음), Modal(팝업창), Toast 같은 공유 프리미티브(여기저기서 쓰는 기본 부품) 가 모여 있고, 결과 화면은 `SimulationResult/dashboard/` 아래에 탭 단위(ForeseeTab, AITab, AbmTab)로 잘 분리되어 있습니다. 다만 두 가지 접근성·안전성 이슈와 한 가지 구조적 이슈가 있습니다.

**접근성 (FormField)** — 접근성(시각 장애인 등 보조 도구를 쓰는 사용자도 화면을 쓸 수 있게 하는 설계). `FormField.tsx:46` 의 `<label>`(입력 칸 설명 표) 에 `htmlFor`(어떤 입력 칸과 짝지어진 라벨인지 알려주는 속성) 가 없습니다. 화면에는 정상으로 보이지만 스크린리더(시각장애인용 화면 읽어주는 프로그램) 는 라벨과 입력을 연결하지 못합니다. 동일 패턴이 `LoginPage.tsx:147-183` 의 email/password input 에도 있어, 로그인 폼 자체가 스크린리더 사용자에게 사용 불가입니다. 접근성 위반은 법적 요건이 되는 시장도 있으므로 우선순위를 낮게 잡기 어렵습니다.

**타입 안전 누수 (AbmTab)** — `tabs/AbmTab.tsx:92` 의 `const r = simResult as any` 는 H-1 의 후속 문제입니다. abmStore 의 `AbmResult` 인터페이스가 정의되면 자동으로 해소됩니다.

**god component (AbmPersonaMap)** — `AbmPersonaMap.tsx` 는 3,827 줄로, 캔버스 렌더러(브라우저의 그림판 영역에 직접 도형/이미지를 그리는 코드)·Kakao Map 래퍼(카카오 지도 API 를 감싸는 코드)·시나리오 패널이 한 파일에 합쳐져 있습니다. 단일 책임 원칙(한 파일·한 함수는 한 가지 일만) 위반이며 진단·수정 비용이 비례해서 늘어납니다. 또한 282 줄에서 `(import.meta as any).env?.VITE_KAKAO_MAP_API_KEY` 처럼 불필요한 `as any` 단언이 있는데, `import.meta.env.VITE_KAKAO_MAP_API_KEY` 로 직접 접근하면 됩니다(H-10).

마지막으로 `dashboard/charts/ScenarioComparisonChart.tsx` 와 `ScenariosComparisonChart.tsx` 의 단/복수 차이로 인한 명칭 혼동(같은 듯 다른 두 파일이 공존) 이 있어, 한쪽으로 통일하고 다른 하나는 deprecated(폐기 예정) 처리하는 것이 좋습니다.

---

## 7. 인증 흐름 (사용자가 로그인해서 보호된 기능을 쓰는 과정)

전체 흐름은 표준적입니다. (1) `LoginPage` 폼 제출이 `apiClient.post('/auth/login', ...)` 을 호출하고, (2) `AuthContext.login()` 이 `{user, brand, token}` 을 localStorage 에 저장한 뒤, (3) Axios 인터셉터가 후속 요청에 `Authorization: Bearer ${token}` 을 자동 부착하며, (4) 새로고침 시 `_readStoredAuth()` 가 상태를 복원합니다.

이 흐름의 두 가지 약한 고리가 앞서 나온 H-2 와 H-4 입니다. abmStore 가 native fetch 를 사용해 (3) 의 인터셉터를 우회하므로, 백엔드 `/api/simulate-abm` 에 JWT 가 강제되는 순간 즉시 401 이 발생합니다. 또한 (2) 의 localStorage 저장은 XSS 한 번이면 토큰이 빠져나가는 구조이므로, 단기적으로는 CSP 헤더 적용, 중기적으로는 httpOnly cookie 전환으로 보호 표면(공격자가 노릴 수 있는 표면적) 을 줄여야 합니다.

---

## 8. 스타일 / 테마 (디자인·색상 관리)

스타일 레이어는 Tailwind 와 자체 CSS Variable System(색상·간격 등을 변수로 정의해 한 곳에서 바꾸면 전체에 반영되는 시스템) 두 축으로 구성되어 있습니다. System A 는 의미 토큰(`--color-bg-primary` 같은 역할 기반 — "주요 배경색" 처럼 의미로 부름), System B 는 색상 토큰(`--blue-500` 같은 원시 색 — 실제 색 이름) 으로 분리되어 있어, 디자인 시스템(전사 디자인 규칙 모음) 으로 진화시키기 좋은 기반입니다.

다만 토큰 시스템 외부로 새는 코드가 두 군데 있습니다. `LoginPage.tsx:232,239` 는 `hover:bg-[#4f46e5]`, `bg-[#3b82f6]`(색상 코드를 그대로 박아 넣음) 처럼 hex 값을 인라인으로 박아 두어 다크모드/테마 변경 시 자동으로 따라오지 못합니다. 또한 `index.css:23-73` 에는 `!important`(다른 모든 스타일을 무시하고 우선 적용하라는 강제 표시) 가 51 줄에 걸쳐 들어가 있어, Tailwind `@layer components`(스타일 우선순위를 깔끔하게 묶는 공식 방법) 로 재구성해 우선순위 싸움을 줄이는 것이 좋습니다. light/dark 마이그레이션(밝은 테마/어두운 테마 전환 작업) 자체는 `docs/light-mode-migration/` 에서 별도 트랙으로 진행 중입니다.

---

## 9. 테스트

스토어 테스트는 비교적 충실합니다. `simulationStore` 가 약 20 케이스(allSettled, monotonic guard, partialize), `abmStore` 가 약 8 케이스, 차트 10 종에 대한 스모크 테스트(가장 기본적인 동작만 빠르게 점검하는 가벼운 테스트) 가 갖추어져 있습니다. 이 정도면 단위 레이어(개별 함수·컴포넌트 수준) 는 안정적이라 볼 수 있습니다.

부족한 부분은 **E2E (End-to-End — 실제 사용자처럼 브라우저를 자동 조작해 처음부터 끝까지 동작을 검증하는 테스트) 와 커버리지(테스트가 코드를 얼마나 폭넓게 검사했는지의 비율) 정책**입니다. 인증 흐름, `pollJobUntilDone` 의 타임아웃 경로, PDF 생성 등 사용자 시나리오 전체를 도는 테스트가 없어 통합 회귀(여러 부품을 합쳤을 때 발생하는 재발 버그) 를 잡기 어렵습니다. Playwright(E2E 자동화 도구) 도입을 권장합니다. 또한 `vitest.config.ts` 에 coverage threshold(커버리지 최소 기준선) 가 설정되어 있지 않아 커버리지가 조용히 하락해도 CI(Continuous Integration — 커밋 시 자동으로 빌드·테스트를 돌리는 시스템) 가 알려주지 않습니다. statements(코드 문장 단위) 기준 ≥70 정도의 보수적인 임계값을 먼저 걸어 두는 것이 좋습니다.

---

## 10. 핵심 이슈 — 사용자 영향 기준 그룹

원래 리뷰에서 HIGH/MEDIUM 으로 나열된 항목들을, 실제 사용자/운영에 미치는 영향 기준으로 다시 묶었습니다.

### 10.1 백엔드 보안 변경과 동시에 깨질 항목

**가장 시급한 분류**입니다. 백엔드에서 JWT 를 강제하거나 인증을 강화하는 순간 즉시 장애로 이어집니다.

- **H-2 — `src/stores/abmStore.ts:245-254`**: `fetchWithTimeout` 가 native fetch 를 직접 사용해 Axios 인터셉터의 Authorization 자동 주입을 우회합니다. 백엔드 JWT 적용 즉시 ABM 시뮬레이션 401. `apiClient` 사용으로 교체하거나 토큰을 수동 주입해야 합니다.
- **H-8 — `frontend/nginx.conf`**: `/vacancy-evaluation` location 블록이 누락되어 prod 에서 404. `vite.config.ts:25-28` 의 dev 프록시 정의와 동기화가 필요합니다.

### 10.2 타입 안전망이 무력화된 영역

데이터가 이상해도 TypeScript 가 잡아주지 않는, 사실상 동적 타이핑(타입을 미리 정하지 않고 실행 중에야 판단되는 방식 — TypeScript 의 장점이 사라짐) 상태인 코드입니다. 런타임 버그가 코드 리뷰와 컴파일 단계를 모두 통과합니다.

- **H-1 / H-9 — `abmStore.ts:89,102` + `AbmTab.tsx:92`**: ABM 결과 핵심 타입이 `any` 로 두 단계에 걸쳐 단언됩니다. `AbmResult` 인터페이스 정의 후 한 번에 교체합니다.
- **H-3 — `tsconfig.json:22-24`**: `src/components/SimulationResult` 트리(폴더 묶음) 전체가 exclude(타입 검사 제외 처리) 되어 있어, MetricCharts·MarketMap 등 가장 복잡한 시각화 코드의 타입 오류가 `tsc`(TypeScript 컴파일러) 단계에서 검출 불가 상태입니다. 더불어 `src/pages/AnalysisDashboard.tsx`, `src/hooks/useSimulation.ts` 는 이미 존재하지 않는 dead exclude(지워진 파일을 가리키는 죽은 항목) 입니다. exclude 를 제거하고 발생하는 타입 오류를 차근차근 수정해야 합니다.
- **H-5 — `src/api/client.ts:436,491,541,557`**: 매퍼 4 종이 `Record<string, any>` 를 받습니다. 백엔드/프론트 경계의 타입 안전이 비어 있습니다. `RawForeseeRow`, `RawAIRow` 인터페이스로 좁혀야 합니다.
- **M — `src/api/client.ts:259`**: `getLivePopulation(): Promise<any>` 반환 타입 누락.
- **M — `as any` 38 회 / 8 파일**: 점진적 제거 대상.

### 10.3 보안 표면

- **H-4 — `src/auth/AuthContext.tsx:91`**: JWT 를 localStorage 에 평문 저장 → XSS 시 토큰 탈취. 단기로는 CSP 헤더, 중기로는 httpOnly cookie 전환이 권장됩니다.
- **M — `src/components/SimulationResult/sections/MarketMap.tsx:214`**: `wrap.innerHTML = ... ${innerHtml}`(HTML 문자열을 그대로 화면에 끼워 넣음) 직접 할당. 현재는 호출부에서 `escapeHtml`(위험 문자 무해화) 을 통과하지만, 미래에 새로운 caller(이 함수를 부르는 다른 곳) 가 들어올 때 누락하면 즉시 XSS 가 됩니다. 함수 내부에서 한 번 더 escape 하거나 텍스트 노드 조립 방식(HTML 문자열 대신 안전한 텍스트 단위로 화면에 추가) 으로 교체하는 것이 안전합니다.

### 10.4 에러를 데이터 부재로 위장하는 코드

사용자 입장에서 "버그" 가 아니라 "데이터 없음" 으로 보이게 되어 디버깅이 가장 어려운 종류입니다.

- **H-7 — `src/api/client.ts:294-297`**: `getOperatedIndustries` 가 모든 예외를 `return []` 로 묻어버립니다. 백엔드 500 이 빈 화면으로 위장됩니다.
- **H-6 — `src/App.tsx:1133`**: `void useSimulationStore.getState().startSimulation(payload); navigate('/dashboard');` 의 fire-and-forget 패턴. startSimulation(시뮬레이션 시작 호출) 이 실패해도 사용자는 그대로 대시보드로 넘어가 빈 화면을 보게 됩니다. `try/catch`(에러를 잡아서 처리하는 구문) 로 감싼 뒤 토스트 등으로 사용자에게 알려야 합니다.
- **부수적** — `abmStore.ts:338,342,557` 의 `void get()._pollStatus()` setInterval 콜백도 같은 계열의 fire-and-forget.

### 10.5 접근성

- **M — `LoginPage.tsx:147-183`**: email/password input 에 `id` 가 없고 `<label>` 에 `htmlFor` 가 없어 스크린리더가 라벨과 입력을 연결하지 못합니다. 로그인 폼 자체가 보조 기술 사용자에게 막힙니다.
- **M — `FormField.tsx:46`**: 같은 패턴의 공유 프리미티브(여러 페이지에서 재사용되는 기본 부품) 단계 누락. 한 곳을 고치면 다수 페이지가 함께 개선됩니다.

### 10.6 구조적 부채 (즉시 장애는 아님)

기술 부채(지금은 동작하지만 나중에 비용이 누적되는 빚 같은 코드 상태) 항목들입니다.

- **M — `src/App.tsx`**: 2,736 줄 god component. 라우팅·폼·대시보드 일부를 함께 들고 있어 사이드 이펙트(어떤 코드가 의도치 않게 다른 코드의 동작에 영향을 미치는 부작용) 추적이 어렵습니다. `SimulatorDashboard`, `SliceProgressRow`, `useInterpolatedProgress` 등 자연스러운 경계가 보이는 곳부터 분리합니다.
- **M — `src/App.tsx:133-606`**: `DONG_DATA`(서울 동 정보) 가 474 줄에 걸쳐 인라인(코드 중간에 직접 박힘) 되어 있고, 동일 데이터가 `data/seoulRegions.ts` 에도 존재합니다. 단일 소스 통합(한 곳에만 두기) 이 필요합니다.
- **M — `src/api/client.ts:51`**: `MOCK_WORKSPACE_ID` 하드코딩 → 환경 변수로 외부화.
- **M — `package.json:18-19`**: `autoprefixer`, `postcss` 가 `dependencies`(운영용 의존성) 에 있어 prod 번들(배포 묶음 파일)/이미지에 불필요하게 포함될 수 있습니다. `devDependencies`(개발 전용 의존성) 로 이동.
- **M — `src/index.css:23-73`**: `!important` 51 줄. Tailwind `@layer components` 로 재구성.
- **L — `src/App.tsx:782,874,888,1024`**: `eslint-disable react-hooks/exhaustive-deps`(리액트 훅 의존성 검사 규칙을 끄는 주석) 4 건. 의존성을 명시하거나 의도를 주석으로 남겨야 합니다.
- **L — `src/App.tsx:751`**: `FTC_TO_FRONTEND_INDUSTRY` 가 컴포넌트 내부에서 정의되어 매 렌더(화면을 다시 그릴 때마다) 새 객체로 생성됩니다. 모듈 스코프(파일 최상단 — 한 번만 만들어지는 위치) 로 옮기면 메모이제이션(중간 결과를 캐싱해 재계산을 줄이는 기법) 비용이 사라집니다.
- **L — `dashboard/DashboardHub.tsx:32`**: Unsplash CDN(외부 이미지 호스팅) URL 하드코딩. 외부 의존이며 운영 시점 가용성을 보장하기 어렵습니다.
- **L — `ScenarioComparisonChart.tsx` vs `ScenariosComparisonChart.tsx`**: 단/복수 명칭 혼동.
- **L — `auth/AuthContext.tsx:83-85`**: `_readStoredAuth()` 3 회 중복 호출.
- **L — `vitest.config.ts`**: coverage threshold 미설정.
- **L — `tsconfig.json`**: dead exclude entries 2 건(`AnalysisDashboard.tsx`, `useSimulation.ts`).
- **L — `abmStore.ts` partialize**: history 배열 직렬화 제외가 의도라면 주석 명시.

---

## 11. 강점

본 리뷰에서 발견된 강점은 단순히 "잘 되어 있다" 가 아니라, 문제 해결의 모범 사례를 그대로 차용할 수 있는 수준이라는 점이 중요합니다.

**simulationStore 설계** — `Promise.allSettled` 로 부분 실패를 안전하게 처리하고, `nextStartedAt()` monotonic guard 로 stale 응답을 거르며, `partialize` 에서 `running`/`error` 를 강제로 `idle` 로 복원해 좀비 상태(영원히 로딩만 도는 화면) 를 막습니다. 단위 테스트도 약 20 케이스로 동작을 잠가 두었습니다. abmStore 가 도달해야 할 목표가 이미 같은 코드베이스 안에 있다는 점이 큰 장점입니다.

**스토어 테스트 충실** — simulationStore 약 20 / abmStore 약 8 + 차트 10 종 스모크. 단위 레이어는 안정적입니다.

**resumePollingIfNeeded** — 새로고침 후에도 ABM polling 을 자동 재개하는 패턴으로, 사용자가 탭을 닫았다가 다시 열어도 진행 상황을 잃지 않습니다.

**보안 기본기** — `safeRedirect` 로 open redirect 차단, 로그인 응답에서 이메일 열거(enumeration — 어떤 이메일이 가입되어 있는지 공격자가 추측할 수 있게 되는 정보 누출) 방지를 위한 통합 에러 메시지(아이디 틀림/비번 틀림을 구분하지 않고 같은 메시지로 응답), Kakao 팝업 동적 값에 대한 `escapeHtml` 일괄 적용 등이 일관되게 되어 있습니다.

**디자인 토큰** — CSS Variable System A/B 의 이중 구조와 Tailwind alias(별칭) 래핑으로 의미 토큰과 색상 토큰을 분리해 두어 다크모드/리브랜딩(브랜드 색·로고 일괄 변경) 에 유리합니다.

**번들 최적화** — `manualChunks`(파일을 작은 묶음으로 쪼개 필요한 것만 다운로드 받게 하는 설정) 로 벤더(외부 라이브러리) 분할, 마케팅 페이지를 lazy 로 분리해 첫 로드 비용(처음 화면이 뜨는 데 걸리는 시간) 을 낮췄습니다.

**Pre-commit Prettier** — 자동 포맷팅으로 PR(Pull Request — 동료에게 코드 변경분을 검토 받아 합치는 절차) 노이즈가 줄어들어 리뷰 품질이 올라갑니다.

---

## 12. 우선순위 로드맵

각 항목은 사용자 영향과 작업 비용을 모두 고려해 4 단계로 나눴습니다.

### P0 — 즉시 (이번 주)

백엔드 보안 변경과 동시에 깨질 항목, 그리고 운영 환경에서 이미 깨진 항목입니다.

1. **H-2 — abmStore Authorization 헤더 주입**: 백엔드 JWT 도입과 동기화. `apiClient` 사용으로 교체.
2. **H-1 + H-9 — `AbmResult` 인터페이스 정의**: ABM 탭의 두 단계 `as any` 를 한 번에 제거.
3. **H-8 — nginx `/vacancy-evaluation` location 추가**: prod 404 해소.

### P1 — 이번 스프린트(약 2 주 단위 개발 주기)

타입 안전망 복구와 사용자에게 보이는 에러 처리 보완입니다.

4. **H-3 — tsconfig SimulationResult exclude 제거** + 발생하는 타입 오류 수정. dead entries 2 건 정리 동반.
5. **H-6 — App.tsx:1133 `startSimulation` try/catch + 토스트**.
6. **H-7 — `getOperatedIndustries` 에러 전파**.
7. **M — Login/FormField 접근성** (`htmlFor` + `id` 연결).

### P2 — 다음 스프린트

보안 표면 축소와 구조 분리. 백엔드 협의가 필요한 항목 포함.

8. **H-4 — JWT httpOnly cookie 전환**: 백엔드 인증 팀과 협의해 쿠키 도메인/SameSite(쿠키를 어떤 사이트 요청에 함께 보낼지 제한하는 옵션 — CSRF 방어용) 설정을 함께 결정.
9. **H-5 — 매퍼 4 종 인터페이스화** (`RawForeseeRow`, `RawAIRow`).
10. **M — App.tsx 분리**: `SimulatorDashboard`, `SliceProgressRow`, `useInterpolatedProgress` 단위로 추출.
11. **M — AbmPersonaMap.tsx 3,827 줄 분해**: 캔버스 렌더러 / Kakao Map 래퍼 / 시나리오 패널.

### P3 — 백로그(우선순위 낮은 대기 작업 목록)

품질 안전망 확장과 누적된 부채 정리.

12. **E2E (Playwright) 도입** — auth flow, `pollJobUntilDone` 타임아웃, PDF 생성 시나리오.
13. **vitest coverage threshold 설정** (statements ≥70 시작).
14. **`as any` 38 회 점진 제거** — 파일별 PR 분리.
15. **`!important` 51 줄 → `@layer` 재구성**.

---

## 13. 승인 조건

이번 머지의 최소 승인 조건은 **H-1 (AbmResult 타입 정의), H-2 (Authorization 헤더 주입), H-8 (nginx /vacancy-evaluation)** 세 가지입니다. 이 셋은 백엔드 보안 변경 또는 운영 환경 라우팅과 직접 충돌하므로, 머지 시점에 반드시 함께 들어가야 합니다.

H-3 (tsconfig exclude 제거), H-4 (httpOnly cookie 전환), H-5 (매퍼 인터페이스화) 는 작업량이 단일 PR 보다 크고 백엔드 협의가 필요한 부분이 있으므로, 별도 태스크로 분리해 트래킹(추적 관리) 하기를 권장합니다. 그 외 MEDIUM/LOW 항목은 P1–P3 로드맵에 따라 정기 스프린트에서 소화하면 됩니다.
