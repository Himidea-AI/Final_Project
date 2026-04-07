# PostgreSQL 테이블·컬럼 정의서

> DB: `mapo_simulator` | 12개 테이블

---

## 1. living_population — 행정동 시간대별 유동인구

> 968,064행 | 출처: 서울 열린데이터광장 (KT 통신 데이터)
> 기간: 2019.02 ~ 2026.02 | 단위: 일별 × 시간대 × 16개 동

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `date` | date | 기준 날짜 | 2024-01-15 |
| `time_zone` | bigint | 시간대 (0=일합계, 1~23=시간대) | 0 |
| `dong_code` | text | 행정동코드 | 11440630 |
| `dong_name` | text | 행정동명 | 망원1동 |
| `total_pop` | float | 총 생활인구수 | 17043.5 |
| `male_0_9` | float | 남자 0~9세 | 481.4 |
| `male_10_14` | float | 남자 10~14세 | 306.8 |
| `male_15_19` | float | 남자 15~19세 | 478.2 |
| `male_20_24` | float | 남자 20~24세 | 357.4 |
| `male_25_29` | float | 남자 25~29세 | 397.9 |
| `male_30_34` | float | 남자 30~34세 | 361.7 |
| `male_35_39` | float | 남자 35~39세 | 474.9 |
| `male_40_44` | float | 남자 40~44세 | 493.8 |
| `male_45_49` | float | 남자 45~49세 | 609.4 |
| `male_50_54` | float | 남자 50~54세 | 638.8 |
| `male_55_59` | float | 남자 55~59세 | 392.3 |
| `male_60_64` | float | 남자 60~64세 | 331.3 |
| `male_65_69` | float | 남자 65~69세 | 242.0 |
| `male_70_plus` | float | 남자 70세 이상 | 557.0 |
| `female_0_9` | float | 여자 0~9세 | 699.5 |
| `female_10_14` | float | 여자 10~14세 | 419.1 |
| `female_15_19` | float | 여자 15~19세 | 421.1 |
| `female_20_24` | float | 여자 20~24세 | 357.8 |
| `female_25_29` | float | 여자 25~29세 | 414.9 |
| `female_30_34` | float | 여자 30~34세 | 453.7 |
| `female_35_39` | float | 여자 35~39세 | 628.8 |
| `female_40_44` | float | 여자 40~44세 | 683.6 |
| `female_45_49` | float | 여자 45~49세 | 727.1 |
| `female_50_54` | float | 여자 50~54세 | 618.4 |
| `female_55_59` | float | 여자 55~59세 | 572.5 |
| `female_60_64` | float | 여자 60~64세 | 473.1 |
| `female_65_69` | float | 여자 65~69세 | 344.3 |
| `female_70_plus` | float | 여자 70세 이상 | 1022.6 |

---

## 2. sgis_population — SGIS 인구통계

> 189,379행 | 출처: 통계청 SGIS 소지역통계
> 기간: 2020~2024 | 단위: 소지역(집계구) × 연도 × 지표

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `year` | bigint | 연도 | 2024 |
| `area_code` | text | 소지역/집계구 코드 (14자리) | 11140730020201 |
| `indicator` | text | 지표명 | to_in_001 (총인구) |
| `value` | float | 값 | 568.0 |

**indicator 종류**: 총인구(`to_in_001`), 평균나이, 인구밀도, 노령화지수, 성연령별인구, 주민등록인구(`resident_*`), 인구통계(`demo_*`)

---

## 3. sgis_household — SGIS 가구통계

> 23,109행 | 출처: 통계청 SGIS
> 기간: 2020~2024 | 단위: 소지역 × 연도 × 지표

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `year` | bigint | 연도 | 2024 |
| `area_code` | text | 소지역 코드 | 11140730020201 |
| `indicator` | text | 지표명 | total (총가구), composition (가구구성) |
| `value` | float | 값 | 245.0 |

---

## 4. sgis_business — SGIS 사업체통계

> 54,971행 | 출처: 통계청 SGIS
> 기간: 2020~2023 | 단위: 소지역 × 연도 × 지표

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `year` | bigint | 연도 | 2023 |
| `area_code` | text | 소지역 코드 | 11140730020201 |
| `indicator` | text | 지표명 | major_count, major_workers, mid_count, mid_workers |
| `value` | float | 값 | 12.0 |

---

## 5. golmok_commercial — 골목상권 종합

> 178,840행 | 출처: 서울 상권분석서비스 API
> 기간: 2019 Q1 ~ 2024 Q4 | 단위: 상권 × 분기 × 업종

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `quarter` | bigint | 분기 (YYYYQ) | 20244 |
| `trdar_code` | text | 상권코드 | 3110564 |
| `data_type` | text | 데이터 유형 | sales, stores, floating_pop, worker_pop, index, change |
| `industry_code` | text | 업종코드 (없으면 ALL) | CS100001 |
| `metrics` | text (JSON) | 세부 지표 (JSONB) | {"THSMON_SELNG_AMT": 417851468, ...} |

**data_type별 metrics 주요 필드:**

| data_type | metrics 필드 |
|-----------|-------------|
| `sales` | THSMON_SELNG_AMT(매출액), THSMON_SELNG_CO(매출건수), 요일별, 시간대별, 성별, 연령대별 |
| `stores` | STOR_CO(점포수), OPBIZ_STOR_CO(개업수), CLSBIZ_STOR_CO(폐업수), CLSBIZ_RT(폐업률) |
| `floating_pop` | TOT_FLPOP_CO(유동인구), ML/FML_FLPOP_CO(성별), 연령대별 |
| `worker_pop` | TOT_WRC_POPLTN_CO(직장인구), 성별, 연령대별 |
| `index` | 상권활성화지수 등 |
| `change` | 상권변화지표 |

---

## 6. district_sales — 행정동 추정매출

> 16,951행 | 출처: 서울 상권분석서비스 (추정매출-행정동)
> 기간: 2019 Q1 ~ 2024 Q4 | 단위: 행정동 × 분기 × 업종

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `quarter` | bigint | 분기 (YYYYQ) | 20244 |
| `dong_code` | text | 행정동코드 | 11440630 |
| `dong_name` | text | 행정동명 | 망원1동 |
| `industry_code` | text | 업종코드 | CS100001 |
| `industry_name` | text | 업종명 | 한식음식점 |
| `monthly_sales` | bigint | 당월 매출 금액 (원) | 4088925153 |
| `monthly_count` | bigint | 당월 매출 건수 | 117858 |
| `weekday_sales` | bigint | 주중 매출 | 2891234567 |
| `weekend_sales` | bigint | 주말 매출 | 1197690586 |
| `mon_sales` | bigint | 월요일 매출 | 381912382 |
| `tue_sales` | bigint | 화요일 매출 | 465137733 |
| `wed_sales` | bigint | 수요일 매출 | 455857239 |
| `thu_sales` | bigint | 목요일 매출 | 521200333 |
| `fri_sales` | bigint | 금요일 매출 | 535612960 |
| `sat_sales` | bigint | 토요일 매출 | 593613095 |
| `sun_sales` | bigint | 일요일 매출 | 328702407 |
| `time_00_06_sales` | bigint | 00~06시 매출 | 1316988 |
| `time_06_11_sales` | bigint | 06~11시 매출 | 47684080 |
| `time_11_14_sales` | bigint | 11~14시 매출 | 1398266584 |
| `time_14_17_sales` | bigint | 14~17시 매출 | 481428971 |
| `time_17_21_sales` | bigint | 17~21시 매출 | 1178943239 |
| `time_21_24_sales` | bigint | 21~24시 매출 | 174396287 |
| `male_sales` | bigint | 남성 매출 | 1432278317 |
| `female_sales` | bigint | 여성 매출 | 1086069188 |
| `age_10_sales` | bigint | 10대 매출 | 6056404 |
| `age_20_sales` | bigint | 20대 매출 | 290082685 |
| `age_30_sales` | bigint | 30대 매출 | 576388693 |
| `age_40_sales` | bigint | 40대 매출 | 525073149 |
| `age_50_sales` | bigint | 50대 매출 | 557543338 |
| `age_60_above_sales` | bigint | 60대 이상 매출 | 563203225 |
| `weekday_count` | bigint | 주중 매출건수 | 74610 |
| `weekend_count` | bigint | 주말 매출건수 | 27882 |
| `mon_count` ~ `sun_count` | bigint | 요일별 건수 | 13661 |
| `time_00_06_count` ~ `time_21_24_count` | bigint | 시간대별 건수 | 20 |
| `male_count` / `female_count` | bigint | 성별 건수 | 49367 |
| `age_10_count` ~ `age_60_above_count` | bigint | 연령대별 건수 | 470 |

---

## 7. store_info — 개별 점포 정보

> 30,488행 | 출처: 소상공인시장진흥공단
> 기준: 2025년 12월 스냅샷

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `store_id` | text | 상가업소번호 (PK) | MA0001234567 |
| `store_name` | text | 상호명 | 스타벅스 망원점 |
| `dong_code` | text | 행정동코드 | 11440630 |
| `dong_name` | text | 행정동명 | 망원1동 |
| `address` | text | 지번주소 | 마포구 망원동 123-4 |
| `road_address` | text | 도로명주소 | 마포구 월드컵로 123 |
| `lat` | float | 위도 | 37.5565 |
| `lon` | float | 경도 | 126.9010 |
| `industry_l_code` | text | 대분류 코드 | Q |
| `industry_l` | text | 대분류명 | 음식 |
| `industry_m_code` | text | 중분류 코드 | Q12 |
| `industry_m` | text | 중분류명 | 커피점/카페 |
| `industry_s_code` | text | 소분류 코드 | Q12A01 |
| `industry_s` | text | 소분류명 | 커피전문점/카페/다방 |
| `building_name` | text | 건물명 | 망원빌딩 |
| `floor_info` | text | 층정보 | 1 |

---

## 8. store_quarterly — 분기별 점포 집계

> 28,305행 | 출처: 서울 상권분석서비스
> 기간: 2019 Q1 ~ 2024 Q4 | 단위: 행정동 × 분기 × 업종

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `quarter` | bigint | 분기 (YYYYQ) | 20244 |
| `dong_code` | text | 행정동코드 | 11440630 |
| `dong_name` | text | 행정동명 | 망원1동 |
| `industry_code` | text | 업종코드 | CS100001 |
| `industry_name` | text | 업종명 | 한식음식점 |
| `store_count` | bigint | 점포수 | 45 |
| `open_count` | bigint | 개업 점포수 | 3 |
| `close_count` | bigint | 폐업 점포수 | 2 |
| `closure_rate` | float | 폐업률 (%) | 4.4 |
| `franchise_count` | bigint | 프랜차이즈 점포수 | 8 |

---

## 9. rent_cost — 임대료·실거래가 통합

> 260행 | 출처: 한국부동산원
> 기간: 2019~2025 (분기별)

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `data_type` | text | 데이터 유형 | building_rent, rent_small_store |
| `area_name` | text | 지역명 | 공덕역 |
| `year` | bigint | 연도 | 2025 |
| `quarter` | bigint | 분기 | 4 |
| `rent` | float | 임대료 (천원/m2) | 40.2 |
| `vacancy_rate` | float | 공실률 (%) | 6.4 |
| `investment_return` | float | 투자수익률 (%) | 2.10 |
| `income_return` | float | 소득수익률 (%) | 0.71 |
| `capital_return` | float | 자본수익률 (%) | 1.40 |
| `source` | text | 데이터 출처 | building_rent |

**data_type 구분:**
- `building_rent` — 매장용빌딩 임대료 (분기별, 248행)
- `rent_small_store` — 소형점포 임대료 (분기별, 12행)

---

## 10. golmok_rent — 행정동별 환산임대료

> 408행 | 출처: 서울 상권분석서비스 (신용보증재단 기반)
> 기간: 2019 Q1 ~ 2024 Q4 | 단위: 행정동 × 분기

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `year` | smallint | 기준 연도 | 2024 |
| `quarter` | smallint | 기준 분기 | 4 |
| `dong_code` | text | 행정동코드 | 11440555 |
| `dong_name` | text | 행정동명 | 상암동 |
| `gubun` | text | 구분 | gu (구 전체) / dong (동) |
| `rent_1f` | int | 1층 환산임대료 (원/3.3㎡) | 217202 |
| `rent_other` | int | 1층 외 환산임대료 (원/3.3㎡) | 124751 |
| `rent_total` | int | 전체 환산임대료 (원/3.3㎡) | 170977 |

**참고:** 환산임대료 = (보증금 × 12%) / 12 + 월세. 서울신용보증재단 보증 고객 통계 기반 추정값.

---

## 11. dong_mapping — 행정동 마스터

> 16행 | 마포구 16개 동 기본 정보

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `dong_code` | text | 행정동코드 (PK) | 11440630 |
| `dong_name` | text | 행정동명 | 망원1동 |
| `resident_pop` | bigint | 주민등록인구 (2024) | 43960 |
| `floating_pop` | float | 평균 생활인구 | 3603433 |
| `avg_age` | float | 평균나이 | 40.9 |
| `total_households` | float | 총 가구수 | 14138.6 |
| `trdar_codes` | text (JSON) | 해당 동의 상권코드 목록 | ["3110564", "3110571"] |

**16개 동 목록:**

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
| 11440640 | 연남동 | |
| 11440660 | 망원2동 | |
| 11440710 | 성산1동 | |
| 11440720 | 성산2동 | |
| 11440740 | 상암동 | |

---

## 11. simulation_result — 시뮬레이션 결과

> 0행 (가변) | 시뮬레이션 입력/출력 저장

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `request_id` | uuid | PK | a1b2c3d4-... |
| `created_at` | date | 생성일 | 2026-04-06 |
| `input_params` | jsonb | 시뮬레이션 입력 | {"business_type": "cafe", ...} |
| `output_result` | jsonb | 시뮬레이션 결과 | {"monthly_projection": [...], ...} |
| `status` | varchar(20) | 상태 | pending / running / completed / failed |

---

## 주요 업종코드 참조

| industry_code | industry_name | 프로젝트 매핑 |
|---|---|---|
| CS100001 | 한식음식점 | restaurant |
| CS100002 | 중식음식점 | - |
| CS100003 | 일식음식점 | - |
| CS100010 | 커피-음료 | cafe |
| CS200001 | 편의점 | convenience |
| CS200002 | 슈퍼마켓 | - |
| CS300007 | 미용실 | - |

---

## 접속 정보

```
Host: localhost
Port: 5432
Database: mapo_simulator
User: postgres
Password: 각자 로컬 PostgreSQL 설치 시 설정한 비밀번호
```
