# TCN 시나리오 시뮬레이터 설계 스펙

**날짜**: 2026-05-02
**담당**: B2 (수지니) — 배치 파이프라인 + API, C1 (강민) — 프론트엔드 UI
**브랜치**: `sj_simul`

---

## 1. 배경 및 목표

현재 TCN 매출 예측은 단일 예측값(4분기)을 반환하여 그래프 변동성이 없다.
시뮬레이터 방향성에 맞게, 사용자가 주요 변수(임대료, 유동인구 등)를 슬라이더로 조절하면
기준 예측선 vs 시나리오 예측선을 차트에서 즉각 비교할 수 있는 인터랙티브 시뮬레이터를 추가한다.

---

## 2. 핵심 설계 결정

### 2-1. 실시간 재추론 대신 사전 배치 계산 + 룩업 테이블

- **이유**: 슬라이더 조절마다 TCN을 재추론하면 지연 발생 (특히 다중 슬라이더 동시 조절 시)
- **방식**: 배치 스크립트로 모든 조합의 탄성치를 사전 계산 → JSON 캐시 저장
- **UI 반응**: 탄성치 테이블 룩업 + 보간(interpolation)만 수행 → 즉각 반응

### 2-2. 슬라이더 변수 (5개)

| 슬라이더 | 반영 피처 | 타입 |
|---|---|---|
| 임대료 | `rent_1f` | ±% 슬라이더 |
| 공실률 | `vacancy_rate` | ±% 슬라이더 |
| 유동인구 | `bus_flpop` + `adstrd_flpop` + `floating_pop` 동시 적용 | ±% 슬라이더 |
| 검색 트렌드 | `trend_score` | ±% 슬라이더 |
| 계절(분기) | `quarter_num` | Q1~Q4 드롭다운 |

### 2-3. 상관관계 자동 연동 (데이터 기반 Pearson 상관계수)

학습 데이터에서 사전 계산된 피처 간 상관계수를 기반으로,
슬라이더 조절 시 연관 슬라이더를 자동 반영한다.

- 유동인구 ↑ → 임대료 자동 연동 (`corr(floating_pop, rent_1f)`)
- 유동인구 ↑ → 공실률 자동 연동 (`corr(floating_pop, vacancy_rate)`)
- 임대료 ↑ → 공실률 자동 연동 (`corr(rent_1f, vacancy_rate)`)

상관계수는 `feature_correlations.json`에 저장, `/predict/sensitivity` API를 통해 프론트에 전달.

### 2-4. 다중 슬라이더 복합 효과 합산 (Additive 가산)

```
시나리오 매출[q] = 기준 매출[q] × (1 + Σ 각 슬라이더 탄성치[q])
```

비선형 교호작용은 무시하는 근사이나 시뮬레이터 수준에서 충분하다.

### 2-5. 차트: 기준선 vs 시나리오 비교 (A안)

- 파란선: TCN 원래 예측 (고정 기준선)
- 주황선: 슬라이더 조절 후 시나리오 예측
- 기존 매출 예측 결과 카드 내 "시나리오 시뮬레이터" 접기/펼치기로 추가

---

## 3. 배치 파이프라인

**파일**: `models/tcn_forecast/sensitivity.py`

### 3-1. 탄성치 계산

```
입력:
  - 156개 (동×업종) 조합
  - 5개 슬라이더 피처 (유동인구는 3개 동시 적용)
  - 7단계 섭동: [-30, -20, -10, 0, +10, +20, +30] %
총 TCN 추론 횟수: 156 × 5 × 7 = 5,460회

계산:
  elasticity[dong][industry][feature][delta] =
    (매출(섭동) - 매출(기준)) / 매출(기준) × 100

quarter_num 처리:
  섭동 대신 Q1~Q4 각각에 대한 예측값 계산
  elasticity[...]["quarter_num"] = {"Q1": ..., "Q2": ..., "Q3": ..., "Q4": ...}
```

### 3-2. 상관계수 계산

```
학습 데이터 전체에서 조절 피처 간 Pearson 상관계수 계산
저장: models/tcn_forecast/weights/feature_correlations.json
포함 쌍:
  - floating_pop ↔ rent_1f
  - floating_pop ↔ vacancy_rate
  - rent_1f ↔ vacancy_rate
```

### 3-3. 저장 형식

```json
{
  "11440530_CS100001": {
    "baseline": [Q1매출, Q2매출, Q3매출, Q4매출],
    "elasticity": {
      "rent_1f":      {"-30": -8.2, "-20": -5.1, "-10": -2.4, "0": 0, "+10": 2.6, "+20": 5.3, "+30": 8.1},
      "vacancy_rate": {"...": "..."},
      "floating_pop": {"...": "..."},
      "trend_score":  {"...": "..."},
      "quarter_num":  {"Q1": -3.2, "Q2": +1.1, "Q3": +5.8, "Q4": -2.4}
    }
  }
}
```

저장 위치: `models/tcn_forecast/weights/sensitivity_cache.json`

---

## 4. API

**엔드포인트**: `GET /predict/sensitivity`

**쿼리 파라미터**: `dong_code`, `industry_code`

**응답**:
```json
{
  "elasticity": {
    "rent_1f":      {"-30": -8.2, ..., "+30": 8.1},
    "vacancy_rate": {"...": "..."},
    "floating_pop": {"...": "..."},
    "trend_score":  {"...": "..."},
    "quarter_num":  {"Q1": -3.2, "Q2": 1.1, "Q3": 5.8, "Q4": -2.4}
  },
  "correlations": {
    "floating_pop→rent_1f":      0.63,
    "floating_pop→vacancy_rate": -0.41,
    "rent_1f→vacancy_rate":      -0.38
  },
  "baseline_sales": [Q1, Q2, Q3, Q4]
}
```

**담당**: B2 — `backend/src/routers/predict.py` 에 추가

---

## 5. 프론트엔드 (C1 담당)

**위치**: 기존 매출 예측 결과 카드 내 "시나리오 시뮬레이터" 섹션 (접기/펼치기)

**슬라이더 UX**:
- 임대료 / 공실률 / 유동인구 / 트렌드: -30% ~ +30% 범위 슬라이더
- 계절(분기): Q1 / Q2 / Q3 / Q4 드롭다운
- 상관 연동 슬라이더는 자동 조절 후 흐리게 표시 (사용자가 수동 override 가능)

**시나리오 매출 계산 (프론트엔드)**:
```
1. 각 슬라이더 값 → 인접 탄성치 구간 선형 보간
2. 상관계수 적용: 연동 슬라이더 자동 조절
3. 복합 효과 가산: scenario[q] = baseline[q] × (1 + Σ elasticity_i[q])
4. 차트 즉시 업데이트 (파란선 고정, 주황선 갱신)
```

**차트**: Recharts `LineChart`
- x축: Q1 ~ Q4
- y축: 매출액 (원, formatKrw 포맷)
- 파란선: 기준 예측, 주황선: 시나리오 예측
- 두 선 차이를 강조하는 차이값(±원) 툴팁

---

## 6. 파일 구조

```
models/tcn_forecast/
  sensitivity.py              # 배치 스크립트 (신규, B2)
  weights/
    sensitivity_cache.json    # 탄성치 테이블 (배치 실행 후 생성)
    feature_correlations.json # 피처 간 상관계수 (배치 실행 후 생성)

backend/src/routers/
  predict.py                  # GET /predict/sensitivity 엔드포인트 추가 (B2)

frontend/src/components/
  ScenarioSimulator.tsx       # 슬라이더 + 차트 컴포넌트 (신규, C1)
```

---

## 7. 담당 분리 요약

| 작업 | 담당 | 파일 |
|---|---|---|
| 배치 섭동 스크립트 | B2 | `models/tcn_forecast/sensitivity.py` |
| 상관계수 계산 | B2 | `models/tcn_forecast/sensitivity.py` |
| `/predict/sensitivity` API | B2 | `backend/src/routers/predict.py` |
| 슬라이더 UI + 차트 | C1 | `frontend/src/components/ScenarioSimulator.tsx` |
| 탄성치 적용 + 보간 로직 | C1 | `frontend/src/components/ScenarioSimulator.tsx` |

---

## 8. 비고

- TCN 모델: v2 기준 (`finetuned_mapo_tcn_v2.pt`, `dilations=[1,2,4,8]`, `window_size=12`, `output_size=4`)
- 제외 조합(`EXCLUDE_COMBOS`: 염리동 중식, 성산1동 제과)은 배치 계산에서 스킵
- `sensitivity_cache.json` 용량 예상: 156조합 × 5피처 × 7단계 ≈ 수백KB, 문제 없음
- `shap_analysis.py` v2 마이그레이션 완료 (본 브랜치에 포함)
- `correlations` API 응답의 상관계수 값은 배치 실행 후 실제 학습 데이터에서 산출되므로, 스펙 내 예시값(0.63 등)은 참고용 수치임
