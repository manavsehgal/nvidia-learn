# Thread #2 follow-up — temperature=0 Fibonacci re-run

Ran 2026-04-22T19:12Z, after handoff resume. Same model / container / prompt.

## Prompt
"Write a Python one-liner that returns the nth Fibonacci number."

## Settings
- model: meta/llama-3.1-8b-instruct
- temperature: 0 (down from 0.7 in the original benchmark)
- max_tokens: 512

## Response (verbatim)
```python
def fibonacci(n): return (pow([[1, 1], [1, 0]], n - 1, mod=10**9 + 7))[0][0]
```

## Finding — hallucination is durable AND worse

At temperature=0 the model returns invalid Python:

1. `pow(x, y, z)` takes **scalars**, not a list-of-lists. There is no
   builtin matrix exponentiation in Python's `pow`.
2. `pow(...)` has no `mod=` keyword argument — the modulus is the third
   positional arg.
3. Result: the function raises `TypeError` on first call.

So the durability story isn't just "8B FP8 hallucinates a fancy helper at 0.7" —
it's **"the greedy decode is confidently wrong, and worse than the sampled
decode that at least produced runnable (if overkill) code."**

## Token counts
- prompt_tokens: 23
- completion_tokens: 205
- total_tokens: 228

## Implication for article angle
The honest frame: **Spark NIM ships fast (24.8 tok/s) and wrong** on constrained
code-prompts. Not a Spark defect — this is the 8B-FP8 model being small.
Cost: readers who grab this as their daily driver will spend real time
debugging imaginary APIs. Benefit: it's genuinely fast and genuinely local.

Reframe the Fibonacci moment in the article: show the temp=0.7 response (a
fabricated `fibonacci_matrix` helper), then the temp=0 response (invalid
`pow` call), then the correct one-liner for comparison:

```python
fib = lambda n: n if n < 2 else fib(n-1) + fib(n-2)
```

That three-step reveal is the article's most-memorable beat.
