#!/usr/bin/env python3
"""Fetch 1000 AG News rows via the Hugging Face datasets-server HTTP API.

AG News is a 120k-row text-classification corpus split across four topic
classes (World / Sports / Business / Sci/Tech). Each row is a short news
lead — tens of tokens — so the corpus doubles as a ground-truth signal for
recall testing: a query like "tennis" should land almost exclusively in the
Sports class under any reasonable embedder.

stdlib only; no datasets/HF-hub install required.
"""
import json
import time
import urllib.parse
import urllib.request

DATASET = "fancyzhx/ag_news"
CONFIG = "default"
SPLIT = "train"
PAGE = 100   # max allowed by datasets-server
TARGET = 1000
LABELS = {0: "World", 1: "Sports", 2: "Business", 3: "Sci/Tech"}

def fetch(offset, length, _retries=5):
    qs = urllib.parse.urlencode({
        "dataset": DATASET,
        "config": CONFIG,
        "split": SPLIT,
        "offset": offset,
        "length": length,
    })
    url = f"https://datasets-server.huggingface.co/rows?{qs}"
    delay = 2
    for attempt in range(_retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _retries - 1:
                print(f"  429 at offset {offset}, retry in {delay}s")
                time.sleep(delay)
                delay *= 2
                continue
            raise

def main():
    # Stratified sample: 250 per class. AG News's first-1k slice is skewed
    # heavily toward Sci/Tech, which would confound a recall benchmark because
    # a query about sports would have fewer true positives to land on.
    per_class = TARGET // len(LABELS)
    buckets = {name: [] for name in LABELS.values()}
    offset = 0
    while any(len(buckets[c]) < per_class for c in buckets):
        obj = fetch(offset, PAGE)
        if not obj.get("rows"):
            break
        for item in obj["rows"]:
            row = item["row"]
            cls = LABELS[row["label"]]
            if len(buckets[cls]) >= per_class:
                continue
            text = row["text"].replace("\\", " ").strip()
            buckets[cls].append({"id": item["row_idx"], "label": cls, "text": text})
        offset += PAGE
        time.sleep(0.6)  # polite; datasets-server rate-limits aggressively

    out = []
    for cls in LABELS.values():
        out.extend(buckets[cls])

    with open("corpus.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")

    # Class balance sanity check.
    tally = {}
    for r in out:
        tally[r["label"]] = tally.get(r["label"], 0) + 1
    print(f"wrote {len(out)} rows to corpus.jsonl")
    print("class balance:", tally)

if __name__ == "__main__":
    main()
