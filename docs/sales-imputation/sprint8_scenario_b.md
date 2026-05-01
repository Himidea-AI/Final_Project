# Sprint 8 — 시나리오 B 결과

**작성일:** 2026-04-27
**작업자:** 찬영 (A1) + Claude Code (Sonnet 4.6)
**시나리오:** B (합격선 spec 변경 X, 데이터/모델 개선만)

---

## 진단

### 디스크 공간

| 항목 | 값 |
|---|---|
| C: 가용 공간 | 17GB |
| checkpoints_v4 현재 | 8.1GB (n=100, depth=15, 6 seed) |
| 삭제 후 확보 가능 | 17 + 8.1 = 25.1GB |
| BEST_PARAMS (n=300, depth=35) 추정 필요량 | ~48GB (6× 현재) |
| **판정** | **불가 — 25.1GB < 48GB** |

> BEST_PARAMS 원본 (n_estimators=300, max_depth=35) 은 `reverse_engineer_sales_v4.py` 주석에
> "seed 당 ~7GB, 6 seed = 42GB" 로 기록되어 있다. 현재 확보 가능한 25.1GB 로는 실행 불가.

### 서울 데이터 (학습 path 비교)

`validation/results/learning_paths_comparison.csv` (Sprint 1 Task 4 결과):

| Path | MNAR WAPE | 비고 |
|---|---|---|
| mapo_only | 40.86% | 현재 채택 경로 |
| seoul_to_mapo | 40.86% | 차이 없음 |
| hybrid (마포 sw=5) | 40.93% | 오히려 미세 악화 |

> 서울 데이터 추가는 MNAR WAPE 에 도움이 되지 않음 (Sprint 1 결론 재확인).
> Hybrid path 재실행 불필요.

### KOSIS 추가 anchor 탐색

`scripts/probe_kosis_additional_anchors.py` 실행 결과 (`validation/results/sprint8_kosis_anchor_probe.csv`):

| Anchor | Pearson r | 비고 |
|---|---|---|
| DT_1KC2023 (기존, Sprint 1) | 0.9291 | 채택 기준선 |
| DT_1K41017 (음식점포함 소매판매액지수) | N/A | KOSIS API 연결 오류 (서버 측 강제 끊김) |
| DT_3KB9001 (시도/산업별 매출액) | N/A | 연간 데이터 — 분기 보간 필요, 기간 2개뿐 |

**판정:** 기존 anchor (r=0.9291) 유지. DT_1K41017 은 API 접근 실패, DT_3KB9001 은 연간 데이터로 분기 단위 비교 불가.

---

## 적용

| 시나리오 | 적용 여부 | 이유 |
|---|---|---|
| 2A BEST_PARAMS 복원 (n=300, depth=35) | **미적용** | 가용 25.1GB < 필요 48GB |
| 2B Hybrid path 재학습 | **미적용** | Sprint 1 결과 차이 없음 (40.86% vs 40.86%) |
| 2C KOSIS anchor 교체 | **미적용** | 신규 anchor r 계산 불가 또는 연간 데이터 |

> Sprint 8 에서 적용된 실제 코드 변경: `scripts/probe_kosis_additional_anchors.py` 신규 작성.

---

## 합격선 변화

Sprint 8 에서 모델 재학습을 수행하지 않았으므로 지표는 Sprint 7 과 동일.

| 합격선 | Sprint 7 | Sprint 8 | 변화 | 판정 |
|---|---|---|---|---|
| 0-1 KOSIS 분리 r | +0.0116 | +0.0116 | 0.0000 | FAIL (target +0.03) |
| 0-3 path 개선 | 0%p | 0%p | 0%p | FAIL (target -1.5%p) |
| 2-3 MNAR | 21.23% | 21.23% | 0.00p | FAIL (target ≤ 15%) |
| 2-4 LODO | 47.62% | 47.62% | 0.00p | FAIL (target ≤ 30%) |
| 2-5 Q1 | 21.14% | 21.14% | 0.00p | FAIL (target ≤ 18%) |
| 2-8 OoM | 96.71% | 96.71% | 0.00p | FAIL (target ≥ 97%) |
| 4-1 sensitivity | 0.70% | 0.70% | 0.00p | FAIL (target ≥ 8%) |
| 1-1 std/mean | 0.0746 | 0.0746 | 0.00 | PASS |
| 2-1 Random WAPE | 9.48% | 9.48% | 0.00p | PASS |
| 2-2 TS WAPE | 12.76% | 12.76% | 0.00p | PASS |
| 2-6 Pearson r | 0.9957 | 0.9957 | 0.0000 | PASS |
| 2-7 RMSLE | 0.3067 | 0.3067 | 0.0000 | PASS |
| 2-9 F1_4tier | 0.8697 | 0.8697 | 0.0000 | PASS |
| 2-10 MASE | 0.0849 | 0.0849 | 0.0000 | PASS |

---

## 100% PASS 달성 여부

**미달성.**

잔존 FAIL 7개 (Sprint 7 에서 변화 없음):

| # | 합격선 | 현재 | 목표 | 근본 원인 |
|---|---|---|---|---|
| 1 | 0-1 KOSIS r | +0.0116 | +0.03 | DT_1KC2023 분리 한계 |
| 2 | 0-3 path | 0%p | -1.5%p | 마포 고유 패턴 — 서울 전이 불가 |
| 3 | 2-3 MNAR | 21.23% | ≤ 15% | n=100, depth=15 용량 제한 (BEST_PARAMS n=300, depth=35 미복원) |
| 4 | 2-4 LODO | 47.62% | ≤ 30% | dong fixed-effect 과의존 (LOO 적용 시 오히려 악화 — Sprint 5 확인) |
| 5 | 2-5 Q1 | 21.14% | ≤ 18% | 소규모 셀 (store≤15) 본질적 고분산 |
| 6 | 2-8 OoM | 96.71% | ≥ 97% | n=100 예측 정밀도 한계 |
| 7 | 4-1 sensitivity | 0.70% | ≥ 8% | v4 결측 보강 32 조합 → ABM popularity 변화 미미 |

---

## 기술 분석: BEST_PARAMS 복원이 유일한 해법인 이유

Sprint 1~7 실험 결과 요약:

| 접근 | MNAR WAPE | 결과 |
|---|---|---|
| ExtraTrees n=300, depth=35 (FINAL_SUMMARY) | **13.35%** | PASS 가능 |
| ExtraTrees n=100, depth=15 (현재 v4) | 21.23% | FAIL |
| v5 LOO cross-fitting (Sprint 5) | 28.90% | 악화 |
| Seoul Transfer Learning | 58.67% | 대실패 |
| HyperImpute/TabPFN | 64%+ | 대실패 |

> **결론:** n=300, depth=35 로 복원하면 MNAR 13.35% ≤ 15% 합격 가능성 높음.
> 디스크 확보 (SSD 60GB+ 여유 확보) 가 Sprint 9 필수 사전 조건.

---

## Sprint 9 권장

### 우선순위 1: 디스크 확보 후 BEST_PARAMS 복원

```bash
# 외부 저장소 (USB/외장 SSD) 로 대용량 데이터 이동
# 예: data/raw/ (21GB), validation/results/checkpoints_v4/ (8.1GB)
# 이후 C: 60GB+ 확보

rm -rf validation/results/checkpoints_v4/   # 8.1GB 해제

# BEST_PARAMS 복원: reverse_engineer_sales_v4.py 수정
# n_estimators: 100 → 300
# max_depth: 15 → 35

python -m validation.reverse_engineer_sales_v4
python -m validation.audit_v4
python -m validation.audit_v4_general_only
python scripts/recalc_confidence_v4_split.py
python scripts/convert_v4_to_sales_imp_mapo.py
```

예상 효과 (FINAL_SUMMARY 기준):
- MNAR WAPE: 21.23% → ~13.35% (PASS)
- OoM accuracy: 96.71% → ~95.7% (여전히 borderline — 추가 확인 필요)
- Q1 WAPE: 21.14% → ~15.39% (PASS 가능)
- LODO WAPE: 47.62% → ~48.58% (여전히 FAIL — 구조적 한계)

### 우선순위 2: LODO WAPE 구조적 접근

LODO 는 단순 n_estimators 증가로 해결 불가 (dong fixed-effect 과의존).
가능한 접근:
- 서울 구별 특성 피처 추가 (상권 규모, 임대료 등) — 마포 dong 을 식별하지 않고 특성으로 설명
- 행정동 클러스터링 피처 (홍대/망원/마포/상암 등 상권권역) 추가

### 우선순위 3: 0-1 KOSIS 추가 anchor

DT_1K41017 (음식점포함 소매판매액지수) API 재시도 (KOSIS API 상태 정상 시):
- 정상 취득 시 r 계산 후 기존 r=0.9291 초과 여부 확인
- Sprint 8 probe 코드 (`scripts/probe_kosis_additional_anchors.py`) 재실행으로 즉시 판정 가능

---

## 파일 위치

| 파일 | 설명 |
|---|---|
| `scripts/probe_kosis_additional_anchors.py` | Sprint 8 신규 — KOSIS 추가 anchor 탐색 |
| `validation/results/sprint8_kosis_anchor_probe.csv` | KOSIS probe 결과 (기존 r=0.9291 기준선 포함) |
| `docs/sales-imputation/audit_v4_report.md` | 현행 합격선 (Sprint 7 = Sprint 8 동일) |
| `validation/results/audit_v4_general_only.csv` | 일반 셀 MNAR 21.23% |
