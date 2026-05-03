#!/usr/bin/env python3
"""A.2 microbench: tok/s for baseline-vLLM vs ESamp-vLLM on the same prompt budget.

Two modes — `baseline` (vanilla vLLM, no tLLM hooks) and `esamp` (full ESamp consumer
with post_filter_exact intervention). Each mode runs a steady-state generation and
reports total decode tokens / wallclock seconds. Run baseline and esamp in separate
processes so the install_runner_patch state can't leak across.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any


PROMPT = "Surprise me with an unexpected story about evil sorcerers and the brave hero."


def run_baseline(*, model_name: str, num_answers: int, max_new_tokens: int, max_model_len: int, gpu_mem: float) -> dict[str, Any]:
    from vllm import LLM, SamplingParams

    llm = LLM(
        model=model_name,
        dtype="bfloat16",
        gpu_memory_utilization=gpu_mem,
        max_model_len=max_model_len,
        enable_prefix_caching=False,
        enforce_eager=True,
        seed=2026,
    )
    prompts = [PROMPT] * num_answers
    params = [
        SamplingParams(n=1, temperature=0.8, top_p=0.95, top_k=-1, min_p=0.1, max_tokens=max_new_tokens, seed=None)
        for _ in range(num_answers)
    ]
    # Warmup pass
    _ = llm.generate(prompts, params, use_tqdm=False)
    # Timed pass
    t0 = time.perf_counter()
    outputs = llm.generate(prompts, params, use_tqdm=False)
    t1 = time.perf_counter()
    decode_tokens = sum(len(out.outputs[0].token_ids) for out in outputs)
    return {
        "mode": "baseline",
        "elapsed_s": t1 - t0,
        "decode_tokens": int(decode_tokens),
        "tok_per_s": float(decode_tokens) / (t1 - t0),
        "num_answers": num_answers,
        "max_new_tokens": max_new_tokens,
        "first_text": outputs[0].outputs[0].text,
    }


def run_esamp(*, model_name: str, num_answers: int, max_new_tokens: int, max_model_len: int, gpu_mem: float, beta: float) -> dict[str, Any]:
    from vllm import SamplingParams
    from tllm import make_llm
    from tllm.runtime import residual_runtime as runtime
    from tllm.util.tools import shutdown_llm_instance
    from tllm.workflows import esamp_support

    consumer = esamp_support.configure_esamp_runtime(
        graph_scratch_rows=max(64, num_answers),
        tap_layer_paths=["model.model.layers[0].input_layernorm", "model.model.layers[-1].input_layernorm"],
        source_layer_path="model.model.layers[0].input_layernorm",
        target_layer_path="model.model.layers[-1].input_layernorm",
        enable_esamp_training=True,
        distiller_hidden_dim=128,
        distiller_lr=1e-3,
        per_request_models=False,
        per_request_model_bank=True,
        model_bank_slots=num_answers,
        model_bank_flush_interval=1,
        model_bank_rank=64,
        model_bank_train_cudagraph=True,
        model_bank_forward_backend="torch",
        enable_distiller_intervention=True,
        distiller_beta=beta,
        distiller_sampler_backend="post_filter_exact",
    )
    llm = make_llm(
        model_name=model_name,
        dtype="bfloat16",
        gpu_memory_utilization=gpu_mem,
        max_model_len=max_model_len,
        enable_prefix_caching=False,
        enforce_eager=True,
        seed=2026,
    )
    prompts = [PROMPT] * num_answers
    params = [
        SamplingParams(n=1, temperature=0.8, top_p=0.95, top_k=-1, min_p=0.1, max_tokens=max_new_tokens, seed=None)
        for _ in range(num_answers)
    ]
    try:
        # Warmup
        _ = esamp_support.run_generate_with_request_mapping(
            llm, prompts, params,
            request_prompt_indices=[0] * num_answers,
            request_sample_indices=list(range(num_answers)),
        )
        runtime.synchronize_esamp()
        runtime.read_and_reset_esamp_stats(sync=True)
        runtime.read_and_reset_distiller_timing_stats(sync=True)
        # Timed pass
        t0 = time.perf_counter()
        outputs = esamp_support.run_generate_with_request_mapping(
            llm, prompts, params,
            request_prompt_indices=[0] * num_answers,
            request_sample_indices=list(range(num_answers)),
        )
        runtime.synchronize_esamp()
        t1 = time.perf_counter()
        stats = runtime.read_and_reset_esamp_stats(sync=True)
        timing = runtime.read_and_reset_distiller_timing_stats(sync=True)
        decode_tokens = sum(len(out.outputs[0].token_ids) for out in outputs)
        return {
            "mode": "esamp",
            "elapsed_s": t1 - t0,
            "decode_tokens": int(decode_tokens),
            "tok_per_s": float(decode_tokens) / (t1 - t0),
            "num_answers": num_answers,
            "max_new_tokens": max_new_tokens,
            "distiller_beta": beta,
            "loss_count": int(getattr(stats, "loss_count", 0)),
            "loss_avg": float(getattr(stats, "loss_avg", 0.0)),
            "port_publish_hit_count": int(getattr(timing, "port_publish_hit_count", 0)),
            "candidate_sample_count": int(getattr(timing, "candidate_sample_count", 0)),
            "candidate_token_count": int(getattr(timing, "candidate_token_count", 0)),
            "first_text": outputs[0].outputs[0].text,
        }
    finally:
        shutdown_llm_instance(llm, cooldown_s=0.0)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["baseline", "esamp"], required=True)
    p.add_argument("--model-name", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--num-answers", type=int, default=16)
    p.add_argument("--max-new-tokens", type=int, default=128)
    p.add_argument("--max-model-len", type=int, default=512)
    p.add_argument("--gpu-mem", type=float, default=0.4)
    p.add_argument("--beta", type=float, default=0.8)
    p.add_argument("--out", default="")
    args = p.parse_args()

    if args.mode == "baseline":
        result = run_baseline(
            model_name=args.model_name,
            num_answers=args.num_answers,
            max_new_tokens=args.max_new_tokens,
            max_model_len=args.max_model_len,
            gpu_mem=args.gpu_mem,
        )
    else:
        result = run_esamp(
            model_name=args.model_name,
            num_answers=args.num_answers,
            max_new_tokens=args.max_new_tokens,
            max_model_len=args.max_model_len,
            gpu_mem=args.gpu_mem,
            beta=args.beta,
        )

    print(json.dumps(result, indent=2))
    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
