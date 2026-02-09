from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Settings:
    models_dir: Path = Path("/app/models")
    base_model_dir: Path = models_dir / "Qwen3-TTS-12Hz-1.7B-Base"
    custom_model_dir: Path = models_dir / "Qwen3-TTS-12Hz-1.7B-CustomVoice"


settings = Settings()


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to synthesize")
    voice: Optional[str] = Field(
        default=None,
        description="Voice id/name (optional). You can map this to your custom voice logic.",
    )
    sample_rate: int = Field(
        default=24000,
        ge=8000,
        le=48000,
        description="Requested audio sample rate",
    )


class TTSResponse(BaseModel):
    # Keep it simple for now: you might return a URL, base64 wav, or stream bytes.
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class AppState:
    """
    Put long-lived resources here (models, tokenizers, etc).
    FastAPI keeps one 'state' per process.
    """

    def __init__(self) -> None:
        self.model: Any = None  # replace Any with your actual model type once you wire it up


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate model directories exist (download happens in entrypoint).
    if not settings.base_model_dir.exists():
        raise RuntimeError(f"Missing base model dir: {settings.base_model_dir}")
    if not settings.custom_model_dir.exists():
        raise RuntimeError(f"Missing custom model dir: {settings.custom_model_dir}")

    # TODO: Load your model(s) here once per process.
    # Example (pseudo):
    # from qwen_tts import QwenTTS
    # state.model = QwenTTS.from_pretrained(str(settings.base_model_dir))
    #
    # If model loading is slow, this is the right place for it.

    yield

    # TODO: Clean up resources if needed
    state.model = None


app = FastAPI(
    title="Qwen3-TTS Server",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/tts", response_model=TTSResponse)
def tts(req: TTSRequest) -> TTSResponse:
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text must not be empty")

    # TODO: Implement synthesis.
    # Common patterns:
    # 1) Return WAV bytes via StreamingResponse
    # 2) Save output to a file and return a URL/path
    # 3) Return base64-encoded audio
    #
    # This stub returns metadata so you can iterate quickly.
    return TTSResponse(
        message="TTS request received (not yet synthesized).",
        details={
            "text_length": len(text),
            "voice": req.voice,
            "sample_rate": req.sample_rate,
            "base_model_dir": str(settings.base_model_dir),
            "custom_model_dir": str(settings.custom_model_dir),
        },
    )