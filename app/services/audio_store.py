# app/services/audio_store.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from app.core.security import sha256_file_bytes
from app.core.config import Settings


SUPPORTED_UPLOAD_FORMATS = {"wav", "mp3", "ogg"}
SUPPORTED_OUTPUT_FORMATS = {"wav", "mp3", "ogg"}


def sniff_ext(filename: str) -> str:
    ext = (Path(filename).suffix or "").lower().lstrip(".")
    return ext


def ensure_supported_upload(ext: str) -> None:
    if ext not in SUPPORTED_UPLOAD_FORMATS:
        raise ValueError(f"Unsupported upload format: {ext}. Supported: {sorted(SUPPORTED_UPLOAD_FORMATS)}")


def ensure_supported_output(fmt: str) -> None:
    if fmt not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {fmt}. Supported: {sorted(SUPPORTED_OUTPUT_FORMATS)}")


def write_dedup_audio(settings: Settings, raw: bytes, ext: str) -> Tuple[str, str]:
    """
    Writes audio bytes to disk under media_dir/audio/<sha256>.<ext>
    Returns (sha256, absolute_path).
    """
    ensure_supported_upload(ext)
    h = sha256_file_bytes(raw)
    out_dir = settings.media_dir / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{h}.{ext}"
    if not path.exists():
        path.write_bytes(raw)
    return h, str(path)