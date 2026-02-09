# app/core/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime
    is_active: bool = True

    api_keys: list["ApiKey"] = Relationship(back_populates="user")
    invites: list["Invite"] = Relationship(back_populates="user")
    voices: list["Voice"] = Relationship(back_populates="user")


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    key_prefix: str = Field(index=True)
    key_hash: str = Field(index=True)

    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    user: User = Relationship(back_populates="api_keys")


class Invite(SQLModel, table=True):
    """
    Invite tokens allow a user to generate their own API key without an admin ever seeing the API key.

    Flow:
      - admin creates an invite for a user (returns invite_code ONCE)
      - user calls /auth/exchange-invite with invite_code -> server returns API key ONCE and marks invite used
    """
    __tablename__ = "invites"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    code_hash: str = Field(index=True)
    created_at: datetime
    used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    user: User = Relationship(back_populates="invites")


class AudioFile(SQLModel, table=True):
    __tablename__ = "audio_files"
    id: Optional[int] = Field(default=None, primary_key=True)

    sha256: str = Field(index=True, unique=True)
    path: str
    fmt: str  # wav/mp3/ogg
    created_at: datetime


class Voice(SQLModel, table=True):
    __tablename__ = "voices"
    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="users.id", index=True)
    name: str = Field(index=True)

    ref_audio_file_id: int = Field(foreign_key="audio_files.id", index=True)
    ref_text: str

    # For "designvoice" voices, store the user's description here (optional for clonevoice).
    voice_description: Optional[str] = None

    # Always store language; default to "auto" if not explicitly set by user.
    language: str = Field(default="auto", index=True)

    # Precomputed voice_clone_prompt blob (serialized bytes)
    prompt_blob: bytes

    created_at: datetime
    deleted_at: Optional[datetime] = None

    use_count: int = 0

    user: User = Relationship(back_populates="voices")


class Batch(SQLModel, table=True):
    __tablename__ = "batches"
    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="users.id", index=True)
    voice_id: int = Field(foreign_key="voices.id", index=True)

    requested_format: str = "wav"  # wav/mp3/ogg
    language: str = "auto"
    store: bool = False

    tokens_used: int
    batch_discount_used: float

    latency_ms_total: int

    status: str = "ok"
    error: Optional[str] = None

    created_at: datetime


class Generation(SQLModel, table=True):
    __tablename__ = "generations"
    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="users.id", index=True)
    voice_id: int = Field(foreign_key="voices.id", index=True)
    batch_id: Optional[int] = Field(default=None, foreign_key="batches.id", index=True)

    store: bool = False
    requested_format: str = "wav"
    language: str = "auto"

    # Per your decision: generations.tokens_used is 0 for batch items.
    # For non-batch /tts it can be stored here (or you can also store it on a separate table).
    tokens_used: int = 0

    latency_ms: int
    status: str = "ok"
    error: Optional[str] = None

    created_at: datetime

    # Only stored if store=True
    audio_path: Optional[str] = None
    input_text: Optional[str] = None


class RuntimeStat(SQLModel, table=True):
    """
    Small key/value table for things like:
      - single_latency_per_char_ms (rolling)
      - batch_discount_current
    """
    __tablename__ = "runtime_stats"
    key: str = Field(primary_key=True)
    value: str
    updated_at: datetime