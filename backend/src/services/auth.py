"""
회원가입 서비스 — 사업자 검증 + 브랜드 매핑 + 회원 저장
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

            # 4. 응답 조립 (비밀번호 제외)
            top_brand = mapping["brands"][0] if mapping["brands"] else None

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
                    "avg_sales": top_brand["avg_sales"] if top_brand else 0,
                    "mapo_store_count": top_brand["mapo_store_count"] if top_brand else 0,
                } if top_brand else None,
            }

        finally:
            engine.dispose()
