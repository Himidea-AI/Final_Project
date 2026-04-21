"""마포구 1000 에이전트 LLM 기반 ABM 시뮬레이션.

토큰 절감 9가지 전략 적용:
1. 계층화 (Tier S/A/B)
2. 모델 라우팅 (Haiku + Flash + Rule)
3. Prompt Caching (Anthropic ephemeral)
4. 이벤트 기반 호출
5. Batch API
6. 메모리 요약
7. 구조화된 출력 (JSON)
8. 임베딩 검색 (pgvector)
9. 로컬 SLM (옵션)
"""
