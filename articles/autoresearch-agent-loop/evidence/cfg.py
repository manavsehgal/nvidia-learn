"""
The training cfg the agent twists. Every knob here matches A5's
perturbation_menu.json. Single source of truth for the baseline.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from typing import Any


@dataclass
class Cfg:
    n_layer: int = 24
    n_head: int = 16
    d_model: int = 1024
    d_ff: int = 4096
    lr: float = 3e-4
    lr_warmup: int = 5
    grad_clip: float = 1.0
    weight_decay: float = 0.0
    beta1: float = 0.9
    beta2: float = 0.95
    batch_size: int = 16
    seq_len: int = 1024
    precision: str = "fp8"

    # Training-loop constants (NOT in the agent's allowlist; baked in here)
    vocab_size: int = 50_257
    steps: int = 60         # per-iteration training step count
    val_chunk_tokens: int = 16_384  # held-out validation slice
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_(self, knob: str, new_value: Any) -> "Cfg":
        return replace(self, **{knob: new_value})


BASELINE = Cfg()
