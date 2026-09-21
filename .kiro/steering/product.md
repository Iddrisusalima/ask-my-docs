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

The stated Oct 4 deadline now falls at the end of Week 2. **The user is
confirming the real deadline with their mentor.** Until that is settled, plan
against Oct 11 but do not assume it — if the mentor holds Oct 4 firm, Week 3
work has to compress and scope gets cut, starting with the optional extras.

Pace is part-time, roughly 1.5–2 hours per weekday.

## Current progress

Week 1 Mon–Tue is complete: embedding backend chosen and wired, cosine
similarity implemented by hand, similarity demo run with results recorded.

Week 1 Wed–Thu is blocked until the user adds 5–10 of their own `.md` or `.pdf`
notes to `sample-notes/`.

## Definition of done

- Public GitHub repo named `ask-my-docs`
- A committed `sample-notes/` folder of non-sensitive documents so the mentor
  can run the tool unmodified
- README covering: what the tool does and the dataset, setup instructions,
  a "What I Learned" section in the user's own words, the chosen chunk size and
  top-k with reasoning, and a screenshot of a real question, answer and citation
- A 3–4 minute demo video showing ingestion and 2–3 live questions
- Answers cite the document and chunk they came from
- A question with no good answer in the notes is handled gracefully, not
  hallucinated
