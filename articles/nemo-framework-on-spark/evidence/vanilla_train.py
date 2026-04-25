"""
Vanilla-PyTorch GPT pretrain — hand-rolled training loop.

The baseline against which the matched NeMo recipe is measured. Designed
to be the smallest honest representative of "what you write yourself"
when you decide not to lean on a framework — same model shape and
hyperparameters as the NeMo run, same synthetic data, same step count.

Run inside nvcr.io/nvidia/pytorch:25.11-py3 (or any recent PyTorch with
bf16 support). Writes evidence/vanilla_metrics.json.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class Cfg:
    vocab_size: int = 50_257
    seq_len: int = 1024
    n_layer: int = 24
    n_head: int = 16
    d_model: int = 1024
    d_ff: int = 4096
    batch_size: int = 4
    steps: int = 100
    warmup: int = 10
    lr: float = 3e-4
    grad_clip: float = 1.0
    seed: int = 0


class CausalSelfAttention(nn.Module):
    def __init__(self, cfg: Cfg):
        super().__init__()
        self.n_head = cfg.n_head
        self.d_head = cfg.d_model // cfg.n_head
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model, bias=False)
        self.proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)

    def forward(self, x):
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, self.n_head, self.d_head).transpose(1, 2)
        k = k.view(B, T, self.n_head, self.d_head).transpose(1, 2)
        v = v.view(B, T, self.n_head, self.d_head).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        return self.proj(y.transpose(1, 2).contiguous().view(B, T, C))


class Block(nn.Module):
    def __init__(self, cfg: Cfg):
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.d_model)
        self.attn = CausalSelfAttention(cfg)
        self.ln2 = nn.LayerNorm(cfg.d_model)
        self.mlp = nn.Sequential(
            nn.Linear(cfg.d_model, cfg.d_ff, bias=False),
            nn.GELU(),
            nn.Linear(cfg.d_ff, cfg.d_model, bias=False),
        )

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    def __init__(self, cfg: Cfg):
        super().__init__()
        self.cfg = cfg
        self.tok = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.pos = nn.Embedding(cfg.seq_len, cfg.d_model)
        self.blocks = nn.ModuleList([Block(cfg) for _ in range(cfg.n_layer)])
        self.ln_f = nn.LayerNorm(cfg.d_model)
        self.head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        self.head.weight = self.tok.weight  # weight tying

    def forward(self, idx, targets=None):
        B, T = idx.shape
        pos = torch.arange(T, device=idx.device)
        x = self.tok(idx) + self.pos(pos)[None, :, :]
        for blk in self.blocks:
            x = blk(x)
        logits = self.head(self.ln_f(x))
        if targets is None:
            return logits, None
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss


def lr_at(step: int, cfg: Cfg) -> float:
    if step < cfg.warmup:
        return cfg.lr * (step + 1) / cfg.warmup
    progress = (step - cfg.warmup) / max(1, cfg.steps - cfg.warmup)
    return cfg.lr * 0.5 * (1 + math.cos(math.pi * progress))


def random_batch(cfg: Cfg, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    g = torch.Generator(device=device).manual_seed(cfg.seed)
    x = torch.randint(0, cfg.vocab_size, (cfg.batch_size, cfg.seq_len),
                      device=device, generator=g)
    y = torch.roll(x, -1, dims=1)
    return x, y


def main() -> None:
    cfg = Cfg()
    torch.manual_seed(cfg.seed)
    device = torch.device("cuda")
    model = GPT(cfg).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, betas=(0.9, 0.95),
                            fused=True)

    print(f"vanilla GPT  params={n_params/1e6:.1f}M  "
          f"layers={cfg.n_layer} d_model={cfg.d_model} seq={cfg.seq_len} "
          f"batch={cfg.batch_size}  device={device}")

    torch.cuda.reset_peak_memory_stats(device)
    step_times: list[float] = []
    losses: list[float] = []

    model.train()
    for step in range(cfg.steps):
        for g in opt.param_groups:
            g["lr"] = lr_at(step, cfg)

        x, y = random_batch(cfg, device)

        torch.cuda.synchronize(device)
        t0 = time.perf_counter()

        with torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16):
            _, loss = model(x, y)

        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        opt.step()

        torch.cuda.synchronize(device)
        dt = time.perf_counter() - t0
        step_times.append(dt)
        losses.append(loss.item())

        if step < 3 or step % 10 == 0 or step == cfg.steps - 1:
            tok_per_s = (cfg.batch_size * cfg.seq_len) / dt
            print(f"step={step:4d}  loss={loss.item():6.3f}  dt={dt*1e3:6.1f}ms  "
                  f"tok/s={tok_per_s:7.0f}  lr={lr_at(step, cfg):.2e}")

    warm = step_times[10:]
    mean_dt = sum(warm) / len(warm)
    tok_per_step = cfg.batch_size * cfg.seq_len
    metrics = {
        "framework": "vanilla_pytorch",
        "params_m": round(n_params / 1e6, 1),
        "n_layer": cfg.n_layer,
        "d_model": cfg.d_model,
        "seq_len": cfg.seq_len,
        "batch_size": cfg.batch_size,
        "steps": cfg.steps,
        "warmup_steps_excluded_from_mean": 10,
        "mean_step_ms": round(mean_dt * 1e3, 2),
        "tokens_per_s": round(tok_per_step / mean_dt, 1),
        "loss_first": round(losses[0], 3),
        "loss_last": round(losses[-1], 3),
        "peak_gpu_mem_gib": round(
            torch.cuda.max_memory_allocated(device) / (1024**3), 2),
        "peak_gpu_reserved_gib": round(
            torch.cuda.max_memory_reserved(device) / (1024**3), 2),
        "torch_version": torch.__version__,
        "cuda_device": torch.cuda.get_device_name(0),
    }

    out = os.path.join(os.path.dirname(__file__), "vanilla_metrics.json")
    with open(out, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nWrote {out}")
    for k, v in metrics.items():
        print(f"  {k:32s} = {v}")


if __name__ == "__main__":
    main()
