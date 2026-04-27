# Sprint 9 — 디스크 Alternative + BEST_PARAMS 복원 시도

**작성일:** 2026-04-27
**작업자:** 찬영 (A1) + Claude Code (Sonnet 4.6)
**목적:** C: 가용 25GB < 필요 48GB 제약 하에서 BEST_PARAMS (n=300, depth=35) 복원 가능 경로 탐색

---

## 진단

### 드라이브 가용 공간

| 드라이브 | 가용 (GB) | 총 (GB) | 50GB+ 여유 |
|---|---|---|---|
| C: | 16.1 | 237.9 | 아니요 |
| D: | 0.0 | 0.0 | 아니요 (빈 드라이브) |

> Sprint 8 시점 (C: 17GB) 대비 약 0.9 GB 감소. 가용 드라이브 없음.

### 복원 필요 공간 계산

| 항목 | 크기 |
|---|---|
| 현재 checkpoints_v4 (n=100, depth=15, 6 seed) | 8.1 GB |
| data/raw/ (원본 데이터) | 19 GB |
| C: 현재 가용 | 16.1 GB |
| checkpoints 삭제 후 확보 가능 | 24.2 GB |
| BEST_PARAMS (n=300, depth=35) 추정 필요량 | ~48 GB (seed 당 ~7 GB × 6) |
| **판정** | **불가 — 24.2 GB ≪ 48 GB** |

### Step 2 검토: 다른 드라이브로 CHECKPOINT_DIR 이전

`validation/reverse_engineer_sales_v4.py` 의 `CHECKPOINT_DIR` 를 `V4_CHECKPOINT_DISK` 환경변수 기반으로
대체 드라이브에 저장하는 방식을 계획:

```python
import os
ALT_DISK = os.environ.get("V4_CHECKPOINT_DISK", "")
CHECKPOINT_DIR = (
    Path(ALT_DISK) / "v4_checkpoints" if ALT_DISK and Path(ALT_DISK).exists()
    else REPO_ROOT / "validation" / "results" / "checkpoints_v4"
)
```

**결과:** D: 가용 0 GB — 대체 드라이브 없음. 코드 변경 적용 불가.

### Step 3 검토: 단일 seed (Scenario B)

단일 seed (seed=42) 로 `SEEDS = [42]` 변경 시:
- 예상 디스크: seed 당 ~7 GB (n=300, depth=35) — 16.1 GB 가용으로 **1 seed 가능**
- 단, 합격선 1-1 `std/mean ≤ 0.10` 은 단일 seed 에서 측정 불가 (std = 0.0)
- 16.1 GB 여유에서 n=300, depth=35, seed=42 단독 → ~7 GB 사용 — **기술적으로 실행 가능**
- 그러나 1-1 합격선 측정 불가 (임시값 0.0 으로 처리 시 형식적 PASS 만 가능)

**위험 평가:** 단일 seed 는 앙상블 분산 측정을 우회하는 편법 — 실험적 가치는 있으나 정식 검증 불가.
사용자 명시적 승인 없이 코드 변경 진행 보류.

---

## 적용 시나리오

| 시나리오 | 조건 | 적용 여부 | 이유 |
|---|---|---|---|
| A — CHECKPOINT_DIR 대체 드라이브 이전 | 50GB+ 여유 드라이브 필요 | **미적용** | D: 가용 0 GB |
| B — 단일 seed (seed=42) 실험 | 디스크 ~7 GB 필요 | **보류** | 1-1 합격선 측정 불가; 사용자 확인 필요 |
| C — 보고서 작성 + 사용자 디스크 정리 요청 | — | **적용** | Scenario A/B 모두 불가/보류 |

**적용 시나리오: C**

---

## 합격선 현황 (Sprint 9 = Sprint 8 = Sprint 7 변화 없음)

모델 재학습을 수행하지 않았으므로 지표는 Sprint 8 과 동일.

| 합격선 | Sprint 7 | Sprint 9 | 변화 | 판정 |
|---|---|---|---|---|
| 2-3 MNAR WAPE | 21.23% | 21.23% | 0.00p | FAIL (target ≤ 15%) |
| 2-4 LODO WAPE | 47.62% | 47.62% | 0.00p | FAIL (target ≤ 30%) |
| 2-5 Q1 WAPE | 21.14% | 21.14% | 0.00p | FAIL (target ≤ 18%) |
| 2-8 OoM accuracy | 96.71% | 96.71% | 0.00p | FAIL (target ≥ 97%) |
| 0-1 KOSIS r | +0.0116 | +0.0116 | 0.0000 | FAIL (target +0.03) |
| 0-3 path 개선 | 0%p | 0%p | 0%p | FAIL (target -1.5%p) |
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

**미달성.** (Sprint 8 에서 변화 없음)

잔존 FAIL 7개:

| # | 합격선 | 현재 | 목표 | 근본 원인 | 해결 경로 |
|---|---|---|---|---|---|
| 1 | 2-3 MNAR | 21.23% | ≤ 15% | n=100, depth=15 용량 제한 | BEST_PARAMS 복원 (디스크 48 GB 필요) |
| 2 | 2-4 LODO | 47.62% | ≤ 30% | dong fixed-effect 과의존 | 구조적 한계 (Sprint 5 확인) |
| 3 | 2-5 Q1 | 21.14% | ≤ 18% | 소규모 셀 본질적 고분산 | BEST_PARAMS 부분 개선 가능 |
| 4 | 2-8 OoM | 96.71% | ≥ 97% | n=100 예측 정밀도 한계 | BEST_PARAMS → 95.7% (여전히 borderline) |
| 5 | 0-1 KOSIS r | +0.0116 | +0.03 | DT_1KC2023 분리 한계 | KOSIS API DT_1K41017 재시도 |
| 6 | 0-3 path | 0%p | -1.5%p | 마포 고유 패턴 | 서울 전이 불가 (구조적) |
| 7 | 4-1 sensitivity | 0.70% | ≥ 8% | v4 결측 보강 → ABM 변화 미미 | BEST_PARAMS 개선 후 재측정 |

---

## Sprint 10 권장 사항

### 필수 선행 조건 (사용자 수동 수행)

Sprint 10 에서 BEST_PARAMS (n=300, depth=35) 복원을 위해 **C: 드라이브에서 약 32 GB 이상** 확보 필요:

| 정리 대상 | 예상 확보량 | 위험도 |
|---|---|---|
| `validation/results/checkpoints_v4/` 삭제 | 8.1 GB | 낮음 (재생성 가능) |
| 외부 SSD/USB 로 `data/raw/` 이동 | 19 GB | 중간 (원본 데이터) |
| 기타 대용량 파일 정리 | 가변 | — |

> **중요:** checkpoints_v4 삭제 후 BEST_PARAMS 복원 실행 시 재생성됨. 원본 데이터는 이동 전 백업 필수.

현재 C: 16.1 GB + 위 항목 정리 시 최대 ~43 GB 확보 가능 → 48 GB 에 근접하지만 부족.
외부 SSD 50 GB 이상 연결 또는 D: 드라이브 포맷/재파티션이 가장 확실한 해결책.

### Scenario B (단일 seed) 실험적 선택지

사용자가 단일 seed 실험에 동의할 경우 즉시 실행 가능:
- `SEEDS = [42]` 임시 변경 + `n_estimators=300, max_depth=35` 복원
- 예상 디스크 사용: ~7 GB (C: 가용 16.1 GB 내)
- 예상 소요 시간: ~30 분
- 예상 효과: MNAR 21.23% → ~15% 내외 (단, 6-seed std 측정 불가)

---

## 파일 위치

| 파일 | 설명 |
|---|---|
| `docs/sales-imputation/sprint9_disk_alternative.md` | 이 보고서 |
| `docs/sales-imputation/sprint8_scenario_b.md` | Sprint 8 진단 (동일 제약 확인) |
| `docs/sales-imputation/audit_v4_report.md` | 현행 합격선 상태 |
| `validation/results/audit_v4_general_only.csv` | MNAR WAPE 21.23% (Sprint 7~9 동일) |
| `validation/reverse_engineer_sales_v4.py` | BEST_PARAMS 주석 (n=300, depth=35 필요) |
