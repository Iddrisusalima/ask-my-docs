"""
Storing embedded chunks in Chroma, a real vector database.

What changes from the in-memory store
-----------------------
Friday's store was a Python list and the search was a `for` loop comparing the
question against every chunk. That was *exact*: it looked at everything, so it
could not miss a match. Its weakness was only that the work grows linearly with
the corpus.

Chroma replaces the loop with an HNSW index. HNSW is an **approximate** nearest
neighbour structure - it builds a layered graph of chunks linked to their
neighbours, then answers a query by greedily walking that graph toward the
target, touching a small fraction of the data. Search time grows roughly
logarithmically rather than linearly.

The trade is real and worth stating plainly: the index can miss a true nearest
neighbour that the brute-force loop would have found. We accept a small
correctness loss for a large speed gain. Two of its knobs govern that balance,
and Chroma exposes both:

- `ef_construction` (default 100) - how thoroughly the graph is built
- `ef_search` (default 100) - how widely each query explores before settling

Raise them for better recall and slower operation; lower them for the reverse.

Two decisions in this module that are easy to get wrong
------------------------------------------------------
1. **Cosine space must be set explicitly.** Chroma's default is squared L2. On
   this corpus a query against perpendicular unit vectors returns distance 2.0
   under the default and 1.0 under cosine - different numbers and, for
   non-normalised embeddings, a different *ranking*. This project uses cosine
   similarity, so cosine is what we configure.

2. **We pass in our own embeddings.** Chroma will happily embed text for you,
   which would hide the stage that was built by hand earlier. `src/embedder.py`
   stays in charge; this module only stores what it produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.chunker import Chunk

DEFAULT_DB_PATH = "chroma_db"
DEFAULT_COLLECTION = "notes"

# Chroma rejects oversized writes; batching keeps ingestion safe on large corpora.
ADD_BATCH_SIZE = 500

# Metadata keys we use to record which embedding model produced a collection.
MODEL_KEY = "embedding_model"
DIMENSIONS_KEY = "embedding_dimensions"


class VectorStoreError(Exception):
    """The store cannot answer - not indexed yet, or indexed by a different model."""


@dataclass(frozen=True)
class StoredMatch:
    """A chunk returned by the database, still expressed as a *distance*.

    Distance, not similarity, on purpose. Chroma speaks distance (lower is
    better) and the rest of this project uses similarity (higher is better). Converting in one
    place - `src/retriever.py` - means every score the user ever sees points the
    same way. Mixing the two conventions is a reliable source of confusion, so
    the raw form is kept only as far as this boundary.
    """

    chunk: Chunk
    distance: float


class VectorStore:
    """A persistent Chroma collection holding embedded chunks.

    Args:
        path: Directory for the on-disk database. Created if absent.
        collection: Collection name within the database.

    Example:
        >>> store = VectorStore()
        >>> store.reset(embedding_model="local:all-MiniLM-L6-v2", dimensions=384)
        >>> store.add_chunks(chunks, embeddings)
        >>> store.count()
        155
    """

    def __init__(self, path: str | Path = DEFAULT_DB_PATH, collection: str = DEFAULT_COLLECTION):
        self.path = Path(path)
        self.collection_name = collection
        self._client = None
        self._collection = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @property
    def client(self):
        """The Chroma client, created on first use."""
        if self._client is None:
            try:
                import chromadb
            except ImportError as exc:  # pragma: no cover - environment problem
                raise ImportError(
                    "The vector store needs chromadb. Install it with:\n"
                    "  pip install chromadb==1.5.9\n"
                    "Note: the older 0.5.x line needs a C++ compiler on Windows."
                ) from exc

            self.path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.path))

        return self._client

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def reset(self, embedding_model: str, dimensions: int) -> None:
        """Delete any existing collection and create an empty one.

        Full rebuild rather than upsert. Re-embedding a few hundred chunks costs
        seconds, and rebuilding from scratch rules out a whole category of
        duplicate and stale-chunk bugs that are tedious to diagnose. It also
        makes ingestion idempotent: running it twice leaves the same state as
        running it once.

        Args:
            embedding_model: Identifier of the model producing the embeddings,
                recorded on the collection so a later mismatch can be detected.
            dimensions: Length of each embedding, recorded for the same reason.
        """
        try:
            self.client.delete_collection(name=self.collection_name)
        except Exception:
            # Nothing to delete on a first run; not an error.
            pass

        self._collection = self.client.create_collection(
            name=self.collection_name,
            # Cosine, not Chroma's squared-L2 default. See module docstring.
            configuration={"hnsw": {"space": "cosine"}},
            metadata={MODEL_KEY: embedding_model, DIMENSIONS_KEY: dimensions},
        )

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        """Store chunks alongside their embeddings.

        Args:
            chunks: Chunks to store.
            embeddings: One embedding per chunk, same order.

        Returns:
            How many chunks were written.

        Raises:
            ValueError: If the two lists differ in length, which would silently
                pair chunks with the wrong embeddings and corrupt every citation.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Got {len(chunks)} chunks but {len(embeddings)} embeddings. "
                "These must correspond one-to-one, in order."
            )

        if not chunks:
            return 0

        collection = self._require_collection()

        for start in range(0, len(chunks), ADD_BATCH_SIZE):
            batch_chunks = chunks[start : start + ADD_BATCH_SIZE]
            batch_embeddings = embeddings[start : start + ADD_BATCH_SIZE]

            collection.add(
                ids=[chunk.chunk_id for chunk in batch_chunks],
                embeddings=batch_embeddings,
                documents=[chunk.text for chunk in batch_chunks],
                metadatas=[_metadata_for(chunk) for chunk in batch_chunks],
            )

        return len(chunks)

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def query(self, embedding: list[float], top_k: int = 5) -> list[StoredMatch]:
        """Find the nearest stored chunks to an embedding.

        Args:
            embedding: The query embedding, from the same model as the index.
            top_k: How many results to return. Asking for more than the
                collection holds returns everything rather than erroring.

        Returns:
            Matches ordered nearest first, carrying raw distances.

        Raises:
            VectorStoreError: If the collection is missing or empty.
        """
        collection = self._open_existing()
        total = collection.count()

        if total == 0:
            raise VectorStoreError(
                f"The '{self.collection_name}' collection is empty - nothing has been indexed yet.\n"
                "Run ingestion first:\n"
                "  python scripts/ingest.py --folder sample-notes"
            )

        # Requesting more than exists is an error in Chroma, so clamp it.
        wanted = max(1, min(top_k, total))

        result = collection.query(
            query_embeddings=[embedding],
            n_results=wanted,
            include=["documents", "metadatas", "distances"],
        )

        return _to_matches(result)

    def count(self) -> int:
        """How many chunks are stored. Zero if the collection does not exist."""
        try:
            return self._open_existing().count()
        except VectorStoreError:
            return 0

    def describe_index(self) -> dict:
        """The collection's HNSW settings, for inspecting the speed/recall trade."""
        collection = self._open_existing()
        try:
            return dict(collection.configuration_json.get("hnsw") or {})
        except Exception:
            return {}

    def embedding_model(self) -> str | None:
        """Which model produced this collection, or None if unrecorded."""
        try:
            metadata = self._open_existing().metadata or {}
        except VectorStoreError:
            return None
        return metadata.get(MODEL_KEY)

    def assert_model_matches(self, embedding_model: str) -> None:
        """Fail loudly if the collection was built by a different model.

        This is the guard against the pipeline's nastiest silent failure. Embeddings
        from two different models are not comparable, but querying across them
        raises nothing - it returns confident, well-formed, meaningless results.
        Better a clear error than answers quietly sourced from noise.

        Raises:
            VectorStoreError: If the recorded model differs from the one given.
        """
        recorded = self.embedding_model()

        if recorded is None:
            # Older collection with no recorded model; nothing to compare.
            return

        if recorded != embedding_model:
            raise VectorStoreError(
                f"This collection was built with '{recorded}' but you are querying with "
                f"'{embedding_model}'.\n"
                "Embeddings from different models are not comparable - results would look "
                "plausible and mean nothing.\n"
                "Re-index with the current model:\n"
                "  python scripts/ingest.py --folder sample-notes"
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_collection(self):
        """The collection created by `reset`, for writing."""
        if self._collection is None:
            raise VectorStoreError("Call reset() before adding chunks.")
        return self._collection

    def _open_existing(self):
        """Open the collection for reading, without creating it."""
        if self._collection is not None:
            return self._collection

        try:
            self._collection = self.client.get_collection(name=self.collection_name)
        except Exception as exc:
            raise VectorStoreError(
                f"No '{self.collection_name}' collection found in {self.path.resolve()}.\n"
                "Run ingestion first:\n"
                "  python scripts/ingest.py --folder sample-notes"
            ) from exc

        return self._collection


# ----------------------------------------------------------------------
# Translating between Chunk objects and Chroma's records
# ----------------------------------------------------------------------


def _metadata_for(chunk: Chunk) -> dict:
    """Flatten a Chunk's provenance into Chroma-safe metadata.

    Chroma accepts only str, int, float and bool values - a None is rejected
    outright. Since `page` is None for markdown, the key is omitted rather than
    given a sentinel like -1, which would later have to be remembered and
    translated back.
    """
    metadata: dict[str, str | int | float | bool] = {
        "source": chunk.source,
        "chunk_index": chunk.chunk_index,
        "start_char": chunk.start_char,
    }

    if chunk.page is not None:
        metadata["page"] = chunk.page

    return metadata


def _to_matches(result: dict) -> list[StoredMatch]:
    """Rebuild Chunk objects from a Chroma query response."""
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    matches: list[StoredMatch] = []

    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        metadata = metadata or {}
        chunk = Chunk(
            chunk_id=chunk_id,
            text=text or "",
            source=str(metadata.get("source", "unknown")),
            chunk_index=int(metadata.get("chunk_index", 0)),
            start_char=int(metadata.get("start_char", 0)),
            page=int(metadata["page"]) if "page" in metadata else None,
        )
        matches.append(StoredMatch(chunk=chunk, distance=float(distance)))

    return matches
