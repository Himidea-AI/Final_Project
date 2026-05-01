"""Legal Agent — 룰 + Specialist 하이브리드 평가 모듈.

- ``rules`` : 사용자 입력으로 결정 가능한 8개 법률 카테고리를 동기 함수로 평가.
- ``specialists`` : RAG + 작은 LLM 으로 컨텍스트 의존 4개 카테고리를 평가.
- ``orchestrator`` : ``asyncio.gather`` 로 12개 평가를 병렬 실행 후 결과 병합.

진입점은 ``backend/src/agents/nodes/legal.py`` 의 ``_run_legal_pipeline`` 이며
``settings.legal_rule_engine_enabled`` 플래그로 legacy single-LLM 모드와 분기된다.
"""
