# LangGraph 에이전트 × ABM 시뮬 연결 로드맵

> 기존 LangGraph 5노드(market_analyst / population_analyst / legal / district_ranking / synthesis) 결과를 **마포 1,000 페르소나 ABM 시뮬의 Scenario로 주입**하는 통합 계획.

---

## 0. 목적

- **LangGraph** = 정적 상권 분석 (AI 5 에이전트 리포트)
- **ABM** = 동적 소비자 시뮬 (1,000 페르소나 하루 행동)
- **연결**: "분석 → 시뮬 검증 → 의사결정" 풀 파이프라인 완성

"다른 조의 상권 분석 대시보드"를 넘어 **의사결정 지원 시스템(DSS)**으로 포지셔닝.

---

## 1. 연결 시나리오

**입력**: `"마포구 상암동에 스타벅스 100평 출점"`

| 단계 | 엔진 | 출력 |
|------|------|------|
| 1. 분석 | LangGraph 5 에이전트 | 적합도 점수, 경쟁 분석, 법률 체크, 예상 매출 |
| 2. 시나리오 변환 | 신규 어댑터 | `Scenario.new_store` 객체 |
| 3. 시뮬 | ABM (1,000 페르소나) | 실 방문 수, 매출, 경쟁 매장 영향 |
| 4. 재합성 | LangGraph synthesis | ABM 결과 포함 최종 리포트 |

### 출력 예시

```
📊 ABM 검증 결과 — 상암동 스타벅스 100평
- 일일 방문: 평균 213명 (σ 18)
- 일일 매출: 932,000원 (월 2.8억)
- 경쟁 영향: 메가MGC 상암점 -22%, 폴바셋 -15%
- 주 고객: 30대 방송 스태프 38%, 20대 학생 24%
- 피크: 10시 / 14시 / 17시
```

---

## 2. Phase 1 — 최소 연결 (4시간)

### 2.1 Scenario 확장
`backend/src/simulation/config.py`:
```python
@dataclass
class Scenario:
    weekend_force: bool = False
    rent_shock_pct: float = 0.0
    # 신규
    new_store: dict | None = None           # LangGraph 출력 기반
    cannibalize_radius_m: int = 500          # 경쟁 영향 반경
    promotion_weeks: int = 0                 # 오프닝 부스트 주차
```

### 2.2 World 병합 로직
`world_loader`에 `inject_new_store(world, spec)` 추가:
- 기존 매장 그대로 로드
- `new_store` dict → `Store` 생성 후 `world.add_store()`
- 반경 내 기존 매장 `popularity_boost` 감소 (카니발리제이션)

### 2.3 API 엔드포인트
`backend/src/api/simulation.py`:
```python
POST /api/simulate-abm
Body: {
  "langgraph_result": { ... },   # 기존 /simulate 결과
  "scenario": {
    "days": 1,
    "mini": true,                 # 100명 축소 실행
    "monte_carlo": 3              # 3회 반복 평균
  }
}
```

### 2.4 프론트엔드 버튼
기존 분석 결과 페이지에:
```
[이 분석 결과로 시뮬 검증하기] ← 버튼
```
클릭 시 위 엔드포인트 호출 → 결과를 기존 리포트에 오버레이.

---

## 3. Phase 2 — 사전 캐시 (3시간)

### 3.1 캐시 디렉토리
```
data/processed/scenario_cache/
├── 상암동_카페_3.json        # dong × category × price_level
├── 연남동_카페_2.json
├── 합정동_음식점_2.json
└── ...
```

### 3.2 조합 인덱싱 (20~30개)
- 마포 16동 × 카테고리 4 × price_level 3 = 192 조합
- 상위 30개 조합 사전 시뮬 (야간/주말 배치)
- 캐시 hit → 즉시 응답 / miss → 비동기 실행

### 3.3 몬테카를로
- 1 시뮬만 하면 seed 의존 큼 → 3~5회 반복
- 결과: `{mean, std}` 리포트
- "월 매출 2.8억 ± 0.3억" 신뢰구간

---

## 4. Phase 3 — 고도화 (5시간+)

### 4.1 abm_verifier 노드
`backend/src/agents/nodes/abm_verifier.py`:
- LangGraph workflow의 `synthesis` 직전에 삽입
- `district_ranking` 결과에서 상위 후보지 → ABM 시나리오 자동 생성
- ABM 결과를 state에 저장

### 4.2 workflow 그래프
```
user_input
  → market_analyst
  → population_analyst
  → legal
  → district_ranking
  → abm_verifier     ← 신규
  → synthesis (ABM 결과 포함 최종 리포트)
```

### 4.3 최종 리포트 섹션
```markdown
## 3. 가상 소비자 시뮬 검증

### 3.1 상위 후보지 3곳 시뮬 결과
| 후보 | 적합도 | 예상 매출 | ABM 검증 | 델타 |
|------|-------|----------|---------|------|
| 상암동 | 72 | 1.8억 | 2.8억 ± 0.3 | **+55%** 긍정 |
| 서교동 | 85 | 2.5억 | 2.1억 ± 0.4 | -16% 경쟁 심함 |
| 연남동 | 78 | 2.2억 | 1.9억 ± 0.2 | -14% 포화 |

### 3.2 추천
**상암동** (정성 분석보다 ABM 결과 우수, 경쟁 영향도 낮음)
```

---

## 5. 기술적 도전 & 해결책

| 도전 | 문제 | 해결 |
|------|------|------|
| 속도 | ABM 1,000명 × 3시간 | **Mini ABM** 100명 × 6시간 집중 → 5~10분 |
| 결과 통합 | 데이터 포맷 차이 | `Scenario` dataclass 통일 |
| 실시간성 | 발표 시연 불가 | 사전 **캐싱** + 대표 조합 리플레이 |
| 시뮬 편차 | 단일 시뮬 노이즈 | **몬테카를로 3~5회** 평균 ± std |
| 경쟁 모델링 | 신규 매장이 기존 매출을 어떻게 잠식? | 반경 N m 내 `popularity_boost *= (1 - 0.3)` |

---

## 6. 데이터 흐름도

```
[사용자 입력: 상암동 스타벅스 출점]
           │
           ▼
┌──────────────────────────────┐
│ LangGraph (기존 5 노드)        │
│  market / pop / legal /      │
│  district_ranking / synthesis│
└──────────────────────────────┘
           │  JSON result
           ▼
┌──────────────────────────────┐
│ Scenario Adapter (신규)       │
│  → Scenario.new_store         │
│  → cannibalize_radius         │
│  → promotion_weeks            │
└──────────────────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ ABM 시뮬 (마포 1000명)         │
│  - world_loader + new_store   │
│  - 1일 × 3회 몬테카를로        │
│  - profile 기반 의사결정       │
│  - 친구 DSL 대화              │
└──────────────────────────────┘
           │  trajectory/visits/chats
           ▼
┌──────────────────────────────┐
│ Result Aggregator (신규)      │
│  - 매출 평균/편차              │
│  - 경쟁 매장 영향도            │
│  - 고객 페르소나 분포          │
└──────────────────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ LangGraph synthesis 재호출    │
│  - ABM 결과 주입              │
│  - 최종 리포트 생성            │
└──────────────────────────────┘
           │
           ▼
[프론트엔드 리포트 + 지도 시각화]
```

---

## 7. 발표 서사 (DSS 각본)

```
입력 → 분석 → 시뮬 → 검증 → 의사결정
```

> "상암동 스타벅스 출점 후보지에 대해, 저희 시스템은 3단계로 분석합니다.
>
> **① 분석**: AI 에이전트 5명이 상권/인구/법률/경쟁을 분석해 **적합도 72점** 산출.
>
> **② 시뮬**: 1,000명의 가상 마포 주민이 실제 하루를 살면서 이 매장을 방문합니다. *[지도 시각화 시연]*
>
> **③ 검증**: 시뮬 결과 월 매출 **2.8억 ± 0.3억**, ROI **14개월**로 검증.
>
> 정적 분석을 넘어 **가상 실행까지 완결한 의사결정 지원 시스템**입니다."

---

## 8. 구현 우선순위

| 우선 | 작업 | 시간 | 발표 기여도 |
|------|------|------|-----------|
| 🥇 **1순위** | Phase 1 최소 연결 | 4h | ⭐⭐⭐⭐⭐ |
| 🥈 **2순위** | Phase 2 캐시 + 몬테카를로 | 3h | ⭐⭐⭐ |
| 🥉 **3순위** | Phase 3 abm_verifier 노드 통합 | 5h+ | ⭐⭐ |

**Phase 1만 완성해도 발표 임팩트 폭발.** 시연은 캐시된 결과 3~5개로 충분.

---

## 9. 체크리스트

### Phase 1 완료 조건
- [ ] `Scenario.new_store` dataclass 필드 추가
- [ ] `world_loader.inject_new_store()` 구현
- [ ] `POST /api/simulate-abm` 엔드포인트
- [ ] 기존 분석 리포트 페이지에 "시뮬 검증" 버튼
- [ ] 프론트엔드에서 결과 fetch + 지도 오버레이
- [ ] mini ABM 10분 내 완료 확인

### Phase 2 완료 조건
- [ ] 30개 조합 사전 시뮬 캐시
- [ ] 몬테카를로 3회 평균 리포팅
- [ ] 캐시 hit/miss 자동 라우팅

### Phase 3 완료 조건
- [ ] `abm_verifier.py` 노드 작성
- [ ] LangGraph workflow 그래프에 삽입
- [ ] synthesis 프롬프트에 ABM 결과 주입 템플릿
- [ ] 최종 리포트 "ABM 검증" 섹션 자동 생성

---

## 10. 관련 문서
- `docs/simulation-visual-roadmap.md` — 시각화 로드맵
- `docs/agent-dsl-cost-analysis.md` — DSL 비용 분석
- `docs/simulation-frontend-integration.md` — 프론트 통합 가이드
- `backend/src/agents/graph.py` — LangGraph workflow
- `backend/src/simulation/runner.py` — ABM 실행기
- `backend/src/simulation/config.py` — Scenario dataclass

---

## 11. 결론

**Phase 1 (4시간)** 만 구현해도 다음이 가능:
1. 기존 분석 리포트에 "ABM 시뮬 돌리기" 버튼
2. 1,000 페르소나가 신규 매장 방문 시뮬
3. 매출·경쟁·고객 분포 결과 리포팅
4. 발표 시연 가능

**경쟁 우위 한 줄**:
> "우리는 분석으로 끝내지 않습니다. **1,000명의 가상 소비자**가 실제로 매장을 방문해보고 결과를 돌려줍니다."
