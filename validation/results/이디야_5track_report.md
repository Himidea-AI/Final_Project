# 이디야 5트랙 검증 Report

- 검증 시각: 2026-04-27T21:51:39.094100+00:00
- 카테고리: 카페
- 설정: days=90, n_seeds=5, multi_quarter_avg=4
- **production_ready: ❌ NO**

## 트랙별 결과

| 트랙 | 측정값 | 합격선 | 결과 |
|---|---|---|---|
| V1A | r=0.9543, MAPE=1.0748 | r ≥ 0.5, MAPE ≤ 0.5 | ❌ FAIL |
| V1B | r=0.953, MAPE=1.293 | r ≥ 0.45, MAPE ≤ 0.55 | ❌ FAIL |
| V1C | mean_ratio=None | 0.5~2.0 | ⚠️ INCOMPLETE |
| V2 | ratio=0.12 | 0.3~3.0 | ❌ FAIL |
| CI | ci_ratio=0.4626 | ≤ 0.3 | ❌ FAIL |

## 진단

- V1a fail (r=0.9543, MAPE=1.0748): 동×업종 매출 분포 격차. 가능 원인: (1) popularity_boost=5.0, (2) 정적 시뮬 한계 [브레인스토밍 옵션 3 future spec], (3) IPF calibration 미적용. → IPF + boost=1.0 재측정 권장.
- V1b fail (r=0.953): 방문 수 분포 격차. visits 의 sample size noise 가능. → agent 1000→3000 또는 PSE n 늘리기.
- V2 fail (ratio=0.12 < 0.3): 시뮬 매출 전국 평균의 12% 미만.
- CI fail (CI/mean=46.3% > 30%): PSE 변동 과다. → n_seeds 3→5→10 또는 days 90→180.

## Limitations

- 정적 시뮬 환경 — 90일 동안 같은 날씨/같은 월 (브레인스토밍 옵션 3 future spec).
- 매장 단위 실측 매출 부재 — 동×업종 평균으로 V1c 측정.
- 검증은 mock 강제 — Mode C/D LLM 활성 시 결정 분포 약간 변화 가능 (margin ~3%).
- 옵션 F (sample x380.0) — 시뮬 1000ag 결과를 마포 유효 인구 비례 scale up. factor 380 = 등록 인구 추정 (Cochran 1977). sensitivity 분석 (380 vs 440 vs 1.0) 은 별도 spec.