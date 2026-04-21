# Policy Generator — LLM 정책 생성 + Python 군중 실행 설계

작성: A1 (찬영) — 2026-04-21
자매 문서: `abm-framework-adoption-plan.md`, `abm-framework-extraction-plan.md`, `demo-cache-strategy.md`

---

## 1. 핵심 원칙

> **소수 대표 정책만 LLM으로 생성하고, 군중 에이전트는 해당 정책을 상속·변형해 Python 확률 함수로 행동시키는 하이브리드 ABM.**

### 지켜야 할 4개 규칙

1. **LLM 출력은 숫자 파라미터만** — 서사 문장·자유 텍스트 금지
2. **정책 개수는 8~12개로 제한** — 역할(4) × 성향/날씨(2~3)
3. **개체별 편차는 Python에서 부여** — 정책을 공유하되 agent마다 ±10~20% perturbation
4. **실제 행동은 deterministic 점수 함수** — `score = Σ weight × feature`

---

## 2. 정책 파라미터 스키마

```python
@dataclass(frozen=True)
class PersonaPolicy:
    # 식별자
    policy_id: str         # "office_30s_rain"
    role: str              # resident / commuter / visitor / owner / ext_commuter / ext_visitor
    weather: str           # 맑음 / 비 / 눈
    time_block: str        # morning(6-11) / lunch(12-14) / afternoon(15-17) / evening(18-22) / night(23-2)

    # 이동/공간 성향 (0~1)
    mobility: float                # 이동 반경 — 비 오면 ↓
    indoor_preference: float       # 실내 선호 — 비 오면 ↑
    distance_sensitivity: float    # 원거리 가중치 (높을수록 근거리 선호)
    crowd_tolerance: float         # 혼잡 허용도

    # 카테고리 선호 (0~1)
    cafe_preference: float
    meal_preference: float
    pub_preference: float
    cvs_preference: float

    # 동 선호 (상위 3개만 LLM이 채움, 나머지는 중립 0.5)
    dong_affinity: dict[str, float]  # {"서교동":0.8, "합정동":0.7, "공덕동":0.3}

    # 행동 경향
    visit_probability: float       # 해당 시간대에 외출/방문할 확률
    repeat_visit_bonus: float      # 재방문 가중치
    spend_tendency: float          # 예산 대비 소비율

    # LLM 생성 근거 (디버깅용, 행동엔 영향 X)
    rationale: str
```

**중요**: 모든 필드가 float 0~1 또는 dict[str, float]. LLM이 서사를 쓰지 못하게 JSON schema로 강제.

---

## 3. 정책 카탈로그 (8~12개 확정)

### 3.1 역할 × 날씨 매트릭스

| 역할 | 맑음 | 비 | 눈 |
|---|---|---|---|
| Resident (거주형) | R_clear | R_rain | (비 공유) |
| Commuter (직장인형) | C_clear | C_rain | (비 공유) |
| Visitor (방문형) | V_clear | V_rain | (비 공유) |
| Ext_Commuter (외부통근) | EC_clear | EC_rain | (비 공유) |
| Ext_Visitor (외부방문) | EV_clear | EV_rain | (비 공유) |
| Owner (점주형) | O_any | (공유) | (공유) |

→ **총 11개** (역할 5개 × 날씨 2개 + Owner 1개)

### 3.2 확장 옵션 (나중에)

- **성향 축**: 보수형 / 외향형 / 비용민감형 — 역할별 2~3개로 세분화 → 20~30개
- **시간대 축**: 시간 블록별 별도 정책 → 50~100개
- 발표용은 **11개만** 생성, 확장은 v2

---

## 4. LLM 프롬프트 (정책 생성자)

```
당신은 마포구 시뮬레이션의 행동 정책 생성자입니다.
다음 페르소나의 행동 성향을 JSON 파라미터로만 출력하세요.
서사 문장은 rationale 필드에만 1~2문장 허용, 그 외는 전부 숫자.

페르소나:
- 역할: {role}
- 날씨: {weather}
- 시간대: {time_block}
- 요일: {weekday}

출력 JSON (모든 float는 0~1):
{
  "mobility": ...,
  "indoor_preference": ...,
  "distance_sensitivity": ...,
  "crowd_tolerance": ...,
  "cafe_preference": ...,
  "meal_preference": ...,
  "pub_preference": ...,
  "cvs_preference": ...,
  "dong_affinity": {"서교동": ..., "합정동": ..., "공덕동": ...},  // 마포 16개 동 중 상위 3개만
  "visit_probability": ...,
  "repeat_visit_bonus": ...,
  "spend_tendency": ...,
  "rationale": "한 두 문장 이내"
}

제약:
- mobility + indoor_preference는 음의 상관 (비 오면 mobility ↓, indoor ↑)
- crowd_tolerance는 외향형 ↑ / 보수형 ↓
- 카테고리 선호 합은 1.0에 근접하지 않아도 됨 (각자 독립)
```

**LLM 선택**: Gemini 2.5 Flash-Lite (저렴 + JSON mode 지원) — 11회 호출 약 $0.002

---

## 5. 개체별 편차 (Python Perturbation)

```python
def apply_personal_variation(policy: PersonaPolicy, agent: Agent, rng: Random) -> PersonaPolicy:
    """정책 파라미터에 ±15% 개체 편차 부여."""
    jitter = lambda v: clamp(v * rng.uniform(0.85, 1.15), 0.0, 1.0)
    return replace(
        policy,
        mobility=jitter(policy.mobility),
        indoor_preference=jitter(policy.indoor_preference),
        # ... 모든 float 필드
        # agent.profile 기반 추가 편차 (price_sensitivity 등)
    )
```

- 같은 정책 기반이어도 ±15% 분포로 1000명이 완전히 동일하게 행동하지 않음
- `agent.profile.price_sensitivity` 등 이미 RDS에서 뽑은 개인 속성과 결합

---

## 6. Python 행동 점수 함수

### 6.1 매장 선택 (_pick_store 대체)

```python
def score_store(store: Store, agent: Agent, policy: PersonaPolicy, world: World) -> float:
    # feature 추출
    indoor_score = 1.0 if store.category in ("카페", "음식점") else 0.3
    cat_score = {
        "카페": policy.cafe_preference,
        "음식점": policy.meal_preference,
        "주점": policy.pub_preference,
        "편의점": policy.cvs_preference,
    }.get(store.category, 0.3)
    distance_cost = dist(agent.current_dong, store.dong) / MAX_DIST
    congestion_penalty = store.occupancy
    dong_affinity = policy.dong_affinity.get(store.dong, 0.5)

    score = (
        policy.indoor_preference * indoor_score
        + cat_score
        + dong_affinity
        + store.popularity_boost * 0.3
        - policy.distance_sensitivity * distance_cost
        - (1.0 - policy.crowd_tolerance) * congestion_penalty
    )
    return max(0.0, score)
```

### 6.2 방문 여부 결정

```python
def should_visit(agent: Agent, policy: PersonaPolicy, rng: Random) -> bool:
    p = policy.visit_probability * agent.profile.mobility_score
    return rng.random() < p
```

### 6.3 시간대 매칭

현재 `age_dong_time_boost()`의 `time_age_boost` 테이블은 그대로 사용 (living_population 실측치). 정책은 **위에 곱해지는** 가중치.

---

## 7. 우리 코드 통합 위치

| 신규/수정 | 파일 | 변경 내용 |
|---|---|---|
| 신규 | `backend/src/simulation/policy_generator.py` | LLM 호출 → PersonaPolicy 11개 생성 + 캐시 |
| 신규 | `backend/src/simulation/policy_executor.py` | `score_store`, `should_visit` 등 순수 Python 행동 함수 |
| 수정 | `backend/src/simulation/world.py` | `policy_cache: dict[str, PersonaPolicy]` 필드 |
| 수정 | `backend/src/simulation/agents.py` | `decide()` 에 `if world.use_policy: return policy_decide(...)` 분기 |
| 수정 | `backend/src/simulation/runner.py` | 시뮬 시작 전 `generate_policies()` 호출 |
| 신규 | `data/processed/policy_cache.json` | 생성된 정책 JSON (재실행 시 LLM 호출 스킵) |

---

## 8. 실행 흐름

```
[시뮬 시작 전 — 1회, LLM 11회 호출]
generate_policies(roles=6, weather=current_weather) →
  policy_cache.json 저장 (11 × PersonaPolicy)

[시뮬 루프 — 1000 agents × 20 steps, LLM 0회]
for tick in range(steps):
    for agent in agents:
        policy = world.policy_cache[(agent.role, world.weather)]
        policy = apply_personal_variation(policy, agent, rng)
        if should_visit(agent, policy, rng):
            store = pick_store_by_score(agent, policy, world, rng)
            agent.apply(Decision(action="visit", target_store_id=store.id))
```

---

## 8.5 추가 도입 패턴 — HuggingFace `jessiexuening/llm-enhanced-abm` 컬렉션 조사 결과

> 컬렉션 3편(Concordia / TraderTalk / Reliability Guide) 조사 결과 우리 Policy Generator 설계는 학계적으로 정당화됨. 다만 **3가지 패턴**을 추가로 도입하여 realism·과학적 엄밀성·이벤트 처리력을 강화한다.

### A. GameMaster 컴포넌트 (Concordia 차용)

현재 정책에 날씨·혼잡·이벤트 충격이 다 섞여 있는데, **환경 이벤트 해석기**를 별도 컴포넌트로 분리한다. 임대료 +30% 같은 시나리오 충격을 정책 재생성 없이 즉시 주입 가능.

**신규 파일**: `backend/src/simulation/game_master.py`

```python
@dataclass
class GameMaster:
    """환경 이벤트 → 정책 파라미터 보정.

    정책 재생성(LLM 호출) 없이 시나리오 충격을 즉시 반영.
    """

    def adjust_policy(self, policy: PersonaPolicy, world: World) -> PersonaPolicy:
        adj = replace(policy)
        # 날씨 충격
        if world.weather == "비":
            adj = replace(adj,
                indoor_preference=clamp(adj.indoor_preference * 1.3, 0, 1),
                mobility=clamp(adj.mobility * 0.7, 0, 1),
            )
        if world.weather == "눈":
            adj = replace(adj,
                indoor_preference=clamp(adj.indoor_preference * 1.5, 0, 1),
                mobility=clamp(adj.mobility * 0.4, 0, 1),
            )
        # 임대료/가격 충격
        if world.price_multiplier > 1.0:
            shock = world.price_multiplier - 1.0
            adj = replace(adj, spend_tendency=clamp(adj.spend_tendency * (1 - shock * 0.5), 0, 1))
        # 공휴일 가산
        if world.is_holiday:
            adj = replace(adj, visit_probability=clamp(adj.visit_probability * 1.3, 0, 1))
        return adj
```

**적용 위치**: `agents.decide()` 흐름의 `apply_personal_variation()` 직후 호출. 정책 11개 그대로 두고, GameMaster가 **런타임에 미세 조정**.

**이점**:
- 시나리오 충격(임대료 +30%, 폭우 등) 추가 시 LLM 재호출 0회
- 충격 효과를 정책에서 분리 → 단위 테스트로 검증 가능
- 사전 캐시 시나리오 30개 생성 시 비용 절감 (정책 11개 × GameMaster 변형 30가지 = 330 변형)

### B. Train/Test Split 검증 Protocol (Reliability Guide 차용)

현재 우리는 living_population 60일치 전부를 calibration에 쓰는데, **train/test 분할** 후 test에서만 RMSE 보고하는 구조로 변경. overfitting 방지 + 과학적 엄밀성 확보.

**프로토콜**:

| 데이터셋 | 기간 | 용도 |
|---|---|---|
| Train | 2026-01 ~ 03 (90일) | `time_age_boost` calibration, 정책 LLM 프롬프트 컨텍스트 |
| Test | 2026-04 (30일) | 시뮬 결과 검증 — 시간×동×연령 분포 RMSE |
| Holdout | 2026-04 마지막주 (7일) | 최종 발표 직전 1회만 검증 |

**검증 지표** (`scripts/validate_simulation.py`):
- 시간×동 유동인구 RMSE — 시뮬 vs test set
- 카테고리별 매출 분포 KL divergence
- Top 20 매장 적중률 (시뮬이 뽑은 top 20 ∩ 실측 top 20)

**산출물**: `docs/validation-report.md` — 발표 슬라이드에 직접 인용

**이점**:
- 심사위원 "이 시뮬이 정확한 거 맞나요?" 질문에 RMSE 수치로 답변
- 논문 인용 가능: "García Navarro et al. 2024 GABM Reliability Guide 프로토콜 따름"

### C. OTR-style Spillover (TraderTalk 차용)

"의도했지만 실행 실패" 시나리오. 매장 만석/폐점/품절로 정책 점수 1위가 아닌 매장으로 spillover. realism 한 단계 ↑.

**구현**: `policy_executor.py`의 `pick_store_by_score()`에 capacity 제약 추가

```python
def pick_store_by_score(agent, policy, world, rng) -> Store | None:
    candidates = world.stores_in_dong(agent.current_dong)
    scored = [(s, score_store(s, agent, policy, world)) for s in candidates]
    scored.sort(key=lambda x: -x[1])

    # 상위 5개 후보 중 capacity 여유 있는 첫 매장 선택
    for store, _ in scored[:5]:
        if store.is_open_now and store.occupancy < 1.0:
            return store
    # 모두 만석 → spillover (인접 동으로)
    for d in adjacent_dongs(agent.current_dong):
        for s in world.stores_in_dong(d):
            if s.is_open_now and s.occupancy < 1.0:
                return s
    # 그래도 없으면 visit 포기
    return None
```

**효과**:
- 인기 매장 집중 현상 완화 → top_stores 분포가 더 자연스러움
- "왜 2위 매장 매출도 높나요?" 답변 가능 (1위 spillover)
- 정책에 capacity 변수 추가 안 해도 됨 (Python 함수에서 처리)

### D. 도입 후 누적 효과

| 항목 | 도입 전 | 도입 후 |
|---|---|---|
| 시나리오 충격 추가 비용 | LLM 11회 재호출 | **0회 (GameMaster)** |
| 시뮬 결과 검증 | 없음 | **RMSE / KL / Top20 적중률** |
| 매장 분포 자연스러움 | 1위 집중 경향 | spillover로 완화 |
| 학계 정당화 | 자체 설계 | **3편 논문 인용 가능** |

### D.5 LangGraph 신규 매장 주입 처리 (B1 확인 사항)

**질문**: Scenario.new_store (B1 LangGraph 결과)가 `world.stores`에 주입될 때 `score_store()`가 이 신규 매장을 후보로 포함하는가?

**답변**: **자동 포함됨**. 흐름:

```
LangGraph 결과 (Scenario.new_store)
   ↓
world.add_store(new_store)
   ↓ (stores[id] + stores_by_dong[dong] 자동 갱신)
world.stores_in_dong(dong)
   ↓
score_store() 후보로 포함
```

**단, 두 가지 속성을 B1 쪽에서 설정 필요**:

| 속성 | 미설정 시 | 권장값 |
|---|---|---|
| `popularity_boost` | 기본 1.0 (RDS 매출·감성 데이터 없음) | LangGraph에서 예상 매출 기반 0.5~2.0 주입, 또는 같은 동·카테고리 평균값 |
| `menu_items` | 빈 리스트 → 카테고리 base 가격 fallback | LangGraph 시나리오에 포함된 메뉴 전달, 없으면 base 사용 |

두 속성이 없어도 시뮬은 돌아가지만 **신규 매장 방문률이 과소 예측됨** (기존 매장의 popularity_boost가 1.0 이상일 가능성 높으므로).

**코드 계약** (B1-A1 인터페이스):

```python
# B1: LangGraph 결과 → Store 변환
new_store = Store(
    store_id=world.next_store_id(),
    name=scenario.new_store_name,
    dong=scenario.dong,
    category=scenario.category,
    popularity_boost=estimate_boost_from_scenario(scenario),  # ← 필수
    menu_items=scenario.menu or [],  # ← 있으면 전달
    ...
)
world.add_store(new_store)  # ← 이 호출 한 번이면 시뮬 반영 완료
```

### E. 구현 우선순위 (5일 로드맵에 통합)

| 추가 항목 | Day | 작업량 |
|---|---|---|
| **A. GameMaster** | Day 3 (policy_executor.py와 함께) | +0.5일 |
| **B. Train/Test split** | Day 5 (벤치와 함께) | +1일 |
| **C. OTR Spillover** | Day 4 (통합 검증과 함께) | +0.5일 |

→ 기존 5일 로드맵이 **6~7일로 확장**, 그러나 발표 방어력은 크게 상승.

---

## 9. 예상 성능

| 항목 | 현재 Tier 모델 | Policy Generator |
|---|---|---|
| LLM 호출 (1000명 1일) | 5,000회 | **11회** |
| 비용 | $0.3~0.7 | **$0.002** |
| 시간 | 9시간 | **30초~2분** (Python only) |
| 개별성 | Tier B 동질 | 1000명 모두 ±15% 편차 |
| 재현성 | 시드 고정해도 LLM 흔들림 | 정책 캐시 후 100% 결정론 |
| 해석가능성 | LLM 응답 분석 필요 | 정책 JSON 사전 검증 가능 |

---

## 10. 심사 방어 포인트

- **"왜 이 매출이 나왔어요?"** → `policy.rationale` 필드에 LLM이 작성한 이유 + 점수 함수 breakdown 제공
- **"LLM 역할이 뭔가요?"** → "행동 정책 파라미터 생성. 실제 시뮬은 결정론적 Python 함수" — 정확히 말할 수 있음
- **"개별성은 있나요?"** → "정책은 11개이나 ±15% 개체 편차 + agent.profile(RDS 실데이터) 결합으로 1000명 모두 고유 행동"
- **"재현 가능한가요?"** → "policy_cache.json 파일로 모든 결정이 투명하게 기록됨. git 에 커밋 가능"

---

## 11. 단점 및 보완책

| 단점 | 완화 방법 |
|---|---|
| 정책이 너무 단조로움 | 역할×성향×날씨 = 12개로 확장 (발표 후 v2) |
| LLM이 엉뚱한 숫자 생성 | JSON schema 강제 + 생성 후 sanity check (`0<=v<=1`) |
| 날씨/시간대 경계 처리 | `time_block` 블록 전환 시 부드러운 interpolation |
| 행동 예측이 너무 예측 가능 | Python rng 온도 상수 추가 (score softmax temperature) |
| 이벤트적 의외성 부재 | 5% 확률로 "탐험 모드" — 정책 무시 무작위 선택 |

---

## 12. 5일 구현 로드맵

| Day | 작업 | 산출물 |
|---|---|---|
| 1 | `PersonaPolicy` dataclass + LLM 프롬프트 템플릿 작성 | `policy_generator.py` 스켈레톤 |
| 2 | Gemini 연결 + 11개 정책 1회 생성 + 검증 | `policy_cache.json` |
| 3 | `score_store`, `should_visit` 등 순수 Python 함수 | `policy_executor.py` |
| 4 | `agents.decide()` 통합 + 20명 tiny 시뮬 검증 | sim 결과 JSON |
| 5 | 1000명 풀 시뮬 벤치 → 목표 시간 도달 확인 | 벤치 레포트 + 사전 캐시 배치 |

---

## 13. 결정 사항 (확정: 2026-04-21)

| 항목 | 결정 | 근거 |
|---|---|---|
| 정책 개수 | **11개 (역할5 × 날씨2 + Owner1)** ✅ | 충분한 다양성 |
| LLM 제공자 | **Gemini 2.5 Flash-Lite JSON mode** ✅ | JSON schema 강제 필요 (Qwen 부적합) |
| 개체 편차 | **±15%** ✅ | 합리적 범위 |
| A. GameMaster | **도입** ✅ | 발표 중 즉흥 시나리오 질문 대응 |
| B. Train/Test Split | **보류** ⚠️ | Day +1 대비 시연 임팩트 낮음, 슬라이드에 "RMSE 검증 예정" 멘션으로 대체 |
| C. OTR Spillover | **도입** ✅ | +0.5일로 realism 크게 향상, "2위 매장도 높은 이유" 방어 |
| Day 1 착수 | **즉시** ✅ | 발표까지 시간 촉박 |

**실제 로드맵**: 기존 5일 + GameMaster(+0.5일) + Spillover(+0.5일) = **6일**

→ `policy_generator.py` Day 1 스켈레톤 작성 착수.

---

## 14. 참고 문헌

- Vezhnevets et al. (DeepMind) 2023. *Concordia: Generative ABM with grounded actions.* https://huggingface.co/papers/2312.03664
- Vidler & Walsh 2024. *TraderTalk: LLM Behavioural ABM for Bilateral Trading.* https://huggingface.co/papers/2410.21280
- García Navarro et al. 2024. *Designing Reliable Experiments with GABM (Concordia Guide).* https://huggingface.co/papers/2411.07038
- 컬렉션: https://huggingface.co/collections/jessiexuening/llm-enhanced-abm
