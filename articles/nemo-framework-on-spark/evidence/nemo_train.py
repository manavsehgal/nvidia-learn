"""
NeMo Framework matched run — same 354M GPT, same hyperparameters, same
data, same step count as vanilla_train.py. The model is assembled from
Megatron-Core's GPTModel with a TransformerEngine layer spec — the same
pair NeMo Framework wraps internally when you run `nemo llm pretrain`.

This script intentionally keeps the training loop structure identical to
vanilla_train.py so the throughput comparison isolates the model
implementation, not the surrounding boilerplate. The "what NeMo earns
in lines of code" comparison lives in the article body, not in a
contrived script.

Run inside nvcr.io/nvidia/pytorch:25.11-py3 after:
  pip install nemo-toolkit megatron-core
Writes evidence/nemo_metrics.json.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass

import torch
import torch.nn.functional as F
from megatron.core import parallel_state
from megatron.core import tensor_parallel
from megatron.core.models.gpt import GPTModel
from megatron.core.models.gpt.gpt_layer_specs import (
    get_gpt_layer_with_transformer_engine_spec,
)
from megatron.core.transformer import TransformerConfig


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


def init_distributed_single_gpu() -> None:
    os.environ.setdefault("MASTER_ADDR", "127.0.0.1")
    os.environ.setdefault("MASTER_PORT", "29500")
    os.environ.setdefault("RANK", "0")
    os.environ.setdefault("WORLD_SIZE", "1")
    os.environ.setdefault("LOCAL_RANK", "0")
    if not torch.distributed.is_initialized():
        torch.distributed.init_process_group(backend="nccl", world_size=1, rank=0)
    torch.cuda.set_device(0)
    parallel_state.initialize_model_parallel(
        tensor_model_parallel_size=1,
        pipeline_model_parallel_size=1,
    )
    tensor_parallel.model_parallel_cuda_manual_seed(0)


def build_model(cfg: Cfg) -> GPTModel:
    tcfg = TransformerConfig(
        num_layers=cfg.n_layer,
        hidden_size=cfg.d_model,
        num_attention_heads=cfg.n_head,
        ffn_hidden_size=cfg.d_ff,
        bf16=True,
        params_dtype=torch.bfloat16,
        attention_softmax_in_fp32=True,
        pipeline_dtype=torch.bfloat16,
        tensor_model_parallel_size=1,
        pipeline_model_parallel_size=1,
        sequence_parallel=False,
        use_cpu_initialization=False,
        gradient_accumulation_fusion=False,
        masked_softmax_fusion=True,
        bias_activation_fusion=False,
        bias_dropout_fusion=False,
        persist_layer_norm=False,
        normalization="LayerNorm",
        activation_func=F.gelu,
        add_bias_linear=False,
    )
    spec = get_gpt_layer_with_transformer_engine_spec()
    model = GPTModel(
        config=tcfg,
        transformer_layer_spec=spec,
        vocab_size=cfg.vocab_size,
        max_sequence_length=cfg.seq_len,
        pre_process=True,
        post_process=True,
        parallel_output=False,
        share_embeddings_and_output_weights=True,
        position_embedding_type="learned_absolute",
    )
    return model.cuda()


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


def make_attention_mask(seq_len: int, device: torch.device) -> torch.Tensor:
    mask = torch.tril(torch.ones((seq_len, seq_len), device=device, dtype=torch.bool))
    return ~mask.unsqueeze(0).unsqueeze(0)


def main() -> None:
    cfg = Cfg()
    torch.manual_seed(cfg.seed)
    init_distributed_single_gpu()
    device = torch.device("cuda")

    model = build_model(cfg)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, betas=(0.9, 0.95),
                            fused=True)

    print(f"NeMo/Megatron GPTModel  params={n_params/1e6:.1f}M  "
          f"layers={cfg.n_layer} d_model={cfg.d_model} seq={cfg.seq_len} "
          f"batch={cfg.batch_size}  TE-attention=enabled  device={device}")

    attn_mask = make_attention_mask(cfg.seq_len, device)
    pos_ids = torch.arange(cfg.seq_len, device=device).unsqueeze(0).expand(cfg.batch_size, -1)

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
            logits = model(x, position_ids=pos_ids, attention_mask=attn_mask, labels=None)
        loss = F.cross_entropy(logits.float().view(-1, logits.size(-1)), y.view(-1))

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
        "framework": "nemo_megatron_core",
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

    out = os.path.join(os.path.dirname(__file__), "nemo_metrics.json")
    with open(out, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nWrote {out}")
    for k, v in metrics.items():
        print(f"  {k:32s} = {v}")


if __name__ == "__main__":
    main()
