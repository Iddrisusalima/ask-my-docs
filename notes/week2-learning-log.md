# Week 2 Learning Log — Vector Databases & Retrieval

Week 2 runs **Mon 28 Sep – Sun 4 Oct 2026** (shifted +1 week from the brief; see
`week1-learning-log.md` for why).

Same dataset caveat as Week 1: `sample-notes/` is still empty, so everything below
was measured against this project's own `.kiro/` docs — 7 files, 57,597 characters,
**159 chunks** at 500/100. Re-run after adding my own notes.

---

## Mon–Tue — Set up a real vector database

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

## Wed–Thu — Implement retrieval

_(not started)_

### Top-k comparison (3 / 5 / 10)

| top-k | observation |
| ----- | ----------- |

---

## Fri — Wrap up Week 2

_(not started)_

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
