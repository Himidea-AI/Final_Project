# 마포 ABM 시뮬레이션 · 시각화 로드맵

> Gemini 4차 조언 + A1 피드백 종합. 구현 우선순위·기술 스택·프레젠테이션 서사까지 한 문서로.

---

## 0. 프로젝트 위치

**단순 코딩 과제가 아님** — "데이터로 도시의 맥락을 읽어내는 인사이트 도구(BI 툴)" 포지셔닝.

한 줄 어필 문장:
> "마포구 공공 데이터 기반 **1,000 페르소나가 하루 동안 생성한 약 1만 건의 의사결정 로그**를 실시간 시각화한 결과입니다."

---

## 1. 완료된 것 (2026-04-20 기준)

### 데이터 파이프라인
- [x] RDS 7+5 테이블 통합 (living_population, dong_subway_access, apt_trade_real, naver_trend_industry, kakao_store, kakao_store_hours, kakao_store_menu, weather_daily, holiday_calendar, district_sales_seoul, mapo_sns_sentiment, pgvector)
- [x] AgentProfile 개인화 (동/연령/성별/소득/취향/이동성)
- [x] 매장 메뉴 JOIN → 실제 가격 기반 spend 계산
- [x] 날씨·휴일 → 이동 확률 영향
- [x] 매출·SNS 감성 → 매장 popularity_boost

### 에이전트 시뮬레이션
- [x] Tier S/A/B 계층화 (50/200/750)
- [x] 원시어 DSL 대화 (5 verbs × 친구 네트워크)
- [x] pgvector 메모리 인덱스
- [x] Scenario 충격 (주말·임대료)
- [x] trajectory / visits / chats / friends / stores 5종 사이드카 dump

### 시각화
- [x] Streamlit 대시보드 (Folium + Plotly 2중 구조)
- [x] 테스트 프론트엔드 (`test_frontend/` — Vite+React+Leaflet)
- [x] 누적 히트맵 (`leaflet.heat`)
- [x] 이벤트 링 (정적 Circle)
- [x] 에이전트 크기 = 누적 지출
- [x] Tier별 링 색 (S=금색)
- [x] 5초 폴링 LIVE 모드
- [x] 좌표 보간 부드러운 이동 (requestAnimationFrame + lerp)

### 백엔드 API
- [x] `GET /api/simulation/*` 7개 엔드포인트
- [x] CORS 3001 허용
- [x] 프론트 통합 문서 (`docs/simulation-frontend-integration.md`)

---

## 2. 우선순위별 TODO (Gemini 조언 반영)

### ⭐⭐⭐ 최우선 — 시각적 임팩트

#### T1. 이벤트 링 Pulse (CSS Keyframe)
**문제**: 현재 `<Circle>` 정적 → "돈이 흐르는 순간" 감각 부족
**해결**: CSS `@keyframes` + one-time class 토글
```css
.ripple.is-spending {
  will-change: transform, opacity;
  animation: ripple 1.2s ease-out;
}
@keyframes ripple {
  from { r: 8; opacity: 1; }
  to   { r: 120; opacity: 0; }
}
```
```ts
// 지출 이벤트 발생 시
markerEl.classList.add("is-spending");
markerEl.addEventListener("animationend",
  () => markerEl.classList.remove("is-spending"),
  { once: true });
```
**효과**: 1000개 동시 애니메이션 아니라 **이벤트 순간만** → 브라우저 부담 제로 + 팝콘 터지는 느낌

#### T2. 친구 네트워크 Hover
**구현**: 에이전트 hover → `L.polyline` 일시 생성 → friends로 선 긋기
```tsx
onMouseOver={(e) => {
  const agent = e.target.options.agent;
  const lines = agent.friends.map(fid => ...);
  setHoverLines(lines);
}}
onMouseOut={() => setHoverLines([])}
```
**의미**: "왜 사람들이 같이 이동하는가"를 시각적으로 증명 → 군집 현상의 **사회적 근거**

---

### ⭐⭐ 중요 — 구조/흐름

#### T3. OD 이동량 가중치 선 (그라데이션)
**구현**:
1. trajectory에서 `(hour N, dong A) → (hour N+1, dong B)` 집계 → OD 매트릭스
2. `L.Polyline` weight = 이동 인원수
3. 방향성 = SVG `<linearGradient>` (출발 연한색 → 도착 진한색)

**왜 곡선(Bezier) 안 쓰는가**: 실제 이동 경로와 괴리 → 데이터 왜곡. 직선 + 굵기 + 그라데이션으로 **연결성·흐름·방향성** 동시 확보.

```tsx
<svg>
  <defs>
    <linearGradient id={`od-${from}-${to}`} x1="0" x2="1">
      <stop offset="0" stopColor="#818cf8" stopOpacity="0.3" />
      <stop offset="1" stopColor="#c7243a" stopOpacity="0.9" />
    </linearGradient>
  </defs>
</svg>
```

#### T4. POI 앵커 마커 (계층적 노출)
**대상**: 홍대입구역 · 망원시장 · 메세나폴리스 · 경의선숲길 · 공덕역 · 합정역 · 상암 DMC · 마포구청

**스타일**:
- z-index 최상위 (다른 마커 위)
- `text-stroke: 2px #000` + 배경 박스 → 지도 배경 상관없이 읽힘
- 줌 10 이하엔 상위 3~4개만, 줌 14+에선 모두 노출

---

### ⭐ 디테일

#### T5. 뷰 모드 탭 (Micro / Event / Macro)
발표 스크립트와 1:1 대응하는 3개 버튼.

| 모드 | 기본 레이어 | 에이전트 opacity | 카메라 |
|------|-----------|----------------|--------|
| Micro | 친구 네트워크 ON, 흐름선 OFF | 선택자 1.0, 나머지 0.3 | 선택 에이전트로 flyTo zoom 16 |
| Event | 이벤트 링 강조, 대화 ON | 0.6 | 현재 시점 유지 |
| Macro | OD 흐름선 + 히트맵 | 0.15 | 마포 전역 zoom 13 |

전환 시 `transition: opacity 0.6s ease` 적용 → fade 효과.

#### T6. Auto Tour
`▶ Auto Tour` 버튼:
- 30초 Micro → 30초 Event → 60초 Macro 자동 순환
- 각 구간 해설 오버레이 ("김지유가 망원시장으로 이동..." 등)
- 발표 중 손 대지 않고 진행 가능

#### T7. 자동 리포트 (Macro 도달 시)
> 🚚 **오늘 하루 마포구 주요 이동축**
> - 연남 → 합정: 32명
> - 공덕 → 마포: 28명
> - 망원 → 홍대: 25명

trajectory 집계만으로 생성 가능 (추가 쿼리 X).

---

## 3. 프레젠테이션 서사 — Micro · Event · Macro

Gemini가 제안한 **발표 핵심 각본**.

```
┌──────────┐      ┌──────────┐      ┌──────────┐
│  Micro   │  →   │  Event   │  →   │  Macro   │
│ (개인)    │      │ (순간)    │      │ (흐름)    │
└──────────┘      └──────────┘      └──────────┘
```

| 단계 | 화면 조작 | 대사 예시 |
|------|---------|---------|
| **Micro** | agent #45 hover → 친구 선 등장 | "이 30대 직장인은 퇴근 후 왜 망원동으로 갔을까요?" |
| **Event** | 19시 슬라이더 → 망원시장 근처 ripple pulse | "바로 그 순간, 망원시장 매출이 발생합니다." |
| **Macro** | 01시 자동 리포트 + 굵은 OD 흐름선 | "오늘 마포의 주요 이동 흐름은 이렇게 형성됐습니다." |

이 3분 시퀀스만으로 "장난감 시뮬 → BI 도구" 포지셔닝 가능.

---

## 4. 기술 스택

| 영역 | 기술 | 비고 |
|------|------|------|
| 지도 엔진 | Leaflet 1.9 + react-leaflet 4.2 | `preferCanvas={true}` 필수 |
| 히트맵 | leaflet.heat | 이미 적용 |
| Pulse 애니메이션 | CSS `@keyframes` + `will-change` | ❌ framer-motion (1000 개체 부담) |
| 그라데이션 선 | SVG `<linearGradient>` | ❌ L.Polyline.AntPath (다중 시 어지러움) |
| 상태 관리 | zustand 5 | 이미 적용 |
| API 통신 | axios 1.7 | 이미 적용 |
| 폴링 | 커스텀 hook `useLivePoll` | 5초 간격 |

### 왜 **Boids / WebGL(deck.gl)**는 안 쓰나
- Boids는 "물리적 군집"이 철학. 우리는 "개인 데이터 의사결정 + 사회적 관계" 축 → 모델 본질 흐림
- WebGL은 10,000개 이상에서 효과. 1000개는 Leaflet Canvas로 충분
- 리팩토링 비용 > 이득

---

## 5. 성능 최적화 체크리스트

- [ ] 이벤트 링 `will-change` 가 `animationend`와 함께 제거되는가?
- [ ] 앵커 마커 `text-stroke`가 복잡한 타일 배경에서도 읽히는가?
- [ ] 뷰 모드 전환 `transition: opacity 0.6s ease` 매끄러운가?
- [ ] `L.polyline` hover overlay는 mouseout 시 즉시 remove되는가?
- [ ] OD 집계가 렌더 시마다 다시 안 도는가 (`useMemo`)?
- [ ] `preferCanvas={true}` 로 SVG 대신 Canvas 렌더 중인가?
- [ ] 1000 마커 상태 변경이 React 재렌더 트리거 최소인가? (key 고정)

---

## 6. 데이터 근거 (발표 시 어필)

| 지표 | 값 | 출처 |
|------|---|------|
| 동별 인구 분포 | 마포 16동 최신 월 | `living_population` |
| 매장 데이터 | 3,905개 실제 상호 | `kakao_store` + `kakao_store_hours` |
| 메뉴 가격 | 81,313개 실제 품목 | `kakao_store_menu` |
| 동 교통 점수 | 지하철 거리 기반 | `dong_subway_access` |
| 경제 수준 | 아파트 단위면적가 | `apt_trade_real` 2024+ |
| 카테고리 트렌드 | 네이버 검색량 12개월 | `naver_trend_industry` |
| 날씨 | 서울 관측소 최신 | `weather_daily` |
| 공휴일 | 2025+ 달력 | `holiday_calendar` |
| 동별 업종 매출 | 서울시 최신 분기 | `district_sales_seoul` |
| SNS 감성 | 마포 장소 180일 | `mapo_sns_sentiment` |

→ 단순 시뮬이 아닌 **공공 데이터 12종 + 메뉴 + 감성 + 날씨 통합** 임을 강조.

---

## 7. 구현 순서 (2~3시간 작업)

1. T1 CSS Pulse (30분) — 가장 큰 시각 임팩트
2. T3 OD 흐름선 (45분) — 집계 로직 + SVG gradient
3. T5 뷰 모드 탭 (30분) — 기존 레이어 토글 재조합
4. T4 POI 앵커 (20분) — 좌표 하드코딩 + 스타일
5. T2 친구 Hover (20분) — event listener 추가
6. T7 자동 리포트 (15분) — trajectory 집계 텍스트
7. T6 Auto Tour (30분) — setTimeout 체인

전체 약 **3시간** 작업으로 발표 완성형 도달.

---

## 8. Gemini 조언 누적 기록

| 차수 | 핵심 |
|-----|------|
| 1차 | Boids + WebGL + 히트맵 + 이벤트 링 + 에이전트 상태 변화 |
| 2차 | CSS Keyframe 성능팁, Bezier 대신 선 굵기 |
| 3차 | Micro-Event-Macro 서사, one-time class, POI 계층 |
| 4차 | Visual Hierarchy, 수치화 한 문장, 마감 체크리스트 |

**네 차례 피드백이 "뭘 만들 것인가 → 어떻게 구현할 것인가 → 어떻게 팔 것인가 → 어떻게 마감할 것인가"로 이어져서 완결된 로드맵.**

---

## 9. 에이전트 설명 — 마포 1,000 페르소나의 작동 원리

### 9.1 에이전트란 무엇인가
마포구의 **가상 거주자·통근자·방문객·점주** 총 1,000명. 각자 고유한 프로필을 갖고 하루 20시간(06시~익일 02시) 동안 **개인 특성 + 날씨/요일 + 사회적 관계**를 종합해 "어디서 뭘 먹을지, 누구와 만날지"를 매 시간 결정합니다. 모든 판단은 RDS 공공데이터·LLM·규칙 기반 3중 로직으로 구동.

### 9.2 인구 구성 (Population Mix)

| Role | 인원 | 특징 | 주요 행동 |
|------|------|------|---------|
| 🏠 **Resident** (거주자) | 600 | 마포 16동 living_population 실분포 샘플링 | 아침 집, 점심/저녁 동 주변 카페·식당 |
| 🚇 **Commuter** (통근자) | 250 | home_dong ≠ work_dong | 08~09시 출근, 12시 점심, 18시 퇴근 |
| 🧳 **Visitor** (방문객) | 100 | 단기 체류 | 1~2시간마다 다른 동으로 관광 이동 |
| 🏪 **Owner** (점주) | 50 | 자영업자 | 09~22시 가게 근무, 친구에게 PROMO DSL |

### 9.3 Tier 계층 — LLM 호출 비용 통제

| Tier | 인원 | 의사결정 엔진 | 호출당 비용 | 역할 |
|------|------|---------------|------------|------|
| **S** | 50 (5%) | GPT-4o-mini + 페르소나 컨텍스트 | ~$0.0001 | 풍부한 스토리 생성 (발표 샘플링용) |
| **A** | 200 (20%) | GPT-4.1-nano 압축 프롬프트 | ~$0.00003 | 일반 의사결정 |
| **B** | 750 (75%) | 파이썬 규칙 기반 (LLM 0) | 0 | 배경 인구 |

**왜 계층화?** 1,000명 전원 풀 LLM이면 $2/일, 계층화로 **$0.20/일**. 95% 비용 절감하면서도 Tier S는 자연어 reason 생성 유지.

### 9.4 AgentProfile — 개인 정체성 벡터

각 에이전트는 **RDS 실데이터 기반** 9개 속성을 가집니다:

| 속성 | 데이터 소스 | 영향 |
|------|------------|------|
| `age`, `gender` | `living_population` (동별 연령×성별) | 초대 수락률, 취향 |
| `home_dong` | `living_population` 가중 샘플 | 활동 중심지 |
| `income_level` (1~3) | `apt_trade_real` 단위면적가 | 일일 예산 |
| `daily_budget` | income × 랜덤 변동 | 매 시간 잔여 예산 체크 |
| `price_sensitivity` (0~1) | 소득 역상관 + 연령 | 저가/프리미엄 매장 선호 |
| `mobility_score` (0~1) | `dong_subway_access` 지하철 거리 | 동 간 원정 확률 |
| `pref_cafe/restaurant/pub/cvs` | `naver_trend_industry` 12개월 + 연령 보정 | 카테고리 선택 가중치 |
| `lifestyle_tag` | 자동 조합 | LLM 프롬프트 (예: "30대 직장인 연남동") |

### 9.5 하루 행동 플로우 (06시 → 25시)

```
06시        기상/집에서 휴식
07시        일부 활성화 (대중교통 이용 시작)
08~09시 ━━━ 🏃 풀 활성화 (Commuter 출근 이동)
10~11시     카페 일부 방문 (Resident/Visitor)
12~13시 ━━━ 🍽 점심 풀 활성화 (식당)
14~17시     산발 활동 (업무/카페/개인)
18~21시 ━━━ 🌆 저녁 풀 활성화 (퇴근+저녁식사+주점)
22~24시     심야 편의점/주점/귀가
25시        대부분 휴식 (95% 스킵)
```

**풀 활성화** = 1000명 모두 decide() 호출. **산발 시간대** = 활성화율 ~30%.

### 9.6 의사결정 단계 (Tier B 규칙 기반 예시)

**#45 김지유 (28세 여성, 연남동 거주, 소득 3, price_sensitivity 0.3, pref_cafe 0.92) 14시:**

1. **시간대 체크** — 14시는 카페 타임
2. **날씨 보정** — `World.weather="비"` → 이동 확률 × 0.4
3. **친구 INV 확인** — pending_invites 중 14시 항목 없음
4. **개인 취향 가중** — `pref_cafe=0.92` → 카페 선택 확률 상승
5. **롤 확률** — `random() < 0.36`(=0.2+0.4×0.92×0.7) → True → 카페 방문
6. **카테고리 매장 후보** — `world.stores_in_dong("연남동", "카페")` → 249개
7. **영업시간 필터** — 14시 영업중만 → ~200개
8. **가중치 계산**:
   - `rating` (4.0 고정)
   - `price_w` (프리미엄 지향 → 높은 price_level 선호)
   - `store_bias` (친구 INFO/PROMO 반영)
   - `popularity_boost` = 연남동 카페 매출 × 매장 SNS 감성
9. **슬로우캘리 연남본점 선택** (popularity 1.35)
10. **메뉴 선택** — 프리미엄 풀에서 랜덤 → "콜드브루 라떼 6,500원"
11. **예산 체크** — `75000 - 15000 = 60000 > 6500` → OK
12. **반환**: `Decision(action="visit", target_store_id=XX, spend=6500)`

### 9.7 사회적 상호작용 — 원시어 DSL 대화

Tier S 에이전트는 **친구 네트워크**(같은 동 + 연령 ±10, 평균 3명)를 통해 메시지 교환:

| Verb | 의미 | 효과 |
|------|------|------|
| `[INV cat=카페 dong=연남 h=14]` | 14시 연남 카페 초대 | receiver의 `pending_invites`에 추가 → 해당 시간 70% 수락 |
| `[ACC]` | 수락 | 없음 (로그 기록) |
| `[DEC reason=budget]` | 거절 | 없음 |
| `[PROMO sid=42]` | 점주 → 친구 매장 홍보 | receiver `store_bias[42] *= 1.5` |
| `[INFO sid=42 rate=good]` | 경험 공유 | `store_bias[42] *= 1.3 (good)` or `0.7 (bad)` |

**→ 같은 동 친구끼리 같은 카페로 모이는 "군집 현상"이 자연 발생**. 발표의 Micro 뷰 핵심.

### 9.8 기억(Memory) — pgvector

Tier S 의사결정 시 과거 자기 행동을 벡터 검색:
- 컬렉션: `sim_agent_memory` (legal_documents와 분리)
- 임베딩: `paraphrase-multilingual-MiniLM-L12-v2` (384차원, 로컬 무료)
- 일별 배치 인덱싱 (Tier S/A의 visit/work만)
- 다음날 의사결정 시 상위 2건 검색 → 프롬프트에 "과거: D1-H18 visit 슬로우캘리" 주입

### 9.9 환경 변수 — 시간·날씨·휴일·가격 충격

World 전역 상태:
- `current_hour` 06~25
- `weekday`, `is_weekend`, `is_holiday`, `holiday_name` (holiday_calendar)
- `weather` (맑음/흐림/비/눈), `temperature`, `rain_mm` (weather_daily)
- `price_multiplier` (임대료 충격 시나리오 +30% 등)

이 변수들이 **에이전트 결정에 동적 영향**. 예: 비 오면 이동 40%↓, 공휴일엔 여가 활동 30%↑.

### 9.10 샘플 페르소나 (Tier S 8가지 아키타입)

| ID | 태그 | 특징 |
|----|------|------|
| `creative_freelancer` | 프리랜서 크리에이터 | 감성 카페, 인증샷, 평점 4.5+ |
| `office_worker` | 공덕 직장인 30대 | 효율, 가성비, 저녁 회식 |
| `broadcasting_staff` | 상암 방송 스태프 | 야근, 새벽 야식, 24시 매장 |
| `student_couple` | 홍대 대학생 커플 | 트렌드, 신상 매장, SNS 검색 |
| `retired_local` | 마포 토박이 시니어 | 단골, 새 매장 회피, 가격 민감 |
| `young_parent` | 유아 동반 30대 부모 | 주말 활동, 키즈존, 주차 |
| `tourist_foreign` | 외국인 단기 관광객 | 한국 음식 호기심, 인스타 핫플 |
| `f&b_owner` | F&B 점주 | 경쟁 매장 모니터링, SNS 마케팅 |

각 Tier S 에이전트는 이 중 1개 아키타입 + 개인 AgentProfile을 합성한 **500 토큰 페르소나 프로필**을 LLM 시스템 프롬프트로 받음 (Anthropic prompt cache 적용 시 90% 할인).

### 9.11 요약 어필 한 줄
> "1,000명 에이전트는 **공공데이터 12종**으로 프로필을 빚고, **GPT-4o-mini + 파이썬 규칙**의 계층 판단으로 행동하며, **원시어 DSL로 친구들과 대화**해 집단 움직임을 만들어냅니다."

---

## 10. 다음 단계

- [ ] 이 문서를 팀 3 Notion/Confluence에 복제
- [ ] 프론트 담당자 체크리스트로 공유
- [ ] 발표 슬라이드 초안에 Micro-Event-Macro 섹션 3장 배정
- [ ] 리허설 시 Auto Tour 시연 확인
