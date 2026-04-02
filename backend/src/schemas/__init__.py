"""
Pydantic 데이터 스키마 패키지 — 프로젝트의 데이터 규격 (뼈대)

API 요청/응답 및 Agent 간 데이터 전달에 사용되는 모든 Pydantic 모델 정의.
interface_spec.md의 JSON 스키마와 1:1 대응.

  - simulation_input.py   : 시뮬레이션 요청 입력 (Client → API)
  - simulation_output.py  : 시뮬레이션 결과 출력 (API → Frontend)
  - district_data.py      : 행정동별 데이터 (유동인구, 주거인구, 임대료 등)
  - competition_models.py : 경쟁 분석 모델 (직접/간접/카니발리제이션)
  - report_models.py      : 리포트 출력 (경영진 요약, 추천, 리스크)

담당: B — AI Agent 개발자
"""
