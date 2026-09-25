"""
Week 2, Wed-Thu: Retrieval, and choosing top-k by measuring rather than guessing.

Run it:
    python scripts/05_retrieve.py
    python scripts/05_retrieve.py --question "why does overlap matter?"
    python scripts/05_retrieve.py --top-k 10 --min-score 0.35

Requires an index. Build one first:
    python scripts/04_ingest.py --folder sample-notes

The brief asks two things of this stage: check by hand whether retrieved chunks
are actually relevant, and tune top-k while observing the tradeoff between more
context and more noise. Part 2 makes that tradeoff numeric, because "more noise"
is easy to say and hard to defend without a measurement.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.console import enable_utf8_output
from src.embedder import Embedder
from src.retrieval_log import RetrievalLog
from src.retriever import RetrievedChunk, Retriever, score_summary
from src.store import VectorStore, VectorStoreError

enable_utf8_output()

# Questions phrased the way a person actually asks them, deliberately avoiding
# the vocabulary of their own answers so retrieval has to work on meaning.
TEST_QUESTIONS = [
    "Why does overlap between chunks matter?",
    "How should I decide how many results to fetch?",
    "What stops the model inventing an answer?",
    "What happens when my notes do not cover the question?",
]

# No answer to this exists in a corpus of study notes.
UNANSWERABLE = "What time does the corner shop close on Sundays?"

TOP_K_VALUES = (3, 5, 10)


def rule(title: str) -> None:
    print(f"\n{'=' * 74}\n{title}\n{'=' * 74}")


def context_characters(results: list[RetrievedChunk]) -> int:
    """How much text these chunks would contribute to a prompt."""
    return sum(len(result.chunk.text) for result in results)


def adjacent_pairs(results: list[RetrievedChunk]) -> list[tuple[str, str]]:
    """Find results that are neighbouring chunks of the same document.

    Consecutive chunks share `overlap` characters by construction, so when both
    come back for one question a chunk of the returned context is duplicated.
    That wastes a top-k slot and pads the prompt with text the model has already
    seen.
    """
    pairs = []
    for i, first in enumerate(results):
        for second in results[i + 1 :]:
            if (
                first.chunk.source == second.chunk.source
                and abs(first.chunk.chunk_index - second.chunk.chunk_index) == 1
            ):
                pairs.append((first.chunk.chunk_id, second.chunk.chunk_id))
    return pairs


def part_1_inspect(
    retriever: Retriever,
    questions: list[str],
    top_k: int,
    log: RetrievalLog | None = None,
    configuration: dict | None = None,
) -> None:
    rule(f"PART 1  Retrieved chunks at top_k={top_k} — judge these by hand")

    for question in questions:
        results = retriever.retrieve(question, top_k=top_k)
        summary = score_summary(results)

        if log is not None:
            log.write(question, results, configuration)

        print(f"\nQ: {question}")
        print(
            f"   best {summary['best']:.4f} · worst {summary['worst']:.4f} · "
            f"spread {summary['spread']:.4f} · {context_characters(results):,} chars of context"
        )

        for rank, result in enumerate(results, start=1):
            print(f"   {rank}. {result.describe()}")

        duplicates = adjacent_pairs(results)
        if duplicates:
            joined = ", ".join(f"{a}+{b}" for a, b in duplicates)
            print(f"   ! neighbouring chunks both returned: {joined}")

    print(
        "\nRead the previews above and ask whether each one could actually answer the\n"
        "question. That judgement cannot be automated, and it is the only real test\n"
        "of whether chunk size and top-k are set sensibly."
    )


def part_2_top_k_tradeoff(retriever: Retriever, questions: list[str]) -> list[dict]:
    rule("PART 2  The top-k tradeoff, measured")

    print(
        "For each k: how good is the average chunk, how weak is the last one added,\n"
        "and how much text does it all cost?\n"
    )
    print(
        f"{'k':>3} {'mean score':>11} {'worst':>8} {'marginal':>9} "
        f"{'context chars':>14} {'sources':>8} {'dup pairs':>10}"
    )
    print(f"{'-' * 3} {'-' * 11} {'-' * 8} {'-' * 9} {'-' * 14} {'-' * 8} {'-' * 10}")

    rows = []
    for top_k in TOP_K_VALUES:
        means = []
        worsts = []
        characters = []
        source_counts = []
        duplicate_counts = []

        for question in questions:
            results = retriever.retrieve(question, top_k=top_k)
            summary = score_summary(results)
            means.append(summary["mean"])
            worsts.append(summary["worst"])
            characters.append(context_characters(results))
            source_counts.append(len({result.chunk.source for result in results}))
            duplicate_counts.append(len(adjacent_pairs(results)))

        row = {
            "top_k": top_k,
            "mean": sum(means) / len(means),
            "worst": sum(worsts) / len(worsts),
            "chars": sum(characters) / len(characters),
            "sources": sum(source_counts) / len(source_counts),
            "duplicates": sum(duplicate_counts) / len(duplicate_counts),
        }
        rows.append(row)

        # "Marginal" is the drop in mean score caused by widening k - the price
        # paid in average quality for the extra context.
        marginal = row["mean"] - rows[0]["mean"] if rows else 0.0

        print(
            f"{top_k:>3} {row['mean']:>11.4f} {row['worst']:>8.4f} {marginal:>+9.4f} "
            f"{row['chars']:>14,.0f} {row['sources']:>8.1f} {row['duplicates']:>10.1f}"
        )

    print(
        "\nReading the table:\n"
        "  mean score    — average quality of what gets sent to the model\n"
        "  worst         — the weakest chunk included, i.e. the noise floor\n"
        "  marginal      — how far mean quality fell relative to k=3\n"
        "  context chars — prompt cost, and Week 3's character budget\n"
        "  dup pairs     — neighbouring chunks both returned, so overlapping text sent twice"
    )

    return rows


def part_3_what_the_tail_looks_like(retriever: Retriever, question: str) -> None:
    rule("PART 3  What the extra chunks at k=10 actually contain")

    results = retriever.retrieve(question, top_k=10)
    print(f"Q: {question}\n")

    for rank, result in enumerate(results, start=1):
        tag = "kept at k=3" if rank <= 3 else ("added by k=5" if rank <= 5 else "added by k=10")
        print(f"   {rank:>2}. [{tag:<13}] {result.describe(56)}")

    if len(results) >= 10:
        top_three = sum(result.score for result in results[:3]) / 3
        last_five = sum(result.score for result in results[5:]) / 5
        print(
            f"\n   mean of top 3:        {top_three:.4f}"
            f"\n   mean of ranks 6-10:   {last_five:.4f}"
            f"\n   quality drop:         {top_three - last_five:.4f}"
        )

    print(
        "\nThis is what 'more context, more noise' means concretely. The tail chunks\n"
        "are not random - they are loosely on topic, which is exactly what makes them\n"
        "a problem. Obvious rubbish would be harmless; plausible-but-irrelevant text\n"
        "is what pulls a model's attention away from the passage that actually answers\n"
        "the question."
    )


def part_4_the_floor(retriever: Retriever, questions: list[str], top_k: int) -> None:
    rule("PART 4  The relevance floor, swept across every question")

    bad = retriever.retrieve(UNANSWERABLE, top_k=top_k)

    print(f"Unanswerable control: {UNANSWERABLE}")
    print(f"  best {bad[0].score:.4f}, worst {bad[-1].score:.4f}")
    for result in bad[:3]:
        print(f"    {result.describe(50)}")

    print(
        "\nHow many chunks survive each floor. Testing only the strongest question would\n"
        "make a threshold look far safer than it is, so all of them are swept:\n"
    )

    floors = (None, 0.25, 0.30, 0.35, 0.40, 0.45)
    labels = [f"Q{index + 1}" for index in range(len(questions))]

    header = f"{'floor':>7} " + "".join(f"{label:>5}" for label in labels) + f" {'UNANSWERABLE':>14}"
    print(header)
    print(f"{'-' * 7} " + "".join("-" * 5 for _ in labels) + f" {'-' * 14}")

    for floor in floors:
        kept = [len(retriever.retrieve(question, top_k=top_k, min_score=floor)) for question in questions]
        kept_bad = len(retriever.retrieve(UNANSWERABLE, top_k=top_k, min_score=floor))
        label = "off" if floor is None else f"{floor:.2f}"
        print(f"{label:>7} " + "".join(f"{count:>5}" for count in kept) + f" {kept_bad:>14}")

    for index, question in enumerate(questions, start=1):
        print(f"  Q{index}: {question}")

    print(
        "\nThe conflict is visible in the columns. The floor needed to silence the\n"
        "unanswerable control also strips most or all of the context from the weaker\n"
        "legitimate questions - the ones asking about topics the notes cover only\n"
        "briefly. A single global threshold cannot serve both.\n"
        "\nWhy that happens: these scores are not calibrated across questions. A question\n"
        "whose wording closely matches how the notes are written scores high throughout;\n"
        "one phrased differently scores low throughout, even when its top hit is exactly\n"
        "right. So an absolute cutoff is comparing numbers that were never on a common\n"
        "scale - the same mistake Week 1 Monday warned about, resurfacing.\n"
        "\nSo min_score defaults to off. A wrong floor silently discards correct answers,\n"
        "which is worse than passing marginal context to a model that has been told it\n"
        "may refuse. Week 3 leans on the prompt as the primary defence, with the floor\n"
        "as a backstop. A relative test - such as requiring the best hit to stand clear\n"
        "of the rest - would likely work better than an absolute one, and is worth\n"
        "trying if time allows."
    )


def part_5_decide(rows: list[dict]) -> None:
    rule("PART 5  Choosing top-k")

    if not rows:
        return

    by_k = {row["top_k"]: row for row in rows}
    three, five, ten = by_k.get(3), by_k.get(5), by_k.get(10)

    if three and five and ten:
        print(
            f"k=3  → mean {three['mean']:.4f}, {three['chars']:,.0f} chars\n"
            f"k=5  → mean {five['mean']:.4f} ({five['mean'] - three['mean']:+.4f}), "
            f"{five['chars']:,.0f} chars ({five['chars'] / three['chars']:.1f}x)\n"
            f"k=10 → mean {ten['mean']:.4f} ({ten['mean'] - three['mean']:+.4f}), "
            f"{ten['chars']:,.0f} chars ({ten['chars'] / three['chars']:.1f}x)\n"
        )

    print(
        "Still to do:\n"
        "  1. Read the Part 1 previews and judge relevance yourself. The scores say\n"
        "     chunks are close in meaning; only you can say whether they answer the\n"
        "     question.\n"
        "  2. Set TOP_K in .env and record the reasoning in notes/week2-learning-log.md,\n"
        "     citing the Part 2 table. 'Why 5 and not 10?' needs a real answer.\n"
        "  3. Re-run all of this against your own notes. These numbers describe an\n"
        "     interim corpus.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieve chunks for questions and tune top-k.")
    parser.add_argument("--db", default="chroma_db")
    parser.add_argument("--collection", default="notes")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=None)
    parser.add_argument("--question", action="append", help="Ask your own (repeatable)")
    parser.add_argument("--no-log", action="store_true", help="Skip writing to logs/retrieval.log")
    arguments = parser.parse_args()

    store = VectorStore(path=arguments.db, collection=arguments.collection)

    try:
        embedder = Embedder()
        retriever = Retriever(store, embedder)
    except (ImportError, RuntimeError) as exc:
        print(f"[setup problem] {exc}")
        return 1

    questions = arguments.question or TEST_QUESTIONS
    log = None if arguments.no_log else RetrievalLog()

    configuration = {
        "model": embedder.describe(),
        "top_k": arguments.top_k,
        "min_score": arguments.min_score,
        "collection": arguments.collection,
        "chunks_indexed": store.count(),
    }

    try:
        print(f"[retriever] collection '{arguments.collection}' · {store.count()} chunks "
              f"· model {embedder.describe()}")

        # One-off mode: a single question, no sweeps.
        if arguments.question:
            for question in questions:
                results = retriever.retrieve(
                    question, top_k=arguments.top_k, min_score=arguments.min_score
                )
                if log is not None:
                    log.write(question, results, configuration)

                print(f"\nQ: {question}")
                if not results:
                    floor = arguments.min_score
                    print(f"   Nothing scored at or above the {floor} floor — "
                          "no relevant passage found in your notes.")
                    continue
                for rank, result in enumerate(results, start=1):
                    print(f"   {rank}. {result.describe()}")

            if log is not None:
                print(f"\n[log] appended to {log.path} ({log.entry_count()} entries total)")
            return 0

        part_1_inspect(retriever, questions, arguments.top_k, log, configuration)
        rows = part_2_top_k_tradeoff(retriever, questions)
        part_3_what_the_tail_looks_like(retriever, questions[0])
        part_4_the_floor(retriever, questions, arguments.top_k)
        part_5_decide(rows)

    except VectorStoreError as exc:
        print(f"\n[error] {exc}")
        return 1
    except ValueError as exc:
        print(f"\n[error] {exc}")
        return 1

    rule("Done")
    if log is not None:
        print(f"Retrieval results appended to {log.path} ({log.entry_count()} entries total).")
        print("That directory is gitignored - it is review material, not a deliverable.")
    print("Next: Week 3, feeding retrieved chunks to a model and citing them.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
