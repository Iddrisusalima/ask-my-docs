"""
Splitting documents into overlapping fixed-size chunks.

Why split at all?
-----------------
Two independent reasons, and they pull in the same direction:

1. **Fixed-size embeddings.** The embedding demo showed that a 7-character input and
   a 200-character input both come back as 384 numbers. Feed in a whole
   10,000-character document and it still gets 384 numbers. Everything it
   discusses is averaged into one position, so a document about five topics
   lands in the bland middle of all five and matches none of them sharply.
   Smaller chunks each get their own 384 numbers, so each keeps its own meaning.

2. **Relevance precision.** The point of retrieval is to hand the language model
   the passage that answers the question, not the file that contains it. A
   whole-document match means stuffing 10,000 characters into the prompt, most
   of it irrelevant - which costs money, burns context, and measurably degrades
   the answer as the model's attention spreads across noise.

Why overlap?
------------
A fixed cut every N characters has no idea what it is cutting. Put the boundary
mid-sentence and a fact can end up half in one chunk and half in the next,
retrievable through neither - each fragment is incomplete enough that neither
scores well. Overlap means the tail of one chunk is repeated at the head of the
next, so any fact shorter than the overlap survives intact somewhere.

The cost is duplication: 500-character chunks with 100 of overlap store roughly
25% more text and can return two near-identical chunks for one query, wasting a
slot in your top-k.

Why characters rather than tokens?
----------------------------------
Characters are directly observable - you can look at a 500-character chunk and
see exactly what it holds. Token counts need a tokenizer and make the link
between "chunk size" and "what I see on screen" indirect. Token-based chunking
is the better production choice, because context limits are denominated in
tokens; character-based is the better choice for learning. Rough conversion for
English: one token is about four characters.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.loader import LoadedDocument

# How far back from the ideal cut point we are willing to search for a natural
# boundary, as a fraction of chunk size. At 0.25 a 500-character chunk will look
# back up to 125 characters for a paragraph or sentence break. Larger values
# give tidier chunks but more variable sizes.
BOUNDARY_LOOKBACK_FRACTION = 0.25

# Tried in order. Each entry is the string to search for and how many of its
# characters belong to the chunk that ends there.
PARAGRAPH_BREAKS = ("\n\n", "\r\n\r\n")
SENTENCE_BREAKS = (". ", "! ", "? ", ".\n", "!\n", "?\n", '." ', ".) ")


@dataclass(frozen=True)
class Chunk:
    """One retrievable passage, carrying everything needed to cite it.

    Attributes:
        chunk_id: Readable identifier, e.g. "notes.md#3". Deliberately not
            a UUID - this string is shown to the user in citations, and a human
            watching a demo should be able to tell where it came from.
        text: The passage itself.
        source: Filename it came from.
        chunk_index: 0-based position within its source file.
        start_char: Character offset within the source document, useful for
            locating the passage in the original.
        page: First PDF page this passage came from, or None.
        page_end: Last PDF page, when short pages were merged into one chunk.
            None when the chunk sits on a single page.
        row: CSV row number, or None.
    """

    chunk_id: str
    text: str
    source: str
    chunk_index: int
    start_char: int
    page: int | None = None
    page_end: int | None = None
    row: int | None = None

    def citation(self) -> str:
        """How this chunk is referred to in an answer's sources list.

        The suffix names whichever landmark the source format provided, so a
        reader can find the passage in the original file:

            notes.md#3                 markdown or .docx - chunk number only
            guide.pdf#7 (p.4)          one PDF page
            slides.pdf#2 (pp.3-5)      several short PDF pages, merged
            settings.csv#0 (r.12)      one CSV row
        """
        if self.page is not None:
            if self.page_end is not None and self.page_end != self.page:
                return f"{self.chunk_id} (pp.{self.page}-{self.page_end})"
            return f"{self.chunk_id} (p.{self.page})"

        if self.row is not None:
            return f"{self.chunk_id} (r.{self.row})"

        return self.chunk_id

    def preview(self, width: int = 80) -> str:
        """Single-line excerpt for logs and terminal output."""
        collapsed = " ".join(self.text.split())
        if len(collapsed) <= width:
            return collapsed
        return collapsed[: width - 3] + "..."


def chunk_spans(
    text: str,
    chunk_size: int,
    overlap: int,
    soften_boundaries: bool = True,
) -> list[tuple[int, int]]:
    """Work out where each chunk starts and ends.

    Offsets are computed separately from the text itself so that `Chunk` can
    record `start_char` without re-deriving it by searching for substrings -
    which would break the moment a passage appears twice in one document.

    Args:
        text: Document text.
        chunk_size: Maximum characters per chunk.
        overlap: Characters of the previous chunk repeated at the start of the
            next one.
        soften_boundaries: Nudge cuts back to a paragraph, sentence, or word
            boundary where one is available nearby.

    Returns:
        (start, end) pairs, in order. Never empty for non-empty input.

    Raises:
        ValueError: If chunk_size is not positive, overlap is negative, or
            overlap is greater than or equal to chunk_size.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}.")

    if overlap < 0:
        raise ValueError(f"overlap cannot be negative, got {overlap}.")

    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be smaller than chunk_size ({chunk_size}). "
            "With overlap greater than or equal to chunk size, each chunk would start "
            "at or before the previous one and the loop would never reach the end of "
            "the document."
        )

    if not text:
        return []

    length = len(text)
    lookback = int(chunk_size * BOUNDARY_LOOKBACK_FRACTION)
    spans: list[tuple[int, int]] = []
    start = 0

    while start < length:
        hard_end = min(start + chunk_size, length)

        # The final chunk always ends at the end of the document - there is
        # nothing after it to tidy the boundary for.
        if soften_boundaries and hard_end < length:
            end = _soften(text, start, hard_end, overlap, lookback)
        else:
            end = hard_end

        spans.append((start, end))

        if end >= length:
            break

        # Step back by the overlap. `_soften` guarantees end > start + overlap,
        # so this always advances and the loop always terminates.
        start = end - overlap

    return spans


def _soften(text: str, start: int, hard_end: int, overlap: int, lookback: int) -> int:
    """Find a natural cut point at or just before `hard_end`.

    Searches backwards for a paragraph break, then a sentence ending, then any
    whitespace, and gives up on `hard_end` if none is close enough.

    The search floor guarantees the returned end leaves room to advance past the
    overlap, so callers cannot be sent into an infinite loop by a document with
    no whitespace in it.
    """
    # Two constraints on how far back we may cut:
    #   - not so far that the chunk fails to clear the overlap (else no progress)
    #   - not further back than the lookback window allows
    span = hard_end - start
    earliest_useful = overlap + 1
    earliest_allowed = span - lookback
    floor = min(start + max(earliest_useful, earliest_allowed), hard_end)

    if floor >= hard_end:
        return hard_end

    # 1. Paragraph break: the cleanest possible boundary, since a blank line
    #    almost always separates two distinct ideas.
    for marker in PARAGRAPH_BREAKS:
        found = text.rfind(marker, floor, hard_end)
        if found != -1 and found + len(marker) <= hard_end:
            return found + len(marker)

    # 2. Sentence ending. Keeps the full stop with the sentence it belongs to.
    best = -1
    for marker in SENTENCE_BREAKS:
        found = text.rfind(marker, floor, hard_end)
        if found != -1 and found + len(marker) <= hard_end:
            best = max(best, found + len(marker))
    if best != -1:
        return best

    # 3. Any whitespace - avoids splitting a word in half, which would leave two
    #    fragments the embedding model has to guess at.
    found = text.rfind(" ", floor, hard_end)
    if found != -1:
        return found + 1

    # 4. No natural boundary within reach: cut where we intended to.
    return hard_end


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
    soften_boundaries: bool = True,
) -> list[str]:
    """Split a string into overlapping chunks.

    The simple entry point, used by the demo script to show what different
    settings produce. `chunk_documents` is what the pipeline actually calls.

    Args:
        text: Text to split.
        chunk_size: Maximum characters per chunk.
        overlap: Characters repeated between consecutive chunks.
        soften_boundaries: Prefer paragraph, sentence, or word boundaries.

    Returns:
        Chunks in document order. Whitespace-only chunks are dropped.
    """
    spans = chunk_spans(text, chunk_size, overlap, soften_boundaries)
    pieces = [text[start:end] for start, end in spans]
    return [piece for piece in pieces if piece.strip()]


def merge_short_pages(
    documents: list[LoadedDocument],
    chunk_size: int,
) -> tuple[list[LoadedDocument], list[tuple[int, int]]]:
    """Join consecutive short PDF pages from the same file into one unit.

    Why this exists
    ---------------
    The loader splits a PDF into one document per page so that citations can
    name a page. That is the right trade for citations and the wrong one for
    chunk size, because documents are chunked independently and therefore can
    never merge. A slide deck averaging 223 characters per page produces
    223-character chunks however large `chunk_size` is set - measured on a real
    31-page lecture deck, 38% of chunks came out under 200 characters with the
    smallest at 47.

    That matters because a chunk holding one slide title embeds as a position
    describing almost nothing. It is too small to answer a question and it
    occupies a slot in the top-k that a fuller passage could have used.

    Merging consecutive pages up to `chunk_size` restores the size the setting
    was tuned for, and the citation becomes a page *range* rather than a single
    page, which is still something a reader can act on.

    Only PDFs are affected. Markdown, .docx and CSV rows have no page numbers,
    so they pass through untouched - and CSV rows must never be merged, since
    joining two records would produce a chunk describing neither.

    Args:
        documents: Output of `load_documents`.
        chunk_size: The size merged pages are allowed to approach.

    Returns:
        The documents with short consecutive pages combined, and a list of
        (first_page, last_page) pairs recording which runs were merged - used
        by the demo script to show what the fix actually did.
    """
    merged: list[LoadedDocument] = []
    ranges: list[tuple[int, int]] = []

    # A page is "short" if it could not fill a chunk on its own. Merging pages
    # that are already full-size would only create oversized units that the
    # chunker has to cut again, moving the boundary problem rather than fixing it.
    buffer: list[LoadedDocument] = []

    def flush() -> None:
        """Emit whatever is in the buffer as a single document."""
        if not buffer:
            return

        if len(buffer) == 1:
            merged.append(buffer[0])
            buffer.clear()
            return

        first, last = buffer[0], buffer[-1]

        # Blank line between pages so the chunker's paragraph-boundary search
        # can still prefer a page break as a cut point. The offsets of each
        # page within the combined text are recorded as they are built, because
        # afterwards they are unrecoverable - an inserted blank line is
        # indistinguishable from one that was already inside a page.
        separator = "\n\n"
        pieces: list[str] = []
        spans: list[tuple[int, int, int]] = []
        position = 0

        for document in buffer:
            spans.append((position, position + len(document.text), document.page))
            pieces.append(document.text)
            position += len(document.text) + len(separator)

        merged.append(
            LoadedDocument(
                source=first.source,
                path=first.path,
                text=separator.join(pieces),
                page=first.page,
                page_spans=tuple(spans),
            )
        )
        ranges.append((first.page, last.page))
        buffer.clear()

    for document in documents:
        if document.page is None:
            flush()
            merged.append(document)
            continue

        if buffer and buffer[0].source != document.source:
            flush()

        pending = sum(len(item.text) for item in buffer)
        separators = 2 * len(buffer)

        if buffer and pending + separators + len(document.text) > chunk_size:
            flush()

        buffer.append(document)

        # A single page that already fills a chunk has nothing to gain from
        # waiting for a neighbour.
        if len(document.text) >= chunk_size:
            flush()

    flush()

    return merged, ranges


def chunk_documents(
    documents: list[LoadedDocument],
    chunk_size: int = 500,
    overlap: int = 100,
    soften_boundaries: bool = True,
    merge_pages: bool = True,
) -> list[Chunk]:
    """Chunk a whole corpus, attaching citation metadata to every piece.

    Args:
        documents: Output of `load_documents`.
        chunk_size: Maximum characters per chunk.
        overlap: Characters repeated between consecutive chunks.
        soften_boundaries: Prefer paragraph, sentence, or word boundaries.
        merge_pages: Combine consecutive short PDF pages before chunking, so a
            slide deck does not produce chunks far below `chunk_size`. Pass
            False to see the unmerged behaviour, which the demo script does in
            order to show the difference.

    Returns:
        Every chunk from every document, in order. Whitespace-only chunks are
        dropped so they never reach the embedder, which rejects empty input.
    """
    if merge_pages:
        documents, _ = merge_short_pages(documents, chunk_size)

    chunks: list[Chunk] = []

    # Chunk numbering runs per source *file*, not per LoadedDocument, so that a
    # multi-page PDF produces notes.pdf#0, #1, #2... rather than restarting at
    # zero on every page and colliding.
    next_index: dict[str, int] = {}

    for document in documents:
        spans = chunk_spans(document.text, chunk_size, overlap, soften_boundaries)

        for start, end in spans:
            piece = document.text[start:end]

            if not piece.strip():
                continue

            index = next_index.get(document.source, 0)
            next_index[document.source] = index + 1

            page_start, page_end = _pages_covered(document, start, end)

            chunks.append(
                Chunk(
                    chunk_id=f"{document.source}#{index}",
                    text=piece,
                    source=document.source,
                    chunk_index=index,
                    start_char=start,
                    page=page_start,
                    page_end=page_end,
                    row=document.row,
                )
            )

    return chunks


def _pages_covered(
    document: LoadedDocument,
    start: int,
    end: int,
) -> tuple[int | None, int | None]:
    """Which pages a chunk at [start, end) actually came from.

    Uses the exact page offsets recorded during the merge rather than guessing
    from the text, so the page range in a citation is correct even when a page
    contained blank lines of its own.

    Returns:
        (first_page, last_page). Both None for a document with no pages.
        `last_page` equals `first_page` when the chunk sits on one page.
    """
    if document.page is None:
        return None, None

    if not document.page_spans:
        return document.page, document.page

    touched = [
        page
        for span_start, span_end, page in document.page_spans
        if span_start < end and span_end > start
    ]

    if not touched:
        # The chunk falls entirely inside a separator, which should not happen
        # for a non-empty chunk. Fall back to the document's first page rather
        # than returning nothing and losing the citation.
        return document.page, document.page

    return min(touched), max(touched)


def chunk_statistics(chunks: list[Chunk]) -> dict[str, float]:
    """Summarise a set of chunks, for comparing one configuration against another.

    Returns:
        Chunk count, character totals, and min/mean/max chunk length. The
        duplication ratio shows how much text overlap is costing: 1.25 means
        25% more characters are stored than the corpus actually contains.
    """
    if not chunks:
        return {"count": 0, "total_chars": 0, "min": 0, "mean": 0.0, "max": 0}

    lengths = [len(chunk.text) for chunk in chunks]
    return {
        "count": len(chunks),
        "total_chars": sum(lengths),
        "min": min(lengths),
        "mean": sum(lengths) / len(lengths),
        "max": max(lengths),
    }
