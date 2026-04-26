"""LangGraph state 의 vacancy_spots → ABM PSE 평가 + 순위 산출.

목적:
    district_ranking 노드 결과(`state["vacancy_spots"]`) 중 top_n 공실에 대해
    ABM 시뮬을 통한 일평균 방문/매출 산출. 순위 기반 추천 가능.

설계 원칙:
    - LangGraph 동기 노드 X (ABM 시뮬 = 5~10분 → HTTP timeout 위험)
    - 본 모듈은 별도 호출 (API 엔드포인트 또는 백그라운드 작업) 가정
    - vacancy_pse 의 PSE N=5 표준 활용

사용:
    from src.services.vacancy_evaluation_service import evaluate_top_vacancies
    rankings = evaluate_top_vacancies(
        vacancy_spots=state["vacancy_spots"],
        category="카페",
        top_n=5,
        n_seeds=5,
    )
    # rankings = [{spot, pse_summary, score, narrative}, ...]
    # 정렬: visits_per_day mean 내림차순
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_vacancy_spot(raw: dict[str, Any]) -> dict[str, Any]:
    """LangGraph district_ranking 의 vacancy_spot → vacancy_pse 호환 dict 변환.

    district_ranking 형식: {id, lat, lon, dong_name, listing_count}
    vacancy_pse 형식:      {dong, lat, lon, ...}
    """
    return {
        "id": raw.get("id"),
        "dong": raw.get("dong_name") or raw.get("dong"),
        "lat": raw.get("lat"),
        "lon": raw.get("lon"),
        "listing_count": raw.get("listing_count"),
        # 원본 보존
        "_raw": raw,
    }


def evaluate_top_vacancies(
    vacancy_spots: list[dict[str, Any]],
    category: str,
    top_n: int = 5,
    n_seeds: int = 5,
    days: int = 1,
    with_cannibalization: bool = False,
    popularity_boost: float | None = None,
    pre_filter_score: list[float] | None = None,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """여러 공실 PSE 평가 + 일평균 방문 내림차순 순위.

    Args:
        vacancy_spots: district_ranking 노드 출력 (`state["vacancy_spots"]`)
        category: 사용자 선택 업종 ("카페" 등)
        top_n: 평가할 상위 공실 수 (시간 절약 — 모든 spot 평가하면 시간 폭주)
        n_seeds: PSE N (기본 5, 권장 ≥ 3)
        days: 시뮬 일수
        with_cannibalization: 카니발 측정 (시간 2배)
        popularity_boost: vacancy_inject default 사용 (None) 또는 명시
        pre_filter_score: vacancy_spots 와 같은 길이 score 리스트 (district_ranking score)
                          제공 시 score 내림차순 top_n 만 평가
        verbose: 진행 로그

    Returns:
        [
            {
                "rank": 1,
                "spot": {dong, lat, lon, id, listing_count},
                "narrative": "서교동 카페 신규 매장 일평균 8.3 ± 0.7 명...",
                "pse_summary": {visits_per_day, revenue_per_day, ...},
                "score": float (visits_per_day mean — 정렬용),
            },
            ...
        ]
    """
    from src.simulation.vacancy_inject import DEFAULT_POPULARITY_BOOST
    from src.simulation.vacancy_pse import evaluate_vacancy_pse

    if not vacancy_spots:
        return []

    # 정규화
    normalized = [_normalize_vacancy_spot(s) for s in vacancy_spots]
    valid = [s for s in normalized if s["dong"] and s["lat"] is not None and s["lon"] is not None]
    if len(valid) < len(normalized):
        logger.warning(f"vacancy_spots {len(normalized)} 중 {len(valid)}개만 유효 (dong/lat/lon 누락 제외)")

    # Pre-filter — score 제공 시 상위만
    if pre_filter_score and len(pre_filter_score) == len(valid):
        valid = [s for _, s in sorted(zip(pre_filter_score, valid), key=lambda x: -x[0])]
    valid = valid[:top_n]

    if verbose:
        logger.info(f"[vacancy_evaluation] {len(valid)} 공실 PSE N={n_seeds} 평가 시작 ({category})")

    pb = popularity_boost if popularity_boost is not None else DEFAULT_POPULARITY_BOOST

    # API/배치 호출은 mock LLM 강제 (비용 안정 + 키 의존성 제거)
    from src.simulation.config import ModelConfig

    mock_cfg = ModelConfig()
    mock_cfg.tier_s_provider = "mock"
    mock_cfg.tier_a_provider = "mock"

    rankings: list[dict[str, Any]] = []
    for i, spot in enumerate(valid):
        if verbose:
            logger.info(f"[vacancy_evaluation] {i + 1}/{len(valid)} — {spot['dong']} 평가 중...")
        try:
            pse_kwargs = {
                "vacancy_spot": {"dong": spot["dong"], "lat": spot["lat"], "lon": spot["lon"]},
                "category": category,
                "n_seeds": n_seeds,
                "days": days,
                "with_cannibalization": with_cannibalization,
                "popularity_boost": pb,
                "cfg": mock_cfg,
                "verbose": False,
            }
            result = evaluate_vacancy_pse(**pse_kwargs)
            rankings.append(
                {
                    "spot": spot,
                    "narrative": result["narrative"],
                    "pse_summary": result["pse_summary"],
                    "score": result["pse_summary"]["visits_per_day"]["mean"],
                }
            )
        except Exception as e:
            logger.exception(f"[vacancy_evaluation] {spot['dong']} 평가 실패: {e}")

    # 일평균 방문 내림차순 정렬
    rankings.sort(key=lambda r: -r["score"])
    for rank, r in enumerate(rankings, 1):
        r["rank"] = rank
    return rankings


def format_rankings_text(rankings: list[dict[str, Any]]) -> str:
    """순위 결과를 사람이 읽기 쉬운 텍스트로."""
    if not rankings:
        return "평가 가능한 공실 없음."
    lines = ["=== Vacancy 평가 순위 (PSE 기반) ==="]
    for r in rankings:
        spot = r["spot"]
        s = r["pse_summary"]
        v = s["visits_per_day"]
        rev = s["revenue_per_day"]
        ratio = s["vacancy_vs_avg_visits_ratio"]
        lines.append(
            f"\n#{r['rank']}  {spot['dong']}  (id={spot.get('id')}, lat={spot['lat']:.4f}, lon={spot['lon']:.4f})"
        )
        lines.append(
            f"  visits/day  : {v['mean']:5.1f} ± {v['ci95']:4.1f} (95% CI, range [{v['min']:.0f}, {v['max']:.0f}])"
        )
        lines.append(f"  revenue/day : {rev['mean'] / 10000:5.1f} ± {rev['ci95'] / 10000:4.1f} 만원")
        lines.append(f"  동 평균 대비: {ratio['mean']:5.1f} ± {ratio['ci95']:4.1f} 배")
        if "cannibalization_pct" in s:
            cann = s["cannibalization_pct"]
            lines.append(f"  카니발 %    : {cann['mean']:+5.1f} ± {cann['ci95']:5.1f}% (- = 시너지)")
    return "\n".join(lines)
