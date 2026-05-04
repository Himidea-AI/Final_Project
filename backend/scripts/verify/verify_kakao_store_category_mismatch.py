"""kakao_store category mismatch 검증.

체크 의도:
  - category='카페' 인데 category_detail 이 실제 카페가 아닌 항목
  - category='음식점' 인데 category_detail 이 실제 음식점이 아닌 항목

카카오 category_detail 은 ">" 로 구분된 path. 예:
  "음식점 > 한식 > 곰탕,설렁탕"
  "음식점 > 카페 > 커피전문점 > 스타벅스"
  "쇼핑,서비스 > ..."

사용법:
  cd backend
  POSTGRES_URL=... python scripts/verify/verify_kakao_store_category_mismatch.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# .env 로드 (worktree/루트 양쪽)
for env_path in (Path(__file__).parents[2] / ".env", Path(__file__).parents[3] / ".env"):
    if env_path.exists():
        load_dotenv(env_path)
        break

_DEFAULT_DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:postgres@localhost:5432/mapo_simulator",
)

# 진짜 카페 category_detail 키워드
_CAFE_KEYWORDS = ["카페", "커피", "디저트", "베이커리", "제과", "찻집", "차전문", "테마카페"]
# 진짜 음식점 category_detail 키워드 (음식점 path 의 모든 합법 하위)
_FOOD_KEYWORDS = [
    "음식점",
    "한식",
    "양식",
    "중식",
    "일식",
    "분식",
    "치킨",
    "햄버거",
    "패스트푸드",
    "피자",
    "샐러드",
    "도시락",
    "간식",
    "뷔페",
    "퓨전요리",
    "아시아음식",
    "샌드위치",
    "닭갈비",
    "족발",
    "보쌈",
    "찜",
    "탕",
    "전골",
    "구이",
    "회",
    "초밥",
    "라멘",
    "우동",
    "국수",
    "냉면",
    "면",
    "갈비",
    "고기",
    "삼겹살",
    "곱창",
    "막창",
    "장어",
    "해물",
    "조개",
    "게요리",
    "꽃게",
    "해산물",
    "생선",
    "장어구이",
    "분식",
    "토스트",
    "주점",
    "술집",
    "포차",
    "이자카야",
    "와인",
    "맥주",
    "호프",
    "바(BAR)",
    "전",
    "퓨전",
]

QUERIES: list[tuple[str, str]] = [
    (
        "[1] kakao_store 전체 category 분포",
        """
        SELECT category, COUNT(*) AS cnt
          FROM kakao_store
         GROUP BY category
         ORDER BY cnt DESC
        """,
    ),
    (
        "[2] category='카페' 인데 detail 에 카페계열 키워드 0개 (의심 항목)",
        f"""
        SELECT kakao_id, place_name, category_detail, dong_name
          FROM kakao_store
         WHERE category = '카페'
           AND NOT (
             {" OR ".join(f"category_detail ILIKE '%{kw}%'" for kw in _CAFE_KEYWORDS)}
           )
         ORDER BY dong_name, place_name
         LIMIT 100
        """,
    ),
    (
        "[3] category='카페' detail top 30 패턴",
        """
        SELECT category_detail, COUNT(*) AS cnt
          FROM kakao_store
         WHERE category = '카페'
         GROUP BY category_detail
         ORDER BY cnt DESC
         LIMIT 30
        """,
    ),
    (
        "[4] category='음식점' 인데 detail 에 음식 키워드 0개 (의심 항목)",
        f"""
        SELECT kakao_id, place_name, category_detail, dong_name
          FROM kakao_store
         WHERE category = '음식점'
           AND NOT (
             {" OR ".join(f"category_detail ILIKE '%{kw}%'" for kw in _FOOD_KEYWORDS)}
           )
         ORDER BY dong_name, place_name
         LIMIT 100
        """,
    ),
    (
        "[5] category='음식점' detail top 30 패턴",
        """
        SELECT category_detail, COUNT(*) AS cnt
          FROM kakao_store
         WHERE category = '음식점'
         GROUP BY category_detail
         ORDER BY cnt DESC
         LIMIT 30
        """,
    ),
    (
        "[6] category='카페' 인데 path 시작이 '음식점 >' 가 아닌 + '카페 >' 가 아닌 (역방향 체크)",
        """
        SELECT category_detail, COUNT(*) AS cnt
          FROM kakao_store
         WHERE category = '카페'
           AND category_detail NOT ILIKE '음식점 >%'
           AND category_detail NOT ILIKE '카페 >%'
           AND category_detail NOT ILIKE '%카페%'
           AND category_detail NOT ILIKE '%커피%'
         GROUP BY category_detail
         ORDER BY cnt DESC
         LIMIT 30
        """,
    ),
    (
        "[7] category='음식점' 인데 path 시작이 '음식점 >' 가 아닌",
        """
        SELECT category_detail, COUNT(*) AS cnt
          FROM kakao_store
         WHERE category = '음식점'
           AND category_detail NOT ILIKE '음식점 >%'
           AND category_detail NOT ILIKE '음식점%'
         GROUP BY category_detail
         ORDER BY cnt DESC
         LIMIT 30
        """,
    ),
]


def main() -> int:
    db_url = os.environ.get("POSTGRES_URL", _DEFAULT_DB_URL)
    print(f"[verify] DB = {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print()

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for title, sql in QUERIES:
                print(f"=== {title} ===")
                try:
                    cur.execute(sql)
                    cols = [d.name for d in cur.description] if cur.description else []
                    rows = cur.fetchall()
                    if not rows:
                        print("  (empty)")
                    else:
                        print(f"  rows: {len(rows)}")
                        print(f"  cols: {cols}")
                        for r in rows[:30]:
                            print(f"  {r}")
                        if len(rows) > 30:
                            print(f"  ... ({len(rows) - 30} more)")
                except Exception as exc:
                    print(f"  ERROR: {exc}")
                print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
