# app/main.py
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.core.config import Settings
from app.core.db import init_db, SessionDep
from app.core.startup import load_models_or_raise
from app.routes import voices, tts, usage, health, auth, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    init_db(settings.db_path)

    # Validate model dirs exist + load models once per process
    load_models_or_raise(settings)

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Qwen3-TTS Server",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, tags=["auth"])
    app.include_router(admin.router, tags=["admin"])
    app.include_router(voices.router, tags=["voices"])
    app.include_router(tts.router, tags=["tts"])
    app.include_router(usage.router, tags=["usage"])

    return app


app = create_app()