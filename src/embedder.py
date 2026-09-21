"""
Turning text into embeddings.

What is an embedding?
---------------------
An embedding model reads a piece of text and outputs a fixed-length list of
numbers. The model was trained so that texts with similar *meaning* get similar
numbers, even when they share no words at all. "I need to reset my password"
and "how do I recover my login?" end up near each other; "the cat sat on the
mat" ends up somewhere else entirely.

Two things worth internalising:

1. The length of the output never changes. Feed in one word or three
   paragraphs, `all-MiniLM-L6-v2` always returns 384 numbers. That fixed shape
   is exactly what makes the numbers comparable, and it's also why very long
   inputs lose detail - everything gets squeezed into the same budget. That is
   the real reason we chunk documents (Week 1, Wed-Thu).

2. The numbers are only meaningful relative to other numbers from *the same
   model*. You cannot compare a MiniLM embedding to an OpenAI embedding. If you
   switch models, you must re-embed everything.

This module hides which provider we use behind one small class, so the rest of
the project never has to care.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

# Read .env once, at import time. Existing real environment variables win.
load_dotenv()

# Defaults, overridable in .env
DEFAULT_BACKEND = "local"
DEFAULT_LOCAL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_OPENAI_MODEL = "text-embedding-3-small"

SUPPORTED_BACKENDS = ("local", "openai")


class Embedder:
    """Converts text into embeddings using either a local model or OpenAI.

    Args:
        backend: "local" or "openai". Defaults to EMBEDDING_BACKEND from .env.
        model_name: Override the model. Defaults to the per-backend model
            configured in .env.

    Example:
        >>> embedder = Embedder()
        >>> vector = embedder.embed("Embeddings turn meaning into numbers.")
        >>> len(vector)
        384
    """

    def __init__(self, backend: str | None = None, model_name: str | None = None):
        self.backend = (backend or os.getenv("EMBEDDING_BACKEND", DEFAULT_BACKEND)).strip().lower()

        if self.backend not in SUPPORTED_BACKENDS:
            raise ValueError(
                f"Unknown embedding backend {self.backend!r}. "
                f"Expected one of: {', '.join(SUPPORTED_BACKENDS)}. "
                "Check EMBEDDING_BACKEND in your .env file."
            )

        if model_name:
            self.model_name = model_name
        elif self.backend == "local":
            self.model_name = os.getenv("LOCAL_EMBEDDING_MODEL", DEFAULT_LOCAL_MODEL)
        else:
            self.model_name = os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_OPENAI_MODEL)

        # The model itself is loaded lazily, on first use. Loading a local model
        # takes a few seconds, so we avoid paying that cost just to import.
        self._model = None
        self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Embed a single string and return its vector."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                "Cannot embed empty text. An embedding describes meaning, "
                "and there is no meaning in an empty string."
            )
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed many strings at once.

        Always prefer this over calling `embed` in a loop. Batching is
        dramatically faster locally (the model processes them in parallel) and
        far cheaper against an API (one request instead of N).
        """
        if not texts:
            return []

        blank_positions = [i for i, t in enumerate(texts) if not isinstance(t, str) or not t.strip()]
        if blank_positions:
            raise ValueError(
                f"Cannot embed empty text at position(s) {blank_positions}. "
                "Filter out blank chunks before embedding."
            )

        if self.backend == "local":
            return self._embed_local(texts)
        return self._embed_openai(texts)

    @property
    def dimensions(self) -> int:
        """How many numbers are in each vector this model produces."""
        return len(self.embed("dimension probe"))

    def describe(self) -> str:
        """A one-line summary, useful for logs and README screenshots."""
        return f"{self.backend}:{self.model_name}"

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._model = _load_local_model(self.model_name)

        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [vector.tolist() for vector in vectors]

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            self._client = _build_openai_client()

        response = self._client.embeddings.create(model=self.model_name, input=texts)
        # The API does not guarantee ordering, but it does return an index on
        # each item. Sorting by it keeps vectors aligned with the input texts.
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]


# ----------------------------------------------------------------------
# Loader helpers, cached so we only ever hold one copy of a model in memory
# ----------------------------------------------------------------------


@lru_cache(maxsize=4)
def _load_local_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - environment problem
        raise ImportError(
            "The 'local' backend needs sentence-transformers.\n"
            "Install it with:  pip install sentence-transformers\n"
            "Or switch to EMBEDDING_BACKEND=openai in your .env file."
        ) from exc

    print(f"[embedder] loading local model {model_name} (first run downloads it)...")
    return SentenceTransformer(model_name)


def _build_openai_client():
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - environment problem
        raise ImportError(
            "The 'openai' backend needs the openai package.\n"
            "Install it with:  pip install openai"
        ) from exc

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file, "
            "or switch to EMBEDDING_BACKEND=local to run fully offline."
        )

    return OpenAI()
