# app/routes/health.py
from __future__ import annotations

from fastapi import APIRouter

from app.services.qwen_models import model_registry

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready():
    if not model_registry.loaded or model_registry.base is None or model_registry.voice_design is None:
        return {"status": "not_ready"}
    return {"status": "ready"}