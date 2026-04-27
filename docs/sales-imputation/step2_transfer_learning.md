# Step 2: Seoul-wide Transfer Learning 실험

**목적:** 서울 전체 데이터로 학습한 모델이 마포 결측 예측에 유리한가?

- Train: Seoul alive 제외 Mapo (84,235 cells)
- Validate: Mapo MNAR-mimic (1,332 작은 셀)
- Test: Mapo missing (137 cells)

## 결과

| 모델 | WAPE | Pearson r | RMSLE | F1 4-tier | OoM 2x |
|:-----|----:|--:|--:|--:|--:|
| **Mapo-only ExtraTrees (기존)** | **13.35%** | 0.965 | 0.327 | 0.838 | 95.72% |
| Seoul_ET | 58.67% | 0.377 | 0.952 | 0.342 | 56.83% |
| Seoul_FT | 61.01% | 0.315 | 0.974 | 0.305 | 55.11% |
| Seoul_TabPFN | 57.64% | 0.416 | 0.925 | 0.332 | 55.93% |

**🏆 최고:** `Mapo_ET_baseline` WAPE 13.35%
