# Alembic phantom revision 복구 가이드

> 작성: 2026-05-04 (audit-2026-05-04 후속)
> 대상: A1 데이터 엔지니어 또는 DB 권한 보유자
> ⚠️ DB 변경 작업 — 실행 전 반드시 백업 + 다른 팀원에 통보

---

## 문제 요약

### Issue 1: alembic phantom revision

DB 의 `alembic_version` 테이블에 `a9c2d3e4f5b6` 가 적혀있는데, `backend/alembic/versions/` 폴더에 해당 .py 파일이 **없음**. 추적 불가능한 phantom 상태.

```bash
$ alembic current
# 출력: a9c2d3e4f5b6  (파일 없음 → 어떻게 적용됐는지 추적 안 됨)

$ ls backend/alembic/versions/ | grep a9c2d3e4f5b6
# (없음)
```

기존에도 비슷한 phantom (`18bfead869d5`) 이 있었음 (memory 기록). 동일 패턴.

### Issue 2: simulation_history 테이블 미존재

코드(`backend/src/database/models.py`, `schemas/`, `services/`, `tests/`) 와 마이그레이션(`a2f3b6d84e9c_add_simulation_history.py`) 은 존재하지만 DB 에 실제 테이블 없음.

**원인 추정**: phantom revision `a9c2d3e4f5b6` 가 코드 head 와 다른 위치라서 `a2f3b6d84e9c` 마이그레이션이 실행되지 않음.

```bash
$ python -c "
from src.config.settings import settings
import sqlalchemy as sa
e = sa.create_engine(settings.postgres_url)
with e.connect() as c:
    print(c.execute(sa.text(\"SELECT to_regclass('public.simulation_history')\")).scalar())
"
# 출력: None
```

---

## 복구 절차

### Phase 0: 사전 점검

```bash
# 1. DB 백업
pg_dump -h localhost -U postgres -d mapo_simulator > /tmp/mapo_pre_recovery_$(date +%Y%m%d).sql

# 2. 현재 alembic 상태
cd backend && alembic current
cd backend && alembic heads
cd backend && alembic history --verbose | head -30

# 3. 코드 head 확인
ls -t backend/alembic/versions/ | head -5
```

### Phase 1: phantom 원인 식별

`a9c2d3e4f5b6` 가 어디서 왔는지 git log:

```bash
git log --all --oneline -S "a9c2d3e4f5b6" -- backend/alembic/
git log --all --oneline -- "backend/alembic/versions/a9c2d3e4f5b6*"
```

이전 commit 에서 파일이 삭제됐다면 `git show <commit>:backend/alembic/versions/a9c2d3e4f5b6_*.py` 로 내용 복원 가능.

### Phase 2: 복구 옵션 선택

| 옵션 | 명령 | 위험도 | 권장 |
|---|---|---|---|
| **A** | `alembic stamp <code_head_revision>` 후 `alembic upgrade head` | LOW | ⭐ 권장 |
| **B** | phantom recovery 빈 .py 파일 생성 + chain 잇기 | MEDIUM | 감사 추적 필요 시 |
| **C** | `UPDATE alembic_version SET version_num = '<head>'` 직접 | HIGH | 비추천 |

#### 옵션 A 상세 (권장)

```bash
# 1. 코드의 실제 head revision 확인
cd backend && alembic heads
# 예: cc33dd44ee55 (head)

# 2. DB 를 코드 head 로 강제 stamp (실제 마이그레이션 실행 안 함, alembic_version 만 업데이트)
cd backend && alembic stamp cc33dd44ee55

# 3. 누락된 테이블 (simulation_history) 별도 적용 — 마이그레이션 down_revision 체인에 들어있으므로
#    stamp 후엔 head 가 cc33dd44ee55 라서 a2f3b6d84e9c 자동 적용 안 됨.
#    수동 실행:
cd backend && alembic upgrade a2f3b6d84e9c+ --sql > /tmp/simhist_upgrade.sql
# 출력 SQL 검토 후
psql -h localhost -U postgres -d mapo_simulator -f /tmp/simhist_upgrade.sql

# 또는 테이블만 직접 생성 (a2f3b6d84e9c_add_simulation_history.py 의 op.create_table 내용 그대로):
# (해당 마이그레이션 파일 참조 후 SQL 추출)

# 4. 검증
cd backend && alembic current
python -c "
from src.config.settings import settings
import sqlalchemy as sa
e = sa.create_engine(settings.postgres_url)
with e.connect() as c:
    print(c.execute(sa.text(\"SELECT to_regclass('public.simulation_history')\")).scalar())
"
# 출력: simulation_history (성공)
```

### Phase 3: 사후 검증

```bash
# 모든 ORM 모델이 DB 에 있는지
python backend/scripts/diagnostics/gen_db_schema_doc.py
# zombie 모델 (DB 없음) 표시 확인 — 0 이 정상

# 통합 테스트
cd backend && pytest tests/test_simulation_history_service.py -v
```

---

## 롤백

문제 발생 시:

```bash
psql -h localhost -U postgres -d mapo_simulator < /tmp/mapo_pre_recovery_<date>.sql
```

복구 전 백업이 필수. Phase 0 단계 반드시 수행.

---

## 향후 예방

1. **alembic 마이그레이션 파일 삭제 금지** — head 변경 시 git revert 또는 새 마이그레이션 추가
2. **`alembic stamp` 사용 후 git commit 메시지에 명시** — phantom 추적 가능
3. **CI 에 `alembic check`** 추가 (DB head ↔ 코드 head 정합 검증)
4. **`backend/scripts/diagnostics/gen_db_schema_doc.py`** 정기 실행으로 zombie/phantom 조기 감지
