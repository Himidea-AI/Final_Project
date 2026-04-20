# A1 (찬영) — WBS (Work Breakdown Structure)

> **Jira 프로젝트 키**: `IM3`
> **담당 영역**: `backend/src/services/`, `backend/src/database/`, `data/`, `models/lstm_forecast/` (공동)
> **최종 업데이트**: 2026-04-20 (에픽 구조 개편)
> **프로젝트 기간**: 04/02 ~ 05/07 (5주)

---

## 에픽 구조 (2026-04-20 개편)

구 에픽 IM3-86(데이터 엔지니어링), IM3-110(딥러닝) 은 승계 코멘트 후 Done 처리.
신규 7개 에픽 기준으로 모든 Task 재부모 완료.

| 에픽 키 | 에픽명 | 상태 |
|---|---|---|
| IM3-207 | [A1-E1] 외부 API 수집 인프라 | Done |
| IM3-208 | [A1-E2] PostgreSQL ETL 파이프라인 | Done |
| IM3-209 | [A1-E3] 딥러닝 매출 예측 모델 (B2 공동) | Done |
| IM3-210 | [A1-E4] 점포 데이터 전수화 (kakao_store) | In Progress |
| IM3-211 | [A1-E5] 분석 노드 구현 (B1 연동) | Todo |
| IM3-212 | [A1-E6] 데이터 파이프라인 문서화 | Todo |
| IM3-213 | [A1-E7] QA/Test — 데이터 품질 검증 | Todo |

---

## 티켓 총괄표

> 난이도: 쉬움 / 보통 / 어려움
> 우선순위: P0 (즉시) / P1 (이번 주) / P2 (다음 주) / P3 (여유 시)

### 데이터 엔지니어링 (IM3-207 / IM3-208 / IM3-210 / IM3-211 / IM3-212 / IM3-213 하위)

| # | Jira 티켓 | 제목 | 주차 | 우선순위 | 난이도 | 상태 |
|---|----------|------|------|---------|--------|------|
| 1 | IM3-32 | BaseAPIClient POST 메서드 구현 | 1주차 | P0 | 쉬움 | 완료 |
| 2 | IM3-33 | 외부 API 클라이언트 구현 (SGIS, 생활인구 등 6개) | 1주차 | P0 | 보통 | 완료 |
| 3 | IM3-34 | CSV 데이터 로더 구현 (오프라인 폴백) | 1주차 | P0 | 쉬움 | 완료 |
| 4 | IM3-35 | services 패키지 export 정리 + 1주차 완료 | 1주차 | P0 | 쉬움 | 완료 |
| 5 | IM3-36 | 2주차 데이터 전처리 — 마포구 16개 동 집계 + 시계열 | 2주차 | P0 | 보통 | 완료 |
| 6 | IM3-37 | 데이터 파이프라인 + PostgreSQL 11개 테이블 적재 | 2주차 | P0 | 어려움 | 완료 |
| 7 | IM3-38 | golmok_rent 테이블 추가 + 실거래가 데이터 정리 | 2주차 | P1 | 보통 | 완료 |
| 8 | IM3-39 | load_to_db.py DB 접속정보 환경변수 처리 | 2주차 | P1 | 쉬움 | 완료 |
| 9 | IM3-172 | kakao_store 테이블 — 카카오 API 실시간 점포 수집 | 3주차 | P1 | 보통 | 완료 |
| 10 | IM3-173 | store_info vs kakao_store 브랜드 정규화 교차 검증 | 3주차 | P2 | 보통 | 해야 할 일 |
| 11 | IM3-57 | population_node 구현 — 서울 생활인구 API 연동 | 4주차 | P1 | 보통 | 해야 할 일 |
| 12 | IM3-58 | demographics_node 구현 — SGIS 인구/가구 API 연동 | 4주차 | P1 | 보통 | 해야 할 일 |
| 13 | IM3-59 | cost_node 구현 — 임대료/실거래가 데이터 연동 | 4주차 | P1 | 보통 | 해야 할 일 |
| 14 | IM3-60 | commercial_node + trend_node 구현 | 4주차 | P2 | 보통 | 해야 할 일 |
| 15 | IM3-61 | 데이터 서비스 통합 테스트 작성 | 4주차 | P2 | 보통 | 해야 할 일 |
| 16 | IM3-176 | 데이터 파이프라인 문서화 — ERD + kakao_store 반영 | 5주차 | P2 | 쉬움 | 해야 할 일 |
| 17 | IM3-175 | 발표 데모용 데이터 검증 — 16개 동 무결성 최종 확인 | 5주차 | P1 | 보통 | 해야 할 일 |

### 딥러닝 예측 모델 (IM3-209 하위, B2 수지니 공동)

| # | Jira 티켓 | 제목 | 주차 | 우선순위 | 난이도 | 상태 |
|---|----------|------|------|---------|--------|------|
| 18 | IM3-111 | 서울 전체 추정매출 전처리 파이프라인 | 2주차 | P0 | 보통 | 완료 |
| 19 | IM3-112 | 서울 전체 점포수 전처리 | 2주차 | P0 | 보통 | 완료 |
| 20 | IM3-113 | 서울 전체 유동인구 전처리 | 2주차 | P0 | 보통 | 완료 |
| 21 | IM3-114 | 마포구 결측값 처리 | 2주차 | P0 | 쉬움 | 완료 |
| 22 | IM3-115 | 외식물가지수(CPI) 수집 | 2주차 | P1 | 쉬움 | 완료 |
| 23 | IM3-116 | 사전학습용 통합 데이터셋 구축 | 2주차 | P0 | 어려움 | 완료 |
| 24 | IM3-117 | LSTM 모델 아키텍처 설계 | 3주차 | P0 | 어려움 | 완료 |
| 25 | IM3-118 | data_prep.py 구현 | 3주차 | P0 | 보통 | 완료 |
| 26 | IM3-119 | 사전학습 구현 (서울 전체) | 3주차 | P0 | 어려움 | 완료 |
| 27 | IM3-120 | 파인튜닝 구현 (마포구) | 3주차 | P0 | 어려움 | 완료 |
| 28 | IM3-121 | predict.py 구현 | 3주차 | P1 | 보통 | 완료 |
| 29 | IM3-122 | 생존률 예측 모델 설계 및 구현 | 3주차 | P1 | 어려움 | 완료 |
| 30 | IM3-123 | BEP 계산 로직 구현 | 3주차 | P1 | 보통 | 완료 |
| 31 | IM3-124 | 백테스팅 파이프라인 구축 | 3주차 | P1 | 보통 | 완료 |
| 32 | IM3-125 | Chronos 베이스라인 테스트 (선택) | 5주차 | P3 | 보통 | 해야 할 일 |
| 33 | IM3-126 | A1-B2 인터페이스 정의 및 연동 | 3주차 | P0 | 보통 | 완료 |

---

## 티켓별 상세 설명

### 1주차 완료 (04/02 ~ 04/06) — 기반 구축

#### IM3-32: BaseAPIClient POST 메서드 구현
- 외부 API 공통 베이스 클라이언트에 POST 메서드 추가
- 산출물: `backend/src/services/base_client.py`

#### IM3-33: 외부 API 클라이언트 구현
- SGIS, 서울 생활인구, 소상공인, 골목상권, 국토부, 네이버 총 6개 API 클라이언트
- 산출물: `backend/src/services/` 하위 클라이언트 파일들

#### IM3-34: CSV 데이터 로더 구현
- API 장애 시 CSV 폴백 로더 구현
- 산출물: `backend/src/services/csv_loader.py`

#### IM3-35: services 패키지 export 정리
- `__init__.py` export 정리, 1주차 API 연동 마무리

---

### 2주차 완료 (04/07 ~ 04/11) — 전처리 + DB 적재

#### IM3-36: 마포구 16개 동 행정동 집계
- 법정동 → 행정동 매핑, 시계열 테이블 구성

#### IM3-37: PostgreSQL 11개 테이블 적재
- `load_to_db.py` ETL 파이프라인 구현
- 11개 테이블, 약 180만 행 적재
- 산출물: `data/pipeline/load_to_db.py`

#### IM3-38: golmok_rent 테이블 추가
- 신용보증재단 기반 환산임대료 데이터

#### IM3-39: DB 접속정보 환경변수 처리
- `.env` 기반 POSTGRES_URL 참조로 전환

#### IM3-111~116: 딥러닝 전처리 파이프라인
- 서울 전체 추정매출/점포수/유동인구 전처리
- 마포구 결측값 보간 (guide-density 방식)
- CPI 물가지수 수집 + 사전학습용 통합 데이터셋 구축
- 산출물: `data/processed/` 하위 CSV 파일들

---

### 3주차 완료 (04/14 ~ 04/18) — LSTM + 카카오 API

#### IM3-117~124: LSTM 모델 구현 (B2 공동)
- 아키텍처 설계 → data_prep → 사전학습(서울) → 파인튜닝(마포구)
- predict.py, 생존률 예측, BEP 계산, 백테스팅
- 전체 MAPE 18.7% (골목상권 피처 적용)
- 산출물: `models/lstm_forecast/` 전체

#### IM3-126: A1-B2 인터페이스 정의
- `models/interface.py` — ModelOutput.generate() 통합 호출
- LSTM → 시뮬레이션 데이터 흐름 확정

#### IM3-172: kakao_store 테이블 (완료)
- 카카오 로컬 API 기반 마포구 프랜차이즈 점포 수집
- 10대 카테고리, 792개 점포, RDS 적재 완료
- 브랜드명 정규화 (메가엠지씨커피→메가MGC커피 등)
- 산출물: `data/pipeline/collect_kakao_stores.py`, `kakao_store` 테이블

---

### 4주차 예정 (04/21 ~ 04/25) — 분석 노드 구현 + 점포 전수화

| 티켓 | 작업 | 에픽 | 비고 |
|------|------|------|------|
| IM3-57 | population_node — 생활인구 API 연동 | IM3-211 | B1 에이전트 연결 |
| IM3-58 | demographics_node — SGIS 인구/가구 연동 | IM3-211 | B1 에이전트 연결 |
| IM3-59 | cost_node — 임대료/실거래가 연동 | IM3-211 | B1 에이전트 연결 |
| IM3-60 | commercial_node + trend_node | IM3-211 | 골목상권 + 트렌드 |
| IM3-214 | 카카오 전수 수집 — 그리드 수집 엔진 구현 | IM3-210 | FD6+CE7 × 500m adaptive |
| IM3-215 | kakao_store 스키마 확장 + UPSERT 적재 | IM3-210 | is_franchise, Alembic |
| IM3-216 | 카카오 전수 수집 QA 스모크 (합정 bbox) | IM3-210 | UPSERT 멱등성 |
| IM3-173 | store_info vs kakao_store 교차 검증 | IM3-213 | 브랜드 정합성 |
| IM3-61 | 데이터 서비스 통합 테스트 | IM3-213 | 전체 노드 검증 |

---

### 5주차 예정 (04/28 ~ 05/07) — 마무리 + 발표

| 티켓 | 작업 | 에픽 | 비고 |
|------|------|------|------|
| IM3-175 | 발표 데모용 데이터 검증 | IM3-213 | 16개 동 무결성 QA |
| IM3-218 | 데이터 회귀 테스트 자동화 | IM3-213 | 행수/컬럼 기준값 고정 |
| IM3-176 | 문서화 — ERD/스키마/데이터사전 업데이트 | IM3-212 | kakao_store 반영 |
| IM3-217 | 데이터 사전(data-dictionary.md) 업데이트 | IM3-212 | 신규 21종 반영 |
| IM3-125 | Chronos 베이스라인 테스트 (선택) | IM3-209 | P3, 시간 여유 시 |

---

## DB 테이블 현황 (A1 담당)

| # | 테이블 | 행수 | 출처 | 상태 |
|---|--------|-----:|------|------|
| 1 | living_population | 43,848 | 서울 열린데이터광장 | RDS 적재 |
| 2 | sgis_population | 189,379 | 통계청 SGIS | RDS 적재 |
| 3 | sgis_household | 23,109 | 통계청 SGIS | RDS 적재 |
| 4 | sgis_business | 54,971 | 통계청 SGIS | RDS 적재 |
| 5 | golmok_commercial | 178,840 | 서울시 우리마을가게 | RDS 적재 |
| 6 | district_sales | 16,951 | 서울시 우리마을가게 | RDS 적재 |
| 7 | store_info | 30,488 | 소상공인시장진흥공단 | RDS 적재 |
| 8 | store_quarterly | 28,305 | 서울시 우리마을가게 | RDS 적재 |
| 9 | rent_cost | 4,703 | 한국부동산원 | RDS 적재 |
| 10 | golmok_rent | - | 신용보증재단 | RDS 적재 |
| 11 | dong_mapping | 16 | 행정동 마스터 | RDS 적재 |
| 12 | kakao_store | 792 | 카카오 로컬 API | RDS 적재 |

---

## 의존성 다이어그램

```
1주차 (완료)
  IM3-32 (BaseAPI) ━━━┓
  IM3-33 (API 6개) ━━━┫
  IM3-34 (CSV 로더) ━━┫
  IM3-35 (export)  ━━━┛

2주차 (완료)
  IM3-35 ━━━━━ IM3-36 (전처리) ━━━ IM3-37 (DB 적재)
                                    IM3-38 (golmok_rent)
                                    IM3-39 (환경변수)
              IM3-111~116 (딥러닝 전처리)

3주차 (완료)
  IM3-116 ━━━ IM3-117~124 (LSTM 모델)
              IM3-126 (인터페이스)
  IM3-37 ━━━━ IM3-172 (kakao_store) ━━━ IM3-173 (교차 검증)

4주차
  IM3-37 ━━━━ IM3-57 (population_node)
              IM3-58 (demographics_node)
              IM3-59 (cost_node)
              IM3-60 (commercial + trend)
              ━━━━━━ IM3-61 (통합 테스트)

5주차
  IM3-61 ━━━━ IM3-175 (데이터 검증)
              IM3-176 (문서화)
```

---

## Jira CLI 자동화

```bash
# 작업 시작 시
python scripts/jira_update.py IM3-57 --status in_progress --comment "population_node 구현 시작"

# 작업 완료 시
python scripts/jira_update.py IM3-57 --status done --comment "구현 완료, 커밋 abc1234"

# 새 티켓 생성
python scripts/jira_update.py --create --summary "A1: 새 작업" --description "설명"

# 티켓 정보 확인
python scripts/jira_update.py IM3-57 --info
```
