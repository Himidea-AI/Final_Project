# Sprint 13 — seoul_district_sales 25구 hybrid path 재실험

**작성일:** 2026-04-27
**작업자:** 찬영 (A1) + Claude Code (Sonnet 4.6)
**브랜치:** IM3-243-dong-fk-followup

---

## 큰 발견 (Sprint 12 → Sprint 13)

Sprint 12 진단에서 `seoul_district_sales` 에 서울 25구 87,938행이 적재되어 있음을 확인.
그러나 `compare_learning_paths.py` 의 `load_data("seoul_10ind")` 가 `store_quarterly` (마포만 3,840행) 를 FROM 테이블로 사용하고 있어,
서울 25구 `seoul_district_sales` 를 LEFT JOIN 해도 실제로는 마포 3,840행만 반환되었다.

Sprint 4 결론 "DONE_WITH_CONCERNS — district_sales 가 마포구만 포함" 은 **부분적으로 오진**:
- `district_sales` (마포만) → `seoul_district_sales` 변경은 이미 Sprint 4 fix 에서 반영됨
- 그러나 `store_quarterly` (마포만) 이 FROM 테이블로 남아 있어 서울 25구 join 이 무효화됨

### 발견된 서울 전체 테이블

| 테이블 | 행 수 | 구 수 | 동 수 | 설명 |
|---|---|---|---|---|
| `store_quarterly` | 3,840 | 1 (마포) | 16 | 기존 마포 전용 |
| `seoul_district_stores` | 100,587 | 25 | 425 | store_quarterly 의 서울 전체 버전 |
| `seoul_district_sales` | 87,938 | 25 | — | 서울 전체 매출 (alive) |

`seoul_district_stores` JOIN `seoul_district_sales` 시 alive=87,938 행 (25구 × 424동 × 10업종 × 24분기 일부).

---

## Step 1: compare_learning_paths.py 수정

`load_data()` 의 `seoul_10ind` scope 에서 `store_quarterly` → `seoul_district_stores` 로 변경.

```python
# 변경 전
store_table = "store_quarterly"   # 마포만 3,840행

# 변경 후
store_table = "seoul_district_stores"  # 서울 25구 100,587행
```

파일: `validation/compare_learning_paths.py`

---

## Step 2: store_quarterly / seoul_district_stores 가용성 확인

| 테이블 | 행 수 | 구 | 동 | alive rows |
|---|---|---|---|---|
| `store_quarterly` (mapo scope) | 3,840 | 1 | 16 | 3,703 |
| `seoul_district_stores` (seoul_10ind scope) | 100,587 | 25 | 425 | 87,938 |
| `seoul_district_stores` (마포제외) | 96,747 | 24 | 409 | 84,235 |

**결론: 25구 모두 있음 → 실험 진행.**

---

## 재실험 결과

3 path × 6 seed × 5-fold CV = 90 학습 세션.

| path | mean_wape | std_wape |
|---|---|---|
| mapo_only | **40.86%** | ±0.53 |
| seoul_to_mapo | 68.53% | ±0.13 |
| hybrid | 68.34% | ±0.22 |

### 비교: Sprint 4 (버그) vs Sprint 13 (수정)

| path | Sprint 4 (store_quarterly 버그) | Sprint 13 (seoul_district_stores 수정) | 변화 |
|---|---|---|---|
| mapo_only | 40.86% | 40.86% | — (동일) |
| seoul_to_mapo | 40.86% | 68.53% | **+27.67%p** (악화) |
| hybrid | 40.93% | 68.34% | **+27.41%p** (악화) |

Sprint 4 에서 seoul_to_mapo / hybrid 가 mapo_only 와 동일했던 이유:
- `store_quarterly` (마포만) 가 FROM 테이블이므로 세 path 모두 실질적으로 마포 데이터만 사용
- 이번 fix 로 실제 서울 25구 데이터를 사용하니 오히려 **mapo_only 가 최선**임이 확인

---

## 합격선 0-3 재판정

합격선: best WAPE − mapo_only WAPE ≥ −1.5%p → 그 path 채택.

| 항목 | 값 |
|---|---|
| best path | mapo_only (40.86%) |
| best − mapo_only | **−0.00%p** |
| 합격 조건 | ≥ −1.5%p |
| **판정** | **FAIL** |

**채택 path: `mapo_only`** (기존과 동일)

---

## 원인 분석: 왜 서울 25구가 오히려 악화?

서울 25구 데이터를 추가할 때 WAPE 가 40.86% → 68.34~68.53% 로 급등하는 원인:

1. **분포 이질성**: 서울 25구의 업종별 매출 분포가 마포구와 상이. 강남/서초 등 고매출 구가 포함되어 모델이 마포를 과소예측.
2. **MNAR 구조 차이**: 마포에서 결측(폐업/소규모) 패턴이 서울 전체 패턴과 다름. 24구 data 의 alive 분포가 마포 MNAR holdout 예측에 노이즈로 작용.
3. **sample_weight=5 효과 미흡**: hybrid 에서 마포 행에 weight=5 를 부여했으나 서울 24구의 84,235 alive 행 대비 마포 3,703 alive (weight 적용 후 등가 18,515) 로 여전히 마포 비중이 낮음.
4. **feature space 불일치**: 동 코드(dong_code), 인구 구조, 상권 밀집도 등 마포 특유 피처가 서울 전체에서는 대표성을 잃음.

---

## 본 학습 재실행 여부 (Step 5)

| 항목 | 현황 |
|---|---|
| 디스크 가용 | **7.8 GB** (238 GB 중 231 GB 사용, 97%) |
| 최소 필요 | ~10 GB (single seed ExtraTrees + temp) |
| 결과 의미 | 0-3 FAIL → `mapo_only` 채택 → 본 학습 변경 불필요 |
| **결정** | **SKIP** — 디스크 부족 + 채택 path 변경 없음 |

---

## 합격선 변화 종합

| 합격선 | Sprint 4 (버그) | Sprint 13 (fix) | 변화 |
|---|---|---|---|
| 0-3 서울/hybrid 개선 여부 | FAIL (데이터 버그로 측정 불가) | **FAIL** (mapo_only 최선) | 확인됨 |
| 채택 path | mapo_only | **mapo_only** | 동일 |

---

## 결론

서울 25구 `seoul_district_stores` 를 사용한 진짜 재실험 결과,
`mapo_only` 가 가장 낮은 WAPE(40.86%) 로 여전히 최선의 학습 path 임이 확인되었다.

서울 전체 데이터를 추가할수록 마포 예측 WAPE 가 악화(+27%p) 되는 현상은
서울 25구의 매출 분포가 마포와 이질적임을 의미하며,
Transfer learning / domain adaptation 없이는 단순 데이터 확장이 역효과임을 시사한다.

**권고사항**: 향후 서울 전체 활용 시 구별 embedding 또는 도메인 가중치 스케일링 도입 고려.
