"""
Week 1, Fri: Embed every chunk, keep it in memory, and search it by hand.

Run it:
    python scripts/03_embed_chunks_memory.py
    python scripts/03_embed_chunks_memory.py --folder notes --top-k 5
    python scripts/03_embed_chunks_memory.py --question "how does overlap help?"

This is a complete, working semantic search engine with no database in it. The
store is a Python list; the search is a `for` loop over the cosine similarity
function written on Monday.

Building it this way first is deliberate. On Monday, Chroma arrives and does
this same job, and "it performs similarity search" is a sentence that means
nothing until you have written the loop it replaces. After today you will know
exactly what the database does, and therefore what it actually buys you - which
is not correctness, but speed at scale.

The keyword baseline in Part 4 is here for contrast only. It is not part of the
RAG pipeline and nothing else imports it.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chunker import Chunk, chunk_documents
from src.console import enable_utf8_output
from src.embedder import Embedder
from src.loader import DocumentLoadError, load_documents
from src.similarity import cosine_similarity

enable_utf8_output()

DEFAULT_QUESTIONS = [
    "Why does overlap between chunks matter?",
    "How do I pick how many results to retrieve?",
    "What happens if the notes do not contain the answer?",
]

# A question with no answer anywhere in a corpus of study notes. Used to show
# what "nothing relevant" looks like numerically.
UNANSWERABLE_QUESTION = "What time does the corner shop close on Sundays?"


def rule(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


# ----------------------------------------------------------------------
# The in-memory store: a list of dicts. That is all "vector store" means.
# ----------------------------------------------------------------------


def build_memory_store(
    chunks: list[Chunk], embedder: Embedder
) -> tuple[list[dict], float]:
    """Embed every chunk and hold the results in a plain Python list.

    Returns:
        The store, and how many seconds embedding took.
    """
    texts = [chunk.text for chunk in chunks]

    started = time.perf_counter()
    embeddings = embedder.embed_batch(texts)
    elapsed = time.perf_counter() - started

    # One dict per chunk: the numbers, the text, and where it came from. A real
    # vector database stores exactly these three things - it just indexes the
    # first one so it does not have to scan all of them.
    store = [
        {"embedding": embedding, "text": chunk.text, "chunk": chunk}
        for chunk, embedding in zip(chunks, embeddings)
    ]

    return store, elapsed


def search_memory_store(
    store: list[dict], question: str, embedder: Embedder, top_k: int = 5
) -> tuple[list[tuple[float, Chunk]], float, float]:
    """Find the top-k most similar chunks by comparing against every single one.

    This is a brute-force linear scan: every stored chunk is compared, every
    time. Exact by construction - it cannot miss a match, because it looks at
    all of them. The cost is that it looks at all of them.

    The two phases are timed separately and that distinction matters. Embedding
    the question costs the same whether the corpus holds 10 chunks or 10 million,
    so it tells you nothing about how search scales. Only the scan grows. Lumping
    them together would make the loop look far worse than it is at small sizes,
    and far better than it is at large ones.

    Returns:
        (score, chunk) pairs sorted best first, seconds spent embedding the
        question, and seconds spent scanning the store.
    """
    embed_started = time.perf_counter()
    question_embedding = embedder.embed(question)
    embed_seconds = time.perf_counter() - embed_started

    scan_started = time.perf_counter()
    scored = [
        (cosine_similarity(question_embedding, entry["embedding"]), entry["chunk"])
        for entry in store
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    scan_seconds = time.perf_counter() - scan_started

    return scored[:top_k], embed_seconds, scan_seconds


# ----------------------------------------------------------------------
# Keyword baseline - for contrast in Part 4 only, not part of the pipeline
# ----------------------------------------------------------------------


def keyword_search(
    chunks: list[Chunk], question: str, top_k: int = 5
) -> list[tuple[float, Chunk]]:
    """Rank chunks by how many of the question's words they contain.

    A crude stand-in for keyword search, included to show what semantic search
    does differently. Scores are the fraction of question words present.
    """
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "do", "does", "did",
        "how", "what", "why", "when", "if", "it", "to", "of", "in", "on",
        "and", "or", "not", "i", "my", "me", "for", "that", "this", "with",
    }
    words = {
        word
        for word in re.findall(r"[a-z']+", question.lower())
        if word not in stopwords and len(word) > 2
    }

    if not words:
        return []

    scored = []
    for chunk in chunks:
        body = chunk.text.lower()
        hits = sum(1 for word in words if word in body)
        scored.append((hits / len(words), chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:top_k]


# ----------------------------------------------------------------------
# Parts
# ----------------------------------------------------------------------


def part_1_build(store: list[dict], chunks: list[Chunk], embed_seconds: float, embedder: Embedder) -> None:
    rule("PART 1  Every chunk embedded and held in memory")

    dimensions = len(store[0]["embedding"])
    numbers = len(store) * dimensions

    print(f"Model:            {embedder.describe()}")
    print(f"Chunks embedded:  {len(store)}")
    print(f"Numbers each:     {dimensions}")
    print(f"Numbers total:    {numbers:,}")
    print(f"Time taken:       {embed_seconds:.2f}s  ({embed_seconds / len(store) * 1000:.1f}ms per chunk)")
    print(f"Store type:       {type(store).__name__} of {type(store[0]).__name__}")

    print("\nOne entry, abbreviated:")
    first = store[0]
    print(f"  chunk_id:  {first['chunk'].chunk_id}")
    print(f"  source:    {first['chunk'].source}")
    print(f"  text:      {first['chunk'].preview(60)!r}")
    print(f"  embedding: [{', '.join(f'{v:.4f}' for v in first['embedding'][:4])}, ... {dimensions} total]")

    print(
        "\nThat is the entire store. A list of dicts, each holding the numbers,\n"
        "the text, and where it came from. A vector database stores the same\n"
        "three things - the difference is how it searches them."
    )


def part_2_search(
    store: list[dict], embedder: Embedder, questions: list[str], top_k: int
) -> tuple[list[float], list[float], list[float]]:
    rule("PART 2  Searching it with a for loop")

    embed_times: list[float] = []
    scan_times: list[float] = []
    all_scores: list[float] = []

    for question in questions:
        results, embed_seconds, scan_seconds = search_memory_store(store, question, embedder, top_k)
        embed_times.append(embed_seconds)
        scan_times.append(scan_seconds)
        all_scores.extend(score for score, _ in results)

        print(f"\nQ: {question}")
        print(
            f"   (embed question {embed_seconds * 1000:.1f}ms + "
            f"scan {len(store)} chunks {scan_seconds * 1000:.1f}ms)"
        )

        for rank, (score, chunk) in enumerate(results, start=1):
            print(f"   {rank}. {score:.4f}  {chunk.citation():<28} {chunk.preview(58)}")

    return embed_times, scan_times, all_scores


def part_3_no_good_answer(
    store: list[dict], embedder: Embedder, top_k: int, genuine_scores: list[float]
) -> None:
    rule("PART 3  What 'nothing relevant' looks like")

    results, _, _ = search_memory_store(store, UNANSWERABLE_QUESTION, embedder, top_k)

    print(f"Q: {UNANSWERABLE_QUESTION}\n")
    for rank, (score, chunk) in enumerate(results, start=1):
        print(f"   {rank}. {score:.4f}  {chunk.citation():<28} {chunk.preview(58)}")

    best = results[0][0] if results else 0.0

    print(
        f"\nThe scan still returned {len(results)} chunks, because a linear scan always\n"
        f"returns its top-k - there is no such thing as 'no result'. The best score\n"
        f"is {best:.4f}, against chunks visibly unrelated to the question."
    )

    # The interesting part: does that score actually separate from real answers?
    if genuine_scores:
        overlapping = sorted(score for score in genuine_scores if score <= best)

        print(
            f"\nSo can we just reject anything below {best:.2f}? Compare against the "
            f"{len(genuine_scores)} scores\nthat Part 2's legitimate questions produced:"
        )

        if overlapping:
            shown = ", ".join(f"{score:.4f}" for score in overlapping)
            print(
                f"\n  {len(overlapping)} of them scored at or BELOW the unanswerable "
                f"question's best:\n    {shown}\n"
                "\n  The bands overlap. A floor set high enough to reject the corner shop\n"
                "  would also discard real answers, and a floor low enough to keep those\n"
                "  would let the corner shop through. There is no clean threshold here."
            )
        else:
            lowest_genuine = min(genuine_scores)
            margin = lowest_genuine - best
            print(
                f"\n  All {len(genuine_scores)} scored above it. The lowest real answer scored "
                f"{lowest_genuine:.4f}\n  against the unanswerable question's {best:.4f} - "
                f"a margin of just {margin:.4f}.\n"
                "\n  So a floor does separate them here, but only barely. That is a much\n"
                "  narrower gap than Monday's 0.617-versus-0.031 suggested, and it is not\n"
                "  a number to hardcode confidently off one corpus and four questions.\n"
                "  Week 2 should widen this test before Week 3 depends on it."
            )

    print(
        "\nWorth looking at *why* the top hit scored as well as it did: the question\n"
        "asks about Sundays, and the chunk contains a schedule full of dates and\n"
        "day names. The model is doing its job - those really are related in\n"
        "meaning. It has no concept of whether the relation answers the question.\n"
        "\nThis is the failure Week 3 has to handle. Hand these chunks to a language\n"
        "model as context and it will dutifully attempt an answer from them. Monday's\n"
        "clean 0.03-versus-0.62 gap came from sentences chosen to be unrelated; a\n"
        "real corpus is messier, because with a few hundred chunks something will\n"
        "always be somewhat close to anything. A score floor is therefore necessary\n"
        "but not sufficient - the prompt itself has to let the model refuse."
    )


def part_4_versus_keywords(store: list[dict], chunks: list[Chunk], embedder: Embedder) -> None:
    rule("PART 4  Semantic search versus keyword search")

    # Phrased to avoid the vocabulary the answer uses, so keyword matching has
    # nothing to grip. This is the case semantic search exists for.
    question = "Why would splitting a document in the wrong place lose information?"

    print(f"Q: {question}\n")

    semantic, _, _ = search_memory_store(store, question, embedder, top_k=3)
    keyword = keyword_search(chunks, question, top_k=3)

    print("SEMANTIC (cosine similarity over embeddings):")
    for rank, (score, chunk) in enumerate(semantic, start=1):
        print(f"   {rank}. {score:.4f}  {chunk.citation():<28} {chunk.preview(52)}")

    print("\nKEYWORD (fraction of question words present):")
    for rank, (score, chunk) in enumerate(keyword, start=1):
        print(f"   {rank}. {score:.4f}  {chunk.citation():<28} {chunk.preview(52)}")

    semantic_ids = {chunk.chunk_id for _, chunk in semantic}
    keyword_ids = {chunk.chunk_id for _, chunk in keyword}
    shared = semantic_ids & keyword_ids

    print(
        f"\nOverlap between the two top-3 lists: {len(shared)} of 3."
        + (f" ({', '.join(sorted(shared))})" if shared else "")
    )

    keyword_scores = {round(score, 4) for score, _ in keyword}
    if len(keyword_scores) == 1:
        print(
            f"\nEvery keyword result scored identically ({keyword_scores.pop():.4f}), which is\n"
            "the giveaway: keyword matching found the same shallow number of word\n"
            "hits in many chunks and had no way to rank between them. The order it\n"
            "returned is arbitrary."
        )

    print(
        "\nKeyword search can only find text that reuses the question's words. Ask\n"
        "about 'splitting in the wrong place' and it has no route to a passage\n"
        "about boundaries and overlap, because the words do not match. Semantic\n"
        "search compares meaning, so it has one.\n"
        "\nBe careful how far you push this result, though. The two methods\n"
        "disagreeing proves they rank differently, not that one ranked better -\n"
        "deciding that means reading the chunks and judging them. Do that on your\n"
        "own notes, where you know what the right answer should be."
    )


def part_5_why_a_database(
    store: list[dict], embed_times: list[float], scan_times: list[float]
) -> None:
    rule("PART 5  What the database will actually buy us")

    if not scan_times:
        return

    average_embed = sum(embed_times) / len(embed_times)
    average_scan = sum(scan_times) / len(scan_times)
    per_comparison = average_scan / len(store)

    print(f"Chunks in store:            {len(store)}")
    print(f"Embedding the question:     {average_embed * 1000:.1f}ms  (fixed - does not grow)")
    print(f"Scanning the whole store:   {average_scan * 1000:.1f}ms  (grows with corpus)")
    print(f"Cost per comparison:        {per_comparison * 1_000_000:.1f}µs")

    embed_share = average_embed / (average_embed + average_scan) * 100
    print(
        f"\nEmbedding the question is {embed_share:.0f}% of the current total. Timing the\n"
        "two together would tell us nothing about scaling, because only the scan\n"
        "grows. Projecting the scan alone:\n"
    )

    print(f"{'corpus size':>14} {'comparisons':>13} {'projected scan':>16}")
    print(f"{'-' * 14} {'-' * 13} {'-' * 16}")
    for multiplier, label in ((1, "now"), (100, "100x"), (10_000, "10,000x")):
        count = len(store) * multiplier
        projected = per_comparison * count
        unit = f"{projected * 1000:.1f}ms" if projected < 1 else f"{projected:.1f}s"
        print(f"{label:>14} {count:>13,} {unit:>16}")

    print(
        "\nAt this size the loop is instant and a database would be pure overhead.\n"
        "The scan is also *exact* - it compares everything, so it cannot miss a\n"
        "match. That matters, because what Chroma provides on Monday is an\n"
        "APPROXIMATE nearest-neighbour index: it deliberately skips most\n"
        "comparisons, trading a small chance of missing a match for search time\n"
        "that barely grows with corpus size.\n"
        "\nSo the database is not more correct than this loop. It is less correct\n"
        "and far faster. Knowing which way that trade runs is the point of having\n"
        "written the loop first."
    )


def part_6_over_to_you() -> None:
    rule("PART 6  The last Week 1 deliverable")

    print(
        "Write 3-4 plain-language sentences on what semantic search means, in\n"
        "notes/week1-learning-log.md. Plain language means a sentence your mentor\n"
        "could read aloud to someone who has never heard the word 'embedding'.\n"
        "\nThe raw material is all now measured:\n"
        "  - Monday: related sentences scored 0.617, unrelated 0.031, with almost\n"
        "    no shared keywords between the related pair\n"
        "  - Part 4 above: a question that keyword search cannot answer, and\n"
        "    semantic search can\n"
        "  - Part 3 above: what it looks like when nothing relevant exists\n"
        "\nThis one is yours to write. It is on your mentor's self-check list, and\n"
        "it is the sentence you will open the demo video with.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Embed all chunks into memory and search them.")
    parser.add_argument("--folder", default="sample-notes", help="Folder of documents (default: sample-notes)")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--question", action="append", help="Ask your own question (repeatable)")
    arguments = parser.parse_args()

    try:
        documents = load_documents(arguments.folder)
    except DocumentLoadError as exc:
        print(f"[error] {exc}")
        return 1

    chunks = chunk_documents(documents, arguments.chunk_size, arguments.overlap)
    if not chunks:
        print("[error] Documents loaded but produced no chunks. Are they all whitespace?")
        return 1

    print(f"[pipeline] {len(documents)} document(s) -> {len(chunks)} chunks "
          f"at size={arguments.chunk_size}, overlap={arguments.overlap}")

    try:
        embedder = Embedder()
        store, embed_seconds = build_memory_store(chunks, embedder)
    except (ImportError, RuntimeError) as exc:
        print(f"\n[setup problem] {exc}")
        return 1

    questions = arguments.question or DEFAULT_QUESTIONS

    part_1_build(store, chunks, embed_seconds, embedder)
    embed_times, scan_times, genuine_scores = part_2_search(
        store, embedder, questions, arguments.top_k
    )
    part_3_no_good_answer(store, embedder, arguments.top_k, genuine_scores)
    part_4_versus_keywords(store, chunks, embedder)
    part_5_why_a_database(store, embed_times, scan_times)
    part_6_over_to_you()

    print(f"\n{'=' * 72}")
    print("Week 1 complete once the write-up is done. Next: Chroma, Week 2 Monday.")
    print(f"{'=' * 72}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
