"""
Reading the tuned settings out of .env.

Four numbers in this project were chosen by measurement rather than taste:
chunk size, chunk overlap, top-k, and the relevance floor. Each one has a
paragraph of justification in notes/ behind it.

They live in .env so that changing one does not mean editing code, and so the
values a reviewer sees in .env.example are the values the tool actually runs
with. Hardcoding a default in three different scripts is how a documented
setting quietly stops being the real one.

Every getter takes an override, because command-line flags must still win over
the file - that is what makes the experiments in `02_chunking_demo.py` and
`05_retrieve.py` possible without editing config between runs.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Fallbacks, used only when .env is missing the key entirely. These match the
# values recorded in the learning logs.
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 5


def _read_int(name: str, fallback: int) -> int:
    """Read an integer setting, failing with a message that names the fix."""
    raw = os.getenv(name)

    if raw is None or not raw.strip():
        return fallback

    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"{name} in your .env file should be a whole number, but it is {raw!r}. "
            f"Either fix it or remove the line to fall back to {fallback}."
        ) from exc


def chunk_size(override: int | None = None) -> int:
    """Characters per chunk. CLI flag beats .env beats the fallback."""
    if override is not None:
        return override
    return _read_int("CHUNK_SIZE", DEFAULT_CHUNK_SIZE)


def chunk_overlap(override: int | None = None) -> int:
    """Characters repeated between consecutive chunks."""
    if override is not None:
        return override
    return _read_int("CHUNK_OVERLAP", DEFAULT_CHUNK_OVERLAP)


def top_k(override: int | None = None) -> int:
    """How many chunks retrieval returns per question."""
    if override is not None:
        return override
    return _read_int("TOP_K", DEFAULT_TOP_K)


def min_score(override: float | None = None) -> float | None:
    """Similarity floor, or None for no floor.

    Returning None rather than 0.0 for "unset" is deliberate. A floor of 0.0
    would still reject negative-scoring chunks, which is a real behaviour change
    dressed up as a default. None means the filter is genuinely off.
    """
    if override is not None:
        return override

    raw = os.getenv("MIN_SCORE")
    if raw is None or not raw.strip():
        return None

    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"MIN_SCORE in your .env file should be a decimal between 0 and 1, "
            f"but it is {raw!r}. Remove the line to run with no floor."
        ) from exc


def describe() -> dict[str, object]:
    """All four settings, for printing at the top of a run or logging alongside results."""
    return {
        "chunk_size": chunk_size(),
        "chunk_overlap": chunk_overlap(),
        "top_k": top_k(),
        "min_score": min_score(),
    }
