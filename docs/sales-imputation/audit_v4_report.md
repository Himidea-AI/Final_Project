# Audit v4 Report

**production_ready:** False

| 지표 | 값 | 합격선 | 통과 |
|:---|---:|---:|:---:|
| random_wape | 7.99% | ≤ 12% | ✅ |
| ts_wape | 11.74% | ≤ 15% | ✅ |
| mnar_wape | 14.67% | ≤ 15% | ✅ |
| lodo_wape | 49.35% | ≤ 30% | ❌ |
| q1_wape | 15.59% | ≤ 18% | ✅ |
| pearson_r | 0.9961 | ≥ 0.97 | ✅ |
| rmsle | 0.2449 | ≤ 0.35 | ✅ |
| oom_accuracy | 0.9784 | ≥ 0.97 | ✅ |
| f1_4tier | 0.9156 | ≥ 0.85 | ✅ |
| mase | 0.0712 | ≤ 0.2 | ✅ |

## Diagnoses

- LODO WAPE 49.3% > 30%: dong fixed effect 의존 잔존. → dong_avg LOO 재적용