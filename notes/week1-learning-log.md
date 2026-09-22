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

Code: `src/loader.py`, `src/chunker.py`, `scripts/02_chunking_demo.py`

```powershell
.\venv\Scripts\python.exe scripts\02_chunking_demo.py --folder sample-notes
```

### ⚠ Dataset caveat

`sample-notes/` was still empty when these measurements were taken, so the sweep
below ran against this project's own markdown docs in `.kiro/` — 7 files,
**55,598 characters** of real prose. **Re-run the sweep once my own notes are in
`sample-notes/`, and replace this table.** The README has to describe the dataset
actually shipped, and chunk counts depend entirely on the corpus.

Worth noting why this corpus is a poor benchmark beyond just being the wrong
data: it is *self-modifying*. Editing the spec files changes the thing being
measured. An earlier run of the same sweep reported 53,852 characters and 149
chunks at 500/100; after editing `tasks.md` and two steering files, the same
command reported 55,598 characters and 155 chunks. The lesson generalises — chunk
counts are a property of the corpus, not of the settings, so any figure quoted in
the README has to name the dataset it came from.

### Why splitting matters

_(REWRITE IN MY OWN WORDS. The brief asks me to note this myself, and the
self-check asks me to explain out loud why chunk size affects retrieved context
quality. The two arguments, with the evidence I produced for each:_

_Argument 1 — fixed-size embeddings. Monday's Part 2 showed 7 characters and 196
characters both produce 384 numbers. A 15,000-character document gets the same
384. Everything it covers is averaged into one position, so a document about
five topics sits in the bland middle of all five and matches none sharply._

_Argument 2 — relevance precision. Retrieval should hand the model the passage
that answers the question, not the file containing it. Part 5 below is the
evidence: the 1500-character chunk swept in an entire unrelated markdown table
alongside the relevant sentence._

_Do not submit the bracketed text — it is scaffolding.)_

### The boundary problem — the result worth showing

A 73-character fact was planted at chars 460–533 of a test document, straddling
the 500-character boundary:

| configuration | chunks | fact retrievable? |
| ------------- | ------ | ----------------- |
| 500 / 0, hard cuts | 2 | **NO CHUNK CONTAINS IT** |
| 500 / 0, softened boundaries | 2 | 1 chunk |
| 500 / 100, softened boundaries | 3 | 1 chunk |

Row 1 is the failure mode chunk tuning exists to prevent. The fact is present in
the document, split across two chunks, and therefore whole in neither. No
question can retrieve it, each fragment is too incomplete to score well, and
**nothing in the system reports a problem** — answers just quietly get worse.

Row 2 fixes it by luck: the splitter found a sentence break before the fact, so
the cut landed harmlessly. Only works when the text happens to have punctuation
near the boundary.

Row 3 fixes it on purpose. Overlap does not depend on the text cooperating.

### Chunk size / overlap experiments

Corpus: 7 markdown files, 55,598 characters.

| chunk size | overlap | chunks | mean len | min | max | stored chars | duplication |
| ---------- | ------- | ------ | -------- | --- | --- | ------------ | ----------- |
| 300 | 0 | 199 | 279.4 | 50 | 300 | 55,598 | 1.00x |
| 300 | 60 | 252 | 279.0 | 72 | 300 | 70,298 | 1.26x |
| 500 | 0 | 124 | 448.4 | 23 | 500 | 55,598 | 1.00x |
| 500 | 100 | 155 | 454.2 | 112 | 500 | 70,398 | **1.27x** |
| 800 | 160 | 96 | 727.5 | 292 | 800 | 69,838 | 1.26x |
| 1500 | 300 | 50 | 1370.0 | 348 | 1500 | 68,498 | 1.23x |

What the numbers say:

- **Overlap has a price.** Every 20% overlap setting stores ~1.26x the corpus.
  Roughly a quarter of what gets embedded is a second copy of text already
  stored. At zero overlap the stored total equals the corpus exactly (55,598 in,
  55,598 out) — a useful sanity check that the splitter is neither losing nor
  inventing text.
- **Chunk count scales roughly inversely with size**, as expected: 199 → 124 →
  96 → 50 as size goes 300 → 500 → 800 → 1500.
- **Mean length always falls short of the maximum** (454.2 against 500). That is
  boundary softening at work, cutting early to land on a paragraph or sentence
  break rather than mid-word.
- **The `min` column is a warning.** At 500/0 the shortest chunk is 23
  characters — the leftover tail of a file. A 23-character chunk carries almost
  no meaning, so it will either never be retrieved or, worse, be retrieved for
  the wrong reason. Worth checking against my own notes: many short files produce
  many near-useless tail chunks.
- **A second knob hides inside overlap.** Going 500/0 → 500/100 raised the chunk
  count 124 → 155. More chunks means more embedding calls and more competition
  for slots in top-k, since near-duplicate chunks can occupy several of them.

### Part 5 — the same passage at three sizes

Taken from `design.md`, 15,502 characters:

| chunk size | chunks from that file | what the sample chunk contained |
| ---------- | --------------------- | ------------------------------- |
| 300 | 71 | one tight idea: the numbered-citations rationale, nothing else |
| 500 | 44 | that idea plus the start of an unrelated markdown table |
| 1500 | 14 | the idea, the whole table, and two further sections |

This is the precision-versus-context tradeoff made concrete. Small chunks match
sharply but may omit context the answer needs. Large chunks carry their context
along and dilute the match — one relevant sentence averaged in with paragraphs
of unrelated material. No universally correct value; it depends on how the notes
are written.

### Provisional choice

**CHUNK_SIZE=500, CHUNK_OVERLAP=100.** Not final. Reasoning so far: 500 is large
enough that a sample chunk held a complete thought, small enough that it had not
yet absorbed a whole unrelated table the way 1500 did. 100 of overlap rescued
the planted fact in the boundary test. The 1.26x storage cost is irrelevant at
this corpus size.

This choice cannot be confirmed until Week 2, when real questions are run
against it. Retrieval quality is the only test that matters; every number above
is a proxy.

### PDF handling — verified

Tested against an 11-page PDF: 11 pages → 11 documents → 7,529 characters → 21
chunks at 500/100. Page numbers survive into citations, e.g.
`gen-ai-brochure.pdf#1 (p.2)`. Chunk numbering runs per *file* rather than per
page, so a multi-page PDF yields `#0, #1, #2...` instead of restarting at zero
on each page and colliding.

Not yet verified: a scanned PDF with no text layer. The code warns and skips by
name; OCR is out of scope.

### Two bugs found by running it

1. **`UnicodeEncodeError` on a `→` character.** The Windows console defaults to
   cp1252 and cannot encode arrows, em dashes or curly quotes. The chunking was
   correct; the crash came from trying to *display* the result. Fixed in
   `src/console.py` by switching stdout to UTF-8 with `errors="replace"` —
   substituting a placeholder glyph beats aborting, because a slightly wrong
   character still lets you read the chunk. This would have hit my own notes
   immediately.
2. **Infinite-loop risk in the boundary softener.** Cutting backwards for a
   natural boundary can, in principle, return a cut point before the overlap
   ends, leaving the next chunk starting at or before the current one. Guarded
   by flooring the search window at `overlap + 1`. Verified on a 2,000-character
   string containing no whitespace at all: 5 chunks, strides all positive.

Error paths also checked: `overlap >= chunk_size` rejected with an explanation,
`chunk_size=0` rejected, negative overlap rejected, missing folder reports the
resolved path, empty folder names the supported extensions, whitespace-only
chunks dropped before reaching the embedder.

---

## Fri — Wrap up Week 1

_(not started)_

### What "semantic search" means, in plain language

_(3–4 sentences, to fill in)_
