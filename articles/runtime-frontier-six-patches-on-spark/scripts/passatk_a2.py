#!/usr/bin/env python3
"""A.2 Pass@k — HumanEval + AIME harness for baseline-vs-ESamp on patched vLLM 0.20.0.

Two modes (`baseline`, `esamp`), two tasks (`humaneval`, `aime`). HumanEval scores via
python sandbox exec; AIME scores via integer answer extraction (last \\boxed{N} or last
standalone int) against the gold answer. Outputs JSON with pass@1, pass@k, tok/s.

Usage:
    python3 passatk_a2.py --task humaneval --mode baseline --num-problems 164 --n 8 --out /tmp/pak-he-base.json
    python3 passatk_a2.py --task aime      --mode esamp    --num-problems 30  --n 8 --max-new-tokens 4096 --max-model-len 6144 --out /tmp/pak-aime-esamp.json
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import time
from typing import Any


# ---------- HumanEval ----------

def _extract_python_code(text: str, entry_point: str | None = None) -> str:
    fenced = re.findall(r"```(?:python|py)?\s*\n?(.*?)```", text, flags=re.DOTALL)
    if fenced:
        return fenced[0].strip()
    if entry_point:
        idx = text.find(f"def {entry_point}")
        if idx >= 0:
            return text[idx:].strip()
    return text.strip()


def _run_with_timeout(code: str, test_code: str, entry_point: str, timeout_s: float = 4.0) -> bool:
    full = code + "\n" + test_code + f"\ncheck({entry_point})\n"

    def _alarm(_signum, _frame):
        raise TimeoutError("solution timed out")

    namespace: dict[str, Any] = {}
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(int(timeout_s + 1))
    try:
        exec(compile(full, "<candidate>", "exec"), namespace)
        return True
    except Exception:
        return False
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _humaneval_prompt(problem: dict[str, Any]) -> str:
    return (
        "You are a Python expert. Complete the function below. "
        "Return ONLY the full function body in a fenced ```python block; do not add prose.\n\n"
        f"{problem['prompt']}"
    )


def _humaneval_grade(text: str, problem: dict[str, Any]) -> bool:
    code = _extract_python_code(text, problem.get("entry_point"))
    return _run_with_timeout(code, problem["test"], problem["entry_point"])


# ---------- AIME ----------

_BOXED_RE = re.compile(r"\\boxed\{\s*(-?\d+)\s*\}")
_FINAL_INT_RE = re.compile(r"(?<![\w.])(-?\d+)(?![\w.])")


def _aime_prompt(problem: dict[str, Any]) -> str:
    return (
        "Solve the problem below. Show clear reasoning, then write the final integer answer "
        "(in the range 000–999) inside \\boxed{...} on its own line.\n\n"
        f"{problem['Problem']}"
    )


def _extract_aime_answer(text: str) -> int | None:
    boxed = _BOXED_RE.findall(text)
    if boxed:
        try:
            return int(boxed[-1])
        except ValueError:
            pass
    ints = _FINAL_INT_RE.findall(text)
    for tok in reversed(ints):
        try:
            v = int(tok)
        except ValueError:
            continue
        if 0 <= v <= 999:
            return v
    return None


def _aime_grade(text: str, problem: dict[str, Any]) -> bool:
    pred = _extract_aime_answer(text)
    if pred is None:
        return False
    try:
        gold = int(problem["Answer"])
    except (KeyError, TypeError, ValueError):
        return False
    return pred == gold


# ---------- task dispatch ----------

def _load_problems(task: str, num_problems: int) -> list[tuple[str, dict[str, Any]]]:
    if task == "humaneval":
        from human_eval.data import read_problems
        all_problems = read_problems()
        keys = sorted(all_problems.keys(), key=lambda k: int(k.split("/")[1]))[:num_problems]
        return [(k, all_problems[k]) for k in keys]
    if task == "aime":
        from datasets import load_dataset
        ds = load_dataset("Maxwell-Jia/AIME_2024")["train"]
        rows = list(ds)[:num_problems]
        return [(str(r["ID"]), r) for r in rows]
    raise ValueError(f"unknown task: {task}")


def _prompt_builder(task: str):
    return {"humaneval": _humaneval_prompt, "aime": _aime_prompt}[task]


def _grader(task: str):
    return {"humaneval": _humaneval_grade, "aime": _aime_grade}[task]


def _pass_at_k(n: int, c: int, k: int) -> float:
    if n - c < k:
        return 1.0
    import math
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


# ---------- runners ----------

def _flatten(problems, n, build_prompt):
    flat_prompts: list[str] = []
    flat_pi: list[int] = []
    flat_si: list[int] = []
    for pi, (_task_id, problem) in enumerate(problems):
        prompt = build_prompt(problem)
        for si in range(n):
            flat_prompts.append(prompt)
            flat_pi.append(pi)
            flat_si.append(si)
    return flat_prompts, flat_pi, flat_si


def _score(outputs, problems, n, flat_pi, grade):
    by_problem: list[list[Any]] = [[] for _ in range(len(problems))]
    decode_tokens = 0
    for pi, out in zip(flat_pi, outputs):
        decode_tokens += len(out.outputs[0].token_ids)
        by_problem[pi].append(out)
    rows: list[dict[str, Any]] = []
    for (task_id, problem), outs in zip(problems, by_problem):
        passed = 0
        first_pred = None
        for i, out in enumerate(outs):
            ok = grade(out.outputs[0].text, problem)
            if ok:
                passed += 1
            if i == 0:
                first_pred = out.outputs[0].text[-200:]  # tail for debugging
        rows.append({"task_id": task_id, "n": n, "passed": passed, "first_pred_tail": first_pred})
    return rows, decode_tokens


def run_baseline(*, task: str, model_name: str, problems, n, max_new_tokens, max_model_len, gpu_mem) -> dict[str, Any]:
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
    flat_prompts, flat_pi, _flat_si = _flatten(problems, n, _prompt_builder(task))
    flat_params = [
        SamplingParams(n=1, temperature=0.8, top_p=0.95, top_k=-1, min_p=0.1, max_tokens=max_new_tokens, seed=None)
        for _ in flat_prompts
    ]
    t0 = time.perf_counter()
    outputs = llm.generate(flat_prompts, flat_params, use_tqdm=False)
    t1 = time.perf_counter()
    rows, decode_tokens = _score(outputs, problems, n, flat_pi, _grader(task))
    return {
        "task": task,
        "mode": "baseline",
        "model_name": model_name,
        "elapsed_s": t1 - t0,
        "decode_tokens": int(decode_tokens),
        "tok_per_s": float(decode_tokens) / (t1 - t0),
        "pass_at_1": sum(_pass_at_k(r["n"], r["passed"], 1) for r in rows) / len(rows),
        "pass_at_k": sum(_pass_at_k(r["n"], r["passed"], n) for r in rows) / len(rows),
        "k": n,
        "problems": rows,
    }


def run_esamp(*, task: str, model_name: str, problems, n, max_new_tokens, max_model_len, gpu_mem, beta) -> dict[str, Any]:
    from vllm import SamplingParams
    from tllm import make_llm
    from tllm.runtime import residual_runtime as runtime
    from tllm.workflows import esamp_support

    total_rows = max(64, len(problems) * n)
    esamp_support.configure_esamp_runtime(
        graph_scratch_rows=total_rows,
        tap_layer_paths=["model.model.layers[0].input_layernorm", "model.model.layers[-1].input_layernorm"],
        source_layer_path="model.model.layers[0].input_layernorm",
        target_layer_path="model.model.layers[-1].input_layernorm",
        enable_esamp_training=True,
        distiller_hidden_dim=128,
        distiller_lr=1e-3,
        per_request_models=False,
        per_request_model_bank=True,
        model_bank_slots=total_rows,
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
    flat_prompts, flat_pi, flat_si = _flatten(problems, n, _prompt_builder(task))
    flat_params = [
        SamplingParams(n=1, temperature=0.8, top_p=0.95, top_k=-1, min_p=0.1, max_tokens=max_new_tokens, seed=None)
        for _ in flat_prompts
    ]
    t0 = time.perf_counter()
    outputs = esamp_support.run_generate_with_request_mapping(
        llm, flat_prompts, flat_params,
        request_prompt_indices=flat_pi,
        request_sample_indices=flat_si,
    )
    runtime.synchronize_esamp()
    t1 = time.perf_counter()
    stats = runtime.read_and_reset_esamp_stats(sync=True)
    timing = runtime.read_and_reset_distiller_timing_stats(sync=True)
    rows, decode_tokens = _score(outputs, problems, n, flat_pi, _grader(task))
    return {
        "task": task,
        "mode": "esamp",
        "model_name": model_name,
        "distiller_beta": beta,
        "elapsed_s": t1 - t0,
        "decode_tokens": int(decode_tokens),
        "tok_per_s": float(decode_tokens) / (t1 - t0),
        "pass_at_1": sum(_pass_at_k(r["n"], r["passed"], 1) for r in rows) / len(rows),
        "pass_at_k": sum(_pass_at_k(r["n"], r["passed"], n) for r in rows) / len(rows),
        "k": n,
        "loss_count_total": int(getattr(stats, "loss_count", 0)),
        "port_publish_hit_count_total": int(getattr(timing, "port_publish_hit_count", 0)),
        "candidate_token_count_total": int(getattr(timing, "candidate_token_count", 0)),
        "problems": rows,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--task", choices=["humaneval", "aime"], default="humaneval")
    p.add_argument("--mode", choices=["baseline", "esamp"], required=True)
    p.add_argument("--model-name", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--num-problems", type=int, default=20)
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--max-new-tokens", type=int, default=300)
    p.add_argument("--max-model-len", type=int, default=1024)
    p.add_argument("--gpu-mem", type=float, default=0.5)
    p.add_argument("--beta", type=float, default=0.8)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--out", default="")
    args = p.parse_args()

    problems = _load_problems(args.task, args.num_problems)

    if args.mode == "baseline":
        result = run_baseline(
            task=args.task,
            model_name=args.model_name,
            problems=problems,
            n=args.n,
            max_new_tokens=args.max_new_tokens,
            max_model_len=args.max_model_len,
            gpu_mem=args.gpu_mem,
        )
    else:
        result = run_esamp(
            task=args.task,
            model_name=args.model_name,
            problems=problems,
            n=args.n,
            max_new_tokens=args.max_new_tokens,
            max_model_len=args.max_model_len,
            gpu_mem=args.gpu_mem,
            beta=args.beta,
        )

    print(json.dumps({k: v for k, v in result.items() if k != "problems"}, indent=2))
    print(
        f"\n# task={result['task']} mode={result['mode']} model={result['model_name']} "
        f"pass_at_1={result['pass_at_1']:.4f} pass_at_{result['k']}={result['pass_at_k']:.4f} "
        f"tok/s={result['tok_per_s']:.1f}"
    )
    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
