# SOTA 모델 비교 — v3 MNAR-Mimic CV

**목적:** 웹서치로 식별한 SOTA imputation 라이브러리가 기존 ExtraTrees(15.96%)를 넘을 수 있는지 검증

**평가:** 137 결측과 유사한 작은 셀(store_count ≤ 15) 5-fold CV

**데이터/피처/CV는 모두 동일**, 오직 모델만 교체

---

## 결과 (MNAR WAPE 낮은 순)

| 순위 | 모델 | MNAR WAPE | Pearson r | R² | 수행시간 |
|:--:|:-----|----:|:--:|:--:|----:|
| 1 | **ExtraTrees (baseline)** | 15.96% | 0.955 | 0.898 | 3s |
| 2 | **RandomForest** | 18.03% | 0.949 | 0.887 | 4s |
| 3 | **XGBoost** | 18.53% | 0.945 | 0.878 | 4s |
| 4 | **LightGBM** | 22.64% | 0.922 | 0.824 | 4s |
| 5 | **CatBoost** | 26.10% | 0.915 | 0.783 | 9s |
| 6 | **HyperImpute/hyperimpute** | 64.09% | 0.398 | 0.138 | 162s |
| 7 | **HyperImpute/ice** | 86.70% | 0.175 | -0.549 | 1s |
| 8 | **HyperImpute/missforest** | 186.51% | 0.149 | -3.282 | 19s |
| 9 | **HyperImpute/mice** | FAIL | — | — | 6s |
| 10 | **HyperImpute/sinkhorn** | FAIL | — | — | 1628s |

## 결론

**최고 성능: `ExtraTrees (baseline)` — MNAR WAPE 15.96%**

🥈 **Lewis Reasonable** — WAPE 15.96%. 15% 장벽 미세 미달이나 실무 수용 가능.