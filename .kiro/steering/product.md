# Ask My Docs — Product Context

## What this is

Project 2 of a mentored learning track. A retrieval-augmented generation (RAG)
tool that answers questions about the user's own PDF and markdown notes, using
only retrieved context from those notes rather than the model's general
knowledge.

Built manually, stage by stage: chunk → embed → store → retrieve → generate.

## Who it is for

The user is the primary audience: they are learning RAG by building it. A mentor
reviews the finished repo and a 3–4 minute demo video.

## The learning goal outranks the shipping goal

Working code is half the grade. By the end the user must be able to explain,
out loud and unaided:

- what an embedding is, without falling back on the word "vector"
- why chunk size changes the quality of retrieved context
- how a vector database finds "similar" chunks
- the full pipeline, start to finish, in under a minute
- when RAG is the right tool versus fine-tuning

Treat any explanation the user must give as **their** work. See
`learning-guardrails.md`.

## Timeline

The brief says the project starts Mon Sep 14, 2026 and is due Sun Oct 4. Week 1
actually began **Mon Sep 21, 2026**, so every week shifts forward by one:

| Week | Dates | Theme |
| ---- | ----- | ----- |
| 1 | Mon Sep 21 – Sun Sep 27 | Embeddings & chunking foundations |
| 2 | Mon Sep 28 – Sun Oct 4 | Vector database & retrieval |
| 3 | Mon Oct 5 – Sun Oct 11 | Generation, full pipeline, submission |

The brief's printed Oct 4 deadline fell at the end of the shifted Week 2. That
was resolved with the mentor: **submission is Fri Oct 30, 2026**, which gave
Week 3 its full span and left time for the write-up and demo recording.

Pace was part-time, roughly 1.5–2 hours per weekday.

## Current progress

**Build complete.** All three stages are written, measured and committed:

| Stage | Module | Script |
| ----- | ------ | ------ |
| Load and chunk | `loader.py`, `chunker.py` | `chunking.py` |
| Embed and compare | `embedder.py`, `similarity.py` | `embeddings.py`, `search_in_memory.py` |
| Store and retrieve | `store.py`, `retriever.py` | `ingest.py`, `retrieve.py` |
| Generate | `generator.py` | `ask.py` |

Settled by measurement, not guesswork: `CHUNK_SIZE=350`, `CHUNK_OVERLAP=70`,
`TOP_K=5`, and `MIN_SCORE` deliberately left empty. The reasoning for each is
in `.env.example` and `notes/learning-log.md`.

Verified on the committed dataset of 5 notes, 79,581 characters, 317 chunks:
8 of 8 answerable questions answered with citations, 2 of 2 unanswerable
questions declined.

Also done: README with architecture diagram and a "What I Learned" section,
6 screenshots in `docs/screenshots/`, two draw.io diagrams, MIT licence, CI
running `compileall` on Python 3.11 and 3.12, a 3:30 demo video, and a
fresh-clone test.

**Remaining work is the user's own, not implementation.** The "What I Learned"
section and the mentor answers in `presentation/mentor-questions.md` are
currently written in the agent's words. They need rewriting in the user's voice
before the mentor review, per `learning-guardrails.md` — a follow-up question
in the demo would expose borrowed phrasing immediately.

## Definition of done

- [x] Public GitHub repo named `ask-my-docs`
- [x] A committed `sample-notes/` folder of non-sensitive documents so the
      mentor can run the tool unmodified — 5 notes, 79,581 characters
- [x] README covering: what the tool does and the dataset, setup instructions,
      a "What I Learned" section in the user's own words, the chosen chunk size
      and top-k with reasoning, and a screenshot of a real question, answer and
      citation
- [x] A 3–4 minute demo video showing ingestion and 2–3 live questions — 3:30,
      linked from the README
- [x] Answers cite the document and chunk they came from — `file.md#chunk`, with
      the similarity score
- [x] A question with no good answer in the notes is handled gracefully, not
      hallucinated — verified on 2 unanswerable questions

The "own words" requirement on the README section is met structurally but not
yet in substance; see the note under Current progress.
