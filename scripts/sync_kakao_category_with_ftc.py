"""kakao_store.category ↔ ftc_brand_franchise.indutyMlsfcNm 정합 스크립트.

목적:
    FTC 가맹사업 정보공개서의 brand 카테고리를 source-of-truth 로 삼아
    kakao_store.category 를 일괄 보정. brand_mapping_resolver 의 alias 확장
    로직을 그대로 사용해 한글/영문/괄호 표기 변형을 모두 매칭한다.

알고리즘:
    1. ftc_brand_franchise 에서 (brandNm, indutyMlsfcNm) 별 max frcsCnt 로 정렬.
    2. brand 별로 BRAND_ALIASES + extra_short alias (괄호/숫자 제거) 확장.
    3. kakao_store.brand_name ILIKE any alias AND category != target 인 row 수집.
    4. kakao_id → target_category dict 구축. frcsCnt 큰 brand 가 먼저 처리되어
       동일 kakao_id 가 여러 brand 에 매칭되면 더 큰 brand 의 category 채택.
    5. dry_run=True 면 카운트만 출력, False 면 UPDATE 실행.

용법:
    python -m scripts.sync_kakao_category_with_ftc           # dry-run
    python -m scripts.sync_kakao_category_with_ftc --commit  # 실제 UPDATE

audit:
    실행 전 kakao_store_backup_20260507_yyyymmdd.csv 자동 생성.
"""

from __future__ import annotations

import csv
import io
import re
import sys
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# repo root → backend 경로 추가
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))

from src.config.settings import settings  # noqa: E402
from src.services.brand_mapping_resolver import BRAND_ALIASES, BRAND_EXCLUDE  # noqa: E402

# FTC indutyMlsfcNm → kakao_store.category canonical 매핑
FTC_TO_KAKAO: dict[str, str] = {
    "한식": "한식음식점",
    "중식": "중식음식점",
    "일식": "일식음식점",
    "서양식": "양식음식점",
    "제과제빵": "제과점",
    "패스트푸드": "패스트푸드점",
    "피자": "패스트푸드점",  # 정책상 흡수 (BUSINESS_TYPE_MAPPING 와 정합)
    "치킨": "치킨전문점",
    "분식": "분식전문점",
    "주점": "호프-간이주점",
    "커피": "커피-음료",
    "음료 (커피 외)": "커피-음료",
    "아이스크림/빙수": "커피-음료",
    "편의점": "편의점",
}


def expand_aliases(brand: str) -> list[str]:
    """brand_mapping_resolver.get_all_mapo_stores_by_brand 의 alias 생성 로직 재현."""
    # 1) BRAND_ALIASES 정방향 + 역방향
    canonical = brand
    for std, alts in BRAND_ALIASES.items():
        if brand == std or brand in alts:
            canonical = std
            break
    aliases_raw = list(BRAND_ALIASES.get(canonical, [])) + [canonical, brand]

    extra_short: list[str] = []
    for a in aliases_raw:
        if not a:
            continue
        # 끝 숫자 제거
        s1 = re.sub(r"\d+$", "", a).strip()
        if s1 and s1 != a:
            extra_short.append(s1)
        # 괄호 제거
        s2 = re.sub(r"\s*\([^)]*\)\s*$", "", a).strip()
        if s2 and s2 != a:
            extra_short.append(s2)
        # 괄호 안 영문 추출
        m = re.search(r"\(([A-Za-z0-9][A-Za-z0-9 &-]*)\)", a)
        if m:
            paren = m.group(1).strip()
            if paren:
                extra_short.append(paren)
        # & 이후 제거
        s4 = re.sub(r"\s*&.*$", "", a).strip()
        if s4 and s4 != a:
            extra_short.append(s4)
    return sorted(set(aliases_raw + extra_short))


def main(commit: bool = False) -> None:
    e = sa.create_engine(settings.postgres_url)

    print("=" * 70)
    print(f"sync_kakao_category_with_ftc — {'COMMIT' if commit else 'DRY-RUN'}")
    print("=" * 70)

    with e.connect() as c:
        # FTC brand 별 indutyMlsfcNm + max frcsCnt
        ftc_rows = c.execute(
            sa.text(
                """
                SELECT "brandNm", "indutyMlsfcNm", MAX("frcsCnt") AS cnt
                  FROM ftc_brand_franchise
                 WHERE "brandNm" IS NOT NULL
                   AND "indutyMlsfcNm" IS NOT NULL
                 GROUP BY "brandNm", "indutyMlsfcNm"
                HAVING MAX("frcsCnt") > 0
                 ORDER BY cnt DESC
                """
            )
        ).fetchall()

        print(f"FTC brand 후보: {len(ftc_rows)}개\n")

        # kakao_id → (target_cat, source_brand, source_cnt)
        mapping: dict[str, tuple[str, str, int]] = {}
        per_brand_stats: dict[str, int] = {}

        for r in ftc_rows:
            m = r._mapping
            ftc_brand = m["brandNm"]
            ftc_cat = m["indutyMlsfcNm"]
            cnt = m["cnt"]
            target = FTC_TO_KAKAO.get(ftc_cat)
            if not target:
                continue
            aliases = expand_aliases(ftc_brand)
            if not aliases:
                continue
            # 짧은 alias (3자 미만) 는 ILIKE false positive 위험 → 정확 매칭만 사용
            cond_parts: list[str] = []
            params: dict = {"target": target}
            for i, a in enumerate(aliases):
                if len(a) < 3:
                    cond_parts.append(f"brand_name = :a{i}")
                    params[f"a{i}"] = a
                else:
                    cond_parts.append(f"brand_name ILIKE :a{i}")
                    params[f"a{i}"] = f"%{a}%"
            conditions = " OR ".join(cond_parts)
            sql = sa.text(
                f"""
                SELECT kakao_id, brand_name, category
                  FROM kakao_store
                 WHERE ({conditions})
                   AND category != :target
                """
            )
            rows = c.execute(sql, params).fetchall()
            # BRAND_EXCLUDE — 빽다방 → "빵연구소" 제외 등 false positive 방지
            excludes = BRAND_EXCLUDE.get(ftc_brand, [])
            added = 0
            for kr in rows:
                kakao_id = kr._mapping["kakao_id"]
                kakao_brand = kr._mapping["brand_name"] or ""
                if any(ex in kakao_brand for ex in excludes):
                    continue
                # 더 큰 frcsCnt brand 가 먼저 처리됨 — 이미 있으면 skip (top brand 우선)
                if kakao_id in mapping:
                    continue
                mapping[kakao_id] = (target, ftc_brand, cnt)
                added += 1
            if added > 0:
                per_brand_stats[ftc_brand] = added

        print(f"UPDATE 대상 row: {len(mapping)}\n")
        print("=== 영향 받는 brand top 30 (변경 row 수) ===")
        for b, n in sorted(per_brand_stats.items(), key=lambda x: -x[1])[:30]:
            target, _, _ = next(iter([v for k, v in mapping.items() if v[1] == b]), ("?", "", 0))
            print(f"  {b:30s} → {target:18s} {n:4d} row")

        if not commit:
            print("\n[DRY-RUN] UPDATE 미실행. --commit 으로 실제 적용.")
            return

        # ── COMMIT 모드: 백업 CSV 생성 후 UPDATE ──
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = _REPO / f"kakao_store_category_backup_{ts}.csv"
        kakao_ids = list(mapping.keys())
        # 백업 — 변경될 row 만 (kakao_id, brand_name, category before)
        with backup_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["kakao_id", "brand_name", "category_before", "category_after", "source_brand"])
            for kid in kakao_ids:
                rb = c.execute(
                    sa.text("SELECT brand_name, category FROM kakao_store WHERE kakao_id = :k"),
                    {"k": kid},
                ).first()
                if rb:
                    target, src, _ = mapping[kid]
                    w.writerow([kid, rb._mapping["brand_name"], rb._mapping["category"], target, src])
        print(f"\n백업 CSV: {backup_path}")

        # 실행 — bulk UPDATE
        with e.begin() as txc:
            updated = 0
            for kid, (target, _, _) in mapping.items():
                txc.execute(
                    sa.text("UPDATE kakao_store SET category = :t WHERE kakao_id = :k"),
                    {"t": target, "k": kid},
                )
                updated += 1
        print(f"UPDATE 완료: {updated} row")


if __name__ == "__main__":
    commit = "--commit" in sys.argv
    main(commit=commit)
