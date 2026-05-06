# 2026-05-05 — 코드베이스 전체 리뷰 (ultrareview 대체)

## 증상

`/ultrareview` 무료 한도 소진. `code-reviewer` 서브에이전트 6개 병렬 디스패치로 전체 코드베이스 수동 리뷰 수행.

## 진단 환경

- 브랜치: `dev`
- 기준 커밋: `cd79bf30` (Merge PR #198, IM3-etl-refill-ttareungi-ecos)
- 리뷰 도구: `code-reviewer` subagent × 6 (병렬)
- 리뷰 범위:
  1. `backend/src/agents/` (graph, edges, state, nodes, legal/, llms, tools)
  2. `backend/src/services/` (외부 API 클라이언트 + 비즈니스 로직 25+ 파일)
  3. `backend/src/database/` + `api/` + `main.py` + `schemas/` + `config/`
  4. `backend/src/simulation/` + `chains/` + `ingest/`
  5. `frontend/src/` (React 전체)
  6. `tests/` + `scripts/` + 인프라/CI/Docker/설정

## 우선순위 요약

| 등급 | 건수 | 의미 |
|------|------|------|
| P0 (Critical) | 2 | 즉시 수정. 비용 폭증·동시성 race |
| P1 (High) | 24 | 머지 전 수정 권장. 보안/SQL/async/lifespan |
| P2 (Medium) | 다수 | 백로그 등록 |

---

## P0 — CRITICAL (즉시 수정)

### P0-1. `simulation/brain.py` — `except Exception: pass` 다발로 토큰 추적 침묵

**위치**: `backend/src/simulation/brain.py:118-119, 401-402, 439-440, 534-535, 1096-1097, 1197-1198`

LangSmith usage 첨부 및 토큰 카운트 누적 라인이 silent fail. 비용 추적 누락이 누적되어 LLM 비용 폭증을 뒤늦게 인지하는 경로. ABM 시뮬레이션은 LLM 기반(Haiku+Flash) `~$0.7/일` 통제가 critical.

**수정안**: `pass` → 최소 `logger.debug(...)` 또는 `logger.warning(...)`. `_ls_attach_usage` 내부는 debug 수준, 토큰 누적 라인은 warning.

### P0-2. `simulation/runner.py:_STATIC_CACHE` — lock 없는 모듈 dict

**위치**: `backend/src/simulation/runner.py:64-78`

모듈 수준 dict를 락 없이 read/write. uvicorn `--workers 2+` 또는 background task 동시 호출 시:
- 첫 `loader()` 가 두 번 실행 (비용)
- 부분 write 중 다른 요청이 `(ts, val)` 튜플을 덜 쓴 상태로 read

**수정안**: `threading.Lock()` 보호 또는 TTL 없는 항목은 `functools.lru_cache`.

---

## P1 — HIGH (머지 전 수정 권장)

### 보안 / SQL

#### P1-S1. f-string SQL 동적 조립

| 위치 | 문제 |
|------|------|
| `services/auth.py:830, 832` | `set_clause` whitelist 키만 추출하나 패턴 자체가 위험. 키 목록 변경 시 즉시 인젝션 |
| `services/auth.py:883, 895` | `table = "users" if role == "master" else "manager_users"`. role Pydantic 검증 누락 시 임의 테이블 가능 |
| `services/simulation_ai_service.py:135, 148-151, 203` | `where_sql`, `access_filter`, `order_sql` f-string 삽입. `sort` whitelist 없음 |
| `services/simulation_foresee_service.py:131, 198` | 동일 패턴 |
| `services/operational_fit.py:177` | `cols_sql` 컬럼명 동적 삽입. 현재 내부 상수지만 안전성 미보장 |
| `scripts/validate_simulation.py:256` | `_MAPO_STATION_HINTS` f-string 삽입. 외부 입력 변경 시 인젝션 |

**수정안**: `sort` → `Literal["created_at_desc","client_name_asc"]` Pydantic 강제. `table` → `{"master":"users","manager":"manager_users"}` dict 매핑. SQLAlchemy `literal_column` 또는 ORM 컬럼 참조.

#### P1-S2. SGIS — secret이 URL 로그에 노출

**위치**: `backend/src/services/sgis_api.py:29-35, 57-63`, `backend/src/services/base_client.py:30`

`authenticate()`가 `consumer_key` + `consumer_secret`을 `params`로 전달. `BaseAPIClient._log("TOOL_CALL", f"{method.upper()} {url}")`이 풀 URL 출력 → httpx가 params를 쿼리스트링으로 붙여 secret이 그대로 로그 기록.

`get_resident_population` 등 3개 메서드도 `accessToken`을 params에 포함, 동일 노출.

**수정안**: `_log`에서 URL 출력 시 params 분리 후 민감 키 (`consumer_key`, `consumer_secret`, `accessToken`, `serviceKey`) 마스킹.

#### P1-S3. JWT 시크릿 기본값 코드 노출

**위치**: `backend/src/config/settings.py:139`

```python
jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-only-not-secret-replace-in-prod")
```

운영에서 `.env` 미설정 시 취약 고정 문자열로 JWT 서명.

**수정안**: pydantic `@validator` 또는 `min_length`로 `APP_MODE=PROD` 시 공백/기본값이면 `ValueError`.

#### P1-S4. 운영 DB 파괴 스크립트

| 위치 | 문제 |
|------|------|
| `scripts/collect_reb_small_store_rent.py:130` | `ensure_schema()` 매 실행 `DROP TABLE IF EXISTS`. dry-run 없음 |
| `scripts/load_v4_to_db.py` | `TRUNCATE seoul_district_sales_imputed_v4` 즉시 실행. CSV 검증 전 발생 |

**수정안**: `--dry-run` 플래그 추가, CSV 존재·헤더 검증 후 truncate, 운영 환경 가드.

#### P1-S5. CI action SHA 미고정

**위치**: `.github/workflows/deploy.yml:92`, `auto-pr-title.yml:14`

`appleboy/ssh-action@v1`, `actions/checkout@v4`, `actions/github-script@v6` 모두 부동 태그. 브랜치 손상 시 운영 서버에 임의 코드 실행 가능.

**수정안**: `appleboy/ssh-action@<full-sha>` 형태 SHA pin.

#### P1-S6. 무인증 고부하 엔드포인트

**위치**: `backend/src/api/vacancy_evaluation.py:104-162`

`POST /vacancy-evaluation/single`이 5~10분 ABM 시뮬을 무인증으로 호출. rate limit 미들웨어가 `/simulate`, `/analyze`만 커버. `async_mode=True` background task도 무인증.

**수정안**: rate limit 경로에 `/vacancy-evaluation` 추가. Bearer 인증 추가.

#### P1-S7. 사용자 입력 LLM 프롬프트 직접 삽입 — prompt injection

**위치**: `backend/src/simulation/runner.py:548, 692-700`

`scenario.new_store.brand` 등 프론트엔드 입력이 `scenario_block` 으로 LLM 프롬프트 직삽입. 특수 JSON 문자, 지시 오버라이드 문자열 허용 시 프롬프트 구조 파괴.

**수정안**: 공백 정규화 + 길이 cap + 허용 문자 whitelist.

#### P1-S8. 프론트 JWT localStorage

**위치**: `frontend/src/auth/AuthContext.tsx:60`, `frontend/src/api/client.ts:69`

JWT access token `localStorage` 평문 저장. refresh token 갱신 로직 없음. 401 시 전체 세션 파기.

**수정안**: 단기 — 별도 이슈 등록, 토큰 회전 정책 문서화. 장기 — httpOnly cookie.

### Async / 이벤트루프 / Lifespan

#### P1-A1. `legal/rules.py:_fetch_mapo_schools` — async에서 동기 SQLAlchemy 블로킹

**위치**: `backend/src/agents/legal/rules.py:696-741`

`rule_school_zone()`이 async (`asyncio.gather`) 안에서 `get_sync_engine()` → `engine.connect()` 직접 호출. 이벤트루프 전체 블로킹.

**수정안**: `asyncio.to_thread`로 감싸거나 async 엔진 전환.

#### P1-A2. `vector_db.py` — async 안에서 psycopg2 동기 연결 + bare except

**위치**: `backend/src/database/vector_db.py:108-134, 96-98`

`get_total_count()`가 async 컨텍스트에서 `psycopg2.connect()` 직접 호출. `except Exception as e: print(...)` 패턴. `vectorstore` property 초기화 실패 시 `return None` → 호출자 None 가드 없으면 `AttributeError`.

**수정안**: `asyncpg` 또는 `run_in_threadpool` 이전. `logger.error` 사용. property는 None 대신 명시적 예외.

#### P1-A3. `simulation/brain.py:646` — async 안에서 `asyncio.run()`

```python
return _aio.run(_run_all())
```

FastAPI 엔드포인트(`/simulate-abm`) running loop 안에서 `asyncio.run()` 호출 → `RuntimeError`. 645-655 fallback이 `new_event_loop()` 생성하지만 `ThreadPoolExecutor` 안에서 중복 루프 위험.

**수정안**: 전체 brain 호출을 async 체인으로 전환. 또는 `run_in_executor` + `concurrent.futures` 통일.

#### P1-A4. `chains/retriever.py:_expand_query_hybrid` — Redis 조기 return 시 close 누락

**위치**: `backend/src/chains/retriever.py:331, 334-336, 413-415`

`aioredis.from_url()` 매 HyDE 호출마다 새 풀 생성. 캐시 히트 경로(334-336)에서 조기 return 시 `finally` 블록에 도달 못 해 close 누락 가능성.

**수정안**: 앱 수준 shared Redis 클라이언트 사용. 또는 try 시작점을 `from_url()` 직후로 명확히.

#### P1-A5. `main.py:171` — deprecated `on_event` + lifespan 누락

**위치**: `backend/src/main.py:171`

FastAPI 0.93+에서 `@app.on_event` deprecated. `PostgresClient.connect()`, `RedisClient.connect()`, `LegalVectorDB.dispose()` 호출이 lifespan에 없음 → `RuntimeError("Not connected")` 경로 잠재.

**수정안**: `lifespan` 컨텍스트 매니저로 교체, startup connect / shutdown dispose 명시.

### LLM / 에이전트 / 도메인

#### P1-L1. `agents/llms.py` — LLMRetryProxy 중첩 + 싱글톤 race

**위치**: `backend/src/agents/llms.py:58-61, 111-132`

- `with_structured_output()`가 내부 LLM 객체에서 새 runnable 생성 후 다시 `LLMRetryProxy`로 감쌈 → retry 2중 적용. `max_retries=5` × 5 = 최대 25회 재시도. 429 복구 지연 폭증.
- `get_fast_llm._instance` / `get_smart_llm._instance` 함수 속성 싱글톤 패턴 thread-safety 없음. 단일 프로세스 첫 동시 요청 시 중복 생성 경로.

**수정안**: 중첩 retry 가드 추가. `threading.Lock()` 또는 모듈 lazy init.

#### P1-L2. `agents/edges.py:29` — Pydantic state에 `.get()` 호출

```python
state.get("iteration_count", 0)
```

`AgentState`는 Pydantic BaseModel. `.get()`은 dict 메서드 → 런타임 `AttributeError`. 단 `should_reanalyze`는 `add_conditional_edges` 미등록으로 사문화 가능성 — 사용 여부 확인 후 dead code 삭제 또는 `getattr` 변경.

**수정안**: `getattr(state, "iteration_count", 0)`. 사문화면 제거.

#### P1-L3. `agents/tools.py:412` — `mapo_avg = 150000` 하드코딩

**위치**: `backend/src/agents/tools.py:412`

```python
mapo_avg = 150000  # 예시: 마포구 평균 15만원
```

`affordability: SAFE/CAUTION` 판단 기준값이 LLM 프롬프트로 주입됨.

**수정안**: `golmok_rent` 실측 평균 서브쿼리 또는 `settings.mapo_avg_rent` 환경변수.

#### P1-L4. `state.py` AgentState ↔ 실제 런타임 상태 불일치

**위치**: `backend/src/agents/state.py:35-51`

노드들이 수십 개 키 (`winner_district`, `scouting_results`, `tcn_sim_result` 등)를 `state.get(...)` 으로 접근하지만 `AgentState` 모델에는 없음. LangGraph state validation 사실상 무효. `src/schemas/state.py` 와 `src/agents/state.py` 분리도 혼선.

**수정안**: 단일 source state schema 통합. 누락 필드 추가 또는 `dict[str, Any]` 명시.

#### P1-L5. `services/brand_mapping_resolver.py` — DB 실패가 영구 캐시

**위치**: `backend/src/services/brand_mapping_resolver.py:54-76`

`_load_db_brands()`가 `@lru_cache(maxsize=1)`로 감싸짐. DB 일시 실패 → 빈 `{}` 영구 캐시 → 서버 재시작 전까지 16K 브랜드 무효화, 수동 fallback만 사용.

**수정안**: `lru_cache` 제거 + 모듈 변수 + 명시적 reload. 또는 빈 dict 반환 시 캐시 무효화 wrapper.

#### P1-L6. Silent fallback `except Exception:` (서비스 레이어)

| 위치 | 영향 |
|------|------|
| `services/operational_fit.py:168-169` | `bus_boarding_daily` 쿼리 실패 무시 |
| `services/biz_mapper.py:84, 130` | 브랜드 검색 실패 무시 |
| `services/population_api.py:44, 64` | httpx + json 오류 구분 없이 삼킴 |

**수정안**: `except (httpx.HTTPError, json.JSONDecodeError)` 구체화 + 최소 `logger.warning`.

### API / 스키마 / DB

#### P1-D1. UUID 파싱 오류에 401 반환

**위치**: `backend/src/api/simulation_foresee.py:32-33`, `backend/src/api/simulation_ai.py:32-33`

JWT 추출 user_id가 잘못된 UUID → 401. 인증 실패가 아닌 데이터 정합성 → 422 또는 500 적절. 401은 클라이언트에 "재인증" 잘못된 시그널.

#### P1-D2. DB 네이밍 규칙 위반 + COMMENT 누락

**위치**: `backend/src/database/models.py`

| 테이블 | 문제 |
|--------|------|
| `living_population` (`:42`) | 서울 전역이면 `seoul_adstrd_flpop` 권장 |
| `district_sales` (`:149`) | 마포 한정이면 `mapo_*` |
| `golmok_commercial` (`:131`), `golmok_sales` (`:704`), `golmok_stores` (`:767`) | `seoul_*` 계열 중복 가능성 |
| `elderly_ratio_region` (`:1005`), `bus_boarding_daily` (`:1053`), `apt_trade_real` (`:1027`) | `seoul_` prefix 누락 추정 |

`__table_args__`에 COMMENT 정의된 테이블이 `simulation_foresee`/`simulation_ai` 2개뿐. CLAUDE.md "COMMENT 필수" 위반.

#### P1-D3. `updated_at` `onupdate` 미설정

**위치**: `backend/src/database/models.py:426 (DongCentroid)`, `:460 (User)`

```python
updated_at = Column(DateTime, server_default=func.now(), comment="수정 일시")
```

UPDATE 시 자동 갱신 안 됨. `onupdate=func.now()` 필요.

#### P1-D4. `useElasticityComparison` race condition

**위치**: `frontend/src/hooks/useElasticityComparison.ts:86-108`

`Promise.allSettled().then()` 안 `forEach` 내부 `return`이 상위 종료 안 함. `axios.isCancel(reason)` 케이스에서 `next` Map에 stale `loading: true` 고착.

**수정안**: `forEach` → `for...of` + `continue`.

---

## P2 — MEDIUM (백로그)

### 단일 진실 소스 / 코드 중복

- `agents/nodes/district_ranking.py:64-79` ↔ `agents/tools.py:34-59`: `_KAKAO_CATEGORY_MAP` 인라인 재정의. 두 맵 drift 시 데이터 불일치
- `simulation_foresee.py` ↔ `simulation_ai.py`: `_to_uuid`, Save Request 모델, CRUD 패턴 거의 동일. `_BaseSimRouter` 추출 권장
- `scripts/validate_simulation.py`: `validate_population`, `validate_category_distribution`, `validate_bus_flow` 마다 `create_engine` 재생성. 모듈 단일 engine + dispose

### 누수/Cleanup

- `agents/nodes/synthesis.py:384-411`: LLM fallback 분기에서 Redis aclose 누락 가능. `_redis` 생성과 close를 더 바깥 try/finally로
- `simulation/runner.py:134-237` (`_load_dong_coords`, `_load_weather_recent`, `_load_holidays`): TTL 만료 후 매번 새 engine 생성. 모듈 싱글톤 권장
- `main.py:106` `_check_rate_limit`: 매 요청마다 `aioredis.from_url`. RedisClient 싱글톤 재사용

### 검증/타입

- `api/sensitivity.py:90-108`: `dong_code`/`industry_code` 8자리 validator 미적용 (commit `8c8302ce`와 일관성 깨짐)
- `simulation/brain.py:1240`: LLM `spend` 음수/거대값 무방비
- `chains/retriever.py:548`: `RELEVANCE_THRESHOLD = 0.3` 하드코딩 (`.env` 외부화 미적용)
- `simulation/runner.py:329`: `hasattr(brain, 'generate_thoughts_batch')` duck-typing — 인터페이스 명시화
- `frontend/api/client.ts:159, 161`: `as AnalysisOutput` 단언 — Zod 또는 type guard
- `frontend/stores/abmStore.ts:45, 74, 89, 102`: `result: any`, `langgraph_result: any` 다수
- `database/models.py FtcBrandFranchise:490-502`: camelCase (`corpNm`) 컬럼명. snake_case 통일

### 경고/로그 누락

- `agents/legal/specialists.py:439-449, 456-478, 595-607, 722-736`: `type` 강제 보정 silent. `logger.warning` 추가
- `agents/nodes/demographic_depth.py:187, 215, 265, 367, 382, 390`, `district_ranking.py:803, 866, 983`, `legal.py:931, 945`: bare `except Exception:` 다수
- `services/auth.py`: `try/finally: pass` 약 15개 메서드 반복 (의미 없음)
- `services/base_client.py:42-51`: `post()`에 retry 미적용 (`get()`은 retry 데코레이터 적용)
- `services/population_api.py:57-58`: API 키 URL 경로 노출 — 액세스 로그 마스킹 정책 명시 필요
- `simulation/conversation.py:211-275`: 대화 LLM 호출 silent fallback. `stats.failures` 연결

### 프론트

- `components/abm/PersonaPreviewStream.tsx:54-73`: `pool` deps inline 배열. `useMemo` 또는 `[businessType]`으로
- `components/GlobalNav.tsx:217`, `pages/landing/AboutPage.tsx:206, 307`: index를 key로 사용
- `App.tsx:783, 909`, `hooks/useSimulationHistory.ts:107`, `components/simulation/SpotterAgentWorkflow.tsx:181`: `eslint-disable react-hooks/exhaustive-deps` 남용. SpotterAgentWorkflow는 stale closure 실재
- `components/NetworkBackground.tsx:110-123`: 350 파티클 O(n²) 매 프레임 — 격자/quadtree
- `components/simulation/SpotterAgentWorkflow.tsx:324-332`: `<div onClick>` 패턴 → `<button>`로 교체 (a11y)
- `components/kakao/useKakaoMap.ts:44`: `VITE_KAKAO_MAP_API_KEY` 빌드 인라인 — 도메인 화이트리스트 확인

### 인프라/CI

- `tests/test_agents.py`, `tests/test_competition.py`: `pass`만. 빈 테스트 green = 거짓 신호
- `pyproject.toml`: mypy/pyright/bandit 설정 없음 — H3 SQL 인젝션 자동 감지 불가
- `backend/requirements.txt`: 전부 `>=`. `pip-compile` lock 필요
- `frontend/Dockerfile:10`: `tsc` 없이 `vite build` — 타입 오류 prod 배포
- `docker-compose.prod.yml:46`: Redis `6379:6379` 호스트 노출 → `ports` 제거
- `scripts/run_tests.sh:5-7`: `xargs`로 `.env` export 패턴 공백 변수 오동작
- `agents/graph.py:180-235 ml_prediction_phase_node`: 함수 본체 lazy import 3개 → top-level import + ImportError guard

### 기타

- 루트 `tmp_*.py` 33개: `.gitignore` 패턴이 제거되면 일괄 추가 위험. `scratch/` 디렉토리 이동 권장
- `auto-pr-title.yml`: `permissions: pull-requests: write` 만 명시. SHA 미고정과 결합 시 권한 탈취 경로
- `simulation/config.py:211`: `log_llm_call`이 `print()`. `logger.info`로 통일
- `backend/agents/edges.py:29` `should_reanalyze`: TODO 3개 + 항상 `"generate_report"` 반환. `add_conditional_edges` 미등록 → 사문화 dead code

---

## 영향 매트릭스

| 영역 | P0 | P1 | P2 |
|------|-----|------|------|
| backend/agents | 0 | 5 | 8 |
| backend/services | 0 | 6 | 7 |
| backend/database+api+main+config | 0 | 6 | 4 |
| backend/simulation+chains+ingest | 2 | 4 | 5 |
| frontend | 0 | 2 | 7 |
| tests+scripts+infra | 0 | 3 | 8 |

## 권장 처리 순서

### 즉시 (이번 주)

1. P0-1, P0-2 (silent except, cache race)
2. P1-S3 (JWT 기본값 PROD 강제)
3. P1-S4 (DROP TABLE / TRUNCATE 가드)
4. P1-S5 (CI action SHA pin)
5. P1-L2 (`edges.py` Pydantic `.get()` 런타임 오류)

### 다음 스프린트

6. P1-S1 (f-string SQL whitelist 전면 교체)
7. P1-S2 (secret 로그 마스킹)
8. P1-A1, A2, A3 (async 블로킹/이벤트루프)
9. P1-D4 (useElasticityComparison race)

### 백로그

- P1-S8 (프론트 토큰 전략 문서화) — 별도 이슈
- P1-L3, L4, L5 (도메인 일관성)
- P2 전체

## 책임 영역

- A1 (찬영, 사용자): `backend/src/database/`, `services/`, `data/`
  - 직접 처리: P1-S1 (services SQL), P1-S2, P1-L5, P1-D2, P1-D3
- 다른 팀원 (AGENTS.md 참조): agents, simulation, chains, frontend, tests, infra
  - A1은 진단·이슈 등록까지. 수정은 담당자

## 검증 절차

- P0/P1 fix 후: 해당 파일 단위 테스트 + `ruff check --fix` + `ruff format`
- SQL 변경: parameterized 쿼리 회귀 테스트
- async 변경: `pytest -k async` + 로컬 uvicorn 부하 테스트
- 보안 변경: 운영 배포 전 security-review 재실행

## 참고 자료

- 리뷰 도구: `code-reviewer` subagent × 6 (병렬)
- 기준 커밋: `cd79bf30`
- 관련 이슈: `2026-04-28-end-to-end-data-flow-gaps.md` (state.py 분리 문제 P1-L4와 연계)
- CLAUDE.md DB 네이밍 규칙
- AGENTS.md 팀 책임 분담
- `spotter-async-cleanup`, `spotter-single-source` skill
