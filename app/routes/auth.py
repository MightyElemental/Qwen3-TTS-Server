# app/routes/auth.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.auth import get_settings
from app.core.config import Settings
from app.core.db import get_session
from app.core.models import Invite, ApiKey
from app.core.security import now_utc, as_utc_aware, hmac_sha256_hex, new_api_key, key_prefix

router = APIRouter(prefix="/auth")


class ExchangeInviteRequest(BaseModel):
    invite_code: str = Field(..., min_length=8)


@router.post("/exchange-invite")
def exchange_invite_for_api_key(
    req: ExchangeInviteRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    code_hash = hmac_sha256_hex(settings.hmac_secret, req.invite_code)
    inv = session.exec(select(Invite).where(Invite.code_hash == code_hash)).first()
    if not inv:
        raise HTTPException(status_code=403, detail="Invalid invite code")

    if inv.used_at is not None:
        raise HTTPException(status_code=403, detail="Invite already used")

    if inv.expires_at is not None and now_utc() > as_utc_aware(inv.expires_at):
        raise HTTPException(status_code=403, detail="Invite expired")

    # Generate API key (admin never sees this).
    api_key = new_api_key()
    ak = ApiKey(
        user_id=inv.user_id,
        key_prefix=key_prefix(api_key),
        key_hash=hmac_sha256_hex(settings.hmac_secret, api_key),
        created_at=now_utc(),
        last_used_at=None,
        revoked_at=None,
    )
    session.add(ak)

    inv.used_at = now_utc()
    session.add(inv)
    session.commit()

    # Return API key ONCE.
    return {"api_key": api_key, "key_prefix": ak.key_prefix}