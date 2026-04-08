# A2 (봉환) — WBS (Work Breakdown Structure)

> **Jira 프로젝트 키**: `IM3`
> **담당 영역**: `backend/src/chains/`, `backend/src/database/vector_db.py`, `backend/src/services/ftc_franchise.py`, `backend/src/agents/nodes/legal.py`
> **최종 업데이트**: 2026-04-08
> **프로젝트 기간**: 04/02 ~ 05/07 (5주)

---

## 티켓 총괄표

> 난이도: 🟢 쉬움 / 🟡 보통 / 🔴 어려움
> 우선순위: P0 (즉시) / P1 (이번 주) / P2 (다음 주) / P3 (여유 시)

| # | Jira 티켓 | 제목 | 주차 | 우선순위 | 난이도 | 상태 |
|---|----------|------|------|---------|--------|------|
| 1 | IM3-40 | RAG + 법률 데이터 파이프라인 구현 | 1주차 | P0 | 🟡 | ✅ 완료 |
| 2 | IM3-41 | ChromaDB 벡터화 + 검색 파이프라인 구축 | 1주차 | P0 | 🟡 | ✅ 완료 |
| 3 | IM3-43 | RAG 반환 형식 통일 및 pgvector 안정화 | 1주차 | P0 | 🟡 | ✅ 완료 |
| 4 | IM3-44 | 식품위생법·다중이용업소 안전관리법 검토 노드 구현 | 1주차 | P0 | 🟡 | ✅ 완료 |
| 5 | IM3-45 | RAG pgvector 전환 + 법률 문서 전체 인제스트 | 1주차 | P0 | 🔴 | ✅ 완료 |
| 6 | IM3-46 | legal_node 무한루프 방지 - legal_info fallback 추가 | 2주차 | P0 | 🟢 | ✅ 완료 |
| 7 | IM3-62 | RAG 통합 테스트 작성 - LangGraph 연동 검증 | 2주차 | P1 | 🟡 | ✅ 완료 |
| 8 | IM3-63 | 비동기 RAG 검색 최적화 | 3주차 | P1 | 🔴 | ✅ 완료 |
| 9 | IM3-64 | pgvector 커넥션 풀 최적화 | 3주차 | P1 | 🟢 | ✅ 완료 |
| 10 | IM3-65 | 판례 API 연동 (식품위생·다중이용업소 포함) | 3주차 | P1 | 🟡 | ✅ 완료 |
| 11 | IM3-66 | 엣지케이스 대응 (빈 검색결과·타임아웃·fallback) | 3주차 | P2 | 🟡 | ✅ 완료 |
| 12 | IM3-67 | 법령 RAG 확장 — 창업 필수 법령 14개 영역 완비 | 4주차 | P1 | 🔴 | ✅ 완료 |

---

## 티켓별 상세 설명

### ✅ 1주차 완료 (04/02 ~ 04/06)

#### IM3-40: RAG + 법률 데이터 파이프라인 구현
- PDF 법률 문서 파싱 + 청크 분할 + 임베딩 파이프라인 구축
- 커밋: `589996b`
- 산출물: `backend/data/legal/` 디렉토리 구조, `parse_pdfs.py`

#### IM3-41: ChromaDB 벡터화 + 검색 파이프라인 구축
- ChromaDB 기반 벡터 저장 + 유사도 검색 파이프라인
- 커밋: `206ae6a`
- 산출물: `vector_db.py` 초안

#### IM3-43: RAG 반환 형식 통일 및 pgvector 안정화
- 반환 형식 통일 (dict → TypedDict), pgvector 연동 안정화
- 커밋: `2292c9b`
- 산출물: `retriever.py` 반환 형식 통일

#### IM3-44: 식품위생법·다중이용업소 안전관리법 검토 노드 구현
- `legal_node`, `check_food_hygiene`, `check_safety_regulation` 구현
- 커밋: `98d91f7`, `86e28c0`

#### IM3-45: RAG pgvector 전환 + 법률 문서 전체 인제스트
- ChromaDB → pgvector 완전 전환, JSONB 메타데이터 마이그레이션
- 커밋: `98d91f7`, `38314c3`
- 산출물: `PGVectorDBClient`, `ingest.py`, langchain_postgres JSONB

---

### ✅ 2주차 완료 (04/07 ~ 04/11)

#### IM3-46: legal_node 무한루프 방지 - legal_info fallback 추가
- `legal_info` 키 없을 때 fallback 처리, TypedDict 호환 수정
- 커밋: `0724446`, `a5817ac`

#### IM3-62: RAG 통합 테스트 작성 - LangGraph 연동 검증
- `test_a2_rag_integration.py` 20개 통합 테스트 작성, 20/20 통과
- 커밋: `e521e7c`
- 검증 항목: retriever→legal_node→LangGraph 흐름, pgvector 반환 형식, fallback 동작, 소스 필터링 정확도

#### 추가 완료 (IM3-62 병행)
- **LLM 프로바이더 전환**: Ollama(느림) → Gemini 2.5 Flash 전환 (`97a7b1d`, `d8a81d1`, `6331e5c`)
  - 429 RESOURCE_EXHAUSTED 자동 재시도 (지수 백오프 30s→60s, 최대 2회)
  - gemini-2.5-flash 확정 (별도 쿼터 풀, 무료 티어 정상 동작)
- **FTC 퍼지 매칭**: `_fuzzy_match()` 추가 — 3단계 매칭 (직접 포함·2글자 토큰·difflib 0.65) (`d8a81d1`)
  - "메가커피" → "메가MGC커피" 자동 매칭 등 6케이스 검증

---

### ✅ 3주차 완료 (04/14 ~ 04/18)

#### IM3-63: 비동기 RAG 검색 최적화
- `asyncio.gather()`로 RAG 5개 + 판례 API 4개 병렬 실행
- 커밋: `8efae4a`
- 효과: 순차 실행 대비 응답 시간 대폭 단축

#### IM3-64: pgvector 커넥션 풀 최적화
- `pool_size=10, max_overflow=20, pool_timeout=30, pool_pre_ping=True`
- 커밋: `8efae4a`
- 산출물: `vector_db.py` create_async_engine 풀 설정

#### IM3-65: 판례 API 연동
- `law_api.py` LawApiClient 구현 (국가법령정보 공동활용 API, OC=bongbong90)
- 판례 검색 4개 쿼리: 가맹사업·권리금·식품위생·다중이용업소
- 판시사항·판결요지·참조조문 추출, RAG docs와 병합하여 LLM 투입
- 커밋: `8efae4a`

#### IM3-66: 엣지케이스 대응
- **빈 검색 결과 fallback**: source_filter 제거 후 전체 재검색 (`retriever.py`)
- **판례 API retry**: TimeoutException·NetworkError 시 1회 재시도 (`law_api.py`)
- 커밋: `3ba6d04`

---

### ✅ 4주차 완료 (04/08 기준 조기 완료)

#### IM3-67: 법령 RAG 확장 — 창업 필수 법령 14개 영역 완비

**추가된 법령 (12개):**

| 법령 | 카테고리 | 청크 수 | 검토 함수 |
|------|---------|---------|---------|
| 건축법 | 건축물 용도·용도변경 | 317개 | `check_building_law` |
| 소방시설 설치 및 관리에 관한 법률 | 소방시설 설치·유지 | 103개 | `check_fire_safety_law` |
| 근로기준법 | 고용·임금·근로계약 | 209개 | `check_labor_law` |
| 최저임금법 | 최저임금 준수 | 49개 | `check_labor_law` (병합) |
| 부가가치세법 | 사업자등록·과세유형 | 194개 | `check_vat_law` |
| 개인정보 보호법 | 고객데이터·CCTV | 305개 | `check_privacy_law` |
| 장애인·노인·임산부 등의 편의증진 보장에 관한 법률 | 편의시설 설치 | 58개 | `check_accessibility_law` |
| 독점규제 및 공정거래에 관한 법률 | 불공정 가맹계약 | 257개 | `check_fair_trade_law` |
| 하수도법 | 오수처리·유류분리기 | 187개 | `check_sewage_law` |
| 물환경보전법 | 폐수 배출 기준 | 293개 | `check_sewage_law` (병합) |
| 주세법 | 주류판매 업종 | 43개 | - (RAG 검색 제공) |
| 식품위생법 본법 | 영업허가·위생기준 | 314개 | `check_food_hygiene` (병합) |

**코드 변경:**
- `parse_pdfs.py`: 파싱 대상 10개 → 22개
- `retriever.py`: SOURCE 상수 5개 → 11개
- `legal.py`: check 함수 6개 → 14개, 병렬 RAG 5개 → 13개, 리스크 검토 6개 → 14개
- 커밋: `1c255f8`

**DB 적재 결과:**
- 총 **3,775개 청크** pgvector 적재 완료 (Docker PostgreSQL `final_project-db-1` 확인)

---

## 현재 RAG 커버리지

| 영역 | 법령 | 상태 |
|------|------|------|
| 프랜차이즈 계약 | 가맹사업법 + 시행령 | ✅ |
| 임대차 | 상가임대차보호법 + 시행령 + 사례집 | ✅ |
| 위생·영업허가 | 식품위생법 본법 + 시행규칙 + 위생교육교재 | ✅ |
| 안전·소방 | 다중이용업소법 + 안전관리기본계획 + 소방시설법 | ✅ |
| 건축·공간 | 건축법 + 장애인편의증진법 | ✅ |
| 환경·시설 | 하수도법 + 물환경보전법 | ✅ |
| 세무 | 부가가치세법 | ✅ |
| 고용 | 근로기준법 + 최저임금법 | ✅ |
| 데이터 | 개인정보 보호법 | ✅ |
| 공정거래 | 공정거래법 | ✅ |
| 주류 | 주세법 | ✅ |
| 지역 조례 | 마포구 지역상권 조례 | ✅ |

---

## 5주차 예정 (04/28 ~ 05/07)

| 작업 | 비고 |
|------|------|
| 실제 마포구 케이스로 RAG 결과 최종 검증 | 연남동·서교동 시나리오 |
| 통합 테스트 신규 법령 영역 케이스 추가 | 14개 영역 커버 |
| 발표 데모용 RAG 예시 시나리오 준비 | |

---

## 의존성 다이어그램

```
1주차 (완료)
  IM3-40 (파이프라인) ━━━┓
  IM3-41 (ChromaDB)  ━━━┫
  IM3-43 (pgvector)  ━━━┫
  IM3-44 (법률노드)  ━━━┫
  IM3-45 (인제스트)  ━━━┛

2주차 (완료)
  IM3-46 (fallback) ━━━━━ IM3-62 (통합 테스트)

3주차 (완료)
  IM3-62 ━━━━━━━━━━━━━━━━ IM3-63 (비동기 최적화)
                          IM3-64 (커넥션 풀)
                          IM3-65 (판례 API)
                          IM3-66 (엣지케이스)

4주차 (완료)
  IM3-65 ━━━━━━━━━━━━━━━━ IM3-67 (법령 14개 확장)

5주차
  IM3-67 ━━━━━━━━━━━━━━━━ 발표 준비 + 최종 검증
```
