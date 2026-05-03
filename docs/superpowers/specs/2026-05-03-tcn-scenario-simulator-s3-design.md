# TCN 시나리오 시뮬레이터 S3 업그레이드 설계 스펙

**날짜**: 2026-05-03
**담당**: B2 (수지니) — 배치 파이프라인 + API, C1 (강민) — 프론트엔드 UI
**브랜치**: `sj_simul`
**기반 스펙**: `2026-05-02-tcn-scenario-simulator-design.md` (1차 버전)

---

## 1. 배경 및 목표

1차 시뮬레이터는 슬라이더 조작 시 그래프 전체가 동일한 비율로 위·아래로 평행이동했다. 영업팀이 신규 점포 오픈 전 사전 시나리오를 검토할 때, **분기별로 다르게 영향을 받는 변수**(공실률, 물가, 상권 활성도 등)의 효과를 시각적으로 구분할 수 없었다.

이번 업그레이드(S3)는 두 가지를 동시에 달성한다.

1. **그래프 비틀림** — 슬라이더 조작 시 분기별로 다른 % 변화율이 적용되어 곡선 모양 자체가 변한다.
2. **비교 UX (Master-Detail)** — 영업팀이 동일 업종에서 N개 동을 동시에 비교 후보로 등록하고, 카드 클릭으로 드릴다운 상세 분석한다.

---

## 2. 핵심 설계 결정

### 2-1. 사전 분기별 % 변화율 캐싱 (Option 1 — 응답 schema 확장)

기존 `perturb_and_predict()`가 4분기 예측을 평균(`mean()`)하여 단일 float를 반환하던 것을, **분기별 4개 값(`list[float]`)을 그대로 보존**한다. TCN v2(DMS, output_size=4)가 이미 분기별로 다른 출력을 내므로, 정보 손실이 발생하던 평균화 단계만 제거한다.

**캐시 schema 변경:**
```jsonc
// AS-IS
"elasticity": {
  "rent_1f": { "+10": 0.57 }   // 단일 % (4분기 평균)
}

// TO-BE
"elasticity": {
  "vacancy_rate": { "+10": [-6.37, -5.61, -5.62, -5.36] }  // 분기별 % (Q1~Q4)
}
```

**라이브 추론(C안) / 페어 캐시(B안) 미선택 사유:**
- 라이브 추론은 응답 50~200ms로 캐시 대비 크게 느려 비교 UX(N개 카드 동시 로드)에 부적합
- 페어 캐시는 슬라이더 간 비선형 교호작용을 부분 반영하나 ~3MB 캐시 + 운영 복잡도 증가
- 영업팀 시나리오는 "단일 변수 가정 비교"가 표준 사용 패턴 → 선형 합 + 안내 문구로 충분

### 2-2. 슬라이더 재구성 (5개 유지, 2개 교체)

검증 스크립트 결과(`tmp_verify_quarter_twist.py`, `tmp_scan_twist_features.py`)로 비틀림 가시성과 영업팀 의미를 평가하여 다음과 같이 재구성한다.

| # | 슬라이더 | 반영 피처 | 비틀림 | 1차 대비 |
|---|----------|----------|--------|----------|
| 1 | 공실률 | `vacancy_rate` | 명확 (1.5~3.7%p spread) | 유지 |
| 2 | 검색 트렌드 | `trend_score` | 약함 | 유지 |
| 3 | 계절(분기) | `quarter_num` | (categorical) | 유지 |
| 4 | **물가지수** | `cpi_index` | **명확** (1.10%p) | **NEW** (rent_1f 제거) |
| 5 | **상권 활성도** | `opr_sale_mt_avg` | **명확** (1.09%p, ratio 0.27) | **NEW** (floating_pop 제거) |

**제거 사유:**
- `rent_1f` (임대료): 비틀림 약함(0.15~0.33%p) + 영업팀 직관에 매우 뻔한 변수("오르면 매출↓")
- `floating_pop` (유동인구): 비틀림 약함(0.06~0.53%p) + 매우 뻔한 변수("많으면 매출↑")

### 2-3. 다중 슬라이더 합산 — 퍼센트 변화율의 선형 합산을 baseline에 곱셈 적용 + 안내 문구

각 슬라이더의 분기별 % 변화율을 단순 합산한 뒤, baseline 매출에 곱셈으로 반영한다.

```
final[q] = baseline[q] × (1 + Σ slider_elasticity[q] / 100)
```

슬라이더 간 비선형 교호작용은 근사로 무시한다. 화면 상단에 1줄 안내:

> "각 슬라이더는 다른 조건이 동일하다는 가정 하의 단일 변수 시뮬레이션입니다 (민감도 분석)."

### 2-4. 상관관계 노출 — 정보 카드 + 슬라이더 툴팁

기존 `feature_correlations.json`을 활용한다. **자동 연동(슬라이더 1개 움직이면 다른 슬라이더 자동 조정)은 채택하지 않는다** — 사용자 통제권 상실 + 인과관계 오해 우려.

- **정보 카드 (㉠)**: 시뮬레이터 상단에 "📊 데이터 인사이트" 박스. 학습 데이터의 변수 간 상관계수 표시.
- **슬라이더 툴팁 (㉡)**: 각 슬라이더 옆 ⓘ 아이콘, hover 시 "이 변수는 ○○와 +0.45 상관이 있어요. 함께 움직일 가능성을 고려해주세요."

### 2-5. 비교 UX (Master-Detail)

좌측 후보 리스트 + 우측 드릴다운 단일 화면 레이아웃.

- **좌측 (Master)**: 동×업종 후보 카드 N개 (최대 5개), 각 카드에 mini sparkline + 합계 % 변화 뱃지
- **우측 (Detail)**: 선택된 후보의 슬라이더 5개 + 분기별 비틀림 그래프 + 인사이트 카드
- **후보별 슬라이더 상태 격리**: 각 후보가 자체 슬라이더 값 보존 (영업팀이 "동마다 다른 가정" 동시 비교 가능)
- **세션 메모리만**: persist X, 공유 링크 X (YAGNI)

### 2-6. X축 라벨

- ❌ "Q1 / Q2 / Q3 / Q4" (달력 분기로 오해 유발)
- ✅ "1분기 후 / 2분기 후 / 3분기 후 / 4분기 후"

`quarter_num` 슬라이더만 예외 (계절성 절댓값) — UI에서 Q1/Q2/Q3/Q4 드롭다운 유지.

---

## 3. 백엔드 변경

### 3-1. 배치 파이프라인 (`models/tcn_forecast/sensitivity.py`)

**`SLIDER_FEATURES` 변경:**
```python
SLIDER_FEATURES: dict[str, list[str]] = {
    "vacancy_rate": ["vacancy_rate"],
    "trend_score": ["trend_score"],
    "cpi_index": ["cpi_index"],            # NEW
    "opr_sale_mt_avg": ["opr_sale_mt_avg"], # NEW
    # rent_1f, floating_pop 제거
}
```

**`perturb_and_predict()` 시그니처 변경:**
```python
# AS-IS
def perturb_and_predict(...) -> float:  # 4분기 평균
    pred_log = float(tgt_scaler.inverse_transform(raw_arr).mean())
    return max(0.0, float(np.expm1(pred_log)))

# TO-BE
def perturb_and_predict(...) -> list[float]:  # 4분기 list
    quarters = []
    for v in raw.flatten():
        pred_log = float(tgt_scaler.inverse_transform([[float(v)]])[0][0])
        quarters.append(max(0.0, float(np.expm1(pred_log))))
    return quarters
```

**`run_batch()` 변경:**
- 각 (slider, level) 조합에서 분기별 % 변화율 list 저장
- baseline_q는 이미 4개 분기 보존 (변경 없음)

**총 TCN 추론 횟수:**
- 153 조합 × (4 슬라이더 × 7 레벨 + 1 분기 슬라이더 × 4 값) = 153 × 32 = **4,896회**
- 1차(5,460회) 대비 약 10% 감소

### 3-2. API 라우터 (`backend/src/api/sensitivity.py`)

**Pydantic schema 변경:**
```python
# AS-IS
class ElasticityLevel(BaseModel):
    elasticity: dict[str, dict[str, float]]
    baseline_sales: float

# TO-BE
class ElasticityLevel(BaseModel):
    elasticity: dict[str, dict[str, list[float]]]  # 분기별 4개
    baseline_sales: list[float]                    # 분기별 4개
    correlations: dict[str, float]                 # 변경 없음
```

**ETag 로직, Cache-Control, 304 분기 처리 모두 변경 없음.**

---

## 4. 프론트엔드 변경

### 4-1. 신규 컴포넌트 (5개)

| 파일 | 책임 |
|------|------|
| `ScenarioCandidateList.tsx` | 좌측 패널, 후보 카드 목록, "+추가" 버튼, 선택 상태 |
| `ScenarioCandidateCard.tsx` | 단일 후보 카드, mini sparkline, 합계 % 뱃지, 삭제 |
| `ScenarioDetailPanel.tsx` | 우측 드릴다운 (기존 ScenarioSimulator 본체 흡수) |
| `useScenarioCandidates.ts` | 후보 추가/삭제/선택, 후보별 슬라이더 상태 격리 |
| `useElasticityComparison.ts` | N개 후보의 elasticity 병렬 fetch + ETag 캐시 활용 |

### 4-2. 수정 컴포넌트 (3개)

| 파일 | 변경 |
|------|------|
| `ScenarioSimulator.tsx` | 최상위 컨테이너, master-detail 레이아웃 재배치 |
| `ScenarioForecastChart.tsx` | 분기별 % 매핑, 4개 점이 비틀린 곡선으로 그려지도록 |
| `useElasticity.ts` | 반환 타입 `Record<slider, Record<level, number[]>>`, X축 라벨 변경 |

### 4-3. UI 추가 요소

- 시뮬레이터 상단 정보 박스 (상관관계 ㉠)
- 슬라이더 옆 ⓘ 아이콘 (상관 변수 툴팁 ㉡)
- 합산 안내 문구 1줄
- X축 라벨: "1분기 후 / 2분기 후 / ..."

---

## 5. 에러 처리 / 엣지 케이스

| 상황 | 처리 |
|------|------|
| 캐시 파일 없음 | 빈 dict + warning log (기존 동작 유지) |
| 캐시 JSON 파싱 실패 | error log + 빈 dict (기존 동작 유지) |
| 특정 조합 데이터 누락 | 응답 404 (기존 동작 유지) |
| 사용자가 같은 동×업종 후보 중복 추가 | 프론트에서 무시 (기존 후보로 포커스 이동) |
| 후보가 0개일 때 | DetailPanel에 "후보를 추가해주세요" 안내 |
| 슬라이더 값 0% (baseline) | elasticity = 0, 그래프는 baseline과 일치 |
| 후보 5개 초과 | 5개 제한 (영업팀 비교용 + UI 가독성) |
| API 호출 중 에러 | 후보 카드에 "데이터 불러오기 실패" + 재시도 버튼 |

---

## 6. 테스트 계획

### 6-1. 백엔드

| 영역 | 변경 |
|------|------|
| 기존 단위 테스트 (20개) | schema 의존 ~5개 수정 (elasticity가 list[float]임을 검증) |
| 신규 단위 테스트 | per-quarter 길이=4 검증, baseline_q 길이=4 검증 (2개 추가) |
| 신규 통합 테스트 | 새 슬라이더 2개(cpi_index, opr_sale_mt_avg) 응답 포함 검증 (1개) |

### 6-2. 프론트엔드

| 영역 | 변경 |
|------|------|
| useScenarioCandidates 훅 | 추가/삭제/선택 동작 (3개) |
| ScenarioForecastChart | 분기별로 다른 점 4개 렌더링 검증 (1개) |
| ScenarioCandidateCard | mini sparkline 데이터 매핑 (1개) |

---

## 7. 운영 정책

| 항목 | 결정 |
|------|------|
| 캐시 파일 배포 | 수동 (`python -m models.tcn_forecast.sensitivity` 운영 서버에서 실행) |
| 캐시 갱신 적용 | 백엔드 재기동 (모듈 import 시점 로드) |
| HTTP 캐시 헤더 | ETag + `Cache-Control: public, must-revalidate` (기존 유지) |
| 운영 메시지 | C1·백엔드담당 디스코드 안내 (schema 변경 명시) |

---

## 8. 비-목표 (YAGNI)

- 비교 전용 신규 엔드포인트 ❌
- 프리컴퓨트 비교 매트릭스 ❌
- 비교 결과 영구 저장 / 공유 링크 ❌
- 슬라이더 자동 연동 (옵션 D) ❌
- 라이브 추론 (옵션 C) ❌
- 페어 캐시 (옵션 B) ❌
- 후보 6개 이상 비교 ❌

---

## 9. 변경 사항 요약

**백엔드:**
- `sensitivity.py`: `perturb_and_predict()` list[float] 반환, `SLIDER_FEATURES` 재구성
- `backend/src/api/sensitivity.py`: Pydantic schema list[float]로 확장
- 캐시 재생성 + 운영 배포

**프론트엔드:**
- 신규 컴포넌트 5개, 수정 3개
- 정보 박스 + 슬라이더 툴팁 + 안내 문구 추가
- X축 라벨 "N분기 후"

**문서:**
- 본 스펙
- 구현 플랜 (`docs/superpowers/plans/2026-05-03-tcn-scenario-simulator-s3.md`)
- C1·백엔드담당 디스코드 안내 (schema breaking change)
