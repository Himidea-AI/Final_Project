# 데이터 사전 (Data Dictionary)

`data/processed/` 디렉토리에 저장된 전처리 완료 데이터 파일 목록입니다.
모든 CSV는 UTF-8 인코딩이며, 원본 데이터에서 마포구(자치구코드 11440)만 필터링한 결과입니다.

---

## 1. 생활인구

### `living_population_mapo.csv` (13.8MB, 43,848행)

KT 통신 데이터 기반 마포구 일별 생활인구. 성별·연령대별 인구를 제공합니다.

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `date` | string | 기준일 (YYYYMMDD) | `20200101` |
| `time_zone` | string | 시간대 구분 (`00`=일합계) | `00` |
| `district_code` | string | 자치구코드 (마포구=`11440`) | `11440` |
| `total_pop` | float | 총 생활인구 수 | `463915.78` |
| `male_0_9` ~ `male_70_plus` | float | 남성 연령대별 인구 (14개 연령대) | `13722.51` |
| `female_0_9` ~ `female_70_plus` | float | 여성 연령대별 인구 (14개 연령대) | `13623.29` |

- **원본**: 서울 열린데이터광장 `LOCAL_PEOPLE_GU_2020~2024.csv` (6개 파일, 각 72~87MB)
- **기간**: 2020.01.01 ~ 2024.12.31 (5년)
- **단위**: 마포구 전체 (자치구 단위, 행정동 단위 아님)
- **활용**: 유동인구 분석 (`population.py` 노드), 시간대별/연령대별 소비 패턴 추정
- **주의**: 생활인구는 소수점으로 표현됨 (통계 추정치)

---

## 2. 소상공인 상가정보

### `store_info_mapo.csv` (7.9MB, 30,488행)

마포구 내 모든 등록 상가 업소의 개별 정보. 경쟁 분석의 핵심 데이터입니다.

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `상가업소번호` | string | 업소 고유 식별자 | `MA010120220800218616` |
| `상호명` | string | 가게 이름 | `골든공인중개사사무소` |
| `지점명` | string | 지점명 (없으면 빈값) | |
| `상권업종대분류코드` | string | 대분류 코드 | `L1` |
| `상권업종대분류명` | string | 대분류명 | `부동산` |
| `상권업종중분류코드` | string | 중분류 코드 | `L102` |
| `상권업종중분류명` | string | 중분류명 | `부동산 서비스` |
| `상권업종소분류코드` | string | 소분류 코드 | `L10203` |
| `상권업종소분류명` | string | 소분류명 | `부동산 중개/대리업` |
| `행정동코드` | string | 행정동 코드 (8자리) | `11440730` |
| `행정동명` | string | 행정동명 | `성산2동` |
| `법정동코드` | string | 법정동 코드 | `1144012500` |
| `법정동명` | string | 법정동명 | `성산동` |
| `지번주소` | string | 지번 주소 | `서울특별시 마포구 성산동 592-2` |
| `도로명주소` | string | 도로명 주소 | `서울특별시 마포구 월드컵로34길 6` |
| `건물명` | string | 건물명 (없으면 빈값) | |
| `층정보` | string | 층 정보 | `1` |
| `경도` | float | 경도 (longitude) | `126.903066` |
| `위도` | float | 위도 (latitude) | `37.564569` |

- **원본**: `소상공인시장진흥공단_상가(상권)정보_서울_202512.csv` (291MB, 534,978행 → 마포구 30,488행)
- **기준일**: 2025년 12월 스냅샷
- **커버리지**: 마포구 16개 행정동 전체
- **업종 분포**: 음식(9,002) > 생활서비스(5,704) > 소매(4,837) > 학문교육(2,690) > 의료(2,634) 등
- **활용**: 경쟁 매장 위치/밀도 분석 (`competition.py` 노드), 카니발리제이션 거리 계산 (위경도 활용)

---

## 3. SGIS 소지역 통계 (11개 파일)

통계청 SGIS에서 제공하는 마포구(코드 11140) 소지역 단위 통계. 모든 파일이 동일한 4컬럼 구조입니다.

### 공통 컬럼 구조

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `year` | int | 기준 연도 | `2020` |
| `area_code` | string | 소지역 코드 (14자리) | `11140710010004` |
| `indicator_code` | string | 지표 코드 | `to_in_001` |
| `value` | float | 지표 값 | `568.0` |

- **주의**: `area_code`는 행정동보다 더 작은 **소지역(집계구)** 단위. 앞 5자리 `11140`이 마포구.
- **지표코드 해석**: 데스크톱의 `statistics_code.xls` 참조 필요

### 인구 관련 (5개)

| 파일 | 행수 | 지표코드 | 내용 | 기간 |
|------|-----:|---------|------|------|
| `sgis_population_total.csv` | 11,310 | `to_in_001` | 총인구 | 2020~2024 |
| `sgis_population_avg_age.csv` | 3,770 | `to_in_002` | 평균나이 | 2020~2024 |
| `sgis_population_density.csv` | 3,770 | `to_in_003` | 인구밀도 (명/km²) | 2020~2024 |
| `sgis_population_aging.csv` | 3,770 | `to_in_004` | 노령화지수 | 2020~2024 |
| `sgis_population_age_gender.csv` | 201,625 | `in_age_*` | 성별·연령대별 인구 | 2020~2024 |

- **활용**: 인구통계 분석 (`demographics.py` 노드), 타겟 연령대 비중 계산

### 가구 관련 (2개)

| 파일 | 행수 | 지표코드 | 내용 | 기간 |
|------|-----:|---------|------|------|
| `sgis_household_total.csv` | 7,540 | `to_ga_001` | 총 가구수 | 2020~2024 |
| `sgis_household_composition.csv` | 17,930 | `ga_sd_*` | 세대구성별 가구 | 2020~2024 |

- **활용**: 1인가구 비율 등 소비 패턴 추정

### 사업체 관련 (4개)

| 파일 | 행수 | 지표코드 | 내용 | 기간 |
|------|-----:|---------|------|------|
| `sgis_business_major_count.csv` | 26,040 | `cp_bnu_*` | 산업 대분류별 사업체 수 | 2020~2023 |
| `sgis_business_major_workers.csv` | 26,040 | `cp_bem_*` | 산업 대분류별 종사자 수 | 2020~2023 |
| `sgis_business_mid_count.csv` | 42,638 | `cp2_bnu_*` | 산업 중분류별 사업체 수 | 2020~2023 |
| `sgis_business_mid_workers.csv` | 42,638 | `cp2_bem_*` | 산업 중분류별 종사자 수 | 2020~2023 |

- **활용**: 업종별 사업체 밀도 분석 (`commercial.py` 노드)
- **주의**: 2024년 사업체 데이터는 아직 미제공

---

## 4. 골목상권 추정매출

### `golmok_sales_mapo.csv` (7.0MB, 15,641행)

서울시 우리마을가게 상권분석서비스 API에서 수집한 마포구 관련 상권의 업종별 추정매출.
카드사 결제금액 기반으로 추정한 매출 데이터입니다. **개별 가게 매출이 아닌, 상권×업종 집계 데이터입니다.**

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `STDR_YYQU_CD` | string | 기준년분기 코드 | `20254` (2025년 4분기) |
| `TRDAR_SE_CD` | string | 상권 구분 코드 | `A`=골목, `D`=발달, `R`=전통시장 |
| `TRDAR_SE_CD_NM` | string | 상권 구분명 | `골목상권` |
| `TRDAR_CD` | string | 상권 코드 | `3110754` |
| `TRDAR_CD_NM` | string | 상권명 | `홍대입구역 2번` |
| `SVC_INDUTY_CD` | string | 서비스 업종 코드 | `CS100001` |
| `SVC_INDUTY_CD_NM` | string | 서비스 업종명 | `한식음식점` |
| **매출금액 (원)** | | | |
| `THSMON_SELNG_AMT` | float | 당월 총 매출액 | `50000000` |
| `THSMON_SELNG_CO` | float | 당월 총 결제 건수 | `3000` |
| `MDWK_SELNG_AMT` | float | 평일 매출액 | `35000000` |
| `WKEND_SELNG_AMT` | float | 주말 매출액 | `15000000` |
| `MON_SELNG_AMT` ~ `SUN_SELNG_AMT` | float | 요일별 매출액 (월~일) | |
| **시간대별 매출 (원)** | | | |
| `TMZON_00_06_SELNG_AMT` | float | 00~06시 매출액 | |
| `TMZON_06_11_SELNG_AMT` | float | 06~11시 매출액 | |
| `TMZON_11_14_SELNG_AMT` | float | 11~14시 매출액 | |
| `TMZON_14_17_SELNG_AMT` | float | 14~17시 매출액 | |
| `TMZON_17_21_SELNG_AMT` | float | 17~21시 매출액 | |
| `TMZON_21_24_SELNG_AMT` | float | 21~24시 매출액 | |
| **성별 매출 (원)** | | | |
| `ML_SELNG_AMT` | float | 남성 매출액 | |
| `FML_SELNG_AMT` | float | 여성 매출액 | |
| **연령대별 매출 (원)** | | | |
| `AGRDE_10_SELNG_AMT` | float | 10대 매출액 | |
| `AGRDE_20_SELNG_AMT` | float | 20대 매출액 | |
| `AGRDE_30_SELNG_AMT` | float | 30대 매출액 | |
| `AGRDE_40_SELNG_AMT` | float | 40대 매출액 | |
| `AGRDE_50_SELNG_AMT` | float | 50대 매출액 | |
| `AGRDE_60_ABOVE_SELNG_AMT` | float | 60대 이상 매출액 | |
| **결제 건수 (위 금액과 동일 패턴)** | | | |
| `*_SELNG_CO` | float | 위 각 항목의 결제 건수 버전 | |

- **원본**: 서울 열린데이터광장 API `VwsmTrdarSelngQq` (2022 Q1 ~ 2025 Q4, 16분기)
- **마포구 필터**: 상권명에 마포구 키워드(홍대, 합정, 망원, 연남, 공덕, 상수 등) 포함 65개 상권
- **활용**: 매출 예측 모델 학습 데이터, 업종별 매출 추이 분석, 시간대/요일/연령 패턴 분석
- **한계**: 상권×업종 집계값 (개별 점포 매출 아님), 상권→행정동 매핑은 키워드 기반 (정확도 한계)

### `golmok_sales_seoul.csv` (155MB, 349,991행) — git 미포함

서울 전체 상권 추정매출 원본. 컬럼 구조는 `golmok_sales_mapo.csv`와 동일.
로컬에만 존재하며 `.gitignore`에 등록됨.

### `mapo_trdar_list.txt` (텍스트)

마포구 관련 65개 상권 코드 및 이름 목록. `golmok_sales_mapo.csv` 필터에 사용된 상권 리스트.

---

## 5. 상권변화지표

### `commercial_change_mapo.csv` (24KB, 448행)

행정동 단위의 상권 변화(확장/축소/다이나믹) 지표. 분기별 데이터.

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `기준_년분기_코드` | string | 기준년분기 | `20254` |
| `행정동_코드` | string | 행정동 코드 (8자리) | `11440740` |
| `행정동_코드_명` | string | 행정동명 | `상암동` |
| `상권_변화_지표` | string | 변화지표 코드 | `LL`, `HH`, `HL`, `LH` |
| `상권_변화_지표_명` | string | 변화지표명 | `다이나믹`, `상권확장`, `상권축소`, `정체` |
| `운영_영업_개월_평균` | int | 운영 중인 업소의 평균 영업 기간 (개월) | `85` |
| `폐업_영업_개월_평균` | int | 폐업 업소의 평균 영업 기간 (개월) | `45` |
| `서울_운영_영업_개월_평균` | int | 서울 전체 운영 업소 평균 (비교용) | `115` |
| `서울_폐업_영업_개월_평균` | int | 서울 전체 폐업 업소 평균 (비교용) | `53` |

- **원본**: `서울시 상권분석서비스(상권변화지표-행정동).csv` (cp949 인코딩, 서울 전체 11,900행 → 마포구 448행)
- **활용**: 상권 활성화/침체 판단 (`commercial.py` 노드), 출점 리스크 평가

---

## 6. 부동산 관련 (2개)

### `commercial_trade_mapo.csv` (735KB, 4,456행)

마포구 상업업무용 부동산 매매 실거래가.

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `NO` | int | 순번 | `1` |
| `시군구` | string | 시군구명 | `마포구` |
| `유형` | string | 집합/일반 | `집합` |
| `지번` | string | 지번 | `서교동 395-130` |
| `도로명` | string | 도로명 주소 | `양화로 156` |
| `용도지역` | string | 용도 지역 | `일반상업지역` |
| `건축물주용도` | string | 건물 용도 | `제1종근린생활시설` |
| `도로조건` | string | 도로 조건 | `8m 이상 12m 미만` |
| `전용/연면적(㎡)` | float | 전용면적 또는 연면적 | `45.5` |
| `대지면적(㎡)` | float | 대지면적 | `120.3` |
| `거래금액(만원)` | string | 매매 거래금액 (만원) | `150,000` |
| `층` | string | 거래 층 | `1` |
| `매수자` | string | 매수자 구분 | `개인` |
| `매도자` | string | 매도자 구분 | `개인` |
| `계약년월` | string | 계약 년월 | `202603` |
| `계약일` | string | 계약일 | `15` |
| `건축년도` | string | 건축 연도 | `2005` |
| `거래유형` | string | 거래 유형 | `중개거래` |
| `중개사소재지` | string | 중개사 소재지 | `마포구` |

- **원본**: `상업업무용(매매)_실거래가_*.xlsx` 7개 파일 (국토부 rt.molit.go.kr 다운로드)
- **기간**: 2025.04 ~ 2026.04 (약 1년)
- **활용**: 부동산 가격 추이 분석 (`cost.py` 노드)
- **주의**: **매매** 실거래가만 포함. **임대차** 데이터 없음.

### `rent_small_store_mapo.csv` (1.5KB, 20행)

한국부동산원 소규모상가 임대료 통계. 마포구 관련 상권의 ㎡당 월 임대료(천원) 추이.

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `source_year` | string | 원본 파일 기준 연도 | `2019` |
| `지역` | string | 상권 지역명 | `서울 영등포신촌 홍대합정` |
| `2019_1분기` ~ `2021_4분기` | float | 분기별 ㎡당 월 임대료 (천원) | `59.0` |

- **원본**: 한국부동산원 `분기별 지역별 임대료(소규모상가)` CSV 3개 파일
- **기간**: 2019 ~ 2021 (3년, 12분기)
- **커버리지**: 마포구 관련 5개 상권만 (공덕역, 홍대합정, 동교/연남, 신촌/이대, 망원역)
- **활용**: 임대료 기준선 제공 (보조 데이터)
- **한계**: 데이터가 20행으로 매우 적음. `rent_building_mapo.csv`로 보강됨.

### `rent_building_mapo.csv` (248행)

서울 열린데이터광장 매장용빌딩 임대료·공실률·수익률 통계 + 기존 `rent_small_store_mapo.csv` 통합.
영등포신촌지역(마포구 관련) 상권 + 서울 평균의 2019~2025 분기별 시계열 데이터.

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `area_name` | string | 상권명 | `공덕역`, `홍대/합정`, `서울_평균` |
| `year` | int | 연도 | `2023` |
| `quarter` | int | 분기 (1~4) | `3` |
| `period` | string | 기간 표시 | `2023_3분기` |
| `rent` | float | ㎡당 월 임대료 (천원) | `39.3` |
| `vacancy_rate` | float | 공실률 (%) | `6.7` |
| `investment_return` | float | 투자수익률 (%) | `0.84` |
| `income_return` | float | 소득수익률 (%) | `0.65` |
| `capital_return` | float | 자본수익률 (%) | `0.19` |
| `source` | string | 데이터 출처 | `building_rent`, `rent_small_store` |

- **원본**: 서울 열린데이터광장 `매장용빌딩 임대료·공실률 및 수익률 통계` (한국부동산원)
- **기간**: 2019 Q1 ~ 2025 Q4 (7년, 28분기)
- **커버리지**: 마포구 관련 7개 상권 (공덕역, 당산역, 동교/연남, 망원역, 신촌/이대, 영등포, 홍대/합정) + 권역·서울 평균
- **활용**: `cost.py` 노드 (임대료 추정), `commercial.py` 노드 (공실률 기반 상권 활성도)
- **전처리**: `data/preprocess_rent_building.py`

---

## 파일 요약

| # | 파일 | 크기 | 행수 | 출처 | 주요 활용 노드 |
|---|------|-----:|-----:|------|--------------|
| 1 | `living_population_mapo.csv` | 13.8MB | 43,848 | 서울 열린데이터광장 | `population.py` |
| 2 | `store_info_mapo.csv` | 7.9MB | 30,488 | 소상공인시장진흥공단 | `competition.py` |
| 3 | `sgis_population_total.csv` | 0.4MB | 11,310 | 통계청 SGIS | `demographics.py` |
| 4 | `sgis_population_avg_age.csv` | 0.1MB | 3,770 | 통계청 SGIS | `demographics.py` |
| 5 | `sgis_population_density.csv` | 0.1MB | 3,770 | 통계청 SGIS | `demographics.py` |
| 6 | `sgis_population_aging.csv` | 0.1MB | 3,770 | 통계청 SGIS | `demographics.py` |
| 7 | `sgis_population_age_gender.csv` | 7.0MB | 201,625 | 통계청 SGIS | `demographics.py` |
| 8 | `sgis_household_total.csv` | 0.3MB | 7,540 | 통계청 SGIS | `demographics.py` |
| 9 | `sgis_household_composition.csv` | 0.6MB | 17,930 | 통계청 SGIS | `demographics.py` |
| 10 | `sgis_business_major_count.csv` | 0.9MB | 26,040 | 통계청 SGIS | `commercial.py` |
| 11 | `sgis_business_major_workers.csv` | 0.9MB | 26,040 | 통계청 SGIS | `commercial.py` |
| 12 | `sgis_business_mid_count.csv` | 1.4MB | 42,638 | 통계청 SGIS | `commercial.py` |
| 13 | `sgis_business_mid_workers.csv` | 1.4MB | 42,638 | 통계청 SGIS | `commercial.py` |
| 14 | `golmok_sales_mapo.csv` | 7.0MB | 15,641 | 서울 상권분석서비스 API | `report.py`, 매출 예측 |
| 15 | `commercial_change_mapo.csv` | 24KB | 448 | 서울시 상권분석서비스 | `commercial.py` |
| 16 | `commercial_trade_mapo.csv` | 735KB | 4,456 | 국토부 실거래가 | `cost.py` |
| 17 | `rent_small_store_mapo.csv` | 1.5KB | 20 | 한국부동산원 | `cost.py` (보조) |
| 18 | `rent_building_mapo.csv` | ~15KB | 248 | 서울 열린데이터광장 (한국부동산원) | `cost.py`, `commercial.py` |

### 신규 추가 파일

| # | 파일 | 크기 | 행수 | 출처 | 주요 활용 |
|---|------|-----:|-----:|------|----------|
| 19 | `living_population_dong_mapo.csv` | ~290MB | 968,064 | 서울 열린데이터광장 (행정동 단위) | `population.py` — 16개 동 시간대별 유동인구 |
| 20 | `district_sales.csv` (교체) | ~5.8MB | 16,951 | 서울 상권분석서비스(추정매출-행정동) | `commercial.py`, 매출 예측 — 16개 동 업종별 매출 |

### PostgreSQL 테이블 매핑

CSV 41개 파일이 PostgreSQL `mapo_simulator` DB의 11개 테이블로 통합 적재됨.

| 테이블 | 행수 | 합친 CSV | 용도 |
|--------|-----:|---------|------|
| `living_population` | 968,064 | `living_population_dong_mapo.csv` | 행정동 시간대별 유동인구 |
| `sgis_population` | 189,379 | `sgis_population_*.csv` (5) + `district_resident_pop/avg_age/demographics` | 인구통계 통합 |
| `sgis_household` | 23,109 | `sgis_household_*.csv` (2) + `district_households` | 가구통계 통합 |
| `sgis_business` | 54,971 | `sgis_business_*.csv` (4) | 사업체통계 통합 |
| `golmok_commercial` | 178,840 | `golmok_*_mapo.csv` (5) + `commercial_change_mapo` | 골목상권 종합 (JSONB) |
| `district_sales` | 16,951 | `district_sales.csv` | 행정동 추정매출 |
| `store_info` | 30,488 | `store_info_mapo.csv` | 개별 점포 |
| `store_quarterly` | 28,305 | `district_stores.csv` | 분기별 점포 집계 |
| `rent_cost` | 4,703 | `rent_building_mapo` + `commercial_trade_mapo` | 임대료/실거래가 통합 |
| `dong_mapping` | 16 | `district_population` + `trdar_dong_mapping` + `district_demographics` | 16개 동 마스터 |
| `simulation_result` | 0 | (신규) | 시뮬레이션 결과 저장 |

ETL 스크립트: `data/pipeline/load_to_db.py`

### git 미포함 (로컬 전용)

| 파일 | 크기 | 사유 |
|------|-----:|------|
| `golmok_sales_seoul.csv` | 155MB | 용량 초과 |
| `living_population_mapo.csv` | 13.8MB | 용량 초과 |
| `living_population_dong_mapo.csv` | ~290MB | 용량 초과 |
