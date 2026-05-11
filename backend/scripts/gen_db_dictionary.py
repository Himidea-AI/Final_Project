"""DB 테이블 사전 HTML 생성 스크립트.

Usage:
    cd backend && python scripts/gen_db_dictionary.py
"""

import os
import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()
from src.database.sync_engine import get_sync_engine  # noqa: E402


def main():
    engine = get_sync_engine(os.environ["POSTGRES_URL"])

    tables = []
    with engine.connect() as conn:
        raw = conn.execute(
            text(
                "SELECT c.relname, obj_description(c.oid) "
                "FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY c.relname"
            )
        ).fetchall()

        for r in raw:
            name = r[0]
            cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
            cols = conn.execute(
                text(
                    f"SELECT column_name, data_type, is_nullable "
                    f"FROM information_schema.columns "
                    f"WHERE table_name = '{name}' AND table_schema = 'public' "
                    f"ORDER BY ordinal_position"
                )
            ).fetchall()

            col_comments = conn.execute(
                text(
                    f"SELECT a.attname, d.description "
                    f"FROM pg_class c "
                    f"JOIN pg_attribute a ON a.attrelid = c.oid "
                    f"LEFT JOIN pg_description d ON d.objoid = c.oid AND d.objsubid = a.attnum "
                    f"WHERE c.relname = '{name}' AND a.attnum > 0 AND NOT a.attisdropped"
                )
            ).fetchall()
            cc = {x[0]: x[1] for x in col_comments if x[1]}

            idxs = conn.execute(text(f"SELECT indexname FROM pg_indexes WHERE tablename = '{name}'")).fetchall()

            tables.append(
                {
                    "name": name,
                    "comment": r[1] or "",
                    "rows": cnt,
                    "cols": [{"n": c[0], "t": c[1], "null": c[2], "c": cc.get(c[0], "")} for c in cols],
                    "idxs": [x[0] for x in idxs],
                }
            )

    engine.dispose()

    # 분류
    CAT_MAP = {
        "서비스 (인증/시뮬레이션)": [
            "users",
            "manager_users",
            "invite_codes",
            "simulation_ai",
            "simulation_foresee",
            "password_reset_tokens",
            "user_usage",
            "biz_brand_mapping",
        ],
        "법률 RAG": [
            "langchain_pg_collection",
            "langchain_pg_embedding",
            "law_legislations",
            "law_precedents",
        ],
        "시스템": ["alembic_version"],
    }

    def categorize(n):
        for cat, names in CAT_MAP.items():
            if n in names:
                return cat
        if n.startswith("seoul_") or n in (
            "district_sales_seoul",
            "sgis_business",
            "sgis_household",
            "sgis_population",
            "resident_pop_monthly",
            "elderly_ratio_region",
            "kosis_regional_income",
            "ecos_key_statistics",
            "ecos_timeseries",
            "cpi_dining_quarterly",
        ):
            return "서울 전역 데이터"
        if (
            n.startswith("golmok_")
            or n.startswith("kakao_")
            or n.startswith("naver_")
            or n
            in (
                "ftc_brand_franchise",
                "store_info",
                "apt_trade_real",
                "molit_nrg_trade",
                "jeonse_dong_master",
                "jeonse_monthly_rent",
            )
        ):
            return "외부 API 수집 데이터"
        return "마포구 상권 데이터"

    # 실무 노트
    NOTES = {
        "users": "팀장(master) 계정. 사업자번호로 가입, biz_brand_mapping과 연동",
        "manager_users": "매니저 계정. 초대코드로 가입, owner_id로 팀장에 소속",
        "invite_codes": "팀장이 발급한 초대코드. max_uses/used_count로 사용 제한",
        "simulation_ai": "AI 분석(Analyze 탭) 저장 이력. master는 소속 매니저 이력도 조회 가능",
        "simulation_foresee": "예측 결과(Predict 탭) 저장 이력. ML 기반 매출/재무/고객/신흥상권 예측",
        "biz_brand_mapping": "사업자번호-브랜드 매핑. 5,900개 FTC seed + 주요 55개 진짜 번호. API 키 발급 후 나머지 교체 예정",
        "password_reset_tokens": "비밀번호 찾기용 토큰 — 아직 미구현, 향후 사용",
        "user_usage": "요금제별 시뮬 횟수 제한용 — 아직 미구현, 향후 사용",
        "district_sales": "마포 16동x10업종 분기 매출. 시뮬레이션 핵심. 네이밍 규칙상 mapo_ 필요하지만 코드 영향으로 유지 중",
        "store_quarterly": "마포 16동x10업종 분기 점포수/개폐업. district_sales와 JOIN해서 점포당 평균매출 산출",
        "kakao_store": "카카오 Places 마포구 매장. 경쟁사 분석 핵심. kakao_store_hours/menu와 FK 연결",
        "ftc_brand_franchise": "공정위 가맹사업 정보공개서 34,725건. 브랜드 매핑/벤치마크 원천",
        "naver_vacancy": "네이버 부동산 마포구 상가 공실 매물. 공실률 분석",
        "living_population": "서울시 생활인구. 시간대/연령/성별 세분화. ABM 시뮬레이션에서 사용",
        "dong_mapping": "마포구 16개 행정동 코드-동명 매핑. 동 조회의 기본",
        "dong_centroid": "마포구 16개 동 중심좌표. 지도 시각화, 거리 계산",
        "bus_boarding_daily": "버스 승하차 370만행. Operational Fit 버스 접근성 점수",
        "seoul_district_sales": "서울 전역 행정동 매출. TCN 모델 사전학습용",
        "seoul_training_dataset": "TCN 학습용 정제 데이터셋",
        "langchain_pg_embedding": "법률 RAG 벡터 임베딩 44,224개. pgvector 기반 조문 검색",
        "industry_master": "업종 코드 마스터 101개. CS100001(한식)~CS100010(커피)",
        "vacancy_enriched": "공실+주변상권 부가정보. naver_vacancy 확장판 — 아직 미사용",
        "molit_nrg_trade": "국토부 부동산 매매 거래. ORM만 정의, 미사용",
        "customers": "고객 방문 기록용. 0행, 향후 구현 예정",
        "mapo_resident_pop": "마포구 주민등록 인구. ORM만 있고 코드 미참조",
        "seoul_district_sales_imputed_v4": "매출 결측값 ML 보정 137건. TCN 학습에 반영 완료, 런타임 미사용",
    }

    cats = {}
    for t in tables:
        c = categorize(t["name"])
        cats.setdefault(c, []).append(t)

    total_rows = sum(t["rows"] for t in tables)
    total_cols = sum(len(t["cols"]) for t in tables)
    empty = sum(1 for t in tables if t["rows"] == 0)

    # HTML 생성
    lines = []
    lines.append("""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SPOTTER DB 테이블 사전</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Pretendard',-apple-system,sans-serif;background:#0f1117;color:#e4e4e7;line-height:1.6}
.ctn{max-width:1400px;margin:0 auto;padding:32px 24px}
h1{font-size:28px;font-weight:700;color:#fff;margin-bottom:4px}
.sub{color:#71717a;font-size:14px;margin-bottom:28px}
.sb{display:flex;gap:20px;margin-bottom:28px;flex-wrap:wrap}
.st{background:#1a1b23;border:1px solid #27272a;border-radius:12px;padding:14px 22px;min-width:150px}
.sn{font-size:26px;font-weight:700;color:#818cf8}
.sl{font-size:11px;color:#71717a;margin-top:2px}
.cat{margin-bottom:36px}
.ct{font-size:18px;font-weight:600;color:#a5b4fc;margin-bottom:14px;padding-bottom:6px;border-bottom:1px solid #27272a}
.tc{background:#1a1b23;border:1px solid #27272a;border-radius:10px;margin-bottom:10px;overflow:hidden}
.th{display:flex;justify-content:space-between;align-items:center;padding:12px 18px;cursor:pointer;transition:background .2s}
.th:hover{background:#1f2029}
.tn{font-weight:600;font-size:14px;color:#e4e4e7;font-family:'JetBrains Mono',monospace}
.tb{display:flex;gap:6px;align-items:center}
.bg{font-size:10px;padding:2px 8px;border-radius:999px;font-weight:500}
.br{background:#312e81;color:#a5b4fc}
.bc{background:#1e3a2f;color:#6ee7b7}
.be{background:#3b1a1a;color:#fca5a5}
.cm{color:#a1a1aa;font-size:12px;padding:0 18px 10px}
.pn{background:#1c1c2e;border-left:3px solid #818cf8;padding:8px 14px;margin:0 18px 10px;border-radius:0 6px 6px 0;font-size:12px;color:#c4b5fd}
.dt{display:none;padding:0 18px 14px}
.dt.op{display:block}
.ct2{width:100%;border-collapse:collapse;font-size:12px}
.ct2 th{background:#16171f;color:#71717a;font-weight:500;text-align:left;padding:6px 14px;font-size:10px;text-transform:uppercase;letter-spacing:.5px}
.ct2 td{padding:5px 14px;border-top:1px solid #1f2029;color:#d4d4d8}
.ct2 td:first-child{font-family:'JetBrains Mono',monospace;color:#93c5fd;font-size:11px}
.ct2 td:nth-child(2){color:#a1a1aa;font-size:11px}
.cc{color:#71717a;font-size:11px}
.bt{background:none;border:1px solid #3f3f46;color:#a1a1aa;padding:3px 10px;border-radius:5px;cursor:pointer;font-size:11px}
.bt:hover{border-color:#818cf8;color:#818cf8}
.ix{font-size:11px;color:#71717a;padding:6px 0}
.ix span{color:#6ee7b7;font-family:monospace}
.sx{width:100%;padding:10px 18px;background:#1a1b23;border:1px solid #27272a;border-radius:8px;color:#e4e4e7;font-size:14px;margin-bottom:20px;outline:none}
.sx:focus{border-color:#818cf8}
.sx::placeholder{color:#52525b}
</style></head><body><div class="ctn">
<h1>SPOTTER DB 테이블 사전</h1>
<p class="sub">마포구 프랜차이즈 상권분석 시뮬레이터 &mdash; 데이터베이스 구조 문서 | 2026-04-28</p>
""")

    lines.append(f"""<div class="sb">
<div class="st"><div class="sn">{len(tables)}</div><div class="sl">테이블</div></div>
<div class="st"><div class="sn">{total_rows:,}</div><div class="sl">총 행 수</div></div>
<div class="st"><div class="sn">{total_cols}</div><div class="sl">총 컬럼</div></div>
<div class="st"><div class="sn">{empty}</div><div class="sl">빈 테이블</div></div>
</div>
<input type="text" class="sx" placeholder="테이블명 또는 설명으로 검색..." oninput="ft(this.value)">
""")

    cat_order = [
        "서비스 (인증/시뮬레이션)",
        "마포구 상권 데이터",
        "서울 전역 데이터",
        "외부 API 수집 데이터",
        "법률 RAG",
        "시스템",
    ]

    for cat_name in cat_order:
        cat_tables = cats.get(cat_name, [])
        if not cat_tables:
            continue
        lines.append(f'<div class="cat"><h2 class="ct">{cat_name} ({len(cat_tables)}개)</h2>')

        for t in sorted(cat_tables, key=lambda x: x["name"]):
            n = t["name"]
            note = NOTES.get(n, "")
            badges = f'<span class="bg br">{t["rows"]:,}행</span>'
            badges += f'<span class="bg bc">{len(t["cols"])}컬럼</span>'
            if t["rows"] == 0:
                badges += '<span class="bg be">빈 테이블</span>'

            cmt = t["comment"].replace("'", "&#39;").replace('"', "&quot;")
            note_safe = note.replace("'", "&#39;").replace('"', "&quot;")

            lines.append(f'<div class="tc" id="{n}" data-s="{n} {cmt} {note_safe}">')
            lines.append(f'<div class="th" onclick="tg(\'{n}\')"><span class="tn">{n}</span>')
            lines.append(f'<div class="tb">{badges}<button class="bt" id="b-{n}">컬럼 보기</button></div></div>')
            lines.append(f'<div class="cm">{t["comment"]}</div>')
            if note:
                lines.append(f'<div class="pn">{note}</div>')

            lines.append(f'<div class="dt" id="d-{n}">')
            lines.append(
                '<table class="ct2"><thead><tr><th>컬럼명</th><th>타입</th><th>NULL</th><th>설명</th></tr></thead><tbody>'
            )
            for col in t["cols"]:
                nl = "O" if col["null"] == "YES" else "X"
                lines.append(
                    f'<tr><td>{col["n"]}</td><td>{col["t"]}</td><td>{nl}</td><td class="cc">{col["c"]}</td></tr>'
                )
            lines.append("</tbody></table>")

            if t["idxs"]:
                idx_str = ", ".join(f"<span>{i}</span>" for i in t["idxs"])
                lines.append(f'<div class="ix"><strong>인덱스:</strong> {idx_str}</div>')

            lines.append("</div></div>")

        lines.append("</div>")

    lines.append("""<script>
function tg(n){var e=document.getElementById('d-'+n),b=document.getElementById('b-'+n);e.classList.toggle('op');b.textContent=e.classList.contains('op')?'접기':'컬럼 보기'}
function ft(q){q=q.toLowerCase();document.querySelectorAll('.tc').forEach(function(c){c.style.display=(c.dataset.s||'').toLowerCase().includes(q)?'':'none'})}
</script></div></body></html>""")

    out = os.path.join("C:\\Users\\804\\Desktop", "SPOTTER_DB_사전.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"완료: {len(tables)}개 테이블 → {out}")


if __name__ == "__main__":
    main()
