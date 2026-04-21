# 마포구 ABM 시뮬레이션 상세 작동 방식

작성: A1 (찬영) — 2026-04-21
대상 독자: 팀원, 심사위원, 유지보수자
관련 문서: `policy-generator-design.md`, `sim-validation-progression.md`

---

## 0. 한 문장 요약

**LLM이 11개의 "행동 정책"을 숫자 파라미터로 생성하고, 1000명의 에이전트는 그 정책을 상속·변형해 순수 Python 점수 함수로 20시간을 살아간다.**

---

## 1. 전체 실행 흐름 (High-level)

```
┌───────────────────────────────────────────────────────────┐
│ 0. 실행 명령                                                │
│    python scripts/sim_mapo_poc.py --rds --profiles         │
│        --policy --trajectory                               │
└────────────────┬──────────────────────────────────────────┘
                 │
     ┌───────────▼────────────┐
     │ 1. World 구축 (RDS)    │  3,856 점포 + 메뉴 + 매출 + 감성
     └───────────┬────────────┘
     ┌───────────▼────────────┐
     │ 2. 정책 로드 / 생성    │  LLM 11회 호출 (캐시 있으면 skip)
     └───────────┬────────────┘
     ┌───────────▼────────────┐
     │ 3. 에이전트 1000명 생성│  역할·Tier·Profile·arrival/departure
     └───────────┬────────────┘
     ┌───────────▼────────────┐
     │ 4. 일 단위 루프        │  20 tick × 1일
     │   └─ tick 단위 루프    │
     │       └─ 에이전트별    │
     │           decide()     │  policy_decide → Decision
     └───────────┬────────────┘
     ┌───────────▼────────────┐
     │ 5. 결과 집계           │  top_stores, category_totals, trajectory
     └────────────────────────┘
```

총 소요: **약 3분** (LLM 호출 11회 + Python 20,000 결정)

---

## 2. LLM 설정 — Policy Generator

### 2.1 제공자 선택 로직 (`policy_generator.py`)

```python
# Provider 우선순위 (기본 "auto")
provider="auto" → OpenAI 키 있으면 OpenAI
              → 없으면 Ollama 서버 체크
              → 둘 다 없으면 mock fallback
```

- **OpenAI 경로**: `gpt-4o-mini`, `response_format=json_object`, temperature=0.4
- **Ollama 경로**: Qwen2.5:3b 로컬, OpenAI 호환 API (`/v1/chat/completions`)
- **Mock 경로**: 하드코딩 기본값 + 비 오면 indoor/mobility 보정

### 2.2 11개 정책 카탈로그

```python
POLICY_CATALOG = [
    ("resident", "맑음"),    ("resident", "비"),     # 주거자
    ("commuter", "맑음"),    ("commuter", "비"),     # 마포 내 통근
    ("visitor", "맑음"),     ("visitor", "비"),      # 방문자
    ("ext_commuter", "맑음"), ("ext_commuter", "비"),  # 외부→마포 출근
    ("ext_visitor", "맑음"),  ("ext_visitor", "비"),   # 외부→마포 저녁 방문
    ("owner", "맑음"),       # 점주 (날씨 무관 단일)
]
# = 총 11개
```

### 2.3 LLM 프롬프트 구조

**System 메시지** (엄격성 강제):
```
You output ONLY valid JSON matching the requested schema.
No preamble, no markdown, no explanation.
All numeric fields must be floats in [0, 1].
```

**User 프롬프트** (약 1000 토큰):
```
페르소나: {role_desc} / 날씨: {weather}

출력 JSON:
- mobility, indoor_preference, distance_sensitivity, crowd_tolerance
- cafe/meal/pub/cvs preference
- dong_affinity: 마포 16개 동 중 상위 3개
- visit_probability, repeat_visit_bonus, spend_tendency
- rationale (1~2문장)

동 특성 가이드:
- 오피스: 상암·공덕·도화
- 유흥: 서교·합정·연남
- 거주: 용강·대흥·염리·아현·망원2·성산1·성산2·도화·서강
- 혼합: 망원1·신수

제약:
- mobility ↔ indoor_preference 음의 상관
- cafe와 meal 선호 차이 20% 이내
- 역할별 적절한 동 선택 (resident=주거, ext_commuter=오피스...)
```

### 2.4 생성 결과 예시

```json
{
  "policy_id": "resident_맑음",
  "mobility": 0.8,
  "indoor_preference": 0.2,
  "distance_sensitivity": 0.6,
  "cafe_preference": 0.7,
  "meal_preference": 0.6,
  "dong_affinity": {"아현동": 0.9, "용강동": 0.8, "대흥동": 0.7},
  "visit_probability": 0.7,
  "rationale": "맑은 날 거주자는 근처 상권을 자주 방문..."
}
```

**캐시**: `data/processed/policy_cache.json` — 11개 정책을 JSON으로 저장. 재시뮬 시 LLM 호출 skip.

### 2.5 GameMaster — 런타임 정책 보정 (LLM 호출 X)

정책 11개는 기본 맑음/비 2 상태만. 아래는 **Python 함수로 추가 조정**:

| 환경 | 조정 |
|---|---|
| 날씨 비 | indoor_preference × 1.3, mobility × 0.7 |
| 날씨 눈 | indoor × 1.5, mobility × 0.4 |
| 임대료 +30% | spend_tendency × 0.85, visit_probability × 0.91 |
| 공휴일 | visit_probability × 1.3, mobility × 1.15 |
| 주말 | pub_preference × 1.2 |

→ 시나리오 충격을 LLM 재호출 없이 즉시 반영

---

## 3. 1000명 에이전트 생성

### 3.1 인구 구성 (PopulationMix)

```python
residents       = 400  # 마포 거주자 (일상 생활)
commuters       = 100  # 마포 내 통근자 (마포 거주+근무)
visitors        = 50   # 단기 방문자 (마포 내 관광)
owners          = 50   # 점주
ext_commuters   = 300  # 외부→마포 출근 (상암/공덕/도화 향)
ext_visitors    = 100  # 외부→마포 저녁 방문 (홍대/합정/연남 향)
# Total = 1000
```

### 3.2 Tier 분배 (LLM vs Rule)

```python
# 기본 1000명 분배
tier_s =  50   # 풀 LLM (Haiku+cache) — 실제론 Policy 모드에서 미사용
tier_a = 200   # 경량 LLM (Gemini Flash-Lite) — 미사용
tier_b = 750   # 규칙 기반 (LLM 0) — 미사용
```

**현재 Policy Generator 모드에서는 Tier 무시** — 1000명 전원 `policy_decide` 호출 (LLM 0회). Tier는 DSL 모드·기존 구조와 호환 유지용.

### 3.3 역할별 에이전트 생성 (`spawn_agents`)

각 에이전트에 할당되는 속성:

| 속성 | 결정 방식 |
|---|---|
| `name`, `gender`, `age` | `ProfileBuilder` — RDS living_population 분포에서 샘플 |
| `home_dong` | resident/commuter: RDS 거주 비율로 샘플<br>ext_*: "외부" |
| `work_dong` | commuter/ext_commuter: subway_inflow 가중치로 샘플<br>ext_visitor: 저녁 하차 많은 동(서교/합정/연남) |
| `income_level` (1~3) | RDS 지역 소득 분포 |
| `budget_today` | income_level × 랜덤 (15k~80k) |
| `arrival_hour` | ext_*: subway_inflow 시간대 가중치 |
| `departure_hour` | ext_*: 저녁 외부 유출 시간대 가중치 |
| `profile` | `AgentProfile` — price_sensitivity, mobility_score, cafe/pub/restaurant 취향 |

### 3.4 External 에이전트 시간 calibration (핵심 realism)

subway_inflow 데이터 사용 (`data/processed/subway_inflow_by_dong_hour.csv`):

```python
# 진입 시간 샘플링 — 06-10시 양수 net_inflow에 비례
morning_in = [((dong, hour), net_inflow_weight) for (d, h), info in subway_inflow
              if 6 <= h <= 10 and info["net_inflow"] > 0]
# → rng.choices로 300명 ext_commuter에게 각자의 진입 (dong, hour) 할당

# 결과 분포 예시 (300명):
#   7시 공덕동 진입 45명
#   8시 상암동 진입 60명
#   8시 공덕동 진입 80명
#   9시 도화동 진입 40명
#   ... (subway 실측 비율 그대로)
```

ext_visitor는 같은 방식으로 17-22시 net_inflow 기반.

### 3.5 개체별 정책 편차 (±15%)

매 tick 의사결정 때 정책을 복사 후 각 에이전트에 랜덤 보정:

```python
def apply_personal_variation(policy, rng):
    jitter = lambda v: clamp(v * rng.uniform(0.85, 1.15), 0.0, 1.0)
    return replace(policy, mobility=jitter(policy.mobility), ...)
```

→ 1000명이 **공유 정책 11개 + 각자 ±15%** = 고유한 행동 분포

---

## 4. World 환경 구축

### 4.1 점포 데이터 (`world_loader.load_world_from_rds`)

```
kakao_store (3,856건)
  + kakao_store_menu (3,060 매장)      → 메뉴 가격 정보
  + district_sales_seoul               → dong × 업종 매출 가중치
  + mapo_sns_sentiment                 → 매장 인기도 보정
  + kakao_store_hours                  → 요일별 영업시간
= World.stores[store_id] = Store(...)
```

각 Store 객체:
```python
Store(
    store_id=1, name="청담이상", dong="도화동",
    category="주점",
    seats=30, rating=4.0, price_level=2,
    lat=..., lon=...,
    menu_items=[{"name":"소주", "price":4000}, ...],
    popularity_boost=1.45,   # 매출×감성 기반
    is_open_now=True,         # tick마다 hours_map 참조하여 갱신
)
```

### 4.2 시간대×연령×동 가중치 (time_age_boost)

living_population 60일치 → (age_group, dong, hour, weekday) → boost 0.5~2.0

```
(20대, 서교동, 22시, 금요일) → 1.85  # 홍대 금요일 밤 20대 많음
(60대, 용강동, 10시, 월요일) → 1.4   # 주거지 노년 오전 활동
```

13,440개 키가 `world.time_age_boost`에 로드. `score_store`에서 **cat_pref 부스트로 사용**.

### 4.3 지하철 외부유입 (subway_inflow)

```
data/processed/subway_inflow_by_dong_hour.csv
  = 서울 열린데이터 CardSubwayTime API 집계
  = (dong, hour) → {board, alight, net_inflow}
```

12개 마포 역 → 258개 (동, 시간) 엔트리. `spawn_agents`의 ext_commuter / ext_visitor 시간·동 가중치로만 사용.

### 4.4 날씨 & 휴일

- `weather_daily` 최신 1건 → world.weather (또는 scenario.weather_override)
- `holiday_calendar` 2025~ → is_weekend, is_holiday, holiday_name

---

## 5. 의사결정 흐름 (매 tick)

```
각 에이전트 (1000명) 매 시간:

    Agent.decide(world, brain, rng)
          │
          │ use_policy=True 분기
          ▼
    policy_executor.policy_decide(agent, world, rng)
          │
          ├─ Owner는 영업시간이면 work, 아니면 rest (즉시 반환)
          │
          ├─ External 에이전트 진입/퇴장 체크
          │   - h == arrival_hour & 외부 → 마포 이동
          │   - h == departure_hour & 마포 → 외부 이동
          │
          ├─ 1. 정책 조회
          │   policy_key = f"{role}_{weather}"
          │   policy = world.policy_cache[policy_key]
          │
          ├─ 2. GameMaster 조정
          │   policy = GameMaster.adjust(policy, world)
          │   → 날씨/충격/공휴일/주말 보정
          │
          ├─ 3. 개체 편차
          │   policy = apply_personal_variation(policy, rng)
          │   → 파라미터에 ±15% 노이즈
          │
          ├─ 4. 방문 여부
          │   should_visit(agent, policy, world, rng)
          │   → visit_probability × 시간boost × profile.mobility
          │   → False면 rest 반환
          │
          ├─ 5. 매장 선택
          │   pick_store_with_spillover(agent, policy, world, rng, top_k=5)
          │   │
          │   ├─ 현재 동 매장 리스트 → score_store로 점수 계산
          │   ├─ mobility>0.6이면 인접 동(dong_affinity 상위 2) 매장도 후보
          │   ├─ 점수 top 5 중 capacity 여유 있는 첫 매장 선택
          │   └─ 모두 만석이면 인접 동으로 spillover
          │
          ├─ 6. 예산 체크 & 소비 계산
          │   spend = compute_spend(store, agent, policy, world, rng)
          │   → 메뉴 있으면 spend_tendency로 가격대 선택
          │   → budget 초과면 rest
          │
          └─ Decision(action="visit", target_store_id=..., spend=...)
```

### 5.1 score_store — 매장 선호도 계산 (v9 최종)

6단계로 점수 계산:

```python
# 1. 정책 카테고리 선호
cat_pref = {"카페": policy.cafe_preference, ...}[store.category]

# 2. 시간대 × 카테고리 부스트 (점심 음식점 ×1.6, 야간 주점 ×2.5)
cat_pref *= _TIME_CATEGORY_BOOST[store.category][hour]

# 3. 개인 profile 취향 완만 적용 (0.75~1.25)
cat_pref *= 0.75 + 0.5 * profile.pref_[cafe|restaurant|pub|convenience]

# 4. 실측 연령×동×시간×요일 (living_population 13,440 entries)
age_time_boost = time_age_boost[(age_group, dong, hour, weekday)]

# 5. 성별·연령 카테고리 보정 (2024 실측 통계 40개 계수)
age_cat_mult = _AGE_GENDER_BOOST[(category, age_bin, gender)]
age_cat_mult *= _age_gender_time_bonus(age, gender, category, hour, weekday)
# 예: 20대 여 카페 14-17시 ×1.25 / 30-50대 남 주점 금·토 19-22시 ×1.40

# 6. 가격 민감도
price_mult = profile.price_sensitivity 기반 0.2~1.3

score = (
    policy.indoor_preference * indoor_score         # 카페 1.0 / 음식점 0.8
    + cat_pref * age_cat_mult * price_mult
    + policy.dong_affinity.get(store.dong, 0.5)
    + popularity_boost * 0.3                         # RDS 매출·감성
    + repeat_visit_bonus (재방문 시)
    - policy.distance_sensitivity * dong_distance
    - (1 - policy.crowd_tolerance) * occupancy
)
score *= 0.7 + 0.3 * age_time_boost                 # 연령×동×시간 완만 적용
score += (store.rating - 3.0) * 0.1
```

### 5.1.1 성별·연령 보정 테이블 (발췌)

출처: 2024 오픈서베이·KCHS·통계청·트렌드모니터

| 카테고리 | 20대 여 | 30대 남 | 40대 남 | 60대 남 |
|---|---|---|---|---|
| 카페 | **1.70** | 1.10 | 0.90 | 0.55 |
| 음식점 | 1.05 | 1.25 | **1.35** | 1.05 |
| 주점 | 1.35 | **1.60** | 1.30 | 0.60 |
| 편의점 | 1.45 | 1.30 | 1.05 | **1.15** |

### 5.1.2 시간대 × 성별·연령 특이 패턴

1. 20대 여성 카페 **14-17시 ×1.25** (디저트·수다)
2. 30-50대 남성 주점 **금·토 19-22시 ×1.40** (회식 피크)
3. 50대+ 남성 편의점 **07-09시 ×1.30** (출근 담배·커피·해장)
4. 20대 편의점 **22-02시 ×1.35** (야식)

### 5.2 시간대 × 카테고리 부스트

```python
_TIME_CATEGORY_BOOST = {
    "음식점": {12: 1.6, 13: 1.5, 18: 1.6, 19: 1.5, ...},   # 점심·저녁
    "카페":   {10: 1.5, 11: 1.3, 14: 1.7, 15: 1.7, ...},   # 오후 카페타임
    "주점":   {20: 2.2, 21: 2.5, 22: 2.5, 23: 2.2, ...},   # 야간 피크
    "편의점": {6: 1.3, 23: 1.3, 0: 1.5, ...},             # 새벽·심야
}
```

---

## 6. 결과 집계

### 6.1 tick별 기록 (trajectory)

매 시간 × 1000명 = 20,000 trajectory 포인트

```json
{
  "agent_id": 1, "day": 1, "hour": 12, "dong": "도화동",
  "action": "visit", "tier": "B", "role": "resident",
  "lat": 37.5451, "lon": 126.9502
}
```

### 6.2 최종 결과 JSON

```json
{
  "days": 1,
  "total_decisions": 10442,
  "tier_s_calls": 0, "tier_a_calls": 0,
  "estimated_cost_usd": 0.0001,

  "top_stores": [              // 매출 상위 10
    {"name": "메가MGC 공덕", "dong": "공덕동", "category": "카페", "visits": 31, "revenue": 342561},
    ...
  ],

  "category_totals": {          // 전체 매장 카테고리별
    "음식점": {"visits": 3120, "revenue": 15420000},
    "카페":   {"visits": 2590, "revenue":  9850000},
    ...
  },

  "dong_totals": {              // 전체 매장 동별
    "공덕동": {"visits": 1820, "revenue": 8240000},
    ...
  }
}
```

---

## 7. 성능 특성

| 단계 | 소요 | 비용 |
|---|---|---|
| RDS 로드 (점포+메뉴+매출) | 15초 | $0 |
| 정책 로드 (캐시 hit) | 1초 | $0 |
| 정책 생성 (캐시 miss, 11회 호출) | 30초 | $0.002 |
| 에이전트 생성 (1000명) | 2초 | $0 |
| time_age_boost 계산 | 5초 | $0 |
| 20시간 × 1000명 의사결정 | **120초** | $0 |
| trajectory 저장 | 3초 | $0 |
| **Total** | **약 3분** | **$0.0001** |

병목: **의사결정 루프** (1000명 × 20tick = 20,000회 score_store 계산).
score_store는 각 매장 후보 60~90개에 대해 계산 → 실제 약 150만~200만 번의 점수 함수 호출.

순수 Python이지만 numpy 미사용으로도 2분 내 완료. **vectorize하면 30초 가능**, 발표 후 v2 최적화 과제.

---

## 8. 실측 검증 흐름 (`scripts/validate_simulation.py`)

```
시뮬 trajectory.json
      │
      ├─ [1] 시간×동 집계 → living_population 평일 평균과 RMSE/Pearson
      │
      ├─ [2] category_totals → district_sales_seoul 마포 분기와 KL divergence
      │   (편의점은 kakao 데이터 없어 제외 후 정규화)
      │
      ├─ [2.5] 동별 tick 합계 → bus_boarding_daily 마포 정류장 평일과 상관
      │
      ├─ [3] 에이전트별 trajectory → External 귀환율, 동 커버리지
      │
      └─ [4] action=visit 필터 → 시간대 피크 (점심·저녁·카페타임)
```

최종 v9 지표:
- RMSE 4.7% / 상관 0.69 / 버스 상관 0.68 / **KL 0.13** / 피크 1/3 / **External 82.8%**
- 성별·연령 보정 40개 + 시간 특이 패턴 4종 (실측 통계 4개 출처)

---

## 9. 핵심 파일 맵

| 파일 | 역할 |
|---|---|
| `backend/src/simulation/policy_generator.py` | LLM 호출, PersonaPolicy 스키마, 캐시 I/O, perturbation |
| `backend/src/simulation/policy_executor.py` | GameMaster, score_store, should_visit, spillover, policy_decide |
| `backend/src/simulation/agents.py` | Agent dataclass, spawn_agents (role×Tier×External calibration) |
| `backend/src/simulation/world.py` | World/Store, policy_cache·subway_inflow·time_age_boost 필드 |
| `backend/src/simulation/world_loader.py` | RDS 로더 (kakao + menu + sales + sentiment + hours) |
| `backend/src/simulation/runner.py` | run_simulation 오케스트레이션, trajectory 기록 |
| `backend/src/simulation/config.py` | Scenario, PopulationMix, TierDistribution, MAPO_DONGS |
| `backend/src/simulation/scheduler.py` | tick 루프, ThreadPoolExecutor LLM concurrency |
| `backend/src/simulation/profile_builder.py` | RDS 기반 AgentProfile 개인화 |
| `scripts/sim_mapo_poc.py` | CLI 엔트리포인트 (`--policy`, `--n100`, `--rds` 등) |
| `scripts/validate_simulation.py` | 실측 대비 RMSE/KL/상관 검증 |
| `data/pipeline/collect_subway_inflow.py` | 서울 열린데이터 지하철 CardSubwayTime 수집 |
| `data/processed/policy_cache.json` | 11개 정책 캐시 |
| `data/processed/subway_inflow_by_dong_hour.csv` | 지하철 calibration |
| `data/processed/sim_policy_v6_n1000.json` | 최종 시뮬 결과 |

---

## 10. 한 줄 정리

> **"LLM은 11개의 정책 규칙만 만들고, 1000명의 에이전트는 그 규칙을 자기만의 ±15% 편차로 해석하며, 실측 지하철·매출·유동인구 데이터에 맞춰 보정된 Python 점수 함수로 3분 만에 하루를 산다."**
