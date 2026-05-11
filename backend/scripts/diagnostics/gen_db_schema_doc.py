"""DB 실측 → docs/database/db-schema.md 자동 생성.

information_schema + pg_catalog 쿼리해서 테이블·컬럼·PK·FK·인덱스·row 수 dump.
ORM 모델(`backend/src/database/models.py`) 과 cross-check 후 markdown 출력.

Usage:
    cd backend && python scripts/diagnostics/gen_db_schema_doc.py

출력 파일: docs/database/db-schema.md (기존 덮어씀)
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.settings import settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
MODELS_PY = ROOT / "backend" / "src" / "database" / "models.py"
OUT_MD = ROOT / "docs" / "database" / "db-schema.md"


def _orm_tablenames() -> set[str]:
    """models.py 에서 __tablename__ 추출."""
    text = MODELS_PY.read_text(encoding="utf-8")
    return set(re.findall(r'__tablename__\s*=\s*"([^"]+)"', text))


def _fetch_schema(conn: sa.engine.Connection) -> dict:
    """DB 실측 dump."""
    out: dict = {"tables": [], "columns": defaultdict(list), "pks": defaultdict(list), "fks": [], "rows": {}}

    out["tables"] = [
        r[0]
        for r in conn.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_type='BASE TABLE' "
                "ORDER BY table_name"
            )
        ).fetchall()
    ]

    for r in conn.execute(
        sa.text(
            "SELECT table_name, column_name, data_type, is_nullable, character_maximum_length, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema='public' "
            "ORDER BY table_name, ordinal_position"
        )
    ).fetchall():
        out["columns"][r[0]].append(
            {"name": r[1], "type": r[2], "nullable": r[3] == "YES", "len": r[4], "default": r[5]}
        )

    for r in conn.execute(
        sa.text(
            "SELECT tc.table_name, kc.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kc "
            "  ON tc.constraint_name = kc.constraint_name AND tc.table_schema = kc.table_schema "
            "WHERE tc.constraint_type='PRIMARY KEY' AND tc.table_schema='public' "
            "ORDER BY tc.table_name, kc.ordinal_position"
        )
    ).fetchall():
        out["pks"][r[0]].append(r[1])

    for r in conn.execute(
        sa.text(
            "SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name "
            "JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name=tc.constraint_name "
            "WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public' "
            "ORDER BY tc.table_name"
        )
    ).fetchall():
        out["fks"].append({"table": r[0], "column": r[1], "ref_table": r[2], "ref_column": r[3]})

    for r in conn.execute(
        sa.text("SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE schemaname='public' ORDER BY relname")
    ).fetchall():
        out["rows"][r[0]] = r[1]

    return out


def _domain_of(table: str) -> str:
    """테이블명 → 도메인 분류."""
    if table.startswith("seoul_signgu"):
        return "서울 시군구"
    if table.startswith("seoul_trdar"):
        return "서울 상권"
    if table.startswith("seoul_adstrd"):
        return "서울 행정동"
    if table.startswith("seoul_") or table in {
        "seoul_district_sales",
        "seoul_district_sales_imputed_v4",
        "seoul_district_sales_imputed_v4_detail",
        "seoul_district_stores",
        "seoul_dong_master",
        "seoul_dong_migration_monthly",
        "seoul_golmok_rent",
        "seoul_population_quarterly",
        "seoul_realtime_hotspots",
        "seoul_resident_pop_quarterly",
        "seoul_subway_passenger_daily",
        "seoul_training_dataset",
        "seoul_ttareungi_usage_daily",
    }:
        return "서울 전역"
    if table.startswith("mapo_"):
        return "마포 전용"
    if table.startswith("kakao_"):
        return "카카오 외부수집"
    if table.startswith("naver_"):
        return "네이버 외부수집"
    if table.startswith("sgis_"):
        return "통계청 SGIS"
    if table.startswith("kosis_") or table.startswith("ecos_") or table.startswith("molit_"):
        return "공공 통계"
    if table.startswith("law_"):
        return "법률 RAG"
    if table.startswith("langchain_"):
        return "Vector DB"
    if (
        table.startswith("master_")
        or table.startswith("industry_master")
        or table in {"dong_mapping", "dong_centroid", "jeonse_dong_master", "holiday_calendar"}
    ):
        return "마스터"
    if table in {"users", "manager_users", "invite_codes", "password_reset_tokens", "user_usage", "biz_brand_mapping"}:
        return "회원/인증"
    if table in {"simulation_ai", "simulation_foresee", "customers"}:
        return "시뮬 결과/고객"
    if table.startswith("golmok_") or table in {
        "district_sales",
        "district_sales_seoul",
        "store_info",
        "store_quarterly",
        "small_store_rent_q",
        "rent_cost",
        "rent_cost_summary_2025",
        "golmok_rent",
        "naver_vacancy",
        "vacancy_enriched",
        "apt_trade_real",
        "jeonse_monthly_rent",
        "elderly_ratio_region",
        "resident_pop_monthly",
        "living_population",
        "living_population_grid",
        "weather_daily",
        "ftc_brand_franchise",
        "mart_brand_territory",
        "bus_boarding_daily",
        "dong_subway_access",
        "cpi_dining_quarterly",
    }:
        return "프로덕션 데이터"
    if table == "alembic_version":
        return "메타"
    return "기타"


def _format_type(c: dict) -> str:
    t = c["type"]
    if c["len"]:
        t = f"{t}({c['len']})"
    return t


def main() -> None:
    engine = sa.create_engine(settings.postgres_url)
    with engine.connect() as conn:
        s = _fetch_schema(conn)

    orm_tables = _orm_tablenames()
    db_tables = set(s["tables"])

    by_domain: dict[str, list[str]] = defaultdict(list)
    for t in s["tables"]:
        by_domain[_domain_of(t)].append(t)

    fks_by_table: dict[str, list[dict]] = defaultdict(list)
    for fk in s["fks"]:
        fks_by_table[fk["table"]].append(fk)

    md: list[str] = []
    md.append("# PostgreSQL 테이블·컬럼 정의서 (DB 실측)")
    md.append("")
    md.append(f"> DB: `mapo_simulator` | **{len(db_tables)}개 테이블**")
    md.append("> 출처: `information_schema` 직접 dump (자동 생성)")
    md.append("> 갱신: `python backend/scripts/diagnostics/gen_db_schema_doc.py`")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## ORM ↔ DB 정합")
    md.append("")
    md.append(f"- DB 실제 테이블: **{len(db_tables)}**")
    md.append(f"- ORM 모델: **{len(orm_tables)}**")
    md.append(f"- 공통: **{len(orm_tables & db_tables)}**")
    zombie = sorted(orm_tables - db_tables)
    db_only = sorted(db_tables - orm_tables)
    md.append(f"- ORM zombie (DB 없음): {', '.join(zombie) if zombie else '없음'}")
    md.append(f"- DB only (ORM 없음): {', '.join(db_only) if db_only else '없음'}")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 도메인별 테이블 목록")
    md.append("")
    for dom in sorted(by_domain.keys()):
        ts = by_domain[dom]
        md.append(f"### {dom} ({len(ts)})")
        md.append("")
        md.append("| 테이블 | row 수 | ORM | PK |")
        md.append("|---|---|---|---|")
        for t in sorted(ts):
            rows = s["rows"].get(t, 0)
            orm = "✓" if t in orm_tables else "—"
            pk = ", ".join(s["pks"].get(t, [])) or "—"
            md.append(f"| `{t}` | {rows:,} | {orm} | {pk} |")
        md.append("")

    md.append("---")
    md.append("")
    md.append("## 테이블별 상세")
    md.append("")
    for t in sorted(s["tables"]):
        rows = s["rows"].get(t, 0)
        pk = ", ".join(s["pks"].get(t, [])) or "(없음)"
        orm = "✓" if t in orm_tables else "✗"
        md.append(f"### `{t}` — {rows:,} rows")
        md.append("")
        md.append(f"- 도메인: {_domain_of(t)}")
        md.append(f"- ORM 정의: {orm}")
        md.append(f"- PK: `{pk}`")

        fks = fks_by_table.get(t, [])
        if fks:
            md.append("- FK:")
            for fk in fks:
                md.append(f"  - `{fk['column']}` → `{fk['ref_table']}.{fk['ref_column']}`")

        md.append("")
        md.append("| 컬럼 | 타입 | NULL | 기본값 |")
        md.append("|---|---|---|---|")
        for c in s["columns"][t]:
            null = "✓" if c["nullable"] else "—"
            default = c["default"] or "—"
            if len(default) > 30:
                default = default[:30] + "…"
            md.append(f"| `{c['name']}` | {_format_type(c)} | {null} | {default} |")
        md.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote: {OUT_MD} ({len(s['tables'])} tables, {sum(len(v) for v in s['columns'].values())} columns)")


if __name__ == "__main__":
    main()
