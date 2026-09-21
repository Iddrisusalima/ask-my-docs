# Week 1 Learning Log — Embeddings & Chunking

Week 1 runs **Mon Sep 21 – Sun Sep 27, 2026**.

> Note on dates: the project brief lists the start as Sep 14 and the deadline as
> Oct 4. Week 1 actually began Sep 21, so every week shifts forward by one:
> Week 1 = Sep 21–27, Week 2 = Sep 28–Oct 4, Week 3 = Oct 5–11. Deadline to be
> confirmed with mentor.

This file is where I write things in my own words. The brief asks for written
explanations at several points, and the final README pulls from here.

---

## Mon–Tue — Understand & generate embeddings

Script: `scripts/01_embedding_basics.py`
Backend chosen: `local` — Sentence Transformers, `all-MiniLM-L6-v2`, 384 dimensions.

### Why this backend

Free, no API key, and it runs on my machine, so I can re-embed as many times as
I want while experimenting with chunk sizes. The model downloads once (~90 MB)
and then works offline. OpenAI's `text-embedding-3-small` is also wired up in
`src/embedder.py` behind `EMBEDDING_BACKEND=openai` if I want to compare quality
later.

### What an embedding actually is

_(REWRITE THIS IN MY OWN WORDS — the self-check says I must explain it without
using "vector" as a cop-out. Draft below is a starting point to react to, not
something to submit as-is.)_

Draft: an embedding model reads text and returns a fixed-size list of numbers
that act as coordinates on a map of meaning. Text that means similar things gets
placed close together on that map, even when the wording is completely
different. The model learned the layout of the map during training, so the
coordinates are not something a human designed or can label one by one — only
the distances between points carry information.

### Cosine similarity results

From `python scripts/01_embedding_basics.py`, model `all-MiniLM-L6-v2` (384 numbers per text).

Group A (all about weekend baking):
- A1 "I bake sourdough bread every weekend."
- A2 "Most Saturdays you will find me making a loaf from scratch."
- A3 "Weekend baking is my favourite hobby."

Group B (mutually unrelated): tax deadline / Saturn's moons / rebooting a router.

| comparison | score |
| ---------- | ----- |
| A1 vs A2 | 0.6178 |
| A1 vs A3 | 0.6082 |
| A2 vs A3 | 0.6254 |
| B1 vs B2 | -0.0190 |
| B1 vs B3 | 0.1112 |
| B2 vs B3 | 0.0009 |
| **Group A internal average** | **0.6172** |
| **Group B internal average** | **0.0310** |
| **Gap** | **0.5861** |

Cross-group (A vs B) scores all landed between -0.058 and 0.063 — the lowest
numbers on the grid, which is exactly what should happen.

### What surprised me

1. A1 and A2 share almost no words. "sourdough bread every weekend" vs
   "Saturdays... a loaf from scratch" — one overlapping concept, zero useful
   keyword overlap. Keyword search would score that pair near nothing. It came
   out at 0.62. That single number is the reason semantic search beats keyword
   search for question answering.

2. Related sentences scored 0.62, not 0.95. I expected "similar" to mean "close
   to 1". It doesn't. 0.62 is a *strong* score for this model, and what makes it
   meaningful is the 0.03 baseline sitting underneath it. So I should rank
   candidates against each other rather than trusting a fixed threshold like
   "keep anything above 0.8" — that cutoff would have thrown away every correct
   match here.

3. Every vector came out with magnitude exactly 1.0000. MiniLM normalises its
   output, so for this model cosine similarity and the plain dot product give
   the same answer. Good to know, but I kept the full division in
   `src/similarity.py` so the code stays correct if I switch to a model that
   doesn't normalise.

4. B1 vs B2 was slightly *negative* (-0.019). Negative means pointing in
   mildly opposite directions. It's noise at that magnitude, not a meaningful
   signal.

---

## Wed–Thu — Chunking pipeline

_(not started)_

### Why splitting matters

_(to fill in — context limits, relevance precision)_

### Chunk size / overlap experiments

| chunk size | overlap | chunks produced | what I noticed |
| ---------- | ------- | --------------- | -------------- |

---

## Fri — Wrap up Week 1

_(not started)_

### What "semantic search" means, in plain language

_(3–4 sentences, to fill in)_
