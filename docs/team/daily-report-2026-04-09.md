# 일일 작업 보고서 — 2026-04-09 (수)

## A1 — 데이터 엔지니어 (찬영 / bat1120)

| 커밋 | 내용 |
|------|------|
| `d460553` | load_to_db 9개 테이블 추가 + CSV 데이터 동기화 + Docker 포트 설정 개선 |
| `82e229e` | User 모델 추가 + 사업자등록번호 브랜드 매핑 API(`/biz/lookup`) + DB 연결 버그 수정 |
| `222ace8` | 회원가입 API 구현 (`POST /auth/signup`) |
| `4cdf449` | 로그인 API 구현 (`POST /auth/login`) |

**요약:**
- 회원 시스템 기반 작업: User 테이블 생성, 회원가입/로그인 API 구현
- 사업자등록번호 → 프랜차이즈 브랜드 매핑 서비스(`BizMapper`) 추가
- DB 적재 파이프라인 확장 (9개 테이블 신규), Docker 포트 설정 개선
- SQLAlchemy 2.x 호환 버그 수정 (`pd.read_sql` + `text()` + `conn`)

---

## A2 — RAG + 법률 (봉환 / bongbong-90)

| 커밋 | 내용 |
|------|------|
| `f4ba804` | legal_node 풀 파이프라인 고도화 |
| `ae46e94` | legal_node 버그 수정 및 테스트 업데이트 |
| `c3fd2cb` | main.py unused import 제거 및 ruff 포맷 정리 |
| `3a1df2a` | legal.py Redis 연결 누수 및 중복 import 수정 |
| `f579cde` | legal.py 임포트 경로 수정 및 articles 추출 개선 |
| `87c787f` | legal_risks risk_level 값 프론트엔드 스키마에 맞게 변환 (`safe→LOW`, `caution→MEDIUM`, `danger→HIGH`) |
| `bbd4787` | legal_node 고도화 4종 — FTC 지역비교, 종합리스크, 캐시키 안전처리, 관련성 필터 |
| `8fbbf60` | legal_node 고도화 후속 — 테스트 보강 및 응답 개선 |

**요약:**
- legal_node 전면 고도화: FTC 지역비교, 종합리스크 분석, 캐시키 안전처리
- 검색 결과 관련성 필터 추가 (`RELEVANCE_THRESHOLD = 0.3`)
- articles 추출 개선: `law_article` 없으면 `case_number`(판례번호)로 폴백
- risk_level 프론트엔드 스키마 매핑, Redis 연결 누수 수정
- import 경로 통일 (`src.agents.state` → `src.schemas.state`)

---

## B2 — 시뮬레이션 + 설명 (수지니 / soooojinn)

| 커밋 | 내용 |
|------|------|
| `80762f7` | SHAP 분석 구현 — `explain_prediction`, `plot_shap_summary` |
| `58a8b0b` | SHAP 코드 리뷰 반영 — em dash 제거, 예외처리 보강, direction 필드 추가 |
| `aeeb02e` | backtest_closure 구현 중 (WIP) |
| `d3debd8` | backtest_closure 구현 완료 — 폐업률 기준 백테스트 |

**요약:**
- SHAP 분석 전면 구현 (stub → 290줄+ 실제 코드)
  - DeepExplainer 우선, 실패 시 GradientExplainer 폴백
  - 한국어 피처명 매핑, direction 필드 추가
  - 가중치 없는 환경에서 mock SHAP 값 반환
- backtest_closure 구현: 생존률 → 폐업률 기준으로 전환
  - 비교 단위: survival_rate(0~1) → closure_rate(%)
  - 예측값 변환: `(1 - survival_rate) * 100`
  - 에러 반환 구조 보강, 이상치 방어 처리

---

## C1 — 프론트엔드 (강민 / Knockcha)

| 커밋 | 내용 |
|------|------|
| `a6b3a0b` | Dashboard API 명세서 작성 + tools.py vector cast 호환 fix |
| `5c5ac6c` | PR #34 머지 (feature/c1-spotter-frontend) |

**요약:**
- Dashboard API 명세서 작성
- tools.py의 pgvector 벡터 캐스팅 호환성 수정
- 프론트엔드 기능 브랜치 머지 완료

---

## 미진행 / 부재

| 역할 | 담당자 | 비고 |
|------|--------|------|
| B1 — LangGraph Agent | 예진 | 커밋 없음 |
| C2 — 인프라 + PM | 혁 | 커밋 없음 |
