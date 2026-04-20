# PostgreSQL 테이블·컬럼 정의서

> DB: `mapo_simulator` | 29개 테이블
> 출처: `backend/src/database/models.py` + `backend/alembic/versions/*` (revision b2d4e8f1c7a3 기준)
> 최종 갱신: 2026-04-17

---

## 데이터 도메인 구분

| 도메인 | 테이블 |
|--------|--------|
| 인구 통계 (마포) | living_population, sgis_population, sgis_household, sgis_business, mapo_resident_pop |
| 상권/매출 (마포) | golmok_commercial, district_sales, golmok_sales, golmok_stores |
| 점포 | store_info, store_quarterly |
| 임대료 | rent_cost, golmok_rent, small_store_rent_q |
| 마스터 | dong_mapping |
| 시뮬레이션 | simulation_result |
| 회원/인증 | users, manager_users, invite_codes |
| 브랜드 | ftc_brand_franchise, biz_brand_mapping, brand_logo |
| 외부 수집 | naver_vacancy, kakao_store |
| 서울 전체 (LSTM 사전학습) | seoul_district_sales, seoul_district_stores, seoul_population_quarterly, seoul_golmok_rent, seoul_training_dataset |
| 보정 지표 | cpi_dining_quarterly |

---

## 1. living_population — 행정동 시간대별 생활인구

> 출처: 서울 열린데이터광장 (KT 통신 데이터) | 단위: 일별 × 시간대 × 16개 동
> PK: (date, time_zone, dong_code)

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `date` | date | 기준 날짜 (PK) | 2024-01-15 |
| `time_zone` | smallint | 시간대 구분 (0=일합계, 1~23) (PK) | 0 |
| `dong_code` | varchar(10) | 행정동 코드 (PK) | 11440630 |
| `dong_name` | varchar(20) | 행정동명 | 망원1동 |
| `total_pop` | float | 전체 생활인구 | 17043.5 |
| `male_0_9` ~ `male_70_74`, `male_70_plus` | float | 남성 5세 단위 연령대 (15구간) | 481.4 |
| `female_0_9` ~ `female_70_74`, `female_70_plus` | float | 여성 5세 단위 연령대 (15구간) | 699.5 |

**주의**: `male_70_74`/`female_70_74`와 `male_70_plus`/`female_70_plus`가 모두 존재 (원천 데이터 포맷 변경 흡수용).

---

## 2. sgis_population — SGIS 인구통계

> 출처: 통계청 SGIS 소지역통계 | 기간: 2020~2024 | 단위: 소지역 × 연도 × 지표
> PK: (year, area_code, indicator)

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `year` | smallint | 기준 연도 (PK) | 2024 |
| `area_code` | varchar(14) | 소지역/집계구 코드 (PK) | 11140730020201 |
| `indicator` | varchar(30) | 지표명 (PK) | to_in_001 |
| `value` | float | 지표 값 | 568.0 |

**indicator 종류**: 총인구(`to_in_001`), 평균나이, 인구밀도, 노령화지수, 성연령별인구, 주민등록인구(`resident_*`), 인구통계(`demo_*`)

---

## 3. sgis_household — SGIS 가구통계

> 출처: 통계청 SGIS | 기간: 2020~2024
> PK: (year, area_code, indicator)

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `year` | smallint | 기준 연도 (PK) | 2024 |
| `area_code` | varchar(14) | 소지역 코드 (PK) | 11140730020201 |
| `indicator` | varchar(30) | 지표명 (PK) | total / composition |
| `value` | float | 값 | 245.0 |

---

## 4. sgis_business — SGIS 사업체통계

> 출처: 통계청 SGIS | 기간: 2020~2023
> PK: (year, area_code, indicator)

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `year` | smallint | 기준 연도 (PK) | 2023 |
| `area_code` | varchar(14) | 소지역 코드 (PK) | 11140730020201 |
| `indicator` | varchar(30) | 지표명 (PK) | major_count, major_workers, mid_count, mid_workers |
| `value` | float | 값 | 12.0 |

---

## 5. golmok_commercial — 골목상권 종합지표

> 출처: 서울 우리마을가게 상권분석서비스 | 기간: 2019 Q1 ~ 2024 Q4 | 단위: 상권 × 분기 × 업종
> PK: id (auto-increment) | 인덱스: quarter, data_type

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | int (PK, auto) | 자동증가 PK | 1 |
| `quarter` | int | 분기 (YYYYQ) | 20244 |
| `trdar_code` | varchar(10) | 상권코드 | 3110564 |
| `data_type` | varchar(20) | 데이터 유형 | sales / store / population 등 |
| `industry_code` | varchar(20) | 업종코드 (없으면 ALL) | CS100001 |
| `metrics` | jsonb | 세부 지표 (JSON) | {"THSMON_SELNG_AMT": 417851468, ...} |

**data_type별 metrics 주요 필드:**

| data_type | metrics 필드 |
|-----------|-------------|
| `sales` | THSMON_SELNG_AMT(매출액), THSMON_SELNG_CO(매출건수), 요일/시간대/성별/연령대별 |
| `stores` | STOR_CO(점포수), OPBIZ_STOR_CO(개업), CLSBIZ_STOR_CO(폐업), CLSBIZ_RT(폐업률) |
| `floating_pop` | TOT_FLPOP_CO, ML/FML_FLPOP_CO, 연령대별 |
| `worker_pop` | TOT_WRC_POPLTN_CO, 성별/연령대별 |
| `index` | 상권활성화지수 |
| `change` | 상권변화지표 |

---

## 6. district_sales — 행정동 추정매출

> 출처: 서울 상권분석서비스(추정매출-행정동) | 기간: 2019 Q1 ~ 2024 Q4
> PK: (quarter, dong_code, industry_code) | 인덱스: dong_code

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `quarter` | int | 분기 (YYYYQ) (PK) | 20244 |
| `dong_code` | varchar(10) | 행정동코드 (PK) | 11440630 |
| `industry_code` | varchar(20) | 업종코드 (PK) | CS100001 |
| `dong_name` | varchar(20) | 행정동명 | 망원1동 |
| `industry_name` | varchar(50) | 업종명 | 한식음식점 |
| `monthly_sales` | bigint | 당월 매출 금액 (원) | 4088925153 |
| `monthly_count` | int | 당월 매출 건수 | 117858 |
| `weekday_sales` / `weekend_sales` | bigint | 평일/주말 매출 | — |
| `mon_sales` ~ `sun_sales` | bigint | 요일별 매출 | — |
| `time_00_06_sales` ~ `time_21_24_sales` | bigint | 시간대별 매출 (6구간) | — |
| `male_sales` / `female_sales` | bigint | 성별 매출 | — |
| `age_10_sales` ~ `age_60_above_sales` | bigint | 연령대별 매출 (6구간) | — |
| `weekday_count` / `weekend_count` | int | 평일/주말 건수 | — |
| `mon_count` ~ `sun_count` | int | 요일별 건수 | — |
| `time_00_06_count` ~ `time_21_24_count` | int | 시간대별 건수 | — |
| `male_count` / `female_count` | int | 성별 건수 | — |
| `age_10_count` ~ `age_60_above_count` | int | 연령대별 건수 | — |

---

## 7. store_info — 개별 점포 정보

> 출처: 소상공인시장진흥공단 (스냅샷)
> PK: store_id | 인덱스: dong_code, dong_name, industry_m, industry_m_code

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `store_id` | varchar(20) | 상가업소번호 (PK) | MA0001234567 |
| `store_name` | varchar(100) | 상호명 | 스타벅스 망원점 |
| `dong_code` | varchar(10) | 행정동코드 | 11440630 |
| `dong_name` | varchar(20) | 행정동명 | 망원1동 |
| `address` | text | 지번주소 | 마포구 망원동 123-4 |
| `road_address` | text | 도로명주소 | 마포구 월드컵로 123 |
| `lat` / `lon` | float | 위도/경도 | 37.5565 / 126.9010 |
| `industry_l_code` / `industry_l` | varchar | 대분류 코드/명 | Q / 음식 |
| `industry_m_code` / `industry_m` | varchar | 중분류 코드/명 | Q12 / 커피점/카페 |
| `industry_s_code` / `industry_s` | varchar | 소분류 코드/명 | Q12A01 / 커피전문점 |
| `building_name` | varchar(100) | 건물명 | 망원빌딩 |
| `floor_info` | varchar(20) | 층정보 | 1 |

---

## 8. store_quarterly — 분기별 점포 집계

> 출처: 서울 상권분석서비스 | 기간: 2019 Q1 ~ 2024 Q4
> PK: (quarter, dong_code, industry_code) | 인덱스: dong_code

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `quarter` | int | 분기 (PK) | 20244 |
| `dong_code` | varchar(10) | 행정동코드 (PK) | 11440630 |
| `industry_code` | varchar(20) | 업종코드 (PK) | CS100001 |
| `dong_name` | varchar(20) | 행정동명 | 망원1동 |
| `industry_name` | varchar(50) | 업종명 | 한식음식점 |
| `store_count` | int | 점포수 | 45 |
| `open_count` | int | 개업 점포수 | 3 |
| `close_count` | int | 폐업 점포수 | 2 |
| `closure_rate` | float | 폐업률 (%) | 4.4 |
| `franchise_count` | int | 프랜차이즈 점포수 | 8 |

---

## 9. rent_cost — 임대료/실거래가

> 출처: 한국부동산원 | 기간: 2019~2025 (분기별)
> PK: id (auto) | 인덱스: data_type

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | int (PK, auto) | 자동증가 PK | 1 |
| `data_type` | varchar(20) | 데이터 유형 | building_rent / rent_small_store / transaction |
| `area_name` | varchar(50) | 지역명 | 공덕역 |
| `year` | smallint | 연도 | 2025 |
| `quarter` | smallint | 분기 | 4 |
| `rent` | float | 임대료 (만원/m²) | 40.2 |
| `vacancy_rate` | float | 공실률 (%) | 6.4 |
| `investment_return` | float | 투자수익률 (%) | 2.10 |
| `income_return` | float | 소득수익률 (%) | 0.71 |
| `capital_return` | float | 자본수익률 (%) | 1.40 |
| `transaction_date` | varchar(10) | 거래 일자 (실거래) | 2025-09-15 |
| `price` | bigint | 거래 금액 (만원) | — |
| `floor_area` | float | 전용 면적 (m²) | — |
| `floor` | varchar(10) | 층 정보 | — |
| `source` | varchar(20) | 데이터 출처 | building_rent |

**data_type 종류**: `building_rent`(매장용빌딩 임대료), `rent_small_store`(소형점포 임대료), `transaction`(실거래가)

---

## 9-1. small_store_rent_q — 소규모상가 임대료 원천 전수 (REB)

> 출처: 한국부동산원 R-ONE OpenAPI (`SttsApiTblData.do`, 7개 STATBL_ID 통합)
> 기간: 2015 Q1 ~ 2025 Q4 (분기, 11년, 276개 상권)
> 적재 스크립트: `scripts/collect_reb_small_store_rent.py`
> PK: id (auto) | UNIQUE: (cls_id, year, quarter) | 인덱스: region, (year, quarter)

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | bigserial (PK) | 자동증가 PK | 1 |
| `cls_id` | int | REB 지역 코드 (조인 키, 안정적 숫자) | 520004 |
| `cls_full_nm` | text | 전체 계층명 | `서울>도심>광화문` |
| `cls_nm` | text | 최하위 지역명 | `광화문` |
| `region` | text | `cls_full_nm` 동일값 (레거시 호환) | `서울>도심>광화문` |
| `year` | int | 연도 | 2025 |
| `quarter` | int | 분기 | 4 |
| `rent` | float | 임대료 (천원/㎡, 전용+공용) | 95.03 |
| `statbl_id` | text | 원천 통계표 ID (표본 재설정 경계 식별) | A_2024_00279 |

**참고**
- `rent_cost`의 `data_type='rent_small_store'`가 정제·요약본이라면, 이 테이블은 REB 원천을 그대로 long 포맷으로 보존한 전수 스냅샷입니다.
- 지역 조인은 `cls_id` 권장 (문자열 `region` 대비 안정).

---

## 10. golmok_rent — 행정동별 환산임대료

> 출처: 서울 상권분석서비스(신용보증재단 기반) | 기간: 2019 Q1 ~ 2024 Q4
> PK: id (auto) | 인덱스: year, dong_code

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | int (PK, auto) | 자동증가 PK | 1 |
| `year` | smallint | 기준 연도 | 2024 |
| `quarter` | smallint | 기준 분기 | 4 |
| `dong_code` | varchar(10) | 행정동코드 | 11440555 |
| `dong_name` | varchar(20) | 행정동명 | 상암동 |
| `gubun` | varchar(10) | 구분 (gu/dong) | dong |
| `rent_1f` | int | 1층 환산임대료 (원/3.3㎡) | 217202 |
| `rent_other` | int | 1층 외 환산임대료 (원/3.3㎡) | 124751 |
| `rent_total` | int | 전체 환산임대료 (원/3.3㎡) | 170977 |

**참고**: 환산임대료 = (보증금 × 12%) / 12 + 월세

---

## 11. dong_mapping — 행정동 마스터

> 마포구 16개 동 기본 정보
> PK: dong_code

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `dong_code` | varchar(10) | 행정동코드 (PK) | 11440630 |
| `dong_name` | varchar(20) | 행정동명 | 망원1동 |
| `resident_pop` | int | 주민등록인구 (2024) | 43960 |
| `floating_pop` | float | 평균 생활인구 | 3603433 |
| `avg_age` | float | 평균나이 | 40.9 |
| `total_households` | int | 총 가구수 | 14138 |
| `trdar_codes` | jsonb | 해당 동의 상권코드 목록 | ["3110564", "3110571"] |

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

## 12. simulation_result — 시뮬레이션 결과

> 시뮬레이션 입력/출력 저장
> PK: request_id | 인덱스: workspace_id

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `request_id` | uuid (PK) | 요청 고유 ID | a1b2c3d4-... |
| `created_at` | date | 생성일 | 2026-04-17 |
| `workspace_id` | varchar(100) | 워크스페이스 ID (멀티테넌시) | ws_001 |
| `input_params` | jsonb | 시뮬레이션 입력 | {"business_type": "cafe", ...} |
| `output_result` | jsonb | 시뮬레이션 결과 | {"monthly_projection": [...], ...} |
| `status` | varchar(20) | 상태 | pending / running / done / error |

---

## 13. users — 회원 (팀장)

> 프랜차이즈 본부 담당자 (팀장 권한)
> PK: id | 유니크: biz_number, email | 인덱스: email

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | uuid (PK) | 회원 고유 ID | — |
| `company_name` | varchar(100) | 기업명 (프랜차이즈 본부) | (주)스타벅스코리아 |
| `biz_number` | varchar(12) | 사업자등록번호 (UNIQUE) | 1208137942 |
| `contact_name` | varchar(50) | 담당자명 | 홍길동 |
| `position` | varchar(50) | 직책 | 매니저 |
| `email` | varchar(100) | 업무용 이메일 (UNIQUE) | hong@example.com |
| `phone` | varchar(20) | 연락처 | 010-1234-5678 |
| `store_count` | int | 현재 가맹점 수 | 150 |
| `password_hash` | varchar(255) | 비밀번호 해시 | bcrypt(...) |
| `plan` | varchar(20) | 요금제 | starter / growth |
| `agree_terms` | bool | 이용약관 동의 | true |
| `created_at` | timestamptz | 가입 일시 | 2026-04-17 |

---

## 14. ftc_brand_franchise — 공정거래위원회 프랜차이즈 브랜드

> 회원가입 시 브랜드 자동 매핑용
> PK: id (auto) | 인덱스: yr, brandNm

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | int (PK, auto) | 자동증가 PK | 1 |
| `yr` | smallint | 기준 연도 | 2023 |
| `corpNm` | varchar(200) | 법인명 | (주)스타벅스코리아 |
| `brandNm` | varchar(200) | 브랜드명 | 스타벅스 |
| `indutyLclasNm` | varchar(50) | 업종 대분류명 | 외식 |
| `indutyMlsfcNm` | varchar(50) | 업종 중분류명 | 커피 |
| `frcsCnt` | int | 가맹점 수 | 1700 |
| `newFrcsRgsCnt` | int | 신규 가맹점 등록 수 | 50 |
| `ctrtEndCnt` | int | 계약 종료 수 | 10 |
| `ctrtCncltnCnt` | int | 계약 해지 수 | 5 |
| `nmChgCnt` | int | 명칭 변경 수 | 0 |
| `avrgSlsAmt` | bigint | 평균 매출액 (천원) | 850000 |
| `arUnitAvrgSlsAmt` | bigint | 면적당 평균 매출액 | 12500 |

---

## 15. biz_brand_mapping — 사업자번호 ↔ 브랜드 매핑

> 회원가입 시 자동 축적 (FTC 브랜드 + 마포구 점포 카운트 결합)
> PK: biz_number

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `biz_number` | varchar(12) (PK) | 사업자등록번호 (하이픈 제거) | 1208137942 |
| `company_name` | varchar(100) | 기업명 (법인명) | (주)스타벅스코리아 |
| `brand_name` | varchar(100) | 매핑된 브랜드명 | 스타벅스 |
| `industry_large` | varchar(50) | 업종 대분류 | 외식 |
| `industry_medium` | varchar(50) | 업종 중분류 | 커피 |
| `franchise_count` | int | 전국 가맹점 수 | 1700 |
| `avg_sales` | bigint | 평균매출 (천원) | 850000 |
| `mapo_store_count` | int | 마포구 점포 수 | 12 |
| `created_at` | timestamptz | 등록 일시 | 2026-04-17 |

---

## 16. naver_vacancy — 네이버 부동산 상가 공실

> 출처: 네이버 부동산 (마포구 상가 매물)
> PK: id (auto) | 인덱스: dong_name

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | int (PK, auto) | 자동증가 PK | 1 |
| `trade_type` | varchar(10) | 거래유형 | 매매 / 전세 / 월세 |
| `trade_code` | varchar(5) | 거래코드 | B1 / B2 / B3 |
| `lat` / `lon` | float | 위도/경도 | 37.5565 / 126.9010 |
| `listing_count` | int | 매물 건수 | 5 |
| `dong_name` | varchar(20) | 행정동명 | 합정동 |
| `lgeo` | varchar(30) | 네이버 지오코드 | — |
| `collected_at` | timestamptz | 수집 일시 | 2026-04-17 |

---

## 17. kakao_store — 카카오 로컬 API 실시간 점포

> 출처: 카카오 로컬 API (마포구 프랜차이즈 브랜드)
> PK: kakao_id | 인덱스: brand_name, category, dong_name

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `kakao_id` | varchar(20) (PK) | 카카오 장소 ID | 12345678 |
| `place_name` | varchar(200) | 장소명 (점포명) | 스타벅스 합정역점 |
| `brand_name` | varchar(100) | 정규화된 브랜드명 | 스타벅스 |
| `category` | varchar(30) | 10대 업종 카테고리 | 카페 |
| `category_detail` | varchar(200) | 카카오 카테고리 상세 | 음식점 > 카페 > 커피전문점 |
| `address` | text | 지번 주소 | — |
| `road_address` | text | 도로명 주소 | — |
| `dong_name` | varchar(20) | 행정동명 | 합정동 |
| `lat` / `lon` | float | 위도/경도 | 37.5491 / 126.9145 |
| `phone` | varchar(20) | 전화번호 | 02-1234-5678 |
| `place_url` | text | 카카오맵 URL | https://place.map.kakao.com/... |
| `collected_at` | timestamptz | 수집 일시 | 2026-04-17 |

---

## 18. invite_codes — 초대코드

> 팀장(users)이 발급, 매니저 가입 시 사용
> PK: id (auto) | 유니크/인덱스: code | FK: owner_id → users.id (CASCADE)

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | int (PK, auto) | 자동증가 PK | 1 |
| `code` | varchar(20) | 초대코드 (8자리, UNIQUE) | A1B2C3D4 |
| `owner_id` | uuid | 발급한 팀장 ID (FK) | — |
| `max_uses` | int | 최대 사용 가능 횟수 (default 10) | 10 |
| `used_count` | int | 현재 사용된 횟수 (default 0) | 3 |
| `is_active` | bool | 활성 여부 (default true) | true |
| `created_at` | timestamptz | 발급 일시 | 2026-04-17 |
| `expires_at` | timestamptz | 만료 일시 (NULL이면 무제한) | NULL |

---

## 19. manager_users — 매니저 회원

> 팀장의 초대코드로 가입, 기업정보는 팀장에서 상속
> PK: id | 유니크/인덱스: email | 인덱스: owner_id
> FK: owner_id → users.id (CASCADE), invite_code_id → invite_codes.id

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | uuid (PK) | 매니저 고유 ID | — |
| `owner_id` | uuid | 소속 팀장 ID (FK) | — |
| `invite_code_id` | int | 사용한 초대코드 ID (FK) | 1 |
| `contact_name` | varchar(50) | 매니저 이름 | 김매니저 |
| `position` | varchar(50) | 직책 | 점포관리 |
| `email` | varchar(100) | 이메일 (UNIQUE) | manager@example.com |
| `phone` | varchar(20) | 연락처 | 010-9999-8888 |
| `password_hash` | varchar(255) | 비밀번호 해시 | bcrypt(...) |
| `is_active` | bool | 활성 여부 (default true) | true |
| `is_approved` | bool | 팀장 승인 여부 (default false) | true |
| `assigned_gu` | varchar(20) | 담당 구 | 마포구 |
| `assigned_dongs` | json | 담당 행정동 배열 | ["서교동","합정동"] |
| `created_at` | timestamptz | 가입 일시 | 2026-04-17 |

---

## 20. brand_logo — 브랜드 로고 수집

> 출처: 네이버 브랜드 검색 / 공식 도메인 크롤링
> PK: brand_name

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `brand_name` | varchar(100) (PK) | 브랜드명 | 스타벅스 |
| `domain` | varchar(100) | 공식 도메인 | starbucks.co.kr |
| `logo_url` | text | 로고 이미지 URL | https://.../logo.png |
| `logo_source` | varchar(30) | 수집 소스 | naver / clearbit / manual |
| `collected_at` | timestamptz | 수집 일시 | 2026-04-17 |

---

## 21. cpi_dining_quarterly — 분기별 외식 소비자물가지수

> 출처: 통계청 소비자물가지수(외식 부문)
> PK: id (auto)

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | int (PK, auto) | 자동증가 PK | 1 |
| `quarter` | bigint | 분기 (YYYYQ) | 20244 |
| `cpi_index` | float | CPI 외식 지수 (2020=100) | 118.4 |

---

## 22. golmok_sales — 골목상권 분기 매출

> 출처: 서울 우리마을가게 상권분석서비스 (trdar_code 단위)
> PK: id (auto) | 인덱스: quarter, trdar_code

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | int (PK, auto) | 자동증가 PK | 1 |
| `quarter` | bigint | 분기 (YYYYQ) | 20244 |
| `trdar_code` | text | 상권 코드 | 3110540 |
| `industry_code` | text | 업종 코드 | CS100001 |
| `monthly_sales` | bigint | 월평균 매출 | — |
| `monthly_count` | bigint | 월평균 건수 | — |
| `weekday_sales` / `weekend_sales`, `mon_sales` ~ `sun_sales` | bigint | 요일별 매출 | — |
| `time_00_06_sales` ~ `time_21_24_sales` | bigint | 시간대별 매출 (6구간) | — |
| `male_sales` / `female_sales`, `age_10_sales` ~ `age_60_above_sales` | bigint | 성별·연령별 매출 | — |
| (같은 그룹의 `*_count` 컬럼) | bigint | 동일 분류 건수 | — |

---

## 23. golmok_stores — 골목상권 분기 점포

> 출처: 서울 우리마을가게 상권분석서비스
> PK: id (auto) | 인덱스: quarter, trdar_code

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | int (PK, auto) | 자동증가 PK | 1 |
| `quarter` | bigint | 분기 (YYYYQ) | 20244 |
| `trdar_code` | text | 상권 코드 | 3110540 |
| `industry_code` | text | 업종 코드 | CS100001 |
| `store_count` | bigint | 점포 수 | 12 |
| `similar_store_count` | bigint | 유사 점포 수 | 8 |
| `open_rate` / `close_rate` | bigint | 개업률/폐업률 | — |
| `open_count` / `close_count` | bigint | 개업/폐업 수 | — |
| `franchise_count` | bigint | 프랜차이즈 수 | 3 |

---

## 24. mapo_resident_pop — 마포구 행정동 분기 주민등록인구

> 출처: 마포구청 / 행안부
> PK: id (auto) | 인덱스: quarter, dong_code

| 컬럼명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `id` | int (PK, auto) | 자동증가 PK | 1 |
| `quarter` | bigint | 분기 (YYYYQ) | 20244 |
| `dong_code` | text | 행정동 코드 | 11440630 |
| `dong_name` | text | 행정동명 | 망원1동 |
| `resident_pop` | float | 주민등록 인구 | 43960.0 |

---

## 25. seoul_district_sales — 서울 전체 행정동 분기 매출 (사전학습용)

> 출처: 서울 상권분석서비스 (서울 전체) | 스키마는 `district_sales` 와 동일
> PK: id (auto) | 인덱스: quarter, dong_code
> 컬럼: `district_sales` 와 동일 (monthly_sales, 요일/시간대/성별/연령대별 매출·건수)

**용도**: LSTM/GRU/TCN 사전학습. 마포구 파인튜닝 전에 서울 전체로 먼저 학습하기 위한 데이터셋.

---

## 26. seoul_district_stores — 서울 전체 행정동 분기 점포 (사전학습용)

> 출처: 서울 상권분석서비스 | 스키마는 `store_quarterly` 와 유사
> PK: id (auto) | 인덱스: quarter, dong_code

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| `id` | int (PK, auto) | 자동증가 PK |
| `quarter` | bigint | 분기 (YYYYQ) |
| `dong_code` / `dong_name` | text | 행정동 코드/명 |
| `industry_code` / `industry_name` | text | 업종 코드/명 |
| `store_count`, `similar_store_count` | bigint | 점포 수, 유사 점포 수 |
| `open_count`, `close_count` | bigint | 개업/폐업 수 |
| `franchise_count` | bigint | 프랜차이즈 수 |
| `closure_rate` | bigint | 폐업률 |

---

## 27. seoul_golmok_rent — 서울 전체 환산임대료 (사전학습용)

> 출처: 서울 상권분석서비스 | 스키마는 `golmok_rent` 와 유사 (float 확장)
> PK: id (auto) | 인덱스: year, dong_code

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| `id` | int (PK, auto) | 자동증가 PK |
| `year` / `quarter` / `quarter_code` | bigint | 연도, 분기, 분기 통합 코드 |
| `dong_code` / `dong_name` | text | 행정동 코드/명 |
| `gubun` | text | 구분 (gu/dong) |
| `rent_1f` / `rent_other` / `rent_total` | float | 환산임대료 (1층/기타/전체) |

---

## 28. seoul_population_quarterly — 서울 행정동 분기 인구 (사전학습용)

> 출처: 서울시 인구 통계
> PK: id (auto) | 인덱스: quarter, dong_code

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| `id` | int (PK, auto) | 자동증가 PK |
| `quarter` | bigint | 분기 (YYYYQ) |
| `dong_code` | text | 행정동 코드 |
| `total_pop` | float | 전체 인구 |

---

## 29. seoul_training_dataset — LSTM 사전학습 통합 데이터셋

> 여러 소스(매출/점포/인구/CPI)를 동×분기×업종 단위로 결합한 학습용 wide-format 테이블
> PK: id (auto) | 인덱스: quarter, dong_code

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| `id` | int (PK, auto) | 자동증가 PK |
| `quarter` | bigint | 분기 (YYYYQ) |
| `dong_code` / `dong_name` | text | 행정동 코드/명 |
| `industry_code` / `industry_name` | text | 업종 코드/명 |
| `monthly_sales`, `monthly_count` | bigint | 월평균 매출/건수 |
| `store_count`, `open_count`, `close_count` | bigint | 점포/개업/폐업 수 |
| `total_pop` | float | 인구 |
| `cpi_index` | float | 외식 CPI |

---

## 부속 시스템 테이블 (관리 외)

`alembic`/`pgvector`가 직접 관리하는 테이블 (애플리케이션 ORM 비대상):

| 테이블 | 용도 |
|--------|------|
| `alembic_version` | Alembic 마이그레이션 리비전 추적 |
| `langchain_pg_collection` | LangChain RAG 컬렉션 메타 |
| `langchain_pg_embedding` | LangChain RAG 벡터 임베딩 (384차원) |

> 시드 로더(`scripts/seed_from_csv.py`)는 위 3개 테이블을 SKIP하며, RAG 임베딩은 앱에서 재생성합니다.

---

## 학습용 CSV 데이터셋 (DB 외부)

> **참고**: 이전까지 CSV로만 관리되던 서울 전체 사전학습 데이터, mapo_resident_pop, cpi, golmok_sales/stores 는 migration `b2d4e8f1c7a3` 에서 DB 테이블로 승격되어 (20~29번 참조) 현재는 `python -m scripts.seed_from_csv` 로 적재합니다.

여전히 DB에 들어가지 않는 CSV 자산 (`data/processed/*.csv`):

| CSV | 내용 | 사용처 |
|-----|------|--------|
| `naver_trend_*.csv` | 네이버 검색 트렌드 | 파인튜닝 피처 |
| `dong_subway_access.csv` | 동별 지하철 접근성 | 입지 피처 |

> 자세한 모델 산출물 구조는 `docs/db-erd.md` 의 "모델 산출물 구조" 섹션 참조.

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

**환경변수**: `POSTGRES_URL=postgresql://postgres:비밀번호@localhost:5432/mapo_simulator`

## 최초 셋업 (팀원 온보딩)

### 사전 준비 (1회만, OS 수준)

1. PostgreSQL 로컬 설치 (14 이상 권장)
2. pgvector 확장 바이너리 설치 — 법률 RAG 용 (없으면 `--skip-ingest` 로 생략 가능)
   - Windows: [pgvector releases](https://github.com/pgvector/pgvector/releases) → PG 설치 폴더에 복사
   - Linux: `apt install postgresql-XX-pgvector`
3. 빈 DB 생성: `createdb mapo_simulator`
4. 환경변수 설정: `export POSTGRES_URL=postgresql://postgres:<비번>@localhost:5432/mapo_simulator`

### 원클릭 초기화

```bash
cd backend
python -m scripts.init_db --csv-dir <받은CSV폴더>
```

자동 수행되는 5단계: DB 연결 → pgvector 확장 → alembic 마이그레이션 → CSV 적재 (29개 테이블) → 법률 RAG 임베딩.

`--skip-ingest` 옵션: 법률 RAG 단계 생략 (pgvector 없이도 일반 데이터 적재 가능, 법률 검색 기능만 비활성).

### 데이터 업데이트 받았을 때 (동기화)

```bash
# 참조 데이터만 재적재 (본인 회원 / 시뮬 이력 유지)
python -m scripts.seed_from_csv --dir <새CSV폴더> --force

# 모든 테이블 재적재 (주의: 앱 생성 데이터도 덮어씀)
python -m scripts.seed_from_csv --dir <새CSV폴더> --force-all
```

보호 대상 테이블 (`--force` 시 스킵): `users`, `manager_users`, `invite_codes`, `simulation_result`, `biz_brand_mapping`.
