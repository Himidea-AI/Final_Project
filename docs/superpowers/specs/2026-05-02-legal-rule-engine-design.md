# Legal Agent — Rule + Specialist 하이브리드 설계

**날짜**: 2026-05-02
**작성자**: 찬영 (A1)
**관련 메모리**: `project_legal_redesign_roadmap.md` (SP6+ 완료 기준)

## 배경

현재 법률 에이전트(`backend/src/agents/nodes/legal.py`)는 12개 카테고리를 단일 LLM 배치 호출로 평가한다.

흐름: 13 RAG 쿼리 + 6 판례 쿼리 → 12 chunk compression (cheap LLM 병렬) → 1 main LLM (`with_structured_output(LegalBatchOutput)`) → 12개 `LegalRiskItem` 산출.

**이 방식의 본질적 문제:**

- "조문 검색해서 LLM이 알아서 판단" = naive RAG 패턴. 도메인 결정성을 LLM에 위임.
- 결정적 항목 (식품위생법 영업신고 = 음식점/카페에 무조건 필수)도 LLM이 매번 추론 → hallucination 여지.
- 12 항목 한 번에 평가 = 항목당 깊이 얕음. 압축 단계에서 조문번호/문구 손실.
- 적용되지 않는 법령도 매번 RAG 검색 (예: 편의점에 그리스트랩 검색).

**개선 방향**: 사용자 입력(`brand_name`, `business_type`, `target_district`, `store_area`)으로 결정 가능한 항목은 룰로 처리하고, 컨텍스트 의존 항목만 LLM specialist에 RAG + 평가를 위임.

## 사용자 입력 (룰 입력)

`SimulationInput` (Pydantic, 검증 완료 상태로 진입):

| 필드 | 타입 | 출처 |
|------|------|------|
| `brand_name` | str | 프론트엔드 브랜드 검색 → FTC DB 매칭 |
| `business_type` | str ∈ {cafe, restaurant, convenience} | 라디오 버튼 |
| `target_district` | str ∈ MAPO_DISTRICTS (16개) | 드롭다운 |
| `store_area` | float (default 15.0) | 평수 입력 |

룰 함수 진입 시점에 모든 값 검증/정규화 완료. 입력 검증 추가 불필요.

## 12 카테고리 분류

### 룰 처리 (8개) — 결정적

| 카테고리 | 룰 | 출력 |
|---------|-----|------|
| `food_hygiene` | `business_type ∈ {카페, 음식점}` → danger | 식품위생법 제37조 영업신고 |
| | `편의점` → caution | 즉석조리 시 |
| `safety_regulation` | 면적 ≥100㎡ + 카페/음식점 → danger | 다중이용업소법 제2조/제9조/제13조 |
| | <100㎡ → safe | |
| `fire_safety_law` | 면적 ≥100㎡ → danger | 소방시설법 제6조 |
| | <100㎡ → caution | |
| `accessibility_law` | 면적 ≥300㎡ + 카페/음식점 → danger | 장애인편의증진법 제7조 |
| | <300㎡ → safe | |
| `commercial_lease_law` | 항상 caution | 상가임대차보호법 제10조/제10조의4 |
| `labor_law` | 항상 caution | 근로기준법 제17조 + 최저임금법 제6조 |
| `vat_law` | 항상 caution | 부가가치세법 제8조 |
| `sewage_law` | `restaurant` → caution / 그 외 safe | 식품위생법 시행규칙 별표 14 |

**면적 기준치 출처:**

- 100㎡ (≈30평): 다중이용업소법 시행령 제2조 (휴게/일반음식점 다중이용업 정의)
- 300㎡ (≈90평): 장애인편의증진법 시행령 별표 1 (편의시설 의무 대상)

### LLM Specialist 처리 (4개) — 컨텍스트 의존

| 카테고리 | 이유 | 입력 |
|---------|------|------|
| `franchise_law` | 브랜드별 정보공개서 폐점률/가맹점수 디테일 | brand, business_type, district, ftc_data |
| `fair_trade_law` | 마포구 조례 + 가맹본부 불공정 패턴 | brand, business_type, district |
| `building_law` | 용도지역 × 업종 × 용도변경 조합 | business_type, district (DISTRICT_ZONE_MAP/ZONING_RULES 활용) |
| `privacy_law` | 멤버십/CRM 운영 여부 추정 | brand, business_type, ftc_data |

## 아키텍처

```
사용자 입력
    ↓
legal_node (entry, 기존 위치)
  ├ Redis 캐시 v5 lookup
  └ LEGAL_RULE_ENGINE_ENABLED 분기
    ├ true → orchestrator.run_legal_evaluation
    └ false → 기존 single LLM batch (legacy)
        ↓
orchestrator
  └ asyncio.gather(8 룰 + 4 specialist)
    ├ rules.py (sync, ~ms)
    └ specialists.py (RAG + LLM, 병렬)
        ↓
후처리: _enrich_penalty_info + _derive_checklist + _compute_overall
        ↓
캐시 write + AgentState 업데이트
```

### 디렉토리 구조

```
backend/src/agents/
├── legal/
│   ├── __init__.py
│   ├── rules.py            # 8 룰 함수 (sync)
│   ├── specialists.py      # 4 LLM specialist (async)
│   └── orchestrator.py     # 병렬 실행 + 결과 병합
└── nodes/
    └── legal.py            # 진입점 (기존 위치, orchestrator 호출 + 캐시 + 후처리)
```

### 공통 출력 인터페이스

룰/스페셜리스트 모두 `LegalRiskItem` 단일 schema 반환:

```python
class LegalRiskItem(BaseModel):
    type: str              # _BATCH_TYPES 중 하나 (12개)
    level: str             # "safe" | "caution" | "danger"
    summary: str           # 1~2문장 평가
    recommendation: str    # 체크리스트 형식 (• [근거: 제N조] ...)
    articles: list[dict]   # [{article_ref, content}]
```

### `articles` 필드 처리

룰 함수의 articles는 DB `law_legislations.body_text`에서 source + article 번호로 fetch. 결정적 + 출처 = 실제 법령 본문.

```python
# 예시
articles = await fetch_article_bodies(
    [("식품위생법", "제37조"), ("식품위생법", "제41조")]
)
```

DB에 누락된 조문은 정적 fallback (시행령/시행규칙 별표 등 일부).

## Specialist 패턴

각 specialist 공통:

1. 카테고리 전용 RAG 쿼리 (사용자 입력 컨텍스트 주입)
2. `top_k=5`, `source_filter=...` (해당 법령 카테고리)
3. 작은 LLM (gpt-4.1-mini) + `with_structured_output(LegalRiskItem)`
4. 평가 기준은 system prompt에 명시 (예: 폐점률 ≥20% → danger)

```python
async def specialist_franchise_law(
    brand: str, business_type: str, district: str, ftc_data: dict | None
) -> LegalRiskItem:
    retriever = LegalDocumentRetriever()
    query = f"{brand} {business_type} {district} 영업지역 가맹사업법 정보공개서 폐점률"
    docs = await retriever.search(
        query, top_k=5, source_filter=LegalDocumentRetriever.FRANCHISE_LAW_SOURCES
    )
    ftc_hint = _format_ftc(ftc_data)  # 가맹점수/폐점률 추출

    prompt = (
        f"브랜드: {brand} / 업종: {business_type} / 지역: {district}\n"
        f"FTC 정보공개서: {ftc_hint or '없음'}\n"
        f"[조문]\n{_format_docs(docs)}\n\n"
        f"평가 기준:\n"
        f"- 폐점률 ≥20% → danger 검토\n"
        f"- 폐점률 ≥10% → caution\n"
        f"- 영업지역 침해(제12조의4)/허위과장(제9조) → danger\n"
    )
    llm = get_cheap_llm().with_structured_output(LegalRiskItem)  # gpt-4.1-mini
    return await llm.ainvoke([SystemMessage(...), HumanMessage(content=prompt)])
```

**LLM 모델 선택**: gpt-4.1-mini (chunk_compressor와 통일). 4 specialist × cheap 모델 = 비용 부담 적음. 정확도 부족 시 specific 카테고리만 fast_llm으로 승격.

## 데이터 흐름

```
[1] frontend POST /simulate
[2] AgentState 초기화 (brand_name, business_type, target_district, store_area)
[3] legal_node(state):
    a. Redis cache lookup (v5:legal:{brand}:{district}:{biz_normalized}:{store_area})
       └ 히트 → 즉시 반환
    b. FTC DB 조회 (_search_ftc_from_db)
    c. flag = settings.legal_rule_engine_enabled?
       ├ true → orchestrator.run_legal_evaluation
       │        ├ 8 룰 (즉시, ~ms each)
       │        └ 4 specialist (RAG + LLM, 병렬, ~3~8s)
       └ false → _legacy_single_llm_batch (기존 코드)
    d. 후처리:
       ├ _enrich_penalty_info (벌칙 매핑)
       ├ _derive_checklist_from_articles
       └ _compute_overall (overall_legal_risk)
    e. Redis cache write (TTL 24h)
    f. AgentState 업데이트 → 다음 노드(synthesis)
```

## 캐시 전략

- 키 prefix `v4:legal:` → `v5:legal:`로 변경 (기존 캐시는 flag false 사용자에게 그대로 유효)
- store_area 추가 (룰엔진은 면적 의존)
- TTL 24h 유지

## 에러 처리

| 단계 | 실패 시 |
|------|--------|
| 룰 함수 (8) | `_make_fallback_risk(type)` → caution |
| Specialist RAG | 빈 docs로 LLM 호출 → "자료 없음" caution |
| Specialist LLM | structured_output 실패 → fallback caution |
| Orchestrator 전체 | `asyncio.gather(return_exceptions=True)` — 한 항목 실패가 나머지 영향 없음 |

## 롤백 전략

`LEGAL_RULE_ENGINE_ENABLED` env flag (default false):

- false → 기존 single LLM batch 그대로
- true → 신규 rule + specialist

PR 머지 후 신/구 동시 유지. 안정 확인 후 다음 PR에서 legacy 코드 삭제.

## 테스트 전략

### 1. Unit test (룰 8개) — `backend/tests/test_legal_rules.py`

각 룰 ~3~5 케이스, 총 ~30 unit test. DB/LLM mock — 빠름. 면적 경계 테스트 필수 (30평/31평, 90평/91평).

### 2. Integration test (specialist 4개) — `backend/tests/test_legal_specialists.py`

`@pytest.mark.integration` (Redis + DB + OpenAI 필요, CI에선 skip). LLM 비결정적이므로 schema/level 범위만 검증.

### 3. E2E (orchestrator) — `backend/tests/test_legal_orchestrator.py`

- 12 항목 모두 반환 검증
- 한 specialist 실패 시 나머지 11 정상 반환 검증

### 4. 회귀 측정

- **Ragas**: specialist 4 카테고리만 필터링한 골든셋. ContextPrecision/Recall 측정.
- **A/B 비교**: env flag로 신/구 모드 동일 입력 실행 → JSON diff.
- **Spot check**: 시나리오 5개 (카페 25평 공덕동, 음식점 50평 서교동, 편의점 10평 망원동, 카페 35평 연남동, 음식점 100평 합정동).

### 5. 성능 측정

| 지표 | 기존 | 신규 (예상) |
|------|------|----------|
| 총 시간 | ~37s | ~10~15s |
| LLM 호출 | 13 (12 cheap + 1 main) | 4 (specialist) |
| RAG 쿼리 | 19 (13 + 6 판례) | 10 (4 + 6 판례) |
| 비용 | baseline | ~70% 감소 |

## 비포함 (out of scope)

- legacy single LLM batch 코드 삭제 (별도 PR)
- 6 판례 쿼리 구조 변경 (현재 그대로 specialist에서 활용)
- chunk_compressor 삭제 (다른 노드에서도 쓰임)
- store_area 검증 강화 (기존 default 15.0 유지)
- multi-query/parent-child 변경 (SP6+에서 확정)

## 마이그레이션 단계

1. `backend/src/agents/legal/` 디렉토리 + 3 파일 신규
2. 8 룰 함수 작성 + unit test
3. 4 specialist 작성 + integration test
4. orchestrator 작성 + E2E test
5. `legal_node` flag 분기 추가
6. 캐시 키 v4 → v5
7. spot check 5 시나리오 + Ragas A/B
8. 검증 완료 후 PR 머지

## 검증 필요 사항 (구현 전)

- [ ] 소방시설법 100㎡ 외 다른 면적 단계(33㎡, 300㎡) 존재 여부 — DB RAG로 확인
- [ ] 그리스트랩 의무 정확한 트리거 (음식점 종류별 차이) — DB RAG로 확인
- [ ] 편의점 즉석조리 휴게음식점 신고 트리거 — DB RAG로 확인

위 3건은 룰 작성 직전 RAG sub-task로 검증.
