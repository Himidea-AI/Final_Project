# 1주차 외부 API 연동 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 6개 외부 API 클라이언트를 구현하여 마포구 상권분석에 필요한 데이터를 수집할 수 있게 한다.

**Architecture:** 모든 클라이언트는 `BaseAPIClient`를 상속. 각 API 응답을 정규화된 dict로 반환. CSV 보유 데이터는 별도 로더로 처리하여 API 장애 시 오프라인 폴백으로 사용.

**Tech Stack:** httpx, tenacity, pandas, pytest, pytest-asyncio

---

## 파일 구조

| 액션 | 파일 | 역할 |
|------|------|------|
| Modify | `backend/src/services/base_client.py` | POST 메서드 추가 |
| Modify | `backend/src/services/seoul_opendata.py` | 서울 생활인구 API 구현 |
| Modify | `backend/src/services/sgis_api.py` | SGIS OAuth2 + 인구/가구/사업체 조회 |
| Modify | `backend/src/services/semas_api.py` | 소상공인 상가정보 조회 |
| Modify | `backend/src/services/golmok_api.py` | 골목상권 추정매출/임대료 조회 |
| Modify | `backend/src/services/molit_api.py` | 국토부 상업용 매매 실거래가 조회 |
| Modify | `backend/src/services/sns_trend.py` | 네이버 트렌드 검색량 조회 |
| Create | `backend/src/services/csv_loader.py` | 보유 CSV 데이터 로더 (오프라인 폴백) |
| Modify | `tests/test_services.py` | 전체 서비스 유닛 테스트 |
| Modify | `backend/requirements.txt` | pytest-asyncio 추가 |

---

### Task 1: base_client.py에 POST 메서드 추가

네이버 트렌드 API가 POST를 사용하므로 BaseAPIClient에 POST 지원이 필요하다.

**Files:**
- Modify: `backend/src/services/base_client.py`
- Modify: `tests/test_services.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: requirements.txt에 pytest-asyncio 추가**

`backend/requirements.txt` 끝에 추가:
```
pytest-asyncio>=0.24.0
```

- [ ] **Step 2: base_client 테스트 작성**

`tests/test_services.py`를 아래 내용으로 교체:

```python
"""
API 클라이언트 검증 — 외부 API 연동 테스트
모든 테스트는 외부 API를 호출하지 않고 httpx mock으로 검증.
"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from src.services.base_client import BaseAPIClient


@pytest.mark.asyncio
async def test_base_client_get():
    """BaseAPIClient GET 요청 동작 검증"""
    client = BaseAPIClient(base_url="https://example.com", timeout=5)
    mock_response = httpx.Response(200, json={"status": "ok"})

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get("/test")
        assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_base_client_post():
    """BaseAPIClient POST 요청 동작 검증"""
    client = BaseAPIClient(base_url="https://example.com", timeout=5)
    mock_response = httpx.Response(200, json={"result": "created"})

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
        result = await client.post("/test", json_data={"key": "value"})
        assert result == {"result": "created"}
```

- [ ] **Step 3: 테스트 실행 — POST 테스트 실패 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py::test_base_client_post -v`
Expected: FAIL (post method not defined)

- [ ] **Step 4: base_client.py에 POST 메서드 구현**

`backend/src/services/base_client.py`에 추가:

```python
async def post(self, endpoint: str, json_data: dict = None, params: dict = None) -> dict:
    """POST 요청"""
    url = f"{self.base_url}{endpoint}"
    self._log("TOOL_CALL", f"POST {url}")

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(url, json=json_data, params=params)
        response.raise_for_status()
        self._log("SUCCESS", f"Status {response.status_code}")
        return response.json()
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py -v`
Expected: 2 passed

- [ ] **Step 6: 커밋**

```bash
git add backend/src/services/base_client.py tests/test_services.py backend/requirements.txt
git commit -m "IM3-28: BaseAPIClient POST 메서드 추가 + 테스트"
```

---

### Task 2: 서울 생활인구 API (seoul_opendata.py)

서울 열린데이터광장의 생활인구 API를 구현한다. API 서버 장애 시를 대비하여 보유 CSV 로딩 기능도 함께 구현한다.

**Files:**
- Modify: `backend/src/services/seoul_opendata.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_services.py`에 추가:

```python
from src.services.seoul_opendata import SeoulOpendataClient


@pytest.mark.asyncio
async def test_seoul_opendata_parse_population():
    """서울 생활인구 API 응답 파싱 검증"""
    client = SeoulOpendataClient(api_key="test_key")

    # 서울 열린데이터 API 실제 응답 형식
    mock_api_response = httpx.Response(200, json={
        "SPOP_LOCAL_RESD_DONG": {
            "list_total_count": 1,
            "row": [
                {
                    "STDR_DE_ID": "20260101",
                    "TMZON_PD_SE": "00",
                    "ADSTRD_CODE_SE": "11440",
                    "TOT_LVPOP_CO": "12345.67",
                    "MALE_F0T9_LVPOP_CO": "500.0",
                    "MALE_F10T14_LVPOP_CO": "600.0",
                    "FEMALE_F0T9_LVPOP_CO": "480.0",
                    "FEMALE_F10T14_LVPOP_CO": "590.0",
                }
            ],
        }
    })

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_api_response):
        result = await client.get_living_population(district_code="11440", date="20260101")
        assert result["total_population"] == 12345.67
        assert "male" in result
        assert "female" in result
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py::test_seoul_opendata_parse_population -v`
Expected: FAIL

- [ ] **Step 3: seoul_opendata.py 구현**

```python
"""
서울 열린데이터광장 API — 생활인구(KT 통신 기반), 지하철 승하차 데이터 조회

주의: 서울시 자체 유동인구조사는 2015년 중단됨.
"서울 생활인구" 데이터(KT 통신 기반, 행정동 단위)를 사용해야 함.
API 코드: SPOP_LOCAL_RESD_DONG (서울 생활인구 - 행정동)
"""
from typing import Optional

from src.services.base_client import BaseAPIClient


# 성별·연령대 컬럼 매핑
AGE_GROUPS = [
    "F0T9", "F10T14", "F15T19", "F20T24", "F25T29",
    "F30T34", "F35T39", "F40T44", "F45T49", "F50T54",
    "F55T59", "F60T64", "F65T69", "F70T74",
]


class SeoulOpendataClient(BaseAPIClient):
    """서울 열린데이터광장 API 클라이언트"""

    def __init__(self, api_key: str):
        super().__init__(base_url="http://openapi.seoul.go.kr:8088", api_key=api_key)

    async def get_living_population(
        self, district_code: str, date: str = "", start: int = 1, end: int = 1000
    ) -> dict:
        """
        서울 생활인구 데이터 조회

        Args:
            district_code: 자치구코드 (예: "11440" = 마포구)
            date: 조회 날짜 (YYYYMMDD, 빈 값이면 최신)
            start: 조회 시작 인덱스
            end: 조회 종료 인덱스

        Returns:
            dict: total_population, male (연령대별), female (연령대별)
        """
        endpoint = f"/{self.api_key}/json/SPOP_LOCAL_RESD_DONG/{start}/{end}"
        params = {"ADSTRD_CODE_SE": district_code}
        if date:
            params["STDR_DE_ID"] = date

        data = await self.get(endpoint, params=params)
        rows = data.get("SPOP_LOCAL_RESD_DONG", {}).get("row", [])

        if not rows:
            return {"total_population": 0, "male": {}, "female": {}}

        return self._parse_population(rows[0])

    def _parse_population(self, row: dict) -> dict:
        """API 응답 row를 정규화된 dict로 변환"""
        male = {}
        female = {}
        for age in AGE_GROUPS:
            male_key = f"MALE_{age}_LVPOP_CO"
            female_key = f"FEMALE_{age}_LVPOP_CO"
            male[age] = float(row.get(male_key, 0))
            female[age] = float(row.get(female_key, 0))

        return {
            "date": row.get("STDR_DE_ID", ""),
            "district_code": row.get("ADSTRD_CODE_SE", ""),
            "total_population": float(row.get("TOT_LVPOP_CO", 0)),
            "male": male,
            "female": female,
        }

    async def get_subway_traffic(self, station_name: str) -> dict:
        """지하철 승하차 데이터 조회"""
        endpoint = f"/{self.api_key}/json/CardSubwayStatsNew/1/1000"
        params = {"SUB_STA_NM": station_name}
        data = await self.get(endpoint, params=params)
        rows = data.get("CardSubwayStatsNew", {}).get("row", [])

        if not rows:
            return {"station": station_name, "total_ride": 0, "total_alight": 0}

        row = rows[0]
        return {
            "station": station_name,
            "total_ride": int(float(row.get("RIDE_PASGR_NUM", 0))),
            "total_alight": int(float(row.get("ALIGHT_PASGR_NUM", 0))),
        }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/src/services/seoul_opendata.py tests/test_services.py
git commit -m "IM3-28: 서울 생활인구 API 클라이언트 구현"
```

---

### Task 3: SGIS 통계 API (sgis_api.py)

OAuth2 인증 + 주거인구/연령분포/가구구성 조회를 구현한다.

**Files:**
- Modify: `backend/src/services/sgis_api.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_services.py`에 추가:

```python
from src.services.sgis_api import SgisAPIClient


@pytest.mark.asyncio
async def test_sgis_authenticate():
    """SGIS OAuth2 인증 테스트"""
    client = SgisAPIClient(consumer_key="test_key", consumer_secret="test_secret")

    mock_response = httpx.Response(200, json={
        "errMsg": "Success",
        "errCd": 0,
        "result": {"accessToken": "mock_token_12345"}
    })

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
        token = await client.authenticate()
        assert token == "mock_token_12345"
        assert client._access_token == "mock_token_12345"


@pytest.mark.asyncio
async def test_sgis_get_resident_population():
    """SGIS 주거인구 조회 테스트"""
    client = SgisAPIClient(consumer_key="test_key", consumer_secret="test_secret")
    client._access_token = "mock_token"

    mock_response = httpx.Response(200, json={
        "errMsg": "Success",
        "errCd": 0,
        "result": [
            {"adm_cd": "11440101", "population": 15000, "avg_age": 38.5}
        ]
    })

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_resident_population(adm_cd="11440101")
        assert result[0]["population"] == 15000
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py::test_sgis_authenticate -v`
Expected: FAIL

- [ ] **Step 3: sgis_api.py 구현**

```python
"""
통계청 SGIS API — 주거인구, 연령별 분포, 가구구성 데이터 조회

주의: SGIS는 OAuth2 인증이 필요.
consumer_key + consumer_secret으로 access_token을 먼저 발급받아야 함.
토큰 유효시간은 1시간.
"""
from typing import Optional

from src.services.base_client import BaseAPIClient


class SgisAPIClient(BaseAPIClient):
    """통계청 SGIS API 클라이언트 (OAuth2 인증)"""

    def __init__(self, consumer_key: str, consumer_secret: str):
        super().__init__(base_url="https://sgis.kostat.go.kr/OpenAPI3")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self._access_token: str = ""

    async def authenticate(self) -> str:
        """OAuth2 액세스 토큰 발급 (유효시간 1시간)"""
        data = await self.get("/auth/authentication.json", params={
            "consumer_key": self.consumer_key,
            "consumer_secret": self.consumer_secret,
        })
        token = data.get("result", {}).get("accessToken", "")
        self._access_token = token
        self._log("AUTH", f"Token acquired: {token[:10]}...")
        return token

    async def _ensure_token(self) -> None:
        """토큰이 없으면 자동 발급"""
        if not self._access_token:
            await self.authenticate()

    async def get_resident_population(self, adm_cd: str, year: str = "2024") -> list[dict]:
        """
        주거인구 조회

        Args:
            adm_cd: 행정동 코드 (예: "11440101")
            year: 기준 연도

        Returns:
            list[dict]: 소지역별 인구 데이터
        """
        await self._ensure_token()
        data = await self.get("/stats/population.json", params={
            "accessToken": self._access_token,
            "adm_cd": adm_cd,
            "year": year,
        })
        return data.get("result", [])

    async def get_age_distribution(self, adm_cd: str, year: str = "2024") -> list[dict]:
        """
        연령별 인구 분포 조회

        Args:
            adm_cd: 행정동 코드
            year: 기준 연도

        Returns:
            list[dict]: 연령대별 인구 데이터
        """
        await self._ensure_token()
        data = await self.get("/stats/agePopulation.json", params={
            "accessToken": self._access_token,
            "adm_cd": adm_cd,
            "year": year,
        })
        return data.get("result", [])

    async def get_household_composition(self, adm_cd: str, year: str = "2024") -> list[dict]:
        """
        가구구성 조회

        Args:
            adm_cd: 행정동 코드
            year: 기준 연도

        Returns:
            list[dict]: 가구 유형별 데이터
        """
        await self._ensure_token()
        data = await self.get("/stats/household.json", params={
            "accessToken": self._access_token,
            "adm_cd": adm_cd,
            "year": year,
        })
        return data.get("result", [])
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/src/services/sgis_api.py tests/test_services.py
git commit -m "IM3-28: SGIS OAuth2 인증 + 인구/가구 API 구현"
```

---

### Task 4: 소상공인 상가정보 API (semas_api.py)

소상공인시장진흥공단 API로 업종밀도, 평균매출, 폐업률을 조회한다.

**Files:**
- Modify: `backend/src/services/semas_api.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_services.py`에 추가:

```python
from src.services.semas_api import SemasAPIClient


@pytest.mark.asyncio
async def test_semas_get_business_density():
    """소상공인 업종밀도 조회 테스트"""
    client = SemasAPIClient(api_key="test_key")

    mock_response = httpx.Response(200, json={
        "header": {"resultCode": "00", "resultMsg": "OK"},
        "body": {
            "items": [
                {
                    "adongNm": "망원1동",
                    "storCnt": 150,
                    "bsnsCdNm": "커피전문점/카페",
                }
            ],
            "totalCount": 1,
        }
    })

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_business_density(adong_cd="11440101", business_code="Q01A01")
        assert result["total_count"] == 1
        assert result["items"][0]["store_count"] == 150
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py::test_semas_get_business_density -v`
Expected: FAIL

- [ ] **Step 3: semas_api.py 구현**

```python
"""
소상공인시장진흥공단 API — 업종밀도, 평균매출, 폐업률 데이터 조회

API 베이스: https://apis.data.go.kr/B553077
인증: ServiceKey 파라미터
"""
from src.services.base_client import BaseAPIClient


class SemasAPIClient(BaseAPIClient):
    """소상공인시장진흥공단 API 클라이언트"""

    def __init__(self, api_key: str):
        super().__init__(base_url="https://apis.data.go.kr/B553077", api_key=api_key)

    def _base_params(self) -> dict:
        return {"ServiceKey": self.api_key, "type": "json", "numOfRows": 1000}

    async def get_business_density(self, adong_cd: str, business_code: str) -> dict:
        """
        업종밀도 조회 — 행정동별 업종 점포 수

        Args:
            adong_cd: 행정동 코드
            business_code: 업종 소분류 코드 (예: "Q01A01")

        Returns:
            dict: total_count, items (store_count, business_name 등)
        """
        params = {**self._base_params(), "adongCd": adong_cd, "indsLclsCd": business_code[:3]}
        data = await self.get("/api/DataInqireService/getStoreInfoInUpjong", params=params)
        body = data.get("body", {})
        items = body.get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]

        return {
            "total_count": body.get("totalCount", 0),
            "items": [
                {
                    "district_name": item.get("adongNm", ""),
                    "store_count": int(item.get("storCnt", 0)),
                    "business_name": item.get("bsnsCdNm", ""),
                }
                for item in items
            ],
        }

    async def get_avg_revenue(self, adong_cd: str, business_code: str) -> dict:
        """
        평균매출 조회

        Args:
            adong_cd: 행정동 코드
            business_code: 업종 소분류 코드

        Returns:
            dict: avg_monthly_revenue, items
        """
        params = {**self._base_params(), "adongCd": adong_cd, "indsLclsCd": business_code[:3]}
        data = await self.get("/api/DataInqireService/getStoreInfoInRevenue", params=params)
        body = data.get("body", {})
        items = body.get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]

        return {
            "total_count": body.get("totalCount", 0),
            "items": [
                {
                    "district_name": item.get("adongNm", ""),
                    "avg_monthly_revenue": int(item.get("avgMonthlySales", 0)),
                }
                for item in items
            ],
        }

    async def get_closure_rate(self, adong_cd: str, business_code: str) -> dict:
        """
        폐업률 조회

        Args:
            adong_cd: 행정동 코드
            business_code: 업종 소분류 코드

        Returns:
            dict: closure_rate, items
        """
        params = {**self._base_params(), "adongCd": adong_cd, "indsLclsCd": business_code[:3]}
        data = await self.get("/api/DataInqireService/getStoreInfoInClose", params=params)
        body = data.get("body", {})
        items = body.get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]

        return {
            "total_count": body.get("totalCount", 0),
            "items": [
                {
                    "district_name": item.get("adongNm", ""),
                    "closure_count": int(item.get("closeCnt", 0)),
                    "closure_rate": float(item.get("closeRate", 0)),
                }
                for item in items
            ],
        }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/src/services/semas_api.py tests/test_services.py
git commit -m "IM3-28: 소상공인 상가정보 API 구현 (업종밀도/매출/폐업률)"
```

---

### Task 5: 골목상권 API (golmok_api.py)

서울 상권분석서비스(우리마을가게) API로 추정매출, 폐업/생존율, 점포수를 조회한다.

**Files:**
- Modify: `backend/src/services/golmok_api.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_services.py`에 추가:

```python
from src.services.golmok_api import GolmokAPIClient


@pytest.mark.asyncio
async def test_golmok_get_estimated_sales():
    """골목상권 추정매출 조회 테스트"""
    client = GolmokAPIClient(api_key="test_key")

    mock_response = httpx.Response(200, json={
        "VwsmTrdarSelng": {
            "list_total_count": 1,
            "row": [
                {
                    "STDR_YR_CD": "2025",
                    "STDR_QU_CD": "4",
                    "TRDAR_CD": "1001",
                    "SVC_INDUTY_CD": "CS100001",
                    "THSMON_SELNG_AMT": 50000000,
                    "THSMON_SELNG_CO": 3000,
                    "MDW_SELNG_AMT": 8000000,
                    "WKN_SELNG_AMT": 4000000,
                }
            ],
        }
    })

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_estimated_sales(trdar_cd="1001", svc_induty_cd="CS100001")
        assert result["monthly_sales"] == 50000000
        assert result["weekday_sales"] == 8000000
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py::test_golmok_get_estimated_sales -v`
Expected: FAIL

- [ ] **Step 3: golmok_api.py 구현**

```python
"""
서울 상권분석서비스(우리마을가게) API — 상권 현황, 폐업률, 생존율, 추정매출 조회

카드사 빅데이터 직접 접근은 기업 제휴 없이 불가하므로,
이 API에서 제공하는 "카드사 결제금액 기반 추정 매출" 데이터를 활용.

베이스 URL: http://openapi.seoul.go.kr:8088
"""
from src.services.base_client import BaseAPIClient


class GolmokAPIClient(BaseAPIClient):
    """서울 상권분석서비스 API 클라이언트"""

    def __init__(self, api_key: str):
        super().__init__(base_url="http://openapi.seoul.go.kr:8088", api_key=api_key)

    async def get_estimated_sales(
        self, trdar_cd: str, svc_induty_cd: str, start: int = 1, end: int = 100
    ) -> dict:
        """
        추정매출 조회 — 카드사 결제금액 기반

        Args:
            trdar_cd: 상권 코드
            svc_induty_cd: 서비스 업종 코드
            start: 시작 인덱스
            end: 종료 인덱스

        Returns:
            dict: monthly_sales, weekday_sales, weekend_sales 등
        """
        endpoint = f"/{self.api_key}/json/VwsmTrdarSelng/{start}/{end}"
        params = {"TRDAR_CD": trdar_cd, "SVC_INDUTY_CD": svc_induty_cd}
        data = await self.get(endpoint, params=params)
        rows = data.get("VwsmTrdarSelng", {}).get("row", [])

        if not rows:
            return {"monthly_sales": 0, "weekday_sales": 0, "weekend_sales": 0}

        row = rows[0]
        return {
            "year": row.get("STDR_YR_CD", ""),
            "quarter": row.get("STDR_QU_CD", ""),
            "commercial_code": row.get("TRDAR_CD", ""),
            "monthly_sales": int(row.get("THSMON_SELNG_AMT", 0)),
            "monthly_count": int(row.get("THSMON_SELNG_CO", 0)),
            "weekday_sales": int(row.get("MDW_SELNG_AMT", 0)),
            "weekend_sales": int(row.get("WKN_SELNG_AMT", 0)),
        }

    async def get_store_count(
        self, trdar_cd: str, svc_induty_cd: str, start: int = 1, end: int = 100
    ) -> dict:
        """
        점포 수 조회 — 업종별 점포 현황

        Returns:
            dict: total_stores, franchise_stores, open_count, close_count
        """
        endpoint = f"/{self.api_key}/json/VwsmTrdarStorQq/{start}/{end}"
        params = {"TRDAR_CD": trdar_cd, "SVC_INDUTY_CD": svc_induty_cd}
        data = await self.get(endpoint, params=params)
        rows = data.get("VwsmTrdarStorQq", {}).get("row", [])

        if not rows:
            return {"total_stores": 0, "franchise_stores": 0}

        row = rows[0]
        return {
            "total_stores": int(row.get("STOR_CO", 0)),
            "franchise_stores": int(row.get("FRC_STOR_CO", 0)),
            "open_count": int(row.get("OPBIZ_STOR_CO", 0)),
            "close_count": int(row.get("CLSBIZ_STOR_CO", 0)),
        }

    async def get_commercial_area_info(
        self, trdar_cd: str, start: int = 1, end: int = 100
    ) -> dict:
        """상권 현황 조회"""
        endpoint = f"/{self.api_key}/json/VwsmTrdarW/{start}/{end}"
        params = {"TRDAR_CD": trdar_cd}
        data = await self.get(endpoint, params=params)
        rows = data.get("VwsmTrdarW", {}).get("row", [])

        if not rows:
            return {}

        row = rows[0]
        return {
            "commercial_code": row.get("TRDAR_CD", ""),
            "commercial_name": row.get("TRDAR_CD_NM", ""),
            "area_size": float(row.get("TRDAR_AREA", 0)),
        }

    async def get_closure_survival_rate(
        self, trdar_cd: str, svc_induty_cd: str, start: int = 1, end: int = 100
    ) -> dict:
        """폐업률/생존율 조회"""
        endpoint = f"/{self.api_key}/json/VwsmTrdarStorQq/{start}/{end}"
        params = {"TRDAR_CD": trdar_cd, "SVC_INDUTY_CD": svc_induty_cd}
        data = await self.get(endpoint, params=params)
        rows = data.get("VwsmTrdarStorQq", {}).get("row", [])

        if not rows:
            return {"open_count": 0, "close_count": 0, "closure_rate": 0}

        row = rows[0]
        open_cnt = int(row.get("OPBIZ_STOR_CO", 0))
        close_cnt = int(row.get("CLSBIZ_STOR_CO", 0))
        total = open_cnt + close_cnt
        rate = (close_cnt / total * 100) if total > 0 else 0

        return {
            "open_count": open_cnt,
            "close_count": close_cnt,
            "closure_rate": round(rate, 2),
        }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py -v`
Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/src/services/golmok_api.py tests/test_services.py
git commit -m "IM3-28: 골목상권 API 구현 (추정매출/점포수/폐업률)"
```

---

### Task 6: 국토부 실거래가 API (molit_api.py)

상업업무용 매매 실거래가를 조회한다. (임대차 API는 공공데이터포털에 없으므로 매매만 구현)

**Files:**
- Modify: `backend/src/services/molit_api.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_services.py`에 추가:

```python
from src.services.molit_api import MolitAPIClient


@pytest.mark.asyncio
async def test_molit_get_commercial_trade():
    """국토부 상업용 매매 실거래가 조회 테스트"""
    client = MolitAPIClient(api_key="test_key")

    mock_response = httpx.Response(200, json={
        "response": {
            "header": {"resultCode": "00"},
            "body": {
                "items": {
                    "item": [
                        {
                            "dealAmount": "150,000",
                            "buildingMainPurps": "제1종근린생활시설",
                            "sggCd": "11440",
                            "umdNm": "서교동",
                            "dealYear": "2026",
                            "dealMonth": "3",
                            "excluUseAr": 45.5,
                        }
                    ]
                },
                "totalCount": 1,
            }
        }
    })

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_commercial_trade(sgg_cd="11440", deal_ymd="202603")
        assert len(result["items"]) == 1
        assert result["items"][0]["deal_amount"] == 150000
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py::test_molit_get_commercial_trade -v`
Expected: FAIL

- [ ] **Step 3: molit_api.py 구현**

```python
"""
국토교통부 실거래가 API — 상업업무용 매매 실거래가 조회

참고: 상업업무용 임대차 API는 공공데이터포털에 없음.
매매 실거래가만 조회 가능. 임대료는 골목상권 API + 부동산원 CSV로 대체.
"""
from src.services.base_client import BaseAPIClient


class MolitAPIClient(BaseAPIClient):
    """국토교통부 실거래가 API 클라이언트"""

    def __init__(self, api_key: str):
        super().__init__(base_url="https://apis.data.go.kr/1613000", api_key=api_key)

    async def get_commercial_trade(self, sgg_cd: str, deal_ymd: str) -> dict:
        """
        상업업무용 매매 실거래가 조회

        Args:
            sgg_cd: 시군구 코드 (예: "11440" = 마포구)
            deal_ymd: 계약년월 (YYYYMM, 예: "202603")

        Returns:
            dict: total_count, items (deal_amount, area, district 등)
        """
        params = {
            "ServiceKey": self.api_key,
            "LAWD_CD": sgg_cd,
            "DEAL_YMD": deal_ymd,
            "type": "json",
            "numOfRows": 1000,
        }
        data = await self.get(
            "/RTMSDataSvcNrgTrade/getRTMSDataSvcSHTrade", params=params
        )
        body = data.get("response", {}).get("body", {})
        items = body.get("items", {})
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]

        return {
            "total_count": body.get("totalCount", 0),
            "items": [self._parse_item(item) for item in items],
        }

    def _parse_item(self, item: dict) -> dict:
        """응답 item을 정규화"""
        amount_str = str(item.get("dealAmount", "0")).replace(",", "").strip()
        return {
            "deal_amount": int(amount_str) if amount_str else 0,
            "building_purpose": item.get("buildingMainPurps", ""),
            "sgg_cd": item.get("sggCd", ""),
            "district_name": item.get("umdNm", ""),
            "deal_year": item.get("dealYear", ""),
            "deal_month": item.get("dealMonth", ""),
            "area": float(item.get("excluUseAr", 0)),
        }

    async def get_rent_trend(self, sgg_cd: str, months: int = 12) -> list[dict]:
        """
        최근 N개월 매매가 추이 조회

        Args:
            sgg_cd: 시군구 코드
            months: 조회 개월 수

        Returns:
            list[dict]: 월별 평균 매매가 리스트
        """
        from datetime import datetime, timedelta

        results = []
        now = datetime.now()
        for i in range(months):
            target = now - timedelta(days=30 * i)
            deal_ymd = target.strftime("%Y%m")
            data = await self.get_commercial_trade(sgg_cd=sgg_cd, deal_ymd=deal_ymd)
            items = data.get("items", [])
            if items:
                avg_amount = sum(it["deal_amount"] for it in items) / len(items)
            else:
                avg_amount = 0
            results.append({"year_month": deal_ymd, "avg_deal_amount": round(avg_amount)})

        return results
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py -v`
Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/src/services/molit_api.py tests/test_services.py
git commit -m "IM3-28: 국토부 상업용 매매 실거래가 API 구현"
```

---

### Task 7: 네이버 트렌드 API (sns_trend.py)

네이버 DataLab 검색량 트렌드를 조회하여 행정동별 힙지수를 산출한다.

**Files:**
- Modify: `backend/src/services/sns_trend.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_services.py`에 추가:

```python
from src.services.sns_trend import NaverTrendClient


@pytest.mark.asyncio
async def test_naver_get_search_trend():
    """네이버 트렌드 검색량 조회 테스트"""
    client = NaverTrendClient(client_id="test_id", client_secret="test_secret")

    mock_response = httpx.Response(200, json={
        "startDate": "2025-04-01",
        "endDate": "2026-04-01",
        "timeUnit": "month",
        "results": [
            {
                "title": "망원동 카페",
                "keywords": ["망원동 카페"],
                "data": [
                    {"period": "2026-03-01", "ratio": 85.5},
                    {"period": "2026-02-01", "ratio": 78.2},
                ],
            }
        ],
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_search_trend(
            keywords=["망원동 카페"],
            start_date="2025-04-01",
            end_date="2026-04-01",
        )
        assert result["results"][0]["title"] == "망원동 카페"
        assert result["results"][0]["data"][0]["ratio"] == 85.5
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py::test_naver_get_search_trend -v`
Expected: FAIL

- [ ] **Step 3: sns_trend.py 구현**

```python
"""
Naver DataLab 트렌드 API — 키워드 검색량 추이 기반 상권 트렌드 분석

Instagram/블로그 크롤링 대신 Naver DataLab API를 사용.
Naver Developers에서 무료 API 키 발급 가능.
"""
from datetime import datetime, timedelta

import httpx

from src.services.base_client import BaseAPIClient


class NaverTrendClient(BaseAPIClient):
    """Naver DataLab 트렌드 API 클라이언트"""

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(base_url="https://openapi.naver.com/v1/datalab")
        self.client_id = client_id
        self.client_secret = client_secret

    def _get_headers(self) -> dict:
        """Naver API 인증 헤더"""
        return {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Content-Type": "application/json",
        }

    async def get_search_trend(
        self,
        keywords: list[str],
        start_date: str,
        end_date: str,
        time_unit: str = "month",
    ) -> dict:
        """
        키워드 검색량 추이 조회

        Args:
            keywords: 검색 키워드 리스트
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            time_unit: 집계 단위 (date/week/month)

        Returns:
            dict: results (기간별 상대 검색량 0~100)
        """
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": [
                {"groupName": kw, "keywords": [kw]} for kw in keywords
            ],
        }

        url = f"{self.base_url}/search"
        self._log("TOOL_CALL", f"POST {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=body, headers=self._get_headers())
            response.raise_for_status()
            self._log("SUCCESS", f"Status {response.status_code}")
            return response.json()

    async def get_district_trend(self, district: str, business_type: str) -> dict:
        """
        행정동+업종 키워드 트렌드 조회

        Args:
            district: 행정동명 (예: "망원동")
            business_type: 업종 키워드 (예: "카페")

        Returns:
            dict: trend_data, growth_rate (전월 대비 증감률 %)
        """
        keyword = f"{district} {business_type}"
        end = datetime.now()
        start = end - timedelta(days=365)

        result = await self.get_search_trend(
            keywords=[keyword],
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            time_unit="month",
        )

        data_points = result.get("results", [{}])[0].get("data", [])
        growth_rate = 0.0
        if len(data_points) >= 2:
            current = data_points[-1]["ratio"]
            previous = data_points[-2]["ratio"]
            if previous > 0:
                growth_rate = round((current - previous) / previous * 100, 2)

        return {
            "keyword": keyword,
            "trend_data": data_points,
            "growth_rate": growth_rate,
        }

    async def calculate_hipness_score(self, district: str) -> float:
        """
        힙지수 계산 — 검색량 트렌드 기반

        Returns:
            float: 0~100 힙지수
        """
        keywords_to_check = ["맛집", "카페", "핫플", "데이트"]
        end = datetime.now()
        start = end - timedelta(days=365)

        result = await self.get_search_trend(
            keywords=[f"{district} {kw}" for kw in keywords_to_check],
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            time_unit="month",
        )

        scores = []
        for group in result.get("results", []):
            data_points = group.get("data", [])
            if not data_points:
                continue
            latest = data_points[-1]["ratio"]
            avg = sum(d["ratio"] for d in data_points) / len(data_points)
            growth = (latest - avg) / avg * 100 if avg > 0 else 0
            # 절대 검색량(50%) + 증감률(50%) 가중 합산
            score = latest * 0.5 + min(max(growth + 50, 0), 100) * 0.5
            scores.append(score)

        return round(sum(scores) / len(scores), 1) if scores else 0.0
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py -v`
Expected: 9 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/src/services/sns_trend.py tests/test_services.py
git commit -m "IM3-28: 네이버 트렌드 API 구현 (검색량/힙지수)"
```

---

### Task 8: CSV 데이터 로더 (csv_loader.py)

보유한 CSV 파일을 로딩하여 API 장애 시 오프라인 폴백으로 사용한다. 데스크톱의 데이터 파일을 `data/` 디렉토리로 복사 후 로딩한다.

**Files:**
- Create: `backend/src/services/csv_loader.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_services.py`에 추가:

```python
import os
import tempfile
from src.services.csv_loader import CsvDataLoader


def test_csv_loader_living_population():
    """생활인구 CSV 로딩 + 마포구 필터링 테스트"""
    # 테스트용 임시 CSV 생성
    csv_content = "stdr_de_id,tmzon_pd_se,adstrd_code_se,tot_lvpop_co\n"
    csv_content += "20260101,00,1144055,12345.67\n"
    csv_content += "20260101,00,1130051,99999.99\n"  # 마포구 아님

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        tmp_path = f.name

    try:
        loader = CsvDataLoader(data_dir=os.path.dirname(tmp_path))
        df = loader.load_living_population(file_path=tmp_path, district_prefix="11440")
        assert len(df) == 1
        assert df.iloc[0]["tot_lvpop_co"] == 12345.67
    finally:
        os.unlink(tmp_path)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py::test_csv_loader_living_population -v`
Expected: FAIL

- [ ] **Step 3: csv_loader.py 구현**

```python
"""
CSV 데이터 로더 — 보유한 CSV 파일을 로딩하여 API 장애 시 오프라인 폴백으로 사용

지원 데이터:
- 서울 생활인구 (LOCAL_PEOPLE_GU_*.csv)
- SGIS 소지역 통계 (11140_*.csv)
- 소상공인 상가정보 (소상공인시장진흥공단_상가*.csv)
- 상권변화지표 (서울시 상권분석서비스*.csv)
"""
from pathlib import Path

import pandas as pd


class CsvDataLoader:
    """CSV 파일 로더"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)

    def load_living_population(
        self, file_path: str, district_prefix: str = "11440"
    ) -> pd.DataFrame:
        """
        서울 생활인구 CSV 로딩 + 마포구 필터링

        Args:
            file_path: CSV 파일 경로
            district_prefix: 자치구 코드 접두사 (마포구 = "11440")

        Returns:
            pd.DataFrame: 마포구 생활인구 데이터
        """
        df = pd.read_csv(file_path, dtype={"adstrd_code_se": str})
        df = df[df["adstrd_code_se"].str.startswith(district_prefix)]
        return df

    def load_sgis_stats(self, file_path: str) -> pd.DataFrame:
        """
        SGIS 소지역 통계 CSV 로딩 (헤더 없음)

        컬럼 순서: 연도, 소지역코드, 지표코드, 값
        """
        df = pd.read_csv(
            file_path,
            header=None,
            names=["year", "area_code", "indicator_code", "value"],
            dtype={"area_code": str},
        )
        return df

    def load_store_info(
        self, file_path: str, sgg_name: str = "마포구", encoding: str = "utf-8"
    ) -> pd.DataFrame:
        """
        소상공인 상가정보 CSV 로딩 + 마포구 필터링

        Args:
            file_path: CSV 파일 경로
            sgg_name: 시군구명 필터
            encoding: 파일 인코딩

        Returns:
            pd.DataFrame: 마포구 상가정보
        """
        df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
        if "시군구명" in df.columns:
            df = df[df["시군구명"] == sgg_name]
        return df

    def load_commercial_change(
        self, file_path: str, encoding: str = "cp949"
    ) -> pd.DataFrame:
        """
        상권변화지표 CSV 로딩

        Args:
            file_path: CSV 파일 경로
            encoding: 파일 인코딩 (기본 cp949)

        Returns:
            pd.DataFrame: 상권변화지표 데이터
        """
        df = pd.read_csv(file_path, encoding=encoding)
        return df
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && python -m pytest ../tests/test_services.py -v`
Expected: 10 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/src/services/csv_loader.py tests/test_services.py
git commit -m "IM3-28: CSV 데이터 로더 구현 (오프라인 폴백)"
```

---

### Task 9: __init__.py 업데이트 + 최종 통합 테스트

모든 클라이언트를 패키지에서 export하고 통합 테스트를 실행한다.

**Files:**
- Modify: `backend/src/services/__init__.py`

- [ ] **Step 1: __init__.py 업데이트**

```python
"""
외부 API 클라이언트 패키지 — 7개 공공/오픈 데이터 소스 연동 + CSV 로더

모든 클라이언트는 base_client.py의 BaseAPIClient를 상속하여
retry, rate limit, 에러 핸들링을 공통 처리.
"""
from src.services.base_client import BaseAPIClient
from src.services.seoul_opendata import SeoulOpendataClient
from src.services.sgis_api import SgisAPIClient
from src.services.semas_api import SemasAPIClient
from src.services.golmok_api import GolmokAPIClient
from src.services.molit_api import MolitAPIClient
from src.services.sns_trend import NaverTrendClient
from src.services.csv_loader import CsvDataLoader

__all__ = [
    "BaseAPIClient",
    "SeoulOpendataClient",
    "SgisAPIClient",
    "SemasAPIClient",
    "GolmokAPIClient",
    "MolitAPIClient",
    "NaverTrendClient",
    "CsvDataLoader",
]
```

- [ ] **Step 2: 전체 테스트 실행**

Run: `cd backend && python -m pytest ../tests/test_services.py -v`
Expected: 10 passed

- [ ] **Step 3: import 테스트**

Run: `cd backend && python -c "from src.services import *; print('All imports OK')"`
Expected: "All imports OK"

- [ ] **Step 4: 최종 커밋 + 푸시**

```bash
git add backend/src/services/__init__.py
git commit -m "IM3-28: services 패키지 export 정리 + 1주차 API 연동 완료"
git push origin dev
```
