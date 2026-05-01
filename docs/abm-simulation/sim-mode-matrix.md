# ABM 모드별 테스트 매트릭스

> **🚨 2026-04-27 정정 banner**: 본 문서의 모든 Pearson r 측정값 (0.7445, 0.7491,
> 0.7539, 0.7930, 0.8051, 0.8099) 은 **재현 안 됨**. 같은 config (1K agent, mock,
> Q1 평균) 으로 측정 시 raw Pearson 은 **0.291 ± 0.037** (PSE N=3, 2026-04-27 실측).
> 이전 측정값들이 어떤 aggregation 으로 산출됐는지 추적 불가.
>
> 다만 같은 측정 framework 안에서의 **상대 비교** 는 유효. 그리고 `ceiling-analysis.md`
> §0~7-A 에 따라 IPF marginal calibration 으로 0.849 도달 입증 (천장 push 성공).
>
> 이 문서의 §2.1~2.6 표는 *historical* 으로 보존하되, baseline 결정 시 신뢰 X.
> 진짜 baseline + Phase H/I/J/K/L 결과는 `validation/results/phase_full_pse3_summary.json` 참조.

작성: A1 (찬영) — 2026-04-26
목적: ABM v12+ 모드 조합별 정확도/비용/시간 종합 매트릭스. 발표·심사·운영 결정 레퍼런스.
관련: `sim-comparison-matrix.md` (v1~v14 진화), `sim-real-gap-analysis.md` (단위 mismatch)

> **이 문서는 "어떤 LLM provider + 어떤 데이터 레이어 조합이 최적인가" 를 실측 비교한 매트릭스입니다.**
> 기존 `sim-comparison-matrix.md` 가 버전 진화 (v1→v14, OpenAI 전제) 라면, 본 문서는 **현재 v12 baseline 의 mode 토글 비교**입니다.

---

## 1. 모드 정의

### 1.1 LLM Provider × Tier 모드 (3종)

| 모드 | Tier S (50명) | Tier A (200명) | Tier B (750명) | LLM 호출 | 의사결정 |
|---|---|---|---|---|---|
| **Full Mock** | mock | mock | python (Policy) | 0회 | 모두 deterministic |
| **Hybrid (Policy)** | (skip) | (skip) | python (Policy) | 0회 | `use_policy=True` — Tier S/A 우회 |
| **Full LLM** | OpenAI gpt-4o-mini | OpenAI gpt-4o-mini | python (Policy) | ~2,500회 | Tier S/A 자연어 의사결정 |

> Tier B (750명) 는 모든 모드에서 Policy 기반 — Python 결정. 비용·속도 안정성의 핵심.

### 1.2 데이터 레이어 토글 (4종)

| 레이어 | 데이터 출처 | 영향 차원 |
|---|---|---|
| `nemotron` | NVIDIA Nemotron-Personas-Korea (7,187 마포 페르소나) | AgentProfile 인구통계 + 자연어 서사 |
| `adstrd_flpop` | `seoul_adstrd_flpop` (16동 × 시간6 × 요일7, 분기 안정) | score_store 동×시간×요일 boost |
| `ofs` | `seoul_adstrd_fclty` 14종 시설 + Hansen+E2SFCA (미적용) | World.ofs_dong_score, ext_visitor 차등 |
| `hotspots` | `seoul_realtime_hotspots` (4 POI 실시간) | popularity_boost 동적화 (미적용) |

---

## 2. 측정 결과 — 시나리오 매트릭스

검증 대상: `living_population_grid` 2026-02-15 (마포 16동 × 24h)
공통 조건: `seed=42`, `days=1`, `use_rds=True`, `use_profiles=True`, `seed_memory=True`, `memory_seed_days=14`

### 2.1 핵심 비교 (5종)

### 2.1 단일 seed 측정 (N=1, ⚠️ noise 가능성 — §2.3 참조)

| # | 모드 | n_agents | Nemotron | adstrd_flpop | OFS | Pearson r | Spearman ρ | MAPE | Peak | 비용 | 시간 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Full Mock | 1,000 | ❌ | ❌ | ❌ | +0.7445 | +0.4407 | 49.0% | 19% (3/16) | $0.001 | 53s |
| 2 | Full Mock | 1,000 | ✅ | ❌ | ❌ | +0.7540 | +0.4416 | 48.0% | 12% (2/16) | $0.001 | 55s |
| 3 | Full LLM | 200 | ✅ | ❌ | ❌ | +0.7288 | +0.1953 | 56.4% | 0% (0/16) | $0.05 | 161s |
| 4 | Full LLM | 1,000 | ✅ | ❌ | ❌ | +0.7641 | +0.2699 | 55.9% | 0% (0/16) | $0.25 | 551s |
| 5 | Full Mock | 1,000 | ✅ | ✅ (0.8/0.2) | ❌ | +0.7515 | +0.4250 | 48.3% | 19% (3/16) | $0.001 | 55s |
| 6 | Full Mock | 1,000 | ✅ | ✅ (0.9/0.1) | ❌ | +0.7539 | +0.4236 | 47.4% | 19% (3/16) | $0.001 | 55s |

### 2.2 PSE N=5 검증 측정 (Paired Seed Evaluation, 2026-04-26)

**검증된 측정값** — seeds [42, 123, 7777, 99, 2024] 평균. 95% CI = 1.96 × SEM.

| 시나리오 | Pearson r | Spearman ρ | MAPE | Peak hour |
|---|---|---|---|---|
| **A: Mock+Nemotron+flpop (현재 main)** | **0.7491 ± 0.0155** | 0.3998 ± 0.0584 | 44.89 ± 1.73% | **12.5 ± 0%** |
| **B: Mock+flpop만 (Nemotron OFF)** | 0.7415 ± 0.0044 | 0.4056 ± 0.0318 | 46.63 ± 3.37% | 13.75 ± 2.45% |
| **A − B (Nemotron 효과)** | +0.0076 | -0.0058 | -1.74%p | -1.25%p |
| **통계적 유의** | ❌ noise | ❌ noise | ❌ noise | ❌ noise |

→ **현재 main vs Nemotron OFF 모든 metric 차이가 95% CI 안에 묻힘**. Nemotron 통합은 baseline metric을 통계적으로 개선하지 못함 (단, 자연어 페르소나·face validity 가치는 별개).

### 2.3 단일 seed 측정의 함정 — Springer 2025 비판 일치

§2.1 의 단일 seed 측정값 비교는 **모두 NOISE 안에 묻혀 있을 가능성** 있음:

| §2.1 비교 | Δ Pearson | PSE CI 폭 | 진짜인가? |
|---|---|---|---|
| #1 → #2 (Nemotron 추가) | +0.0095 | ±0.016 | ❌ noise |
| #2 → #6 (adstrd_flpop 추가) | -0.0001 | ±0.016 | ❌ noise |
| #2 → #4 (LLM 1000ag) | +0.0101 | ±0.016 | ❌ noise (단, 다른 noise 분포) |
| #5 → #6 (강도 0.8→0.9) | +0.0024 | ±0.016 | ❌ noise |

**Springer 2025 *"Validation is the central challenge"* 비판이 정확히 우리에게 적용**:
> "objective metrics 안 쓰면 stochastic noise가 진짜 효과처럼 보인다"

### 2.4 지표별 우승 시나리오 (PSE 기준)

| 지표 | 1위 (검증된 값) | 비고 |
|---|---|---|
| Pearson r (안정성) | A 0.7491 ± 0.0155 | B 와 noise 차이 |
| MAPE (안정성) | A 44.89 ± 1.73% | B 와 noise 차이 |
| Peak hour (안정성) | **A 12.5 ± 0%** | 5/5 동일 — 가장 reproducible |
| 비용/성능 효율 | A | $0.001 |
| 시간/처리 효율 | A | ~55s/run |

→ §2.1 의 "19% Peak" 는 outlier (단일 seed). PSE 기준 진짜 baseline은 **12.5%**.

### 2.5 Harness Engineering — Iterative Improvement (2026-04-26)

규칙: PSE N=5 표준, Δ > CI width 만 개선 인정, 실패 시 revert, null baseline 우선.

**Phase 0 — Floor 측정 (반드시 우리 ABM 정당성 입증부터)**

| 모델 | Pearson r | 우리 ABM 대비 | 가치 |
|---|---|---|---|
| **Random walk** (모든 매장 균등) | **0.6922 ± 0.0117** | -0.057 | floor (null hypothesis) |
| Hansen gravity (popularity/d²) | 0.3685 ± 0.0259 | -0.380 | (구현 단순화로 floor 미만) |
| **우리 ABM** (현재 main) | **0.7491 ± 0.0155** | — | **null 대비 +0.057 통계적 유의** |

→ 우리 1000줄 ABM 복잡도가 단순 random 대비 **+5.7% Pearson** 의 진짜 가치 추가.
   floor → ceiling 진행률: 약 21% (학술 천장 0.96 가정).

**Phase 1 — Unit Alignment 가설 (district_sales 매출 비교)** ❌

| 검증 metric | Pearson r | Spearman ρ | MAPE | 판정 |
|---|---|---|---|---|
| vs living_pop_grid | 0.7491 ± 0.0155 | 0.3998 ± 0.0584 | 44.89 ± 1.73% | control |
| vs district_sales | 0.7598 ± 0.0412 | 0.2466 ± 0.0679 | **175.43 ± 16.75%** | ❌ revert |

→ Pearson 동일 (CI 겹침), MAPE 폭발 (절대 스케일 mismatch).
   "단위만 맞추면 r=0.9" 가설 부분 기각.

**Phase 2/3 — Real Data Multi-Period Averaging** ✅

검증 데이터 noise 흡수 — 우리 ABM 그대로, 비교 대상만 평균.

| 검증 real | Pearson r | Spearman ρ | MAPE | Δ vs control |
|---|---|---|---|---|
| 단일 날짜 02-15 | 0.7491 ± 0.0155 | 0.3998 ± 0.0584 | 44.89 ± 1.73% | — |
| **30일 평균 (2026-02)** | **0.8051 ± ~0.018** | 0.4597 ± ? | 40.95 ± ? | **+0.056** ✅ |
| **3개월 평균 (2026-Q1)** | **0.8099 ± 0.0169** | **0.4809 ± 0.0536** | **39.35 ± 2.21%** | **+0.061** ✅ |

→ **단순 검증 데이터 평균만으로 +0.06 Pearson**. 코드 변경 0.
   30일 → 3개월 marginal (+0.005). 30일 saturation.

**Phase 4 — ABM Multi-Day (양쪽 평균)** ❌

| 비교 | Pearson r | 판정 |
|---|---|---|
| ABM 1d vs real 3m (P3a) | 0.8099 ± 0.0169 | best |
| ABM 7d vs real 3m (P4) | ~0.8063 (4-seed) | ❌ noise |

→ PSE N=5 가 이미 ABM noise 흡수 → ABM days 늘려도 효과 없음.

### 2.6 Harness 결과 — 진짜 baseline 갱신

**Phase 0~4 (1K agent) 시점**:
```
시작 (이전 baseline):    Pearson 0.7491 (1K, single-day)
Phase 0~4 완료:          Pearson 0.8099 (1K, real 3-month avg, 1-seed)
가치 추가:                +0.0608 (통계적 유의, CI ±0.017)
floor 대비 진행:          +0.1177 (random walk 0.6922)
```

**Phase 7 (3K agent + PSE N=3, 진짜 baseline 정정)**:
```
3K agent baseline:       Pearson 0.7930 ± 0.005 (PSE 검증, CI 70% 감소)
학술 천장 진행률:         37% (학술 0.96, floor 0.69 기준)
```

→ 1K + 1-seed 측정의 0.81 은 sample noise 포함. 3K + PSE N=3 의 0.79 ± 0.005
가 더 정확한 baseline. 천장 push 한계 분석은 `ceiling-analysis.md` 참조.

**검증 권장 표준** (이후 모든 측정):
- ABM: 3K agent × 1d × PSE N=3 (또는 1K × N=5)
- Real: 3개월 평균 (`ymd BETWEEN '2026-Q1 시작' AND '2026-Q1 끝'`)
- 진짜 v12 baseline: **Pearson r 0.79 ± 0.005**

---

## 3. 핵심 발견 — 비판적 해석

### 3.1 LLM 모드의 양면성

**Full LLM (#4) 이 Pearson r 최고치 (+0.7641)** 를 달성했지만:
- Spearman ρ 0.44 → 0.27 **급락** (순위 상관 약화)
- MAPE 48% → 56% **악화** (절대 크기 오차 증가)
- Peak hour 0% (모든 동에서 잘못 예측)
- 비용 **250배** ($0.001 → $0.25)

**원인** (Springer 2025 *Validation is the central challenge* 비판과 일치):
- LLM 의 stochastic 의사결정이 동 순위 일관성을 깨뜨림
- agent 수 늘려도 (200 → 1,000) Spearman/MAPE 회복 안 됨 — LLM 의 본질적 noise

### 3.2 Nemotron 효과 (mock 환경)

| 비교 | Δ Pearson | Δ MAPE | Δ Peak |
|---|---|---|---|
| #1 → #2 (Nemotron 추가) | +0.0095 | -1.0%p | -7%p |

- 분포 fit 개선 (+0.01) but Peak 정확도 악화 (-7%p)
- Nemotron 자연어 페르소나가 mock 환경에서 활용 못 됨 — **Tier S 프롬프트에 자연어 주입되어야 진짜 효과** (현재 미연결)

### 3.3 adstrd_flpop 통합 효과

| 비교 | 강도 | Δ Pearson | Δ MAPE | Δ Peak |
|---|---|---|---|---|
| #2 → #5 | 0.8 + 0.2 | -0.0025 | +0.3%p | **+7%p** |
| #2 → #6 | 0.9 + 0.1 | -0.0001 | **-0.6%p** | **+7%p** |

**Sweet spot (#6, 0.9/0.1)**:
- ✅ Peak hour 12 → 19% (큰 약점 회복)
- ✅ MAPE 48.0 → 47.4% (-0.6%p)
- ✅ Pearson r 거의 무손실 (-0.0001)
- ⚠️ Spearman ρ 미세 손실 (-0.018, 분기 mismatch noise 추정)

→ **분기 안정 데이터의 보수적 적용이 안전**. 강하게 적용 (0.7+0.3) 시 noise 폭발 위험.

### 3.4 비용/성능 ROI 분석

| 시나리오 | 비용 | Pearson r | $/Pearson 단위 |
|---|---|---|---|
| #1 baseline | $0.001 | 0.7445 | $0.00134 |
| #2 +Nemotron | $0.001 | 0.7540 | $0.00133 |
| #6 +Nemotron+flpop | $0.001 | 0.7539 | $0.00133 |
| #4 Full LLM | $0.25 | 0.7641 | $0.327 |

**LLM 모드는 245× 비용 비효율**. baseline metric 개선용으로는 압도적으로 Mock+데이터 통합이 우위.

---

## 4. 운영 권장 가이드

### 4.1 시나리오별 모드 선택

| 사용 사례 | 권장 모드 | 근거 |
|---|---|---|
| **분포 fit 검증 / Pearson 측정** | **#6 Mock + Nemotron + flpop(0.9/0.1)** | 비용/성능 최적, Peak 회복 |
| **자연어 스토리 / B1 리포트** | #4 Full LLM 1000ag | 페르소나 다양성 + sample_stories |
| **24조합 매트릭스 검증** | #1 또는 #6 (Mock 기반) | 비용 무시 가능 |
| **빠른 반복 실험** | #1~#2 Mock | 55초/run |
| **공실 추천 평가** | #6 + vacancy_inject | 안정 + 빠름 |
| **발표 데모용** | #4 Full LLM small (200ag) | 자연어 narrative 가시성 |

### 4.2 모드 조합 안티패턴

- ❌ Full LLM × 단일 날짜 검증 — Spearman noise 너무 큼, 24조합 매트릭스 필요
- ❌ Full LLM × Peak hour 평가 — 0% 일관됨, mock 모드가 더 정확
- ❌ adstrd_flpop 강하게 적용 (0.7+0.3) — Pearson/Spearman 손실 큼
- ❌ Mock 단독 + Nemotron 미적용 — baseline 의 의미 없음 (#1보다 #2 항상 우위)

---

## 5. 학술 비교 — 우리 위치

자세한 학술 벤치마크 비교는 `sim-comparison-matrix.md` §3 참조.

| 비교 | 우리 (#6) | 학술 평균 | 평가 |
|---|---|---|---|
| Pearson r | 0.7539 | 0.5~0.9 | 중간 |
| Telecom-ABM peer (Brussels 2024) | — | 0.96 | 우리 못 미침 (단위 mismatch) |
| Park 2023 Generative Agents | — | (believability 평가) | 다른 방법론 |
| 객관적 metric 사용률 (Springer 2025 메타리뷰) | ✅ 5종 | 17/35 만 객관적 | **우위** |
| 비용 효율 | $0.001~0.25 | (보고 드묾) | **압도적** |

→ **"Mid-scale High-fidelity, 객관 metric + 비용 효율 차별화"** 포지셔닝 (sim-comparison-matrix.md 와 일치)

---

## 6. 향후 추가 측정 시나리오 (TODO)

| 우선순위 | 시나리오 | 예상 효과 | 작업 |
|---|---|---|---|
| 🔴 high | #6 + OFS scorer (seoul_adstrd_fclty 14종) | Pearson +0.01~0.03 | 3h |
| 🔴 high | 24조합 매트릭스 검증 (요일×날씨×계절) | 신뢰구간 산출 | 2h |
| 🟡 mid | #4 Full LLM × 7 days 평균 | LLM noise 흡수 가능성 검증 | $1.75 비용 |
| 🟡 mid | Hybrid (Policy + 부분 LLM Tier S만) | 비용/Pearson trade-off | 0.5h |
| 🟢 low | Anthropic Haiku 비교 | provider 차이 | $1+ 비용 |
| 🟢 low | n_personas 200/500/1000/2000 sweep | scale 효과 곡선 | 시간 |

---

## 7. 재현 가이드 (스크립트)

각 시나리오 재현용 코드는 `validation/abm_vs_grid.py` 변형. 권장 호출:

```bash
# #1 baseline (Mock + 정책)
python -m validation.abm_vs_grid --date 2026-02-15  # 기본값이 use_policy=True

# #6 Sweet spot (Nemotron + adstrd_flpop, 현 main 기본 동작)
# profile_builder.py 의 _attach_nemotron_features + load_adstrd_flpop_boost 자동 적용
# policy_executor.py 의 0.9 + 0.1 강도 적용
python -m validation.abm_vs_grid --date 2026-02-15

# #4 Full LLM
# 환경변수 OPENAI_API_KEY 필수, ANTHROPIC_API_KEY/GOOGLE_API_KEY unset
# cfg.tier_s_provider='openai', cfg.tier_a_provider='openai'
# use_policy=False
```

---

## 8. 변경 로그 (이 매트릭스의 변경 추적)

| 날짜 | 추가/변경 |
|---|---|
| 2026-04-26 | 초기 매트릭스 작성 — 6 시나리오 측정 (Mock × Nemotron × adstrd_flpop, OpenAI 200/1000) |
| 2026-04-26 | **§2.2 PSE N=5 검증 추가** — A vs B 비교, Nemotron 효과가 noise 안에 묻힘을 입증. 모든 단일 seed 측정값을 §2.1 로 강등 ("noise 가능성") |
| 2026-04-26 | §2.3 Springer 2025 비판 일치 사례 명시 |
| 2026-04-26 | **§2.5 Harness Engineering Phase 0~4 추가** — random/gravity floor 측정, real 3개월 평균으로 +0.06 Pearson 도약 (0.7491 → 0.8099). Phase 1 (unit alignment), Phase 4 (ABM multi-day) 는 noise 로 revert. |
| 2026-04-26 | §2.6 진짜 baseline 갱신 — ABM 1d × PSE N=5 vs real 3개월 평균 표준화 |
| 2026-04-26 | OFS scorer 통합 (`backend/src/services/operational_fit.py`) — Hansen+E2SFCA, 14종 시설 가중합. PSE N=5 검증: Δ Pearson noise (CI 겹침). 학술 정당화·ext_visitor 다양화 가치 별개. |
| TODO | §2.2 에 OpenAI N=5 평균 추가 ($1.25 비용) |
| 2026-04-27 | Phase 5 (새벽 home stay) ❌ revert (§12), Phase 6 (hyperparam) marginal, Phase 7 (3K agent) ✅ baseline 정정 (0.79 ± 0.005) |
| 2026-04-27 | Sprint Phase A (weekday boost), B (5K+새벽), C (24h time), G (KT trip) — 모두 실패. `sprint-2026-04-week-ceiling-push.md` |
| TODO | Trajectory-cell 단위 matching (큰 리팩터) — `ceiling-analysis.md` 의 진짜 천장 돌파 가설 |
