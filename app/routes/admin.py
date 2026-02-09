# app/routes/admin.py
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.auth import get_settings, require_admin
from app.core.db import get_session
from app.core.models import User, Invite
from app.core.security import now_utc, hmac_sha256_hex, new_invite_code
from app.core.config import Settings

router = APIRouter(prefix="/admin")


@router.post("/users")
def admin_create_user(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
):
    user = User(created_at=now_utc(), is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"user_id": user.id}


@router.post("/users/{user_id}/invites")
def admin_create_invite(
    user_id: int,
    expires_hours: int = 24,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_admin),
):
    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user:
        return {"error": "user_not_found"}

    invite_code = new_invite_code()
    code_hash = hmac_sha256_hex(settings.hmac_secret, invite_code)

    inv = Invite(
        user_id=user_id,
        code_hash=code_hash,
        created_at=now_utc(),
        used_at=None,
        expires_at=now_utc() + timedelta(hours=expires_hours),
    )
    session.add(inv)
    session.commit()
    # Important: return the invite code ONCE.
    return {"invite_code": invite_code, "expires_hours": expires_hours}