# Frontier Scout — paper triage

_Last refresh: 2026-05-02 · 21 papers tracked · [run history](runs/index.md)_

## Recommended dive-deep candidates

These are the papers most worth running through `/frontier-scout eval <id>` next, ranked by combined relevance × popularity × verdict-feasibility:

1. **[Heterogeneous Scientific Foundation Model Collaboration](2604.27351/paper.md)** · 181 upv · spark-feasible · Autoresearch
   _Lightweight LLM-orchestrator over domain foundation models is software glue that fits NemoClaw/NIM; underlying scientific FMs would be hosted as endpoints._
2. **[ClawGym: A Scalable Framework for Building Effective Claw Agents](2604.26904/paper.md)** · 44 upv · spark-feasible · Autoresearch
   _Claw-style sandboxed agent SFT + lightweight RL on per-task sandboxes maps directly onto NemoClaw + NeMo fine-tuning within the 128 GB envelope._
3. **[Large Language Models Explore by Latent Distilling](2604.24927/paper.md)** · 59 upv · spark-feasible · LLM Wiki
   _Lightweight test-time distiller plus reweighted sampling on existing open-weight reasoning models fits comfortably within Spark's 128 GB inference envelope._
4. **[AutoResearchBench: Benchmarking AI Agents on Complex Scientific Literature Discovery](2604.25256/paper.md)** · 27 upv · spark-feasible · Autoresearch
   _Agent-driven literature discovery benchmark fits Autoresearch arc; runnable on Spark via NemoClaw + NIM + NeMo Retriever with pgvector, no training needed._
5. **[Claw-Eval-Live: A Live Agent Benchmark for Evolving Real-World Workflows](2604.28139/paper.md)** · 22 upv · spark-feasible · Autoresearch
   _Live agent benchmark with execution traces and graders maps cleanly onto NemoClaw/OpenClaw sandboxed agents on Spark for local workflow eval._

## What's new this run

See [runs/2026-05-02/refresh-summary.md](runs/2026-05-02/refresh-summary.md).

## Full listing

### Foundations (1)

#### spark-feasible (1)

- [2604.24954](2604.24954/paper.md) · 20 · Nemotron 3 Nano Omni: Efficient and Open Multimodal Intelligence
  _Native NVIDIA Nemotron 3 Nano Omni 30B-A3B MoE shipped with BF16/FP8/FP4 — FP4 weights (~15 GB) leave ample 128 GB headroom for KV + multimodal context._

### LLM Wiki (4)

#### spark-feasible (4)

- [2604.24927](2604.24927/paper.md) · 31 · Large Language Models Explore by Latent Distilling
  _Lightweight test-time distiller plus reweighted sampling on existing open-weight reasoning models fits comfortably within Spark's 128 GB inference envelope._
- [2604.27039](2604.27039/paper.md) · 22 · Length Value Model: Scalable Value Pretraining for Token-Level Lengt
  _Token-level length value head over a 7B model is a small auxiliary network atop standard inference — comfortably inside Spark's envelope._
- [2604.26779](2604.26779/paper.md) · 15 · Accelerating RL Post-Training Rollouts via System-Integrated Specula
  _Speculative decoding inside NeMo-RL with vLLM at 8B scale is exactly Spark-class — 8B target + small draft model fit comfortably in 128 GB._
- [2604.27251](2604.27251/paper.md) · 14 · Compliance versus Sensibility: On the Reasoning Controllability in L
  _Behavioral study of induction/deduction/abduction conflicts in LLMs is a pure-inference replication runnable against any NIM-hosted model._

### Autoresearch (11)

#### spark-feasible (10)

- [2604.27351](2604.27351/paper.md) · 41 · Heterogeneous Scientific Foundation Model Collaboration
  _Lightweight LLM-orchestrator over domain foundation models is software glue that fits NemoClaw/NIM; underlying scientific FMs would be hosted as endpoints._
- [2604.26904](2604.26904/paper.md) · 30 · ClawGym: A Scalable Framework for Building Effective Claw Agents
  _Claw-style sandboxed agent SFT + lightweight RL on per-task sandboxes maps directly onto NemoClaw + NeMo fine-tuning within the 128 GB envelope._
- [2604.25256](2604.25256/paper.md) · 26 · AutoResearchBench: Benchmarking AI Agents on Complex Scientific Lite
  _Agent-driven literature discovery benchmark fits Autoresearch arc; runnable on Spark via NemoClaw + NIM + NeMo Retriever with pgvector, no training needed._
- [2604.28139](2604.28139/paper.md) · 25 · Claw-Eval-Live: A Live Agent Benchmark for Evolving Real-World Workf
  _Live agent benchmark with execution traces and graders maps cleanly onto NemoClaw/OpenClaw sandboxed agents on Spark for local workflow eval._
- [2604.28158](2604.28158/paper.md) · 21 · Intern-Atlas: A Methodological Evolution Graph as Research Infrastru
  _Method-evolution graph extraction is an LLM-over-corpus pipeline that maps directly onto NIM + NeMo Retriever + pgvector on Spark, on a subset._
- [2604.27419](2604.27419/paper.md) · 18 · InteractWeb-Bench: Can Multimodal Agent Escape Blind Execution in In
  _Multimodal agent benchmark with persona-driven instructions runs on Spark via NemoClaw + NIM-served MLLMs without training._
- [2604.28181](2604.28181/paper.md) · 18 · Synthetic Computers at Scale for Long-Horizon Productivity Simulatio
  _Synthetic-computer long-horizon agent sims map directly onto OpenShell sandboxes inside NemoClaw, with NIM-hosted Nemotron driving the loop._
- [2604.27151](2604.27151/paper.md) · 17 · Step-level Optimization for Efficient Computer-use Agents
  _Routing routine GUI steps to a small policy and reserving the big MLLM for high-risk steps is exactly the kind of single-Spark optimization the blog studies._
- [2604.25135](2604.25135/paper.md) · 17 · FAMA: Failure-Aware Meta-Agentic Framework for Open-Source LLMs in I
  _Failure-trajectory analysis + targeted helper agents over open-source LLMs runs cleanly atop NemoClaw with a Spark-hosted Nemotron._
- [2604.24658](2604.24658/paper.md) · 16 · The Last Human-Written Paper: Agent-Native Research Artifacts
  _Agent-native research artifact protocol is process + tooling — implementable as a NemoClaw skill atop NIM-hosted reasoning models on Spark._

#### borderline (1)

- [2604.26752](2604.26752/paper.md) · 35 · GLM-5V-Turbo: Toward a Native Foundation Model for Multimodal Agents
  _GLM-5V-Turbo is a frontier multimodal agent model; only borderline for Spark inference depending on released parameter count and quantization._

### Looking Beyond Spark (1)

#### borderline (1)

- [2604.27085](2604.27085/paper.md) · 26 · Efficient Training on Multiple Consumer GPUs with RoundPipe
  _Multi-consumer-GPU pipeline-parallel scheduler doesn't run on Spark's single GB10, but the throughput math extrapolates cleanly into Looking Beyond Spark._

### Frontier Scout (4)

#### borderline (4)

- [2604.26951](2604.26951/paper.md) · 29 · Turning the TIDE: Cross-Architecture Distillation for Diffusion Larg
  _8B dense and 16B MoE teachers distilling into 0.6B student fits the 128 GB envelope, but full TIDE training pipeline is heavy and dLLM tooling on NeMo is unproven._
- [2604.27083](2604.27083/paper.md) · 28 · Co-Evolving Policy Distillation
  _Co-evolving multiple experts in parallel during RLVR is memory-heavy; whether it fits the 128 GB unified pool depends on expert sizes._
- [2604.27505](2604.27505/paper.md) · 23 · Leveraging Verifier-Based Reinforcement Learning in Image Editing
  _CoT reasoning verifier RM + RLHF for image editing is multi-stage and image-domain; whether it fits depends on backbone scale._
- [2604.25719](2604.25719/paper.md) · 20 · Step-Audio-R1.5 Technical Report
  _Audio reasoning post-training fits NeMo's speech surface but RLVR-on-audio at scale is a non-trivial Spark workload._

## Stats

| Metric | Value |
|--------|------:|
| Total tracked | 21 |
| spark-feasible | 15 |
| borderline | 6 |

## Run history

[Append-only refresh log →](runs/index.md)
