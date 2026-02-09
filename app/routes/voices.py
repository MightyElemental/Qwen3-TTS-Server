# app/routes/voices.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select
import soundfile as sf

from app.core.auth import get_current_user, get_settings
from app.core.config import Settings
from app.core.db import get_session
from app.core.models import AudioFile, Voice
from app.core.security import now_utc
from app.services.audio_store import sniff_ext, write_dedup_audio
from app.services.tokens import tokens_for_text
from app.services.qwen_models import model_registry

router = APIRouter()


class DesignVoiceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(..., min_length=1)
    language: Optional[str] = Field(default="auto")


class VoiceOut(BaseModel):
    voice_id: int
    name: str
    created_at: str
    use_count: int
    language: str


class VoiceDetail(BaseModel):
    voice_id: int
    name: str
    created_at: str
    use_count: int
    language: str
    ref_text: str
    voice_description: Optional[str] = None


STANDARD_EN_REFERENCE_SCRIPT = (
    # You can replace this with your preferred phoneme/grapheme coverage sentence.
    # Kept as a single constant so its length is deterministic and token-charged.
    "The quick brown fox jumps over the lazy dog. "
    "Pack my box with five dozen liquor jugs. "
    "Sphinx of black quartz, judge my vow."
)


@router.post("/clonevoice")
async def clonevoice(
    name: str = Form(...),
    transcript: str = Form(...),
    language: str = Form("auto"),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    user=Depends(get_current_user),
):
    transcript = transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript must not be empty")
    if not name.strip():
        raise HTTPException(status_code=400, detail="Name must not be empty")

    ext = sniff_ext(file.filename or "")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file upload")

    # Dedup audio
    sha, path = write_dedup_audio(settings, raw, ext)
    audio = session.exec(select(AudioFile).where(AudioFile.sha256 == sha)).first()
    if audio is None:
        audio = AudioFile(sha256=sha, path=path, fmt=ext, created_at=now_utc())
        session.add(audio)
        session.commit()
        session.refresh(audio)
    if audio.id is None:
        raise HTTPException(status_code=500, detail="ID missing")

    # Compute prompt blob now (costs tokens)
    if model_registry.base is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    prompt_obj = model_registry.base.create_voice_clone_prompt(ref_audio=audio.path, ref_text=transcript)
    prompt_blob = model_registry.dump_prompt(prompt_obj)

    voice = Voice(
        user_id=user.id,
        name=name.strip(),
        ref_audio_file_id=audio.id,
        ref_text=transcript,
        voice_description=None,
        language=(language or "auto"),
        prompt_blob=prompt_blob,
        created_at=now_utc(),
        deleted_at=None,
        use_count=0,
    )
    session.add(voice)
    session.commit()
    session.refresh(voice)

    tokens_used = tokens_for_text(transcript)
    return {"voice_id": voice.id, "tokens_used": tokens_used}


@router.post("/designvoice")
def designvoice(
    req: DesignVoiceRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    user=Depends(get_current_user),
):
    if model_registry.voice_design is None or model_registry.base is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    language = (req.language or "auto").strip() or "auto"

    # 1) Generate reference audio with VoiceDesign model
    # Qwen3-TTS supports batch lists, but here it's single.
    out_wavs, sr = model_registry.voice_design.generate_voice_design(
        text=STANDARD_EN_REFERENCE_SCRIPT,
        language=language,
        instruct=req.description,
    )

    # Store reference wav
    out_dir = settings.media_dir / "voices" / str(user.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_wav_path = str(out_dir / f"designed_{int(now_utc().timestamp())}.wav")
    audio = out_wavs[0]
    sf.write(ref_wav_path, audio, sr)

    # Add to audio_files with sha256 dedup
    raw = Path(ref_wav_path).read_bytes()
    sha, dedup_path = write_dedup_audio(settings, raw, "wav")
    if dedup_path != ref_wav_path:
        # If dedup created a different canonical path, remove temp and use canonical
        try:
            Path(ref_wav_path).unlink(missing_ok=True)
        except Exception:
            pass
        ref_wav_path = dedup_path

    audio = session.exec(select(AudioFile).where(AudioFile.sha256 == sha)).first()
    if audio is None:
        audio = AudioFile(sha256=sha, path=ref_wav_path, fmt="wav", created_at=now_utc())
        session.add(audio)
        session.commit()
        session.refresh(audio)
    if audio.id is None:
        raise HTTPException(status_code=500, detail="ID missing")

    # 2) Compute clone prompt blob from the reference audio + reference text
    prompt_obj = model_registry.base.create_voice_clone_prompt(ref_audio=audio.path, ref_text=STANDARD_EN_REFERENCE_SCRIPT)
    prompt_blob = model_registry.dump_prompt(prompt_obj)

    voice = Voice(
        user_id=user.id,
        name=req.name.strip(),
        ref_audio_file_id=audio.id,
        ref_text=STANDARD_EN_REFERENCE_SCRIPT,
        voice_description=req.description,
        language=language,
        prompt_blob=prompt_blob,
        created_at=now_utc(),
        deleted_at=None,
        use_count=0,
    )
    session.add(voice)
    session.commit()
    session.refresh(voice)

    tokens_used = len(req.description) + len(STANDARD_EN_REFERENCE_SCRIPT)
    return {"voice_id": voice.id, "tokens_used": tokens_used}


@router.get("/voices", response_model=list[VoiceOut])
def list_voices(
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    voices = session.exec(
        select(Voice).where(Voice.user_id == user.id, Voice.deleted_at.is_(None)).order_by(Voice.created_at.desc())
    ).all()
    return [
        VoiceOut(
            voice_id=v.id,
            name=v.name,
            created_at=v.created_at.isoformat(),
            use_count=v.use_count,
            language=v.language or "auto",
        )
        for v in voices
    ]


@router.get("/voices/{voice_id}", response_model=VoiceDetail)
def get_voice(
    voice_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    v = session.exec(select(Voice).where(Voice.id == voice_id, Voice.user_id == user.id, Voice.deleted_at.is_(None))).first()
    if not v:
        raise HTTPException(status_code=404, detail="Voice not found")
    return VoiceDetail(
        voice_id=v.id,
        name=v.name,
        created_at=v.created_at.isoformat(),
        use_count=v.use_count,
        language=v.language or "auto",
        ref_text=v.ref_text,
        voice_description=v.voice_description,
    )


@router.get("/voices/{voice_id}/sample")
def voice_sample(
    voice_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    v = session.exec(select(Voice).where(Voice.id == voice_id, Voice.user_id == user.id, Voice.deleted_at.is_(None))).first()
    if not v:
        raise HTTPException(status_code=404, detail="Voice not found")
    audio = session.exec(select(AudioFile).where(AudioFile.id == v.ref_audio_file_id)).first()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(audio.path, media_type="audio/wav", filename=f"{v.name}_sample.wav")


@router.post("/voices/{voice_id}/delete")
def delete_voice(
    voice_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    user=Depends(get_current_user),
):
    v = session.exec(select(Voice).where(Voice.id == voice_id, Voice.user_id == user.id, Voice.deleted_at.is_(None))).first()
    if not v:
        raise HTTPException(status_code=404, detail="Voice not found")

    v.deleted_at = now_utc()
    session.add(v)
    session.commit()

    # If the audio file is not referenced by ANY non-deleted voice, delete it from disk and db.
    other = session.exec(
        select(Voice).where(
            Voice.ref_audio_file_id == v.ref_audio_file_id,
            Voice.deleted_at.is_(None),
        )
    ).first()

    if other is None:
        audio = session.exec(select(AudioFile).where(AudioFile.id == v.ref_audio_file_id)).first()
        if audio:
            try:
                Path(audio.path).unlink(missing_ok=True)
            except Exception:
                pass
            session.delete(audio)
            session.commit()

    return {"status": "deleted"}