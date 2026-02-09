# app/routes/usage.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.sql.functions import count
from sqlmodel import Session, select, func

from app.core.auth import get_current_user
from app.core.db import get_session
from app.core.models import Voice, Generation, Batch

router = APIRouter()


@router.get("/usage")
def usage(
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    # Tokens are accounted in:
    #  - Generation.tokens_used for /tts
    #  - Batch.tokens_used for /batchtts
    gen_tokens = session.exec(
        select(func.coalesce(func.sum(Generation.tokens_used), 0)).where(Generation.user_id == user.id)
    ).one()
    batch_tokens = session.exec(
        select(func.coalesce(func.sum(Batch.tokens_used), 0)).where(Batch.user_id == user.id)
    ).one()

    voices_created = session.exec(
        select(count(Voice.id)).where(Voice.user_id == user.id)
    ).one()

    tts_calls = session.exec(
        select(count(Generation.id)).where(
            Generation.user_id == user.id,
            Generation.batch_id == None,  # pylint: disable=singleton-comparison
        )
    ).one()

    batch_calls = session.exec(
        select(count(Batch.id)).where(Batch.user_id == user.id)
    ).one()

    return {
        "tokens_used_total": int(gen_tokens) + int(batch_tokens),
        "tokens_used_tts": int(gen_tokens),
        "tokens_used_batch": int(batch_tokens),
        "voices_created": int(voices_created),
        "tts_calls": int(tts_calls),
        "batch_calls": int(batch_calls),
    }