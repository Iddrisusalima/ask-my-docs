---
inclusion: always
---

# Project Structure & Conventions

## Layout

```
ASK-MY-DOCS/
├── .kiro/
│   ├── steering/            # these files
│   ├── specs/ask-my-docs/   # requirements, design, tasks
│   └── hooks/               # automation
├── .github/workflows/       # CI: compileall on Python 3.11 and 3.12
├── src/                     # importable pipeline modules
│   ├── __init__.py
│   ├── console.py           # UTF-8 stdout, so cp1252 cannot crash on a dash
│   ├── config.py            # reads .env, one place that knows the defaults
│   ├── loader.py            # read .md, .txt and .pdf from a folder
│   ├── chunker.py           # overlapping windows, cut on a soft boundary
│   ├── embedder.py          # text -> embeddings, local or OpenAI
│   ├── similarity.py        # hand-written cosine similarity
│   ├── store.py             # Chroma wrapper, cosine space
│   ├── retriever.py         # question -> top-k chunks
│   ├── retrieval_log.py     # append retrieval results to logs/
│   └── generator.py         # context + question -> cited answer
├── scripts/                 # runnable, demo-able, one pipeline stage each
│   ├── embeddings.py        # embeddings and cosine similarity demo
│   ├── chunking.py          # chunking pipeline, boundary demo, size sweep
│   ├── search_in_memory.py  # brute-force scan, before the vector DB
│   ├── ingest.py            # load -> chunk -> embed -> persist to Chroma
│   ├── retrieve.py          # question -> ranked chunks, no model involved
│   └── ask.py               # the full pipeline, with --show-prompt
├── notes/
│   └── learning-log.md      # the user's learning log, organised by stage
├── docs/
│   ├── architecture.drawio          # detailed, for the mentor
│   ├── architecture-overview.drawio # recruiter-facing
│   └── screenshots/                 # evidence for README claims
├── presentation/            # gitignored: decks, demo script, mentor questions
├── sample-notes/            # committed test dataset, non-sensitive
├── logs/                    # gitignored retrieval logs
├── chroma_db/               # gitignored, rebuilt by ingestion
├── venv/                    # gitignored
├── .env                     # gitignored, real secrets
├── .env.example             # committed template
├── requirements.txt
├── LICENSE                  # MIT
└── README.md
```

Scripts are ordered above in the sequence the pipeline runs, which is also the
order they were built. Each one works standalone, since they double as the demo
material for the video.

## Where things go

- **`src/`** holds logic, imports cleanly, prints nothing except explicit
  progress messages prefixed like `[embedder]`.
- **`scripts/`** holds presentation: prints, section headers, formatted tables.
  Scripts orchestrate `src/` modules and own all the narration.
- **`notes/learning-log.md`** is the user's writing, organised by pipeline stage
  rather than by calendar week. Add measurements and results here; leave the
  prose sections for the user (see `learning-guardrails.md`).
- **`docs/`** holds the diagrams and the screenshots the README cites. Every
  screenshot has a `.txt` transcript beside it so the text is searchable and
  reviewable without opening an image.

Keeping print formatting out of `src/` is what lets the same retrieval function
serve the CLI, the logs, and the demo without duplication.

## Script path bootstrap

Scripts run from the project root and need `src/` importable. Every script
starts with:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

## Code conventions

- `from __future__ import annotations` at the top of every module.
- Type hints on all public functions.
- Google-style docstrings with `Args:`, `Returns:`, `Raises:`.
- Module-level docstrings explain the *concept*, not just the API — these are
  part of how the user learns the material, and they are the first thing the
  mentor reads. `src/embedder.py` and `src/similarity.py` set the standard.
- Error messages must say what to do next, not just what broke. Compare
  "invalid backend" against "Unknown embedding backend 'foo'. Expected one of:
  local, openai. Check EMBEDDING_BACKEND in your .env file."
- No single-letter variable names outside tight numeric loops.
- British or American spelling, either is fine, just stay consistent per file.

## Git

- Commit at the end of each work session, using Conventional Commits:
  `type(scope): Subject`. The types in use are `feat`, `fix`, `docs`,
  `refactor`, `test` and `chore`; the scope is the area touched, such as
  `scripts`, `README` or `repo`. Example:
  `refactor(scripts): Remove weekday references from terminal output`.
- Never commit `.env`, `venv/`, `chroma_db/`, `logs/`, `presentation/`, or the
  HF model cache.
- `sample-notes/` **is** committed — the mentor must be able to run the tool
  without supplying their own data.
- The remote is `github.com/Iddrisusalima/ask-my-docs`.

## Presentation decks

`presentation/` is **gitignored** — it holds the mentor check-in deck, the demo
video script and the mentor question list, none of which belong in a repo a
reviewer clones. The files stay on disk; they are simply not part of the
submission. `.github/workflows/ci.yml` therefore runs `compileall` against
`src/` and `scripts/` only.

`presentation/build_deck.py` generates `review-deck.pptx` for the mentor
check-in. Decks are generated from a script rather than hand-edited so that every
figure traces back to a recorded run, and so a deck can be regenerated after new
measurements instead of being patched by hand.

Two rules for decks:

- **Every number must already exist in `notes/`.** If a figure is not in the
  learning log, it does not belong on a slide. The log is the source of truth.
- **Own-words slides stay blank.** Slides covering explanations the user must
  give verbally are left as placeholders with the evidence listed underneath,
  per `learning-guardrails.md`. Filling them in would defeat the purpose.

Needs `python-pptx`, deliberately **not** in `requirements.txt` — the tool does
not need it, and a reviewer cloning the repo should not have to install it:

```powershell
.\venv\Scripts\python.exe -m pip install python-pptx==1.0.2
.\venv\Scripts\python.exe presentation\build_deck.py
```

To check a deck renders correctly, export to PNG through PowerPoint COM and look
at the slides. If the COM server errors with `CO_E_SERVER_EXEC_FAILURE`, kill
stale `POWERPNT` processes first.
