"""
국가법령정보 공동활용 API 클라이언트 (law.go.kr)

지원 기능:
  - 판례 검색 + 상세 조회 병렬 처리

인증: OC 파라미터 (settings.law_oc)
응답 형식: JSON

API 문서: https://www.law.go.kr/LSW/openApi.do
"""

import asyncio
import re

import httpx

from src.config.settings import settings

_BASE_URL = "https://www.law.go.kr/DRF"
_TIMEOUT = 10.0


def _strip_html(text: str) -> str:
    """API 응답의 HTML 태그 제거"""
    return re.sub(r"<[^>]+>", "", text).strip()


class LawApiClient:
    """국가법령정보 공동활용 API 비동기 클라이언트"""

    def __init__(self):
        self._oc = settings.law_oc

    def _is_available(self) -> bool:
        return bool(self._oc)

    async def search_precedents(self, query: str, display: int = 3) -> list[dict]:
        """
        판례 검색 — 검색 결과의 상세 내용(판결요지 등)을 병렬로 조회.

        Args:
            query: 검색어 (예: "권리금 회수 보호")
            display: 반환할 판례 수 (최대 20)

        Returns:
            list[dict]: 판례 목록
            형식: {"content": str, "metadata": {"source", "case_name", "case_number", ...}}
        """
        if not self._is_available():
            return []

        try:
            ids = await self._search(query, display)
            if not ids:
                return []

            # 상세 조회 병렬 실행
            details = await asyncio.gather(*[self._fetch_detail(id_) for id_ in ids])
            return [d for d in details if d]

        except Exception as e:
            print(f"[LawApiClient] 판례 검색 실패 (query={query!r}): {e}")
            return []

    async def _search(self, query: str, display: int) -> list[str]:
        """판례 검색 — 판례일련번호 목록 반환"""
        params = {
            "OC": self._oc,
            "target": "prec",
            "type": "JSON",
            "query": query,
            "display": display,
            "page": 1,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(f"{_BASE_URL}/lawSearch.do", params=params)
            r.raise_for_status()
            data = r.json()

        raw = data.get("PrecSearch", {}).get("prec", [])
        if isinstance(raw, dict):
            raw = [raw]

        return [p["판례일련번호"] for p in raw if "판례일련번호" in p]

    async def _fetch_detail(self, prec_id: str) -> dict | None:
        """판례 상세 조회 — 판시사항·판결요지·참조조문 포함"""
        params = {
            "OC": self._oc,
            "target": "prec",
            "ID": prec_id,
            "type": "JSON",
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(f"{_BASE_URL}/lawService.do", params=params)
                r.raise_for_status()
                p = r.json().get("PrecService", {})

            판시사항 = _strip_html(p.get("판시사항", ""))
            판결요지 = _strip_html(p.get("판결요지", ""))
            참조조문 = _strip_html(p.get("참조조문", ""))

            content_parts = []
            if 판시사항:
                content_parts.append(f"[판시사항]\n{판시사항}")
            if 판결요지:
                content_parts.append(f"[판결요지]\n{판결요지}")
            if 참조조문:
                content_parts.append(f"[참조조문]\n{참조조문}")

            content = "\n\n".join(content_parts) or "판례 내용 없음"

            return {
                "content": content,
                "metadata": {
                    "source": "국가법령정보 판례",
                    "case_name": p.get("사건명", ""),
                    "case_number": p.get("사건번호", ""),
                    "court": p.get("법원명", ""),
                    "date": p.get("선고일자", ""),
                    "case_type": p.get("사건종류명", ""),
                    "relevance": 1.0,
                },
            }
        except Exception as e:
            print(f"[LawApiClient] 판례 상세 조회 실패 (ID={prec_id}): {e}")
            return None
