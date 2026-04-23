# Transcript — guardrails-on-the-retrieval-path

Working notes and command logs from the session that produced article #7. Cleaned for privacy per the scrub rules (no credentials, no personal identifiers, no system fingerprinting). The artifacts referenced here live under `evidence/` in this folder.

## Setup

The session began from the article #6 handoff (`handoff/2026-04-22-article6-bigger-generator-published.md`), which queued article #7 as "NeMo Guardrails on the retrieval path." The runtime smoke test from the handoff ran clean on session start — LLM NIM, Embed NIM, pgvector, and Astro dev server all up; Ollama and NemoClaw both correctly stopped; 45 GB free memory.

## Install — the only friction

`pip install nemoguardrails` pulls `annoy>=1.17.3` as a hard dependency. On aarch64 Python 3.12 there is no pre-built wheel, and the source build needs `Python.h`:

```
src/annoymodule.cc:17:10: fatal error: Python.h: No such file or directory
```

Fixed by `sudo apt-get install -y python3-dev build-essential`. After that, `pip install nemoguardrails` built `annoy` from source (a couple of seconds) and installed cleanly at `nemoguardrails==0.21.0`.

The first attempt to instantiate `LLMRails` failed with:

```
nemoguardrails.llm.models.langchain_initializer.ModelInitializationError:
  Failed to initialize model 'meta/llama-3.1-8b-instruct' with provider
  'openai' in 'chat' mode: Initializing ChatOpenAI requires the
  langchain-openai package. Please install it with `pip install
  langchain-openai`
```

The error is helpful; `pip install langchain-openai` is all that's needed. This got added to the article's install block so readers save the iteration.

## The probe config

Minimal working `config.yml` for a rail-free sanity check against the local NIM:

```yaml
models:
  - type: main
    engine: openai
    model: meta/llama-3.1-8b-instruct
    parameters:
      openai_api_base: http://localhost:8000/v1
      openai_api_key: nim-local

rails:
  input:  { flows: [] }
  output: { flows: [] }
```

And the probe:

```python
from nemoguardrails import RailsConfig, LLMRails
rails = LLMRails(RailsConfig.from_path('/tmp/gr-probe'))
result = rails.generate(messages=[{'role':'user','content':'Say hi in 5 words.'}])
# RESULT: {'role': 'assistant', 'content': 'Hello, how are you today?'}
```

The NIM answered; the rail wiring was confirmed.

## The three arc configs

Written in parallel: `config-sb/`, `config-wiki/`, `config-auto/`. Each holds a `config.yml` with the model config + declared flows, and a `rails.co` file with the Colang. The Colang is small — two or three `define flow` blocks per arc — and all the real logic is in the Python actions registered by `guardrails_ask.py`.

## Detectors are regex

Deliberately. The article argues for rails-as-scaffolding, and regex keeps the detector layer transparent. The five registered actions:

- `check_input_pii(text)` → SSN, credit card, email, phone patterns
- `check_output_pii(text)` → same patterns
- `check_wiki_style(text)` → hedging phrases, self-reference phrases, missing `Sources:` trailer
- `check_input_exec(text)` → `cat ~/.ssh`, `env | curl`, `curl | bash`, `/etc/{passwd,shadow}`, `AWS_(SECRET|ACCESS)_KEY`
- `check_output_code(text)` → `rm -rf /`, `sudo rm -rf`, `curl | bash`, `--no-verify`, `git push --force`, `dd if=/dev/zero`

The Colang flows dispatch to these via `execute <action_name>(text=$user_message)` on input and `text=$bot_message` on output.

## The wrapper and the retrieval reuse

`guardrails_ask.py` imports `hybrid_ask` from article #6's evidence directory via `sys.path.insert`. The retrieval pipeline — dense embed + pgvector cosine + BM25 + RRF + Nemotron rerank — is used verbatim. The only new code is the rails-wrapping layer and the per-arc config loading.

## Smoke tests

Ran one violating + one clean query per arc before the full benchmark:

```
=== SB: violating (has email) ===
answer: "I can't process content that contains personal identifiers..."
blocked_by_rail: pii

=== AUTO: exfil query (cat ~/.ssh) ===
answer: "Request blocked: the planner step asks for an exfiltration..."
blocked_by_rail: exec_intent

=== WIKI: with retrieval, well-supported question ===
answer: "Michael Phelps' quest to win eight gold medals is over, and he
         won seven gold medals at the Olympics. Sources: [601, 594, 626, 1185]"
blocked_by_rail: null
```

All three rails worked first try. The Wiki case was the one to worry about — the rail's output check requires a `Sources:` trailer, and the 8B's strict-context prompt from article #4 already instructs the model to emit one, so well-supported queries pass and bad-retrieval queries naturally fail (because the refusal string has no Sources). That dual-purpose behavior made it into the article as a "design-choice bonus."

## The benchmark

`benchmark.py` ran 15 synthetic queries — 5 per arc, 3 violating + 2 clean — through the full retrieval+generation chain. Per-arc summary:

```
arc     viol  clean  TB  FP  TP  FB  recall  clean_pass
sb         3      2   3   0   2   0     1.0         1.0
wiki       3      2   3   0   2   0     1.0         1.0
auto       3      2   3   0   2   0     1.0         1.0
```

15-for-15. The raw records are at `evidence/benchmark.json` and the log at `evidence/03-benchmark.log`. The number is a demo, not a proof — detector strength and a bigger adversarial set would both matter for a real confidence statement, and the article makes that clear in the tradeoffs section.

## Editorial decisions

- **One diagram, not two.** The signature (`RetrievalGuardrails.astro`) shows the three-lane + central rail topology; the in-body `fn-diagram` is the thesis hub-and-spoke. A second in-body diagram of the policy-trigger breakdown was sketched but removed — the prose + code-block evidence in the benchmark section was carrying the weight, and the ceiling is two per article.
- **Regex framed honestly.** The tradeoffs section explicitly calls out Presidio, Nemotron-Aegis, AST parsing as production upgrades. The article's claim is about the scaffolding, not the detectors.
- **Dropped the local-NIM Guardrails engine story.** Guardrails can use a separate model for rail-internal intent matching (the `main` vs. a `rails`-specific engine); the article uses one model for everything to keep the narrative minimal. A future polish could split the rail LLM from the main LLM.
- **Closed with the arc state-lines per the use-case-arc.md pattern.** The next article is the bridge (#8, `one-substrate-three-apps`).
