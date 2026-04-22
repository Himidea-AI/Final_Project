"""JWT 발급/검증 + FastAPI dependency.

- create_access_token(subject): Bearer 토큰 발급
- decode_token(token): 서명 검증 + payload 반환
- get_current_user: Authorization: Bearer 헤더에서 사용자 컨텍스트 추출

기존 /auth/login · /auth/manager/login 응답 구조는 그대로 유지하되
'access_token' 필드를 추가로 담는다. 나머지 기존 엔드포인트는 이번 단계에서
Bearer 요구로 전환하지 않는다 (회귀 방지).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.config.settings import settings

# optional — 토큰 없이도 라우트 자체는 접근 가능하게 하려면 auto_error=False
_bearer_optional = HTTPBearer(auto_error=False)
# simulation-history 같은 신규 엔드포인트는 토큰 필수
_bearer_required = HTTPBearer(auto_error=True)

UserRole = Literal["master", "manager"]


@dataclass
class UserContext:
    """토큰 payload를 파싱한 런타임 사용자 컨텍스트."""

    user_id: str  # UUID (users.id 또는 manager_users.id)
    role: UserRole
    email: str
    owner_id: Optional[str] = None  # manager인 경우 소속 팀장(users.id)


def create_access_token(
    *,
    user_id: str,
    role: UserRole,
    email: str,
    owner_id: Optional[str] = None,
    expires_minutes: Optional[int] = None,
) -> str:
    """HS256 JWT 발급. 기본 만료 24시간 (settings.jwt_expire_minutes)."""
    exp_min = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_min)).timestamp()),
    }
    if owner_id is not None:
        payload["owner_id"] = owner_id

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> UserContext:
    """토큰 검증 → UserContext. 서명 실패·만료 시 HTTPException(401)."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        return UserContext(
            user_id=str(payload["sub"]),
            role=payload["role"],
            email=payload["email"],
            owner_id=payload.get("owner_id"),
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed token payload: missing {exc}",
        ) from exc


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer_required),
) -> UserContext:
    """Authorization: Bearer <token> 필수 dependency."""
    return decode_token(creds.credentials)


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
) -> Optional[UserContext]:
    """토큰 있으면 파싱, 없으면 None. 기존 public 엔드포인트 호환용."""
    if creds is None:
        return None
    try:
        return decode_token(creds.credentials)
    except HTTPException:
        return None
