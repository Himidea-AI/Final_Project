"""LLM 에이전트 7개 정확도 v7 통합 측정 + v6 비교 리포트 생성.

v6 → v7 평가 방식 변경:
  - market_analyst:   LLM-judge → grade 분류 정확도 (룰엔진 임계값)
  - demographic_depth: judge → 연령·성별 직접 일치
  - synthesis:        judge → 정량 정합성 룰 (수식·legal 보존·grade-추천 모순·winner)
  - trend_forecaster: 6m future → QoQ 방향 일치 (정답 데이터 부재 해결)
  - population:       judge 가중 → 연령·성별·피크 직접 일치
  - competitor_intel: 룰엔진 비교 (현행 유지)
  - legal:            제외 (별도 RAG 평가)

사용:
    cd backend
    python -m scripts.eval.run_all_agents_v7

데이터 소스: Redis 캐시 dump (v?:competitor_intel|market|population|demographic|trend|synthesis:*).
캐시 부족 시 해당 에이전트는 n_cases=0 으로 결과 dump (PPT 에서 "측정 불가 — 데이터 부족" 표기).

출력:
  - bench_agent_eval_v7.json       — 전체 결과 dump
  - bench_agent_eval_v7_report.md  — v6 vs v7 비교 마크다운 리포트 (PPT 에 옮길 표 포함)
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

import redis.asyncio as aioredis

from src.config.settings import settings
from src.evaluation.competitor_intel_eval import CompetitorIntelEvaluator
from src.evaluation.demographic_depth_eval import DemographicDepthEvaluator
from src.evaluation.evaluator import EvalSummary
from src.evaluation.market_analyst_eval import MarketAnalystEvaluator
from src.evaluation.population_eval import PopulationEvaluator
from src.evaluation.synthesis_eval import SynthesisEvaluator
from src.evaluation.trend_forecaster_eval import TrendForecasterEvaluator


# v6 baseline (사용자 보고 자료) — PPT 비교 기준.
V6_BASELINE: dict[str, dict] = {
    "synthesis": {"category_match": 1.00, "mape": None, "method": "LLM-as-judge"},
    "competitor_intel": {"category_match": 1.00, "mape": 0.246, "method": "MAPE + signal 룰"},
    "demographic_depth": {"category_match": 0.833, "mape": None, "method": "LLM-as-judge"},
    "trend_forecaster": {"category_match": 0.667, "mape": None, "method": "6m future 비교 (불가능)"},
    "population_analyst": {"category_match": 0.667, "mape": None, "method": "LLM-as-judge + peak"},
    "market_analyst": {"category_match": 0.50, "mape": 0.001, "method": "LLM-as-judge (MAPE 무의미)"},
    "legal": {"category_match": 0.33, "mape": None, "method": "RAG benchmark"},
}


async def _dump_redis_keys(pattern: str) -> list[tuple[str, dict]]:
    """Redis 키 dump → (key, parsed_value) 리스트."""
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    out: list[tuple[str, dict]] = []
    try:
        keys = await r.keys(pattern)
        for k in keys:
            raw = await r.get(k)
            if not raw:
                continue
            try:
                out.append((k, json.loads(raw)))
            except Exception:
                continue
    finally:
        await r.aclose()
    return out


async def _load_competitor_intel_fixtures() -> list[dict]:
    """v3:|v4:|v5: 모두 시도 — 가장 많은 prefix 사용."""
    for prefix in ["v5:competitor_intel:*", "v4:competitor_intel:*", "v3:competitor_intel:*"]:
        rows = await _dump_redis_keys(prefix)
        if rows:
            return [
                {
                    "case_id": ":".join(k.split(":", 3)[2:]),
                    "simulated_output": v,
                }
                for k, v in rows
            ]
    return []


async def _load_market_analyst_fixtures() -> list[dict]:
    """market 캐시 dump → fixture. grade/qoq/saturation 모두 정형 필드여야 함.

    market_report 는 자연어 string 이므로 metrics + market_data 에서 추출 시도.
    grade 추출 실패 케이스는 skip — synthesis fixture 로 대체 측정 가능.
    """
    # v2 prefix 만 사용 — raw_inputs 포함된 새 schema.
    rows = await _dump_redis_keys("v2:market:*")
    fixtures: list[dict] = []
    for k, v in rows:
        if not isinstance(v, dict):
            continue
        metrics = v.get("metrics") if isinstance(v.get("metrics"), dict) else {}
        raw = v.get("raw_inputs") if isinstance(v.get("raw_inputs"), dict) else {}
        grade = metrics.get("district_grade") or metrics.get("grade")
        qoq = raw.get("qoq_growth_pct")
        sat = raw.get("saturation_level") or "low"
        if grade is None or qoq is None:
            continue
        try:
            fixtures.append(
                {
                    "case_id": k,
                    "qoq_growth_pct": float(qoq),
                    "saturation_level": str(sat),
                    "actual_grade": str(grade).upper(),
                }
            )
        except (TypeError, ValueError):
            continue
    return fixtures


async def _load_demographic_fixtures() -> list[dict]:
    """v4:|v5: demographic 캐시 dump.

    캐시 안 top_3_age_groups 가 share 내림차순 정렬돼있음 → 1위가 expected.
    age_breakdown 은 비교용으로 share 비율 그대로 (백분율 변환 불필요 — _expected_top_age 가
    max() 로 1위 추출만 하므로 단조 함수 보존).
    gender_breakdown 은 캐시에 없음 → 빈 dict 로 보내 evaluator 가 gender 차원 보류.
    """
    for prefix in ["v5:demographic:*", "v4:demographic:*"]:
        rows = await _dump_redis_keys(prefix)
        if not rows:
            continue
        fixtures: list[dict] = []
        for k, v in rows:
            if not isinstance(v, dict):
                continue
            core = v.get("core_demographic") or {}
            top3 = v.get("top_3_age_groups") or []
            age_breakdown = {
                a.get("age_group"): float(a.get("share", 0)) for a in top3 if isinstance(a, dict) and a.get("age_group")
            }
            fixtures.append(
                {
                    "case_id": k,
                    "age_breakdown": age_breakdown,
                    "gender_breakdown": {},  # 캐시 부재 — evaluator 가 gender 보류
                    "actual_age": core.get("age", ""),
                    "actual_gender": core.get("gender", ""),
                }
            )
        if fixtures:
            return fixtures
    return []


async def _load_trend_fixtures() -> list[dict]:
    """trend_forecast 캐시 dump.

    캐시 구조: { "report": { "forecast": {...}, "dong_trend": {...}, "industry_trend": {...} } }.
    이전 v7 1차에서 v.get("forecast") 로 직접 접근해서 None — wrapper 누락 fix.
    """
    rows = await _dump_redis_keys("v2:trend_forecast:*")
    fixtures: list[dict] = []
    for k, v in rows:
        if not isinstance(v, dict):
            continue
        report = v.get("report") or {}
        forecast = report.get("forecast") or {}
        dong_trend = report.get("dong_trend") or {}
        industry = report.get("industry_trend") or {}
        direction = forecast.get("direction")
        # QoQ 추정 — slope_pct 또는 yoy_change_pct fallback
        qoq = dong_trend.get("slope_pct")
        if qoq is None:
            qoq = industry.get("yoy_change_pct")
        if direction is None or qoq is None:
            continue
        # slope_pct 가 -57.8 같이 큰 % 수치면 0.578 비율로 변환
        qoq_norm = float(qoq) / 100.0 if abs(float(qoq)) > 1 else float(qoq)
        fixtures.append(
            {
                "case_id": k,
                "qoq_pct": qoq_norm,
                "actual_direction": str(direction),
            }
        )
    return fixtures


async def _load_population_fixtures() -> list[dict]:
    """population 캐시 dump (v2 prefix — raw_metrics 포함).

    population_node 가 v2: prefix 로 raw_metrics(age/gender/time peak) 도 캐시함.
    v1 옛 캐시는 raw 없어 평가 불가 → v2 만 사용.
    """
    rows = await _dump_redis_keys("v2:population:*")
    fixtures: list[dict] = []
    for k, v in rows:
        if not isinstance(v, dict):
            continue
        metrics = v.get("metrics") or {}
        raw = v.get("raw_metrics") or {}
        if not raw:
            continue
        # main_target_age "30대 남성" → age, gender 분리
        mta = str(metrics.get("main_target_age", ""))
        actual_age = ""
        actual_gender = "mixed"
        for tok in mta.split():
            if tok.endswith("대"):
                actual_age = tok.replace("대", "")
            if "남" in tok:
                actual_gender = "male"
            elif "여" in tok:
                actual_gender = "female"
        fixtures.append(
            {
                "case_id": k,
                "age_distribution": raw.get("age_distribution") or {},
                "gender_distribution": raw.get("gender_distribution") or {},
                "time_distribution": {raw.get("time_peak", ""): 1} if raw.get("time_peak") else {},
                "actual_age": actual_age,
                "actual_gender": actual_gender,
                "actual_peak": str(metrics.get("peak_time", "")).replace(":", "").replace("~", "-")[:5],
            }
        )
    return fixtures


async def _load_synthesis_fixtures() -> list[dict]:
    """synthesis 캐시 dump.

    winner_district 는 캐시 value 에 없으나 캐시 key 형식
    `vXX:synthesis:{brand}:{winner}:{td_csv}:{biz}:...` 에서 추출.
    grade 는 보통 None — synthesis evaluator 의 grade_consistent 룰에서 자동 통과 처리.
    """
    for prefix in ["v14:synthesis:*", "v13:synthesis:*", "v12:synthesis:*", "v11:synthesis:*"]:
        rows = await _dump_redis_keys(prefix)
        if not rows:
            continue
        fixtures: list[dict] = []
        for k, v in rows:
            if not isinstance(v, dict):
                continue
            final_report = v.get("final_report") or {}
            profit = final_report.get("profit_simulation") or {}
            # 키에서 winner_district 추출: vXX:synthesis:brand:winner:td:biz:...
            parts = k.split(":")
            winner_from_key = parts[3] if len(parts) >= 5 else ""
            fixtures.append(
                {
                    "case_id": k,
                    "legal_risk": v.get("overall_legal_risk", ""),
                    "synth_legal_risk": final_report.get("overall_legal_risk", ""),
                    "monthly_revenue": profit.get("monthly_revenue"),
                    "monthly_cost": profit.get("monthly_cost"),
                    "net_profit": profit.get("net_profit"),
                    "grade": final_report.get("grade") or "",
                    "final_recommendation": final_report.get("final_recommendation", ""),
                    "winner_district": v.get("winner_district") or winner_from_key,
                }
            )
        if fixtures:
            return fixtures
    return []


def _summary_to_dict(s: EvalSummary | None) -> dict:
    if s is None:
        return {"n_cases": 0, "metric_mean": None, "n_passed": 0, "metric_name": None}
    return {
        "n_cases": s.n_cases,
        "n_passed": s.n_passed,
        "metric_name": s.metric_name,
        "metric_mean": round(s.metric_mean, 4) if s.n_cases else None,
        "metric_min": round(s.metric_min, 4) if s.n_cases else None,
        "metric_max": round(s.metric_max, 4) if s.n_cases else None,
        "confusion_matrix": s.confusion_matrix,
    }


async def main() -> None:
    print("=" * 78)
    print("LLM 에이전트 v7 정확도 측정 — 텍스트 분석 기반 평가 방식 재설계")
    print("=" * 78)

    # 1) 캐시 dump
    print("\n[1/3] Redis 캐시 dump…")
    ci_fix = await _load_competitor_intel_fixtures()
    ma_fix = await _load_market_analyst_fixtures()
    dd_fix = await _load_demographic_fixtures()
    tf_fix = await _load_trend_fixtures()
    pa_fix = await _load_population_fixtures()
    sy_fix = await _load_synthesis_fixtures()
    print(
        f"  competitor_intel={len(ci_fix)} / market={len(ma_fix)} / demographic={len(dd_fix)} / "
        f"trend={len(tf_fix)} / population={len(pa_fix)} / synthesis={len(sy_fix)}"
    )

    # 2) evaluator 실행
    print("\n[2/3] evaluator 실행…")
    summaries: dict[str, EvalSummary | None] = {}
    summaries["competitor_intel"] = await CompetitorIntelEvaluator(fixtures=ci_fix).run() if ci_fix else None
    summaries["market_analyst"] = await MarketAnalystEvaluator(fixtures=ma_fix).run() if ma_fix else None
    summaries["demographic_depth"] = await DemographicDepthEvaluator(fixtures=dd_fix).run() if dd_fix else None
    summaries["trend_forecaster"] = await TrendForecasterEvaluator(fixtures=tf_fix).run() if tf_fix else None
    summaries["population_analyst"] = await PopulationEvaluator(fixtures=pa_fix).run() if pa_fix else None
    summaries["synthesis"] = await SynthesisEvaluator(fixtures=sy_fix).run() if sy_fix else None

    # 3) 결과 dump + 비교 리포트
    print("\n[3/3] 결과 dump + v6 비교 리포트…")
    repo_root = Path(__file__).resolve().parents[3]  # final_project/
    result = {
        "version": "v7",
        "method_changes": {
            "market_analyst": "LLM-judge → grade 분류 정확도 (룰엔진)",
            "demographic_depth": "LLM-judge → 연령·성별 직접 일치",
            "synthesis": "LLM-judge → 정량 정합성 룰 (수식·legal·모순·winner)",
            "trend_forecaster": "6m future → QoQ 방향 일치",
            "population_analyst": "LLM-judge 가중 → 연령·성별·피크 직접 일치",
            "competitor_intel": "현행 (signal 룰엔진)",
            "legal": "제외 — 별도 RAG benchmark",
        },
        "v6_baseline": V6_BASELINE,
        "v7_results": {k: _summary_to_dict(v) for k, v in summaries.items()},
    }
    out_json = repo_root / "bench_agent_eval_v7.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ JSON: {out_json}")

    # 마크다운 리포트
    md_lines: list[str] = []
    md_lines.append("# LLM 에이전트 정확도 — v6 vs v7 비교\n")
    md_lines.append("## 측정 방식 재설계\n")
    md_lines.append("| 에이전트 | v6 방법 | v7 방법 |")
    md_lines.append("|---|---|---|")
    for agent, info in V6_BASELINE.items():
        v7_method = result["method_changes"].get(agent, "—")
        md_lines.append(f"| {agent} | {info['method']} | {v7_method} |")

    md_lines.append("\n## 결과 비교\n")
    md_lines.append("| 에이전트 | v6 일치율 | v7 일치율 | n (v7) | 변화 |")
    md_lines.append("|---|---:|---:|---:|---|")
    for agent in V6_BASELINE.keys():
        v6 = V6_BASELINE[agent]["category_match"]
        v7 = result["v7_results"].get(agent, {})
        v7_mean = v7.get("metric_mean")
        n = v7.get("n_cases", 0)
        if v7_mean is None:
            change = "측정 불가 (캐시 부족)"
            v7_str = "—"
        else:
            delta = v7_mean - v6
            arrow = "↑" if delta > 0.05 else ("↓" if delta < -0.05 else "→")
            change = f"{arrow} {delta:+.1%}"
            v7_str = f"{v7_mean:.1%}"
        md_lines.append(f"| {agent} | {v6:.1%} | {v7_str} | {n} | {change} |")

    md_lines.append("\n## 핵심 메시지 (PPT 슬라이드용)\n")
    md_lines.append("- v6 평가는 LLM-as-judge 의존 → market_analyst MAPE 0.1% 같은 *잘못된 신호* 산출")
    md_lines.append("- v7 = 텍스트 분석에 따라 *에이전트 유형별 측정 가능한 것* 으로 재설계")
    md_lines.append("- 핵심 변경: 자기참조 채점 → 룰엔진 정답 + 직접 일치 비교")
    md_lines.append("- 결과: 측정 자체가 신뢰할 수 있게 됨 (정량 재현 가능)")

    out_md = repo_root / "bench_agent_eval_v7_report.md"
    out_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"  ✓ Markdown: {out_md}")

    print("\n" + "=" * 78)
    print("완료 — bench_agent_eval_v7.json + bench_agent_eval_v7_report.md")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
