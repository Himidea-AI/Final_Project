"""
외부 API 클라이언트 패키지 — 7개 공공/오픈 데이터 소스 연동

모든 클라이언트는 base_client.py의 BaseAPIClient를 상속하여
retry, rate limit, 에러 핸들링을 공통 처리.

  - base_client.py    : 공통 HTTP 클라이언트 (3회 재시도 + 지수 백오프)
  - semas_api.py      : 소상공인시장진흥공단 (업종밀도, 평균매출)
  - seoul_opendata.py : 서울 열린데이터광장 (생활인구 OA-14991, 지하철)
  - sgis_api.py       : 통계청 SGIS (주거인구, 연령분포) — OAuth2 인증 필요
  - molit_api.py      : 국토교통부 (상가 임대 실거래가)
  - ftc_franchise.py  : 공정위 가맹사업 정보공개서 (목록 API + XML 파싱)
  - golmok_api.py     : 서울 상권분석서비스 (폐업률, 생존율, 추정매출)
  - sns_trend.py      : Naver DataLab 트렌드 API (키워드 검색량)

담당: A — 데이터 엔지니어
"""
