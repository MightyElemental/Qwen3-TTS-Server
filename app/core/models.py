# app/core/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime
    is_active: bool = True


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    key_prefix: str = Field(index=True)
    key_hash: str = Field(index=True)

    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class Invite(SQLModel, table=True):
    __tablename__ = "invites"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    code_hash: str = Field(index=True)
    created_at: datetime
    used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


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

    voice_description: Optional[str] = None
    language: str = Field(default="auto", index=True)

    prompt_blob: bytes

    created_at: datetime
    deleted_at: Optional[datetime] = None

    use_count: int = 0


class Batch(SQLModel, table=True):
    __tablename__ = "batches"
    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="users.id", index=True)
    voice_id: int = Field(foreign_key="voices.id", index=True)

    requested_format: str = "wav"
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
    temperature: float = 1.0

    tokens_used: int = 0

    latency_ms: int
    status: str = "ok"
    error: Optional[str] = None

    created_at: datetime

    audio_path: Optional[str] = None
    input_text: Optional[str] = None


class RuntimeStat(SQLModel, table=True):
    __tablename__ = "runtime_stats"
    key: str = Field(primary_key=True)
    value: str
    updated_at: datetime