"""
Turning a question into the passages that should answer it.

This module is small, and that is the point: it is the seam where three separate
concerns meet, and each one is a place the pipeline can go quietly wrong.

**1. The same model on both sides.** The question must be embedded by the model
that embedded the chunks. Nothing enforces this automatically, and getting it
wrong produces no error - just confident nonsense. `retrieve` checks the
collection's recorded model before doing anything else.

**2. Distance becomes similarity, exactly once, here.** Chroma speaks distance
(lower is better). Week 1 taught similarity (higher is better). Both conventions
are defensible; having both alive in one codebase is not. The conversion happens
at this boundary so that every number anything downstream ever sees points the
same way.

    cosine similarity = 1 - cosine distance

**3. "Nothing relevant" has to be expressible.** A nearest-neighbour search always
returns its top-k. Ask an empty question of a full database and you still get k
chunks back, ranked, looking exactly like real answers. Without a floor there is
no difference between "here is the passage that answers you" and "here are the k
least irrelevant things I have" - and the language model downstream cannot tell
either. `min_score` is what makes the distinction representable.

A caution on that floor, measured in Week 1 Friday rather than assumed: against a
real corpus an unanswerable question scored 0.3386, while the weakest genuinely
useful result scored 0.3655. A gap of 0.027. Week 1 Monday's tidy
0.617-versus-0.031 separation came from sentences chosen to be unrelated; once a
few hundred chunks are in play, something is always somewhat close to anything.

So the floor defaults to **off**. A wrong threshold silently discards correct
answers, which is worse than passing marginal context to a model that has been
told it may refuse. Week 3 uses both defences together.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.chunker import Chunk
from src.embedder import Embedder
from src.store import VectorStore

DEFAULT_TOP_K = 5


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk with its relevance score, on Week 1's scale.

    Attributes:
        chunk: The passage and its provenance.
        score: Cosine similarity. 1.0 is identical direction, 0.0 unrelated,
            negative means pointing the other way. Higher is better - always,
            everywhere downstream of this module.
    """

    chunk: Chunk
    score: float

    def citation(self) -> str:
        """Source label for display, e.g. `notes.md#3 (p.2)`."""
        return self.chunk.citation()

    def describe(self, width: int = 70) -> str:
        """One-line summary for terminal output and logs."""
        return f"{self.score:.4f}  {self.citation():<30} {self.chunk.preview(width)}"


class Retriever:
    """Finds the passages most likely to answer a question.

    Args:
        store: The indexed collection to search.
        embedder: Must be the same model that built the index.

    Example:
        >>> retriever = Retriever(VectorStore(), Embedder())
        >>> results = retriever.retrieve("why does overlap matter?", top_k=3)
        >>> results[0].score
        0.669
    """

    def __init__(self, store: VectorStore, embedder: Embedder):
        self.store = store
        self.embedder = embedder
        self._model_checked = False

    def retrieve(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        min_score: float | None = None,
    ) -> list[RetrievedChunk]:
        """Return the top-k most similar chunks to a question.

        Args:
            question: The question, in natural language.
            top_k: How many chunks to return. More context, more noise.
            min_score: Optional similarity floor. Results scoring below it are
                dropped, so an empty list means "nothing relevant found" rather
                than "no results available".

        Returns:
            Chunks ordered most to least similar. Empty if nothing clears
            `min_score`.

        Raises:
            ValueError: If the question is blank or top_k is not positive.
            VectorStoreError: If the collection is missing, empty, or was built
                by a different embedding model.
        """
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Cannot retrieve for an empty question.")

        if top_k <= 0:
            raise ValueError(f"top_k must be positive, got {top_k}.")

        # Guard against querying an index built by another model. Checked once
        # per Retriever rather than per query, since it cannot change midway.
        if not self._model_checked:
            self.store.assert_model_matches(self.embedder.describe())
            self._model_checked = True

        question_embedding = self.embedder.embed(question)
        matches = self.store.query(question_embedding, top_k=top_k)

        # The one place distance becomes similarity.
        results = [
            RetrievedChunk(chunk=match.chunk, score=1.0 - match.distance)
            for match in matches
        ]

        # Chroma returns nearest-first, so this is already sorted. Sorting again
        # is cheap and means the guarantee does not depend on Chroma's ordering.
        results.sort(key=lambda result: result.score, reverse=True)

        if min_score is not None:
            results = [result for result in results if result.score >= min_score]

        return results

    def retrieve_many(
        self,
        questions: list[str],
        top_k: int = DEFAULT_TOP_K,
        min_score: float | None = None,
    ) -> dict[str, list[RetrievedChunk]]:
        """Retrieve for several questions, for comparing settings side by side."""
        return {
            question: self.retrieve(question, top_k=top_k, min_score=min_score)
            for question in questions
        }


def score_summary(results: list[RetrievedChunk]) -> dict[str, float]:
    """Summarise a result set's scores.

    `spread` is the interesting one. A wide gap between the best and worst hit
    means the ranking is discriminating - the top result is meaningfully better
    than the tail. A narrow gap means everything scored about the same, which
    usually indicates the question found nothing in particular and the ordering
    is close to arbitrary.
    """
    if not results:
        return {"count": 0, "best": 0.0, "worst": 0.0, "mean": 0.0, "spread": 0.0}

    scores = [result.score for result in results]
    return {
        "count": len(scores),
        "best": max(scores),
        "worst": min(scores),
        "mean": sum(scores) / len(scores),
        "spread": max(scores) - min(scores),
    }
