# app/services/qwen_models.py
from __future__ import annotations

import pickle
from dataclasses import dataclass
from typing import Any, Optional

# Qwen3-TTS official usage shows Qwen3TTSModel and methods like generate_voice_clone/design.
# Install package "qwen-tts" per your requirements.txt.
# Repo: https://github.com/QwenLM/Qwen3-TTS
from qwen_tts import Qwen3TTSModel  # type: ignore


@dataclass
class ModelRegistry:
    base: Optional[Any] = None
    voice_design: Optional[Any] = None
    loaded: bool = False

    def load(self, base_dir: str, voice_design_dir: str) -> None:
        if self.loaded:
            return
        # Base model for prompt creation + voice clone
        self.base = Qwen3TTSModel.from_pretrained(base_dir)
        # VoiceDesign model for designvoice endpoint
        self.voice_design = Qwen3TTSModel.from_pretrained(voice_design_dir)
        self.loaded = True

    def dump_prompt(self, prompt_obj: Any) -> bytes:
        # Store as opaque blob
        return pickle.dumps(prompt_obj, protocol=pickle.HIGHEST_PROTOCOL)

    def load_prompt(self, blob: bytes) -> Any:
        return pickle.loads(blob)


model_registry = ModelRegistry()