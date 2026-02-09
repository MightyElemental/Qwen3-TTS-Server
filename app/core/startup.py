# app/core/startup.py
from __future__ import annotations

from app.core.config import Settings
from app.services.qwen_models import model_registry


def load_models_or_raise(settings: Settings) -> None:
    if not settings.base_model_dir.exists():
        raise RuntimeError(f"Missing base model dir: {settings.base_model_dir}")
    if not settings.voice_design_dir.exists():
        raise RuntimeError(f"Missing voice design dir: {settings.voice_design_dir}")

    # Ensure media dir exists
    settings.media_dir.mkdir(parents=True, exist_ok=True)

    # Load models once per process
    model_registry.load(base_dir=str(settings.base_model_dir), voice_design_dir=str(settings.voice_design_dir))