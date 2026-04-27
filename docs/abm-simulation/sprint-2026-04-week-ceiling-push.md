# 1주 Sprint — ABM 천장 Push (0.79 → 0.85~0.92 목표)

작성: A1 (찬영) — 2026-04-27
브랜치: `IM3-243-dong-fk-followup` (또는 신규 sprint 브랜치)
목표: Pearson r 0.79 ± 0.005 → **0.85+** (PSE 검증)
관련: `sim-mode-matrix.md` §2.5 Harness, `2026-04-26-abm-product-iteration.md` §12

---

## 배경 — 왜 1주 sprint?

지난 sprint (2026-04-26~27) Phase 5/7/8/9/10 모두 실패:
- 단순 데이터 추가 / scale-up / 검증 metric 변경 = noise
- ABM 모델 자체의 본질 한계 (visit flow vs KT stock)
- weekday 차별화 약함, 새벽 trajectory 누락

→ **종합적 ABM 모델 확장 + 5K scale + 자동 calibration** 필요. 1주 단위 sprint.

---

## Sprint 규칙 (Harness)

1. **PSE N=5 표준** — 단일 seed 측정 금지
2. **Δ > 합산 CI 폭** 만 개선 인정
3. **실패 시 즉시 revert** (Phase 5 사례)
4. **각 Phase 끝 commit + 문서**
5. **천장 측정**: 매 Phase 결과 sim-mode-matrix.md 추가

---

## Phase 별 계획 (7 단계)

### Phase A — ABM Weekday 차별화 강화 (Day 1)
**가설**: adstrd_flpop_boost 가 mon~sun 차별 보유하나 score_store 에서 약하게 적용됨. 더 강한 weekday boost 적용 시 Phase 10 (요일+시간+동) Pearson 회복 가능.

**작업**:
- `policy_executor.score_store` 에 weekday boost 강화 (현 0.9+0.1 → 0.7+0.3 시도)
- DONG_CHARACTER 에 weekday/weekend cat_boost 변형 추가
- PSE N=5 + Phase 10 metric (요일+시간+동) 검증

**기준**: Δ > +0.02 면 adopt

### Phase B — 5K agent + 새벽 trajectory 동시 (Day 2)
**가설**: Phase 5 (새벽 추가) + Phase 7 (5K) 단독은 실패. 동시 적용 시 sample size 충족 → 새벽 추가 효과 발현.

**작업**:
- `n_personas=5000`, `PopulationMix(residents=2000, ...)`
- runner.py 의 새벽 home stay 로직 재활성화
- PSE N=3 (시간 절약, 5K × 5 seed = 25 sims)

**기준**: Δ > +0.03 면 adopt

### Phase C — Commute / Work trajectory 명시화 (Day 3)
**가설**: KT 데이터 잡는 "직장 체류 ~30%" 가 ABM trajectory 누락. ext_commuter 가 work_dong 에서 8h 머무는 trajectory 명시 추가.

**작업**:
- runner.py 매 hour trajectory append 시 ext_commuter 의 9~17h 위치 = work_dong (마포 내) 명시
- agent 에 work_dong 추가 (이미 있는지 확인)
- PSE N=3

**기준**: Δ > +0.03 면 adopt

### Phase D — 행동 확장 (Day 4)
**가설**: 우리 ABM 4 카테고리 (카페/음식점/주점/편의점) 외 ~10% 활동 누락. "shop", "exercise", "errand" 비-매장 행동 추가.

**작업**:
- agents.py decide() 에 5번째~7번째 action 추가
- 비-매장 행동도 trajectory 에 동 entry 생성
- PSE N=3

**기준**: Δ > +0.02 면 adopt

### Phase E — GA Hyperparameter Calibration (Day 5)
**가설**: 핵심 3 hyperparameter (time_boost, flpop_boost, OFS) 자동 sweep 시 +0.02~0.05.

**작업**:
- scipy.optimize.differential_evolution
- 3 hp × 5 sample × 5 seed = 75 sims (~1h)
- 최고 Pearson 조합 채택

**기준**: Δ > +0.02 면 adopt

### Phase F — Trajectory cell matching (Day 6, optional)
**가설**: 동 단위 → cell 단위 비교로 +0.02~0.05.

**작업**:
- KT cell 좌표 → 매장/agent 좌표 매핑
- cell 단위 PSE
- 큰 리팩터 — 시간 부족하면 skip

**기준**: Δ > +0.02 면 adopt

### Day 7 — 통합 + 최종 측정
- 채택된 모든 Phase 통합 (revert된 것 제외)
- 최종 PSE N=5 측정
- sim-mode-matrix.md / retrospective 업데이트
- PR → dev 머지

---

## 예상 결과 시나리오

| Phase | 채택 가능성 | 누적 Pearson |
|---|---|---|
| 시작 | — | 0.79 ± 0.005 |
| A 채택 | 60% | 0.81~0.82 |
| B 채택 | 50% | 0.83~0.85 |
| C 채택 | 70% | 0.85~0.88 |
| D 채택 | 40% | 0.86~0.89 |
| E 채택 | 60% | 0.88~0.91 |
| F 채택 | 30% | 0.90~0.93 |

**현실적 종합 결과**: **Pearson 0.85 ± 0.02** (PSE 검증, 신뢰구간 포함).

학술 천장 0.96 진행률: 37% → **60%~75%**.

---

## 위험 / 한계 명시

1. **모든 Phase 가 noise일 가능성** — 지난 sprint 5 phases 모두 실패
2. **Stock vs Flow 본질 차이** 는 어떤 작업으로도 0.96 도달 못 함
3. **Calibration 시간 비용** — GA 100 trials 시 수 시간
4. **모델 변경 위험** — ABM v12 baseline 깨질 가능성, 각 Phase revert 가능해야

---

## Phase별 측정 표 (실시간 갱신)

| Phase | 변경 | Pearson | Δ | 판정 | 비고 |
|---|---|---|---|---|---|
| Start | (current main) | 0.79 ± 0.005 | — | baseline | 3K agent, real 3m |
| A | weekday 강화 | TBD | TBD | TBD | TBD |
| B | 5K + 새벽 | TBD | TBD | TBD | TBD |
| C | commute trajectory | TBD | TBD | TBD | TBD |
| D | 행동 확장 | TBD | TBD | TBD | TBD |
| E | GA calibration | TBD | TBD | TBD | TBD |
| F | cell matching | TBD | TBD | TBD | TBD |
| Final | 통합 | TBD | TBD | TBD | TBD |

---

## 학술 인용 추가 후보

- Cervero (2002) — weekday/weekend mode choice
- Brussels ABM (Tandfonline 2024) — calibration with cellphone data
- McGrail-Humphreys (2009) — 2SFCA cap function
- Sommet & Lipps (2025) — Fixed-effects panel modeling for ABM

---

## 변경 로그

| 날짜 | 추가/변경 |
|---|---|
| 2026-04-27 | 초기 sprint plan |
| TBD | Phase A 결과 |
| TBD | Phase B 결과 |
| TBD | ... |
| TBD | 통합 + 최종 |
