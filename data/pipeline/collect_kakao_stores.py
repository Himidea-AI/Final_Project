"""
카카오 로컬 API 기반 마포구 프랜차이즈 점포 수집 → kakao_store 테이블 적재

담당: A1 — 데이터 엔지니어 (찬영)

Usage:
    python data/pipeline/collect_kakao_stores.py
    python data/pipeline/collect_kakao_stores.py --csv-only
    python data/pipeline/collect_kakao_stores.py --db-url postgresql://user:pw@host/db
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "src"))
from database.models import Base  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

KAKAO_API_KEY = os.environ.get("KAKAO_API_KEY", "8348393ff2ba1edb7a8779be210a7191")

# 마포구 바운딩 박스 (서,남,동,북)
MAPO_RECT = "126.88,37.53,126.96,37.59"

# 위도 1도 ≈ 111km (고정). 경도 1도 ≈ 111km × cos(lat) — 마포(~37.56°)에서 ≈ 88km.
_LAT_M_PER_DEG = 111_000.0
_LON_M_PER_DEG_MAPO = 88_000.0  # cos(37.56°) × 111000


def generate_grid(
    bbox: tuple[float, float, float, float],
    cell_m: int = 500,
) -> list[tuple[float, float, float, float]]:
    """bbox(west, south, east, north)를 cell_m 미터 격자로 분할.

    반환값: [(w, s, e, n), ...] 리스트. 경계가 딱 떨어지지 않으면 마지막 셀이 더 작다.
    """
    west, south, east, north = bbox
    lat_step = cell_m / _LAT_M_PER_DEG
    lon_step = cell_m / _LON_M_PER_DEG_MAPO

    cells: list[tuple[float, float, float, float]] = []
    lat = south
    while lat < north:
        lon = west
        next_lat = min(lat + lat_step, north)
        while lon < east:
            next_lon = min(lon + lon_step, east)
            cells.append((lon, lat, next_lon, next_lat))
            lon = next_lon
        lat = next_lat
    return cells


# category_name prefix → 프로젝트 카테고리 매핑
# Kakao 실제 포맷: "음식점 > 카페 > ...", "음식점 > 간식 > 제과,베이커리" 등
# BRANDS 딕셔너리 분류와 일관성 유지하도록 파생 카테고리 포괄
_CATEGORY_PREFIX_MAP: list[tuple[str, str]] = [
    # 한식
    ("음식점 > 한식", "한식음식점"),
    ("음식점 > 도시락", "한식음식점"),  # 한솥·본도시락
    ("음식점 > 퓨전요리 > 퓨전한식", "한식음식점"),  # 본죽&비빔밥cafe
    ("음식점 > 샤브샤브", "한식음식점"),  # 등촌샤브칼국수
    ("음식점 > 뷔페 > 한식뷔페", "한식음식점"),
    ("음식점 > 기사식당", "한식음식점"),
    # 중식
    ("음식점 > 중식", "중식음식점"),
    ("음식점 > 퓨전요리 > 퓨전중식", "중식음식점"),
    # 일식
    ("음식점 > 일식", "일식음식점"),
    ("음식점 > 퓨전요리 > 퓨전일식", "일식음식점"),
    ("음식점 > 퓨전요리 > 아비꼬", "일식음식점"),  # 아비꼬 카레
    # 양식
    ("음식점 > 양식", "양식음식점"),
    ("음식점 > 패밀리레스토랑", "양식음식점"),  # 빕스·아웃백·매드포갈릭·애슐리
    # 치킨
    ("음식점 > 치킨", "치킨전문점"),
    ("음식점 > 간식 > 닭강정", "치킨전문점"),  # 가마로강정
    # 분식
    ("음식점 > 분식", "분식전문점"),
    # 패스트푸드
    ("음식점 > 패스트푸드", "패스트푸드점"),
    ("음식점 > 간식 > 토스트", "패스트푸드점"),  # 이삭토스트
    ("음식점 > 샐러드", "패스트푸드점"),  # 슬로우캘리·포케올데이·샐러디
    # 제과
    ("음식점 > 간식 > 제과", "제과점"),
    ("음식점 > 제과", "제과점"),
    ("음식점 > 간식 > 도넛", "제과점"),  # 던킨·크리스피크림
    ("음식점 > 간식 > 떡,한과", "제과점"),
    # 호프
    ("음식점 > 술집", "호프-간이주점"),
    # 커피
    ("음식점 > 카페", "커피-음료"),
    ("카페", "커피-음료"),  # fallback
]


def classify_category(category_name: str) -> str:
    """카카오 category_name → 프로젝트 10개 카테고리 + '기타'."""
    if not category_name:
        return "기타"
    for prefix, label in _CATEGORY_PREFIX_MAP:
        if category_name.startswith(prefix):
            return label
    return "기타"


def search_category(
    category_group_code: str,
    rect: tuple[float, float, float, float],
    page: int = 1,
) -> tuple[list[dict], bool]:
    """카카오 카테고리 검색 API. (documents, is_end) 반환."""
    rect_str = f"{rect[0]},{rect[1]},{rect[2]},{rect[3]}"
    params = urllib.parse.urlencode(
        {
            "category_group_code": category_group_code,
            "rect": rect_str,
            "size": 15,
            "page": page,
        }
    )
    url = f"https://dapi.kakao.com/v2/local/search/category.json?{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {KAKAO_API_KEY}"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("documents", []), data.get("meta", {}).get("is_end", True)


MAX_PAGE = 3  # 카카오 API: page 1~3 (15 × 3 = 45건)


def _split_rect(
    rect: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    """bbox를 4분할 (남서/남동/북서/북동)."""
    w, s, e, n = rect
    mid_lon = (w + e) / 2
    mid_lat = (s + n) / 2
    return [
        (w, s, mid_lon, mid_lat),
        (mid_lon, s, e, mid_lat),
        (w, mid_lat, mid_lon, n),
        (mid_lon, mid_lat, e, n),
    ]


def collect_cell(
    category_group_code: str,
    rect: tuple[float, float, float, float],
    max_depth: int = 3,
    _depth: int = 0,
) -> list[dict]:
    """한 셀의 모든 문서 수집. page3까지도 is_end=False면 4분할 재귀."""
    docs: list[dict] = []
    reached_limit = False

    for page in range(1, MAX_PAGE + 1):
        batch, is_end = search_category(category_group_code, rect, page)
        docs.extend(batch)
        if is_end:
            break
        if page == MAX_PAGE:
            reached_limit = True
        time.sleep(0.05)

    if reached_limit and _depth < max_depth:
        for sub in _split_rect(rect):
            docs.extend(collect_cell(category_group_code, sub, max_depth=max_depth, _depth=_depth + 1))
    return docs


_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")
DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"postgresql://postgres:{_pw}@localhost:5432/mapo_simulator",
)

OUT_CSV = Path(__file__).resolve().parents[1] / "processed" / "kakao_store_mapo.csv"

# ---------------------------------------------------------------------------
# 10대 카테고리별 검색 브랜드 목록
# ---------------------------------------------------------------------------

BRANDS: dict[str, list[str]] = {
    "한식음식점": [
        "본죽",
        "한솥도시락",
        "새마을식당",
        "놀부부대찌개",
        "원할머니보쌈",
        "명륜진사갈비",
        "본도시락",
        "국수나무",
        "등촌샤브칼국수",
        "유가네닭갈비",
        "지호한방삼계탕",
        "장수한방삼계탕",
        "오봉집",
        "마포갈매기",
        "보승회관",
        "신의주찹쌀순대",
        "풍년식당",
        "홍대닭갈비",
        "역전우동",
        "남원추어탕",
        "종로빈대떡",
        "김덕후의곱창조",
        "더진국",
        "감나무집",
        "백년옥",
    ],
    "중식음식점": [
        "홍콩반점",
        "탕화쿵푸마라탕",
        "춘리마라탕",
        "마라공방",
        "라화쿵부",
        "손오공마라탕",
        "미스타교자",
        "경성양꼬치",
        "이가네양꼬치",
        "수저가",
        "짬뽕지존",
        "취향저격",
    ],
    "일식음식점": [
        "긴자료코",
        "미야비",
        "키움참치",
        "아비꼬",
        "카츠업",
        "이치류",
        "난바우동",
        "스미비부타동",
        "하코야",
        "생마차",
        "야키토리쇼몽",
        "오레타치카레",
        "멘지",
    ],
    "양식음식점": [
        "샐러디",
        "명동왕돈까스",
        "감성타코",
        "아웃백",
        "매드포갈릭",
        "뚜띠쿠치나",
        "서울미트볼",
        "빕스",
        "열정타코",
        "돈까스브로스",
        "마이클돈까스",
    ],
    "커피-음료": [
        "메가커피",
        "스타벅스",
        "투썸플레이스",
        "이디야",
        "컴포즈커피",
        "빽다방",
        "매머드커피",
        "바나프레소",
        "할리스",
        "커피빈",
        "공차",
        "텐퍼센트커피",
        "백억커피",
        "파스쿠찌",
        "더벤티",
        "감성커피",
        "커피베이",
        "카페베네",
        "엔제리너스",
        "폴바셋",
        "커피집단",
        "커넥츠커피",
        "에이블커피",
    ],
    "치킨전문점": [
        "BBQ치킨",
        "굽네치킨",
        "교촌치킨",
        "bhc치킨",
        "네네치킨",
        "페리카나",
        "노랑통닭",
        "푸라닭",
        "처갓집양념치킨",
        "후라이드참잘하는집",
        "깐부치킨",
        "치킨플러스",
        "명가통닭",
        "또래오래",
        "호식이두마리치킨",
        "지코바치킨",
        "60계치킨",
        "가마로강정",
    ],
    "분식전문점": [
        "김밥천국",
        "김가네김밥",
        "동대문엽기떡볶이",
        "응급실국물떡볶이",
        "청년다방",
        "얌샘김밥",
        "바르다김선생",
        "고봉민김밥",
        "신전떡볶이",
        "죠스떡볶이",
        "테라김밥",
        "마포만두",
    ],
    "제과점": [
        "파리바게뜨",
        "뚜레쥬르",
        "던킨도너츠",
        "스마일꽈배기",
        "코코호도",
        "크리스피크림",
        "브레디크",
    ],
    "패스트푸드점": [
        "써브웨이",
        "도미노피자",
        "롯데리아",
        "맘스터치",
        "이삭토스트",
        "파파존스",
        "피자스쿨",
        "에이셉피자",
        "버거킹",
        "맥도날드",
        "피자헛",
        "에그드랍",
        "고피자",
        "레코드피자",
        "노모어피자",
        "슬로우캘리",
        "포케올데이",
    ],
    "호프-간이주점": [
        "투다리",
        "생활맥주",
        "역전할머니맥주",
        "봉구비어",
        "참새방앗간",
        "노가리호프",
        "을지로골뱅이",
        "펀비어킹",
        "달려라포차",
    ],
}

# 브랜드 정규화 규칙: (정규식, 통일 브랜드명)
NORMALIZE_RULES: list[tuple[str, str]] = [
    # 한식
    (r"본죽.*", "본죽"),
    (r"한솥.*", "한솥도시락"),
    (r"본도시락.*", "본도시락"),
    (r"유가네.*", "유가네닭갈비"),
    (r"등촌샤브.*", "등촌샤브칼국수"),
    (r"지호한방.*", "지호한방삼계탕"),
    (r"장수한방.*", "장수한방삼계탕"),
    (r"국수나무.*", "국수나무"),
    (r"종로계림.*", "종로계림닭도리탕"),
    # 중식
    (r"홍콩반점.*", "홍콩반점"),
    (r"탕화쿵푸.*", "탕화쿵푸마라탕"),
    (r"라화쿵부.*", "라화쿵부"),
    # 커피-음료
    (r"메가(엠지씨|MGC|엠디)?커피.*", "메가MGC커피"),
    (r"투썸플레이스.*", "투썸플레이스"),
    (r"컴포즈커피.*", "컴포즈커피"),
    (r"매머드(익스프레스|커피).*", "매머드커피"),
    (r"이디야.*", "이디야커피"),
    (r"빽다방.*", "빽다방"),
    (r"백억커피.*", "백억커피"),
    (r"커피빈.*", "커피빈"),
    (r"할리스.*", "할리스커피"),
    (r"스타벅스.*", "스타벅스"),
    (r"바나프레소.*", "바나프레소"),
    (r"공차.*", "공차"),
    # 치킨
    (r"비비큐.*|BBQ.*", "BBQ"),
    (r"비에이치씨.*|bhc.*|BHC.*", "BHC"),
    (r"굽네치킨.*", "굽네치킨"),
    (r"교촌치킨.*", "교촌치킨"),
    (r"페리카나.*", "페리카나"),
    (r"네네치킨.*", "네네치킨"),
    (r"노랑통닭.*", "노랑통닭"),
    (r"푸라닭.*", "푸라닭"),
    (r"처갓집.*", "처갓집양념치킨"),
    (r"후라이드참.*", "후라이드참잘하는집"),
    (r"깐부치킨.*", "깐부치킨"),
    (r"치킨플러스.*", "치킨플러스"),
    # 분식
    (r"김밥천국.*", "김밥천국"),
    (r"김가네.*", "김가네김밥"),
    (r"동대문엽기.*|불닭발땡초동대문.*", "동대문엽기떡볶이"),
    (r"응급실.*", "응급실국물떡볶이"),
    (r"얌샘.*", "얌샘김밥"),
    # 제과
    (r"파리바게[뜨트].*", "파리바게뜨"),
    (r"뚜레쥬르.*", "뚜레쥬르"),
    # 패스트푸드
    (r"써브웨이.*", "써브웨이"),
    (r"도미노.*", "도미노피자"),
    (r"롯데리아.*", "롯데리아"),
    (r"맘스터치.*", "맘스터치"),
    (r"이삭토스트.*", "이삭토스트"),
    (r"파파존스.*", "파파존스"),
    (r"비케이알.*|버거킹.*", "버거킹"),
    (r"한국맥도날드.*|맥도날드.*", "맥도날드"),
    # 호프
    (r"투다리.*", "투다리"),
    (r"역전할머니.*", "역전할머니맥주"),
    (r"봉구비어.*", "봉구비어"),
    (r"생활맥주.*", "생활맥주"),
]


def normalize_brand(place_name: str, search_keyword: str) -> str:
    """장소명에서 브랜드명을 정규화한다."""
    for pat, brand in NORMALIZE_RULES:
        if re.match(pat, place_name):
            return brand
    # 규칙에 없으면 검색 키워드를 그대로 사용
    return search_keyword


def extract_dong(address: str) -> str:
    """지번 주소에서 행정동명을 추출한다."""
    m = re.search(r"마포구\s+(\S+동)", address)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Kakao API 호출
# ---------------------------------------------------------------------------


def _kakao_search(query: str, page: int = 1) -> dict:
    """카카오 로컬 키워드 검색 API 호출."""
    params = urllib.parse.urlencode(
        {
            "query": query,
            "rect": MAPO_RECT,
            "size": 15,
            "page": page,
        }
    )
    url = f"https://dapi.kakao.com/v2/local/search/keyword.json?{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {KAKAO_API_KEY}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect_brand(brand: str, category: str) -> list[dict]:
    """특정 브랜드의 마포구 내 점포를 수집한다."""
    stores = []
    seen_ids = set()

    for page in range(1, 4):
        data = _kakao_search(f"{brand} 마포구", page)

        for doc in data["documents"]:
            addr = doc.get("address_name", "")
            road = doc.get("road_address_name", "")
            if "마포구" not in addr and "마포구" not in road:
                continue
            kid = doc["id"]
            if kid in seen_ids:
                continue
            seen_ids.add(kid)

            stores.append(
                {
                    "kakao_id": kid,
                    "place_name": doc["place_name"],
                    "brand_name": normalize_brand(doc["place_name"], brand),
                    "category": category,
                    "category_detail": doc.get("category_name", ""),
                    "address": addr,
                    "road_address": road,
                    "dong_name": extract_dong(addr),
                    "lat": float(doc["y"]),
                    "lon": float(doc["x"]),
                    "phone": doc.get("phone", ""),
                    "place_url": doc.get("place_url", ""),
                }
            )

        if data["meta"]["is_end"]:
            break
        time.sleep(0.05)

    return stores


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def collect_all() -> pd.DataFrame:
    """전체 카테고리 × 브랜드 수집."""
    all_stores: list[dict] = []
    seen_ids: set[str] = set()

    for category, brands in BRANDS.items():
        cat_count = 0
        for brand in brands:
            stores = collect_brand(brand, category)
            for s in stores:
                if s["kakao_id"] not in seen_ids:
                    seen_ids.add(s["kakao_id"])
                    all_stores.append(s)
                    cat_count += 1
            time.sleep(0.1)
        print(f"  {category}: {cat_count}개 점포 수집")

    df = pd.DataFrame(all_stores)
    print(f"\n총 {len(df)}개 점포 수집 완료")
    return df


def load_to_db(df: pd.DataFrame, db_url: str) -> int:
    """DataFrame → kakao_store 테이블 적재 (TRUNCATE+INSERT, 브랜드 모드 전용)."""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine, checkfirst=True)

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE kakao_store;"))

    df.to_sql(
        "kakao_store",
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )
    return len(df)


UPSERT_SQL = text(
    """
    INSERT INTO kakao_store (
        kakao_id, place_name, brand_name, category, category_detail,
        address, road_address, dong_name, lat, lon, phone, place_url,
        is_franchise
    ) VALUES (
        :kakao_id, :place_name, :brand_name, :category, :category_detail,
        :address, :road_address, :dong_name, :lat, :lon, :phone, :place_url,
        :is_franchise
    )
    ON CONFLICT (kakao_id) DO UPDATE SET
        place_name = EXCLUDED.place_name,
        category = EXCLUDED.category,
        category_detail = EXCLUDED.category_detail,
        address = EXCLUDED.address,
        road_address = EXCLUDED.road_address,
        dong_name = EXCLUDED.dong_name,
        lat = EXCLUDED.lat,
        lon = EXCLUDED.lon,
        phone = EXCLUDED.phone,
        place_url = EXCLUDED.place_url,
        is_franchise = kakao_store.is_franchise OR EXCLUDED.is_franchise,
        brand_name = COALESCE(EXCLUDED.brand_name, kakao_store.brand_name),
        collected_at = NOW();
    """
)


def upsert_stores(df: pd.DataFrame, db_url: str, chunksize: int = 500) -> int:
    """DataFrame → kakao_store UPSERT. is_franchise 는 OR 머지, brand_name 은 COALESCE.

    kakao_store_hours FK 보존 (TRUNCATE 하지 않음).
    """
    engine = create_engine(db_url)
    Base.metadata.create_all(engine, checkfirst=True)

    records = df.to_dict(orient="records")
    with engine.begin() as conn:
        for i in range(0, len(records), chunksize):
            conn.execute(UPSERT_SQL, records[i : i + chunksize])
    return len(records)


# 음식점(FD6), 카페(CE7) 두 코드만 사용
CATEGORY_GROUP_CODES = ["FD6", "CE7"]


def _doc_to_row(doc: dict) -> dict | None:
    """카카오 document → kakao_store row dict. 마포 외면 None."""
    addr = doc.get("address_name", "")
    road = doc.get("road_address_name", "")
    if "마포구" not in addr and "마포구" not in road:
        return None

    place_name = doc["place_name"]
    category_name = doc.get("category_name", "")
    category = classify_category(category_name)

    # 브랜드 매칭 시도: NORMALIZE_RULES에 걸리는 경우만 is_franchise=True
    brand: str | None = None
    for pat, bname in NORMALIZE_RULES:
        if re.match(pat, place_name):
            brand = bname
            break

    return {
        "kakao_id": doc["id"],
        "place_name": place_name,
        "brand_name": brand,
        "category": category,
        "category_detail": category_name,
        "address": addr,
        "road_address": road,
        "dong_name": extract_dong(addr),
        "lat": float(doc["y"]),
        "lon": float(doc["x"]),
        "phone": doc.get("phone", ""),
        "place_url": doc.get("place_url", ""),
        "is_franchise": brand is not None,
    }


def collect_all_by_category(
    bbox: tuple[float, float, float, float] | None = None,
    cell_m: int = 500,
) -> pd.DataFrame:
    """그리드 × FD6/CE7로 전수 수집."""
    if bbox is None:
        parts = [float(x) for x in MAPO_RECT.split(",")]
        bbox = (parts[0], parts[1], parts[2], parts[3])

    cells = generate_grid(bbox, cell_m=cell_m)
    print(f"그리드: {len(cells)}셀 (bbox={bbox}, cell={cell_m}m)")

    seen: set[str] = set()
    rows: list[dict] = []
    for idx, cell in enumerate(cells, 1):
        for code in CATEGORY_GROUP_CODES:
            try:
                docs = collect_cell(code, cell)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{idx}/{len(cells)}] {code} 셀 실패 {cell}: {exc}")
                continue
            for doc in docs:
                kid = doc.get("id")
                if not kid or kid in seen:
                    continue
                row = _doc_to_row(doc)
                if row is None:
                    continue
                seen.add(kid)
                rows.append(row)
        if idx % 20 == 0:
            print(f"  진행 {idx}/{len(cells)} 셀, 누적 {len(rows)}건")

    df = pd.DataFrame(rows)
    print(f"\n총 {len(df)}건 수집 (마포 필터, dedupe 후)")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="카카오 로컬 API → kakao_store 적재")
    parser.add_argument(
        "--mode",
        choices=["brands", "categories"],
        default="brands",
        help="brands=기존 150개 프랜차이즈 키워드, categories=FD6+CE7 전수",
    )
    parser.add_argument("--db-url", default=DB_URL)
    parser.add_argument("--csv-only", action="store_true", help="CSV만 저장")
    parser.add_argument("--cell-m", type=int, default=500, help="그리드 셀 크기(m)")
    args = parser.parse_args()

    if args.mode == "brands":
        print("=== 카카오 로컬 API 프랜차이즈 수집 시작 ===\n")
        df = collect_all()
        out_csv = OUT_CSV
    else:
        print("=== 카카오 로컬 API 전수 수집 (카테고리 모드) ===\n")
        df = collect_all_by_category(cell_m=args.cell_m)
        out_csv = OUT_CSV.with_name("kakao_store_full_mapo.csv")

    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\nCSV 저장: {out_csv}")

    if args.csv_only:
        return

    if args.mode == "brands":
        cnt = load_to_db(df, args.db_url)
        print(f"DB 적재 (TRUNCATE+INSERT): {cnt}건 → kakao_store")
    else:
        cnt = upsert_stores(df, args.db_url)
        print(f"DB 적재 (UPSERT): {cnt}건 → kakao_store")

    if args.mode == "brands":
        print("\n=== 카테고리별 브랜드 Top 3 ===\n")
        for cat in BRANDS:
            subset = df[df["category"] == cat]
            top3 = subset["brand_name"].value_counts().head(3)
            print(f"  {cat}:")
            for rank, (brand, n) in enumerate(top3.items(), 1):
                print(f"    {rank}. {brand} : {n}개")
            print()
    else:
        print("\n=== 카테고리별 점포수 / 프랜차이즈 비율 ===\n")
        summary = (
            df.groupby("category")
            .agg(total=("kakao_id", "count"), franchise=("is_franchise", "sum"))
            .sort_values("total", ascending=False)
        )
        print(summary.to_string())


if __name__ == "__main__":
    main()
