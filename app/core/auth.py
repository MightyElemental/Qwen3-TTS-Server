# app/core/auth.py
from __future__ import annotations

from fastapi import Depends, HTTPException, Header
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.db import get_session
from app.core.models import ApiKey, User
from app.core.security import hmac_sha256_hex, now_utc


def get_settings() -> Settings:
    return Settings()


def require_admin(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """
    Admin endpoints use a separate token (NOT user API keys).
    Authorization: Bearer <ADMIN_TOKEN>
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing admin bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    api_key = authorization.split(" ", 1)[1].strip()
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_hash = hmac_sha256_hex(settings.hmac_secret, api_key)
    row = session.exec(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    ).first()
    if not row:
        raise HTTPException(status_code=403, detail="Invalid or revoked API key")

    user = session.exec(select(User).where(User.id == row.user_id, User.is_active == True)).first()
    if not user:
        raise HTTPException(status_code=403, detail="User disabled")

    row.last_used_at = now_utc()
    session.add(row)
    session.commit()
    return user