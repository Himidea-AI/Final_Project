# Ingest pipelines — 신흥 상권 B1 (인구·이동성)

서울 인구·이동성 공공데이터 3종을 PostgreSQL 적재한다.

| 데이터셋 | 출처 | 위치 | 비고 |
|----------|------|------|------|
| 지하철 일별 승하차 (OA-12921) | data.seoul.go.kr | `master_subway_station`, `seoul_subway_passenger_daily` | 서울교통공사 1~8호선만, 2023~2024 |
| 따릉이 일별 이용 (OA-15246) | data.seoul.go.kr | `master_ttareungi_station`, `seoul_ttareungi_usage_daily` | 일×대여소 집계 (raw 대여이력 X) |
| 따릉이 대여소 마스터 (OA-13252) | data.seoul.go.kr | `master_ttareungi_station` | 좌표/주소/자치구 — xlsx |
| 동별 인구이동 | KOSIS / 행안부 | `seoul_dong_migration_monthly` | **수동 다운로드 필요** (API key 있어도 동 단위 데이터 가용성 미확정) |

## 흐름

```
[1] 다운로드:
    python -m scripts.ingest.download_raw          # 자동 시도 (subway/ttareungi 일부)
    또는 사용자가 manual 다운로드 → backend/data/seed/raw/<source>/

[2] 정제 (raw → seed CSV):
    python -m src.ingest.ingest_subway_passenger \
        --raw-dir data/seed/raw/subway --cleaned-dir data/seed --reject-dir data/seed/raw/reject
    python -m src.ingest.ingest_dong_migration \
        --raw-dir data/seed/raw/migration --cleaned-dir data/seed --reject-dir data/seed/raw/reject
    python -m src.ingest.ingest_ttareungi \
        --raw-dir data/seed/raw/ttareungi --cleaned-dir data/seed --reject-dir data/seed/raw/reject

[3] 마포 sigungu_code 패치 (마스터 테이블):
    아래 ad-hoc 스크립트 (마포 station 화이트리스트 정규식)

[4] DB 적재 (psycopg COPY 또는 seed_from_csv):
    POSTGRES_URL=... python -m scripts.seed_from_csv --dir data/seed
    또는 직접:
    POSTGRES_URL=... python -c "..."  # COPY 호출

[5] 검증:
    python scripts/verify/verify_emerging_trend_data.py
    pytest tests/data/test_emerging_trend_filters.py -v -m integration
```

## 데이터 소스 직접 다운로드 URL

서울 열린데이터광장은 `downloadFile('seq')` JS handler 를 사용. 실제 endpoint:

```
POST https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false
form: infId=<OA-XXXX>, seqNo='', seq=<seqNo>, infSeq=<infSeq>
```

`infSeq` 값은 데이터셋 페이지의 `<form name="frmFile">` 안 hidden input 에서 추출.
세션 쿠키 (data.seoul.go.kr 방문 후 획득) + Referer 헤더 필요.

OA-12921 (지하철) 은 별도 endpoint 사용 가능: `/bigfile/iot/sheet/csv/download.do?srvType=S&infId=OA-12921&serviceKind=1` — GET 단일 파일.

## KOSIS 인구이동

KOSIS_API_KEY 가 .env 에 있지만:
- DT_1B26001 (시군구별 인구이동) 은 시군구 단위까지만 — **동 단위 X**
- 행정동 단위 인구이동은 KOSIS 외부 (행정안전부 EMD 시스템) 일 가능성
- API objL/itmId 파라미터가 까다로워 시행착오 필요

권장: KOSIS 통계 사이트에서 [DT_1B26001](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B26001) 직접 다운로드 → `data/seed/raw/migration/` 투입.
