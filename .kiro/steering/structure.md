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
├── src/                     # importable pipeline modules
│   ├── __init__.py
│   ├── embedder.py          # text -> embeddings, local or OpenAI
│   ├── similarity.py        # hand-written cosine similarity
│   ├── console.py           # UTF-8 stdout, so cp1252 cannot crash on a dash
│   ├── loader.py            # read .md, .txt and .pdf from a folder
│   ├── chunker.py           # fixed-size chunks with overlap
│   ├── store.py             # (Week 2) Chroma wrapper
│   ├── retriever.py         # (Week 2) question -> top-k chunks
│   └── generator.py         # (Week 3) context + question -> cited answer
├── scripts/                 # numbered, runnable, demo-able
│   ├── 01_embedding_basics.py
│   └── 02_chunking_demo.py
├── notes/                   # the user's written learning log per week
├── presentation/            # mentor check-in decks + the script that builds them
├── sample-notes/            # committed test dataset, non-sensitive
├── logs/                    # gitignored retrieval logs (Week 2 Fri)
├── venv/                    # gitignored
├── .env                     # gitignored, real secrets
├── .env.example             # committed template
├── requirements.txt
└── README.md                # written in Week 3
```

Files listed above that do not exist yet are planned, not missing. Create them
when their week arrives rather than stubbing them early.

## Where things go

- **`src/`** holds logic, imports cleanly, prints nothing except explicit
  progress messages prefixed like `[embedder]`.
- **`scripts/`** holds presentation: prints, section headers, formatted tables.
  Scripts orchestrate `src/` modules and own all the narration.
- **`notes/`** is the user's writing. Add measurements and results here; leave
  the prose sections for the user (see `learning-guardrails.md`).

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

- Commit at the end of each work session, message prefixed with the week and
  day: `Week 1 Mon-Tue: ...`.
- Never commit `.env`, `venv/`, `chroma_db/`, `logs/`, or the HF model cache.
- `sample-notes/` **is** committed — the mentor must be able to run the tool
  without supplying their own data.
- The remote repo must be named `ask-my-docs`.

## Presentation decks

`presentation/build_week1_deck.py` generates `week1-review.pptx` for the mentor
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
.\venv\Scripts\python.exe presentation\build_week1_deck.py
```

To check a deck renders correctly, export to PNG through PowerPoint COM and look
at the slides. If the COM server errors with `CO_E_SERVER_EXEC_FAILURE`, kill
stale `POWERPNT` processes first.
