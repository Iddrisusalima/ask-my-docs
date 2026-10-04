"""
Week 3: The full pipeline. A question in, a cited answer out.

Run it:
    python scripts/06_ask.py --question "why does overlap matter?"
    python scripts/06_ask.py --question "..." --show-prompt
    python scripts/06_ask.py                      (interactive)

Requires an index. Build one first:
    python scripts/04_ingest.py --folder sample-notes

`--show-prompt` prints the exact text that would be sent to the model and stops,
without calling any API. Two reasons that mode exists:

  1. It demonstrates the grounding step rather than asserting it. "The model only
     sees my notes" is a claim; the printed prompt is evidence.
  2. It works with no API key, so the stage can be inspected and explained
     before any provider is chosen.

The pipeline runs in four visible steps, deliberately kept separate so each can
be shown on its own:

    question -> embed -> retrieve -> assemble prompt -> answer + citations
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.console import enable_utf8_output
from src.embedder import Embedder
from src.generator import SYSTEM_PROMPT, build_prompt, generate_answer
from src.retrieval_log import RetrievalLog
from src.retriever import Retriever
from src.store import VectorStore, VectorStoreError

enable_utf8_output()


def rule(title: str) -> None:
    print(f"\n{'=' * 74}\n{title}\n{'=' * 74}")


def show_sources(answer) -> None:
    """Print the passages behind an answer, marking the ones it actually cited."""
    cited = set(answer.cited_numbers())

    print("\nSOURCES")
    for number, chunk in answer.citations():
        mark = "cited" if number in cited else "  -  "
        print(f"  [{number}] {mark}  {chunk.score:.4f}  {chunk.chunk.citation()}")

    if not cited:
        print(
            "\n  The model cited nothing. Either it could not answer from these\n"
            "  passages, or it ignored the instruction to cite. Check the answer\n"
            "  text above before trusting it."
        )
    elif len(cited) < len(answer.used_chunks):
        unused = len(answer.used_chunks) - len(cited)
        print(
            f"\n  {unused} of {len(answer.used_chunks)} passages went unused. If that keeps\n"
            "  happening, top-k is higher than it needs to be."
        )

    if answer.omitted:
        print(f"\n  {answer.omitted} retrieved passage(s) did not fit the character budget.")


def answer_one(
    question: str,
    retriever: Retriever,
    top_k: int,
    min_score: float | None,
    show_prompt: bool,
    log: RetrievalLog | None,
    configuration: dict,
) -> int:
    # --- step 1 and 2: embed the question, retrieve the nearest passages ----
    try:
        results = retriever.retrieve(question, top_k=top_k, min_score=min_score)
    except VectorStoreError as exc:
        print(f"[error] {exc}")
        return 1

    if log is not None:
        log.write(question, results, configuration)

    print(f"\nQ: {question}")
    print(f"   retrieved {len(results)} passage(s)")
    for rank, result in enumerate(results, start=1):
        print(f"   {rank}. {result.describe(58)}")

    if not results:
        # Nothing cleared the floor. Answering anyway would mean inventing, so
        # the pipeline stops here rather than handing the model empty context.
        print(
            f"\nA: Nothing in your notes scored at or above the {min_score} floor, so there is\n"
            "   no relevant passage to answer from."
        )
        return 0

    # --- step 3: assemble the prompt ---------------------------------------
    prompt, used, omitted = build_prompt(question, results)

    if show_prompt:
        rule("SYSTEM PROMPT  (the instruction that keeps answers grounded)")
        print(SYSTEM_PROMPT)
        rule("USER PROMPT  (exactly what the model would receive)")
        print(prompt)
        print(
            f"\n{'-' * 74}\n"
            f"{len(used)} passage(s) included, {omitted} omitted, "
            f"{len(prompt):,} characters.\n"
            "Nothing was sent anywhere. Drop --show-prompt to get a real answer."
        )
        return 0

    # --- step 4: generate ---------------------------------------------------
    try:
        answer = generate_answer(question, results)
    except (ImportError, RuntimeError) as exc:
        print(f"\n[generation unavailable] {exc}")
        return 1

    rule("ANSWER")
    print(answer.text)
    show_sources(answer)
    print(f"\n  model: {answer.model}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask a question about your notes.")
    parser.add_argument("--question", action="append", help="Question to ask (repeatable)")
    parser.add_argument("--db", default="chroma_db")
    parser.add_argument("--collection", default="notes")
    parser.add_argument("--top-k", type=int, default=None, help="Overrides TOP_K in .env")
    parser.add_argument("--min-score", type=float, default=None, help="Overrides MIN_SCORE in .env")
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Print the prompt and stop, without calling any model",
    )
    parser.add_argument("--no-log", action="store_true", help="Skip logs/retrieval.log")
    arguments = parser.parse_args()

    top_k = config.top_k(arguments.top_k)
    min_score = config.min_score(arguments.min_score)

    store = VectorStore(path=arguments.db, collection=arguments.collection)

    try:
        embedder = Embedder()
        retriever = Retriever(store, embedder)
    except (ImportError, RuntimeError) as exc:
        print(f"[setup problem] {exc}")
        return 1

    indexed = store.count()
    if indexed == 0:
        print(
            "[error] No chunks are indexed yet.\n"
            "Run ingestion first:\n"
            "  python scripts/04_ingest.py --folder sample-notes"
        )
        return 1

    print(f"[ask] {indexed} chunks · top_k={top_k} · min_score={min_score} · {embedder.describe()}")

    log = None if arguments.no_log else RetrievalLog()
    configuration = {
        "model": embedder.describe(),
        "top_k": top_k,
        "min_score": min_score,
        "collection": arguments.collection,
        "chunks_indexed": indexed,
    }

    if arguments.question:
        status = 0
        for question in arguments.question:
            status |= answer_one(
                question, retriever, top_k, min_score, arguments.show_prompt, log, configuration
            )
        return status

    # Interactive mode, for the demo video.
    print("\nAsk a question, or press Enter on an empty line to quit.")
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            break

        answer_one(
            question, retriever, top_k, min_score, arguments.show_prompt, log, configuration
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
