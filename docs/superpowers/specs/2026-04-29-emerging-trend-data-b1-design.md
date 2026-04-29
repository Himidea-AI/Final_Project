# 신흥 상권 감지 데이터 적재 — B1 (인구·이동성)

- **작성일**: 2026-04-29
- **담당**: 찬영 (A1)
- **branch**: IM3-243-dong-fk-followup (또는 분기)
- **상태**: spec — 사용자 리뷰 대기

## 1. 배경

기존 SPOTTER DB 는 상권 매출/인구/유동인구 정적 데이터는 풍부하지만, **신흥 상권의 "전조 신호"** 를 잡을 시계열 지표가 부족하다. 사용자 분석 (`Desktop/image (1).webp`) 으로 식별된 5개 무료 공공데이터 중 **인구·이동성 성격 3종** 을 본 spec 에서 적재한다.

| 데이터 | 신호 | 선행/후행 |
|--------|------|-----------|
| 지하철 승하차 시계열 | 합정/홍대/망원 분기별 승하차 증감 = 상권 변화 전조 | 선행 |
| 동별 전입/전출 인구 | 20-30대 유입 증가 = 가장 빠른 상권 변화 신호 | 선행 |
| 따릉이 동별 이용 | 20-30대 이동 패턴 지표 | 동행 |

부동산·개발 성격 2종 (건축인허가, 공시지가) 은 **B2 spec** 에서 다룬다.

## 2. 목표 / 비목표

### 목표
- 5년치 (2021-04 ~ 2026-03) 데이터 CSV one-shot 적재
- 마스터 테이블 2개 (지하철역, 따릉이 대여소) + 운영 테이블 3개 신설
- CLAUDE.md DB 네이밍/필터링 룰 100% 준수 (`seoul_*` prefix, `master_*` prefix, 마포 전용 테이블 X)
- Alembic 마이그레이션 + `seed_from_csv.py` 호환 + 검증 스크립트 동봉

### 비목표
- 자동 스케줄러 / live API ingestion (별도 이슈)
- ML 모델 학습, feature engineering
- 대시보드 / API endpoint 노출
- 건축인허가, 공시지가 (B2 spec)

## 3. 범위 / 데이터 정책

| 항목 | 결정 |
|------|------|
| 적재 방식 | CSV one-shot (data.seoul.go.kr / KOSIS / 행안부) |
| 시간 범위 | 5년 (2021-04 ~ 2026-03) |
| 마포 필터 정책 | 서울 전역 적재 후 `WHERE sigungu_code = '11440'` 또는 `dong_code LIKE '11440%'` |
| 따릉이 입자도 | 일×대여소 집계 (raw 보관 X) |
| 지하철 입자도 | 일×역 (시간대 split X) |
| 전입출 입자도 | 동×월, 20-30대 별도 컬럼 보관 |
| 화이트리스트 | DB 마스터 테이블 (`master_subway_station`, `master_ttareungi_station`) |

## 4. 스키마 설계

### 4.1 마스터 테이블

#### `master_subway_station`
```python
station_code = Column(String(10), primary_key=True, comment="서울교통공사 역코드")
station_name = Column(String(50), nullable=False, comment="역명")
line_name    = Column(String(20), comment="호선/노선 (예: 2호선, 공항철도)")
sigungu_code = Column(String(5), index=True, comment="자치구 코드 (마포=11440)")
lat          = Column(Float, comment="위도")
lon          = Column(Float, comment="경도")
created_at   = Column(DateTime, server_default=func.now())
```
COMMENT: `'담당: 찬영 | 서울 전체 지하철역 마스터 | 출처: 서울교통공사 + 국토부 좌표'`

#### `master_ttareungi_station`
```python
station_id   = Column(String(20), primary_key=True, comment="대여소 ID")
station_name = Column(String(100), nullable=False, comment="대여소명")
sigungu_code = Column(String(5), index=True, comment="자치구 코드")
dong_code    = Column(String(8), ForeignKey("seoul_dong_master.dong_code"),
                      index=True, comment="행정동 코드 (8자리 FK)")
lat          = Column(Float)
lon          = Column(Float)
opened_at    = Column(Date, comment="개소일 (있으면)")
created_at   = Column(DateTime, server_default=func.now())
```
COMMENT: `'담당: 찬영 | 서울 전체 따릉이 대여소 마스터 | 출처: 서울 열린데이터광장'`

### 4.2 운영 테이블

#### `seoul_subway_passenger_daily`
```python
date          = Column(Date, primary_key=True, comment="영업일")
station_code  = Column(String(10), ForeignKey("master_subway_station.station_code"),
                       primary_key=True, comment="역코드")
boarding_cnt  = Column(Integer, comment="승차 인원")
alighting_cnt = Column(Integer, comment="하차 인원")
__table_args__ = (Index("ix_subway_passenger_station", "station_code"),)
```
COMMENT: `'담당: 찬영 | 서울 전체 지하철 일별 승하차 | 출처: 서울교통공사'`

#### `seoul_dong_migration_monthly`
```python
ym             = Column(Integer, primary_key=True, comment="YYYYMM")
dong_code      = Column(String(8), ForeignKey("seoul_dong_master.dong_code"),
                        primary_key=True, comment="행정동 코드")
move_in_cnt    = Column(Integer, comment="전입 총수")
move_out_cnt   = Column(Integer, comment="전출 총수")
net_move       = Column(Integer, comment="순이동 (전입 - 전출)")
move_in_2030   = Column(Integer, comment="20-30대 전입자 수")
move_out_2030  = Column(Integer, comment="20-30대 전출자 수")
```
COMMENT: `'담당: 찬영 | 서울 전체 동별 월간 전입/전출 | 출처: 행정안전부 주민등록 이동통계'`

#### `seoul_ttareungi_usage_daily`
```python
date       = Column(Date, primary_key=True, comment="이용일")
station_id = Column(String(20), ForeignKey("master_ttareungi_station.station_id"),
                    primary_key=True, comment="대여소 ID")
rent_cnt   = Column(Integer, comment="대여 건수")
return_cnt = Column(Integer, comment="반납 건수")
__table_args__ = (Index("ix_ttareungi_usage_station", "station_id"),)
```
COMMENT: `'담당: 찬영 | 서울 전체 따릉이 일×대여소 집계 | 출처: 서울 열린데이터광장 (raw 집계)'`

## 5. 적재 파이프라인

```
[1] CSV 다운로드 (Claude 가 직접 시도)
    저장: backend/data/seed/raw/<source>/<yyyymm>.csv
    소스:
      - 지하철 승하차       : data.seoul.go.kr
      - 따릉이 raw          : data.seoul.go.kr (월 zip)
      - 따릉이 master       : data.seoul.go.kr
      - 지하철 master + 좌표: data.seoul.go.kr + 국가공간정보
      - 전입/전출           : KOSIS 또는 행안부 (로그인 필요 시 사용자 패스)
    실패 시: 사용자에게 URL 안내 → 수동 투입 폴백

[2] 정제 스크립트 (backend/scripts/ingest/  ← 신설 디렉토리)
    ├─ ingest_subway_passenger.py   -- 컬럼/날짜 정규화, master 추출
    ├─ ingest_dong_migration.py     -- 동코드 8자리 정규화, 20-30대 집계
    └─ ingest_ttareungi.py          -- raw → 일×대여소 집계 (Pandas/DuckDB)
    출력: backend/data/seed/<table>_<yyyymm>.csv  (seed_from_csv 호환 형식)

[3] Alembic 마이그레이션 (1 개)
    add_emerging_trend_b1_tables.py
      - master_subway_station, master_ttareungi_station
      - seoul_subway_passenger_daily, seoul_dong_migration_monthly,
        seoul_ttareungi_usage_daily
      - 인덱스 + COMMENT 포함

[4] seed_from_csv.py 확장
    SKIP_TABLES 갱신, 5개 테이블 COPY 정상 동작 확인

[5] 검증 (backend/scripts/verify/verify_emerging_trend_data.py)
    행 수 / 마포 행 수 / 날짜 범위 / NULL 비율 / 중복 PK 점검
```

### 5.1 병렬 실행 전략

[2] 정제 단계의 3개 ingest 스크립트는 **상호 의존 없음** → subagent 3개로 병렬 실행 가능.
[3] 마이그레이션과 [4] seed 적재는 직렬 (Alembic 단일 head 보장).

## 6. 마포 필터링 — 사용 예시

```sql
-- 합정/홍대/망원역 일별 승하차 (최근 12개월)
SELECT date, m.station_name, p.boarding_cnt, p.alighting_cnt
FROM seoul_subway_passenger_daily p
JOIN master_subway_station m USING (station_code)
WHERE m.sigungu_code = '11440'
  AND date >= CURRENT_DATE - INTERVAL '12 months';

-- 마포 동별 20-30대 순유입 (최근 6개월)
SELECT ym, d.dong_name, (move_in_2030 - move_out_2030) AS net_2030
FROM seoul_dong_migration_monthly m
JOIN seoul_dong_master d USING (dong_code)
WHERE d.dong_code LIKE '11440%'
  AND ym >= 202510
ORDER BY ym DESC, net_2030 DESC;

-- 마포 동별 따릉이 월간 이용량
SELECT TO_CHAR(date, 'YYYYMM') AS ym, m.dong_code,
       SUM(rent_cnt) AS rent_cnt, SUM(return_cnt) AS return_cnt
FROM seoul_ttareungi_usage_daily u
JOIN master_ttareungi_station m USING (station_id)
WHERE m.sigungu_code = '11440'
GROUP BY 1, 2;
```

별도 마포 전용 테이블 신설 없음 (CLAUDE.md 룰).

## 7. 에러 처리 / 검증

| 상황 | 정책 |
|------|------|
| CSV 다운로드 실패 | 사용자에게 URL 안내, `data/seed/raw/` 수동 투입 폴백 |
| 컬럼명/포맷 변경 | ingest 스크립트 명시적 raise (silent fail 금지) |
| dong_code 매칭 실패 | row reject → `reject/<table>_<ym>.csv` 분리 보관 |
| 중복 PK | 사전 dedup 또는 COPY 후 `ON CONFLICT DO NOTHING` |
| 검증 게이트 | `verify_emerging_trend_data.py` 통과 필수 (PR 머지 전) |

## 8. 테스트

- ingest 스크립트별 unit test (`tests/ingest/test_<source>.py`)
  - 샘플 CSV 입력 → 기대 DataFrame 출력 골든 테스트
- Alembic up/down 양방향 테스트 (`tests/db/test_migrations.py` 확장)
- 마포 필터 sanity check (`tests/data/test_emerging_trend_filters.py`)
- 5년치 적재 후 검증 스크립트 결과 → spec 디렉토리에 마크다운으로 기록

## 9. 명시적 비범위 (재확인)

- 자동 fetch 스케줄러
- ML 학습 / feature engineering
- 대시보드 / API endpoint 노출
- B2: 건축인허가, 공시지가 (별도 spec, 동일 패턴 적용 예정)
- 시간대별 지하철 raw, OD 따릉이 raw (필요 시 archive 별도 도입)

## 10. 오픈 이슈

- KOSIS / 행안부 다운로드가 로그인 필요한지 실측 후 폴백 결정
- 따릉이 master 데이터 갱신 주기 (월? 분기?) 확인 필요
- `seoul_dong_master` 8자리 코드 커버리지 확인 (전입출 동코드 매칭 누락 비율)
- **지하철역 코드 체계 통합**: 서울교통공사(1-8호선), 한국철도공사(공항철도, 경의중앙선 등), 서울9호선 운영사가 자체 코드 체계를 쓰는 경우 통합 키 정의 필요. ingest 단계에서 `(station_name + line_name)` 해시로 surrogate `station_code` 발급하는 정책 검토.
- **환승역 처리**: 공덕역 (5/6/공항철도/경의중앙) 같은 환승역이 master 에서 1행 vs 노선별 N행 보관할지. 현재 schema 는 `station_code` PK 단일 행 가정. 노선별 승하차 분리 필요하면 `(station_code, line_name)` composite key 로 변경.

---

## Approval

이 spec 은 사용자 리뷰 후 `writing-plans` 스킬로 implementation plan 으로 전개된다. plan 단계에서 5개 테이블 마이그레이션, 3개 ingest 스크립트, seed_from_csv 확장, 검증 스크립트, 테스트를 **subagent 병렬 3개 + 직렬 마이그레이션** 패턴으로 분배한다.
