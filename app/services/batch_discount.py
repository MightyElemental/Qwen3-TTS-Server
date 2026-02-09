# app/services/batch_discount.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.models import RuntimeStat
from app.core.config import Settings
from app.core.security import now_utc


SINGLE_LAT_PER_CHAR_KEY = "single_latency_per_char_ms"
BATCH_DISCOUNT_KEY = "batch_discount_current"


def _get_float(session: Session, key: str, default: float) -> float:
    row = session.exec(select(RuntimeStat).where(RuntimeStat.key == key)).first()
    if not row:
        return default
    try:
        return float(row.value)
    except Exception:
        return default


def _set_float(session: Session, key: str, value: float) -> None:
    row = session.exec(select(RuntimeStat).where(RuntimeStat.key == key)).first()
    if not row:
        row = RuntimeStat(key=key, value=str(value), updated_at=now_utc())
        session.add(row)
    else:
        row.value = str(value)
        row.updated_at = now_utc()
    session.commit()


def get_batch_discount(session: Session, settings: Settings) -> float:
    return _get_float(session, BATCH_DISCOUNT_KEY, settings.batch_discount_default)


def update_single_latency_per_char(session: Session, settings: Settings, chars: int, latency_ms: int) -> None:
    if chars <= 0:
        return
    observed = latency_ms / float(chars)
    current = _get_float(session, SINGLE_LAT_PER_CHAR_KEY, default=observed)
    alpha = settings.batch_discount_ewma_alpha
    new_val = (1 - alpha) * current + alpha * observed
    _set_float(session, SINGLE_LAT_PER_CHAR_KEY, new_val)


def update_batch_discount_from_observation(
    session: Session,
    settings: Settings,
    total_chars: int,
    batch_latency_ms: int,
) -> float:
    """
    We infer batch efficiency using the rolling single-latency-per-char baseline:
      expected = single_lat_ms_per_char * total_chars
      efficiency = batch_latency_ms / expected
    If batching is faster, efficiency < 1.0 => discount < 1.0

    We EWMA update batch_discount_current toward clamp(efficiency).
    """
    if total_chars <= 0:
        return get_batch_discount(session, settings)

    single_lat = _get_float(session, SINGLE_LAT_PER_CHAR_KEY, default=None)  # type: ignore
    if single_lat is None:
        # no baseline yet; keep current
        return get_batch_discount(session, settings)

    expected = single_lat * total_chars
    if expected <= 0:
        return get_batch_discount(session, settings)

    efficiency = batch_latency_ms / expected
    # clamp
    efficiency = max(settings.batch_discount_min, min(settings.batch_discount_max, efficiency))

    current = get_batch_discount(session, settings)
    alpha = settings.batch_discount_ewma_alpha
    new_discount = (1 - alpha) * current + alpha * efficiency
    new_discount = max(settings.batch_discount_min, min(settings.batch_discount_max, new_discount))
    _set_float(session, BATCH_DISCOUNT_KEY, new_discount)
    return new_discount