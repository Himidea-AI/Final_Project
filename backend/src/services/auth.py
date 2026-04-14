"""
회원 인증 서비스 — 회원가입 + 로그인 + 브랜드 매핑 + 초대코드 + 매니저 가입
"""

import secrets
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
                    "contact_name": data["contactName"],
                    "email": data["email"],
                    "phone": data["phone"],
                    "position": data.get("position", ""),
                    "store_count": str(store_count) if store_count is not None else "",
                    "plan": data.get("plan", "starter"),
                },
                "verification": mapping["verification"],
                "brand": {
                    "brand_name": top_brand["brand_name"] if top_brand else None,
                    "franchise_count": top_brand["franchise_count"] if top_brand else 0,
                    "avg_sales": top_brand.get("avrgSlsAmt", top_brand.get("avg_sales", 0)) if top_brand else 0,
                    "mapo_store_count": top_brand["mapo_store_count"] if top_brand else 0,
                }
                if top_brand
                else None,
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
                        "store_count": str(user["store_count"]) if user["store_count"] is not None else "",
                        "plan": user["plan"],
                    },
                    "brand": {
                        "brand_name": brand_data.get("brand_name", ""),
                        "franchise_count": brand_data.get("franchise_count", 0),
                        "avg_sales": brand_data.get("avrgSlsAmt", brand_data.get("avg_sales", 0)),
                        "mapo_store_count": brand_data.get("mapo_store_count", 0),
                    }
                    if brand_data
                    else None,
                }
        finally:
            engine.dispose()

    # ------------------------------------------------------------------
    # 초대코드 발급
    # ------------------------------------------------------------------

    def generate_invite_code(self, owner_id: str, max_uses: int = 10) -> dict:
        """팀장이 초대코드를 발급한다."""
        engine = create_engine(self._db_url, echo=False)
        try:
            with engine.connect() as conn:
                owner = conn.execute(
                    text("SELECT id, company_name FROM users WHERE id = :id"),
                    {"id": owner_id},
                ).fetchone()
                if not owner:
                    return {"status": "error", "message": "존재하지 않는 사용자입니다."}

                code = secrets.token_hex(4).upper()

                conn.execute(
                    text("""
                        INSERT INTO invite_codes (code, owner_id, max_uses, used_count, is_active)
                        VALUES (:code, :owner_id, :max_uses, 0, true)
                    """),
                    {"code": code, "owner_id": owner_id, "max_uses": max_uses},
                )
                conn.commit()

                return {
                    "status": "success",
                    "invite_code": code,
                    "max_uses": max_uses,
                    "company_name": owner._mapping["company_name"],
                }
        finally:
            engine.dispose()

    # ------------------------------------------------------------------
    # 초대코드 검증 — 팀장 기업정보 반환
    # ------------------------------------------------------------------

    def verify_invite_code(self, code: str) -> dict:
        """초대코드를 검증하고, 유효하면 팀장의 기업정보를 반환한다."""
        engine = create_engine(self._db_url, echo=False)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text("""
                        SELECT ic.id, ic.owner_id, ic.max_uses, ic.used_count, ic.is_active, ic.expires_at,
                               u.company_name, u.biz_number, u.store_count
                        FROM invite_codes ic
                        JOIN users u ON ic.owner_id = u.id
                        WHERE ic.code = :code
                    """),
                    {"code": code.strip().upper()},
                ).fetchone()

                if not row:
                    return {"status": "error", "message": "유효하지 않은 초대코드입니다."}

                inv = dict(row._mapping)

                if not inv["is_active"]:
                    return {"status": "error", "message": "비활성화된 초대코드입니다."}
                if inv["used_count"] >= inv["max_uses"]:
                    return {"status": "error", "message": "사용 횟수를 초과한 초대코드입니다."}
                if inv["expires_at"] and inv["expires_at"] < datetime.now(timezone.utc):
                    return {"status": "error", "message": "만료된 초대코드입니다."}

                return {
                    "status": "success",
                    "company_name": inv["company_name"],
                    "biz_number": inv["biz_number"],
                    "store_count": inv["store_count"],
                    "owner_id": str(inv["owner_id"]),
                }
        finally:
            engine.dispose()

    # ------------------------------------------------------------------
    # 매니저 회원가입
    # ------------------------------------------------------------------

    def manager_signup(self, data: dict) -> dict:
        """
        매니저 회원가입 — 초대코드로 팀장의 기업정보를 상속받아 가입.

        Args:
            data: inviteCode, contactName, position, email, phone, password
        """
        engine = create_engine(self._db_url, echo=False)
        try:
            with engine.connect() as conn:
                # 1. 초대코드 검증
                inv_row = conn.execute(
                    text("""
                        SELECT ic.id, ic.owner_id, ic.max_uses, ic.used_count, ic.is_active, ic.expires_at,
                               u.company_name, u.biz_number, u.store_count
                        FROM invite_codes ic
                        JOIN users u ON ic.owner_id = u.id
                        WHERE ic.code = :code
                    """),
                    {"code": data["inviteCode"].strip().upper()},
                ).fetchone()

                if not inv_row:
                    return {"status": "error", "message": "유효하지 않은 초대코드입니다."}

                inv = dict(inv_row._mapping)

                if not inv["is_active"]:
                    return {"status": "error", "message": "비활성화된 초대코드입니다."}
                if inv["used_count"] >= inv["max_uses"]:
                    return {"status": "error", "message": "사용 횟수를 초과한 초대코드입니다."}
                if inv["expires_at"] and inv["expires_at"] < datetime.now(timezone.utc):
                    return {"status": "error", "message": "만료된 초대코드입니다."}

                # 2. 이메일 중복 체크 (users + manager_users)
                existing = conn.execute(
                    text(
                        "SELECT 1 FROM manager_users WHERE email = :email "
                        "UNION SELECT 1 FROM users WHERE email = :email"
                    ),
                    {"email": data["email"]},
                ).fetchone()
                if existing:
                    return {"status": "error", "message": "이미 가입된 이메일입니다."}

                # 3. 매니저 저장
                manager_id = str(uuid.uuid4())
                password_hash = _hash_password(data["password"])

                conn.execute(
                    text("""
                        INSERT INTO manager_users (
                            id, owner_id, invite_code_id, contact_name, position,
                            email, phone, password_hash, is_active, is_approved
                        ) VALUES (
                            :id, :owner_id, :invite_code_id, :contact_name, :position,
                            :email, :phone, :password_hash, true, false
                        )
                    """),
                    {
                        "id": manager_id,
                        "owner_id": inv["owner_id"],
                        "invite_code_id": inv["id"],
                        "contact_name": data["contactName"],
                        "position": data.get("position", ""),
                        "email": data["email"],
                        "phone": data["phone"],
                        "password_hash": password_hash,
                    },
                )

                # 4. 초대코드 사용 횟수 증가
                conn.execute(
                    text("UPDATE invite_codes SET used_count = used_count + 1 WHERE id = :id"),
                    {"id": inv["id"]},
                )
                conn.commit()

                return {
                    "status": "success",
                    "user": {
                        "id": manager_id,
                        "role": "manager",
                        "contact_name": data["contactName"],
                        "email": data["email"],
                        "phone": data["phone"],
                        "position": data.get("position", ""),
                        "company_name": inv["company_name"],
                        "biz_number": inv["biz_number"],
                        "store_count": str(inv["store_count"]) if inv["store_count"] is not None else "",
                    },
                }
        finally:
            engine.dispose()

    # ------------------------------------------------------------------
    # 매니저 로그인
    # ------------------------------------------------------------------

    def manager_login(self, email: str, password: str) -> dict:
        """매니저 로그인 — 이메일/비밀번호 검증 후 소속 팀장 기업정보 포함 반환."""
        engine = create_engine(self._db_url, echo=False)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text("""
                        SELECT m.id, m.owner_id, m.contact_name, m.position, m.email, m.phone,
                               m.password_hash, m.is_active, m.is_approved,
                               u.company_name, u.biz_number, u.store_count, u.plan
                        FROM manager_users m
                        JOIN users u ON m.owner_id = u.id
                        WHERE m.email = :email
                    """),
                    {"email": email},
                ).fetchone()

                if not row:
                    return {"status": "error", "message": "가입되지 않은 이메일입니다."}

                mgr = dict(row._mapping)

                if not mgr["is_active"]:
                    return {"status": "error", "message": "비활성화된 계정입니다."}

                if not mgr["is_approved"]:
                    return {"status": "error", "message": "팀장의 승인을 기다리고 있습니다."}

                if not _verify_password(password, mgr["password_hash"]):
                    return {"status": "error", "message": "비밀번호가 일치하지 않습니다."}

                return {
                    "status": "success",
                    "user": {
                        "id": str(mgr["id"]),
                        "role": "manager",
                        "contact_name": mgr["contact_name"],
                        "email": mgr["email"],
                        "phone": mgr["phone"],
                        "position": mgr["position"],
                        "company_name": mgr["company_name"],
                        "biz_number": mgr["biz_number"],
                        "store_count": str(mgr["store_count"]) if mgr["store_count"] is not None else "",
                        "plan": mgr["plan"],
                    },
                }
        finally:
            engine.dispose()

    # ------------------------------------------------------------------
    # 매니저 승인 관리
    # ------------------------------------------------------------------

    def get_managers(self, owner_id: str) -> dict:
        """팀장 소속 매니저 전체 목록을 조회한다 (승인 상태 포함)."""
        engine = create_engine(self._db_url, echo=False)
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT id, contact_name, position, email, phone,
                               is_active, is_approved, created_at,
                               assigned_gu, assigned_dongs
                        FROM manager_users
                        WHERE owner_id = :owner_id
                        ORDER BY created_at DESC
                    """),
                    {"owner_id": owner_id},
                ).fetchall()

                managers = [
                    {
                        "id": str(r._mapping["id"]),
                        "contact_name": r._mapping["contact_name"],
                        "position": r._mapping["position"],
                        "email": r._mapping["email"],
                        "phone": r._mapping["phone"],
                        "is_active": r._mapping["is_active"],
                        "is_approved": r._mapping["is_approved"],
                        "created_at": str(r._mapping["created_at"]),
                        "assigned_gu": r._mapping["assigned_gu"],
                        "assigned_dongs": r._mapping["assigned_dongs"],
                    }
                    for r in rows
                ]

                return {"status": "success", "managers": managers}
        finally:
            engine.dispose()

    def approve_manager(
        self,
        owner_id: str,
        manager_id: str,
        assigned_gu: str | None = None,
        assigned_dongs: list[str] | None = None,
    ) -> dict:
        """팀장이 매니저 가입을 승인한다 (담당 구/행정동 지정 포함)."""
        engine = create_engine(self._db_url, echo=False)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT id, contact_name, email FROM manager_users "
                        "WHERE id = :manager_id AND owner_id = :owner_id"
                    ),
                    {"manager_id": manager_id, "owner_id": owner_id},
                ).fetchone()

                if not row:
                    return {"status": "error", "message": "해당 매니저를 찾을 수 없습니다."}

                import json

                conn.execute(
                    text(
                        "UPDATE manager_users "
                        "SET is_approved = true, assigned_gu = :gu, assigned_dongs = :dongs "
                        "WHERE id = :id"
                    ),
                    {
                        "id": manager_id,
                        "gu": assigned_gu,
                        "dongs": json.dumps(assigned_dongs) if assigned_dongs else None,
                    },
                )
                conn.commit()

                mgr = row._mapping
                dong_info = f" (담당: {assigned_gu} {assigned_dongs})" if assigned_gu else ""
                return {
                    "status": "success",
                    "message": f"{mgr['contact_name']}({mgr['email']}) 매니저를 승인했습니다.{dong_info}",
                }
        finally:
            engine.dispose()

    def reject_manager(self, owner_id: str, manager_id: str) -> dict:
        """팀장이 매니저 가입을 거절한다 (비활성화)."""
        engine = create_engine(self._db_url, echo=False)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT id, contact_name, email FROM manager_users "
                        "WHERE id = :manager_id AND owner_id = :owner_id"
                    ),
                    {"manager_id": manager_id, "owner_id": owner_id},
                ).fetchone()

                if not row:
                    return {"status": "error", "message": "해당 매니저를 찾을 수 없습니다."}

                conn.execute(
                    text("UPDATE manager_users SET is_active = false WHERE id = :id"),
                    {"id": manager_id},
                )
                conn.commit()

                mgr = row._mapping
                return {
                    "status": "success",
                    "message": f"{mgr['contact_name']}({mgr['email']}) 매니저를 거절했습니다.",
                }
        finally:
            engine.dispose()
