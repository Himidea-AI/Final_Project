# operational_fit_scorer — 점수식 스펙 v2

> 담당: A2 봉환 · 작성일: 2026-04-24 · 최종 갱신: 2026-04-24 (v2)
> 상태: **검증 완료, PR 대기**
> 관련 Jira: 미발급 (IM3-?)

**v2 변경 (2026-04-24)**
- 가중치 재조정: 0.40·지하철 + 0.30·버스 + 0.30·집객 → **0.10·지하철 + 0.40·버스 + 0.50·집객**
- 근거: 실매출 16동 × 최신 8분기 평균 회귀에서 지하철 서브 R²=0.004 (상관 없음)
- 전체 R² 0.33 → **0.55 (강한 양의 상관, r=+0.74)**
- 데이터 한계 발견 기록 (`dong_subway_access`는 동 행정중심 기준 거리라 경계 환승역 미반영)
- Phase C 과제 문서화 (polygon 경계 기반 거리 재계산)

## 1. 목적

마포구 16개 행정동의 **대중교통·집객 인프라 접근성**을 단일 점수(0~100)로 정량화하여, `district_ranking` 에이전트의 winner 결정 가중합에 한 축을 추가한다.

- 현재 `market_report.accessibility`는 [backend/src/main.py:455](../../backend/src/main.py#L455)에서 **하드코딩 75** 폴백 상태 — 아무도 실데이터를 주입하지 않음
- 기존 점수식(매출/인구/임대료)은 **업종 매출 역사**만 반영 — 교통·집객 인프라는 블랙박스

## 2. 방법론 & 레퍼런스 체인

학술·실무 방어를 위한 인용 체인을 의도적으로 설계.

| 구성 요소 | 출처 |
|---|---|
| **이론 골격** — gravity-based accessibility | Hansen, W.G. (1959). *How Accessibility Shapes Land Use*. JAPA |
| **분류 프레임** — location-based accessibility | Geurs, K.T. & Van Wee, B. (2004). *Accessibility evaluation of land-use and transport strategies*. J. of Transport Geography |
| **거리감쇠 함수** — Gaussian decay | McGrail, M.R. & Humphreys, J.S. (2009). *E2SFCA method* |
| **ML 가중치 결합** — Hansen + ML | *Hansen's Accessibility Theory and Machine Learning: a Potential Merger* (Springer, Networks and Spatial Economics, **2025**) |
| **SHAP 캘리브레이션** (국내 사례) | 『공공데이터와 설명가능한 AI 기법을 활용한 자영업 상권 분석과 장기 생존 예측』 (대한산업공학회지, **2024**) |
| **현대 분류체계** | *Accessibility Measures: From a Literature Review to a Classification Framework* (MDPI IJGI, 2024) |

**심사 방어 한 줄**:
> Hansen(1959) gravity-based accessibility 이론을 소매 입지 도메인에 이식, 거리감쇠는 E2SFCA(2009) Gaussian 함수, 가중치는 Springer 2025의 Hansen+ML 결합 노선을 따라 본 프로젝트 TCN SHAP로 캘리브레이션.

## 3. 입출력 스키마

**입력**:
```python
def score_district(dong_name: str) -> OperationalFitResult
```

**출력**:
```python
class OperationalFitResult(TypedDict):
    operational_fit_score: float   # 0~100 최종 점수
    subway_sub: float              # 0~100 지하철 서브점수
    bus_sub: float                 # 0~100 버스 서브점수
    fclty_sub: float               # 0~100 집객시설 서브점수
    evidence: dict                 # 원천 수치 — synthesis 프롬프트 근거용
    # evidence 예시:
    # {
    #   "nearest_subway": "광흥창역",
    #   "subway_distance_m": 32,
    #   "subway_count_1km": 5,
    #   "bus_daily_avg_boarding": 42000,
    #   "bus_stop_count": 14,
    #   "fclty_count_by_type": {"의료": 3, "교육": 4, "공공": 2, ...},
    # }
```

**네이밍 주의**: `legal.py`에 이미 `accessibility_law`(장애인편의증진법)가 있어 **`accessibility_*`** 접두는 회피. 본 점수는 **`operational_fit_*`** 로 통일.

## 4. 데이터 소스 (수집 완료)

| 테이블 | 행 수 | 비고 |
|---|---|---|
| `dong_subway_access` | 424동 (마포 16동 포함) | 동 중심좌표·최근접역·거리·1km내 역 개수 사전 계산 완료 |
| `bus_boarding_daily` | 3,710,007행 (2019~2026.03) | 정류장별 일별 승하차 |
| `seoul_adstrd_fclty` | 336행 (마포 16동) | 서울 전수 미수집이나 **MVP 범위 충분** |
| `holiday_calendar` | 3,287행 (2019~2027) | 요일·공휴일 가중치용 (Phase B) |

ORM 매핑은 [backend/src/database/models.py](../../backend/src/database/models.py) 867/900/943/1214 라인에 2026-04-20자로 완료.

**추가 수집 불필요** — 읽기 전용 SELECT만 수행.

## 5. 공식

### 5.1 거리 감쇠 함수 (E2SFCA Gaussian)

$$G(d, d_0) = \frac{e^{-\frac{1}{2}(d/d_0)^2} - e^{-\frac{1}{2}}}{1 - e^{-\frac{1}{2}}}, \quad d \le d_0$$

- `d_0 = 1000m` (TOD 역세권 500m의 2배, 버스·집객 포괄)
- `d > d_0` → `G = 0`

### 5.2 서브점수 (각 0~100 정규화)

$$S_i^{(subway)} = \sum_{역 \in 1km} G(d_{i, 역}, 1000)$$

$$S_i^{(bus)} = \sum_{정류장 \in 1km} \text{승하차}_{stop} \cdot G(d_{i, stop}, 1000)$$

$$S_i^{(fclty)} = \sum_{시설 \in 동_i} w_{type} \cdot \mathbb{1}(시설)$$

- 서브점수별 min-max 정규화로 0~100
- `w_type`: 의료=1.5, 교육=1.2, 공공=1.0, 기타=0.8 (Phase A 휴리스틱, Phase B에서 SHAP으로 교체)

### 5.3 최종 점수

$$\text{OperFit}_i = w_1 \cdot S_i^{(subway)} + w_2 \cdot S_i^{(bus)} + w_3 \cdot S_i^{(fclty)}$$

| Phase | w₁ (지하철) | w₂ (버스) | w₃ (집객) | 근거 | 전체 R² |
|---|---|---|---|---|---|
| A (초기 휴리스틱) | 0.40 | 0.30 | 0.30 | TOD 연구 관례 | 0.33 |
| **B (현재, 2026-04-24)** | **0.10** | **0.40** | **0.50** | **실매출 회귀 기반 재조정** | **0.55** |
| C (향후 polygon 거리 도입 시) | 재검토 | 재검토 | 재검토 | 동 경계 거리 반영 후 지하철 상향 여지 | TBD |

**Phase B 재조정 근거** (`validate_operational_fit_r2.py` 출력):
- 지하철 서브 R² = 0.004 (r=-0.06) — 상관 없음 → 0.10으로 대폭 축소
- 버스 서브 R² = 0.48 (r=+0.69) — 중간~강한 상관 → 0.40
- 집객 서브 R² = 0.54 (r=+0.73) — 강한 상관 → 0.50

### 5.4 정류장 ↔ 동 매핑

- **Phase A**: `station_name ILIKE '%<동명>%'` 화이트리스트 (마포 16동, ~32줄 dict)
- **Phase B**: 정류장 좌표 API(TOPIS) → `dong_subway_access.center_lat/lon` 반경 매칭

## 6. 파일 변경 범위

| 파일 | 주인 | 상태 | 협의 |
|---|---|---|---|
| `backend/src/services/operational_fit_scorer.py` (**신규**) | A1 찬영 | 신규 생성 | **찬영 사전 OK 필수** |
| `backend/src/agents/nodes/district_ranking.py` | 봉환 확장 ✅ | 가중합에 1축 추가 | 없음 |
| `backend/src/schemas/state.py` | B1 예진 | `operational_fit_results` 필드 추가 | **예진 리뷰** |
| `backend/src/main.py:455` | 공통 | `accessibility` 폴백을 실점수로 교체 | 공통 — PR 설명만 |
| `frontend/src/types/index.ts` + IndicatorGrid | C1 강민 | 서브점수 표시 | **강민 스키마 요청** |

## 7. 기존 점수식과의 통합 (district_ranking.py)

현재 가중치 ([district_ranking.py:302-306](../../backend/src/agents/nodes/district_ranking.py#L302-L306)):
```
population_weight=True : sales 35% + pop 45% + rent 20% (+density 15% + trend 5%)
population_weight=False: sales 50% + pop 10% + rent 40% (+density 15% + trend 5%)
```

**제안**: `operational_fit` 15% 주입, 매출·인구에서 재분배:

```
population_weight=True : sales 30% + pop 40% + rent 15% + operfit 15% (+density 15% + trend 5% 조건부)
population_weight=False: sales 45% + pop 10% + rent 30% + operfit 15% (+density 15% + trend 5% 조건부)
```

구현 위치: [district_ranking.py:370-376](../../backend/src/agents/nodes/district_ranking.py#L370-L376) `ranked` 루프에 `operfit_norm[i] * w_operfit` 합산 1줄 추가.

## 8. 구현 단계

### Phase A — MVP (1일)
1. `services/operational_fit_scorer.py` 작성 (Gaussian decay + 서브점수 3개 + 휴리스틱 가중합)
2. 정류장-동 화이트리스트 dict (마포 16동)
3. `district_ranking_node` 통합 — 16동 병렬 호출
4. `state.py`에 `operational_fit_results: dict[str, OperationalFitResult]` 추가
5. `main.py:455` 실점수 교체

### Phase B — 검증·튜닝 (데모 전)
1. **Before/After 랭킹 비교** — 16동 순위 변화. 변화 없으면 이 피처의 존재 가치 재검토
2. **SHAP 가중치 역산** — 기존 TCN SHAP에서 교통·집객 관련 피처 기여도 추출
3. **실매출 회귀 검증** — 과거 매출과의 상관 R² 리포트
4. 정류장-동 매핑 정밀화 (방법 B)

## 9. 검증 체크리스트

- [ ] 16동 점수 분포가 상식과 일치 (서강동·공덕동 상위, 상암동 하위 등)
- [ ] winner 순위가 실제로 변경되는 동 1개 이상
- [ ] 서브점수 `(subway, bus, fclty)` 각각 상관관계 < 0.8 (다중공선성 체크)
- [ ] 평균 실행시간 < 50ms (LLM 에이전트와 병렬 제약)
- [ ] `evidence` dict가 `synthesis` 프롬프트에 주입되어 LLM 자연어 근거로 활용

## 10. 데모 스토리 (심사용)

> *"왜 서강동이 1위인가?"*
>
> 기존 답변: "매출 성장률과 인구가 높아서"
>
> **신규 답변**: "광흥창역 도보 1분(점수 95), 반경 1km 내 지하철 5개역, 버스 일평균 승하차 42,000명, 동 내 집객시설 12개(의료·교육·공공 가중) → **operational_fit 87점**. Hansen gravity accessibility 이론(1959) + Gaussian 거리감쇠(E2SFCA 2009) + TCN SHAP 가중치(Springer 2025 방법론)."

## 11. 협의 결정 필요 사항

**Phase A MVP 기준, 봉환 단독 진행 가능.** 차단 요인은 찬영 사전 OK 1건.

| 대상 | 필요성 | 내용 |
|---|---|---|
| **찬영 (A1)** | 🟢 **필수 (사전)** | `services/operational_fit_scorer.py` 신규 파일 생성 OK? DB 커넥션은 `db_client`(`market_analyst.py`) 재사용 vs 별도 풀? |
| **예진 (B1)** | 🟡 PR 리뷰로 충분 | `state.py`에 `operational_fit_results` 필드 **추가**는 "기존 인터페이스 유지하면서 확장" 규칙에 해당 → 사전 DM 불필요, 실제 PR 리뷰만 |
| **강민 (C1)** | ⚪ 불필요 | `main.py:455`의 `accessibility` 필드는 이미 존재 — 값만 75 → 실점수로 바뀜. 프론트 무수정 |
| **수지니 (B2)** | ⚪ 불필요 (Phase A) | Phase B 튜닝 시에만 기존 `shap_result` state **읽기**만 수행 — 수지니 코드 수정 없음 |

## 12. Out of Scope

- 서울 전체 `seoul_adstrd_fclty` 재수집 — 마포 후보지 점수화 목적상 불필요
- 정류장 좌표 TOPIS API 수집 — Phase C 정밀화 단계
- `holiday_calendar` 연동 — Phase D(요일별 점수 동적 변화)
- LLM 프롬프트 자동 생성 — `evidence` dict 전달까지만, synthesis 프롬프트 변경은 별도 PR

## 13. 검증 결과 (2026-04-24 로컬 DB 기준)

**단위 테스트**: `pytest tests/test_operational_fit_scorer.py`
- 9/9 pass (Gaussian 경계, min-max, SHAP 캘리브레이션 edge case)

**DB 통합 테스트**: `RUN_DB_TESTS=1 pytest ...`
- 2/2 pass (16동 점수 계산 완주, Before/After 랭킹 로그)

**실매출 R² 리포트**: `python -m tests.validate_operational_fit_r2`
- 16/16 동 유효 샘플, 전체 R² = **0.5517** (r=+0.7428)
- 서브: 지하철 0.0042 / 버스 0.4823 / 집객 0.5399

**end-to-end `district_ranking_node` 직접 호출**:
- winner 서교동, analysis_metrics.operational_fit_score=95.7 주입 확인
- `operational_fit_results` 16동 전체, scouting_results 각 동에 operfit 4개 필드

**기존 회귀 테스트** (operational_fit·RAG·bench·integration 제외):
- 85 pass / 1 pre-existing fail (`test_demographic_integration` — parallel_analysis_node 이름 변경 이전 테스트, 본 변경과 무관)

## 14. 16동 실제 점수 분포 (가중치 v2 적용)

| 순위 | 동 | 총점 | 지하철 | 버스 | 집객 | 매출(만원) |
|---|---|---|---|---|---|---|
| 1 | 서교동 | 95.7 | 56.7 | 100.0 | 100.0 | 1,794,194 |
| 2 | 상암동 | 66.5 | 69.8 | 67.0 | 65.5 | 457,013 |
| 3 | 성산2동 | 48.7 | 23.0 | 65.3 | 40.7 | 98,635 |
| 4 | 아현동 | 48.2 | 92.5 | 50.2 | 37.8 | 64,124 |
| 5 | 공덕동 | 47.6 | 47.9 | 49.1 | 46.3 | 209,810 |
| ... | ... | ... | ... | ... | ... | ... |
| 16 | 연남동 | 14.1 | 10.0 | 20.3 | 10.0 | 296,471 |

**이상 신호**:
- 연남동 최하위(14.1)이나 실매출 29억(중상위) — `dong_subway_access`가 동 경계 홍대입구역(2호선) 미반영. Phase C에서 polygon 거리로 개선.
- 공덕동 지하철 47.9 — 실제는 4중 환승역이나 동 중심좌표 기준 "애오개역 486m"로 계산됨. 동일 한계.

## 15. Phase C 과제 (polygon 경계 거리)

`dong_subway_access` 데이터 자체가 "동 행정중심점 → 최근접역 직선거리" 기준. 상권 접근성은 실제로는 **동 경계의 임의 지점에서 역까지의 최단거리**가 더 적절.

- 데이터: `backend/src/services/` 또는 `data/geo/mapo_geo.json` 활용
- 방법: 동 경계 polygon ↔ 역 좌표 최단거리 계산 (Shapely)
- 효과 예상: 서교동·공덕동·연남동 지하철 서브점수 정상화 → 지하철 가중치 상향 여지

---

**다음 액션**: PR 업로드 → 찬영·예진 리뷰 → dev 머지.
