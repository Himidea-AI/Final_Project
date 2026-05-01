# validation/sensitivity_v4_abm.py
"""Phase 4: imputed v4 사용/미사용 ABM 시뮬 비교."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

# world_loader.py 의 module-level 'from src.database.sync_engine' import 가
# repo root 실행 시 ModuleNotFoundError 를 발생시키는 pre-existing issue.
# backend/ 를 sys.path 에 추가해 src.database 를 찾을 수 있도록 한다.
_backend_path = str(Path(__file__).resolve().parents[1] / "backend")
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_MD = REPO_ROOT / "docs" / "sales-imputation" / "sensitivity_v4_report.md"


def _get_engine():
    return create_engine(os.environ["POSTGRES_URL"])


THRESHOLD_SENSITIVITY = 0.08
THRESHOLD_EXTRAP_IMPACT = 0.07


def collect_popularity_via_loader(engine):
    """world_loader._load_dong_industry_weight() 호출 결과."""
    from backend.src.simulation.world_loader import _load_dong_industry_weight

    return _load_dong_industry_weight(engine)


def main():
    print("=== Phase 4: Sensitivity v4 ABM ===")
    # WARNING: 이 스크립트는 v4 테이블을 일시적으로 비우고 다시 채운다.
    # 운영 DB 에서 실행 시 다른 세션이 그 짧은 순간 popularity=0 을 볼 위험.
    # 스테이징 DB 에서만 실행해야 한다.
    db_url = os.environ.get("POSTGRES_URL", "")
    if "prod" in db_url.lower() and not os.environ.get("ALLOW_PROD_SENSITIVITY"):
        raise RuntimeError(
            "sensitivity_v4_abm 은 운영 DB 에서 실행 금지 (DELETE 중 popularity=0 노출 위험). "
            "스테이징 DB 사용 또는 ALLOW_PROD_SENSITIVITY=1 환경변수 설정."
        )
    print(f"[DB] {db_url[:30]}... (운영 아닌지 확인됨)")

    engine = _get_engine()

    # 1) v4 사용 (현 상태)
    print("[1/2] v4 적용 popularity ...")
    pop_v4 = collect_popularity_via_loader(engine)
    print(f"  cells: {len(pop_v4)}, mean: {np.mean(list(pop_v4.values())):.3f}")

    # 2) v4 비움 — 임시
    print("[2/2] v4 미적용 popularity (DELETE 임시) ...")
    with engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE v4_backup_sens AS SELECT * FROM seoul_district_sales_imputed_v4"))
        conn.execute(text("DELETE FROM seoul_district_sales_imputed_v4"))
    try:
        pop_baseline = collect_popularity_via_loader(engine)
        print(f"  cells: {len(pop_baseline)}, mean: {np.mean(list(pop_baseline.values())):.3f}")
    finally:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO seoul_district_sales_imputed_v4 SELECT * FROM v4_backup_sens"))

    # 3) 비교
    common_keys = set(pop_v4.keys()) & set(pop_baseline.keys())
    new_keys_v4 = set(pop_v4.keys()) - set(pop_baseline.keys())
    print("\n[비교]")
    print(f"  common cells: {len(common_keys)}")
    print(f"  v4 신규 cells (결측 보강): {len(new_keys_v4)}")

    diffs = []
    for k in common_keys:
        diffs.append(abs(pop_v4[k] - pop_baseline[k]) / max(pop_baseline[k], 0.01))
    sensitivity = float(np.mean(diffs)) if diffs else 0.0
    print(f"  popularity 변화 mean: {sensitivity * 100:.2f}%")

    # 합격 판정
    pass_4_1 = sensitivity >= THRESHOLD_SENSITIVITY
    coverage_gain = len(new_keys_v4)

    # MD 보고서
    lines = ["# Sensitivity v4 ABM Report\n"]
    lines.append(
        f"**합격선 4-1 (sensitivity ≥ {THRESHOLD_SENSITIVITY * 100:.0f}%):** {'✅' if pass_4_1 else '❌'} {sensitivity * 100:.2f}%"
    )
    lines.append(f"**v4 신규 popularity 셀 (결측 보강 효과):** {coverage_gain}")
    lines.append("\n## 결과")
    lines.append(f"- v4 적용 popularity 평균: {np.mean(list(pop_v4.values())):.3f} ({len(pop_v4)} cells)")
    lines.append(f"- baseline popularity 평균: {np.mean(list(pop_baseline.values())):.3f} ({len(pop_baseline)} cells)")
    lines.append(f"- 공통 cell 의 popularity 평균 변화: {sensitivity * 100:.2f}%")
    lines.append("\n## 해석")
    if pass_4_1:
        lines.append(
            f"v4 도입이 ABM popularity 분포에 의미 있는 영향 ({sensitivity * 100:.1f}% > {THRESHOLD_SENSITIVITY * 100:.0f}%) — sprint 가치 입증."
        )
    else:
        lines.append(
            f"v4 도입 영향이 미미 ({sensitivity * 100:.1f}% < {THRESHOLD_SENSITIVITY * 100:.0f}%) — 정직 명시."
        )
    if coverage_gain > 0:
        lines.append(
            f"\n결측 보강으로 신규 {coverage_gain} (dong, category) 조합에 popularity 부여 — ABM 시뮬 왜곡 감소."
        )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[saved] {OUT_MD}")


if __name__ == "__main__":
    for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

    main()
