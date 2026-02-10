# app/core/security.py
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # assume naive values are UTC (common convention with SQLite)
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hmac_sha256_hex(secret: str, value: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def new_api_key() -> str:
    # 32 bytes ~ 43 chars urlsafe; plenty.
    return secrets.token_urlsafe(32)


def new_invite_code() -> str:
    # shorter, still unguessable
    return secrets.token_urlsafe(18)


def sha256_file_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def key_prefix(key: str, n: int = 8) -> str:
    return key[:n]