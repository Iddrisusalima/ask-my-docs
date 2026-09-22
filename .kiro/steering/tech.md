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
| `openai` | 1.59.6 | optional embedding backend, and Week 3 chat model |
| `pypdf` | 5.1.0 | PDF text extraction |
| `chromadb` | 0.5.23 | vector database, Week 2 |

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

## Configuration

All config goes through `.env`, with `.env.example` as the committed template.
`.env` is gitignored and must stay that way — it holds the OpenAI key.

Switching embedding backend is a single value: `EMBEDDING_BACKEND=local` or
`openai`. Nothing outside `src/embedder.py` should care which is active.

Changing the embedding model invalidates every stored embedding. Re-ingest from
scratch after any such change; never mix vectors from two models in one
collection.

## Running things

```powershell
# Week 1 Mon-Tue: embeddings and cosine similarity demo
.\venv\Scripts\python.exe scripts\01_embedding_basics.py

# Week 1 Wed-Thu: chunking pipeline, boundary demo, size/overlap sweep
.\venv\Scripts\python.exe scripts\02_chunking_demo.py --folder sample-notes

# one configuration only, for a quick check
.\venv\Scripts\python.exe scripts\02_chunking_demo.py --folder sample-notes --chunk-size 800 --overlap 160
```

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

Scripts in `scripts/` are numbered in the order the brief introduces them and
are meant to be run directly. Each one must work standalone, since they double
as the demo material for the video.

## Testing

The brief does not ask for a test suite, and none exists. Do not add one
unprompted. Verification is by running the scripts and inspecting output, which
is also what the mentor will do.

`py_compile` runs automatically on save via a hook — see `.kiro/hooks/`.
