---
inclusion: always
---

# Tech Stack & Commands

## Environment

- Windows, PowerShell. Use `;` as the command separator, never `&&`.
- Python 3.12.5, in a venv at `venv/` in the project root.
- Always invoke the venv interpreter explicitly rather than relying on
  activation: `.\venv\Scripts\python.exe`. Activation state does not persist
  between tool calls.

## Dependencies

Pinned in `requirements.txt`. Installed with:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

| Package | Version | Role |
| ------- | ------- | ---- |
| `numpy` | 2.1.3 | vector arithmetic |
| `python-dotenv` | 1.0.1 | reads `.env` |
| `sentence-transformers` | 3.3.1 | local embedding model (pulls torch, CPU build) |
| `openai` | 1.59.6 | optional embedding backend, and the chat model used for generation |
| `pypdf` | 5.1.0 | PDF text extraction |
| `chromadb` | 1.5.9 | vector database |

Before adding anything new, check it against the allow/deny list in
`learning-guardrails.md`.

## Embedding model

Default is local: `sentence-transformers/all-MiniLM-L6-v2`, **384 dimensions**,
output already L2-normalised (so magnitudes come out at 1.0 and cosine
similarity equals the dot product for this model).

The model lives in the Hugging Face cache at
`~/.cache/huggingface/hub`, roughly 90 MB, downloaded once.

**This user's connection drops on long downloads.** The default HF read timeout
of 10 seconds is too short and causes repeated restarts. When a model download
is needed:

```powershell
$env:HF_HUB_DOWNLOAD_TIMEOUT=120
```

Run large downloads as a background process and poll the cache size to track
progress, rather than blocking a foreground call that will time out. Once the
model is cached, `$env:HF_HUB_OFFLINE=1` makes startup fast and avoids network
checks entirely.

## Chroma

Two things that will waste an hour if forgotten.

**Install.** Use the 1.x line. `chromadb` 0.5.x depends on `chroma-hnswlib`, a
C++ extension with no Python 3.12 wheel — pip falls back to compiling it and
fails with `Microsoft Visual C++ 14.0 or greater is required`. The 1.x line
replaced that binding with a Rust core and ships prebuilt wheels.

**Distance metric.** Chroma's default space is **squared L2**, not cosine. Always
create collections with:

```python
configuration={"hnsw": {"space": "cosine"}}
```

Measured: for perpendicular unit vectors the default reports distance 2.0 where
cosine reports 1.0. With cosine, `similarity = 1 - distance` recovers the same
scale as the hand-written cosine in `src/similarity.py`, so scores from
`search_in_memory.py` and from Chroma are directly comparable — which is what
made the 10-of-10 agreement check between them meaningful.
For L2-normalised embeddings the two rank the same way, so getting
this wrong does not raise an error — it silently degrades retrieval the moment a
non-normalising model is used.

Chroma writes to `chroma_db/`, which is gitignored. It is rebuilt by ingestion, so
deleting it is always safe.

To silence its telemetry notice in scripted runs: `$env:ANONYMIZED_TELEMETRY='False'`.

## Configuration

All config goes through `.env`, read in one place, `src/config.py`, with
`.env.example` as the committed template. `.env` is gitignored and must stay
that way — it holds the API key.

The settled values, each chosen by measurement rather than guesswork. The
reasoning for every one is in `.env.example` and `notes/learning-log.md`:

| Setting | Value | Why |
| ------- | ----- | --- |
| `CHUNK_SIZE` | 350 | at 500 a sentence was cut mid-word and never retrieved; at 900 a short section was diluted and stopped matching |
| `CHUNK_OVERLAP` | 70 | one fifth of chunk size, enough to carry a sentence across a cut |
| `TOP_K` | 5 | k=10 cost 3.4x the context for a 0.06 drop in mean relevance; k=3 drew on too few sources |
| `MIN_SCORE` | empty | any floor high enough to reject an unanswerable question also stripped real answers; refusal is handled in the prompt instead |

Generation runs against Gemini through its OpenAI-compatible endpoint, so the
`openai` client is used unchanged — `OPENAI_BASE_URL` points at
`https://generativelanguage.googleapis.com/v1beta/openai/`. Any
OpenAI-compatible provider works the same way.

Switching embedding backend is a single value: `EMBEDDING_BACKEND=local` or
`openai`. Nothing outside `src/embedder.py` should care which is active.

Changing the embedding model invalidates every stored embedding. Re-ingest from
scratch after any such change; never mix vectors from two models in one
collection.

## Running things

The scripts are listed here in pipeline order. Each works standalone.

```powershell
# embeddings and cosine similarity demo
.\venv\Scripts\python.exe scripts\embeddings.py

# chunking pipeline, boundary demo, size/overlap sweep
.\venv\Scripts\python.exe scripts\chunking.py --folder sample-notes

# one chunking configuration only, for a quick check
.\venv\Scripts\python.exe scripts\chunking.py --folder sample-notes --chunk-size 800 --overlap 160

# brute-force search over an in-memory list, before any vector database
.\venv\Scripts\python.exe scripts\search_in_memory.py --folder sample-notes

# load, chunk, embed and persist into Chroma
.\venv\Scripts\python.exe scripts\ingest.py --folder sample-notes

# retrieval only: question in, ranked chunks out, no model involved
.\venv\Scripts\python.exe scripts\retrieve.py --question "why are input and output tokens priced differently?"

# the full pipeline, with a cited answer
.\venv\Scripts\python.exe scripts\ask.py --question "how did I keep my API key safe?"

# show the assembled prompt and stop, without calling any model
.\venv\Scripts\python.exe scripts\ask.py --question "..." --show-prompt
```

`retrieve.py` and `ask.py` both accept `--top-k` and `--min-score` to override
`.env` for one run, and `--no-log` to skip writing to `logs/retrieval.log`.
`--question` is repeatable on `search_in_memory.py`, `retrieve.py` and `ask.py`.

## Console encoding

The Windows console defaults to cp1252, which cannot encode arrows, em dashes or
curly quotes — all common in real notes. Printing one raises `UnicodeEncodeError`
and kills the script, with the crash coming from *display* rather than from any
logic fault.

Every script must call `enable_utf8_output()` from `src/console.py` before
printing. When running a script from PowerShell and expecting non-ASCII output,
also set the console encoding so the text renders rather than mojibakes:

```powershell
[Console]::OutputEncoding=[Text.Encoding]::UTF8
```

Scripts in `scripts/` are named for what they do, not numbered — the pipeline
order is documented in `structure.md` and in the Running things block above.
Each one must work standalone, since they double as the demo material for the
video.

## Testing

The brief does not ask for a test suite, and none exists. Do not add one
unprompted. Verification is by running the scripts and inspecting output, which
is also what the mentor will do.

`py_compile` runs automatically on save via a hook — see `.kiro/hooks/`.
