"""
Stage 2 - Chunking: build and inspect the chunking pipeline.

Run it:
    python scripts/chunking.py
    python scripts/chunking.py --folder notes
    python scripts/chunking.py --chunk-size 800 --overlap 150

What this script demonstrates, in order:
  1. What a chunk physically is, on a short text you can read in full.
  2. What overlap actually duplicates, shown character by character.
  3. A fact severed by a chunk boundary, and the two mechanisms that rescue it.
  4. The cost and benefit of several size/overlap settings on the real corpus.
  5. The same passage as seen at 300, 500, and 1500 characters.

Part 3 is the one to watch. Everything else is bookkeeping; that one shows the
failure mode that chunk tuning exists to prevent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.chunker import chunk_documents, chunk_spans, chunk_statistics, chunk_text
from src.console import enable_utf8_output
from src.loader import DocumentLoadError, load_documents

# Notes contain arrows, em dashes and curly quotes; a cp1252 console cannot
# print them. Must happen before any output.
enable_utf8_output()

# A short text with clear paragraph structure, used for Parts 1 and 2 so the
# chunks are small enough to read in full.
SHORT_TEXT = (
    "Retrieval-augmented generation has five stages. First the documents are "
    "split into chunks. Then each chunk is embedded.\n\n"
    "The embeddings go into a vector database, which can search them by "
    "similarity rather than by keyword. A question is embedded with the same "
    "model, and the closest chunks come back.\n\n"
    "Those chunks are placed into the prompt as context, and the model answers "
    "from them rather than from its general knowledge."
)

# The fact we will deliberately cut in half in Part 3.
BURIED_FACT = (
    "The overlap between consecutive chunks was set to one hundred characters."
)


def rule(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def part_1_what_a_chunk_is() -> None:
    rule("PART 1  What a chunk physically is")

    size, overlap = 200, 50
    spans = chunk_spans(SHORT_TEXT, chunk_size=size, overlap=overlap)

    print(f"Source text: {len(SHORT_TEXT)} characters")
    print(f"Settings:    chunk_size={size}, overlap={overlap}")
    print(f"Result:      {len(spans)} chunks\n")

    for index, (start, end) in enumerate(spans):
        piece = SHORT_TEXT[start:end]
        print(f"--- chunk {index}  chars {start}-{end}  (len {len(piece)}) ---")
        print(piece.replace("\n", "\\n"))
        print()

    print(
        "Note the chunks are not all exactly 200 characters. The splitter looks\n"
        "backwards a short distance for a paragraph break, then a sentence\n"
        "ending, then any space - so it cuts between ideas where it can, and\n"
        "never mid-word. Ending a chunk halfway through 'embed|dings' would\n"
        "hand the model two fragments neither of which means anything."
    )


def part_2_what_overlap_duplicates() -> None:
    rule("PART 2  What overlap actually duplicates")

    size, overlap = 200, 50
    spans = chunk_spans(SHORT_TEXT, chunk_size=size, overlap=overlap)

    if len(spans) < 2:
        print("Text too short to show overlap.")
        return

    for index in range(len(spans) - 1):
        current_start, current_end = spans[index]
        next_start, _ = spans[index + 1]
        shared = SHORT_TEXT[next_start:current_end]

        print(f"chunk {index} ends at {current_end}, chunk {index + 1} starts at {next_start}")
        print(f"  shared text ({len(shared)} chars): {shared.replace(chr(10), ' ')!r}")

    print(
        "\nThat shared tail is the insurance policy. Any fact shorter than the\n"
        "overlap appears complete in at least one chunk, even if a boundary\n"
        "happens to land in the middle of it."
    )


def part_3_the_boundary_problem() -> None:
    rule("PART 3  A fact severed by a boundary, and how to rescue it")

    # Position the fact so it straddles the 500-character mark.
    filler_before = ("This is background material that pads out the document. " * 9)[:460]
    filler_after = " And the document continues afterwards with more padding text. " * 6
    document = filler_before + BURIED_FACT + filler_after

    fact_start = document.index(BURIED_FACT)
    fact_end = fact_start + len(BURIED_FACT)

    print(f"Document length:  {len(document)} characters")
    print(f"The fact sits at: chars {fact_start}-{fact_end}")
    print(f"Fact:             {BURIED_FACT!r}")
    print(f"\nWith chunk_size=500 the first boundary falls at 500 - inside the fact.\n")

    configurations = [
        ("500 / 0, hard cuts", 500, 0, False),
        ("500 / 0, softened boundaries", 500, 0, True),
        ("500 / 100, softened boundaries", 500, 100, True),
    ]

    print(f"{'configuration':<34} {'chunks':>7} {'fact intact in':>15}")
    print(f"{'-' * 34} {'-' * 7} {'-' * 15}")

    for label, size, overlap, soften in configurations:
        pieces = chunk_text(document, chunk_size=size, overlap=overlap, soften_boundaries=soften)
        intact = sum(1 for piece in pieces if BURIED_FACT in piece)
        verdict = f"{intact} chunk(s)" if intact else "NO CHUNK"
        print(f"{label:<34} {len(pieces):>7} {verdict:>15}")

    print(
        "\nRow 1 is the failure. The fact exists in the document, is split across\n"
        "two chunks, and is therefore in neither one whole. No question can\n"
        "retrieve it, because neither fragment carries the full meaning - and\n"
        "nothing in the system reports a problem. Answers just quietly get worse.\n"
        "\nRow 2 fixes it by accident: the splitter found a sentence break before\n"
        "the fact, so the cut landed in a harmless place. Reliable only when your\n"
        "text happens to have punctuation near every boundary.\n"
        "\nRow 3 fixes it on purpose. Overlap does not depend on the text\n"
        "cooperating."
    )


def part_4_configuration_sweep(folder: str) -> list[dict]:
    rule("PART 4  Cost and benefit across settings, on the real corpus")

    try:
        documents = load_documents(folder)
    except DocumentLoadError as exc:
        print(f"[skipped] {exc}")
        return []

    corpus_characters = sum(len(document.text) for document in documents)
    sources = sorted({document.source for document in documents})

    print(f"\n{len(sources)} file(s), {corpus_characters:,} characters of text:")
    for source in sources:
        source_characters = sum(len(d.text) for d in documents if d.source == source)
        print(f"  {source:<38} {source_characters:>8,} chars")

    configurations = [
        (300, 0),
        (300, 60),
        (500, 0),
        (500, 100),
        (800, 160),
        (1500, 300),
    ]

    print(
        f"\n{'size':>6} {'overlap':>8} {'chunks':>7} {'mean len':>9} "
        f"{'min':>6} {'max':>6} {'stored':>9} {'dup':>6}"
    )
    print(f"{'-' * 6} {'-' * 8} {'-' * 7} {'-' * 9} {'-' * 6} {'-' * 6} {'-' * 9} {'-' * 6}")

    results = []
    for size, overlap in configurations:
        chunks = chunk_documents(documents, chunk_size=size, overlap=overlap)
        stats = chunk_statistics(chunks)
        duplication = stats["total_chars"] / corpus_characters if corpus_characters else 0.0

        print(
            f"{size:>6} {overlap:>8} {stats['count']:>7} {stats['mean']:>9.1f} "
            f"{stats['min']:>6} {stats['max']:>6} {stats['total_chars']:>9,} {duplication:>5.2f}x"
        )

        results.append(
            {
                "chunk_size": size,
                "overlap": overlap,
                "chunks": stats["count"],
                "mean": stats["mean"],
                "min": stats["min"],
                "max": stats["max"],
                "stored": stats["total_chars"],
                "duplication": duplication,
            }
        )

    print(
        "\n'stored' is how many characters end up in the database; 'dup' is that\n"
        "divided by the real corpus size. 1.25x means a quarter of what you store\n"
        "and embed is a second copy of text you already have."
    )

    return results


def part_5_same_passage_three_ways(folder: str) -> None:
    rule("PART 5  The same passage at three chunk sizes")

    try:
        documents = load_documents(folder, verbose=False)
    except DocumentLoadError as exc:
        print(f"[skipped] {exc}")
        return

    # Use the longest document so all three sizes have room to differ.
    document = max(documents, key=lambda d: len(d.text))
    print(f"Source: {document.describe()}  ({len(document.text):,} chars)\n")

    for size in (300, 500, 1500):
        chunks = chunk_documents([document], chunk_size=size, overlap=size // 5)
        if not chunks:
            continue

        # Show a chunk from the middle, where content is more representative
        # than a title block at the top of the file.
        sample = chunks[len(chunks) // 2]
        body = " ".join(sample.text.split())

        print(f"--- chunk_size={size}, overlap={size // 5} -> {len(chunks)} chunks ---")
        print(f"    id: {sample.citation()}   starts at char {sample.start_char}")
        print(f"    {body[:size] if len(body) <= size else body[: size - 3] + '...'}")
        print()

    print(
        "Small chunks are sharply about one thing, which makes a match precise -\n"
        "but the answer may need context the chunk no longer contains. Large\n"
        "chunks carry their context along, and dilute the match: one sentence of\n"
        "relevance averaged in with a paragraph of unrelated material.\n"
        "\nThis is the tradeoff to name when asked why chunk size matters. There is\n"
        "no universally correct value - it depends on how your notes are written."
    )


def part_6_over_to_you(results: list[dict]) -> None:
    rule("PART 6  What to write up, and what to decide")

    if results:
        baseline = next((r for r in results if r["chunk_size"] == 500 and r["overlap"] == 100), None)
        if baseline:
            print(
                f"At 500/100 this corpus produces {baseline['chunks']} chunks, "
                f"mean length {baseline['mean']:.0f}, storing "
                f"{baseline['duplication']:.2f}x the original text.\n"
            )

    print(
        "Still to do before Friday:\n"
        "  1. Put 5-10 of your own notes in sample-notes/ and re-run this. The\n"
        "     numbers above describe whatever folder you pointed at, and the\n"
        "     README has to describe the dataset you actually ship.\n"
        "  2. Write, in your own words, why splitting matters. Parts 3 and 5 give\n"
        "     you the two arguments - a fact lost at a boundary, and the\n"
        "     precision-versus-context tradeoff. Your mentor's self-check asks\n"
        "     you to explain this out loud.\n"
        "  3. Pick CHUNK_SIZE and CHUNK_OVERLAP and record why. You need an\n"
        "     answer to 'why 500 and not 1000?' that cites the table above.\n"
        "     Nothing is final until retrieval tests it against real\n"
        "     questions.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the chunking pipeline.")
    parser.add_argument(
        "--folder",
        default="sample-notes",
        help="Folder of documents to chunk (default: sample-notes)",
    )
    parser.add_argument("--chunk-size", type=int, default=None, help="Show one configuration only")
    parser.add_argument("--overlap", type=int, default=None, help="Overlap for --chunk-size")
    arguments = parser.parse_args()

    # Single-configuration mode, for quick one-off checks.
    if arguments.chunk_size is not None:
        overlap = arguments.overlap if arguments.overlap is not None else arguments.chunk_size // 5
        try:
            documents = load_documents(arguments.folder)
        except DocumentLoadError as exc:
            print(f"[error] {exc}")
            return 1

        chunks = chunk_documents(documents, chunk_size=arguments.chunk_size, overlap=overlap)
        stats = chunk_statistics(chunks)
        print(
            f"\nchunk_size={arguments.chunk_size}, overlap={overlap} -> "
            f"{stats['count']} chunks, mean {stats['mean']:.1f} chars "
            f"(min {stats['min']}, max {stats['max']})\n"
        )
        for chunk in chunks[:5]:
            print(f"  {chunk.citation():<28} {chunk.preview()}")
        if len(chunks) > 5:
            print(f"  ... and {len(chunks) - 5} more")
        return 0

    part_1_what_a_chunk_is()
    part_2_what_overlap_duplicates()
    part_3_the_boundary_problem()
    results = part_4_configuration_sweep(arguments.folder)
    part_5_same_passage_three_ways(arguments.folder)
    part_6_over_to_you(results)

    print(f"\n{'=' * 72}")
    print("Done. Next: Friday, embed every chunk and search them by hand.")
    print(f"{'=' * 72}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
