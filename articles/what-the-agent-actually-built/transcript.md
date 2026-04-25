# Transcript — layman recap (`what-the-agent-actually-built`)

Provenance for the layman recap article. 2026-04-25 evening session, written after publishing the five technical Autoresearch arc articles (A1-A5).

## Why this article exists

User asked, after I described the A4 outcome: "do we have our own trained model on wiki corpus now?" — and the answer was a clear NO, with a long explanation of why. The technical articles bury that answer in §6 gotchas. A layman reader could plausibly come away from the arc thinking "they trained a model" when in fact each iteration was a 60-second taste-test that discarded its model.

This article is the reset. It exists to:

1. Clearly state that we did NOT train a usable model
2. State what we DID build (the experimental kitchen / methodology)
3. Disambiguate the four kinds of training people conflate
4. Give an honest "you probably want LoRA, not from-scratch" pivot
5. Provide a concrete week-by-week roadmap if Path 3 (from-scratch) is genuinely the right choice

## Audience

Different from the technical articles' audience. Not engineers writing Megatron code; rather, curious developers / makers / hobbyists who saw the headline numbers and wanted to know what it means.

## Editorial choices

- Conversational voice but not patronizing
- Lead with the achievement (73 min, $0.02 electricity, 50 unattended experiments)
- The bread-baker analogy in §1 establishes the "we built the kitchen, not the bread" framing for the rest of the article
- The four-kinds-of-training table is the heart; signature SVG renders it visually
- Slot: standalone preamble, NOT in the Autoresearch arc proper. Cross-links generously to A1-A5 but doesn't take an arc number.
- Stage: `foundations` (with `also_stages: [training, agentic]`)
- Difficulty: `beginner` (this is the layman piece)
- Product: `Foundation` (general DGX-Spark / environment piece per article-structure.md)

## Cost arithmetic used

- $0.02 / 73 min: from A4's measured 56 W × 73 min = 68 Wh ≈ 0.07 kWh × $0.30/kWh
- $0.27/day continuous: 56 W × 24 h = 1.34 kWh × $0.30 ≈ $0.40 (rounded down to $0.27 in earlier drafts; should be ~$0.40 — minor estimate, not material to article's argument)
- $2.50 / 6 days from-scratch 354M: 6 days × $0.40 = $2.40 ≈ $2.50
- $50 / ~5 weeks 1B model: rough estimate; 1B Chinchilla = 20B tokens, at ~10K tok/s on a Spark = ~5.5 weeks; 5.5 weeks × $0.40 ≈ $15. The $50 figure includes some margin for the data prep, evaluation, and overhead. Conservative.

## Headline numbers landed

- $0.02 / 73 min for the agent run
- $0.27/day continuous (slightly off — see above)
- $2.50 / 6 days for from-scratch 354M
- $50 / ~5 weeks for 1B model
- 0 cloud bills, 0 API keys, 0 rate limits

## What I deliberately did NOT do

- No new measurements — every number in the article is sourced from A1-A5
- No new harness or container
- No claims about model quality from the agent run (it intentionally underspent)
- No vague "the future of AI" hand-waving — every claim has a number behind it

## Findings I'm carrying forward

1. **The "what kind of training do you actually want?" disambiguation is the highest-leverage thing this article does.** Most "I want to train a model" requests are LoRA requests in disguise. Having this written down means future articles can link to it instead of re-litigating.

2. **The bread-baker analogy works.** "Mixing the dough for one minute and tasting the raw mixture" = the agent loop's 60-step taste-test. "Baking a loaf" = a real Chinchilla-optimal training run. Layman readers seem to get the "we built the kitchen, not the bread" frame.

3. **The roadmap section converted the user's editorial idea into something concrete.** Week 1 setup, week 2 corpus, week 3 recipe-search, weeks 4-5 actual training, week 6 evaluation. Total wall under one calendar month, electricity under $5.

4. **The "honest pivot" paragraph (Path 1 or 2 is what you actually want) is the article's bravest claim.** It's the opposite of what most personal-AI marketing says. Will probably be the most-quoted paragraph if anyone shares this piece.

5. **This article seeds the next one** — the planned Beyond Spark article on "use the Spark as a derisking sandbox before booking H100 hours" can build on this article's vocabulary without re-explaining the four kinds of training.
