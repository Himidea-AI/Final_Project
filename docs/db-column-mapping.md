# DB 컬럼 매핑 가이드 (B1 에이전트 노드용)

> A1 → B1 전달 문서. Agent 노드에서 PostgreSQL 쿼리 시 참고.

## DB 접속 정보

```
Host: localhost
Port: 5432
Database: mapo_simulator
User: postgres
```

## Pydantic 스키마 → DB 테이블 매핑

---

### AgentState.district_data (DistrictData)

#### `floating_population` → `living_population` 테이블

```sql
-- 특정 동의 평일/주말 평균 유동인구
SELECT dong_name,
       AVG(CASE WHEN EXTRACT(DOW FROM date) BETWEEN 1 AND 5 THEN total_pop END) as weekday,
       AVG(CASE WHEN EXTRACT(DOW FROM date) IN (0, 6) THEN total_pop END) as weekend
FROM living_population
WHERE dong_code = '11440630'  -- 망원1동
  AND time_zone = 0           -- 일합계
GROUP BY dong_name;

-- 시간대별 유동인구 (피크 시간 탐색)
SELECT time_zone, ROUND(AVG(total_pop)::numeric) as avg_pop
FROM living_population
WHERE dong_code = '11440630' AND time_zone BETWEEN 1 AND 23
GROUP BY time_zone
ORDER BY avg_pop DESC
LIMIT 1;  -- peak_hour
```

| DistrictData 필드 | DB 테이블 | DB 컬럼 | 비고 |
|---|---|---|---|
| `floating_population.weekday` | `living_population` | `total_pop` | DOW 1~5 필터 후 AVG |
| `floating_population.weekend` | `living_population` | `total_pop` | DOW 0,6 필터 후 AVG |
| `floating_population.peak_hour` | `living_population` | `time_zone`, `total_pop` | AVG(total_pop) DESC LIMIT 1 |

#### `resident_population` → `dong_mapping` + `sgis_population` 테이블

```sql
-- 총 주민인구
SELECT resident_pop FROM dong_mapping WHERE dong_code = '11440630';

-- 20~39세 비율 (SGIS 성연령별 인구)
SELECT SUM(value) as age_20_39
FROM sgis_population
WHERE area_code LIKE '11440630%'    -- 해당 동의 소지역들
  AND year = 2024
  AND indicator LIKE 'age_gender%'  -- 연령별 인구 지표
```

| DistrictData 필드 | DB 테이블 | DB 컬럼 |
|---|---|---|
| `resident_population.total` | `dong_mapping` | `resident_pop` |
| `resident_population.age_20_39_ratio` | `sgis_population` | `value` (indicator로 필터) |

#### `competition` → `store_info` + `store_quarterly` 테이블

```sql
-- 동일 업종 점포수
SELECT store_count, closure_rate, franchise_count
FROM store_quarterly
WHERE dong_code = '11440630'
  AND industry_code = 'CS100001'  -- 한식음식점
  AND quarter = 20244;            -- 최신 분기

-- 반경 내 경쟁점포 (위경도 기반)
SELECT store_name, industry_m, lat, lon,
       (6371 * ACOS(
           COS(RADIANS(37.5565)) * COS(RADIANS(lat)) *
           COS(RADIANS(lon) - RADIANS(126.9010)) +
           SIN(RADIANS(37.5565)) * SIN(RADIANS(lat))
       )) * 1000 as distance_m
FROM store_info
WHERE dong_name = '망원1동'
  AND industry_m_code = 'Q12'  -- 커피/음료
ORDER BY distance_m;
```

| CompetitionAnalysis 필드 | DB 테이블 | DB 컬럼 |
|---|---|---|
| `direct.same_category_count` | `store_quarterly` | `store_count` |
| `direct.saturation_index` | `store_quarterly` | `store_count` / `dong_mapping.resident_pop` |
| `direct.radius_500m` | `store_info` | `lat`, `lon` (거리 계산) |
| `cannibalization.distance_m` | `store_info` | `lat`, `lon` |
| `indirect.store_count` | `store_quarterly` | `store_count` (다른 industry_code) |

#### `rent_avg` → `rent_cost` / `golmok_rent` 테이블

```sql
-- (A) 상권 단위 임대료 (빌딩/점포 평균)
SELECT rent, vacancy_rate
FROM rent_cost
WHERE data_type = 'building_rent'
  AND area_name = '망원역'        -- dong_mapping.trdar_codes로 상권 확인
  AND year = 2025
ORDER BY quarter DESC LIMIT 1;

-- (B) 행정동 단위 환산임대료 (1층 vs 기타층 구분 가능)
SELECT rent_1f, rent_other, rent_total
FROM golmok_rent
WHERE dong_code = '11440630'
  AND gubun = 'dong'
  AND year = 2024
ORDER BY quarter DESC LIMIT 1;
```

| DistrictData 필드 | DB 테이블 | DB 컬럼 | 비고 |
|---|---|---|---|
| `rent_avg` | `rent_cost` | `rent` (천원/m²) | 상권 단위, 공실률 포함 |
| `rent_avg` (대안) | `golmok_rent` | `rent_1f` / `rent_total` (원/3.3㎡) | 행정동 단위, 층별 구분 |

#### `closure_rate` → `store_quarterly` 테이블

```sql
SELECT AVG(closure_rate) as closure_rate
FROM store_quarterly
WHERE dong_code = '11440630'
  AND quarter = 20244;
```

---

### 매출 예측 (AnalysisResults)

#### `estimated_monthly_revenue` → `district_sales` 테이블

```sql
-- 동/업종별 최근 4분기 평균 매출
SELECT ROUND(AVG(monthly_sales)) as avg_monthly_sales,
       ROUND(AVG(monthly_count)) as avg_monthly_count
FROM district_sales
WHERE dong_code = '11440630'
  AND industry_code = 'CS100001'
  AND quarter >= 20241;

-- 시간대별 매출 비중 (운영시간 분석)
SELECT time_00_06_sales, time_06_11_sales, time_11_14_sales,
       time_14_17_sales, time_17_21_sales, time_21_24_sales
FROM district_sales
WHERE dong_code = '11440630'
  AND industry_code = 'CS100001'
  AND quarter = 20244;

-- 연령대별 매출 (타겟 고객층 분석)
SELECT age_10_sales, age_20_sales, age_30_sales,
       age_40_sales, age_50_sales, age_60_above_sales
FROM district_sales
WHERE dong_code = '11440630'
  AND industry_code = 'CS100001'
  AND quarter = 20244;
```

| AnalysisResults 필드 | DB 테이블 | DB 컬럼 |
|---|---|---|
| `estimated_monthly_revenue` | `district_sales` | `monthly_sales` (AVG) |
| `bep_months` | `district_sales` + `rent_cost` | 매출 - 비용으로 계산 |

---

### 골목상권 상세 데이터 (Commercial Node)

#### `golmok_commercial` 테이블 (JSONB)

```sql
-- 특정 상권의 매출 데이터
SELECT quarter, metrics
FROM golmok_commercial
WHERE trdar_code = '3110564'     -- 홍대입구역 3번
  AND data_type = 'sales'
  AND industry_code = 'CS100001'
ORDER BY quarter DESC LIMIT 4;

-- metrics JSONB 내부 필드 접근
SELECT quarter,
       (metrics->>'THSMON_SELNG_AMT')::bigint as monthly_sales,
       (metrics->>'MDWK_SELNG_AMT')::bigint as weekday_sales
FROM golmok_commercial
WHERE data_type = 'sales'
  AND trdar_code = '3110564';
```

| data_type | metrics 주요 필드 |
|---|---|
| `sales` | THSMON_SELNG_AMT, THSMON_SELNG_CO, MDWK/WKEND, 시간대별, 성별, 연령대별 |
| `stores` | STOR_CO, OPBIZ_STOR_CO, CLSBIZ_STOR_CO, CLSBIZ_RT, FRC_STOR_CO |
| `floating_pop` | TOT_FLPOP_CO, ML_FLPOP_CO, FML_FLPOP_CO, 연령대별 |
| `worker_pop` | TOT_WRC_POPLTN_CO, ML/FML, 연령대별 |
| `index` | 상권활성화지수 등 |
| `change` | 상권변화지표 |

---

### 동 마스터 조회

#### `dong_mapping` 테이블 (16행)

```sql
-- 전체 동 목록
SELECT dong_code, dong_name, resident_pop, floating_pop, avg_age, total_households
FROM dong_mapping ORDER BY dong_name;

-- 특정 동의 상권코드 목록
SELECT dong_name, trdar_codes
FROM dong_mapping
WHERE dong_code = '11440630';
-- trdar_codes: ["3110564", "3110571", ...]
```

---

## 외부 수집 실시간 데이터

### `kakao_store` — 카카오 로컬 API 실시간 점포

`store_info`(소상공인진흥공단 스냅샷) 보완 — 프랜차이즈 브랜드 실시간 집계용.

```sql
-- 동별 특정 브랜드 점포 수 (정규화된 브랜드명 기준)
SELECT dong_name, COUNT(*) as store_count
FROM kakao_store
WHERE brand_name = '스타벅스'
GROUP BY dong_name
ORDER BY store_count DESC;

-- 업종별 점포 + 위경도 (반경 기반 경쟁 분석)
SELECT place_name, brand_name, lat, lon
FROM kakao_store
WHERE dong_name = '합정동'
  AND category = '카페';
```

| 용도 | DB 컬럼 |
|---|---|
| 특정 브랜드 마포구 전체 점포 수 | `brand_name` (=) + COUNT |
| 업종별 실시간 점포 위치 | `category`, `lat`, `lon` |
| 주소·전화·URL | `address`, `road_address`, `phone`, `place_url` |

### `naver_vacancy` — 네이버 부동산 상가 공실

`rent_cost.vacancy_rate` 보완 — 실시간 매물 현황으로 공실 체감도 산출.

```sql
-- 동별 매물 건수 (거래유형별)
SELECT dong_name, trade_type, SUM(listing_count) as total_listings
FROM naver_vacancy
WHERE dong_name = '합정동'
GROUP BY dong_name, trade_type;
```

| 용도 | DB 컬럼 |
|---|---|
| 동별 매물 수 | `dong_name`, `listing_count` |
| 거래 유형 (매매/전세/월세) | `trade_type`, `trade_code` |
| 위경도 (지도 시각화) | `lat`, `lon` |

### `brand_logo` — 브랜드 로고 URL

UI 렌더링용 — `biz_brand_mapping.brand_name` 로 JOIN.

```sql
-- 회원의 브랜드 로고 조회
SELECT bl.logo_url, bl.logo_source
FROM biz_brand_mapping bbm
LEFT JOIN brand_logo bl ON bbm.brand_name = bl.brand_name
WHERE bbm.biz_number = '1208137942';
```

| 용도 | DB 컬럼 |
|---|---|
| 로고 URL | `logo_url` |
| 수집 소스 (naver / clearbit 등) | `logo_source` |

---

## 행정동코드 참조

| dong_code | dong_name | 비고 |
|-----------|-----------|------|
| 11440520 | 아현동 | |
| 11440530 | 공덕동 | MVP |
| 11440540 | 도화동 | |
| 11440550 | 용강동 | |
| 11440560 | 대흥동 | MVP |
| 11440570 | 염리동 | |
| 11440580 | 신수동 | |
| 11440590 | 서강동 | |
| 11440600 | 서교동 | |
| 11440610 | 합정동 | |
| 11440620 | 망원1동 | MVP |
| 11440660 | 망원2동 | |
| 11440640 | 연남동 | |
| 11440710 | 성산1동 | |
| 11440720 | 성산2동 | |
| 11440740 | 상암동 | |

## 업종코드 참조 (주요)

| industry_code | industry_name | constants.py 매핑 |
|---|---|---|
| CS100001 | 한식음식점 | restaurant |
| CS100002 | 중식음식점 | - |
| CS100003 | 일식음식점 | - |
| CS100010 | 커피-음료 | cafe |
| CS200001 | 편의점 | convenience |
| CS200002 | 슈퍼마켓 | - |
| CS300007 | 미용실 | - |

> 캐노니컬 매핑 소스: `backend/src/agents/tools.py` 의 `_BIZ_TO_INDUSTRY_CODE` 딕셔너리 참고.

## 시뮬레이션 결과 저장

```sql
-- 결과 저장 (SimulationOutput → JSONB, workspace_id 로 멀티테넌시 분리)
INSERT INTO simulation_result (request_id, workspace_id, input_params, output_result, status)
VALUES (
    gen_random_uuid(),
    'ws_user_123',                   -- 팀장 회원 ID 기반 워크스페이스
    '{"business_type": "cafe", "target_district": "망원1동", ...}'::jsonb,
    '{"monthly_projection": [...], "comparison": [...], ...}'::jsonb,
    'completed'
);

-- 워크스페이스별 결과 조회 (인덱스 ix_simulation_result_workspace 활용)
SELECT request_id, created_at, status,
       output_result->'ai_recommendation' as recommendation
FROM simulation_result
WHERE workspace_id = 'ws_user_123'
ORDER BY created_at DESC;

-- 단건 조회
SELECT * FROM simulation_result WHERE request_id = 'uuid-here';
```
