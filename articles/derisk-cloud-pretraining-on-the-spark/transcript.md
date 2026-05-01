# Transcript — derisk-cloud-pretraining-on-the-spark

This article was written from a queued spec in
`handoff/2026-04-25-end-of-day-beyond-spark-queued.md` (lines 37–146). No
new GPU work was done — the piece is a math/economics deep dive that
extrapolates from prior measured Spark work into cloud pretraining cost
arithmetic.

## Source material

The spec carried over from the prior session:

- **Title and frontmatter:** as given in the handoff.
- **The argument in one paragraph:** lifted from the handoff, adjusted to
  honest cost numbers (see "Cost-arithmetic reconciliation" below).
- **Section structure:** the 8-section deep-dive shape from the handoff,
  re-anchored to the 3-phase Phase 1 / Phase 2 / Phase 3 framing the
  handoff also proposed.
- **Signature SVG:** SparkSandboxToCloud as a horizontal funnel — chosen
  over the "100 dots, 90 culled" alternative because the funnel
  visualizes the *act* of de-risking, which is the article's point.
- **Inline fn-diagram:** 3-phase timeline (Phase 1 / Phase 2 / Phase 3)
  with a dashed reject-path under Phase 1 and Phase 2 showing where the
  savings actually come from.
- **Evidence dir:** cost_arithmetic.py + .json + recipe_lab_template.py
  + README.md per the handoff spec.
- **Cross-links:** to A2 baseline-training-loop-on-spark, A3
  nemo-curator-training-data-prep, A4 autoresearch-agent-loop, A5
  guardrails-for-code-generation, the prior Beyond Spark piece
  (gpu-sizing-math-for-fine-tuning), and the layman recap
  (what-the-agent-actually-built).

## Cost-arithmetic reconciliation

The handoff's headline numbers ($50K final pretrain, $36K avoided cloud
sweep) were illustrative rather than computed. The published article uses
honest spot-rate arithmetic:

- **8× H100 spot at $2.50/hr × 168 hours** = **$3,360** for a one-week
  7B-class final pretrain. The $50K headline scales to a 70B Llama-class
  campaign on 1024 H100s for 21 days — also true, but a different
  campaign size than the 7B walked through the body.
- **Spark recipe-search at total cost-of-use** = **~$1.01 per 100 iters**
  (240 W sustained × $0.13/kWh + amortized $5K capex over 1.5 yr).
  Marginal electricity alone is $0.08.
- **Cloud sweep at proxy scale** = **~$6 single H100, ~$49 8-GPU node**
  per 100 iters — much smaller than the handoff's $400/iter, because at
  proxy scale the cloud sweep is also cheap. The honest savings argument
  is at *target scale* ($2,933 per 100-iter sweep on 8× H100) and at the
  expected-loss-from-blind-booking level (50% wrong-pick rate × final
  pretrain cost).

This reframing kept the article's argument intact (the Spark filter pays
for itself on the first prevented wrong-pick) while putting it on
defensible numerical ground.

## Files produced

```
articles/derisk-cloud-pretraining-on-the-spark/
├── article.md
├── assets/
├── evidence/
│   ├── README.md
│   ├── cost_arithmetic.py
│   ├── cost_arithmetic.json
│   ├── cost_arithmetic_ondemand_3wk.json
│   └── recipe_lab_template.py
├── screenshots/                  (empty — no UI in this piece)
└── transcript.md                 (this file)
src/components/svg/SparkSandboxToCloud.astro
```

No screenshots were taken — this article is pure prose + arithmetic +
diagrams. The signature thumbnail and the inline 3-phase timeline carry
the visual load.

## Verification log

Run before commit:

- `python3 evidence/cost_arithmetic.py` — produces the JSON the article
  quotes.
- `H100_HOURLY_USD=3.50 FINAL_NODE_HOURS=504 python3 evidence/cost_arithmetic.py`
  — produces the medium-campaign comparison.
- `bash scripts/verify_article.sh derisk-cloud-pretraining-on-the-spark`
  — frontmatter, image refs, secret scan, SVG invariants.
- `python3 ~/.claude/skills/nvidia-learn-stats/scripts/compute_stats.py`
  — refreshes the home infographic.
- `python3 ~/.claude/skills/tech-writer/scripts/refresh_readme.py` —
  refreshes the GitHub-rendered README.
