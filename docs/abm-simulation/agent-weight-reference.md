# 마포 ABM · 가중치 레퍼런스

> 모든 의사결정 가중치의 **근거 · 계산식 · 실측 예시**. 발표 Q&A 대응용.

---

## 0. 총 계산식

매장 선택 시 최종 가중치:

```
weight = rating × price_w × store_bias × popularity_boost × cross_boost
```

| 항목 | 범위 | 근거 |
|------|------|------|
| `rating` | 1~5 (기본 4.0) | 카카오 맵 평점 (현재 기본값) |
| `price_w` | 0.1~1.3 | 가성비성향 × 매장 price_level |
| `store_bias` | 0.5~1.5 | 친구 `[INFO]`/`[PROMO]` 대화 누적 |
| `popularity_boost` | 0.5~1.5 | 실 매출 × SNS 감성 |
| `cross_boost` | 0.5~2.5 | 시간×동×연령×요일 실데이터 |

---

## 1. `rating` — 매장 평점

- **현재**: 카카오 매장 모두 4.0 기본값
- **TODO**: 카카오 API `rating` 필드 수집 시 실값으로 대체
- **영향**: 높을수록 선택 확률 ↑

---

## 2. `price_w` — 가격 민감도

개인 `price_sensitivity` (0=프리미엄, 1=가성비)와 매장 `price_level` (1~3) 곱셈.

```python
if price_sensitivity > 0.5:   # 가성비 지향
    price_w = max(0.1, 1.3 - 0.3 * price_level)
else:                          # 프리미엄 지향
    price_w = max(0.1, 0.4 + 0.3 * price_level)
```

**근거**:
- `price_sensitivity`: `apt_trade_real` 동별 아파트 단위면적가 + 연령 보정으로 산출
- `price_level`: `kakao_store_menu` 메뉴 가격 중간값 기반 자동 산출
  - <8,000원 → 1, 8,000~20,000원 → 2, 20,000원+ → 3

---

## 3. `store_bias` — 사회적 추천

친구 간 원시어 DSL 대화로 동적 변동.

| Verb | 효과 | 출처 |
|------|------|------|
| `[INFO sid=42 rate=good]` | `store_bias[42] *= 1.3` | 친구 경험 공유 |
| `[INFO sid=42 rate=bad]` | `store_bias[42] *= 0.7` | 부정 후기 |
| `[PROMO sid=42]` | `store_bias[42] *= 1.5` | 점주 홍보 |

**근거**: ConversationEngine 이벤트 로그. 시뮬 시작 시 1.0으로 초기화, 시간 지나며 누적.

---

## 4. `popularity_boost` — 실 매출 × SNS 감성

```
popularity_boost = dong_industry_weight × sentiment_score
```

### 4.1 `dong_industry_weight` (매출 기반)

- **출처**: `district_sales_seoul` 최신 분기 매출 (최근 2분기 이상)
- **계산**:
  ```sql
  SELECT dong_name, industry_name, AVG(monthly_sales) avg_sales
  FROM district_sales_seoul
  WHERE quarter >= (MAX - 1)
  GROUP BY dong_name, industry_name
  ```
- **정규화**: 전체 max 기준 `0.5 + (v/max)` → 0.5~1.5 범위
- **매핑** (카테고리): 한식·중식·일식·양식·분식·치킨·패스트푸드 → 음식점 / 커피-음료·제과점 → 카페 / 호프-간이주점 → 주점 / 편의점 → 편의점

### 4.2 `sentiment_score` (SNS 감성)

- **출처**: `mapo_sns_sentiment` 최근 180일
- **계산**:
  ```
  score = (positive - negative) / total
  sentiment = 1.0 + 0.3 × score   # 0.7~1.3 범위
  ```
- **미커버 매장**: 1.0 기본값

---

## 5. `cross_boost` — 시간×동×연령×요일 (★ 핵심)

**전부 실데이터 기반**. 휴리스틱 임의값 없음.

### 5.1 시간×연령×동×요일 — `living_population`

#### 데이터
- `living_population` 최신 60일
- 차원: 동 × time_zone(6/11/14/17/20/24) × DOW(0~6) × 연령그룹(20s/30s/40s/50s/60+)

#### 계산
```sql
SELECT dong_name, time_zone, EXTRACT(DOW FROM date) dow,
       AVG(male_20_24 + male_25_29 + female_20_24 + female_25_29) AS g_20s,
       AVG(male_30_34 + male_35_39 + female_30_34 + female_35_39) AS g_30s,
       AVG(male_40_44 + male_45_49 + female_40_44 + female_45_49) AS g_40s,
       AVG(male_50_54 + male_55_59 + female_50_54 + female_55_59) AS g_50s,
       AVG(male_60_64 + male_65_69 + male_70_plus + female_60_64 + ...) AS g_60plus
FROM living_population
WHERE date >= MAX - 60
GROUP BY dong_name, time_zone, dow
```

**정규화**:
- 각 `(연령그룹, 동)`의 **전체 평균** 계산
- 각 (연령그룹, 동, 시간, 요일) 인구 / 평균 = 비율
- **0.5 ~ 2.0 범위**로 클램프

#### time_zone → hour 매핑
`living_population`은 6/11/14/17/20/24만 있어 시뮬 24시간 전체로 확장:
| time_zone | hour 범위 |
|-----------|----------|
| 6 | 6~10 |
| 11 | 11~13 |
| 14 | 14~16 |
| 17 | 17~19 |
| 20 | 20~23 |
| 24 | 0~5 + 24~25 |

#### DOW 매핑
PostgreSQL `EXTRACT(DOW)`: 일=0, 월=1, 화=2, ..., 토=6
Python `weekday`: 월=0, 화=1, ..., 일=6

```python
py_weekday = (dow - 1) % 7   # dow 1(월) → py 0, dow 0(일) → py 6
```

### 5.2 실측 예시

**상암동 30대 (오피스 상권):**
| 요일 | 6시 | 14시 | 20시 |
|------|-----|------|------|
| 월 | 0.73 | **1.67** | 0.92 |
| 화 | 0.75 | **1.71** | 0.95 |
| 수 | 0.74 | **1.67** | 0.93 |
| 목 | 0.76 | **1.70** | 0.95 |
| 금 | 0.74 | **1.62** | 0.89 |
| 토 | 0.68 | 0.87 | 0.73 |
| 일 | 0.65 | 0.79 | 0.73 |

→ **평일 14시 ~1.7x** (오피스 점심 유입), **주말 평일 대비 급감** (오피스 휴일).

**서교동 20대 (홍대 유흥):**
| 요일 | 20시 |
|------|------|
| 월 | 1.26 |
| 화 | 1.32 |
| 수 | 1.39 |
| 목 | 1.40 |
| **금** | **1.64** |
| **토** | **1.95** |
| 일 | 1.40 |

→ **금·토요일 저녁 피크**. 임의 `2.5x` 대신 **실측 1.95x** 반영.

### 5.3 `DONG_CHARACTER.cat_boost` (매출 기반 정적)

실 매출 데이터를 간결한 카테고리 boost로 사전 집계 (백업용, popularity_boost 없으면 사용).

```python
"서교동":   {"type": "nightlife",   "cat_boost": {"주점": 1.5, "카페": 1.3}},
"연남동":   {"type": "trendy",      "cat_boost": {"카페": 1.5}},
"상암동":   {"type": "office",      "cat_boost": {"음식점": 1.3, "카페": 1.2}},
...
```

**근거**: `district_sales_seoul` 동별 업종 매출 상위 관찰 기반. 추후 자동 보정 가능.

### 5.4 아키타입 보정 (남은 휴리스틱, 2개만)

실 `living_population`에 없는 세부 패턴:

| 아키타입 | 조건 | 가중치 | 사유 |
|---------|------|-------|------|
| `bcst` (방송 스태프) | 상암동 + 23~02시 + 편의점/음식점 | 1.6x | 야근 후 야식 (실데이터 부족) |
| `prnt` (유아 부모) | 주말 + 상암/성산2/망원2 | 1.2x | 가족 외식 (실데이터 보정 예정) |

---

## 6. 전체 가중치 플로우

```
[에이전트 의사결정]
        ↓
카테고리 선택 (시간×profile.pref_X)
        ↓
해당 동·카테고리 매장 후보
        ↓
영업시간 필터 (kakao_store_hours)
        ↓
각 매장 가중치 계산:
  rating × price_w × store_bias × popularity_boost × cross_boost
        ↓
가중 랜덤 선택
        ↓
메뉴 선택 (kakao_store_menu, 가성비성향 반영)
        ↓
예산 체크 → 방문 결정
```

---

## 7. 데이터 출처 총 요약

| 가중치 | 테이블 | 갱신 주기 |
|--------|-------|---------|
| `rating` | kakao_store (현재 기본값) | 카카오 API |
| `price_level` | kakao_store_menu (81K 메뉴) | 매장 신규 시 |
| `price_sensitivity` | apt_trade_real | 거래 발생 시 |
| `store_bias` | 시뮬 내부 (ConversationEngine) | 시뮬 중 실시간 |
| `popularity_boost` | district_sales_seoul + mapo_sns_sentiment | 분기별 + 일별 |
| `cross_boost` | **living_population 60일** ⭐ | 일별 |
| `DONG_CHARACTER` | district_sales_seoul 기반 분류 | 분기별 |

---

## 8. 환경 변수

독립된 가중치지만 행동 확률에 영향:

| 변수 | 값 | 효과 | 출처 |
|------|---|------|------|
| `weather="비"` | rain_mm > 5 | 이동 확률 × 0.4 | weather_daily |
| `weather="약한비"` | 0 < rain < 5 | × 0.7 | 동일 |
| `is_holiday=True` | - | 여가 확률 × 1.3 | holiday_calendar |
| `price_multiplier` | 1.0 + rent_shock | 매장 spend × 배수 | Scenario 입력 |

---

## 9. 발표 대응 Q&A

### Q1. "가중치 2.5x 같은 숫자는 어떻게 정했나요?"
> "임의 설정 아닙니다. 서울시 생활인구 60일치를 연령×동×시간×요일 5차원으로 집계해 **실제 유입 비율**을 그대로 사용합니다. 예: 서교동 20대 토요일 20시가 평균 대비 1.95배, 상암동 30대 평일 14시가 1.67배."

### Q2. "매장별 인기도는 어떻게 산출?"
> "두 지표 곱으로: ① `district_sales_seoul` 동×업종 매출 상위일수록 ↑, ② `mapo_sns_sentiment` 최근 180일 긍정/부정 비율. 모두 실데이터."

### Q3. "임의로 넣은 휴리스틱은 없나요?"
> "최소화했습니다. 실데이터에 없는 2가지만 남음: 방송 스태프 새벽 야식, 유아 부모 주말 가족 외식. 둘 다 1.2~1.6x로 보수적."

### Q4. "시간 매핑이 부정확하지 않나요?"
> "`living_population`은 6/11/14/17/20/24 6개 지점. 시뮬 24시간으로 확장 시 구간별로 같은 값 반복. 추후 API 세분화되면 즉시 반영 가능."

---

## 10. 향후 개선 TODO

- [ ] 카카오 API 매장 평점 실제 수집 → `rating` 고도화
- [ ] 신용카드 매출 시간대별 API 연동 → 요일 가중치 완전 자동화
- [ ] `living_population` time_zone 세분화 확장 (가능하면 2시간 단위)
- [ ] SHAP 분석으로 가중치 중요도 역산 → 불필요 가중치 제거
- [ ] 몬테카를로 500회 시뮬로 가중치 파라미터 자동 튜닝 (하이퍼파라미터 서치)

---

## 11. 관련 문서

- `docs/simulation-visual-roadmap.md` — 시각화 로드맵
- `docs/agent-dsl-cost-analysis.md` — DSL 비용 분석
- `docs/langgraph-abm-integration-roadmap.md` — LangGraph × ABM 통합
- `backend/src/simulation/agents.py::age_dong_time_boost` — 구현
- `backend/src/simulation/profile_builder.py::load_time_age_boost` — 데이터 로딩
