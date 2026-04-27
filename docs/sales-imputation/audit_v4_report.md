# Audit v4 Report

**production_ready:** False

| 지표 | 값 | 합격선 | 통과 |
|:---|---:|---:|:---:|
| random_wape | 9.48% | ≤ 12% | ✅ |
| ts_wape | 12.76% | ≤ 15% | ✅ |
| mnar_wape | 21.23% | ≤ 15% | ❌ |
| lodo_wape | 47.62% | ≤ 30% | ❌ |
| q1_wape | 21.14% | ≤ 18% | ❌ |
| pearson_r | 0.9957 | ≥ 0.97 | ✅ |
| rmsle | 0.3067 | ≤ 0.35 | ✅ |
| oom_accuracy | 0.9671 | ≥ 0.97 | ❌ |
| f1_4tier | 0.8697 | ≥ 0.85 | ✅ |
| mase | 0.0849 | ≤ 0.2 | ✅ |

## Diagnoses

- MNAR WAPE 21.2% > 15%: 결측 복원 신뢰성 부족. → confidence 일괄 0.10 하향
- LODO WAPE 47.6% > 30%: dong fixed effect 의존 잔존. → dong_avg LOO 재적용