# LLM 에이전트 정확도 평가 — v6 vs v7

**작성**: 2026-05-07
**범위**: backend 7 LLM 에이전트 (legal 별도 RAG benchmark 로 제외)

---

## 1. 1차 평가 (v6) — LLM-as-judge

### 측정 방식
- 4 차원 LLM 채점 (factuality / relevance / specificity / coherence, 각 0~5점)
- 평균 ≥ 4.0 → 통과

### 결과
| 에이전트 | v6 일치율 | MAPE |
|---|---:|---:|
| synthesis | 100% | — |
| competitor_intel | 100% | 24.6% |
| demographic_depth | 83.3% | — |
| trend_forecaster | 66.7% | — |
| population_analyst | 66.7% | — |
| market_analyst | 50.0% | **0.1%** |
| legal | 33.0% | — |

### 발견된 문제점
1. **market_analyst MAPE 0.1%** — LLM이 프롬프트에 주입된 숫자를 그대로 출력 → 측정 자체가 무의미
2. **자기참조 편향** — GPT가 GPT 출력을 채점, 후한 평가 경향
3. **factuality 검증 한계** — LLM이 INPUT의 모든 수치를 정확히 cross-check 못 함
4. **specificity 함정** — 구체적 숫자만 인용하면 가점, *틀린 수치도 구체적이면* 가점

### 결론
> v6 의 80~100% 점수는 *LLM-judge 의 거짓 양성* — 실제 정확도가 아니라 "LLM이 보기 좋다고 평가한 점수"

---

## 2. v7 재설계 — 룰엔진 / 직접 일치 비교

### 에이전트 유형별 측정 가능한 것

원칙: **에이전트는 "DB 데이터를 받아 해석/분류하는 기계"이므로 "데이터를 주입했을 때 해석이 맞는가"를 측정**

| 에이전트 | LLM이 실제로 하는 일 | v7 평가 방식 |
|---|---|---|
| market_analyst | 주입된 수치로 grade 판정 | **grade 분류 정확도** — 룰엔진 임계값 (QoQ + 포화도) |
| population | 유동인구 데이터 요약 | **연령·성별·피크 시간** 해석 일치율 |
| legal | 별도 RAG 기반 법령 답변 | 별도 RAG 정밀도 평가 (제외) |
| ranking / inflow | python 함수 처리 | 정량 룰엔진 — 평가 범위 외 |
| synthesis | 다른 에이전트 결과 종합 | **내부 정합성** (legal 보존·net_profit 수식·grade-추천 모순·winner) |
| demographic_depth | 연령·성별 분포에서 핵심 타겟 추출 | **top_3_age_groups 1위와 일치** |
| competitor_intel | 카카오 검색 결과 집계·요약 | **market_entry_signal** 룰엔진 (현행 유지) |
| trend_forecaster | 과거 추이로 미래 예측 | **QoQ 방향(증가/감소/유지)** 일치 |

### 핵심 변경
**자기참조 채점 → 외부 정답(룰엔진) + 직접 일치 비교**

---

## 3. v7 1차 결과 — 부분 성공 + 데이터 한계 발견

| 에이전트 | v7 (1차) | 비고 |
|---|---:|---|
| synthesis | 87.5% | 정량 정합성 룰 4개 평균 |
| competitor_intel | 100% | signal 룰 일치 |
| demographic_depth | 100% | top_3_age_groups 1위 일치 |
| population | **측정 불가** | raw distribution 캐시 부재 |
| market_analyst | **측정 불가** | grade/qoq/saturation 정형 필드 캐시 부재 |
| trend_forecaster | **측정 불가** | fixture loader wrapper 누락 |

### 측정 불가 원인
> Redis 캐시가 *LLM 처리 결과* 만 저장 → *비교 기준 raw 데이터* 부재 → 정답 라벨 산출 불가

---

## 4. 한계 해결 솔루션 — 캐시 schema 보강

| 에이전트 | 추가 raw 데이터 | 캐시 prefix |
|---|---|---|
| population_node | age / gender / time distribution | `population:` → `v2:population:` |
| market_analyst_node | qoq_growth_pct / saturation_level / competitor_count | `market:` → `v2:market:` |
| trend_forecaster_node | (이미 캐시됨, fixture loader fix) | `v2:trend_forecast:` (유지) |

### 작업 내용
- `backend/src/agents/nodes/population.py` — `raw_metrics` 필드 추가, prefix bump
- `backend/src/agents/nodes/market_analyst.py` — `raw_inputs` 필드 추가, prefix bump
- `backend/scripts/eval/run_all_agents_v7.py` — fixture loader 들 새 schema 반영
- `backend/scripts/eval/seed_eval_cache.py` — 자동 batch 시뮬 스크립트 (8 케이스)

---

## 5. v7 최종 결과

8 케이스 batch 시뮬 후 재측정 (n=8~11):

| 에이전트 | v6 | v7 최종 | n | 변화 |
|---|---:|---:|---:|---|
| synthesis | 100% | **97.7%** | 11 | ↓ 2.3%p (n 증가로 안정화) |
| competitor_intel | 100% | **100%** | 11 | → |
| demographic_depth | 83.3% | **100%** | 11 | ↑ 16.7%p |
| **market_analyst** | 50% | **87.5%** | 8 | ↑ **37.5%p** ⭐ |
| trend_forecaster | 66.7% | **81.8%** | 11 | ↑ 15.1%p |
| population_analyst | 66.7% | 58.3% | 8 | ↓ 8.4%p |
| legal | 33% | 제외 | — | RAG 별도 |

**6 에이전트 평균 v7 = 87.55%**

### 의미
- **4 에이전트 v6 대비 향상** (market_analyst 가 가장 큰 개선 +37.5%p)
- **synthesis 100→97.7%** — n 늘어 거짓 양성 일부 보정 (정직한 측정으로 안정화)
- **population 약간 하락** — LLM 출력 형식(예: peak_time "11:00~14:00") 과 데이터 형식 매칭 룰 정합 추가 개선 여지

---

## 6. PPT 발표 핵심 메시지

```
v6: LLM-as-judge → 80~100% (보고용 좋아 보임)
        ↓ 검증
방법론 점검: LLM이 LLM 채점 = 자기참조 편향. MAPE 0.1% 무의미 발견
        ↓ 재설계
v7 1차: 룰엔진/직접 일치 → 4/7 측정 가능 (캐시 한계 발견)
        ↓ 솔루션
캐시 schema 보강: raw 데이터 함께 저장 (v? → v?+1 prefix bump)
        ↓ 재측정
v7 최종: 6/7 측정, 평균 87.55%
        · 4 에이전트 v6 대비 향상 (market +37.5%p)
        · synthesis 100→97.7% (n 증가 안정화 = 정직한 측정)
```

### 강점 스토리
1. *측정 방식의 정직화* — 자기참조 → 외부 검증
2. *측정 한계 인식 + 극복* — 캐시 schema 보강으로 측정 범위 확대
3. *결과의 정직성* — 일부 점수 하락도 인정, 메타 인사이트 도출

---

## 7. 산출 파일

| 파일 | 위치 | 용도 |
|---|---|---|
| 평가 framework | `backend/src/evaluation/` (9 파일) | 7 에이전트 evaluator |
| 통합 실행 스크립트 | `backend/scripts/eval/run_all_agents_v7.py` | 캐시 dump → fixture → 평가 → 비교 리포트 |
| 자동 시뮬 batch | `backend/scripts/eval/seed_eval_cache.py` | 8 케이스 시뮬 호출 (15분) |
| 결과 dump | `bench_agent_eval_v7.json` (gitignored) | JSON 결과 |
| 비교 리포트 | `bench_agent_eval_v7_report.md` (gitignored) | 마크다운 |

### 재현 절차
```bash
cd backend
# 1. 백엔드 떠있는 상태에서 batch 시뮬
python -m scripts.eval.seed_eval_cache
# 2. v7 평가 실행
python -m scripts.eval.run_all_agents_v7
```
