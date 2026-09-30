"""
Week 2, Mon-Tue: Index the chunks into a real vector database.

Run it:
    python scripts/04_ingest.py --folder sample-notes
    python scripts/04_ingest.py --folder sample-notes --chunk-size 800 --overlap 160

This is the ingestion half of the pipeline, and it runs once per change to the
notes folder:

    load -> chunk -> embed -> index

The query half (Wed-Thu) then reuses the stored index for every question.

The script also answers the question the brief sets for this week - how does the
database actually perform similarity search - by measuring it against Friday's
brute-force loop rather than just describing it. Part 5 checks whether Chroma's
approximate index returns the same chunks the exact scan found.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.chunker import chunk_documents, chunk_statistics
from src.console import enable_utf8_output
from src.embedder import Embedder
from src.loader import DocumentLoadError, load_documents
from src.similarity import cosine_similarity
from src.store import VectorStore, VectorStoreError

enable_utf8_output()

SMOKE_TEST_QUESTIONS = [
    "Why does overlap between chunks matter?",
    "How should I choose how many results to retrieve?",
]


def rule(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def exact_search(
    embeddings: list[list[float]], chunk_ids: list[str], query_embedding: list[float], top_k: int
) -> list[tuple[float, str]]:
    """Friday's brute-force scan, kept as the yardstick for the index.

    Compares against every embedding, so its answer is exact by construction.
    That makes it the right baseline for measuring what the approximate index
    misses.
    """
    scored = [
        (cosine_similarity(query_embedding, embedding), chunk_id)
        for embedding, chunk_id in zip(embeddings, chunk_ids)
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:top_k]


def main() -> int:
    parser = argparse.ArgumentParser(description="Load, chunk, embed and index a folder of notes.")
    parser.add_argument("--folder", default="sample-notes", help="Folder of documents to ingest")
    parser.add_argument("--chunk-size", type=int, default=None, help="Overrides CHUNK_SIZE in .env")
    parser.add_argument("--overlap", type=int, default=None, help="Overrides CHUNK_OVERLAP in .env")
    parser.add_argument("--db", default="chroma_db", help="Directory for the Chroma database")
    parser.add_argument("--collection", default="notes")
    parser.add_argument("--top-k", type=int, default=None, help="Results for the smoke-test queries")
    arguments = parser.parse_args()

    # .env holds the values chosen by measurement; flags override for experiments.
    arguments.chunk_size = config.chunk_size(arguments.chunk_size)
    arguments.overlap = config.chunk_overlap(arguments.overlap)
    arguments.top_k = config.top_k(arguments.top_k)

    # ------------------------------------------------------------------
    rule("STEP 1  Load")
    # ------------------------------------------------------------------
    try:
        documents = load_documents(arguments.folder)
    except DocumentLoadError as exc:
        print(f"[error] {exc}")
        return 1

    sources = sorted({document.source for document in documents})
    print(f"{len(sources)} file(s) -> {len(documents)} document(s)")

    # ------------------------------------------------------------------
    rule("STEP 2  Chunk")
    # ------------------------------------------------------------------
    chunks = chunk_documents(documents, arguments.chunk_size, arguments.overlap)

    if not chunks:
        print("[error] Documents loaded but produced no chunks. Are they all whitespace?")
        return 1

    stats = chunk_statistics(chunks)
    print(
        f"chunk_size={arguments.chunk_size}, overlap={arguments.overlap} -> "
        f"{stats['count']} chunks, mean {stats['mean']:.1f} chars "
        f"(min {stats['min']}, max {stats['max']})"
    )

    # ------------------------------------------------------------------
    rule("STEP 3  Embed")
    # ------------------------------------------------------------------
    try:
        embedder = Embedder()
        started = time.perf_counter()
        embeddings = embedder.embed_batch([chunk.text for chunk in chunks])
        embed_seconds = time.perf_counter() - started
    except (ImportError, RuntimeError) as exc:
        print(f"[setup problem] {exc}")
        return 1

    dimensions = len(embeddings[0])
    model_id = embedder.describe()

    print(f"model:      {model_id}")
    print(f"dimensions: {dimensions}")
    print(f"embedded:   {len(embeddings)} chunks in {embed_seconds:.2f}s "
          f"({embed_seconds / len(embeddings) * 1000:.1f}ms each)")

    # ------------------------------------------------------------------
    rule("STEP 4  Index into Chroma")
    # ------------------------------------------------------------------
    store = VectorStore(path=arguments.db, collection=arguments.collection)

    existing = store.count()
    if existing:
        print(f"collection already holds {existing} chunks - rebuilding from scratch")

    try:
        started = time.perf_counter()
        # Recording the model on the collection is what makes the mismatch check
        # in step 6 possible.
        store.reset(embedding_model=model_id, dimensions=dimensions)
        written = store.add_chunks(chunks, embeddings)
        index_seconds = time.perf_counter() - started
    except (VectorStoreError, ImportError, ValueError) as exc:
        print(f"[error] {exc}")
        return 1

    print(f"indexed:    {written} chunks in {index_seconds:.2f}s")
    print(f"database:   {Path(arguments.db).resolve()}")
    print(f"collection: {arguments.collection}")

    index_settings = store.describe_index()
    if index_settings:
        print(f"\nHNSW settings Chroma is using:")
        for key in ("space", "ef_construction", "ef_search", "max_neighbors"):
            if key in index_settings:
                print(f"  {key:<16} {index_settings[key]}")
        print(
            "\n  space=cosine was set explicitly. Chroma's default is squared L2,\n"
            "  which would have reported distance 2.0 where cosine reports 1.0 -\n"
            "  and ranked non-normalised embeddings differently from Week 1.\n"
            "  ef_search is the speed/recall dial: higher explores more of the\n"
            "  graph per query, finds more true neighbours, and costs more time."
        )

    # ------------------------------------------------------------------
    rule("STEP 5  Confirm it persisted")
    # ------------------------------------------------------------------
    # A fresh VectorStore object, opening the collection from disk rather than
    # reusing the one just written to. This is the property the in-memory list
    # from Friday did not have.
    reopened = VectorStore(path=arguments.db, collection=arguments.collection)
    print(f"reopened from disk: {reopened.count()} chunks")
    print(f"recorded model:     {reopened.embedding_model()}")
    print(
        "\nFriday's store was a Python list and vanished when the process exited.\n"
        "Every question meant re-embedding the whole corpus first - 30 seconds\n"
        "before answering anything. This survives restarts, so that cost is now\n"
        "paid once per change to the notes instead of once per run."
    )

    # ------------------------------------------------------------------
    rule("STEP 6  The model-mismatch guard")
    # ------------------------------------------------------------------
    try:
        reopened.assert_model_matches(model_id)
        print(f"matching model ({model_id}): passes")
    except VectorStoreError as exc:
        print(f"unexpected failure: {exc}")
        return 1

    try:
        reopened.assert_model_matches("openai:text-embedding-3-small")
        print("PROBLEM: a mismatched model was not detected")
        return 1
    except VectorStoreError:
        print("mismatched model (openai:text-embedding-3-small): correctly rejected")

    print(
        "\nThis is the pipeline's nastiest silent failure. Querying an index built\n"
        "by a different model raises nothing on its own - it returns confident,\n"
        "well-formed, meaningless results. Recording the model on the collection\n"
        "turns that silence into an error message."
    )

    # ------------------------------------------------------------------
    rule("STEP 7  Approximate index vs exact scan")
    # ------------------------------------------------------------------
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    agreements = 0
    comparisons = 0

    for question in SMOKE_TEST_QUESTIONS:
        question_embedding = embedder.embed(question)

        started = time.perf_counter()
        approximate = reopened.query(question_embedding, top_k=arguments.top_k)
        approximate_seconds = time.perf_counter() - started

        started = time.perf_counter()
        exact = exact_search(embeddings, chunk_ids, question_embedding, arguments.top_k)
        exact_seconds = time.perf_counter() - started

        approximate_ids = [match.chunk.chunk_id for match in approximate]
        exact_ids = [chunk_id for _, chunk_id in exact]
        shared = set(approximate_ids) & set(exact_ids)

        agreements += len(shared)
        comparisons += len(exact_ids)

        print(f"\nQ: {question}")
        print(f"   Chroma HNSW : {approximate_seconds * 1000:6.1f}ms")
        print(f"   exact scan  : {exact_seconds * 1000:6.1f}ms")
        print(f"   agreement   : {len(shared)}/{len(exact_ids)} of the top-{arguments.top_k}")

        print(f"\n   {'rank':<5} {'chunk (Chroma)':<30} {'distance':>9} {'similarity':>11}")
        for rank, match in enumerate(approximate, start=1):
            similarity = 1.0 - match.distance
            print(f"   {rank:<5} {match.chunk.citation():<30} {match.distance:>9.4f} {similarity:>11.4f}")

    recall = agreements / comparisons if comparisons else 0.0
    print(
        f"\nOverall agreement with the exact scan: {agreements}/{comparisons} ({recall:.0%})"
    )

    if recall == 1.0:
        print(
            "\n100% at this corpus size, which is expected rather than reassuring. With\n"
            "only a few hundred chunks the HNSW graph is small enough that a greedy\n"
            "walk reaches the true nearest neighbours anyway. The approximation only\n"
            "starts costing recall when the graph is large enough that the walk has\n"
            "to skip meaningful portions of it. So this measurement confirms the\n"
            "index is wired up correctly - it does not demonstrate that approximate\n"
            "search is free."
        )
    else:
        print(
            f"\nThe index missed {comparisons - agreements} chunk(s) the exact scan found.\n"
            "That is the approximation showing up. Raising ef_search would recover\n"
            "them at the cost of query time."
        )

    print(
        "\nNote the distance-to-similarity conversion above: cosine distance 0.0 means\n"
        "identical direction, so similarity = 1 - distance puts these back on Week 1's\n"
        "scale where higher is better. src/retriever.py does this conversion once, on\n"
        "Wednesday, so nothing downstream has to remember which way round it is."
    )

    rule("Done")
    print(f"{written} chunks indexed and queryable.")
    print("Next: Wed-Thu, the retrieval function and tuning top-k.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
