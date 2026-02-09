# app/services/tokens.py
from __future__ import annotations

import math
from dataclasses import dataclass


def tokens_for_text(s: str) -> int:
    return len(s)


def tokens_for_design(description: str, standard_script: str) -> int:
    return len(description) + len(standard_script)


def tokens_for_batch(texts: list[str], discount: float) -> int:
    total = sum(len(t) for t in texts)
    return int(math.floor(total * discount))