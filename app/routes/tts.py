# app/routes/tts.py
from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select
import soundfile as sf
from torch import cuda

from app.core.auth import get_current_user, get_settings
from app.core.config import Settings
from app.core.db import get_session
from app.core.models import Voice, Generation, Batch
from app.core.security import now_utc
from app.services.tokens import tokens_for_text, tokens_for_batch
from app.services.audio_store import ensure_supported_output
from app.services.encode import convert_audio
from app.services.qwen_models import model_registry
from app.services.batch_discount import (
    get_batch_discount,
    update_single_latency_per_char,
    update_batch_discount_from_observation,
)

router = APIRouter()


class TTSRequest(BaseModel):
    text: list[str] | str = Field(..., min_length=1)
    voice_id: int
    store: bool = False
    language: str = "auto"
    temperature: float = 1.0
    format: str = Field(default="wav", description="wav|mp3|ogg")


def preprocess_text_single(text: str, settings: Settings):
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text must not be empty")
    if len(text) > settings.max_text_len:
        raise HTTPException(status_code=400, detail=f"Text too long (max {settings.max_text_len})")
    return text

def preprocess_text_batch(texts: list[str], settings: Settings):
    texts = [t.strip() for t in texts]
    if any(not t for t in texts):
        raise HTTPException(status_code=400, detail="All texts must be non-empty")
    if any(len(t) > settings.max_text_len for t in texts):
        raise HTTPException(status_code=400, detail=f"Each text must be <= {settings.max_text_len} chars")
    return texts


@router.post("/tts")
def tts(
    req: TTSRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    user=Depends(get_current_user),
):
    if isinstance(req.text, list):
        raise HTTPException(status_code=400, detail="Single TTS endpoint expects a single text string, not a list")
    text = preprocess_text_single(req.text, settings)

    ensure_supported_output(req.format)

    v = session.exec(select(Voice).where(Voice.id == req.voice_id, Voice.user_id == user.id, Voice.deleted_at.is_(None))).first()
    if not v:
        raise HTTPException(status_code=404, detail="Voice not found")
    if v.id is None:
        raise HTTPException(status_code=500, detail="Voice has no ID (DB error)")

    if model_registry.base is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    prompt = model_registry.load_prompt(v.prompt_blob)
    language = (req.language or "auto").strip() or "auto"

    t0 = time.perf_counter()
    out_wavs, sr = model_registry.base.generate_voice_clone(
        text=text,
        language=language,
        voice_clone_prompt=[prompt],
        temperature=req.temperature,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    cuda.empty_cache()

    # Save to temp wav, convert if needed
    out_dir = settings.media_dir / "gens" / str(user.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    gen_ts = int(now_utc().timestamp() * 1000)
    tmp_wav = str(out_dir / f"gen_{gen_ts}.wav")
    audio = out_wavs[0]
    sf.write(tmp_wav, audio, sr)

    final_path = tmp_wav
    if req.format != "wav":
        final_path = str(out_dir / f"gen_{gen_ts}.{req.format}")
        convert_audio(tmp_wav, final_path)
        try:
            Path(tmp_wav).unlink(missing_ok=True)
        except Exception:
            pass

    # DB write
    tokens_used = tokens_for_text(text)
    gen = Generation(
        user_id=user.id,
        voice_id=v.id,
        batch_id=None,
        store=req.store,
        requested_format=req.format,
        language=language,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
        status="ok",
        error=None,
        created_at=now_utc(),
        audio_path=final_path if req.store else None,
        input_text=text if req.store else None,
    )
    session.add(gen)

    v.use_count += 1
    session.add(v)
    session.commit()
    session.refresh(gen)

    # Update single latency baseline for batch calibration
    update_single_latency_per_char(session, settings, chars=len(text), latency_ms=latency_ms)

    # Return audio + metadata headers
    headers = {
        "X-Generation-Id": str(gen.id),
        "X-Tokens-Used": str(tokens_used),
        "X-Latency-Ms": str(latency_ms),
    }
    media_type = {"wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg"}[req.format]
    return FileResponse(final_path, media_type=media_type, filename=f"tts.{req.format}", headers=headers)


@router.post("/batchtts")
def batchtts(
    req: TTSRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    user=Depends(get_current_user),
):
    if isinstance(req.text, str):
        raise HTTPException(status_code=400, detail="Batch TTS endpoint expects a list of text strings, not a single string")
    if len(req.text) > settings.max_batch_size:
        raise HTTPException(status_code=400, detail=f"Batch too large (max {settings.max_batch_size})")

    texts = preprocess_text_batch(req.text, settings)

    ensure_supported_output(req.format)

    v = session.exec(select(Voice).where(Voice.id == req.voice_id, Voice.user_id == user.id, Voice.deleted_at.is_(None))).first()
    if not v:
        raise HTTPException(status_code=404, detail="Voice not found")
    if v.id is None:
        raise HTTPException(status_code=500, detail="Voice has no ID (DB error)")
    if model_registry.base is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    prompt = model_registry.load_prompt(v.prompt_blob)
    language = (req.language or "auto").strip() or "auto"

    # Current discount, then update after observing batch latency
    discount_before = get_batch_discount(session, settings)

    t0 = time.perf_counter()
    out_wavs, sr = model_registry.base.generate_voice_clone(
        text=texts,                     # batch list supported by Qwen3-TTS
        language=[language] * len(texts),
        voice_clone_prompt=[prompt],
        temperature=req.temperature,
    )
    latency_ms_total = int((time.perf_counter() - t0) * 1000)
    cuda.empty_cache()

    # Update discount based on observed efficiency vs rolling single baseline
    total_chars = sum(len(t) for t in texts)
    discount_after = update_batch_discount_from_observation(session, settings, total_chars, latency_ms_total)
    tokens_used = tokens_for_batch(texts, discount_after)

    # Create batch row
    batch = Batch(
        user_id=user.id,
        voice_id=v.id,
        requested_format=req.format,
        language=language,
        store=req.store,
        tokens_used=tokens_used,
        batch_discount_used=discount_after,
        latency_ms_total=latency_ms_total,
        status="ok",
        error=None,
        created_at=now_utc(),
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)

    # Write outputs and generations (generations.tokens_used = 0 for batch items)
    out_dir = settings.media_dir / "batches" / str(user.id) / str(batch.id)
    out_dir.mkdir(parents=True, exist_ok=True)

    gen_ids: list[int] = []
    file_paths: list[str] = []

    # out_wavs expected list
    if not isinstance(out_wavs, list) or len(out_wavs) != len(texts):
        raise HTTPException(status_code=500, detail="Batch generation returned unexpected output shape")

    for i, wav in enumerate(out_wavs):
        tmp_wav = str(out_dir / f"{i}.wav")
        sf.write(tmp_wav, wav, sr)

        final_path = tmp_wav
        if req.format != "wav":
            final_path = str(out_dir / f"{i}.{req.format}")
            convert_audio(tmp_wav, final_path)
            try:
                Path(tmp_wav).unlink(missing_ok=True)
            except Exception:
                pass

        g = Generation(
            user_id=user.id,
            voice_id=v.id,
            batch_id=batch.id,
            store=req.store,
            requested_format=req.format,
            language=language,
            tokens_used=0,  # per your requirement
            latency_ms=0,   # you could store per-item if you time it; otherwise keep 0
            status="ok",
            error=None,
            created_at=now_utc(),
            audio_path=final_path if req.store else None,
            input_text=texts[i] if req.store else None,
        )
        session.add(g)
        session.commit()
        session.refresh(g)
        gen_ids.append(g.id)
        file_paths.append(final_path)

    v.use_count += len(texts)
    session.add(v)
    session.commit()

    # Create zip in memory for response
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        for i, fp in enumerate(file_paths):
            z.write(fp, arcname=f"{i}.{req.format}")
        # manifest
        manifest = {
            "batch_id": batch.id,
            "generation_ids": gen_ids,
            "format": req.format,
            "language": language,
            "tokens_used": tokens_used,
            "batch_discount_used": discount_after,
            "latency_ms_total": latency_ms_total,
            "store": req.store,
        }
        import json
        z.writestr("manifest.json", json.dumps(manifest, indent=2))

    buf.seek(0)
    headers = {
        "X-Batch-Id": str(batch.id),
        "X-Tokens-Used": str(tokens_used),
        "X-Batch-Discount-Used": str(discount_after),
        "X-Latency-Ms-Total": str(latency_ms_total),
    }
    return StreamingResponse(buf, media_type="application/zip", headers=headers)