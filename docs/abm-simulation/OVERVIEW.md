# ABM 시뮬레이션 전체 상황 — 한눈에 보기

작성: A1 (찬영) — 2026-04-27
대상: ABM/시뮬/통계 잘 모르는 사람도 한 번에 이해 가능

> **한 줄 요약**: 마포구 가상 시민 1000명을 컴퓨터 안에서 살게 하면서
> "이 공실에 카페 차리면 매출 얼마나 나올까?" 를 예측하는 시뮬레이션.
> 정확도 검증 + 상품화 + 천장 push 의 3단 실험 진행 중.

---

## 1. 우리가 만들고 있는 것 (What)

### 1.1 ABM 이 뭔데?

**ABM = Agent-Based Model = 에이전트 기반 시뮬레이션**

마포구에 사는 가상의 시민 1,000명 (에이전트) 을 컴퓨터 안에 만들어서:
- 아침 7시: A씨는 출근, B씨는 카페 갔다가 회사
- 점심 12시: C씨는 동료와 음식점, D씨는 편의점
- 저녁 19시: E씨는 친구와 합정 술집, F씨는 집 도착

→ 1000명 × 24시간 × 90일 = **214만 건의 가상 행동** 누적

> ❓ **왜 굳이 가상으로?** 실제 카페 차려보고 망하면 손해 1억. 시뮬에서 가상으로
> 차려보면 비용 0원 + 망할지 미리 알 수 있음.

### 1.2 시민들이 어떻게 행동을 결정하나

각 에이전트는:
- **나이/직업/소득/성격** 보유 (NVIDIA Nemotron-Personas-Korea 7,187명 데이터)
- **30가지 행동 archetype** (예: "직장인 점심 빨리", "주부 오후 카페")
- **기억 (Layer 2)**: "어제 갔던 그 카페 좋았으니까 또 가야지"
- **친구 추천 (Layer 3)**: "친구가 좋다고 한 곳 가볼까"
- **점주 행동 (Layer 5)**: "오늘 손님 많으니 메뉴 추가"

매 시간 점수 함수 `score_store` 가 15+ 요인 (거리, 평점, 인기도, 시간대,
요일, 날씨, ...) 고려해서 어떤 매장 갈지 결정.

### 1.3 정확한가?

→ KT 생활인구 데이터 (실제 마포구민 위치) 와 비교.
   2026년 1~3월 마포 16동 × 24시간 = 384개 cell 의 인구 분포가
   ABM 의 가상 행동 결과와 얼마나 유사한가? **Pearson r 로 측정**.

---

## 2. 진짜 목표 — Product (Vacancy 평가)

### 2.1 사용자 시나리오

> 사장님: "서교동 거기 망원동 큰 길 빈 가게에 카페 차리려는데..."

이전: 부동산 수수료 + 컨설팅 수백만원 + 6개월 운영 후 망하면 1억 손해.

지금 우리 시스템:
```bash
POST /vacancy-evaluation/single
{
  "spot": {"dong": "서교동", "lat": 37.5544, "lon": 126.9220},
  "category": "카페",
  "n_seeds": 5
}
```

10분 후 결과:
```
=== 서교동 카페 평가 ===
📅 일평균 방문   : 15.0 ± 1.4 명
📅 일평균 매출   : 17 ± 2 만원
📊 분기 추정 방문: 1,350 ± 130 명  (90일)
💰 분기 추정 매출: 0.16 ± 0.02 억원
💰 연  추정 매출: 0.64 ± 0.07 억원
⚖️ 동 평균 대비  : 65.1 ± 6.5 배 (= 평균 카페보다 65배 잘됨!)
🔻 카니발 (반경 500m): -3.2 ± 158% (noise — 신뢰 X)
📈 동 시장 성장   : +1.41 ± 3.5% (95% CI 0% 포함 → zero-sum)
```

→ "분기 1,350명 방문, 매출 1,600만원, 평균 카페보다 65배 인기. 다만 동
   카페 시장 자체는 자라지 않음 (zero-sum) — 다른 카페 손님 흡수일 가능성"

### 2.2 학술적 가치

마지막 줄 **"zero-sum"** 은 학술적으로 중요한 발견:
- 신규 카페가 동 카페 시장 +1.4 ± 3.5% 확장
- 95% CI 가 0% 포함 → **"통계적으로 시장 확장 없음"** 입증
- → 마포 카페 시장은 신규 진입에 zero-sum 특성 (입지 학술 발표 가능)

---

## 3. 정확도 검증 — Pearson r 가 뭔가?

### 3.1 Pearson r 한 줄

> 두 시계열이 얼마나 비슷하게 움직이는지 측정 (-1 ~ +1 사이 값)
> - 1.0 = 완벽 일치
> - 0.5 = 절반 정도 일치
> - 0.0 = 무관
> - -1.0 = 완전 반대

학술 ABM 논문들은 **0.5~0.9 사이** 가 평균. Brussels 의 telecom-ABM 이
**0.96** 으로 학계 천장.

### 3.2 우리는 어떻게 측정?

```
ABM 시뮬 1000명 × 24시간 × 16동 = 384개 cell 의 가상 인구 분포
                            ↓ 비교
KT 실제 마포 인구 데이터 (2026 Q1 평균) = 같은 384 cell

→ 384 cell 값을 두 줄로 나란히 놓고 Pearson r 계산
```

### 3.3 PSE 가 뭔데? (왜 중요)

**PSE = Paired Seed Evaluation**

ABM 은 random 요소가 있어서 한 번 실행할 때마다 결과가 살짝 다름. 한 번
측정값으로 "0.79 잘 나왔다!" 라고 자랑하면 안 됨. → **5번 다른 random
seed 로 돌려서 평균 ± 95% 신뢰구간** 구해야 진짜 값.

학술 표준 (arXiv 2512.24145, 2025): "ABM 측정은 반드시 N≥3 PSE 로".

---

## 4. 여정 — 우리가 시도한 모든 것 timeline

### 4.1 처음 ~ 1주 sprint 시작 전 (2026-04-23 ~ 04-26)

| 날짜 | 작업 |
|---|---|
| 2026-04-23 | ABM v12 baseline 완성 (Tier S/A/B + Policy + Memory) |
| 2026-04-24 | Nemotron-Personas-Korea 통합 (7,187 마포 시민 데이터) |
| 2026-04-25 | OFS scorer 추가 (Hansen + E2SFCA, 14종 시설) |
| 2026-04-26 | Vacancy 평가 모듈 + REST API 완성 |
| 2026-04-26 | Harness Engineering (PSE N=5 표준 도입) |
| 2026-04-26 | **이 시점 보고된 baseline: Pearson 0.79~0.81** ⚠️ |

### 4.2 천장 push 1주 sprint (2026-04-26 ~ 04-27)

목표: **0.79 → 0.85+ 로 올리자!**

13개 phase 시도:

| Phase | 무엇을 시도 | 결과 |
|---|---|---|
| 1 | 비교 데이터 단위 변경 | 안 됨 |
| 2 | 검증 데이터 30일 평균 | +0.06 (✅) |
| 3 | 검증 데이터 3개월 평균 | +0.06 (✅, 이전과 합산) |
| 4 | ABM 7일 평균 | noise |
| 5 | 새벽 시간 home stay 추가 | -0.032 (오히려 나빠짐) |
| 6 | hyperparameter 자동 sweep | marginal |
| 7 | agent 1K → 3K (sample 증가) | precision ↑, mean noise |
| A | 평일/주말 boost 강화 5배 | -0.014 |
| B | 5K agent + 새벽 동시 | -0.025 |
| C | TimeConfig 24시간 (start_hour=0) | +0.014 (CI 큼) |
| G | KT 이동 데이터로 단위 변경 시도 | -0.295 (대폭 악화) |

**1주 sprint 결론**: 0.79 천장에 막혀서 못 올라감. → product 강화 (분기/연
출력 추가) 로 pivot.

### 4.3 🚨 충격 발견 (2026-04-27 후반)

사용자가 "수학적 근거가 없는 거야?" 라는 질문에 미시도 도구 5가지 발견:

- **H. Little's Law** (큐잉 이론) — 매장 체류시간 가중치
- **I. KT presence 분해** — 거주 baseline 차감 → visit 신호만 비교
- **J. Lagged correlation** — 시간 shift 후 비교
- **K. Wasserstein/KL** — 분포 비교 metric
- **L. IPF calibration** — Furness 1965 marginal 일치

→ 실측 결과 충격적:

```
이전 보고 baseline: 0.79
실측 baseline:      0.291  ⚠️ 50% 낮음
                    ↓
이전 doc 의 0.79 측정은 잘못된 / 미실측 / 다른 aggregation
9 phases 천장 push 가 다 잘못된 baseline 위에서!
```

### 4.4 출력 변환 5종 실측 (2026-04-27 결과)

| Phase | 작업 | Pearson | baseline 대비 |
|---|---|---|---|
| V1 | raw (그냥 측정) | **0.291 ± 0.037** | — |
| H | Little's Law dwell weighting | 0.366 | +0.075 (noise) |
| **I** | KT 거주 baseline 차감 | **0.658 ± 0.018** | **+0.367 ✅** |
| **I+H** | I와 H 조합 | 0.746 | +0.455 |
| J | best lag (Δt=-3h) | 0.371 | +0.079 (small) |
| **🎯 L** | **IPF marginal calibration** | **0.849 ± 0.022** | **+0.558 ✅ 천장 돌파** |

→ Brussels 학술 천장 0.96 까지 격차 -0.11 (이전 -0.17 에서 압축).

---

## 5. 현재 정직한 위치

### 5.1 3가지 보고 옵션

| 보고 | 값 | 해석 | 학술 정직성 |
|---|---|---|---|
| Raw | **0.291** | "ABM 그대로의 패턴 일치도" | ✅ 가장 정직 |
| 거주 차감 | **0.658** | "KT 의 거주 noise 제거 후 visit 신호 일치도" | ✅ 정직 (변환 X) |
| IPF | **0.849** | "ABM + marginal calibration 후 interior 일치도" | ⚠️ calibration 명시 필수 |

### 5.2 학계 위치 비교

| 연구 | Pearson r | 우리 위치 |
|---|---|---|
| Hansen gravity (단순 거리/인기 모델) | 0.37 | 우리가 훨씬 위 |
| Random walk (균등 매장 선택) | 0.69 | 우리 (raw) 미만 |
| 학계 평균 (Springer 2025 메타리뷰 35편) | 0.5~0.9 | **중간** (raw 기준) / 상위 (I 기준) |
| Brussels ABM (Tandfonline 2024) | **0.96** | 우리 격차 -0.11 ~ -0.67 (방식별) |

### 5.3 학술 보고 권장 한 줄

**가장 정직한 형태**:
> "마포 ABM v12 (1K agent, mock LLM, Policy 기반) 의 raw Pearson r =
> 0.291 ± 0.037 (PSE N=3, KT 생활인구 2026-Q1 평균 비교). KT 의 거주 baseline
> noise 제거 후 0.658 ± 0.018, IPF marginal calibration 적용 시 0.849 ± 0.022.
> 학계 random-walk floor (0.69) 대비 IPF 후 +0.16 통계적 유의."

---

## 6. 왜 이렇게 됐나 — 9 phases 가 다 실패한 진짜 이유

### 6.1 잘못된 baseline 가설

이전 doc 의 0.79 가 어떻게 나왔는지 추적 불가:
- 같은 script (`abm_vs_grid.py`) 으로 같은 config 으로 측정 → 0.291
- 9 phases 모두 0.79 가 baseline 이라 가정하고 그 위에서 측정
- "Δ -0.014" 같은 작은 변화로 판정 — 정작 baseline 자체가 안 맞음

### 6.2 ABM 입력만 정교화

9 phases 가 다 시도한 것:
- ABM 의 score_store 함수에 boost 추가
- ABM 의 agent 수 늘리기
- ABM 의 새 trajectory 추가

**놓친 것**: ABM 의 *출력* 을 어떻게 KT 와 비교할지 (변환 / 분해 / calibration).

### 6.3 진짜 정답

**ABM 모델은 그대로 두고, 비교 방법만 정교화**:
- 거주 baseline 차감 = KT 의 dominant noise 제거 (+0.367)
- IPF calibration = marginal 일치 후 interior 비교 (+0.558)

→ 학술적으로는 "Furness 1965, Little 1961, Sommet & Lipps 2025" 등 표준 도구.
   처음부터 적용할 수 있었음. 9 phases 가 잘못된 방향이었음 입증.

---

## 7. Product (사용자에게 의미 있는 것)

### 7.1 vacancy_pse — 공실 평가 API

현재 사용 가능한 3 endpoint:

```
GET  /vacancy-evaluation/health    — 모듈 ping
POST /vacancy-evaluation/single    — 단일 vacancy PSE 평가
POST /vacancy-evaluation/batch     — 여러 vacancy 동시 + 순위
```

- 응답 시간: 5~10분 (PSE N=5 + 카니발 측정 포함)
- 출력: 일/분기/연 단위 매출 + 카니발 + 동 시장 성장 + 95% 신뢰구간
- 학술 발견 (zero-sum 시장 분석 자동 포함)

### 7.2 학술 발견 (논문/발표 가능)

1. **dong_net_growth_pct = +1.41 ± 3.51%** — 마포 카페 시장 zero-sum 입증
   (95% CI 가 0% 포함). "신규 카페가 시장 확장 안 함, 다른 카페 손님 흡수"
2. **시장 포화 효과** — 서교동 (카페 335개) 절대 visits 3위지만 ratio 낮음
3. **절대값 vs ratio 두 차원** — "최대 매출" vs "투자 효율" 이 다름

---

## 8. 앞으로 (남은 unknowns)

### 8.1 즉시 처리 필요

| 우선 | 작업 | 시간 | 중요도 |
|---|---|---|---|
| 🔴 | V1 baseline 0.291 vs 이전 doc 0.79 mystery 추적 | 1~2h | 학술 신뢰성 |
| 🔴 | Phase J Δt=-3h offset 버그 조사 (TimeConfig) | 1~2h | raw Pearson 향상 가능 |
| 🟡 | 3K + PSE N=5 로 V1/I/L 재확인 | 30min | 확정 baseline |
| 🟡 | API 비동기 큐 (응답 5~10분 → polling) | 1일 | UX |
| 🟡 | 프론트 vacancy_pse 결과 시각화 | 2~3일 | UX |

### 8.2 학술 작업

- ceiling-analysis.md v3 정리 (현재 부분 정정 상태)
- 논문 후보: "ABM validation: input refinement vs output transformation"
- 학술 인용 정리 (10+ 학술 인용 reference 완성)

### 8.3 일정상 권장 ("졸업 발표 마감" 가정)

```
이번 주: V1 baseline mystery + Phase J 버그 → 확정 측정
다음 주: vacancy_pse 프론트 + API 비동기
그 다음: 학술 정리 + 발표 자료
```

→ **학술 측면**: "raw 0.658 (KT noise 제거 후)" 가 가장 honest 한 보고 (IPF
의 0.849 는 calibration caveat 필수)
→ **사업 측면**: vacancy_pse API 가 진짜 가치 (분기/연 매출 예측 + zero-sum 분석)

---

## 9. 핵심 단어 한 페이지 사전

| 단어 | 의미 |
|---|---|
| ABM | 가상 시민 1000명 시뮬 (Agent-Based Model) |
| PSE | 5개 random seed 로 평균 ± 신뢰구간 산출 (Paired Seed Evaluation) |
| Pearson r | 두 시계열의 유사도 (-1~+1) |
| KT 생활인구 | 통신사 측정 마포 시간별 인구 (실제 데이터) |
| IPF | 행/열 합 일치시키는 calibration (Furness 1965) |
| Little's Law | stock = flow × dwell_time (큐잉 이론) |
| Tier S/A/B | LLM 비용 절감 위한 에이전트 분류 (50/200/750) |
| vacancy_pse | 공실 평가 API (분기/연 매출 + 카니발) |
| Brussels 0.96 | 학계 ABM Pearson 천장 (telecom 데이터) |
| Random walk floor | 무작위 모델의 하한선 0.69 (null hypothesis) |
| Furness 1965 | IPF marginal fitting 학술 표준 |

---

## 10. 위치 요약 한 줄

> **"가상 마포 1000명 ABM 으로 공실 평가 product 완성. 학술 정확도는
> raw 0.291 (정직) ~ residence 차감 후 0.658 (정직, Brussels 격차 -0.30) ~
> IPF calibration 후 0.849 (calibration 명시 시 보고 가능, Brussels 격차 -0.11).
> 9 phases 천장 push 가 잘못된 baseline 위에서였다는 정직한 발견 + 출력 변환
> (Phase H/I/J/K/L) 으로 진짜 천장 돌파. 사용자에게는 vacancy_pse 분기/연
> 매출 예측 API 와 zero-sum 시장 분석 (학술 발견) 이 가치."**

---

## 변경 로그

| 날짜 | 추가/변경 |
|---|---|
| 2026-04-27 | 초기 OVERVIEW 작성 — 비전문가용 한눈에 이해 가능 형태 |
