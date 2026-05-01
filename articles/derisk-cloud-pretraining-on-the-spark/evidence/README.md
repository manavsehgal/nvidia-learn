# Evidence — derisking a cloud pretrain on the Spark

Three files here. Two are the article's headline tables; one is a sketch
for adapting the A4 agent loop to a 7B-shaped cloud target.

## cost_arithmetic.py

Computes the three cost tables the article quotes. Cloud rates and Spark
amortization are env vars so the math stays reproducible at any rate
envelope. From this directory:

```bash
python3 cost_arithmetic.py > cost_arithmetic.json
```

Headline run uses spot-rate H100 ($2.50/hr per GPU), 168-hour final
pretrain (one week of 8×H100 for a 7B Llama-style Chinchilla run), 1.5-yr
Spark amortization horizon, 240W sustained training draw, $0.13/kWh US
average. Override any of those:

```bash
H100_HOURLY_USD=4.00 FINAL_NODE_HOURS=336 python3 cost_arithmetic.py
```

### What the numbers mean

- **`per_iter_usd`** — cost per single 60-step taste-test iteration
  (~88 seconds on Spark, equivalent on each cloud config)
- **`campaign_100_iters_usd`** — what a 100-candidate recipe-search costs
  on each substrate
- **`final_pretrain_usd.8xh100_one_week`** — the cloud bill if the chosen
  architecture trains for the configured wall time
- **`expected_value_argument`** — net savings if the Spark filter prevents
  one wrong final-training booking, assuming a 50% wrong-pick rate without
  the filter

## cost_arithmetic.json

Output of the headline run, regenerated whenever the script is rerun. The
article quotes rounded versions of these.

## cost_arithmetic_ondemand_3wk.json

Output for a larger campaign — on-demand H100 ($3.50/hr per GPU), 3-week
final-training duration. Used to show the argument scales: bigger campaign,
bigger savings, same Spark sweep cost. The Spark-cost line stays at $1.01;
expected savings climb from ~$1.7K (small campaign) to ~$7K (medium) to
$1M+ (a full 70B Llama-class campaign on 1024 GPUs for 21 days, which the
script can also model — set `FINAL_NODE_HOURS` and `H100_HOURLY_USD`
accordingly).

## recipe_lab_template.py

Sketch — not a runnable script. Shows how to point the A4 agent loop at a
7B-shaped target architecture: a `TargetArchitecture` dataclass, a
`ProxyMenu` for the Spark search, and a `project_to_target` function that
maps Spark-measured shapes onto the cloud-target dimensions. Copy the
relevant pieces into `articles/autoresearch-agent-loop/evidence/agent_loop.py`
when you're running a real recipe-lab session.

## Reproduction notes

- The Spark electricity figure (240W) is the system draw observed during
  A4's 50-iter agent loop, not the GB10's TDP (which is higher peak but
  rarely sustained during normal training).
- The amortization line treats the Spark as a 1.5-year-useful-life capital
  asset. Shorter horizons make the per-iter line look cheaper; longer
  horizons (and serious utilization) make it look essentially free.
- Cloud rates are spot-class; on-demand is typically 1.4–2× higher.
  Reserved capacity is similar to spot for sustained workloads but locks
  you in. The script's defaults track Lambda Labs / RunPod / CoreWeave
  spot-rate envelopes as of 2025–2026.
- "Wrong pick rate" of 50% is conservative — real-world architectural
  search without prior signal often picks losing configurations more than
  half the time. With the Spark filter cutting that rate to (say) 10%,
  the expected savings number multiplies.
