"""
Agent 노드 모듈 — LangGraph에서 호출되는 개별 분석 Agent들

각 파일은 하나의 Agent 노드를 담당하며, Git 충돌을 방지하기 위해 파일을 분리함.

  - commercial.py   : 상권분석 (업종밀도, 폐업률, 평균매출)
  - population.py   : 유동인구 (생활인구 OA-14991, 지하철 승하차)
  - demographics.py : 인구통계 (주거인구, 연령분포, 가구구성)
  - cost.py         : 비용산정 (임대료, 인건비, 운영비)
  - competition.py  : 경쟁분석 (직접경쟁 + 카니발리제이션 + 간접경쟁)
  - trend.py        : 트렌드 (Naver DataLab 키워드 검색량, 소비패턴)
  - legal.py        : 법규검토 (RAG 기반 가맹사업법/상가임대차법)
  - report.py       : 리포트 생성 (종합 보고서, 비교표, 리스크 요약)
  - supervisor.py   : Supervisor (결과 충분성 판단, 재분석 루프 제어)
"""
