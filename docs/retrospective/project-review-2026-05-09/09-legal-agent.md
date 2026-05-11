# Legal Agent -- 종합 리뷰 (2026-05-09)

> 작성일: 2026-05-09
> 담당 트랙: B1 (Agents), 연관: A1 (services/database), B2 (models)
> 리뷰 범위: `backend/src/agents/legal/`, `backend/src/agents/nodes/legal.py`, `backend/src/chains/retriever.py`

---

## 🚨 한 줄 진단

**DB 학교 시딩 전까지 mock 5 개로 안전 판정 → 학교 인근 주점 출점 "안전" 으로 오안내 가능 + summary 4중첩 prefix 노이즈.**

(쉽게: 학교 정보가 데이터베이스에 채워지기 전까지는, 코드에 미리 박아 둔 가짜 학교 5 곳 만으로 "이 자리 안전합니다" 라고 잘못 답할 수 있고, 사용자에게 보여 주는 한 줄 요약 앞에 시스템 메모용 꼬리표가 4 개나 붙어 본 내용이 가려진다.)

## 비전문가용 요약

- **무엇이 문제인가요?**
  - 마포구 학교 데이터가 DB(데이터베이스. 정보를 표 형태로 저장한 저장소) 에 없으면 — 즉 POSTGRES_URL(PostgreSQL 연결 문자열 환경변수. 어떤 DB 서버에 어떤 계정으로 접속할지 알려 주는 설정값) 이 비어 있거나 네트워크 오류가 나면 — 코드에 박힌 5 개(초3·중1·대1) 만으로 "학교 정화구역(학교 200m 이내 등 주류 판매가 제한되는 지역)" 을 판정합니다. 마포구 실제 학교는 수십 개라서, 학교 옆 주점 출점을 "안전" 으로 잘못 안내할 수 있습니다.
  - 사용자에게 보여주는 요약(summary) 앞에 brand·RAG empty·territory floor·fact prefix 가 동시에 4 개 붙어, 시스템 내부 메모가 실질 정보보다 많아지는 alert fatigue(경고 메시지가 너무 많아 사용자가 결국 무시하게 되는 현상) 가 발생합니다.
  - 산업 baseline 캐시(자주 쓰는 값을 미리 계산해 메모리에 보관해 두는 임시 저장소) 가 프로세스 단위라 멀티 워커 배포 시 워커별 캐시 불일치 가능.
- **얼마나 위험한가요?** H1 은 직접 사용자 손해 가능. mapo_schools 시딩(빈 테이블에 처음 데이터를 채워 넣는 작업) 전까지 안전판 필수.
- **얼마나 걸리나요?** mock caution 강제 0.5 일. prefix 통합 0.5 일.

## 가장 시급한 2 가지

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| H-1 | `agents/legal/rules.py:648-741` | mock 5 개로 false-safe (실제로는 위험한데 안전이라고 잘못 답하는 오류) | mock fallback(실패 시 대체 동작) 시 `level="caution"` + `is_mock=True` 강제 |
| H-2 | `agents/legal/specialists.py:479-527` | summary prefix 4 중첩 | 우선순위 정의 (territory > fact > rag_empty > brand), 1 개만 노출 |

---

## 1. 아키텍처 개요 — 무엇이 어떻게 돌아가는가

법률 에이전트는 SP1 (2026-04-30) 작업을 기점으로 단일 LLM(Large Language Model. ChatGPT 같은 대규모 언어 모델) batch 방식에서 벗어나 8 개 룰 + 4 개 specialist(특정 법 도메인 — 가맹사업법·공정거래법·건축법 — 만 다루도록 지정한 LLM 서브 에이전트) 의 하이브리드 구조로 재설계되었습니다. 이전에는 모든 항목을 한 번의 LLM 호출로 처리하다 보니 비용도 비싸고, 환각 / hallucination(LLM 이 사실이 아닌 내용을 그럴듯하게 지어내는 현상) 이 발생했을 때 어디서 잘못된 건지 추적하기도 어려웠습니다. 지금은 결정론적(같은 입력에 항상 같은 출력. LLM 처럼 매번 답이 달라지지 않음) 인 룰 / 룰 엔진(LLM 없이 if/else 와 거리·면적 계산 같은 결정론적 코드로 판정하는 부분) 과 LLM specialist 가 명확히 분리되어 있어 비용·속도·신뢰도 사이의 균형이 훨씬 좋아졌습니다.

운영 카테고리 중 `food_hygiene`, `labor`, `vat`, `sewage`, `privacy` 5 종은 현재 비활성 상태입니다. 프론트엔드(사용자가 보는 화면) 에 노출되지 않으며, LLM 호출도 일어나지 않아 비용 절감에 기여합니다. 실제로 사용자에게 보여지는 활성 카테고리는 8 개로, 이 중 5 개는 결정론적 룰, 나머지 3 개는 RAG(Retrieval-Augmented Generation. 관련 법조문을 먼저 검색해 LLM 에 같이 넣어 환각을 줄이는 기법) +LLM specialist 가 처리합니다.

처리 순서를 풀어 쓰면 다음과 같습니다. 1번부터 5번까지는 동기 룰(결과가 나올 때까지 기다렸다가 다음으로 넘어가는 방식의 룰) 로, 면적·업종·거리 같은 명시적 조건만 보면 즉시 판정할 수 있습니다. `safety_regulation`, `fire_safety_law`, `accessibility_law` 는 면적·업종 기준이고, `school_zone` 은 Haversine 거리(두 좌표 간 구면 위에서의 직선 거리를 구하는 공식) 50m/200m 거리, `commercial_lease_law` 는 고정 텍스트를 반환합니다. 6번부터 8번까지의 `franchise_law`, `fair_trade_law`, `building_law` 는 RAG 로 법조문을 검색한 뒤 LLM specialist 가 종합 해석을 만듭니다.

---

## 2. Specialist 멀티-라우팅 구조

진입점은 `orchestrator.run_legal_evaluation()` 입니다. 이 함수가 룰과 specialist 를 조율하며, 어디서 무엇이 실패해도 다른 항목이 영향을 받지 않도록 설계되어 있습니다.

### 동기 룰과 비동기 specialist 의 분업

5 개 동기 룰은 직접 함수 호출로 처리됩니다. Haversine 거리 계산이나 면적 분기 같은 가벼운 연산이라 수십 ms 안에 끝나고, 이벤트 루프(여러 비동기 작업을 순서대로 깨워 주는 파이썬의 작업 관리자) 를 블로킹할 만큼 무겁지 않습니다. 반면 3 개의 specialist (`franchise_law`, `fair_trade_law`, `building_law`) 는 `asyncio.gather(*tasks, return_exceptions=True)` (여러 비동기 작업을 동시에 실행하고, 일부가 실패하더라도 예외 객체로 결과 자리에 남겨 놓는 호출 방식) 로 병렬 실행됩니다. 한 specialist 가 LLM 타임아웃이나 RAG 오류로 죽어도 나머지 두 개는 정상 결과를 반환합니다. 실패한 항목은 `_to_risk_dict` 와 `_fallback_for_type` 을 거쳐 fallback(실패 시 caution 기본값으로 대체하는 비상용 결과) 으로 채워집니다.

마지막에 무결성 가드가 있습니다. `rule + specialist` 합계가 `_RULE_ENGINE_ORDER` 길이와 다르면 즉시 `ValueError` 를 발생시켜 누락된 카테고리를 잡아냅니다. 사용자에게 일부 결과만 보내는 사고를 막기 위한 마지막 안전장치입니다.

### Specialist 별 RAG 소스 필터

specialist 마다 검색 대상 코퍼스(검색 대상이 되는 문서 모음) 가 다릅니다. 모든 specialist 가 같은 문서 풀을 보면 가맹사업법 specialist 가 건축법을 인용하는 식의 혼선이 생기기 때문입니다.

`franchise_law` 는 `FRANCHISE_LAW_SOURCES` + 판례 (`legal_precedent_top_k=2`) 를 검색하고, 추가로 `_analyze_territory()` 가 500m 반경 동일 브랜드 매장 수를 결정론적으로 카운트합니다. `fair_trade_law` 는 `FAIR_TRADE_SOURCES` + `_MAPO_DISTRICTS` 조례 hint 를 함께 사용하고, `building_law` 는 `BUILDING_LAW_SOURCES` + `DISTRICT_ZONE_MAP`/`ZONING_RULES` 상수로 마포 16 동의 용도지역을 반영합니다.

---

## 3. 임베딩 현황 검증 — 4 배 중복은 해소되었다

`backend/src/chains/retriever.py` 의 `LegalDocumentRetriever` singleton(클래스 인스턴스를 하나만 두고 모든 곳에서 그 한 개를 재사용하는 패턴) 을 기준으로 임베딩(텍스트를 의미를 담은 숫자 벡터로 바꾼 결과) 상태를 점검했습니다.

### 모델과 청크 수

임베딩 모델은 BGE-m3(BAAI 가 만든 다국어 임베딩 모델. 1024 차원 벡터로 텍스트를 표현) (`BAAI/bge-m3`) 1024 차원입니다. 한국어 법률 문서에 잘 맞고, 다국어 토큰화가 KoBERT 보다 안정적이라는 점에서 채택되었습니다. 청크(문서를 일정 크기로 자른 조각. 여기서는 10,341 개 법조문 청크) 수는 정확히 10,341 / 10,341 로 일치합니다. 5 월 3 일 audit 에서 지적되었던 4 배 중복(같은 청크가 4 번 인덱싱되어 RAG 결과가 동일 문서로 도배되던 현상) 이 완전히 해소된 것이 확인되었습니다.

### BM25 와 RRF, 그리고 본법 우선순위

BM25(전통적 키워드 기반 검색 점수. 단어 빈도와 희소성으로 관련도를 계산) 인덱스는 Kiwi(한국어 형태소 분석기. 문장을 의미 단위 단어로 쪼갬) 형태소 분석기 기반으로 lazy 빌드(처음 호출될 때까지 미루어 두는 방식) 됩니다 (`_build_bm25_index`). 첫 검색 요청 시 한 번만 빌드되고 메모리에 캐시됩니다.

RRF(Reciprocal Rank Fusion. 서로 다른 검색 결과를 각자의 순위만 가지고 합치는 방법) fusion 가중치는 grid search 결과 vector 0.4 / bm25 0.6 으로 고정되었습니다. 이 조합이 NDCG 0.273, Hit 62.1% 로 가장 좋았습니다. 추가로 `primary_law_boost=2.0` (본법 청크 점수를 끌어올려 시행령·부칙을 밀어내는 가중치) 이 본법 청크 점수를 3 배로 끌어올려, 시행령이나 부칙이 본법보다 위로 올라오는 현상을 차단합니다. 이 부스트만 적용해도 29-case 벤치에서 Hit 100%, MRR(첫 정답이 등장한 순위의 역수 평균. 1 에 가까울수록 1 위로 잘 올린다는 뜻) 0.570, NDCG(순위 가중을 둔 검색 품질 지표. 위쪽에 정답이 있을수록 높음) 0.525 까지 향상되었습니다.

### Rerank 가 만든 차이

마지막에 OpenAI gpt-5.4-nano 가 listwise rerank(쿼리와 후보 전체를 한꺼번에 보고 LLM 이 순서를 다시 매기는 방식) 를 수행합니다. initial_k=30 으로 넓게 뽑은 뒤 최종 k=10 으로 재정렬하는 구조입니다. 이 단계 자체를 리랭커(1 차 검색 결과를 LLM 이 다시 정렬하는 단계) 라고 부릅니다. rerank 적용 전후로 MRR 은 0.785 → 0.931, NDCG 는 0.642 → 0.776 으로 각각 +19%, +21% 개선되었습니다. 최종 벤치 결과는 MRR 0.931, Hit@10(상위 10 개 안에 정답이 들어 있는 비율) 93.1% (27/29), NDCG@10 0.776, Recall@10 0.785 로 상용 수준에 도달했다고 평가할 수 있습니다.

---

## 4. commit c03273e5 분석 — z-score 폐점률 판정

이 커밋은 `backend/src/agents/nodes/legal.py` 의 `check_ftc_franchise()` 에서 hardcode 10% 임계를 업종별 baseline z-score(평균에서 표준편차 몇 배 떨어졌는지를 나타내는 수치) 판정으로 교체한 변경입니다.

### 왜 중요한가

이전 로직은 폐점률 10% 를 일률 기준으로 사용했습니다. 그런데 FTC 2024 데이터를 보면 외식업 평균 폐점률이 25-37% 수준입니다. 즉 10% 기준은 사실상 거의 모든 외식 브랜드를 danger 로 오판정하는 회귀(이전엔 잘 되던 게 나빠지는 변경) 였습니다. 이 상태로 사용자에게 결과를 보여주면 "어느 브랜드를 조회해도 위험" 이라고 나와 정보 가치가 0 에 가까워집니다.

새 로직은 업종별 평균(`mean`)과 표준편차(`std`) 를 계산해 z-score 가 1.0 을 넘으면 danger, 0.0 을 넘거나 평균 매출이 1 억 미만이면 caution, 그 외에는 safe 로 판정합니다. 업종 내 상대적 위치를 보기 때문에 외식업의 35% 폐점률은 평균 근처라 caution 또는 safe 로 분류되고, 같은 35% 라도 폐점률이 낮은 업종에서는 정확히 danger 로 잡힙니다.

### 어떻게 고치나 — 잔존 우려

`_INDUSTRY_BASELINE_CACHE` (legal.py:434) 는 프로세스 단위 dict 이며 TTL(Time To Live. 캐시가 자동으로 만료되기까지의 시간) 이나 캐시 무효화(오래된 캐시를 지우거나 다시 계산하도록 표시하는 동작) 로직이 없습니다. 서버를 재시작하지 않는 한 데이터가 stale 상태로 남습니다. FTC DB 가 연 1 회 업데이트되는 점을 감안하면 단일 워커 환경에서는 수용 가능하지만, `uvicorn --workers N` (FastAPI 를 여러 워커 프로세스로 띄우는 옵션. 워커별로 메모리가 분리되어 캐시도 각자 따로 가짐) 으로 멀티 워커 배포 시 워커별 캐시가 분리되어 같은 요청이 다른 답을 받을 수 있습니다.

n<5 가드(표본이 5 개 미만일 때 z-score 계산을 건너뛰는 안전장치) 와 std<=0 가드(표준편차가 0 이거나 음수일 때 0 으로 나누기를 피하기 위한 안전장치) 는 적절히 들어가 있습니다. 업종 브랜드 수가 5 개 미만이면 `None` 을 반환해 hardcode fallback 으로 떨어지고, `legal.py:470` 에서 표준편차가 0 인 경우도 처리합니다. 신뢰 구간이 부족할 때 무리해서 z-score 를 계산하지 않는다는 점에서 안전합니다.

---

## 5. 로드맵 현황 (SP1-SP5)

5 개 단계 중 4 단계가 완료되었습니다. SP1 은 8-rule + hybrid 재설계와 임베딩 중복 제거, SP2 는 specialist 4 종 분리와 RAG per-specialist 소스 필터, SP3 는 RRF grid search 와 primary_law_boost 벤치, SP4 는 reranker 와 chunk compression(청크 본문에서 핵심 문장만 추려 내 LLM 입력 토큰을 줄이는 단계, 현재 default OFF) 까지 완료된 상태입니다.

남은 SP5 는 `mapo_schools` DB 연동과 `privacy_law` 재활성화입니다. 이 단계의 핵심 블로커가 바로 H1 으로 지목한 `rules.py:648-741` 의 `_MOCK_MAPO_SCHOOLS` 입니다. mock 5 개(초3·중1·대1) 는 마포구 실제 학교 수십 개 대비 극소수라, DB 가 비어있을 때 학교 근처 위치를 오판정할 위험이 큽니다. SP5 완료 전까지는 안전 장치가 추가로 필요합니다.

---

## 6. Audit 발견사항 반영 여부

2026-05-03 audit (`project_legal_agent_audit.md`) 대비 진행 상황을 정리하면, 임베딩 4 배 중복 제거는 10,341/10,341 일치로 완료, z-score baseline 판정은 c03273e5 로 완료, prompt injection(사용자 입력으로 시스템 지시문을 덮어쓰려는 공격) defense 의 `<<<`/`>>>` 치환도 완료, 영업지역 환각 차단을 위한 deterministic fact prefix(LLM 이 아니라 코드가 계산한 사실을 요약 앞에 붙이는 고정 문구) 도 완료 상태입니다.

미완료로 남은 두 항목은 노드 강제 보정으로 인한 alert fatigue 와 mock school data 의 DB 연동입니다. 전자는 본 리뷰의 H2 로, 후자는 H1 으로 다시 다룹니다. 두 건 모두 사용자가 체감하는 품질 문제라 우선순위가 높습니다.

---

## 7. RAG 파이프라인 상세

`LegalDocumentRetriever.search()` 가 호출되면 9 단계를 거쳐 결과가 만들어집니다. 흐름을 풀어 쓰면 다음과 같습니다.

먼저 쿼리 확장 단계에서 HyDE (가상의 답변 문서를 먼저 LLM 에게 만들게 한 뒤 그 가짜 답변으로 검색하는 기법, `HYDE_ENABLED=false` default) 와 `_LEGAL_SYNONYM_MAP` 약 100 개 일상어→법률 용어 매핑이 적용됩니다. HyDE 는 비활성이지만 시노님(같은 의미를 갖는 다른 표현) 매핑은 늘 동작해서 "임대차" 같은 일상어를 "상가건물 임대차보호법" 같은 법률 표현으로 펼칩니다. 다음으로 multi-query (한 질문을 여러 변형 질문으로 나눠 각각 검색하는 기법, `MULTI_QUERY_ENABLED=false` default) 는 비활성 상태라 실제 운영 경로에는 영향이 없습니다.

1차 검색에서는 ChromaDB(임베딩 벡터를 저장하고 빠르게 비슷한 벡터를 찾아 주는 전용 데이터베이스) 코사인 vector 검색과 Kiwi 기반 BM25 검색이 병렬로 실행됩니다. 두 결과는 RRF fusion 으로 합쳐지는데, `rrf_k=60` 에 vector 0.4 / bm25 0.6 가중치가 적용됩니다. 그 다음 `primary_law_boost` 가 본법 청크 점수를 3 배로 키워 시행령·부칙을 밀어내고, `supplementary_penalty` 가 부칙 BM25 점수에 0.6 을 곱해 한 번 더 감점합니다. 이렇게 거른 30 개 후보를 gpt-5.4-nano 에 listwise 로 넘겨 재정렬하면 상위 10 개가 확정됩니다.

마지막으로 parent-child chunking(긴 문서를 부모-자식 두 단계 청크로 자르는 방식. 검색은 작은 자식으로, 답변은 큰 부모를 함께 줘서 문맥 보존) 이 적용됩니다. 자식 청크가 hit 했을 때 부모 전문을 함께 반환해 LLM 이 문맥을 잃지 않도록 합니다. 디버깅을 위해 `RAG_TRACE_ENABLED=false` 옵션이 있어 활성화하면 단계별 후보와 점수가 JSONL(한 줄에 JSON 한 개씩 적은 로그 파일 형식) 로 기록됩니다.

### 미사용 상수

`retriever.py:488-495` 의 `FIRE_PREVENTION_SOURCES` 는 정의되어 있지만 specialist 와 노드 어디서도 참조되지 않습니다. `fire_safety_law` specialist 가 비활성화되었거나 `FIRE_LAW_SOURCES` 로 통합된 흔적으로 추정되며, 사용하지 않는다면 제거하거나 의도를 주석으로 남겨야 합니다.

---

## 8. 도메인 지식과 코퍼스 구성

법률 specialist 의 답변 품질은 결국 어떤 법조문 위에서 RAG 가 동작하느냐에 달려 있습니다. 현재 코퍼스에 들어간 핵심 조문을 정리해두면 다음과 같습니다.

가맹사업법은 제6조의2(정보공개서), 제9조(허위 기재), 제12조의4(영업지역 보장) 가 중심 조문입니다. 가맹점 분쟁의 대부분이 이 세 조문 주변에서 발생하기 때문에 specialist 가 이 조문들을 안정적으로 검색해내는 것이 중요합니다. 건축법과 용도지역(주거지역·상업지역 등 그 땅에서 무엇을 지을 수 있는지를 정한 도시계획상 분류) 은 `DISTRICT_ZONE_MAP` + `ZONING_RULES` 상수로 마포 16 동의 용도지역을 하드코딩(코드 안에 값을 직접 박아 넣어 둠) 했고, 학교보건법 제 6 조는 Haversine 50m/200m 정화구역을 주점만 트리거하도록 조건을 제한했습니다(카페·일반음식점은 safe). 공정거래법 영역에서는 `_MAPO_DISTRICTS` 조례 hint 가 서울시 공정거래 조례와 연결되고, 판례는 `legal_precedent_top_k=2` 로 ChromaDB 의 category=판례 청크가 동시에 검색됩니다.

### _PENALTY_ARTICLE_MAP 의 역할

`legal.py:47-84` 의 `_PENALTY_ARTICLE_MAP` 은 의무 조문과 벌칙 조문을 17 건 매핑한 딕셔너리(키-값 쌍을 모아 둔 자료구조) 입니다. `_enrich_penalty_info()` 가 RAG 결과에 벌칙 정보를 후속 주입해 recommendation 의 구체성을 끌어올립니다. "이 조문 위반 시 어떤 처벌을 받는가" 가 자동으로 붙기 때문에 사용자가 판단을 내리기 쉬워집니다.

---

## 9. 테스트와 벤치 현황

### 단위 테스트가 커버하는 영역

`backend/tests/test_legal_rules.py` 는 8 개 룰 함수를 전수 커버합니다. 면적 경계값, 학교 거리 계산, 스키마(데이터의 구조와 타입을 정의한 명세) 검증 등 약 50 개 케이스가 포함됩니다. `backend/tests/test_legal_orchestrator.py` 는 E2E(End-to-End. 시작부터 끝까지 전체 흐름을 한 번에 검사) 흐름을 monkeypatch stub(테스트 중 실제 함수를 가짜 함수로 임시 바꿔치기) 으로 검증해 8-item 반환과 실패 격리 동작을 보장합니다.

### 미커버 경로

반대로 다음 영역은 단위 테스트가 비어 있습니다. `_get_industry_baseline()` 의 z-score 분기, `_analyze_territory()` 와 `_territory_to_level()` 의 영업지역 분석 로직, `_explain_articles_batch()` 의 LLM mock 테스트, 그리고 가장 중요하게 `_MOCK_MAPO_SCHOOLS` fallback 시 false safe 가 발생하는지 확인하는 테스트가 없습니다. H1 안전장치를 만든 뒤에는 반드시 이 케이스를 추가해야 다음 회귀를 잡을 수 있습니다.

### RAG 벤치

29-case golden set(정답이 미리 정해져 있어 평가 기준으로 쓰는 표준 테스트 모음, 2026-05-04) 기준으로 MRR 0.931, Hit@10 93.1% 까지 도달했습니다. 케이스 수가 절대적으로 많은 편은 아니지만 가맹·공정거래·건축·학교·임대차 영역을 골고루 다루고 있어 회귀 감지에는 충분합니다.

---

## 10. 출력 형식과 스키마

응답은 `LegalRiskItem` Pydantic(파이썬에서 데이터 형태가 맞는지 자동으로 검사해 주는 라이브러리) 모델로 직렬화됩니다. `type` 은 `_RULE_ENGINE_ORDER` 값과 1:1 매핑되고, `level` 은 `safe`/`caution`/`danger` 셋 중 하나, `summary` 는 최대 200 자 분량의 브랜드·업종·지역 맞춤 설명, `recommendation` 은 최대 5 줄 체크리스트, `articles` 는 `article_ref` + `content` + `explanation` (1-2 문장) 으로 구성된 리스트입니다.

타입 보정은 5 단계로 방어됩니다. 마지막 방어선이 `_to_risk_dict()` (orchestrator.py:60-73) 인데, LLM 출력이 잘못된 타입 이름을 뱉어도 여기서 강제로 정규화합니다. 다만 이런 다층 방어는 alert fatigue 의 원인이기도 하므로 H2 에서 다시 다룹니다.

---

## 11. 코드 품질 — 보안·환각·폴백

### 보안 측면

prompt injection 은 `_format_docs()` (specialists.py:82-96) 에서 `<<<`/`>>>` 를 `«`/`»` 로 치환해 시스템 prompt 의 RAG_CONTEXT delimiter(여기서부터 여기까지가 검색 결과라는 경계 표시 문자) 를 사용자 입력이 위장하지 못하도록 차단합니다. `_SYSTEM_PROMPT_BASE` 안에도 delimiter 사용 규칙이 명시되어 있습니다. 사용자 입력 길이는 FastAPI Pydantic schema 단에서 검증됩니다.

다만 `settings.py:139` 의 JWT(로그인 사실을 증명하는 서명된 토큰) fallback 값이 `dev-only-not-secret-replace-in-prod` 로 되어 있어, 운영에서는 반드시 `.env` 로 덮어써야 하고 CI(코드를 푸시할 때마다 자동으로 검사·테스트를 돌리는 파이프라인) 단계에서 secret leak 검사가 부재한 점은 별도 개선 항목입니다.

### 환각 방지 장치

영업지역 같은 정량 정보는 LLM 이 환각하기 쉬운 영역이라 deterministic 처리가 들어가 있습니다. `specialists.py:521-527` 의 fact prefix 는 영업구역 내 동일 브랜드 매장 수를 `[사실확인: ...]` 형식으로 summary 앞에 결정론적으로 삽입합니다. `_territory_to_level()` 은 정량 룰 floor(코드가 계산한 최소 위험 수준. LLM 이 이보다 낮춰서 출력해도 강제로 끌어올림) 를 두어 LLM 이 부당하게 낮은 level 을 산출했을 때 강제로 상향하면서 근거를 명시합니다. `_build_llm(max_tokens=4000)` 는 무한 reasoning(LLM 이 답을 내지 않고 끝없이 사고만 이어 가는 상태) 을 차단합니다 (이전에 32768 토큰까지 도달한 사례가 있었습니다).

### 폴백 체계

LLM 호출이 실패하면 `_make_specialist_fallback()` 이 caution 기본값과 hardcode recommendation 을 반환합니다. DB 조회가 실패하면 `_MOCK_MAPO_SCHOOLS` 5 개를 반환하는데, 이것이 H1 의 핵심 위험입니다. `_INDUSTRY_BASELINE_CACHE` 미스 시에는 hardcode 10%/5% 임계값으로 떨어집니다.

---

## 12. 강점 — 잘 만들어진 부분

법률 에이전트는 다른 도메인 에이전트에 비해 구조적 완성도가 높은 편입니다. 정리하면 6 가지가 두드러집니다.

첫째, 결정론적 룰 5 개 + LLM specialist 3 개 라는 하이브리드 아키텍처가 비용·속도·신뢰도의 균형을 잘 잡았습니다. 둘째, RAG 품질이 MRR 0.931, Hit@10 93.1% 로 한국어 법률 도메인에서 상용 수준에 도달했습니다. BM25 + vector + rerank 조합이 기여했습니다. 셋째, `asyncio.gather(return_exceptions=True)` 로 영역을 격리해 한 specialist 실패가 전체 응답을 막지 못합니다. 넷째, z-score 판정 도입으로 외식업 평균 25-37% 라는 현실을 반영해 이전 10% hardcode 회귀를 해소했습니다. 다섯째, specialists → orchestrator → graph node 3 단 보정으로 LLM 타입 오염 방어가 이중·삼중으로 걸려 있습니다. 여섯째, 29-case golden set 으로 RRF 가중치와 primary_law_boost 가 정량 검증된 상태라 가벼운 튜닝에도 회귀를 즉시 감지할 수 있습니다.

---

## 13. 리스크와 기술 부채

### HIGH 위험 — 사용자 손해 가능성

**H1. Mock school data 로 인한 false-safe 위험** (`backend/src/agents/legal/rules.py:648-741`)

`_MOCK_MAPO_SCHOOLS` 는 초등 3, 중 1, 대학 1 의 5 개 학교만 담고 있습니다. 마포구 실제 초·중·고는 수십 개 단위입니다. DB 조회가 실패하거나 (`POSTGRES_URL` 미설정, 네트워크 오류) `mapo_schools` 테이블이 비어 있을 때 이 5 개만으로 school_zone 룰이 동작하면, 실제로는 학교 50m 안에 있는 위치가 safe 로 판정될 수 있습니다. 학교보건법 제 6 조 정화구역에 해당하는 주점 출점이 "허가 가능" 으로 잘못 안내되면 사용자에게 직접적 손해가 발생합니다. 코드상 fallback 분기는 다음과 같습니다.

```python
# rules.py:736-741
if not out:
    logger.warning("[rule_school_zone] mapo_schools 비어 있음 -- mock fallback")
    return list(_MOCK_MAPO_SCHOOLS)   # 5개만 반환 -- false safe 위험
```

권고는 두 가지입니다. 단기 안전장치로 mock fallback 결과는 무조건 `level="caution"` 강제 + `is_mock=True` 플래그를 반환하도록 분기를 추가합니다. 근본 해결은 SP5 의 `mapo_schools` DB 시딩 완료입니다.

**H2. Summary prefix 중첩 alert fatigue** (`backend/src/agents/legal/specialists.py:479-527`)

최악 시나리오는 사용자가 브랜드를 입력했고 + RAG 가 빈 결과를 반환했고 + territory floor 가 발동했고 + fact prefix 도 붙는 경우입니다. summary 앞에 bracket prefix 가 최대 4 개까지 중첩됩니다.

```
[사실확인: 영업구역(500m) 안 동일 브랜드 매장 0개] [정량 분석 자동 상향: ...] [RAG 법조문 자료 부재 -- 수동 검토 필요] [브랜드 입력됨] LLM summary
```

사용자 화면에 노출되는 텍스트의 절반 이상이 시스템 메타 노이즈로 채워져, 정작 읽어야 할 LLM 결론이 뒤로 밀립니다. 이는 사용자가 "또 시스템 메시지구나" 하고 무시하게 만드는 alert fatigue 패턴입니다. 권고는 prefix 우선순위를 명시적으로 정의하고 (`territory_floor` > `fact` > `rag_empty` > `brand`) 최대 1 개만 노출하는 것입니다. 나머지는 `recommendation` 본문이나 `debug_flags` (개발자 디버깅용으로만 보이는 내부 플래그 필드) 필드로 옮겨야 합니다.

### MEDIUM 위험

**M1. `_INDUSTRY_BASELINE_CACHE` TTL 부재** (`backend/src/agents/nodes/legal.py:434`)

프로세스 단위 dict 이고 무효화 로직이 없습니다. 단일 워커 + FTC 연 1 회 업데이트 주기에서는 수용 가능하지만, `uvicorn --workers N` 멀티 워커 배포 시 워커별 캐시가 분리되어 동일 입력에 다른 답을 줄 수 있습니다. 권고는 `ttl=86400` (24h) expiry 추가, 장기적으로는 Redis(여러 프로세스가 공유할 수 있는 메모리 캐시 서버) 이전입니다. 단기 대안으로 `asyncio.Lock` (한 번에 한 코루틴만 들어갈 수 있게 잠그는 비동기 락) + timestamp 체크도 가능합니다.

**M2. `_get_specialist_llm()` thread safety gap** (`backend/src/agents/legal/specialists.py:39-53`)

`hasattr(_get_specialist_llm, "_instance")` 패턴은 asyncio 단일 이벤트 루프에서는 안전하지만, `concurrent.futures.ThreadPoolExecutor` (여러 작업을 별도 스레드에서 동시에 돌리는 실행기) 또는 multiprocessing 과 결합되면 race condition(여러 작업이 같은 자원을 동시에 건드려 결과가 꼬이는 상황) 이 가능합니다. 현재 FastAPI + asyncio 단일 루프 구조에서는 실질 위험이 낮으나, 향후 CPU-bound 작업을 별도 스레드 풀로 분리할 계획이라면 미리 모듈 레벨 `_SPECIALIST_LLM: LLM | None = None` + `asyncio.Lock()` 초기화로 교체하는 것이 안전합니다.

**M3. RAG empty 와 retriever error 구분 불가** (`backend/src/agents/legal/specialists.py:487-489`)

`rag_empty` 플래그는 `docs` 길이가 0 일 때 set 됩니다. 그런데 retriever 가 내부에서 exception(예외. 코드 실행 중 발생하는 비정상 상황) 을 삼키고 빈 리스트를 반환할 때도 동일하게 처리되어, "검색 결과가 없는 것" 과 "검색이 실패한 것" 을 구분할 수 없습니다. 권고는 `retriever.search()` 반환에 `source: "empty" | "error" | "results"` 필드를 추가하거나 exception 을 위로 올려보내는 것입니다.

**M4. `nearby_stores[:10]` 하드캡** (`backend/src/agents/legal/specialists.py` `_analyze_territory` 내부)

영업지역 분석 시 인근 매장 상위 10 개만 사용합니다. 홍대·합정처럼 고밀도 상권에서는 영업지역 500m 안에 동일 브랜드 매장이 10 개를 초과할 수 있어, territory 가 과소 계산될 수 있습니다. 권고는 카운트는 영업지역 반경 내 전수로 계산하고, `[:10]` 은 summary 출력용으로만 제한하는 것입니다.

### LOW 위험

**L1. `FIRE_PREVENTION_SOURCES` 미사용** (`backend/src/chains/retriever.py:488-495`)

상수만 정의되어 있고 specialist 와 노드 어디서도 참조되지 않습니다. 사용 의도가 없다면 제거하고, 향후 `fire_safety_law` specialist 재활성화를 염두에 두고 있다면 `# TODO: fire_safety_law specialist 재활성 시 연결` 주석을 명시하는 것이 안전합니다.

**L2. `commercial_lease_law` 고정 반환** (`backend/src/agents/legal/rules.py` `rule_commercial_lease()`)

항상 `level="caution"` 과 동일한 텍스트를 반환합니다. 브랜드·지역·임대료와 무관하게 같은 결과가 나오므로 매 시뮬레이션마다 동일 텍스트가 반복 노출되어 정보 가치가 거의 없습니다. 권고는 `mapo_commercial_rent` 테이블 연동 또는 업종별 텍스트 분기입니다.

---

## 14. 개선 우선순위

가장 먼저 손대야 할 것은 H1 mock school 안전장치입니다. 약 30 분 분량의 작업이고 false-safe 라는 직접적인 사용자 손해 가능성을 즉시 차단합니다. 그 다음으로 SP5 의 `mapo_schools` DB 시딩을 약 2 시간 안에 완료하면 mock fallback 자체를 제거할 수 있습니다.

세 번째 우선순위는 H2 prefix 우선순위 정리로, 약 1 시간 작업입니다. 사용자 체감 품질에 직결되는 alert fatigue 를 줄입니다. 네 번째는 M1 baseline cache TTL 추가로 30 분, 다섯 번째는 z-score 분기·territory·mock fallback 에 대한 단위 테스트 추가로 약 2 시간입니다. 마지막으로 L1 `FIRE_PREVENTION_SOURCES` 정리는 10 분 안에 끝낼 수 있는 청소 작업입니다.

---

## 리뷰 결과 요약

[심각도: HIGH -- H1, H2 해결 후 승인]

### HIGH (머지 전 수정 권장)

- `backend/src/agents/legal/rules.py:648-741` -- `_MOCK_MAPO_SCHOOLS` 5 개 false-safe. mock fallback 시 caution 강제 또는 SP5 DB 시딩 완료 선행 필요.
- `backend/src/agents/legal/specialists.py:479-527` -- summary prefix 최대 4 중첩 alert fatigue. prefix 우선순위 정리 + 최대 1 개 노출 권고.

### MEDIUM

- `backend/src/agents/nodes/legal.py:434` -- `_INDUSTRY_BASELINE_CACHE` TTL 없음. 멀티 워커 배포 시 캐시 불일치.
- `backend/src/agents/legal/specialists.py:39-53` -- `_get_specialist_llm` singleton thread safety gap (asyncio 단일 루프에서는 위험 낮음).
- `backend/src/agents/legal/specialists.py:487-489` -- RAG empty 와 retriever error 구분 불가.
- `backend/src/agents/legal/specialists.py` (`_analyze_territory`) -- `nearby_stores[:10]` 하드캡으로 territory 과소 계산.

### LOW

- `backend/src/chains/retriever.py:488-495` -- `FIRE_PREVENTION_SOURCES` 미사용 상수.
- `backend/src/agents/legal/rules.py` `rule_commercial_lease()` -- 항상 동일 텍스트, 정보 가치 낮음.

### 승인 조건

H1 (mock school caution 강제) 과 H2 (prefix 중첩 완화) 가 해결되면 승인 가능합니다. M1-M4 는 SP5 일정 안에서 함께 처리하는 것을 권고합니다.
