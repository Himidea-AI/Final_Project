"""
회원 인증 서비스 — 회원가입 + 로그인 + 브랜드 매핑
"""

import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import create_engine, text

from src.services.biz_mapper import BizMapper, DB_URL


def _hash_password(password: str) -> str:
    """비밀번호를 bcrypt 해시로 변환."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    """비밀번호 검증."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class AuthService:
    """회원가입 및 인증 서비스"""

    def __init__(self, nts_api_key: str = "", db_url: str | None = None):
        self._db_url = db_url or DB_URL
        self._mapper = BizMapper(nts_api_key=nts_api_key, db_url=self._db_url)

    async def signup(self, data: dict) -> dict:
        """
        회원가입 처리.

        Args:
            data: 프론트엔드에서 받은 회원가입 데이터
                - companyName, bizNumber, contactName, position
                - email, phone, storeCount, password, plan

        Returns:
            dict: 생성된 회원 정보 + 매핑된 브랜드 정보
        """
        engine = create_engine(self._db_url, echo=False)

        try:
            # 1. 이메일 중복 체크
            with engine.connect() as conn:
                existing = conn.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": data["email"]},
                ).fetchone()
                if existing:
                    return {"status": "error", "message": "이미 가입된 이메일입니다."}

                # 사업자번호 중복 체크
                biz_clean = data["bizNumber"].replace("-", "")
                existing_biz = conn.execute(
                    text("SELECT id FROM users WHERE biz_number = :biz"),
                    {"biz": biz_clean},
                ).fetchone()
                if existing_biz:
                    return {"status": "error", "message": "이미 가입된 사업자등록번호입니다."}

            # 2. 사업자번호 검증 + 브랜드 매핑
            mapping = await self._mapper.map_franchise(data["bizNumber"], data["companyName"])

            # 3. 회원 DB 저장
            user_id = str(uuid.uuid4())
            password_hash = _hash_password(data["password"])

            store_count = None
            if data.get("storeCount"):
                try:
                    store_count = int(data["storeCount"])
                except (ValueError, TypeError):
                    pass

            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO users (
                            id, company_name, biz_number, contact_name, position,
                            email, phone, store_count, password_hash, plan, agree_terms, created_at
                        ) VALUES (
                            :id, :company_name, :biz_number, :contact_name, :position,
                            :email, :phone, :store_count, :password_hash, :plan, :agree_terms, :created_at
                        )
                    """),
                    {
                        "id": user_id,
                        "company_name": data["companyName"],
                        "biz_number": biz_clean,
                        "contact_name": data["contactName"],
                        "position": data.get("position", ""),
                        "email": data["email"],
                        "phone": data["phone"],
                        "store_count": store_count,
                        "password_hash": password_hash,
                        "plan": data.get("plan", "starter"),
                        "agree_terms": data.get("agreeTerms", False),
                        "created_at": datetime.now(timezone.utc),
                    },
                )
                conn.commit()

            # 4. biz_brand_mapping 테이블에 매핑 저장 (축적)
            top_brand = mapping["brands"][0] if mapping["brands"] else None
            if top_brand:
                with engine.connect() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO biz_brand_mapping (
                                biz_number, company_name, brand_name,
                                industry_large, industry_medium,
                                franchise_count, avg_sales, mapo_store_count
                            ) VALUES (
                                :biz, :company, :brand,
                                :ind_l, :ind_m,
                                :frc_cnt, :avg_sales, :mapo_cnt
                            )
                            ON CONFLICT (biz_number) DO UPDATE SET
                                brand_name = EXCLUDED.brand_name,
                                franchise_count = EXCLUDED.franchise_count,
                                avg_sales = EXCLUDED.avg_sales,
                                mapo_store_count = EXCLUDED.mapo_store_count
                        """),
                        {
                            "biz": biz_clean,
                            "company": data["companyName"],
                            "brand": top_brand["brand_name"],
                            "ind_l": top_brand.get("industry_large", ""),
                            "ind_m": top_brand.get("industry_medium", ""),
                            "frc_cnt": top_brand["franchise_count"],
                            "avg_sales": top_brand["avg_sales"],
                            "mapo_cnt": top_brand["mapo_store_count"],
                        },
                    )
                    conn.commit()

            # 5. 응답 조립 (비밀번호 제외)
            return {
                "status": "success",
                "user": {
                    "id": user_id,
                    "company_name": data["companyName"],
                    "email": data["email"],
                    "plan": data.get("plan", "starter"),
                },
                "verification": mapping["verification"],
                "brand": {
                    "brand_name": top_brand["brand_name"] if top_brand else None,
                    "franchise_count": top_brand["franchise_count"] if top_brand else 0,
                    "avg_sales": top_brand.get("avrgSlsAmt", top_brand.get("avg_sales", 0)) if top_brand else 0,
                    "mapo_store_count": top_brand["mapo_store_count"] if top_brand else 0,
                } if top_brand else None,
            }

        finally:
            engine.dispose()

    def login(self, email: str, password: str) -> dict:
        """
        로그인 처리 — 이메일 + 비밀번호 검증 후 회원 정보 + 브랜드 매핑 반환.

        Returns:
            dict: 로그인 결과 (회원 정보 + 매핑된 브랜드)
        """
        engine = create_engine(self._db_url, echo=False)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT id, company_name, biz_number, contact_name, position, "
                        "email, phone, store_count, password_hash, plan "
                        "FROM users WHERE email = :email"
                    ),
                    {"email": email},
                ).fetchone()

                if not row:
                    return {"status": "error", "message": "가입되지 않은 이메일입니다."}

                user = dict(row._mapping)

                if not _verify_password(password, user["password_hash"]):
                    return {"status": "error", "message": "비밀번호가 일치하지 않습니다."}

                # 브랜드 매핑 — biz_brand_mapping 우선, 없으면 ftc_brand_franchise 검색
                brand_row = conn.execute(
                    text(
                        "SELECT brand_name, industry_large, industry_medium, "
                        "franchise_count, avg_sales, mapo_store_count "
                        "FROM biz_brand_mapping WHERE biz_number = :biz"
                    ),
                    {"biz": user["biz_number"]},
                ).fetchone()

                if brand_row:
                    brand_data = dict(brand_row._mapping)
                else:
                    brands = self._mapper.search_brand_by_company(user["company_name"])
                    top = brands[0] if brands else None
                    if top:
                        top["mapo_store_count"] = self._mapper.count_mapo_stores(top["brand_name"])
                        brand_data = top
                    else:
                        brand_data = None

                return {
                    "status": "success",
                    "user": {
                        "id": str(user["id"]),
                        "company_name": user["company_name"],
                        "contact_name": user["contact_name"],
                        "email": user["email"],
                        "phone": user["phone"],
                        "position": user["position"],
                        "store_count": user["store_count"],
                        "plan": user["plan"],
                    },
                    "brand": {
                        "brand_name": brand_data.get("brand_name", ""),
                        "franchise_count": brand_data.get("franchise_count", 0),
                        "avg_sales": brand_data.get("avrgSlsAmt", brand_data.get("avg_sales", 0)),
                        "mapo_store_count": brand_data.get("mapo_store_count", 0),
                    } if brand_data else None,
                }
        finally:
            engine.dispose()
