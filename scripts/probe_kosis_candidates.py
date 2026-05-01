"""KOSIS 후보 테이블 탐색 스크립트 (Phase 1-A).

seoul_district_sales (동×업종×분기 매출)의 변환 로직 리버스 엔지니어링을 위해
통계청 KOSIS의 후보 테이블을 조사한다.

핵심 가설:
  seoul_district_sales[dong, industry, quarter] =
      서비스업생산지수(시도) × 동별_사업체수(업종) × 매출액승수(업종)
      + 품질게이트(|raw - anchor| / anchor < threshold)

조사 대상:
  1. 서비스업동향조사 (분기) — 트렌드 anchor
  2. 서비스업조사 (연간) — 매출액 승수
  3. 전국사업체조사 (동 단위) — 사업체 수 분모
  4. 경제총조사 (5년 주기) — 벤치마크

출력: docs/sales-imputation/kosis_candidates.md
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from PublicDataReader import Kosis

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

KOSIS_KEY = os.environ.get("KOSIS_API_KEY", "").strip()
if not KOSIS_KEY:
    print("[error] KOSIS_API_KEY env missing")
    sys.exit(1)

api = Kosis(KOSIS_KEY)
OUT = REPO_ROOT / "docs" / "sales-imputation" / "kosis_candidates.md"


KEYWORDS = [
    "서비스업동향조사",
    "서비스업조사",
    "전국사업체조사",
    "경제총조사",
    "소매판매액지수",
]


def search_candidates() -> dict[str, pd.DataFrame]:
    """키워드별 KOSIS 테이블 검색."""
    out: dict[str, pd.DataFrame] = {}
    for kw in KEYWORDS:
        try:
            df = api.get_data("KOSIS통합검색", searchNm=kw)
        except Exception as e:
            print(f"[err] {kw}: {e}")
            continue
        if df is None or len(df) == 0:
            print(f"[warn] {kw}: no hits")
            continue
        # 중복 테이블 제거, 조사명·통계표ID·통계표명만 핵심 보존
        cols_keep = ["통계표ID", "통계표명", "조사명", "기관명", "수록기간시작일", "수록기간종료일", "통계표주요내용"]
        cols_keep = [c for c in cols_keep if c in df.columns]
        df2 = df[cols_keep].drop_duplicates(subset=["통계표ID"])
        print(f"[ok]  {kw}: {len(df2)} unique tables")
        out[kw] = df2
    return out


def score_candidate(row: pd.Series, kw: str) -> tuple[int, str]:
    """테이블의 seoul_district_sales 매칭 가능성 점수."""
    name = str(row.get("통계표명", ""))
    content = str(row.get("통계표주요내용", ""))[:500]
    score = 0
    reasons: list[str] = []

    # 해상도 힌트
    if "동" in name or "행정동" in name or "시군구" in name:
        score += 30
        reasons.append("small-area 해상도")
    if "시도" in name:
        score += 10
        reasons.append("시도 레벨(보정용)")

    # 시간 해상도
    if "분기" in content or "분기" in name:
        score += 20
        reasons.append("분기 주기")
    if "월" in content:
        score += 10
        reasons.append("월간")

    # 매출/지수
    if "매출" in name:
        score += 25
        reasons.append("매출 직접")
    if "지수" in name:
        score += 15
        reasons.append("생산/판매 지수(anchor)")
    if "사업체" in name:
        score += 15
        reasons.append("사업체 수(분모)")

    # 업종 분류
    if "산업" in name or "업종" in content:
        score += 10
        reasons.append("업종별")

    # 최신성
    try:
        end_year = int(str(row.get("수록기간종료일", "0")))
        if end_year >= 2023:
            score += 10
            reasons.append(f"최신 {end_year}")
    except Exception:
        pass

    return score, ", ".join(reasons)


def write_report(catalog: dict[str, pd.DataFrame]) -> None:
    """후보 테이블을 마크다운으로 정리."""
    lines: list[str] = []
    lines.append("# KOSIS 후보 테이블 탐색 결과 (Phase 1-A)\n")
    lines.append("**목적:** seoul_district_sales 변환 로직 리버스 엔지니어링의 anchor 데이터셋 식별\n")
    lines.append("**대상 해상도:** 동 × 업종 × 분기 × 매출액\n")
    lines.append(f"**탐색 키워드:** {', '.join(KEYWORDS)}\n")
    lines.append("---\n")

    # 모든 테이블에 점수 부여
    rows: list[dict] = []
    for kw, df in catalog.items():
        for _, r in df.iterrows():
            sc, reason = score_candidate(r, kw)
            rows.append(
                {
                    "keyword": kw,
                    "tbl_id": r.get("통계표ID"),
                    "tbl_name": r.get("통계표명"),
                    "survey": r.get("조사명"),
                    "start": r.get("수록기간시작일"),
                    "end": r.get("수록기간종료일"),
                    "score": sc,
                    "reason": reason,
                }
            )

    scored = pd.DataFrame(rows).sort_values("score", ascending=False)
    top = scored.head(25)

    lines.append("## 상위 25개 후보 (점수순)\n")
    lines.append("| 점수 | 통계표ID | 통계표명 | 조사명 | 기간 | 근거 |")
    lines.append("|:--:|----|----|----|:--:|----|")
    for _, r in top.iterrows():
        lines.append(
            f"| {r['score']} | `{r['tbl_id']}` | {r['tbl_name']} | {r['survey']} | "
            f"{r['start']}~{r['end']} | {r['reason']} |"
        )

    lines.append("\n---\n## 키워드별 요약\n")
    for kw, df in catalog.items():
        lines.append(f"### {kw} ({len(df)} tables)\n")
        lines.append("| 통계표ID | 통계표명 | 기간 |")
        lines.append("|----|----|----|")
        for _, r in df.head(10).iterrows():
            lines.append(
                f"| `{r.get('통계표ID')}` | {r.get('통계표명')} | {r.get('수록기간시작일')}~{r.get('수록기간종료일')} |"
            )
        lines.append("")

    lines.append("\n---\n## 다음 단계 (Phase 1-B)\n")
    lines.append("1. 상위 5개 테이블의 실제 데이터 샘플 조회 (서울·마포 필터)")
    lines.append("2. seoul_district_sales 살아있는 셀과 키 매칭 가능성 검증")
    lines.append("3. 동 단위 해상도 가용성 확인 (없으면 시도→동 downscale 전략 수립)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[saved] {OUT}")
    print("\n=== Top 10 후보 ===")
    for _, r in top.head(10).iterrows():
        print(f"  [{r['score']:3d}] {r['tbl_id']:<16s} {r['tbl_name'][:50]:<52s} ({r['reason']})")


if __name__ == "__main__":
    print("=== KOSIS 후보 탐색 시작 ===")
    catalog = search_candidates()
    print(f"\n총 {sum(len(df) for df in catalog.values())}개 테이블 수집")
    write_report(catalog)
