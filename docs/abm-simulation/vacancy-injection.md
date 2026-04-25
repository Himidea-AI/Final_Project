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
- `popularity_boost`: 인지도 (기본 1.0, 마케팅 가정 시 > 1.0)

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
    popularity_boost=1.2,  # 적당한 마케팅 가정
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

## 6. 한계 — 정직하게

1. **`popularity_boost` 디폴트 1.0** — 신규 매장의 인스타·블로그 마케팅 효과 미반영. SNS 노출 강도에 따라 1.2~2.0 수동 보정 필요.
2. **`rating` 4.0 가정** — 임의값. 동일 동·업종 평균을 사용하면 더 정확. 향후 개선 가능.
3. **0일차 cold start** — Layer 2 기억(`learned_prefs`/`habit_store`) 누적 안 됨. 신규 매장이 첫날 score 낮음. `warmup_days` 옵션으로 완화 가능.
4. **인지·탐색 가정** — 모든 agent 가 즉시 신규 매장을 "안다고 가정". 현실은 정보 확산 시간 필요. ABM 의 친구 추천 로직이 일부 보완하지만 완벽하지 않음.
5. **카니발리제이션 미산출** — 신규 매장이 인근 기존 매장 매출을 얼마나 잠식하는지 별도 계산 필요. `Scenario.cannibalize_radius_m` 활용 가능.
6. **단일 카테고리 가정** — 한 공실에는 한 업종만. 멀티 컨셉 매장(카페+책방 등) 미지원.
7. **`world.reset_daily()` 영향** — 다일 시뮬에서는 마지막 날 visits 만 보존. 매일 누적 보존이 필요하면 `runner.py` 측 trajectory 기록 사용 권장.

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

## 8. 다음 단계 후보

| 우선순위 | 항목 | 설명 |
|---|---|---|
| 🔴 high | `simulate-vacancy-batch` API 엔드포인트 | LangGraph 결과를 HTTP 로 받아 시뮬 실행 |
| 🔴 high | trajectory 기록에 vacancy_id 보존 | 시간대별 방문 패턴 분석 가능 |
| 🟡 mid | `popularity_boost` 자동 추정 | 동·업종·평수 기반 baseline 산출 |
| 🟡 mid | 카니발리제이션 계산 통합 | `Scenario.cannibalize_radius_m` 와 연결 |
| 🟢 low | 멀티 카테고리 매장 지원 | Store 모델 확장 필요 |
| 🟢 low | 시간대별 visits 분포 차트 | 프론트 시각화 |
