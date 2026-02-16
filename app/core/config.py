# app/core/config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # Storage
    data_dir: Path = Path(os.getenv("DATA_DIR", "/app/data"))
    db_path: Path = Path(os.getenv("DB_PATH", "/app/data/db.sqlite3"))
    media_dir: Path = Path(os.getenv("MEDIA_DIR", "/app/data/media"))

    # Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    # Security
    hmac_secret: str = os.getenv("HMAC_SECRET", "change-me")  # MUST override in prod
    admin_token: str = os.getenv("ADMIN_TOKEN", "change-me")  # for /admin/* endpoints

    # Models (downloaded by entrypoint.sh)
    models_dir: Path = Path(os.getenv("MODELS_DIR", "/app/models"))
    base_model_dir: Path = models_dir / "Qwen3-TTS-12Hz-1.7B-Base"
    voice_design_dir: Path = models_dir / "Qwen3-TTS-12Hz-1.7B-VoiceDesign"

    # Limits
    max_text_len: int = int(os.getenv("MAX_TEXT_LEN", "3000"))
    max_batch_size: int = int(os.getenv("MAX_BATCH_SIZE", "50"))
    min_batch_size: int = int(os.getenv("MIN_BATCH_SIZE", "2"))

    # Batch discount calibration defaults
    batch_discount_default: float = float(os.getenv("BATCH_DISCOUNT_DEFAULT", "0.90"))
    batch_discount_min: float = float(os.getenv("BATCH_DISCOUNT_MIN", "0.60"))
    batch_discount_max: float = float(os.getenv("BATCH_DISCOUNT_MAX", "1.00"))
    batch_discount_ewma_alpha: float = float(os.getenv("BATCH_DISCOUNT_EWMA_ALPHA", "0.10"))