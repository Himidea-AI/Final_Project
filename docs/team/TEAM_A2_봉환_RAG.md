### A2 — RAG + 법률 (봉환)

**담당 영역**: 법률 문서 RAG, 벡터 검색, 하이브리드 retrieval, 청킹 전략

#### 법률 문서 청킹 및 전처리

**청킹 전략 설계**:
- **법률**: 조문 단위 분할 (제1조, 제2조, ...)
- **판례**: 판시사항 + 판결요지 기준 분할
- **Chunk size**: 평균 500 토큰 (최대 1000 토큰)
- **Overlap**: 50 토큰 (문맥 연속성 보장)

**전처리 파이프라인**:
1. PDF 파싱 (pdfplumber)
2. 조문 번호 정규화 (제1조 → Article_1)
3. 특수문자 제거 (법조문 기호 보존)
4. 메타데이터 추출 (법령명, 시행일, 개정일)

**데이터 규모**:
- 법률 문서: 10,255 chunks
- 판례: (대법원 판례 수 기록)
- 총 벡터: 10,255개 (BGE-m3 1024D)

#### 13 카테고리 법률 분석 구조 설계

**9 Deterministic Rules** (Python 로직):
1. food_hygiene: 식품위생법
2. safety_regulation: 안전관리
3. fire_safety: 소방안전
4. accessibility: 장애인 접근성
5. commercial_lease: 상가임대차보호법
6. labor: 근로기준법
7. vat: 부가가치세법
8. sewage: 하수도법
9. school_zone: 학교보건법 (주점 50m/200m 버퍼)

**4 RAG Specialists** (벡터 검색):
1. franchise_law: 가맹사업법 (영업구역, 계약 관련)
2. fair_trade_law: 공정거래법 (부당표시, 경쟁 제한)
3. building_law: 건축법 (용도지역, 건폐율)
4. privacy_law: 개인정보보호법 (CCTV, 고객 데이터)

#### BGE-m3 Embedding 구현

**BGE-m3 모델 통합**:
- Model: BAAI/bge-m3 (1024 dimension)
- sentence-transformers 라이브러리
- Batch encoding (batch_size=32)
- GPU 가속 (CUDA available 시)

**Embedding 최적화**:
- 쿼리와 문서 embedding 분리 (query: 짧음, document: 긴 context)
- 정규화 (L2 norm)로 cosine similarity 계산 간소화

#### Kiwi BM25 한글 키워드 검색

**Kiwi 형태소 분석기**:
- 한글 토큰화 (명사, 동사, 형용사 추출)
- 불용어 제거 (조사, 어미)
- 어간 추출 (먹다 → 먹)

**BM25 알고리즘**:
- TF-IDF 기반 랭킹
- k1=1.5, b=0.75 (표준 파라미터)
- Document frequency 계산으로 희귀 단어 가중치 상승

#### RRF (Reciprocal Rank Fusion) 하이브리드 검색

**가중 융합 전략**:
```python
RRF_score = 0.4 * vector_score + 0.6 * bm25_score
```

**성능 지표** (초기 구현):
- Recall: 0.408
- NDCG: 0.273
- Hit@10: 62.1%

**가중치 조정 근거**:
- Vector (0.4): 의미적 유사도 (동의어, 유사 개념 포착)
- BM25 (0.6): 키워드 정확도 (법조문 조 번호, 법령명 정합)

#### Primary-law Boost (찬영 최적화)

**우선 법령 가중치 상승**:
- Primary law (주요 법령): boost=2.0 (saturate)
- Supplementary law (보조 법령): penalty=0.4

**성능 개선**:
- Hit@10: 62.1% → **100%**
- MRR: 0.570 (Mean Reciprocal Rank)
- NDCG: 0.525

#### OpenAI Rerank (찬영 최적화)

**List-wise Reranking**:
- Model: gpt-4.1-mini
- RRF top 10 결과를 LLM이 재정렬
- Prompt: "다음 법률 조항 중 '{query}'와 가장 관련성 높은 순서대로 정렬"

**성능 개선**:
- MRR: 0.785 → **0.931** (+0.146)
- NDCG: 0.642 → **0.776** (+0.134)

#### 판례 RAG 통합

**대법원 판례 검색**:
- 판례 문서 별도 인덱스 (pgvector HNSW)
- 검색 쿼리 예시: "상가임대차 계약 해지 사유"
- Top-k=3 판례 반환

**Article LLM 풀어쓰기**:
- 법조문 원문 → 1~2문장 케이스 맞춤 설명
- Prompt: "'{law_article}'을 '{business_type}' 업종 관점에서 쉽게 설명"
- 예시: "제12조의4 → 한신포차 기준 250m 내 다른 가맹점이 있으면 위반"

#### pgvector + HNSW Index (찬영 마이그레이션)

**Vector DB 구성**:
- PostgreSQL + pgvector extension
- HNSW index (Hierarchical Navigable Small World)
- ef_construction=200, m=16 (HNSW 파라미터)

**검색 성능**:
- 10,255 벡터 대상 top-k=10 검색: ~50ms
- HNSW vs IVFFlat: 3배 속도 향상

#### Windows 호환성 개선 (찬영 fix, 2026-05-07)

**문제**: Windows ProactorEventLoop에서 psycopg async 오류
**해결**: 
```python
# pgvector retriever를 sync engine으로 전환
retriever = await asyncio.to_thread(sync_retriever.invoke, query)
```
- Async 코드 내에서 sync 함수 호출 (thread pool 활용)
- Windows 환경 InterfaceError 차단

#### 성과 요약

- **청킹**: 10,255 법률 chunks (평균 500 토큰)
- **Embedding**: BGE-m3 1024D
- **하이브리드 검색**: Vector(0.4) + BM25(0.6)
- **성능**: MRR 0.931, NDCG 0.776, Hit@10 100%
- **판례 RAG**: 대법원 판례 통합
- **인덱스**: pgvector HNSW (~50ms 검색)
- **13 카테고리**: 9 rules + 4 RAG specialists

---

