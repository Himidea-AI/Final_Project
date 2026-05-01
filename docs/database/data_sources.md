# 데이터 소스 목록 및 수집 방법

## 공공/오픈 API (7개 서비스)

| # | 데이터 소스 | 담당 파일 | 주요 데이터 | 비고 |
|---|-----------|----------|-----------|------|
| 1 | 소상공인시장진흥공단 | `semas_api.py` | 업종밀도, 평균매출 | 업종코드 247개 신체계 |
| 2 | 서울 열린데이터광장 | `seoul_opendata.py` | **생활인구**(OA-14991), 지하철 | 유동인구조사 2015년 중단 → KT 생활인구 사용 |
| 3 | 통계청 SGIS | `sgis_api.py` | 주거인구, 연령분포, 가구구성 | **OAuth2 인증** 필요 |
| 4 | 국토교통부 실거래가 | `molit_api.py` | 상가 임대료 추이 | |
| 5 | 공정위 가맹사업 정보공개서 | `ftc_franchise.py` | 브랜드 매출, 가맹점 현황 | API=목록만, **상세는 XML 파싱** |
| 6 | 서울 상권분석서비스 | `golmok_api.py` | 폐업률, 생존율, **추정매출** | 카드사 매출 대체 |
| 7 | Naver DataLab | `sns_trend.py` | 키워드 검색량 트렌드 | 크롤링 대신 API 사용 |

## 주의사항

### 크롤링 금지
- Instagram/블로그 크롤링은 이용약관 위반 + 차단 리스크
- Naver DataLab 트렌드 API로 대체 (무료, Naver Developers 키 발급)

### 카드사 빅데이터
- 신한카드/BC카드 빅데이터는 기업 제휴 없이 접근 불가
- golmok API의 "카드사 결제금액 기반 추정 매출" 데이터로 대체

### 소상공인 업종코드
- 2024년 개편: 837개 → 247개 (대분류 10, 중분류 75, 소분류 247)
- 과거 상가업소번호와 연계 불가 (신규 체계)

### SGIS 인증
- OAuth2 방식: consumer_key + consumer_secret → access_token 발급
- 토큰 유효시간 1시간

## API 키 발급처

| API | 발급처 | URL |
|-----|--------|-----|
| 소상공인/국토부/공정위 | 공공데이터포털 | data.go.kr |
| 서울 열린데이터 | 서울 열린데이터광장 | data.seoul.go.kr |
| 통계청 SGIS | SGIS 오픈플랫폼 | sgis.kostat.go.kr |
| 서울 상권분석 | 서울시 우리마을가게 | golmok.seoul.go.kr |
| Naver DataLab | Naver Developers | developers.naver.com |
