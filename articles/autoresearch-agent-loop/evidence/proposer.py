"""
Proposer — calls NIM Llama 3.1 8B at localhost:8000 with the
perturbation menu + recent trajectory; asks for ONE structured proposal
JSON {knob, new_value, reason}.

Returns the raw text the LLM produced (as a string). The string is
*never* trusted — it goes straight into A5's `gate()` which performs
the schema/menu/range/cross/diff lint checks. This module only handles
the network call + prompt construction.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

EVIDENCE = Path(__file__).resolve().parent
A5_EVIDENCE = Path(os.environ.get(
    "A5_EVIDENCE",
    str(EVIDENCE.parent.parent / "guardrails-for-code-generation" / "evidence"),
))
MENU_PATH = A5_EVIDENCE / "perturbation_menu.json"

NIM_BASE = os.environ.get("NIM_BASE", "http://localhost:8000")
MODEL = os.environ.get("AGENT_MODEL", "meta/llama-3.1-8b-instruct")


def _menu_lines() -> str:
    with open(MENU_PATH) as f:
        menu = json.load(f)
    out = []
    for knob, spec in menu["knobs"].items():
        if "choices" in spec:
            domain = "choices=" + str(spec["choices"])
        else:
            domain = f"range=[{spec['range'][0]}, {spec['range'][1]}]"
        out.append(f"  - {knob}  ({spec['type']}, {domain})  default={spec['default']}  // {spec['doc']}")
    return "\n".join(out)


def _history_lines(history: list[dict], k: int = 5) -> str:
    if not history:
        return "(no prior iterations yet)"
    recent = history[-k:]
    out = []
    for h in recent:
        if h.get("verdict_ok"):
            outcome = (f"applied; val_bpb {h.get('baseline_val_bpb', '?')}→{h.get('val_bpb', '?')}; "
                       f"decision={h.get('decision', '?')}")
        else:
            outcome = f"BLOCKED by {h.get('rail', '?')}: {h.get('reason', '?')[:60]}"
        proposal_str = (
            f"{h['proposal']['knob']}={h['proposal']['new_value']}"
            if h.get("proposal") else "(parse failed)"
        )
        out.append(f"  iter {h['iter']:>3d}  {proposal_str:<28s}  {outcome}")
    return "\n".join(out)


SYSTEM_PROMPT = """You are an autonomous training-loop research agent. Your job is to find a
small perturbation to a 354M-parameter GPT pretrain configuration that
lowers validation cross-entropy on a held-out wikitext-103 slice.

You can twist exactly ONE knob per iteration. Your output MUST be a
single JSON object on one line, with exactly these three keys:

    {"knob": "<knob name>", "new_value": <value>, "reason": "<one short sentence>"}

Constraints:
- knob must be from the allowlist below
- new_value must be the right type and within the declared range or choices
- reason is a single sentence, ≤ 200 characters
- DO NOT output anything else — no preamble, no markdown, no code block fences
- DO NOT propose the same knob and value as the last accepted state

If you cannot decide, propose the most informative change you have not tried."""


def build_prompt(history: list[dict], baseline_cfg: dict, recent_k: int = 5) -> list[dict]:
    user = f"""## Allowlisted knobs

{_menu_lines()}

## Current cfg (baseline since last accepted change)

{json.dumps(baseline_cfg, indent=2)}

## Recent iterations

{_history_lines(history, k=recent_k)}

## Your task

Propose ONE knob change that you think will improve val_bpb. Output JSON only."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user},
    ]


def call_nim(messages: list[dict], temperature: float = 0.5,
             max_tokens: int = 200, timeout_s: int = 60) -> dict:
    """Call NIM's OpenAI-compatible /v1/chat/completions and return
    {ok, text, latency_s, error?}."""
    import time
    url = f"{NIM_BASE}/v1/chat/completions"
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    t0 = time.perf_counter()
    try:
        r = requests.post(url, json=payload, timeout=timeout_s)
        latency_s = round(time.perf_counter() - t0, 2)
        if r.status_code != 200:
            return {"ok": False, "text": "", "latency_s": latency_s,
                    "error": f"http {r.status_code}: {r.text[:200]}"}
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return {"ok": True, "text": text, "latency_s": latency_s}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "text": "", "latency_s": round(time.perf_counter() - t0, 2),
                "error": f"network: {e}"}


def propose(history: list[dict], baseline_cfg: dict) -> dict:
    """Top-level: build prompt, call NIM, return raw response dict."""
    msgs = build_prompt(history, baseline_cfg)
    return call_nim(msgs)


if __name__ == "__main__":
    # Smoke test: build a prompt with empty history + call NIM once.
    sys.path.insert(0, str(EVIDENCE))
    from cfg import BASELINE  # noqa: E402

    print("=== prompt ===")
    msgs = build_prompt([], BASELINE.to_dict())
    for m in msgs:
        print(f"\n[{m['role']}]")
        print(m["content"][:1200])
        print("...")
    print("\n=== calling NIM ===")
    r = call_nim(msgs)
    print(json.dumps(r, indent=2))
