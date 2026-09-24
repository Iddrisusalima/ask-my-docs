# Implementation Plan — Ask My Docs

Tasks follow the brief's day-by-day structure. Week 1 began Mon Sep 21, 2026, so
weeks are shifted one forward from the dates printed in the brief.

Status legend: `[x]` complete, `[ ]` not started. Tasks marked **BLOCKED** need
something from the user before they can start.

---

## Week 1 — Sep 21–27 — Embeddings & Chunking Foundations

- [x] 1. Project scaffold and environment
- [x] 1.1 Create venv, pin dependencies in `requirements.txt`, install core packages
- [x] 1.2 Write `.gitignore` covering `venv/`, `.env`, `chroma_db/`, `logs/`, model cache
- [x] 1.3 Write `.env.example` with backend selection and model names, copy to `.env`
- [x] 1.4 Initialise git repository and make the first commit
  - _Requirements: 12.4_

- [x] 2. Embedding interface — Mon–Tue
- [x] 2.1 Write `src/embedder.py` with an `Embedder` class wrapping local and OpenAI backends
  - lazy model loading, `lru_cache` on the loader, batch-first API
  - module docstring explaining what an embedding represents and why output length is fixed
  - _Requirements: 1.1, 1.2, 1.3, 1.7, 1.8_
- [x] 2.2 Validate configuration and inputs with actionable error messages
  - unknown backend lists supported values; missing API key names the variable and offers the local backend; empty text rejected
  - _Requirements: 1.4, 1.5, 1.6_
- [x] 2.3 Order OpenAI batch results by the response `index` field
  - _Requirements: 1.7_

- [x] 3. Cosine similarity, hand-written — Mon–Tue
- [x] 3.1 Write `src/similarity.py` with `cosine_similarity` from first principles
  - dot product divided by both magnitudes, no library similarity function
  - docstring explaining why magnitude is divided out and how to read the score
  - _Requirements: 2.1, 2.4_
- [x] 3.2 Guard against mismatched lengths and zero vectors
  - _Requirements: 2.2, 2.3_
- [x] 3.3 Add `similarity_matrix` for all-pairs comparison
  - _Requirements: 2.5_

- [x] 4. Embedding demonstration script — Mon–Tue
- [x] 4.1 Write `scripts/01_embedding_basics.py` printing dimensionality and sample values
  - _Requirements: 1.1_
- [x] 4.2 Demonstrate that input length does not change output length
  - _Requirements: 1.2_
- [x] 4.3 Compare 3 topically related sentences against 3 unrelated ones
  - related sentences chosen to share almost no keywords, so any high score comes from meaning
  - _Requirements: 2.6_
- [x] 4.4 Print the full 6×6 similarity matrix with readable labels
  - _Requirements: 2.5_
- [x] 4.5 Run the script and record real numbers in `notes/week1-learning-log.md`
  - measured: related average 0.617, unrelated average 0.031, gap 0.586
  - _Requirements: 11.1, 11.2_

- [ ] 5. **BLOCKED** — Test dataset
- [ ] 5.1 User adds 5–10 non-sensitive `.md` or `.pdf` notes to `sample-notes/`
  - nothing in section 6 or 7 can be measured without real documents
  - _Requirements: 12.2_

- [x] 6. Document loading — Wed
- [x] 6.1 Write `src/loader.py` with a `LoadedDocument` dataclass and folder discovery
  - recurse subfolders, accept `.md`, `.markdown`, `.txt`, `.pdf`
  - _Requirements: 3.1, 3.7_
- [x] 6.2 Extract PDF text page by page, one `LoadedDocument` per page
  - verified on an 11-page PDF: 11 pages → 11 documents → 21 chunks, page numbers reaching citations as `file.pdf#1 (p.2)`
  - _Requirements: 3.2_
- [x] 6.3 Handle per-file failures without aborting the run
  - verified: missing folder reports the resolved path; empty folder names supported extensions; non-UTF-8 and empty files skipped by name
  - scanned-PDF path written but unverified — needs a real scanned file
  - _Requirements: 3.3, 3.4, 3.5, 3.6_
- [x] 6.4 Fix cp1252 console crash on non-ASCII document text
  - `UnicodeEncodeError` on a `→`; `src/console.py` switches stdout to UTF-8 with `errors="replace"`
  - _Requirements: 10.4_

- [ ] 7. Chunking pipeline — Wed–Thu
- [x] 7.1 Write `src/chunker.py` with `chunk_text` producing fixed-size overlapping windows
  - advance by `chunk_size - overlap`; reject overlap >= chunk_size
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.7_
- [x] 7.2 Soften chunk boundaries toward paragraph, then sentence, then whitespace breaks
  - search window floored at `overlap + 1` to guarantee forward progress; verified on a 2,000-character string with no whitespace
  - _Requirements: 4.8_
- [x] 7.3 Attach `Chunk` metadata: source, chunk index, character offset, page
  - chunk numbering runs per source *file*, not per page, so multi-page PDFs do not collide at `#0`
  - _Requirements: 4.6, 9.1, 9.2_
- [x] 7.4 Discard empty and whitespace-only chunks before they reach the embedder
  - _Requirements: 4.5, 1.6_
- [x] 7.5 Write `scripts/02_chunking_demo.py` comparing size/overlap settings on real notes
  - six configurations swept; Part 3 demonstrates a planted fact severed by a boundary
  - _Requirements: 4.7, 10.5_
- [x] 7.6 Run the experiment across at least three size/overlap pairs and log observations
  - six pairs measured; boundary test shows 500/0 hard cuts leaving the fact in **no chunk at all**
  - 20% overlap costs 1.26x storage; 500/0 → 500/100 raises chunk count 120 → 149
  - _Requirements: 11.2_
- [ ] 7.6a Re-run the sweep against `sample-notes/` once the user's own notes are in
  - the logged table describes `.kiro/` docs, used as an interim corpus; the README must describe the shipped dataset
  - _Requirements: 11.2, 12.2_
- [ ] 7.7 User writes, in their own words, why splitting matters
  - context limits and relevance precision; measurements supplied, prose deliberately left blank
  - _Requirements: 11.3, 11.4_

- [ ] 8. Week 1 wrap-up — Fri
- [x] 8.1 Write `scripts/03_embed_chunks_memory.py` embedding every chunk into a plain list
  - 155 chunks embedded in 29.90s (192.9ms each, CPU); store is a `list` of `dict`
  - _Requirements: 1.7, 2.1_
- [x] 8.2 Search that list with a test question and print ranked results
  - hand-written linear scan over `cosine_similarity`; this is the baseline Chroma must beat
  - _Requirements: 6.2, 6.3_
- [x] 8.3 Record timing and chunk count as the pre-database baseline
  - question embedding ~27ms (fixed) vs scan ~15ms (grows); 95.0µs per comparison
  - first version wrongly lumped both phases together, inflating per-comparison cost ~3x
  - _Requirements: 11.2_
- [x] 8.3a Test a question with no answer in the corpus
  - unanswerable question scored 0.3386; lowest legitimate score 0.3655; **margin only 0.0269**
  - Monday's 0.617/0.031 gap does not survive a real corpus - a score floor is necessary but not sufficient, so Week 3's prompt must also permit refusal
  - _Requirements: 6.6, 8.4_
- [x] 8.3b Compare semantic search against a keyword baseline
  - 0 of 3 overlap in top-3; all keyword scores tied at 0.2857, so its ranking was arbitrary
  - _Requirements: 2.6_
- [ ] 8.4 User writes 3–4 plain-language sentences on what semantic search means
  - _Requirements: 11.3, 11.4_
- [x] 8.5 Commit Week 1 work

---

## Week 2 — Sep 28–Oct 4 — Vector Databases & Retrieval

- [x] 9. Vector store — Mon–Tue
- [x] 9.0 Resolve the chromadb install failure
  - `chromadb==0.5.23` needs `chroma-hnswlib`, which has no Python 3.12 wheel and fails to compile without MSVC build tools
  - moved to `chromadb==1.5.9` (Rust core, prebuilt wheels); numpy and sentence-transformers still import cleanly
- [x] 9.1 Write `src/store.py` wrapping a Chroma `PersistentClient`
  - cosine set explicitly via `configuration={"hnsw": {"space": "cosine"}}`
  - probed the default: squared L2 gives distance 2.0 where cosine gives 1.0 for perpendicular unit vectors
  - _Requirements: 5.1, 5.2_
- [x] 9.2 Pass our own embeddings in rather than attaching Chroma's embedding function
  - keeps the embed step visible, which is the point of having built it
  - _Requirements: 5.2_
- [x] 9.3 Make `reset()` delete and recreate the collection for idempotent re-ingestion
  - verified: reset+add run twice leaves count at 1, no duplicates
  - _Requirements: 5.3_
- [x] 9.4 Store the producing model name as collection metadata and detect mismatches
  - verified both directions: matching model passes, `openai:text-embedding-3-small` against a MiniLM index is rejected
  - _Requirements: 5.5_
- [x] 9.5 Report an actionable message when the collection is empty or missing
  - both cases name the ingestion command; `count()` returns 0 rather than raising
  - _Requirements: 5.6_
- [x] 9.6 Write `scripts/04_ingest.py` running load → chunk → embed → index
  - 159 chunks: embed 61.79s, index 0.54s — embedding dominates ingestion by ~115x
  - confirms persistence by reopening the collection with a fresh `VectorStore`
  - _Requirements: 5.4, 10.1, 10.3_
- [x] 9.7 Read up on HNSW and record how approximate nearest-neighbour search avoids comparing against every chunk
  - layered proximity graphs, greedy descent, `ef_search` / `ef_construction` / `max_neighbors`, recorded with sources
  - _Requirements: 11.1_
- [x] 9.8 Measure the approximate index against Friday's exact scan
  - 10/10 top-5 agreement — expected at 159 chunks, and **not** evidence that HNSW never misses
  - similarity reproduces Friday's hand-written cosine to 4dp (0.6690 / 0.6070 / 0.5247), cross-validating both implementations
  - _Requirements: 6.3, 11.2_

- [ ] 10. Retrieval — Wed–Thu
- [ ] 10.1 Write `src/retriever.py` embedding the question with the same model as the index
  - _Requirements: 6.1_
- [ ] 10.2 Convert Chroma distance to cosine similarity at the retriever boundary
  - every number the user sees should mean "higher is better", as in Week 1
  - _Requirements: 6.3_
- [ ] 10.3 Return top-k ordered results carrying score, text, and source metadata
  - _Requirements: 6.2, 6.3, 6.5_
- [ ] 10.4 Add an optional `min_score` floor returning an empty set when nothing clears it
  - distinguishes "nothing relevant" from "the five least irrelevant chunks"
  - _Requirements: 6.6_
- [ ] 10.5 Write `scripts/05_retrieve.py` printing retrieved chunks with scores
  - _Requirements: 10.2, 10.5_
- [ ] 10.6 Test several questions and manually judge whether retrieved chunks are relevant
  - including a question phrased with no keyword overlap with its answer
  - _Requirements: 11.2_
- [ ] 10.7 Compare top-k of 3, 5, and 10 and record the context-versus-noise tradeoff
  - _Requirements: 6.4, 11.2_
- [ ] 10.8 Choose `TOP_K` from those measurements and record the reasoning
  - _Requirements: 11.2, 12.3_

- [ ] 11. Week 2 wrap-up — Fri
- [ ] 11.1 Log question, configuration, and retrieved chunks with scores to `logs/retrieval.log`
  - create the directory if absent; truncate chunk text to a skimmable preview
  - _Requirements: 7.1, 7.2, 7.3, 7.4_
- [ ] 11.2 User writes a comparison of Chroma against one alternative
  - supply the factual contrasts; the argument must be theirs
  - _Requirements: 11.3, 11.4_
- [ ] 11.3 Commit Week 2 work
- [ ] 11.4 Confirm the real deadline with the mentor if still unresolved, and cut scope now if it holds at Oct 4

---

## Week 3 — Oct 5–11 — Generation, Full Pipeline & Submission

- [ ] 12. Grounded generation — Mon–Tue
- [ ] 12.1 Write `build_prompt` in `src/generator.py` as a pure function
  - returns the prompt and the chunks that actually fit the budget, so citations match what the model saw
  - _Requirements: 8.1, 8.5_
- [ ] 12.2 Number context passages `[1]`, `[2]`, … in the prompt
  - _Requirements: 9.3_
- [ ] 12.3 Write the system prompt instructing context-only answers with an explicit way to refuse
  - a model given no acceptable refusal will invent one instead
  - _Requirements: 8.2, 8.4_
- [ ] 12.4 Call the chat model and handle API failure without losing the question or context
  - _Requirements: 8.7_
- [ ] 12.5 Add a flag to print the assembled prompt without calling the API
  - needed to demonstrate grounding in the video rather than assert it
  - _Requirements: 8.6, 10.5_
- [ ] 12.6 Verify grounding with a fact that exists only in the notes
  - and a fact in the notes that contradicts common knowledge
  - _Requirements: 8.3_

- [ ] 13. Source citations — Wed
- [ ] 13.1 Resolve cited passage numbers back to source filename, chunk id, and page
  - _Requirements: 9.1, 9.2_
- [ ] 13.2 Display similarity score alongside each citation
  - _Requirements: 9.4_
- [ ] 13.3 Open the source files and confirm each citation genuinely contains the claim
  - _Requirements: 9.1_

- [ ] 14. Test and refine — Thu
- [ ] 14.1 Write `scripts/06_ask.py` as the full pipeline entry point, one-shot and interactive
  - _Requirements: 10.2, 10.3_
- [ ] 14.2 Exit non-zero with clean messages on failure instead of tracebacks
  - _Requirements: 10.4_
- [ ] 14.3 Run at least 10 questions and rate each answer's quality in the log
  - _Requirements: 11.2_
- [ ] 14.4 Test a question with no answer in the notes and confirm graceful refusal
  - tune `MIN_SCORE` from the observed score distribution
  - _Requirements: 8.4, 6.6_
- [ ] 14.5 Revisit chunk size, top-k, or the prompt based on the ratings, and record what changed
  - _Requirements: 11.2_

- [ ] 15. Polish and document — Fri–Sat
- [ ] 15.1 Handle the remaining edge cases: empty folder, no matches, missing `.env`
  - _Requirements: 3.5, 3.6, 5.6, 10.4_
- [ ] 15.2 Review comments and docstrings across `src/` for the mentor reading it cold
  - _Requirements: 11.1_
- [ ] 15.3 Write the README description, dataset summary, and setup instructions
  - including how a reviewer adds their own documents
  - _Requirements: 12.3, 12.5_
- [ ] 15.4 User writes the README "What I Learned" section
  - embeddings, chunking, and the pipeline in their own words; must survive a follow-up question
  - _Requirements: 11.3, 11.4, 12.3_
- [ ] 15.5 Document final `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K`, and `MIN_SCORE` with the measurements behind them
  - _Requirements: 12.3_
- [ ] 15.6 Capture a screenshot of a real question, answer, and citation for the README
  - _Requirements: 12.3_
- [ ] 15.7 Verify no secrets, venv, database, or model cache are tracked by git
  - _Requirements: 12.4_
- [ ] 15.8 Record the 3–4 minute demo: ingestion, then 2–3 live questions, narrating each stage
  - _Requirements: 12.6_

- [ ] 16. Submit — Sun
- [ ] 16.1 Push to a public GitHub repository named `ask-my-docs`
  - _Requirements: 12.1_
- [ ] 16.2 Clone fresh into a temporary folder and follow the README exactly to confirm it works
  - _Requirements: 12.5_
- [ ] 16.3 Walk the self-check list in section 7 of the brief, out loud
  - explain an embedding without saying "vector"; explain the pipeline in under a minute
  - _Requirements: 11.3_
- [ ] 16.4 Send the mentor the repo link and the video link before 11:59 PM
  - _Requirements: 12.6_
