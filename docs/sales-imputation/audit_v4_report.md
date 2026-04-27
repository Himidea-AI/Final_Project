# Audit v4 Report

**production_ready:** False

| 지표 | 값 | 합격선 | 통과 |
|:---|---:|---:|:---:|
| random_wape | 10.89% | ≤ 12% | ✅ |
| ts_wape | 13.86% | ≤ 15% | ✅ |
| mnar_wape | 28.90% | ≤ 15% | ❌ |
| lodo_wape | 46.58% | ≤ 30% | ❌ |
| q1_wape | 26.02% | ≤ 18% | ❌ |
| pearson_r | 0.9949 | ≥ 0.97 | ✅ |
| rmsle | 0.3784 | ≤ 0.35 | ❌ |
| oom_accuracy | 0.9371 | ≥ 0.97 | ❌ |
| f1_4tier | 0.8411 | ≥ 0.85 | ❌ |
| mase | 0.0970 | ≤ 0.2 | ✅ |

## Diagnoses

- MNAR WAPE 28.9% > 15%: 결측 복원 신뢰성 부족. → confidence 일괄 0.10 하향
- LODO WAPE 46.6% > 30%: dong fixed effect 의존 잔존. → dong_avg LOO 재적용