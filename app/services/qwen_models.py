# app/services/qwen_models.py
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Optional

from torch import bfloat16
import torch

# Qwen3-TTS official usage shows Qwen3TTSModel and methods like generate_voice_clone/design.
# Install package "qwen-tts" per your requirements.txt.
# Repo: https://github.com/QwenLM/Qwen3-TTS
from qwen_tts import Qwen3TTSModel  # type: ignore
from qwen_tts.inference.qwen3_tts_model import VoiceClonePromptItem


@dataclass
class ModelRegistry:
    base: Optional[Any] = None
    voice_design: Optional[Any] = None
    loaded: bool = False

    def load(
        self,
        base_dir: str,
        voice_design_dir: str,
        base_use_gpu: bool = True,
        design_use_gpu: bool = False,
    ) -> None:
        if self.loaded:
            return
        # Base model for prompt creation + voice clone
        if base_use_gpu:
            self.base = Qwen3TTSModel.from_pretrained(
                base_dir,
                device_map="cuda:0",
                dtype=bfloat16,
                attn_implementation="flash_attention_2",
            )
        else:
            self.base = Qwen3TTSModel.from_pretrained(base_dir)

        # VoiceDesign model for designvoice endpoint
        if design_use_gpu:
            self.voice_design = Qwen3TTSModel.from_pretrained(
                voice_design_dir,
                device_map="cuda:0",
                dtype=bfloat16,
                attn_implementation="flash_attention_2",
            )
        else:
            self.voice_design = Qwen3TTSModel.from_pretrained(voice_design_dir)
        self.loaded = True

    def dump_prompt(self, prompt_obj: Any) -> bytes:
        buf = io.BytesIO()
        torch.save(prompt_obj, buf)
        return buf.getvalue()

    def load_prompt(self, blob: bytes) -> Any:
        buf = io.BytesIO(blob)
        # map_location="cpu" is safest; Qwen will move as needed internally.
        torch.serialization.add_safe_globals([VoiceClonePromptItem])
        return torch.load(buf, map_location="cpu", weights_only=False)


model_registry = ModelRegistry()