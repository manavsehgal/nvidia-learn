"""
Evaluator — runs N steps of training with the given cfg on the A3 corpus,
returns val_bpb (bits per byte = cross-entropy / log(2)) on a held-out
slice of the packed memmap.

Same Megatron-Core scaffolding as A2's sweep.py and A3's data_sweep.py.
This module is the *measurement* the agent's decisions hinge on; it
must be deterministic at the cfg level (same cfg → same val_bpb to
within step-time noise) so the agent's keep/revert decisions are
reproducible.

Returns a dict {ok, val_bpb, train_loss_first, train_loss_last,
mean_step_ms, peak_gpu_mem_gib, error?, oom?}.
"""
from __future__ import annotations

import gc
import math
import os
import time
import traceback
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import transformer_engine.pytorch as te
from transformer_engine.common.recipe import DelayedScaling, Format
from megatron.core import parallel_state, tensor_parallel
from megatron.core.models.gpt import GPTModel
from megatron.core.models.gpt.gpt_layer_specs import (
    get_gpt_layer_with_transformer_engine_spec,
)
from megatron.core.transformer import TransformerConfig

EVIDENCE = Path(__file__).resolve().parent
A3_PACKED = Path(os.environ.get(
    "A3_PACKED",
    str(EVIDENCE.parent.parent / "nemo-curator-training-data-prep" / "evidence"
        / "packed.int32.npy"),
))


_DIST_INITED = False


def _init_distributed_once(seed: int) -> None:
    global _DIST_INITED
    if _DIST_INITED:
        return
    os.environ.setdefault("MASTER_ADDR", "127.0.0.1")
    os.environ.setdefault("MASTER_PORT", "29500")
    os.environ.setdefault("RANK", "0")
    os.environ.setdefault("WORLD_SIZE", "1")
    os.environ.setdefault("LOCAL_RANK", "0")
    if not torch.distributed.is_initialized():
        torch.distributed.init_process_group(backend="nccl", world_size=1, rank=0)
    torch.cuda.set_device(0)
    parallel_state.initialize_model_parallel(1, 1)
    tensor_parallel.model_parallel_cuda_manual_seed(seed)
    _DIST_INITED = True


def _build_model(cfg) -> GPTModel:
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


def _lr_at(step: int, cfg) -> float:
    if step < cfg.lr_warmup:
        return cfg.lr * (step + 1) / max(1, cfg.lr_warmup)
    progress = (step - cfg.lr_warmup) / max(1, cfg.steps - cfg.lr_warmup)
    return cfg.lr * 0.5 * (1 + math.cos(math.pi * progress))


def _make_attention_mask(seq: int, device: torch.device) -> torch.Tensor:
    mask = torch.tril(torch.ones((seq, seq), device=device, dtype=torch.bool))
    return ~mask.unsqueeze(0).unsqueeze(0)


class _Batcher:
    """Sequential walker over the A3 packed memmap. Splits the corpus into
    train (first 95%) and val (last 5%) to avoid leakage. Validation pulls
    a fixed window from the val slice each call so val_bpb is comparable
    across iterations."""

    def __init__(self, packed_path: Path, train_frac: float = 0.95):
        self._packed = np.load(packed_path, mmap_mode="r")
        n = self._packed.shape[0]
        self._train_end = int(n * train_frac)
        self._cursor = 0
        self._n = n

    @property
    def n_total(self) -> int:
        return self._n

    @property
    def n_train(self) -> int:
        return self._train_end

    def next_train_batch(self, batch: int, seq: int) -> tuple[torch.Tensor, torch.Tensor]:
        need = batch * (seq + 1)
        if self._cursor + need > self._train_end:
            self._cursor = 0
        view = np.asarray(self._packed[self._cursor:self._cursor + need], dtype=np.int64)
        self._cursor += batch * seq
        view = view.reshape(batch, seq + 1)
        x = torch.from_numpy(view[:, :-1]).to("cuda", dtype=torch.long, non_blocking=True)
        y = torch.from_numpy(view[:, 1:]).to("cuda", dtype=torch.long, non_blocking=True)
        return x, y

    def val_batches(self, batch: int, seq: int, total_tokens: int):
        """Yield val batches drawn from the val slice (fixed across runs)."""
        per = batch * (seq + 1)
        n_batches = max(1, total_tokens // (batch * seq))
        cursor = self._train_end
        for _ in range(n_batches):
            if cursor + per > self._n:
                cursor = self._train_end
            view = np.asarray(self._packed[cursor:cursor + per], dtype=np.int64)
            cursor += batch * seq
            view = view.reshape(batch, seq + 1)
            x = torch.from_numpy(view[:, :-1]).to("cuda", dtype=torch.long, non_blocking=True)
            y = torch.from_numpy(view[:, 1:]).to("cuda", dtype=torch.long, non_blocking=True)
            yield x, y


def evaluate(cfg) -> dict:
    """Run cfg.steps of training + a fixed val pass. Return metrics."""
    _init_distributed_once(cfg.seed)
    device = torch.device("cuda")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)

    model = None
    opt = None
    try:
        torch.manual_seed(cfg.seed)
        model = _build_model(cfg)
        n_params = sum(p.numel() for p in model.parameters())
        opt = torch.optim.AdamW(
            model.parameters(),
            lr=cfg.lr, betas=(cfg.beta1, cfg.beta2),
            weight_decay=cfg.weight_decay, fused=True,
        )
        attn_mask = _make_attention_mask(cfg.seq_len, device)
        pos_ids = torch.arange(cfg.seq_len, device=device).unsqueeze(0).expand(cfg.batch_size, -1)
        batcher = _Batcher(A3_PACKED)

        fp8_recipe = None
        if cfg.precision == "fp8":
            fp8_recipe = DelayedScaling(
                fp8_format=Format.HYBRID, amax_history_len=16, amax_compute_algo="max"
            )

        train_losses = []
        step_times = []
        model.train()
        t_train0 = time.perf_counter()

        for step in range(cfg.steps):
            for g in opt.param_groups:
                g["lr"] = _lr_at(step, cfg)
            x, y = batcher.next_train_batch(cfg.batch_size, cfg.seq_len)
            torch.cuda.synchronize(device)
            t0 = time.perf_counter()
            with torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16):
                if fp8_recipe is not None:
                    with te.fp8_autocast(enabled=True, fp8_recipe=fp8_recipe):
                        logits = model(x, position_ids=pos_ids,
                                       attention_mask=attn_mask, labels=None)
                else:
                    logits = model(x, position_ids=pos_ids,
                                   attention_mask=attn_mask, labels=None)
            loss = F.cross_entropy(logits.float().view(-1, logits.size(-1)), y.view(-1))
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            opt.step()
            torch.cuda.synchronize(device)
            step_times.append(time.perf_counter() - t0)
            train_losses.append(loss.item())

        train_wall_s = time.perf_counter() - t_train0

        # Validation: average cross-entropy over val_chunk_tokens.
        model.eval()
        val_losses = []
        val_t0 = time.perf_counter()
        with torch.no_grad():
            for x, y in batcher.val_batches(cfg.batch_size, cfg.seq_len, cfg.val_chunk_tokens):
                with torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16):
                    if fp8_recipe is not None:
                        with te.fp8_autocast(enabled=True, fp8_recipe=fp8_recipe):
                            logits = model(x, position_ids=pos_ids,
                                           attention_mask=attn_mask, labels=None)
                    else:
                        logits = model(x, position_ids=pos_ids,
                                       attention_mask=attn_mask, labels=None)
                vloss = F.cross_entropy(logits.float().view(-1, logits.size(-1)),
                                        y.view(-1)).item()
                val_losses.append(vloss)
        val_wall_s = time.perf_counter() - val_t0

        mean_val = sum(val_losses) / max(1, len(val_losses))
        # Bits per token (we report as bpb because gpt2 BPE bytes ≈ tokens
        # for English ASCII; readers familiar with bpb will understand it
        # as the right scale).
        val_bpb = mean_val / math.log(2)

        peak_alloc = torch.cuda.max_memory_allocated(device) / (1024**3)
        return {
            "ok": True,
            "params_m": round(n_params / 1e6, 2),
            "train_steps": cfg.steps,
            "train_loss_first": round(train_losses[0], 3),
            "train_loss_last": round(train_losses[-1], 3),
            "val_bpb": round(val_bpb, 4),
            "val_n_batches": len(val_losses),
            "mean_step_ms": round(sum(step_times) / len(step_times) * 1e3, 2),
            "train_wall_s": round(train_wall_s, 1),
            "val_wall_s": round(val_wall_s, 2),
            "peak_gpu_mem_gib": round(peak_alloc, 2),
        }

    except torch.cuda.OutOfMemoryError as e:
        return {"ok": False, "oom": True, "error": str(e)[:300]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "oom": False, "error": str(e)[:300],
                "trace_tail": traceback.format_exc()[-400:]}
    finally:
        try:
            del opt
            del model
        except Exception:  # noqa: BLE001
            pass
        gc.collect()
        torch.cuda.empty_cache()


if __name__ == "__main__":
    # Smoke test: run baseline once.
    import json
    import sys
    sys.path.insert(0, str(EVIDENCE))
    from cfg import BASELINE  # noqa: E402
    print("evaluating baseline cfg ...")
    m = evaluate(BASELINE)
    print(json.dumps(m, indent=2))
