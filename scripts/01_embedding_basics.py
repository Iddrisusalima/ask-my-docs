"""
Stage 1 - Embeddings: turn text into numbers that can be compared.

Run it:
    python scripts/01_embedding_basics.py

What this script demonstrates, in order:
  1. A sentence becomes a fixed-length list of numbers.
  2. That length does not change with input length.
  3. Sentences about the same topic score high against each other.
  4. Unrelated sentences score noticeably lower.

Point 4 is the whole foundation of semantic search: if "similar meaning" is
reliably a higher number, then "find me the relevant chunk" becomes "find me
the highest number", which a computer is very good at.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Let this script import from src/ when run directly from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.console import enable_utf8_output
from src.embedder import Embedder
from src.similarity import cosine_similarity, similarity_matrix

enable_utf8_output()

# Three sentences that mean roughly the same thing, with deliberately
# different wording. Only one word ("sourdough"/"bread") overlaps at all -
# so any high score here comes from meaning, not shared keywords.
SIMILAR_SENTENCES = [
    "I bake sourdough bread every weekend.",
    "Most Saturdays you will find me making a loaf from scratch.",
    "Weekend baking is my favourite hobby.",
]

# Three sentences with nothing to do with each other or with baking.
UNRELATED_SENTENCES = [
    "The tax filing deadline falls in April.",
    "Saturn has dozens of confirmed moons.",
    "Please reboot the router before calling support.",
]


def rule(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def part_1_single_embedding(embedder: Embedder) -> None:
    rule("PART 1  One sentence -> one vector")

    sentence = "Embeddings turn the meaning of text into numbers."
    vector = embedder.embed(sentence)

    print(f'Sentence: "{sentence}"')
    print(f"Characters in:     {len(sentence)}")
    print(f"Numbers out:       {len(vector)}   <- this is the dimensionality")
    print(f"First 8 numbers:   {[round(v, 4) for v in vector[:8]]}")
    print(f"Vector magnitude:  {np.linalg.norm(vector):.4f}")
    print(
        "\nNone of those individual numbers means anything you could name.\n"
        "Only their position relative to other vectors carries information."
    )


def part_2_length_independence(embedder: Embedder) -> None:
    rule("PART 2  Input length changes nothing about output length")

    samples = [
        "Coffee.",
        "I drink coffee in the morning.",
        "I drink coffee every single morning, usually a flat white, because it "
        "helps me focus for the first few hours of the working day and I have "
        "never managed to build the habit of drinking tea instead.",
    ]

    print(f"{'chars in':>10} | {'numbers out':>12}")
    print(f"{'-' * 10}-+-{'-' * 12}")
    for text in samples:
        vector = embedder.embed(text)
        print(f"{len(text):>10} | {len(vector):>12}")

    print(
        "\nSame budget of numbers for 7 characters and 200+. A long document\n"
        "therefore gets *averaged out* into that same fixed space, blurring the\n"
        "detail. That is precisely why we split documents into chunks before\n"
        "embedding them (coming up Wed-Thu)."
    )


def part_3_compare_groups(embedder: Embedder) -> tuple[float, float]:
    rule("PART 3  Similar sentences vs unrelated sentences")

    print("GROUP A - all about weekend baking:")
    for i, sentence in enumerate(SIMILAR_SENTENCES, start=1):
        print(f"  A{i}. {sentence}")

    print("\nGROUP B - unrelated to each other and to baking:")
    for i, sentence in enumerate(UNRELATED_SENTENCES, start=1):
        print(f"  B{i}. {sentence}")

    # One batched call instead of six separate ones.
    similar_vectors = embedder.embed_batch(SIMILAR_SENTENCES)
    unrelated_vectors = embedder.embed_batch(UNRELATED_SENTENCES)

    print("\n--- Within GROUP A (expect HIGH) ---")
    similar_scores = []
    for i in range(len(similar_vectors)):
        for j in range(i + 1, len(similar_vectors)):
            score = cosine_similarity(similar_vectors[i], similar_vectors[j])
            similar_scores.append(score)
            print(f"  A{i + 1} vs A{j + 1}:  {score:.4f}")

    print("\n--- Within GROUP B (expect LOW) ---")
    unrelated_scores = []
    for i in range(len(unrelated_vectors)):
        for j in range(i + 1, len(unrelated_vectors)):
            score = cosine_similarity(unrelated_vectors[i], unrelated_vectors[j])
            unrelated_scores.append(score)
            print(f"  B{i + 1} vs B{j + 1}:  {score:.4f}")

    avg_similar = float(np.mean(similar_scores))
    avg_unrelated = float(np.mean(unrelated_scores))

    print(f"\nAverage within GROUP A:  {avg_similar:.4f}")
    print(f"Average within GROUP B:  {avg_unrelated:.4f}")
    print(f"Gap:                     {avg_similar - avg_unrelated:.4f}")

    return avg_similar, avg_unrelated


def part_4_full_matrix(embedder: Embedder) -> None:
    rule("PART 4  Everything against everything")

    all_sentences = SIMILAR_SENTENCES + UNRELATED_SENTENCES
    labels = ["A1", "A2", "A3", "B1", "B2", "B3"]
    vectors = embedder.embed_batch(all_sentences)
    matrix = similarity_matrix(vectors)

    header = "     " + "".join(f"{label:>8}" for label in labels)
    print(header)
    for row_index, label in enumerate(labels):
        cells = "".join(f"{matrix[row_index][col]:>8.3f}" for col in range(len(labels)))
        print(f"{label:>5}{cells}")

    print(
        "\nHow to read it: the diagonal is 1.000 (every sentence is identical to\n"
        "itself). The top-left 3x3 block is the A group agreeing with itself.\n"
        "The bottom-left block is A vs B - the lowest numbers on the grid."
    )


def part_5_the_takeaway(avg_similar: float, avg_unrelated: float) -> None:
    rule("PART 5  Why this matters")

    if avg_similar > avg_unrelated:
        print(
            f"Related sentences scored {avg_similar:.3f} on average.\n"
            f"Unrelated ones scored {avg_unrelated:.3f}.\n\n"
            "The model was never told these sentences were about baking. It has\n"
            "no keyword list. It placed them near each other purely from meaning,\n"
            "and that ordering is what the rest of this project stands on:\n\n"
            "  chunk -> embed -> store -> RETRIEVE BY SIMILARITY -> generate\n"
        )
    else:
        print(
            "Unexpected: the unrelated group scored as high as the related one.\n"
            "Worth investigating before moving on - check the model loaded\n"
            "correctly and that the sentences really are distinct topics.\n"
        )

    print(
        "One caveat to remember: these scores are only comparable to each other.\n"
        "0.62 is not universally 'quite similar' - it depends on the model. Judge\n"
        "candidates by their ranking against each other, never by a fixed cutoff."
    )


def main() -> int:
    embedder = Embedder()

    print(f"\nBackend: {embedder.describe()}")

    try:
        part_1_single_embedding(embedder)
        part_2_length_independence(embedder)
        avg_similar, avg_unrelated = part_3_compare_groups(embedder)
        part_4_full_matrix(embedder)
        part_5_the_takeaway(avg_similar, avg_unrelated)
    except (ImportError, RuntimeError) as exc:
        print(f"\n[setup problem] {exc}")
        return 1

    print(f"\n{'=' * 68}")
    print("Done. Next: Wed-Thu, splitting real documents into chunks.")
    print(f"{'=' * 68}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
