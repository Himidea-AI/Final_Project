"""모든 API 키 작동 검증 — .env 의 각 키를 실제 endpoint 호출로 테스트.

⚠️ 키 값 자체는 절대 print 안 함 (보안). OK/FAIL/NOT_SET 만 출력.

실행:
    python scripts/check_api_keys.py
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _is_set(name: str) -> bool:
    v = os.environ.get(name, "")
    return bool(v) and not v.startswith("your_") and v != "changeme"


def _result(name: str, status: str, detail: str = "") -> None:
    icon = {"OK": "✓", "FAIL": "✗", "NOT_SET": "·", "SKIP": "−"}.get(status, "?")
    line = f"  {icon} {name:30s} {status}"
    if detail:
        line += f" — {detail}"
    print(line)


# ---------------------------------------------------------------------------
# LLM API
# ---------------------------------------------------------------------------
def check_openai() -> None:
    if not _is_set("OPENAI_API_KEY"):
        _result("OPENAI_API_KEY", "NOT_SET")
        return
    try:
        from openai import OpenAI

        c = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        # cheapest call: list models (no token cost)
        models = list(c.models.list())
        _result("OPENAI_API_KEY", "OK", f"{len(models)} models")
    except Exception as e:
        _result("OPENAI_API_KEY", "FAIL", str(e)[:80])


def check_anthropic() -> None:
    if not _is_set("ANTHROPIC_API_KEY"):
        _result("ANTHROPIC_API_KEY", "NOT_SET")
        return
    try:
        import anthropic

        c = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        # min token call
        r = c.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3,
            messages=[{"role": "user", "content": "hi"}],
        )
        _result("ANTHROPIC_API_KEY", "OK", f"haiku model={r.model[:25]}")
    except Exception as e:
        _result("ANTHROPIC_API_KEY", "FAIL", str(e)[:80])


def check_gemini() -> None:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key or key.startswith("your_"):
        _result("GEMINI_API_KEY", "NOT_SET")
        return
    try:
        import google.generativeai as genai

        genai.configure(api_key=key)
        m = genai.GenerativeModel("gemini-2.5-flash-lite")
        r = m.generate_content("hi")
        _result("GEMINI_API_KEY", "OK", f"len={len(r.text or '')}")
    except Exception as e:
        _result("GEMINI_API_KEY", "FAIL", str(e)[:80])


def check_langsmith() -> None:
    key = os.environ.get("LANGCHAIN_API_KEY")
    endpoint = os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    if not key or key.startswith("your_"):
        _result("LANGCHAIN_API_KEY", "NOT_SET")
        return
    try:
        import requests

        r = requests.get(
            f"{endpoint.rstrip('/')}/api/v1/sessions",
            headers={"x-api-key": key},
            params={"limit": 1},
            timeout=10,
        )
        if r.status_code == 200:
            _result("LANGCHAIN_API_KEY", "OK", f"http {r.status_code}")
        else:
            _result("LANGCHAIN_API_KEY", "FAIL", f"http {r.status_code}: {r.text[:60]}")
    except Exception as e:
        _result("LANGCHAIN_API_KEY", "FAIL", str(e)[:80])


# ---------------------------------------------------------------------------
# 한국 정부 API
# ---------------------------------------------------------------------------
def check_ftc() -> None:
    """공정거래위원회 가맹사업거래 API."""
    if not _is_set("FTC_API_KEY"):
        _result("FTC_API_KEY", "NOT_SET")
        return
    try:
        import requests

        # FTC openapi.kftc.or.kr 또는 공정위 openapi — 다양함. 단순 인증 ping
        url = "https://www.ftc.go.kr/api/franchise/getFranchiseList"
        r = requests.get(url, params={"serviceKey": os.environ["FTC_API_KEY"], "pageNo": 1, "numOfRows": 1}, timeout=10)
        if r.status_code == 200 and "INVALID" not in r.text.upper() and "ERROR" not in r.text.upper()[:200]:
            _result("FTC_API_KEY", "OK", f"http {r.status_code}")
        else:
            _result("FTC_API_KEY", "FAIL", f"http {r.status_code}: {r.text[:60]}")
    except Exception as e:
        _result("FTC_API_KEY", "FAIL", str(e)[:80])


def check_molit() -> None:
    """국토교통부 부동산 실거래 API."""
    if not _is_set("MOLIT_API_KEY"):
        _result("MOLIT_API_KEY", "NOT_SET")
        return
    try:
        import requests

        # data.go.kr 표준 — 단순 ping (1행만)
        url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
        r = requests.get(
            url,
            params={
                "serviceKey": os.environ["MOLIT_API_KEY"],
                "LAWD_CD": "11440",
                "DEAL_YMD": "202404",
                "pageNo": 1,
                "numOfRows": 1,
            },
            timeout=10,
        )
        if r.status_code == 200 and "SERVICE ERROR" not in r.text.upper() and "INVALID" not in r.text.upper()[:300]:
            _result("MOLIT_API_KEY", "OK", f"http {r.status_code}")
        else:
            _result("MOLIT_API_KEY", "FAIL", f"http {r.status_code}: {r.text[:60]}")
    except Exception as e:
        _result("MOLIT_API_KEY", "FAIL", str(e)[:80])


def check_nts() -> None:
    """국세청 사업자 진위확인."""
    if not _is_set("NTS_API_KEY"):
        _result("NTS_API_KEY", "NOT_SET")
        return
    try:
        import requests

        url = f"https://api.odcloud.kr/api/nts-businessman/v1/status?serviceKey={os.environ['NTS_API_KEY']}"
        r = requests.post(url, json={"b_no": ["1234567890"]}, timeout=10)
        # NTS 는 아무 사업자번호로 ping 도 200 응답. INVALID KEY 면 다른 응답
        if r.status_code == 200:
            _result("NTS_API_KEY", "OK", "http 200")
        elif r.status_code in (401, 403):
            _result("NTS_API_KEY", "FAIL", f"http {r.status_code} (auth)")
        else:
            _result("NTS_API_KEY", "FAIL", f"http {r.status_code}: {r.text[:60]}")
    except Exception as e:
        _result("NTS_API_KEY", "FAIL", str(e)[:80])


def check_law_oc() -> None:
    """법제처 OC (open id)."""
    if not _is_set("LAW_OC"):
        _result("LAW_OC", "NOT_SET")
        return
    try:
        import requests

        # 법령 검색 ping
        url = f"https://www.law.go.kr/DRF/lawSearch.do?OC={os.environ['LAW_OC']}&target=law&type=JSON&query=상가건물"
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and "<html" not in r.text[:200].lower():
            _result("LAW_OC", "OK", f"http {r.status_code}")
        elif "<html" in r.text[:200].lower():
            _result("LAW_OC", "FAIL", "html error page (auth issue)")
        else:
            _result("LAW_OC", "FAIL", f"http {r.status_code}")
    except Exception as e:
        _result("LAW_OC", "FAIL", str(e)[:80])


def check_semas() -> None:
    """소상공인시장진흥공단 상권정보 API."""
    if not _is_set("SEMAS_API_KEY"):
        _result("SEMAS_API_KEY", "NOT_SET")
        return
    try:
        import requests

        url = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRectangle"
        r = requests.get(
            url,
            params={
                "serviceKey": os.environ["SEMAS_API_KEY"],
                "minX": 126.91,
                "maxX": 126.92,
                "minY": 37.55,
                "maxY": 37.56,
                "type": "json",
                "pageNo": 1,
                "numOfRows": 1,
            },
            timeout=10,
        )
        if r.status_code == 200 and "SERVICE_KEY" not in r.text.upper()[:300]:
            _result("SEMAS_API_KEY", "OK", f"http {r.status_code}")
        else:
            _result("SEMAS_API_KEY", "FAIL", f"http {r.status_code}: {r.text[:60]}")
    except Exception as e:
        _result("SEMAS_API_KEY", "FAIL", str(e)[:80])


def check_seoul() -> None:
    """서울 열린데이터 광장."""
    if not _is_set("SEOUL_OPENDATA_KEY"):
        _result("SEOUL_OPENDATA_KEY", "NOT_SET")
        return
    try:
        import requests

        key = os.environ["SEOUL_OPENDATA_KEY"]
        url = f"http://openapi.seoul.go.kr:8088/{key}/json/SdeTlSccoSigKor/1/1/"
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and ("INFO-200" not in r.text and "INFO-100" in r.text or "RESULT" in r.text):
            _result("SEOUL_OPENDATA_KEY", "OK", f"http {r.status_code}")
        elif "INFO-200" in r.text or "INFO-100" in r.text:
            _result("SEOUL_OPENDATA_KEY", "OK", "INFO-100 (success)")
        else:
            _result("SEOUL_OPENDATA_KEY", "FAIL", f"http {r.status_code}: {r.text[:80]}")
    except Exception as e:
        _result("SEOUL_OPENDATA_KEY", "FAIL", str(e)[:80])


def check_sgis() -> None:
    """통계청 SGIS — token 발급 endpoint 호출."""
    if not _is_set("SGIS_API_KEY") or not _is_set("SGIS_SECRET_KEY"):
        _result("SGIS_API_KEY+SECRET", "NOT_SET")
        return
    try:
        import requests

        url = "https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json"
        r = requests.get(
            url,
            params={
                "consumer_key": os.environ["SGIS_API_KEY"],
                "consumer_secret": os.environ["SGIS_SECRET_KEY"],
            },
            timeout=10,
        )
        d = r.json()
        if r.status_code == 200 and d.get("errCd") == 0 and d.get("result", {}).get("accessToken"):
            _result("SGIS_API_KEY+SECRET", "OK", "token issued")
        else:
            _result("SGIS_API_KEY+SECRET", "FAIL", f"errCd={d.get('errCd')}: {d.get('errMsg', '')[:60]}")
    except Exception as e:
        _result("SGIS_API_KEY+SECRET", "FAIL", str(e)[:80])


# ---------------------------------------------------------------------------
# 외부 API (Naver, Kakao)
# ---------------------------------------------------------------------------
def check_naver() -> None:
    """네이버 검색 API."""
    cid = os.environ.get("NAVER_CLIENT_ID")
    csec = os.environ.get("NAVER_CLIENT_SECRET")
    if not cid or cid.startswith("your_") or not csec or csec.startswith("your_"):
        _result("NAVER_CLIENT_ID+SECRET", "NOT_SET")
        return
    try:
        import requests

        r = requests.get(
            "https://openapi.naver.com/v1/search/local.json",
            headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec},
            params={"query": "공덕역", "display": 1},
            timeout=10,
        )
        if r.status_code == 200:
            _result("NAVER_CLIENT_ID+SECRET", "OK", "http 200")
        else:
            _result("NAVER_CLIENT_ID+SECRET", "FAIL", f"http {r.status_code}: {r.text[:60]}")
    except Exception as e:
        _result("NAVER_CLIENT_ID+SECRET", "FAIL", str(e)[:80])


def check_kakao() -> None:
    """카카오 REST API (지도)."""
    # 흔한 명칭 후보 — 어느 것이 .env 에 있는지 모름
    candidates = ["KAKAO_REST_API_KEY", "KAKAO_API_KEY", "KAKAO_REST_KEY", "KAKAO_NATIVE_KEY"]
    found_name = None
    found_key = None
    for c in candidates:
        v = os.environ.get(c)
        if v and not v.startswith("your_"):
            found_name = c
            found_key = v
            break
    if not found_key:
        _result("KAKAO_*_KEY", "NOT_SET", f"checked: {','.join(candidates)}")
        return
    try:
        import requests

        r = requests.get(
            "https://dapi.kakao.com/v2/local/search/address.json",
            headers={"Authorization": f"KakaoAK {found_key}"},
            params={"query": "서울특별시 마포구 공덕동", "size": 1},
            timeout=10,
        )
        if r.status_code == 200:
            _result(found_name, "OK", "http 200")
        else:
            _result(found_name, "FAIL", f"http {r.status_code}: {r.text[:60]}")
    except Exception as e:
        _result(found_name, "FAIL", str(e)[:80])


# ---------------------------------------------------------------------------
# Infra
# ---------------------------------------------------------------------------
def check_postgres() -> None:
    url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
    if not url:
        _result("POSTGRES_URL", "NOT_SET")
        return
    try:
        import psycopg2

        conn = psycopg2.connect(url, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        _result("POSTGRES_URL", "OK", "connect + SELECT 1")
    except Exception as e:
        _result("POSTGRES_URL", "FAIL", str(e)[:80])


def check_redis() -> None:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    try:
        import redis

        r = redis.from_url(url, socket_timeout=3)
        r.ping()
        _result("REDIS_URL", "OK", "ping")
    except Exception as e:
        _result("REDIS_URL", "FAIL", str(e)[:80])


# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 72)
    print("API 키 작동 검증 (값은 print 안 함)")
    print("=" * 72)

    print("\n[LLM]")
    check_openai()
    check_anthropic()
    check_gemini()
    check_langsmith()

    print("\n[한국 정부 API]")
    check_ftc()
    check_molit()
    check_nts()
    check_law_oc()
    check_semas()
    check_seoul()
    check_sgis()

    print("\n[외부 API]")
    check_naver()
    check_kakao()

    print("\n[Infra]")
    check_postgres()
    check_redis()

    print("\n" + "=" * 72)
    print("범례: ✓ OK  ✗ FAIL  · NOT_SET  − SKIP")
    print("=" * 72)


if __name__ == "__main__":
    main()
