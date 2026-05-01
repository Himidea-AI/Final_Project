# CLAUDE.md

> Claude Code 전용 추가 지시. 공통 규칙은 `AGENTS.md`를 참조합니다.

## 필수 참조

- 작업 전 반드시 `AGENTS.md`를 읽고 팀원별 담당 영역을 확인하세요.
- 현재 작업자의 담당 디렉토리 외 파일을 수정하지 마세요.

## 작업 방식

- 코드 수정 전 관련 파일을 먼저 읽어서 기존 패턴을 파악하세요.
- Python 코드 작성 후 `ruff check --fix` 및 `ruff format`을 실행하세요.
- 프론트엔드 코드 작성 후 `cd frontend && npx prettier --write .`을 실행하세요.

## 커밋

- 사용자가 요청할 때만 커밋하세요.
- 커밋 메시지는 변경 내용을 명확히 설명하세요.

## DB 테이블 네이밍 규칙

새 테이블을 만들 때 반드시 아래 규칙을 따르세요. 기존 테이블은 건드리지 않습니다.

### 접두사 규칙

| 접두사 | 용도 | 예시 |
|--------|------|------|
| `seoul_` | 서울 전역 데이터 | `seoul_district_sales` |
| `mapo_` | 마포구 전용 데이터 | `mapo_resident_pop` |
| `master_` | 코드/매핑 마스터 테이블 | `master_dong`, `master_industry` |
| (없음) | 서비스 기능 테이블 | `users`, `simulation_history` |

### 네이밍 형식

- `{범위}_{데이터주제}_{시간단위}` 순서로 작성
- 예: `seoul_adstrd_flpop` (서울 + 행정동 + 유동인구)
- 단어 구분은 언더스코어(`_`), 약어는 서울열린데이터 원본 따름 (`adstrd`, `signgu`, `trdar`, `flpop`, `fclty`)

### 금지 사항

- 접두사를 뒤에 붙이지 마세요: ~~`district_sales_seoul`~~ → `seoul_district_sales`
- 백업 테이블을 운영 DB에 만들지 마세요: ~~`xxx_backup_20260420`~~
- 동일 데이터의 마포 필터 버전을 별도 테이블로 만들지 마세요. 서울 전역 테이블에서 `WHERE dong_code LIKE '114%'`로 필터하세요.

### COMMENT 필수

테이블 생성 시 반드시 COMMENT를 추가하세요:

```sql
COMMENT ON TABLE 테이블명 IS '담당: 이름 | 용도 설명 | 출처: 데이터소스';
```

## 프로젝트 실행

```bash
# 백엔드 개발서버
cd backend && uvicorn src.main:app --reload

# 프론트엔드 개발서버
cd frontend && npm run dev

# 전체 서비스 (Docker)
docker compose up --build
```
