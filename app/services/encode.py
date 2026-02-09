# app/services/encode.py
from __future__ import annotations

import subprocess
from pathlib import Path


def convert_audio(in_wav_path: str, out_path: str) -> None:
    """
    Uses ffmpeg to convert from wav to mp3/ogg or to normalize wav output.
    Assumes ffmpeg exists in the container (it does in your Dockerfile).
    """
    out_ext = Path(out_path).suffix.lower().lstrip(".")
    if out_ext == "wav":
        # Just copy/ensure valid wav through ffmpeg (optional). We’ll do a pass-through.
        subprocess.run(
            ["ffmpeg", "-y", "-i", in_wav_path, out_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    if out_ext == "mp3":
        subprocess.run(
            ["ffmpeg", "-y", "-i", in_wav_path, "-codec:a", "libmp3lame", "-q:a", "3", out_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    if out_ext == "ogg":
        subprocess.run(
            ["ffmpeg", "-y", "-i", in_wav_path, "-codec:a", "libvorbis", "-q:a", "5", out_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    raise ValueError(f"Unsupported output format: {out_ext}")