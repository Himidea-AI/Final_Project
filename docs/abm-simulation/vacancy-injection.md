# Vacancy Injection — 공실 → ABM 가상 매장 주입

작성: A1 (찬영) — 2026-04-26
모듈: `backend/src/simulation/vacancy_inject.py`

> **한 줄 요약**: LangGraph `district_ranking` 노드가 추출한 공실 좌표를 ABM World 에 가상 Store 로 주입해, 1000 agent 시뮬레이션 결과로 "이 공실에 X 업종 차렸을 때의 일 평균 방문/매출"을 정량화한다.

---

## 1. 동기

기존 ABM 의 한계:
- `World.stores` 는 `kakao_store` 테이블의 **실제 영업 매장**만 로드
- 공실 좌표는 `district_ranking` 노드가 따로 로드하지만 ABM 에 흘러가지 않음
- B1 LangGraph 추천 결과(`vacancy_spots`) 와 ABM 시뮬 사이 **연결 다리 없음**

기존 자산:
- `runner.py` 의 `scenario.new_store` — **단일** 신규 매장 주입만 지원, 다중 추천 처리 불가
- `score_store / should_visit / pick_store_with_spillover` — 매장 추가만 하면 자동으로 score 경쟁에 노출

→ 본 모듈은 **배치 주입 + 결과 집계 API** 만 제공. 시뮬 로직은 기존 자산 그대로 활용.

---

## 2. 데이터 흐름

```
[B1 LangGraph: district_ranking]               [ABM]                            [결과]
_load_vacancy_spots(dong_names)                inject_vacancies_batch           evaluate_vacancies_batch
  → vacancy_spots = [                  →       (world, spots, "카페")    →     [{vid, dong, visits,
      {dong, lat, lon, wolse}, ...                                                revenue_per_day, ...}, ...]
    ]
                                               (run_simulation 1000 agents × N일)
```

데이터 출처:
- 공실: 네이버 부동산 월세 매물 (좌표 유효한 것만), 2026-04 기준
- 추천 업종: B1 LangGraph 분석 결과 또는 사용자 지정

---

## 3. API 레퍼런스

### `inject_vacancy_as_store(world, vacancy_spot, category, **kwargs) -> str`

공실 1개를 가상 Store 로 주입.

**파라미터**:
- `world`: ABM `World` 인스턴스
- `vacancy_spot`: `{"dong": str, "lat": float, "lon": float, ...}` — `district` 키도 허용
- `category`: 업종 (`"음식점" | "카페" | "주점" | "편의점" | "기타"`)
- `name`: 매장 이름 (생략 시 `VACANCY_{idx}_{dong}`)
- `seats`: 좌석 수 (기본 30, 혼잡도 영향)
- `rating`: 평점 (기본 4.0, 신규라 중립 권장)
- `price_level`: 가격대 1~3 (기본 2)
- `popularity_boost`: 인지도 (기본 **5.0** — 신규 마케팅 가정. ⚠️ 1.0 사용 시 매장 단위 noise dominant — §5.3 참조)

**반환**: `vacancy_id` 문자열 — 형식 `"vacancy_{N}_{dong}"`, 기존 매장과 충돌 없음

**예외**: `VacancyInjectionError` — 좌표 누락, 동 매칭 실패, 카테고리 무효

---

### `inject_vacancies_batch(world, vacancy_spots, category, skip_invalid=True, **overrides) -> list[str]`

여러 공실 일괄 주입 (모두 같은 카테고리).

- `skip_invalid=True` (기본): 실패 spot 은 로그만 남기고 스킵
- `skip_invalid=False`: 첫 실패에서 즉시 `VacancyInjectionError` raise
- `**overrides`: `seats`, `rating`, `price_level`, `popularity_boost` 일괄 적용

**반환**: 성공한 vacancy_id 리스트 (입력 순서, 실패 제외)

---

### `evaluate_vacancy_store(world, vacancy_id, days_simulated=1) -> dict`

가상 매장 1개 시뮬 결과 집계.

**반환**:
```python
{
    "vacancy_id": "vacancy_0_서교동",
    "dong": "서교동",
    "category": "카페",
    "lat": 37.5544,
    "lon": 126.9220,
    "visits": 312,           # 시뮬 종료 시점 누적 방문
    "revenue": 1_456_000,    # 누적 매출(원)
    "occupancy": 1.0,        # 좌석 점유 (visits/seats, 1.0 cap)
    "visits_per_day": 44.6,  # days_simulated 로 나눈 평균
    "revenue_per_day": 208_000,
}
```

⚠️ **주의**: `world.reset_daily()` 호출 시 `visits_today`/`revenue_today` 초기화. 다일 시뮬에서는 마지막 날 데이터만 집계되거나, 매일 누적값을 별도로 보존해야 함.

---

### `measure_cannibalization(world_with, world_baseline, vid, radius_m=500) -> dict` (NEW 2026-04-26)

신규 매장이 인근 기존 매장 visits/revenue 에 미치는 영향을 with/without 시뮬 비교로 측정.

**필수**: 같은 seed 로 baseline (vacancy 없음) 시뮬과 with-vacancy 시뮬을 별도 실행한 후 두 World 인스턴스 전달.

**반환**:
```python
{
    "vacancy_id", "vacancy_visits", "vacancy_revenue",
    "radius_m": 500,
    "n_neighbors": int,        # 반경 내 기존 매장 수 (vacancy 자체 제외)
    "same_category": {         # 같은 카테고리 (직접 경쟁/잠식)
        "n_stores": int,
        "delta_visits": int,   # 음수 = 잠식, 양수 = 시너지
        "delta_revenue": float,
        "cannibalization_pct": float,  # -delta_revenue / vacancy_revenue × 100
        "top_affected": [{store_id, name, dong, delta_visits, delta_revenue, distance_m}]  # 가장 잠식된 5
    },
    "other_category": {        # 다른 카테고리 (시너지/경쟁)
        "n_stores": int,
        "delta_visits": int,
        "delta_revenue": float,
        "synergy_pct": float,
    },
}
```

**해석**:
- `cannibalization_pct > 0`: 잠식 (학술 표준 30~50%)
- `cannibalization_pct < 0`: 시너지 (신규 매장이 인근 카페 traffic 같이 끌어옴)
- ⚠️ single seed 결과는 noise 가능 — PSE N=5 권장

---

### `compare_to_dong_average(world, vid, days_simulated=1) -> dict` (NEW 2026-04-26)

Vacancy 결과를 동·카테고리 평균 매장과 비교. Sample size 한계 (개별 매장 noise) 우회용.

**반환**:
```python
{
    "vacancy_id",
    "vacancy_visits_per_day", "vacancy_revenue_per_day",
    "dong_category_n_stores": 334,                    # 같은 동·카테고리 매장 수
    "dong_category_avg_visits_per_day": 0.21,         # 평균 매장당 visits
    "dong_category_avg_revenue_per_day": 10000,       # 평균 매장당 revenue (원)
    "vacancy_vs_avg_visits_ratio": 37.6,              # vacancy 가 평균의 X 배
    "vacancy_vs_avg_revenue_ratio": 16.4,
    "dong_total_visits_per_day": 78.2,                # 동 전체 (vacancy 포함) 합계
    "dong_total_revenue_per_day": 78_000,
}
```

**해석**: ratio 가 의미 있는 신호 (visits 절대값보다 더 robust). 해석 쉬움 — "이 자리에 차리면 평균 카페보다 X배 잘 됨".

---

### `evaluate_vacancies_batch(world, vacancy_ids, days_simulated=1) -> list[dict]`

여러 가상 매장 결과 일괄 집계, **visits 내림차순** 정렬.

---

## 4. 사용 예제

### 단일 공실 평가

```python
from src.simulation.runner import run_simulation
from src.simulation.world_loader import load_world_from_rds
from src.simulation.vacancy_inject import inject_vacancy_as_store, evaluate_vacancy_store

world = load_world_from_rds()
vid = inject_vacancy_as_store(
    world,
    vacancy_spot={"dong": "서교동", "lat": 37.5544, "lon": 126.9220},
    category="카페",
    # popularity_boost 생략 시 DEFAULT_POPULARITY_BOOST=5.0 사용 (마케팅 가정).
    # 1.0~1.2 는 1000ag × 1d 시뮬에서 visits=0 dominant — §6.1 참조.
)
result = run_simulation(world, n_agents=1000, days=7)
print(evaluate_vacancy_store(world, vid, days_simulated=7))
# → {visits: 312, revenue: 1_456_000, visits_per_day: 44.6, ...}
```

### B1 LangGraph 결과 → 다중 평가

```python
# LangGraph 결과 state 로부터 받은 spots
vacancy_spots = state["vacancy_spots"]  # district_ranking 노드 출력
# [{dong:"서교동", lat:..., lon:..., wolse:5_000_000}, ...]

vids = inject_vacancies_batch(world, vacancy_spots, category="카페")
print(f"{len(vids)}개 공실에 가상 카페 주입")

result = run_simulation(world, n_agents=1000, days=7)

ranking = evaluate_vacancies_batch(world, vids, days_simulated=7)
for r in ranking[:5]:
    print(f"{r['dong']:6s} {r['vacancy_id']:30s} → {r['visits_per_day']:5.1f}회/일, {r['revenue_per_day']/10000:.0f}만원/일")
```

### API 엔드포인트 통합 (제안)

```python
# backend/src/api/simulation.py
@router.post("/api/simulate-vacancy-batch")
async def simulate_vacancy_batch(req: VacancyBatchRequest):
    world = load_world_from_rds()
    vids = inject_vacancies_batch(world, req.vacancy_spots, req.category)
    sim_result = run_simulation(world, n_agents=req.n_agents, days=req.days)
    return {
        "rankings": evaluate_vacancies_batch(world, vids, req.days),
        "sim_meta": {"agents": req.n_agents, "days": req.days},
    }
```

---

## 5. ABM 의 어떤 로직이 가상 매장을 평가하나

`world.add_store()` 만 호출하면 신규 매장도 기존 매장과 동일하게 시뮬 대상이 됨. 작용하는 자산:

| ABM 로직 | 위치 | 가상 매장에 작용? |
|---|---|---|
| `score_store` (15+ 요인) | `policy_executor.py:373` | ✅ 자동 |
| Haversine 거리 비용 | `policy_executor.py:430` | ✅ vacancy_spot lat/lon 사용 |
| 동 거리 (dong_distance) | `policy_executor.py:50` | ✅ vacancy_spot.dong 사용 |
| 영업시간 (`is_open_now`) | `scheduler.py:79` | ✅ 기본 항상 영업 (필요시 hours 지정) |
| 혼잡도 패널티 | `policy_executor.py:435` | ✅ seats 기본 30 기준 |
| 페르소나 30종 + Nemotron | `profile_builder.py` | ✅ |
| 친구 추천 spillover | `policy_executor.py:457` | ✅ visits 후 자동 발생 |
| Layer 2 기억 (visit_history) | `agents.py:157` | ✅ 신규지만 누적 시작 |
| OFS dong score boost (Option E) | `policy_executor.py:484` | ✅ ext_visitor 일수록 강하게 |
| 카테고리 시간대 boost | `policy_executor.py:387` | ✅ |

---

## 6. 한계 — 정직하게 (2026-04-26 갱신)

### 6.1 ⚠️ Sample Size — 가장 큰 한계 (NEW)

**1000 agent × 1일 시뮬은 매장 단위 noise dominant**.

- 서교동에 카페만 335개 → 1000 agent 분산 후 매장당 평균 0.2 visits/day
- popularity_boost=1.0 (중립) 시 vacancy 도 단지 314개 0-visit 매장 중 하나 → **visits=0 흔함**
- popularity_boost sweep 측정:
    - 1.0 → 0 visits/day (noise)
    - **5.0 → 15 visits/day (sweet spot)** ⭐
    - 10.0 → 12 visits/day (saturation)

**해결**:
- `DEFAULT_POPULARITY_BOOST = 5.0` 채택 (마케팅 가정 명시)
- N=5 PSE 권장 (single seed 결과 신뢰 X)
- `compare_to_dong_average()` 동 평균 비교 utility 사용 (절대값보다 ratio 가 robust)

### 6.2 가정 / 미모델링

1. **`popularity_boost` default 5.0 가정** — 신규 매장 마케팅 효과의 임의 상수.
   실제 인지도는 운영 1~3개월 누적 후 결정되므로 상한 가정 (§6.1 참조).
2. **`rating` 4.0 가정** — 임의값. 동일 동·업종 평균을 사용하면 더 정확.
3. **0일차 cold start** — Layer 2 기억 누적 안 됨. `warmup_days` 옵션으로 완화 가능.
4. **인지·탐색 가정** — 모든 agent 가 즉시 신규 매장을 "안다고 가정". 정보 확산 시간 미반영.
5. **단일 카테고리 가정** — 한 공실에 한 업종만 (카페+책방 같은 멀티 컨셉 미지원).
6. **`world.reset_daily()` 영향** — 다일 시뮬은 마지막 날 visits 만 보존.
7. **카니발리제이션 PSE 필요** — single seed 측정값은 noise 와 구분 불가.
   `measure_cannibalization()` 으로 산출은 가능하나 N=5 PSE 권장.

---

## 7. 검증 항목 (smoke test)

`backend/src/simulation/vacancy_inject.py` 모듈에 대한 통과 케이스:

- ✅ 단일 주입 — `vacancy_0_{dong}` ID 생성, World 에 등록
- ✅ 배치 주입 — N 개 spot 중 유효한 것만 등록 (잘못된 동 스킵)
- ✅ 좌표 누락 시 `VacancyInjectionError`
- ✅ 잘못된 카테고리 시 `VacancyInjectionError`
- ✅ 동 미등록 시 `VacancyInjectionError`
- ✅ ID 충돌 없음 (기존 매장 80개 + vacancy 4개 = 84개)
- ✅ `evaluate_vacancies_batch` visits 내림차순 정렬

---

## 8. 추가 모듈 — PSE + LangGraph 통합 (2026-04-26 추가)

기존 `vacancy_inject` 단일 seed 결과의 noise 문제를 해결하는 상위 레이어 2개:

### 8.1 `vacancy_pse.py` — PSE N=5 통합 평가

```python
from src.simulation.vacancy_pse import evaluate_vacancy_pse

result = evaluate_vacancy_pse(
    vacancy_spot={"dong": "서교동", "lat": 37.5544, "lon": 126.9220},
    category="카페",
    n_seeds=5,                  # PSE N — 권장 ≥ 3
    days=1,
    with_cannibalization=True,  # baseline 시뮬도 (시간 2배)
    popularity_boost=5.0,       # default (마케팅 가정)
)

# 반환:
# result["pse_summary"]["visits_per_day"]       — {mean, std, ci95, min, max, n}
# result["pse_summary"]["dong_net_growth_pct"]  — 동 시장 변화 (TIGHT, 권장)
# result["narrative"]                            — 사람 읽기용
# result["per_seed"]                             — raw seed 결과
```

**검증된 측정값 (서교동 카페, PSE N=10)**:
- visits/day: **10.0 ± 1.43** (95% CI tight)
- revenue/day: 11 ± 1 만원
- 동 평균 대비: 48.1 ± 6.6 배
- **dong_net_growth_pct: +1.41 ± 3.51%** (vacancy ≈ zero-sum, 학술 발견)

> 참고: PSE N=3 측정 (`vacancy_pse_seogyo_cafe_n10.json` 이전 run) 은
> visits/day **9.7 ± 1.3** 로 나옴. N 증가 시 mean ~10 으로 수렴.

### 8.2 `vacancy_evaluation_service.py` — LangGraph 통합 + 순위

```python
from src.services.vacancy_evaluation_service import evaluate_top_vacancies, format_rankings_text

rankings = evaluate_top_vacancies(
    vacancy_spots=state["vacancy_spots"],  # district_ranking 노드 출력
    category="카페",
    top_n=5,                # 시간 절약 — 상위만
    n_seeds=5,
    pre_filter_score=...,   # district_ranking score 제공 시 상위만
)
print(format_rankings_text(rankings))
```

district_ranking 키 (`dong_name`) → vacancy_pse 키 (`dong`) 자동 변환.

### 8.3 REST API — `backend/src/api/vacancy_evaluation.py`

```
GET  /vacancy-evaluation/health    — 모듈 ping
POST /vacancy-evaluation/single    — 단일 vacancy PSE
POST /vacancy-evaluation/batch     — 여러 vacancy + 순위
```

**주요 특징**:
- API 호출 시 mock LLM 강제 (비용 안정, 키 의존성 제거)
- `popularity_boost` None → default 5.0 fallback
- Pydantic 검증: 카테고리/좌표/N 범위
- 응답 시간: 5분 (single, no cannibal) ~ 14분 (batch 5 × N=3)
- 클라이언트 timeout >= 600s 권장

**curl 예제**:
```bash
curl -X POST http://localhost:8000/vacancy-evaluation/single \
  -H "Content-Type: application/json" \
  -d '{
    "spot": {"dong": "서교동", "lat": 37.5544, "lon": 126.9220},
    "category": "카페",
    "n_seeds": 5,
    "with_cannibalization": true
  }'
```

### 8.4 검증 결과 — Test 4 (4동 batch, 2026-04-26)

| 순위 | 동 | visits/day | ratio_to_avg |
|---|---|---|---|
| #1 | 상암동 | 12.3 ± 2.6 | (office, 카페 적음) |
| #2 | 합정동 | 8.3 ± 1.3 | 57.4× |
| #3 | 서교동 | 7.7 ± 1.7 | 36.5× (포화 시장) |
| #4 | 망원1동 | 5.0 ± 0.0 | 82.9× |

**발견**: 절대 visits ≠ ratio. 서교동 절대 매출은 약하지만 시장 포화 효과 (카페 335개).

저장: `validation/results/vacancy_batch_ranking_4dongs.json`

---

## 9. 다음 단계 후보

| 우선순위 | 항목 | 설명 |
|---|---|---|
| 🔴 high | 프론트 연결 (`/vacancy-evaluation/single` 콜) | 사용자 → API → ABM 흐름 완성 |
| 🔴 high | LangGraph district_ranking → vacancy_evaluation_service 자동 연결 | B1 → ABM 다리 |
| 🔴 high | API 비동기 큐 (RQ/Celery) | 응답 5~10분 → polling/webhook |
| 🟡 mid | trajectory 기록에 vacancy_id 보존 | 시간대별 방문 분석 |
| 🟡 mid | `popularity_boost` 자동 추정 | 동·업종·평수 기반 |
| 🟡 mid | Test 4 가설 정정 (포화도 변수 추가) | Kendall τ ≥ 0.5 목표 |
| 🟢 low | 멀티 카테고리 매장 지원 | Store 모델 확장 |
| 🟢 low | 시간대별 visits 분포 차트 | 프론트 시각화 |
