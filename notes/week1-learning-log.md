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

> **DRAFT — rewrite in my own voice before submitting.** The self-check asks me to
> explain this without using "vector" as a cop-out, and a mentor will ask a
> follow-up. Borrowed phrasing fails at the follow-up, not at the first sentence.

An embedding is what you get when a model reads text and turns it into a position
on a map of meaning. Text that means similar things lands in nearby positions,
even when the actual words are completely different. The model worked out the
layout of that map during training, so nobody chose what each number stands for —
and one number on its own tells you nothing. What carries the information is how
close two pieces of text end up to each other.

**Follow-ups I should be ready for:**

- *What makes two things land near each other?* The model was trained on huge
  amounts of text and learned which words and phrases appear in similar
  situations. Nobody programmed the positions.
- *Why 384 numbers?* That is just what this model outputs. A larger model uses
  more and captures finer distinctions, at more cost. The important part is that
  the count never changes with input length.
- *Is this just a search index?* No. A search index stores words. This stores a
  position, which is why two passages can be close together with no words in
  common.

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

> **DRAFT — rewrite in my own voice before submitting.**

There are two reasons, and they push the same way.

First, an embedding is always the same size. Monday's run showed 7 characters and
196 characters both coming back as 384 numbers — and a 15,000-character document
gets the same 384. Everything the document discusses is averaged into one
position, so a file covering five topics sits in the bland middle of all five and
matches none of them sharply.

Second, retrieval should hand the model the passage that answers the question, not
the file that contains it. Everything else in that file is noise: it costs money,
fills the context window, and pulls the model's attention away from the part that
actually matters. Part 5 below is the evidence — the 1500-character chunk dragged
in an entire unrelated table alongside the one relevant sentence.

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

Script: `scripts/03_embed_chunks_memory.py`

```powershell
.\venv\Scripts\python.exe scripts\03_embed_chunks_memory.py --folder sample-notes
```

A complete semantic search engine with no database in it. The store is a list of
dicts; the search is a `for` loop over Monday's `cosine_similarity`. Built this
way deliberately, so that when Chroma arrives on Monday I know exactly which loop
it replaced.

Same corpus caveat as Wed–Thu: ran against `.kiro/` (7 files, 55,598 chars, 155
chunks at 500/100), not my own notes.

### What "semantic search" means, in plain language

> **DRAFT — rewrite in my own voice before submitting.** This is also the opening
> line of the demo video, so it needs to sound like me talking, not like a
> definition being read out.

Semantic search looks for text that *means* the same thing as your question,
rather than text that happens to use the same words. My own measurements showed
it: two sentences about weekend baking scored 0.618 against each other despite
sharing no useful words, while sentences on unrelated topics scored about 0.03. So
when I ask my notes a question, the tool is not scanning for keywords — it is
comparing meaning and ranking passages by how close they come. That is why it can
find the right paragraph even when I phrase the question completely differently
from how I originally wrote the note.

**The honest caveat**, worth saying if asked: it has no idea whether being related
actually answers the question. Asking about "Sundays" pulled up a chunk containing
"Sun Oct 4" — genuinely related in meaning, completely useless as an answer.

### The store, measured

| | |
| --- | --- |
| Chunks embedded | 155 |
| Numbers per chunk | 384 |
| Numbers in the store | 59,520 |
| Time to embed all of them | **29.90s** (192.9ms per chunk) |
| Store type | `list` of `dict` |

Each entry holds three things: the 384 numbers, the chunk text, and where it came
from. A vector database stores exactly the same three things — the difference is
only how it searches them.

192.9ms per chunk on CPU is the number that justifies choosing local embeddings
for experimentation but would not survive a large corpus. Ingestion is a one-time
cost per change to the notes, so it is tolerable; it would not be if it ran per
query.

### Search timing — and why the two phases must be timed separately

| phase | time | scales with corpus? |
| ----- | ---- | ------------------- |
| Embedding the question | ~27ms | **no** — fixed cost |
| Scanning all 155 chunks | ~15ms | **yes** |
| Per comparison | 95.0µs | — |

Embedding the question is 65% of the current total. My first version of the script
timed both together and divided by chunk count, which produced a per-comparison
figure roughly 3x too high and a scaling projection that was simply wrong. Worth
remembering: a fixed cost mixed into a per-item measurement makes small corpora
look slow and large ones look fast.

Projecting the scan alone:

| corpus | comparisons | projected scan |
| ------ | ----------- | -------------- |
| now | 155 | 14.7ms |
| 100x | 15,500 | 1.5s |
| 10,000x | 1,550,000 | 147.3s |

### What the database actually buys us — the answer that surprised me

At 155 chunks the loop is instant and Chroma would be pure overhead. More
importantly, **the loop is exact**: it compares every chunk, so it cannot miss a
match.

Chroma's HNSW index is *approximate*. It deliberately skips most comparisons,
accepting a small chance of missing a true nearest neighbour in exchange for
search time that barely grows with corpus size.

So the database is not more correct than my `for` loop. It is **less** correct and
far faster. I had assumed "real database" meant "better"; it means "a different
point on a speed/accuracy trade". Knowing which direction that trade runs is the
entire payoff of having written the loop first, and it is what I should say when
asked how a vector database finds similar chunks.

### Part 3 — the no-good-answer test, and a result that contradicts Monday

Asked a question with no answer anywhere in the corpus: *"What time does the
corner shop close on Sundays?"*

| | score | chunk |
| --- | ----- | ----- |
| 1 | 0.3386 | `product.md#4` — a schedule table full of dates and day names |
| 2 | 0.3085 | `product.md#5` |
| 3 | 0.2794 | `tasks.md#0` |

The scan still returned three chunks. A linear scan always returns its top-k —
there is no such thing as "no result". Top hit scored 0.3386 because the question
mentions **Sundays** and that chunk contains **Sun Oct 4**. The model is doing its
job: those genuinely are related in meaning. It has no concept of whether a
relation *answers* the question.

Now the part that matters. The nine scores from Part 2's legitimate questions:
the lowest was **0.3655**, against the unanswerable question's **0.3386**. A
margin of **0.0269**.

A floor does separate them here — but only barely. Monday's 0.617-versus-0.031
gap made a threshold look obvious; against a real corpus the usable gap is 20x
narrower. The reason is structural: with a few hundred chunks, *something* will
always be somewhat close to anything you ask.

Conclusion for later weeks: **a score floor is necessary but not sufficient.** The
prompt itself has to give the model permission to refuse. Two independent
defences, because neither is reliable alone. `MIN_SCORE` must not be hardcoded
from this one measurement — Week 2 needs to widen the test first.

### Part 4 — semantic versus keyword, on the same question

Question phrased to avoid the vocabulary of its own answer: *"Why would splitting
a document in the wrong place lose information?"*

Overlap between the two top-3 lists: **0 of 3**. Completely different results.

The giveaway was in the keyword scores: all three tied at exactly **0.2857**.
Keyword matching found the same shallow count of word hits across many chunks and
had no way to rank between them, so its ordering is arbitrary. Semantic search
produced distinct, ordered scores.

Honest caveat: the two methods disagreeing proves they rank *differently*, not
that semantic ranked *better*. Deciding that requires reading the chunks and
judging them, and this corpus is specification boilerplate rather than notes, so
the comparison is muddier than it will be on real material. Re-run on my own
notes, where I know what the right answer should be.

### Week 1 status

| deliverable | state |
| ----------- | ----- |
| Embeddings generated, length printed | done |
| Similar vs unrelated cosine comparison | done — 0.617 vs 0.031 |
| Chunking with fixed size + overlap | done |
| Chunk size / overlap experiments | done on interim corpus, **re-run on own notes** |
| Every chunk embedded, held in memory | done — 155 chunks, list of dicts |
| "What an embedding is" in my own words | **outstanding** |
| "Why splitting matters" in my own words | **outstanding** |
| "What semantic search means" in my own words | **outstanding** |
| 5–10 of my own notes in `sample-notes/` | **outstanding** |
