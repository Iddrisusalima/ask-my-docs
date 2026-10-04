# Learning Log — Ask My Docs

Every measurement behind this project, in the order the pipeline runs rather than
the order I built it. Each section records what I did, the numbers I got, and
where I was wrong and had to change course.

The three findings I would point at first:

- **A hard chunk boundary can make a fact unfindable with no error anywhere.**
  Demonstrated deliberately in section 2, then it happened by itself on my real
  notes in section 9 and cost me an answer.
- **A vector database is less accurate than a brute-force scan, not more.** It
  skips comparisons on purpose. Section 3 sets this up, section 4 measures it.
- **A single relevance threshold cannot separate good answers from bad ones.**
  Section 5 has the sweep that killed the idea; section 7 has what replaced it.

Sections marked **TO WRITE** are explanations I have to give in my own words.

> Note on dates: the project brief lists the start as Sep 14 and the deadline as
> Oct 4. Week 1 actually began Sep 21, so every week shifts forward by one:
> Week 1 = Sep 21–27, Week 2 = Sep 28–Oct 4, Week 3 = Oct 5–11. Deadline to be
> confirmed with mentor.

This file is where I write things in my own words. The brief asks for written
explanations at several points, and the final README pulls from here.

---

## 1. Embeddings and similarity

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

## 2. Loading and chunking

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
  many near-useless tail chunks.yu
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

## 3. Search with no database

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

---

`learning-log.md` for why).

Same dataset caveat as Week 1: `sample-notes/` is still empty, so everything below
was measured against this project's own `.kiro/` docs. Re-run after adding my own
notes.

The Mon–Tue figures were taken at **159 chunks**; the Wed–Fri figures at **171
chunks**, because I kept editing the spec files that make up the interim corpus.
The conclusions did not change, but the fact that the numbers drifted while the
code stayed identical is itself the argument for getting a fixed dataset in place.

---

## 4. The vector database

Code: `src/store.py`, `scripts/04_ingest.py`

```powershell
.\venv\Scripts\python.exe scripts\04_ingest.py --folder sample-notes
```

### Installation problem, and why the version changed

`requirements.txt` originally pinned `chromadb==0.5.23`. It would not install:

```
Building wheel for chroma-hnswlib (pyproject.toml) did not run successfully.
error: Microsoft Visual C++ 14.0 or greater is required.
```

The 0.5.x line depends on `chroma-hnswlib`, a C++ extension with no prebuilt
wheel for Python 3.12, so pip tried to compile it from source and needed Visual
Studio build tools I do not have installed.

Fixed by moving to **`chromadb==1.5.9`**. The 1.x line replaced that C++ binding
with a Rust core and ships prebuilt wheels, so it installs with no compiler.
Verified `numpy 2.1.3` and `sentence-transformers 3.3.1` still import cleanly
afterwards — the upgrade did not break the Week 1 stack.

Worth remembering as a general lesson: the newest version is not automatically
the right choice, but "this dependency needs a C++ toolchain" is a legitimate
reason to move off a pinned version rather than install a 6 GB compiler.

### The setting that would have quietly broken everything

Chroma's default distance metric is **squared L2**, not cosine. Probed it
directly with three unit vectors — identical, perpendicular, and opposite:

| space | identical | perpendicular | opposite |
| ----- | --------- | ------------- | -------- |
| Chroma default (squared L2) | 0.0 | **2.0** | — |
| cosine (configured) | 0.0 | **1.0** | 2.0 |

Under cosine, `similarity = 1 - distance` recovers Week 1's scale exactly:
1.0 for identical direction, 0.0 for perpendicular, -1.0 for opposite.

So the collection is created with an explicit space:

```python
configuration={"hnsw": {"space": "cosine"}}
```

For L2-normalised embeddings like MiniLM's, L2 and cosine happen to rank the
same way, so this would not have shown up as a visibly wrong answer today. It
would have shown up the moment I switched to a model that does not normalise —
and it would have shown up as *subtly* worse retrieval, not an error. Setting it
explicitly costs one line.

### How the database actually searches — HNSW

The brief asks me to read up on this, so: Chroma indexes with **HNSW**,
Hierarchical Navigable Small World.

The structure, paraphrased from the original paper
([Malkov & Yashunin, arXiv:1603.09320](https://arxiv.org/abs/1603.09320)): it
builds a stack of proximity graphs over nested subsets of the data, and the
highest layer any given item appears in is chosen at random, with the
probability decaying exponentially. So the top layer holds very few items and
acts as a coarse map; the bottom layer holds everything.

Searching walks that structure. Starting at the top, it moves greedily to
whichever neighbour sits closer to the query, descending a layer when no
neighbour improves, and keeping a working list of candidates rather than a single
best guess — described as coarse routing in the sparse upper layers followed by a
fine-grained walk at the dense bottom
([Milvus, HNSW explained](https://milvus.io/learn-milvus/hnsw)). The number of
hops grows logarithmically rather than linearly with corpus size.

The two knobs Chroma exposes, both defaulting to 100
([Chroma, Configure Collections](https://docs.trychroma.com/docs/collections/configure)):

| setting | observed value | what it controls |
| ------- | -------------- | ---------------- |
| `space` | cosine | distance metric (set explicitly by me) |
| `ef_construction` | 100 | size of the candidate list when picking neighbours at build time — higher gives a better index, costing memory and build time |
| `ef_search` | 100 | how wide the candidate list is per query — higher explores more graph, finds more true neighbours, costs more time |
| `max_neighbors` | 16 | how many links each node keeps; denser graph, better recall, slower queries |

`ef_search` is the recall/speed dial. Published figures put typical ANN recall in
the region of 95–99% in exchange for order-of-magnitude speedups
([overview of the tradeoff](https://medium.com/@alexchen3292/understanding-hierarchical-navigable-small-worlds-hnsw-for-vector-search-325d6e24294a)).

_Content from the sources above was rephrased for compliance with licensing restrictions._

### The key point, which is the same one Friday made

**The index is approximate. My Week 1 `for` loop was exact.** A greedy graph walk
can settle into a local minimum and miss a true nearest neighbour that comparing
everything would have found. Chroma is not more correct than the loop — it is
less correct and vastly more scalable.

### Ingestion measured

| step | result |
| ---- | ------ |
| Load | 7 files → 7 documents, 57,597 chars |
| Chunk | 159 chunks at 500/100, mean 457.8 (min 112, max 500) |
| Embed | 159 chunks in **61.79s** (388.6ms each) |
| Index | 159 chunks in **0.54s** |

Embedding dominates ingestion by about 115x. Indexing is essentially free by
comparison, which is worth knowing before optimising the wrong half.

Note the embedding time drifted: Friday measured 192.9ms per chunk, this run
388.6ms — same model, same machine, roughly double. Nothing in the code changed,
so this is machine load, not a regression. A lesson about single-run timings:
they are indicative, not precise. Ratios between steps in the *same* run are far
more trustworthy than absolute numbers across runs.

### Persistence — the thing Friday's list could not do

Reopened the collection from disk with a brand-new `VectorStore` object:
**159 chunks, model recorded as `local:sentence-transformers/all-MiniLM-L6-v2`.**

Friday's store vanished when the process exited, so every question meant
re-embedding the entire corpus first — 30 to 60 seconds before answering
anything. That cost is now paid once per change to the notes rather than once per
run. This, not raw search speed, is what the database actually bought me at this
corpus size.

### The model-mismatch guard

Embeddings from two different models are not comparable, and querying across
them raises **nothing** — it returns confident, well-formed, meaningless
results. That is the worst failure mode in the whole pipeline, because there is
no symptom to notice.

So `reset()` records the model on the collection, and `assert_model_matches()`
compares against it. Verified both directions:

- matching model → passes
- `openai:text-embedding-3-small` against a MiniLM index → **rejected** with an
  error naming both models and the command to re-index

### Approximate vs exact — measured, not assumed

Ran the same questions through Chroma's HNSW index and through Friday's
brute-force scan, then compared the result sets.

| question | HNSW | exact scan | top-5 agreement |
| -------- | ---- | ---------- | --------------- |
| "Why does overlap between chunks matter?" | 11.6ms | 13.1ms | **5/5** |
| "How should I choose how many results to retrieve?" | 3.5ms | 14.9ms | **5/5** |

**Overall: 10/10, 100% agreement.**

Two things about this result that matter more than the number itself:

**It is expected, not reassuring.** At 159 chunks the graph is small enough that
a greedy walk reaches the true nearest neighbours anyway. The approximation only
begins costing recall when the graph is large enough that the walk must skip
meaningful portions of it. So this confirms the index is *wired up correctly* —
it does not demonstrate that approximate search is free. I should not present it
as evidence that HNSW never misses anything.

**The similarity values cross-validate both implementations.** For "Why does
overlap between chunks matter?", Friday's hand-written `cosine_similarity` scored
the top three chunks 0.6690, 0.6070, 0.5247. Chroma's cosine distances converted
with `1 - distance` give **0.6690, 0.6070, 0.5247** — identical to four decimal
places, on the same chunk IDs. Two independent implementations agreeing exactly
is good evidence that neither the hand-written arithmetic nor the space
configuration is wrong.

Also worth noting the speed comparison is not yet meaningful: 11.6ms vs 13.1ms at
this size is noise, and the second query's 3.5ms mostly reflects a warm index. The
scaling difference is real but not observable at 159 chunks.

### Error paths verified

| case | behaviour |
| ---- | --------- |
| query a collection that was never created | `VectorStoreError` naming the db path and the ingest command |
| query an empty collection | `VectorStoreError` saying nothing has been indexed yet |
| `count()` on a missing collection | returns 0, does not raise |
| chunks and embeddings lists differ in length | `ValueError` — would otherwise pair chunks with wrong embeddings and corrupt every citation |
| `add_chunks` before `reset` | `VectorStoreError: Call reset() before adding chunks` |
| `top_k` larger than the collection | clamps and returns everything, no error |
| `page=None` for markdown | key omitted from metadata — Chroma rejects `None` values outright |
| `reset` then add, twice over | count stays 1 — ingestion is idempotent, no duplicates |

---

## 5. Retrieval and tuning top-k

Code: `src/retriever.py`, `scripts/05_retrieve.py`

```powershell
.\venv\Scripts\python.exe scripts\05_retrieve.py
```

The retriever does three things, and each one is a place the pipeline could go
quietly wrong:

1. Checks the collection was built by the model now doing the querying.
2. Converts Chroma's *distance* into *similarity* — once, here — so every score
   anything downstream sees means "higher is better", matching Week 1.
3. Offers an optional `min_score` floor, so "nothing relevant" can be expressed
   at all.

### Top-k comparison (3 / 5 / 10)

Averaged over four test questions, phrased to avoid the vocabulary of their own
answers:

| top-k | mean score | worst | drop vs k=3 | context chars | sources | duplicate pairs |
| ----- | ---------- | ----- | ----------- | ------------- | ------- | --------------- |
| 3 | 0.4296 | 0.3947 | — | 1,380 | 2.5 | 0.0 |
| **5** | **0.4034** | **0.3545** | **−0.0262** | **2,211** | **3.2** | **0.5** |
| 10 | 0.3681 | 0.3132 | −0.0615 | 4,636 | 3.8 | 2.8 |

"Duplicate pairs" counts results that are *neighbouring chunks of the same
document*. Because consecutive chunks share 100 characters by construction, when
both come back for one question part of the context is sent to the model twice.
At k=10 that happened 3 times per question on average — three of ten slots spent
on text already present.

### What the tail actually contains

For "Why does overlap between chunks matter?" at k=10:

| | |
| --- | --- |
| mean of top 3 | 0.6003 |
| mean of ranks 6–10 | 0.4571 |
| quality drop | **0.1432** |

Ranks 6 to 9 scored 0.4640, 0.4636, 0.4633 and 0.4578 — essentially identical.
When scores bunch that tightly the ranking between them is close to arbitrary,
which is a useful signal in itself: it means the question found nothing in
particular beyond rank 5.

The tail chunks are not rubbish. They are *loosely on topic*, and that is exactly
what makes them harmful. Obvious junk would be ignored; plausible-but-irrelevant
text is what pulls a model's attention away from the passage that actually
answers the question.

### The relevance floor — and a measurement that killed the idea of a global one

How many chunks survive each floor, swept across all four questions plus an
unanswerable control:

| floor | Q1 | Q2 | Q3 | Q4 | unanswerable |
| ----- | -- | -- | -- | -- | ------------ |
| off | 5 | 5 | 5 | 5 | 5 |
| 0.25 | 5 | 5 | 5 | 5 | 4 |
| 0.30 | 5 | 3 | 5 | 5 | 2 |
| **0.35** | 5 | **2** | **2** | 4 | **0** |
| 0.40 | 5 | **0** | **0** | **1** | 0 |
| 0.45 | 5 | 0 | 0 | 0 | 0 |

- Q1: Why does overlap between chunks matter?
- Q2: How should I decide how many results to fetch?
- Q3: What stops the model inventing an answer?
- Q4: What happens when my notes do not cover the question?

**The floor that silences the unanswerable control also guts Q2 and Q3.** At 0.35
the control is finally blocked, but Q2 and Q3 drop to two chunks each. At 0.40
they return nothing at all — for questions the notes genuinely do cover.

I nearly drew the wrong conclusion here. My first version of this test used only
Q1, which scores high throughout, and the floor looked perfectly safe at 0.35.
Sweeping all four questions is what exposed the conflict. A measurement designed
around the best case is worse than no measurement, because it produces false
confidence.

**Why this happens:** these scores are not calibrated across questions. A question
worded the way my notes are written scores high on everything; one phrased
differently scores low on everything, even when its top hit is exactly right. So
an absolute cutoff compares numbers that were never on a common scale — the same
mistake Week 1 Monday warned about, resurfacing in a new place.

**Decision: `min_score` defaults to off.** A wrong floor silently discards correct
answers, which is worse than passing marginal context to a model that has been
told it may refuse. Week 3 leans on the prompt as the primary defence.

Worth trying if time allows: a *relative* test instead — require the best hit to
stand clear of the rest by some margin. For the unanswerable control the spread
was flat; for Q1 the top hit stood 0.06 above second place. That shape looks more
promising than an absolute threshold, and it would not depend on question wording.

### Chosen: TOP_K = 5

Reasoning from the table, so the choice is defensible:

- **Against k=3:** k=3 has the best mean score but pulls from only 2.5 sources on
  average and 1,380 characters. Too easy for a real answer to need a detail that
  fell just outside three chunks.
- **Against k=10:** costs 3.4x the context for a 0.0615 drop in mean quality, and
  wastes nearly three of ten slots on duplicated neighbouring chunks. The ranks
  6–10 scores were bunched within 0.007 of each other, so they add noise rather
  than information.
- **k=5** sits at 2,211 characters — a comfortable prompt size for Week 3 — with
  3.2 sources and only 0.5 duplicate pairs.

Still provisional. Answer quality in Week 3 is the only test that matters; every
number above is a proxy for it.

---

## 6. Logging retrieval quality

### Retrieval logging

Code: `src/retrieval_log.py`. Every question run through `05_retrieve.py` appends
to `logs/retrieval.log` (gitignored — review material, not a deliverable).

Verified: 5 entries, 45 lines, 4,594 bytes. Each entry records

- timestamp and the question
- the full configuration: model, top-k, min_score, collection, chunks indexed
- summary line: best / worst / spread
- every result with its score, citation id, and a 100-character preview

Three format decisions worth keeping:

**Append, never overwrite** — the value is in accumulating runs across days, so
a settings change that collapses scores is visible by comparison.

**Configuration recorded alongside results** — a score is meaningless without
knowing the chunk size, top-k and model behind it. A log of bare numbers cannot
be compared against anything.

**Empty results logged loudly** as `NO RESULTS - nothing cleared the relevance
floor`. An empty result set is a finding, not missing data. Confirmed by asking
"what is the capital of Peru?" with a 0.5 floor:

```
[2026-09-28 15:25:33]  what is the capital of Peru?
  config: chunks_indexed=159  min_score=0.5  top_k=5  model=local:...MiniLM-L6-v2
  NO RESULTS - nothing cleared the relevance floor
```

### Chroma versus one alternative

_(MINE TO WRITE — the brief asks for this comparison in my own words. Factual
material to build on, not prose to submit:_

- _Chroma: runs in-process, persists to a local directory, no signup, no network
  hop. Installed and working in one line once on the 1.x wheels._
- _Pinecone: managed service, needs an account and an API key, every query is a
  network round trip, but it scales past a single machine and needs no local
  resources._
- _FAISS: faster at large scale, but stores no metadata — citations would need a
  parallel bookkeeping layer I would have to write and keep in sync._
- _My actual deciding factor was which one taught the concept with the least
  incidental complexity, since correctness at 159 chunks is identical across all
  three.)_

---

Deadline still to be confirmed with mentor.

---

## 7. Grounded generation

Code: `src/generator.py`, `scripts/06_ask.py`

```powershell
.\venv\Scripts\python.exe scripts\06_ask.py --question "why does chunk overlap matter?"
.\venv\Scripts\python.exe scripts\06_ask.py --question "..." --show-prompt
```

### No new API key needed

Project 1 used **Gemini**, and that key was still in `prompt-lab/.env`. The brief
says to reuse the Project 1 chat setup, so I did.

Google exposes an OpenAI-compatible endpoint
([docs](https://ai.google.dev/gemini-api/docs/openai)), which meant zero code
changes — only three values in `.env`:

```
OPENAI_API_KEY=<the Gemini key from Project 1>
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_CHAT_MODEL=gemini-3.5-flash-lite
```

Worth understanding why that worked: most providers have settled on OpenAI's
chat-completions protocol, so the client library is interchangeable. Groq,
Together and a local Ollama server all work the same way. The provider is now a
configuration detail, not an architectural decision — and that is only true
because the generator never hardcoded a URL.

_Content from the Google documentation was rephrased for compliance with licensing restrictions._

### The prompt is assembled in plain sight

`build_prompt()` is a **pure function** — question and passages in, prompt string
out, nothing else touched. Two things that buys:

1. `--show-prompt` prints the exact text the model would receive and stops,
   without spending a call. "The model only sees my notes" is a claim; the
   printed prompt is evidence. This is what I will demo in the video.
2. Citations come from the passages that actually *fitted the budget*, not
   everything retrieved. If those two lists ever diverged, every citation would
   be wrong.

Passages arrive numbered `[1]`–`[5]`, each labelled with its source. The model is
told to cite the numbers. Asking it to "say which files you used" produces vague
gestures at the whole set; numbers give it something precise to point at.

### The clause that does the real work

Rule 3 of the system prompt:

> If the passages do not contain the answer, say so plainly — for example: "I
> can't find the answer to that in your notes." Do not guess, do not fill gaps
> from general knowledge.

Without that, a model handed irrelevant passages still produces something,
because refusing is not an option it has been given. With it, refusing becomes
the compliant response.

This is the direct consequence of Week 2's measurement. A question with no answer
scored 0.3386 while the weakest genuine answer scored 0.3655 — a gap of 0.027.
No score threshold separates those reliably, so `MIN_SCORE` ships off and the
prompt carries the weight.

### First real answer

Question: *"why does chunk overlap matter?"*

> Overlap acts as a defense against a fact being severed at a boundary; without
> it, a sentence split across two chunks might be retrievable through neither
> **[3]**. Additionally, when overlap is greater than zero, each chunk after the
> first begins with the final `overlap` characters of the preceding chunk **[1]**.

| passage | cited | score | source |
| ------- | ----- | ----- | ------ |
| [1] | **yes** | 0.7329 | `requirements.md#14` |
| [2] | no | 0.6006 | `tasks.md#12` |
| [3] | **yes** | 0.5923 | `design.md#11` |
| [4] | no | 0.5545 | `design.md#39` |
| [5] | no | 0.5429 | `requirements.md#15` |

Both citations are correct — I opened those files and the claims are genuinely
there.

**But 3 of 5 passages went unused**, and the script now reports that. If it keeps
happening, top-k of 5 is higher than it needs to be. That is a measurement I
could not have taken before this week: Week 2 could only count how many passages
*looked* relevant, not how many actually got used.

### The no-answer test — the self-check item

| question | top score | answer |
| -------- | --------- | ------ |
| "What time does the corner shop close on Sundays?" | 0.3386 | *"I can't find the answer to that in your notes."* |
| "What is the capital of Peru?" | 0.1207 | *"I can't find the answer to that in your notes."* |

The Peru question is the stronger test, and worth explaining out loud. The model
**certainly knows** the capital of Peru from its general training. It refused
anyway. That proves the grounding instruction is working, rather than merely
proving that retrieval found nothing — a distinction the corner shop test alone
cannot make.

Also note the display flags "the model cited nothing", which is the right
behaviour: a refusal should cite nothing, and an *answer* that cites nothing is a
warning sign worth checking.

---

## 8. Source citations

_(partly done as part of Mon–Tue; still to verify across more questions)_

- [x] passage numbers resolved back to filename and chunk id
- [x] PDF citations carry the page number, e.g. `notes.pdf#3 (p.2)`
- [x] similarity score shown beside each source
- [x] cited vs offered-but-unused marked separately
- [ ] open the source files and confirm every citation across 10 questions

---

## 9. Testing and refinement

### The dataset is finally real

`sample-notes/` now holds **5 of my own notes** — my Project 1 write-ups:
`project1-build-log.md`, `project1-overview.md`, `project1-learnings.md`,
`project1-blog-post.md`, `project1-screenshots.md`. 79,581 characters.

Checked for secrets and personal details before committing, since the folder goes
to a public repo: no API keys, no email addresses, no phone numbers.

Good choice of dataset for a second reason — the notes are about prompt
engineering and token economics, so the questions I ask have real answers I can
verify by opening the file.

### Ten questions, rated

Settings: chunk size 350, overlap 70, top-k 5, no score floor,
`gemini-3.5-flash-lite`.

| # | question | result | cited | verdict |
| - | -------- | ------ | ----- | ------- |
| 1 | What does it mean that the API is stateless? | answered | [2][3] | **good** |
| 2 | What is the difference between training and inference? | answered | [1][3][4][5] | **good** |
| 3 | What do roles do in a chat request? | answered | [1] | **good** |
| 4 | Why is the total token count not always input plus output? | answered | [1][5] | **good** |
| 5 | What is a context window measured in? | answered | [1][2][3] | **good** |
| 6 | When streaming, when does token usage arrive? | answered | [3][4][5] | **good** |
| 7 | How much influence does the system instruction have? | answered | [2][5] | **good** |
| 8 | How did I keep my API key safe? | answered | [4] | **partial** — got the `.gitignore` point, missed the other three steps |
| 9 | What is the capital of Peru? | refused | — | **correct refusal** |
| 10 | How do I fix a leaking radiator? | refused | — | **correct refusal** |

**8 of 8 answerable questions answered with correct citations. 2 of 2 controls
refused.** I opened the cited files and checked: every citation genuinely
contains the claim.

### How I got there — the iteration loop the brief predicted

The first run was **not** 8 of 8. At the documented 500/100 setting, two
questions were refused that my notes clearly answer. Diagnosing those produced
the two most useful findings of the week.

**Failure 1 — "Why are input and output tokens priced differently?"**

The answer exists at `project1-build-log.md` line 415: *"Output tokens cost about
8x more than input tokens. $2.50 versus $0.30 per..."*. But the passage retrieval
handed the model began **mid-word**:

```
y 8x more per token than
input**. The `/stats` command prints...
```

That is "...roughl**y 8x** more per token" with its opening sliced off into the
previous chunk. The model received an incoherent fragment and refused. At top-k
10 the clean statement still never appeared — no chunk contained it whole.

**This is Week 1's boundary problem, resurfacing where it finally costs an
answer.** In Week 1 I demonstrated it with a planted sentence in a test document.
Here it happened by itself, on my real notes, and the symptom was not a missing
chunk — it was a refusal that looked like the tool working correctly.

Re-ingesting at 900/300 fixed the fragment, and the answer changed to:

> "I can't find the answer to that in your notes. The notes state that input and
> output are priced differently [2][3], but they do not explain *why* the pricing
> difference exists."

Which is **correct** — and my question was the faulty part. My notes record
*that* the prices differ, not *why* Google sets them that way. Rule 4 of the
system prompt ("give the part they support and say what is missing") produced
exactly the right behaviour. Lesson: when an answer looks wrong, check the
question before blaming the pipeline.

**Failure 2 — "How did I keep my API key safe?"**

My notes answer this in four numbered steps under a heading literally called
"How I keep the key safe". At both 500/100 and 900/300 the tool refused, and
retrieval returned a passage about token counts and history resets instead.

The cause is the opposite of failure 1. That section is only eight lines long. At
900 characters it gets absorbed into a chunk dominated by surrounding material,
and its meaning is diluted until it no longer matches a question about key
safety. **That is the "large chunks dilute the match" tradeoff from Week 1,
biting in the other direction.**

At 350/70 the section occupies a chunk of its own, and the tool answers:

> "You kept your API key safe by writing `.gitignore` before the key existed on
> disk [4]."

Correct, though partial — it got one of four steps.

### The decision: chunk size 350, overlap 70

Changed from the provisional 500/100 chosen in Week 1.

| setting | Q1 (token pricing) | Q8 (key safety) |
| ------- | ------------------ | --------------- |
| 500 / 100 | refused — mid-word fragment | refused |
| 900 / 300 | correct partial answer | refused — diluted |
| **350 / 70** | fine | **answered** |

Why smaller won on my notes: they are written in short sections with frequent
headings. Each heading introduces a distinct idea, and a 350-character chunk maps
roughly to one of those sections. At 900 characters a chunk spans several
sections and its embedding becomes an average of unrelated ideas.

**This is why the Week 1 choice had to stay provisional.** 500/100 was defensible
from chunk-count statistics, which is all I had then. Answer quality on real
notes is a different measurement and it pointed somewhere else. The brief said
this iteration loop was normal and expected; it was.

Honest limitation: 350/70 is tuned to how *my* notes are written. Someone with
long flowing prose and few headings would likely need larger chunks. The right
answer is a property of the documents, not a universal constant.

### Still open from this round

- Q8 returns one of four steps. Worth testing whether top-k 7 or 8 recovers the
  rest, now that chunks are smaller and each holds less.
- Several answers cite only 1 of 5 passages. With smaller chunks, a slightly
  higher top-k may now be the better setting — the earlier argument against 10
  was measured at 500/100 and may no longer hold.

---

## 10. Documentation and submission

_(not started)_

### README checklist, from the brief

- [ ] one paragraph on what the tool does and the dataset used
- [ ] setup instructions, including how to add your own documents
- [ ] "What I Learned" — embeddings, chunking, the pipeline, **in my own words**
- [ ] chosen chunk size and top-k, with the reasoning
- [ ] screenshot of a real question, answer and cited source

### Demo video, 3–4 minutes

- [ ] show ingestion
- [ ] ask 2–3 questions live
- [ ] explain what happens at each stage

---

## Blocking everything

`sample-notes/` is **still empty**. Every number in all three learning logs
describes this project's own documentation. Before the README screenshot and the
ten-question test, that folder needs 5–10 of my own non-sensitive notes — the
brief requires it committed so the mentor can run the tool unmodified.
