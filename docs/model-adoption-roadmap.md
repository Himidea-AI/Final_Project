# 유사 LLM-ABM 모델로부터 차용 가능 패턴 적용 로드맵

작성: A1 (찬영) — 2026-04-21
분석 대상: AgentSociety, OASIS, GATSim, Chiu Taipei, MobilityGen, Imagery2Flow
관련 문서: `sim-comparison-matrix.md`, `sim-validation-progression.md`

> **목적**: 5개 최신 LLM-ABM 모델의 GitHub 레포·논문을 깊이 분석한 결과에서 우리 v14 ABM에 **실제 이식 가능한 10개 패턴**을 도출하고 우선순위로 정렬.

---

## 1. 요약 — 10개 패턴 우선순위 매트릭스 (냉정 평가 후)

> **2026-04-21 code-reviewer subagent 냉정 평가**에 따라 대부분 강등. 10개 중 🟢 0개, 🟡 2개, 🔴 8개. **발표용으로 실제 가치 있는 건 "Huff 재설계 1개 + Polarization 1개"뿐**.

| # | 패턴 | 최초 등급 | **재평가** | 이유 |
|---|---|---|---|---|
| 1 | **Huff Attractiveness Term** | ⭐⭐⭐ | 🟡 **조건부** | 현재 코드 스니펫은 단순 popularity rename. 진짜 Huff는 `attr/distance^β` 분모가 본질. 재설계 필요 (2~3일) |
| 2 | **LLM-as-judge** | ⭐⭐⭐ | 🔴 **Circular** | 생성/판정 모두 GPT-4o-mini → 심사 즉각 지적 |
| 3 | **Co-presence + Zipf** | ⭐⭐ | 🔴 **표본 부족** | 1000 에이전트로 power-law 방어 불가 |
| 4 | **CPC 메트릭** | ⭐⭐ | 🔴 **도메인 오인용** | OD commuting 지표, 매장 방문 시뮬에 부적합 |
| 5 | **IPF 인구 보정** | ⭐⭐ | 🔴 **Redundant** | v14 이미 통계청 marginal 정합 |
| 6 | **StreamMemory (recency)** | ⭐ | 🟡 **약한 효과** | 안전하나 signal 거의 안 나올 것 |
| 7 | **Dong Attractiveness Prior** | ⭐ | 🔴 **3겹 중복** | `popularity_boost`·`dong_affinity`·`time_age_boost` 이미 존재 |
| 8 | **Polarization Metric** | ⭐ | 🟡 **안전, 2h** | 발표 지표 +1, 리스크 없음 |
| 9 | DDPM Trajectory Refinement | ❌ | 🔴 유지 | GPU 필요 |
| 10 | Multi-Scale Reflection | ❌ | 🔴 유지 | 비용 폭발 |

**발표 전 현실적 Top 2**: ① **Huff 제대로 재설계** (2~3일) ② **Polarization metric** (2h)
**나머지 시간**: regression test 인프라 + v14 재현 스크립트 구축 (디버깅 지옥 방지)

---

## 2. 모델별 상세 분석

### 2.1 AgentSociety (Piao et al. 2025) — 10K LLM 에이전트

- **Repo**: https://github.com/tsinghua-fib-lab/AgentSociety
- **arXiv**: https://arxiv.org/abs/2502.08691
- **Docs**: https://agentsociety.readthedocs.io/

**핵심 추상화**
- `CitizenAgent` — 집·직장·개인속성, status memory 기반 행동
- `StreamMemory` — Event/Perception Flow, 감정·인지 피드백 폐루프
- Multi-head workflow: Perception → Emotion/Cognition → Action → Feedback → Memory update
- `ExpConfig.SimulatorConfig` — `steps_per_simulation_day`, `steps_per_simulation_step` YAML 제어
- Polarization use case — 극단화 `extremism_shift_ratio` 지표

**차용 가능**
- ✅ **StreamMemory 경량판** — `deque(maxlen=7)` 최근 7일 방문 이력 → `recency_bonus`
- ✅ **Polarization metric** — 시나리오 전후 선택 분포의 극단화 비율
- ❌ **Multi-head LLM loop** — 비용 $100+/일, 우리 철학과 반대

---

### 2.2 OASIS (Yang 2024) — 1M 에이전트 [이전 분석 재확인]

- **Repo**: https://github.com/camel-ai/oasis
- **arXiv**: https://arxiv.org/abs/2411.11581

**핵심 추상화**
- `Channel` (asyncio.Queue + AsyncSafeDict) — agent↔state 분리
- `Platform.running()` — 단일 consumer 리플렉션 디스패치
- `asyncio.Semaphore(128) + gather` — fan-out 병렬 실행

**차용 가능** (이미 adoption-plan에 포함)
- ✅ Channel + Semaphore 패턴 (아직 미구현, 필요시 추후)

---

### 2.3 GATSim (Liu, Li, Ma 2025) — 생성 교통 ABM

- **Repo**: https://github.com/qiliuchn/gatsim (Apache 2.0)
- **arXiv HTML**: https://arxiv.org/html/2506.23306v3

**핵심 추상화**
- `ConceptNode {text, embedding, keywords, spatial_coverage, temporal_scope, importance, access_history}`
- Multi-modal retrieval — keyword + semantic + spatio-temporal
- Multi-Scale Reflection — Immediate / Daily / Long-term (3계층)
- **LLM-as-judge 검증** — GPT-o1 판정, 순서 random permute, binomial test
  - 결과: 50 시나리오 중 agent 23승·human 20승·7무 → posterior 92% agent ≥ human

**차용 가능**
- ✅ **LLM-as-judge** — `backend/tests/simulation/test_llm_judge.py` 신규
- ✅ **ConceptNode spatio-temporal retrieval (경량판)** — 프롬프트에 과거 정책 성과 요약 주입
- ❌ **Embedding 기반 retrieval full** — 벡터 DB 인프라 비용
- ❌ **Multi-Scale Reflection** — Immediate/Long-term은 LLM 반복 호출

---

### 2.4 Chiu et al. (2025) — LLM + 대도시 Mobility

- **arXiv**: https://arxiv.org/abs/2505.21880
- **PDF**: https://arxiv.org/pdf/2505.21880

**핵심 알고리즘**
1. **IPF 합성 인구 보정** — LLM 생성 인구의 marginal을 실측(통계청)에 강제 일치
2. **Modified Huff model** — `P(loc_j) ∝ attractiveness_j / distance_ij^β`
3. **Semantic similarity POI matching** — LLM 활동 토큰 ↔ POI 카테고리 임베딩

**차용 가능**
- ✅ **Huff attractiveness term** — `score_store` 곱항 추가 (popularity × rating 기반)
- ✅ **IPF calibrator** — `backend/src/services/ipf_calibrator.py` 신규
- ❌ **LLM 프로파일 재생성** — 비용 과다

---

### 2.5 MobilityGen (Wang/Hong et al. 2025) — Deep Generative

- **Repo**: https://github.com/mie-lab/mobility_generation
- **arXiv**: https://arxiv.org/abs/2510.06473

**핵심 알고리즘**
1. **DDPM + Transformer** 이벤트 시퀀스 생성
2. **Shared latent multi-attribute embedding** — mode/time/loc 공동 학습
3. **Co-presence / segregation metric** — (hour, dong) 공존율 P-value 검증

**차용 가능**
- ✅ **Co-presence KL/JSD 메트릭** — `validate_simulation.py`에 함수 1개
- ✅ **Scaling law check** — Zipf 기울기 (log-log) 검증
- ❌ **DDPM refinement full** — GPU + 대량 trajectory 학습 필요

---

### 2.6 Imagery2Flow (Rong et al. 2025) — Nature Commun.

- **Repo**: https://github.com/GeoDS/Imagery2Flow
- **Paper**: https://www.nature.com/articles/s41467-025-65373-z

**핵심 알고리즘**
1. **Bilinear OD decoder** — `flow_ij = h_i^T W h_j`
2. **GAT (Graph Attention Network)** — census-tract 이웃 aggregation
3. **Cross-city generalization** — 도시 A 학습 → 도시 B 예측
4. **CPC (Common Part of Commuters)** 메트릭 — OD flow 표준

**차용 가능**
- ✅ **CPC 메트릭** — `validate_simulation.py` (OD flow 지표)
- ✅ **Dong attractiveness prior** — 위성영상 embedding 사전 학습 → CSV 로드
- ❌ **GAT full 학습** — 위성영상 파이프라인 + GPU

---

## 3. 실구현 Top 2 (냉정 평가 후 축소)

### 3.1 Huff 제대로 재설계 (조건부 채택)

**중요**: 내 원안 "popularity_boost * (1 + rating/5.0)"은 단순 **rename** — 진짜 Huff가 아님.

**진짜 Huff 모델** (Chiu 2025 §3.2 참고):
```python
# 현재 score_store 내부
# + popularity * 0.3    ← 제거
# + viral_boost          ← 제거
# Chiu 스타일로 대체:
distance_km = _store_distance_km(None, None, store)
beta = 1.5  # 거리 감쇄 지수 (문헌 표준)
huff_term = attractiveness / (1.0 + distance_km) ** beta
# score 식에 + huff_term * 0.5로 편입
```

**재설계 절차**:
1. 현재 v14 결과 백업 (`sim_policy_v14_n1000.json`)
2. `score_store` 변경 → regression test로 RMSE/KL/상관 재측정
3. 지표 개선 없으면 롤백

**예상 비용**: 2~3일 (주장 "2줄"은 순진함 인정)
**리스크**: v14 지표(RMSE 5.1%, KL 0.077, 상관 0.64) 중 하나는 흔들릴 가능성

### 3.2 Polarization Metric (안전, 2h)

**파일**: `scripts/validate_simulation.py` 에 함수 1개 추가

```python
def validate_polarization(traj_baseline: list, traj_shock: list) -> dict:
    """시나리오 전후 동별 선택 분포의 극단화 변화율.

    baseline: 기본 시뮬
    shock: 예) 임대료 +30% 시나리오
    반환: 동별 분포의 극단화 shift_ratio (0~1)
    """
    from collections import Counter
    b_dist = Counter(p["dong"] for p in traj_baseline if p.get("action") == "visit")
    s_dist = Counter(p["dong"] for p in traj_shock if p.get("action") == "visit")
    # Gini coefficient 또는 Herfindahl index 차이로 계산
    ...
    return {"baseline_gini": ..., "shock_gini": ..., "polarization_delta": ...}
```

**발표 임팩트**: 리스크 없이 지표 +1, 차트 1장 추가

---

## 3.3 배제 항목 (냉정 평가 결과)

| # | 배제 이유 |
|---|---|
| 2 LLM-judge | 생성자와 판정자 동일 LLM = circular, 심사위원 첫 질문감. 판정자를 Claude/Gemini로 바꾸면 1일 추가 → ROI 나쁨 |
| 3 Co-presence + Zipf | 1000 에이전트 × 17동 × 24시 = 408 버킷. Power-law 검증에 heavy tail 표본 부족 |
| 4 CPC | OD commuting flow 지표. 매장 방문 시뮬에 억지 적용 시 첫 질문에 무너짐 |
| 5 IPF | v14 이미 통계청 marginal 정합. 중복 |
| 7 Dong attractiveness prior | `popularity_boost`·`dong_affinity`·`time_age_boost` 3겹 중복 |

---

## 3.4 Regression Test 인프라 (리뷰어 최강 권고)

> *"나머지 시간은 regression test 인프라와 v14 결과 재현 스크립트 구축에 써야 발표 당일 디버깅 지옥을 피함."*

**신규 파일**: `scripts/regression_test_v14.py`

```python
"""v14 baseline 지표 회귀 테스트.

매번 score_store 수정 후 이 스크립트로 검증:
  - RMSE 5.1% ± 0.3%
  - Pearson 0.64 ± 0.05
  - 버스 상관 0.66 ± 0.05
  - 카테고리 KL 0.077 ± 0.02
  - External 귀환 92% ± 3%
  - total_visits 4000 ± 500

하나라도 벗어나면 경고 출력.
"""
```

**가치**: 발표 직전 갑자기 지표 깨짐 사고 예방. Huff 재설계 시도 시 필수.

---

## 4. 냉정한 적용 가능성 평가 (다음 단계)

이 문서 작성 후 **code-reviewer subagent**로 재검토하여 각 패턴의:
1. 실제 우리 코드와의 호환성
2. 예상 효과의 과대평가 여부
3. 구현 complexity 대비 ROI
4. 논문 인용 시 정확성

을 **냉정하게** 평가한다.

---

## 5. 최종 판단 기준

- 🟢 **확정 채택**: 명확한 수치 개선 + 0.5일 내 구현 + 발표 설득력
- 🟡 **조건부 채택**: 효과 불확실하나 시도 가치 있음
- 🔴 **배제**: 비용/시간 ROI 낮거나 우리 도메인과 불일치

**사전 예측**:
- #1 Huff: 🟢 (코드 2줄)
- #2 LLM-judge: 🟢 (발표 임팩트 명확)
- #3 Co-presence: 🟡 (효과 미지수, 3시간 투자)
- #4~#10: 대부분 🟡 또는 🔴

코드 리뷰 후 이 예측이 맞는지 재검증.
