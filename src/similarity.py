"""
Cosine similarity, written by hand.

We could import this from a library, but the whole point of Week 1 is
understanding *why* two pieces of text score as "similar". So we do the
arithmetic ourselves.

The idea
--------
An embedding is a list of numbers describing a point in space. Two texts that
mean similar things land close together, pointing in roughly the same
direction from the origin.

Cosine similarity measures the angle between two of those arrows and ignores
how long they are. That matters: a long document and a short sentence can mean
the same thing, and we don't want length to drown out meaning.

    cos(a, b) = (a . b) / (|a| * |b|)

Reading the score:
     1.0  -> same direction (as close to "same meaning" as this tool gets)
     0.0  -> perpendicular, unrelated
    -1.0  -> opposite directions

In practice, with modern embedding models, scores cluster in a narrow band.
Unrelated English sentences often still score ~0.0-0.2 rather than a clean 0,
because they share grammar and general "English-ness". So judge scores
*relative to each other*, not against an absolute threshold.
"""

from __future__ import annotations

import numpy as np


def cosine_similarity(a, b) -> float:
    """Return the cosine similarity between two equal-length vectors.

    Args:
        a: First embedding (any sequence of numbers).
        b: Second embedding, same length as `a`.

    Returns:
        A float, normally in [-1.0, 1.0].

    Raises:
        ValueError: If lengths differ, or if either vector is all zeros
            (a zero vector has no direction, so the angle is undefined).
    """
    vec_a = np.asarray(a, dtype=np.float64)
    vec_b = np.asarray(b, dtype=np.float64)

    if vec_a.shape != vec_b.shape:
        raise ValueError(
            f"Vectors must be the same length to compare: "
            f"got {vec_a.shape} and {vec_b.shape}. "
            "This usually means they came from two different embedding models."
        )

    # Step 1: the dot product. Large and positive when the two vectors agree
    # dimension by dimension.
    dot_product = float(np.dot(vec_a, vec_b))

    # Step 2: each vector's length (magnitude / Euclidean norm).
    magnitude_a = float(np.sqrt(np.sum(vec_a**2)))
    magnitude_b = float(np.sqrt(np.sum(vec_b**2)))

    if magnitude_a == 0.0 or magnitude_b == 0.0:
        raise ValueError(
            "Cannot compute cosine similarity against a zero vector - "
            "it has no direction. Check that the text you embedded was not empty."
        )

    # Step 3: dividing by both lengths cancels out magnitude, leaving only
    # the angle. This is what makes the score length-independent.
    return dot_product / (magnitude_a * magnitude_b)


def similarity_matrix(vectors) -> np.ndarray:
    """Compare every vector against every other vector.

    Handy for eyeballing which texts in a set cluster together.

    Args:
        vectors: A sequence of embeddings, all the same length.

    Returns:
        An (n x n) array where cell [i][j] is the similarity of
        vectors[i] to vectors[j]. The diagonal is always 1.0.
    """
    count = len(vectors)
    matrix = np.zeros((count, count), dtype=np.float64)

    for i in range(count):
        for j in range(count):
            matrix[i][j] = cosine_similarity(vectors[i], vectors[j])

    return matrix
