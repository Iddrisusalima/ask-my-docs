"""
Reading a folder of documents into plain text.

This is the least glamorous stage of the pipeline and the one most likely to
quietly ruin everything downstream. Retrieval can only ever be as good as the
text that reached it: if a PDF extracts as gibberish, no amount of chunk-size
tuning will rescue the answers.

The central question this module answers
----------------------------------------
Every format arrives with its own natural unit, and the choice of unit decides
what a citation can say. Get it wrong here and the information is gone - you
cannot recover "which page was this on?" later from a character offset without
reverse-engineering something you threw away.

So each format is split at the boundary its own structure provides:

- **Markdown and text: one document per file.** The file is already one
  continuous piece of prose. There is no internal landmark to cite, so the
  citation names the file and the chunk number within it.

- **PDF: one document per page.** Page numbers exist for free at this point and
  are the landmark a reader can actually use - "page 7" means something when
  they open the file. The cost is that pages cannot merge, so a slide deck with
  200 characters on a page yields a 200-character chunk no matter what chunk
  size is configured. `merge_short_pages` in the chunker exists for exactly
  that, and it carries a page *range* into the citation.

- **DOCX: one document per file.** A .docx has no reliable page boundaries at
  all - pagination is computed by the renderer from fonts and page size, not
  stored in the file. Claiming a page number would mean inventing one, so this
  format is treated like markdown.

- **CSV: one document per row.** A row is a record, not a sentence. Flattening
  a whole sheet into prose produces chunks that straddle unrelated records and
  embed as an average of all of them. One row per document keeps each record
  individually retrievable, and the column names are repeated into every row so
  that a value like "350" still carries the word "chunk_size" next to it.

One more rule, which applies throughout
---------------------------------------
**One bad file must not kill the run.** A single scanned PDF with no text layer,
sitting in a folder of ten good notes, should produce a warning naming the file -
not a traceback that abandons the other nine.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

# Extensions we know how to read. Anything else in the folder is ignored
# silently, so a stray .png or .keynote is not treated as an error.
MARKDOWN_EXTENSIONS = {".md", ".markdown", ".txt"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
CSV_EXTENSIONS = {".csv", ".tsv"}
SUPPORTED_EXTENSIONS = (
    MARKDOWN_EXTENSIONS | PDF_EXTENSIONS | DOCX_EXTENSIONS | CSV_EXTENSIONS
)

# A CSV cell holding a paragraph of prose is a document in its own right, but a
# cell holding "42" is not. Rows shorter than this contribute too little meaning
# to be worth their own embedding, and are reported rather than indexed.
MINIMUM_ROW_CHARACTERS = 12


@dataclass(frozen=True)
class LoadedDocument:
    """One unit of text pulled off disk, with enough context to cite it later.

    The unit differs by format - a PDF page, a CSV row, or a whole markdown
    file - which is why `page` and `row` are both optional and mutually
    exclusive. Whichever is set determines how the chunk is cited.

    Attributes:
        source: Filename as it will appear in a citation, e.g. "notes.md".
            Deliberately not the full path - absolute paths in citations are
            noise, and they leak the directory layout of the author's machine.
        path: Full path on disk, kept for debugging.
        text: The extracted text.
        page: 1-based page number for PDFs, None for every other format. When
            several short pages have been merged, this is the first of them.
        row: 1-based row number for CSVs, counting data rows and excluding the
            header. None for every other format.
        page_spans: (start, end, page) triples recording exactly which range of
            characters in `text` came from which page. Empty for a document
            that is a single page or has no pages at all. Populated by
            `merge_short_pages`, which is the only place the mapping is still
            known - once pages are concatenated, the boundaries cannot be
            inferred from the text, because a blank line inserted between two
            pages looks identical to one that was already inside a page.
    """

    source: str
    path: Path
    text: str
    page: int | None = None
    row: int | None = None
    page_spans: tuple[tuple[int, int, int], ...] = ()

    def describe(self) -> str:
        """Human-readable label, used in warnings and citations."""
        if self.page is not None:
            return f"{self.source} p.{self.page}"
        if self.row is not None:
            return f"{self.source} r.{self.row}"
        return self.source


class DocumentLoadError(Exception):
    """The folder itself is unusable - wrong path, or nothing readable inside."""


def load_documents(folder: str | Path, verbose: bool = True) -> list[LoadedDocument]:
    """Read every supported document in a folder, including subfolders.

    Args:
        folder: Directory to read.
        verbose: Print a per-file summary and any warnings.

    Returns:
        LoadedDocument objects, one per natural unit of each format:
        markdown, text and .docx files contribute exactly one entry each;
        PDFs contribute one entry per page that has extractable text; CSVs and
        TSVs contribute one entry per data row.

    Raises:
        DocumentLoadError: If the folder does not exist, is not a directory, or
            contains no supported files at all.
    """
    folder_path = Path(folder).resolve()

    if not folder_path.exists():
        raise DocumentLoadError(
            f"Folder not found: {folder_path}\n"
            "Create it and add some notes, or pass a different path."
        )

    if not folder_path.is_dir():
        raise DocumentLoadError(f"Not a folder: {folder_path}")

    candidates = sorted(
        path
        for path in folder_path.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not candidates:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise DocumentLoadError(
            f"No supported documents found in {folder_path}\n"
            f"Supported extensions: {supported}\n"
            "Add 5-10 of your own notes to this folder and try again."
        )

    documents: list[LoadedDocument] = []
    warnings: list[str] = []

    for path in candidates:
        suffix = path.suffix.lower()

        try:
            if suffix in PDF_EXTENSIONS:
                loaded, file_warnings = _load_pdf(path)
            elif suffix in DOCX_EXTENSIONS:
                loaded, file_warnings = _load_docx(path)
            elif suffix in CSV_EXTENSIONS:
                loaded, file_warnings = _load_csv(path)
            else:
                loaded, file_warnings = _load_text_file(path)

            documents.extend(loaded)
            warnings.extend(file_warnings)

        except Exception as exc:
            # Deliberately broad: a malformed PDF can fail in many ways, and no
            # single bad file is worth abandoning the rest of the folder for.
            warnings.append(f"{path.name}: could not be read ({exc.__class__.__name__}: {exc})")

    if verbose:
        _report(folder_path, candidates, documents, warnings)

    if not documents:
        raise DocumentLoadError(
            f"Found {len(candidates)} file(s) in {folder_path} but extracted no text from any of them.\n"
            "If these are scanned PDFs they contain images rather than text, and would need OCR "
            "(out of scope for this project). Try markdown notes instead."
        )

    return documents


def _load_text_file(path: Path) -> tuple[list[LoadedDocument], list[str]]:
    """Read a markdown or plain text file as UTF-8."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], [
            f"{path.name}: not valid UTF-8, skipped. "
            "Re-save it as UTF-8 if you want it included."
        ]

    if not text.strip():
        return [], [f"{path.name}: file is empty, skipped."]

    return [LoadedDocument(source=path.name, path=path, text=text)], []


def _load_pdf(path: Path) -> tuple[list[LoadedDocument], list[str]]:
    """Extract text from a PDF, one LoadedDocument per page with text on it."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - environment problem
        raise ImportError(
            "Reading PDFs needs pypdf. Install it with:  pip install pypdf"
        ) from exc

    reader = PdfReader(str(path))

    if reader.is_encrypted:
        # An empty user password is common and harmless; a real one we skip.
        try:
            reader.decrypt("")
        except Exception:
            return [], [f"{path.name}: password protected, skipped."]

    documents: list[LoadedDocument] = []
    empty_pages: list[int] = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            empty_pages.append(page_number)
            del exc
            continue

        if not text.strip():
            empty_pages.append(page_number)
            continue

        documents.append(
            LoadedDocument(source=path.name, path=path, text=text, page=page_number)
        )

    warnings: list[str] = []
    if empty_pages and not documents:
        warnings.append(
            f"{path.name}: no extractable text on any of {len(empty_pages)} page(s), skipped. "
            "This is usually a scanned PDF - the pages are images, and reading them "
            "would need OCR."
        )
    elif empty_pages:
        pages = ", ".join(str(number) for number in empty_pages[:10])
        suffix = "..." if len(empty_pages) > 10 else ""
        warnings.append(f"{path.name}: no text on page(s) {pages}{suffix}, those pages skipped.")

    return documents, warnings


def _load_docx(path: Path) -> tuple[list[LoadedDocument], list[str]]:
    """Extract text from a Word document, as a single LoadedDocument.

    Unlike a PDF, a .docx stores no page boundaries. Pagination is worked out by
    whatever renders the file, from the font metrics and page size in use, so
    there is no page number to read. Inventing one would put a number in a
    citation that nothing could verify, so this is treated like markdown: one
    document per file, cited by chunk number.

    Both paragraphs and table cells are collected. Tables are common in real
    documents and skipping them would silently lose content - the worst kind of
    failure, because retrieval would simply never return it and nothing would
    say why.
    """
    try:
        from docx import Document as DocxDocument
    except ImportError as exc:  # pragma: no cover - environment problem
        raise ImportError(
            "Reading .docx files needs python-docx. Install it with:  "
            "pip install python-docx"
        ) from exc

    document = DocxDocument(str(path))

    blocks: list[str] = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue

        # Headings carry structure that the chunker's paragraph-boundary search
        # can use, so they are kept as their own block rather than run together
        # with the body text that follows.
        blocks.append(text)

    table_cells = 0
    for table in document.tables:
        for table_row in table.rows:
            cells = [cell.text.strip() for cell in table_row.cells]
            filled = [cell for cell in cells if cell]
            if not filled:
                continue
            # Repeated cells are common in merged-cell layouts; collapsing them
            # avoids feeding the embedder the same phrase three times.
            deduplicated = list(dict.fromkeys(filled))
            blocks.append(" | ".join(deduplicated))
            table_cells += len(deduplicated)

    text = "\n\n".join(blocks)

    if not text.strip():
        return [], [
            f"{path.name}: no text found in paragraphs or tables, skipped. "
            "If the content is inside images or text boxes, python-docx cannot "
            "reach it."
        ]

    warnings: list[str] = []
    if table_cells:
        warnings.append(
            f"{path.name}: {table_cells} table cell(s) included alongside the paragraphs."
        )

    return [LoadedDocument(source=path.name, path=path, text=text)], warnings


def _load_csv(path: Path) -> tuple[list[LoadedDocument], list[str]]:
    """Read a CSV or TSV, producing one LoadedDocument per data row.

    Why per row rather than per file
    --------------------------------
    A spreadsheet is a set of records, and records are independent. Rendering
    the whole sheet as one block of text and then cutting it every 350
    characters produces chunks that begin halfway through one record and end
    halfway through another. The embedding of such a chunk describes no record
    in particular, so a question about any single row matches it only weakly.

    One document per row keeps each record whole and individually retrievable,
    and gives the citation a row number that a reader can find in the file.

    Why the column names are repeated into every row
    ------------------------------------------------
    A row rendered as bare values - "350, 70, 5" - has lost the only thing that
    made it meaningful. Rendering it as "chunk_size: 350 | overlap: 70 | top_k:
    5" means the words a question would actually use are present in the text
    being embedded. The repetition costs storage and buys retrievability.
    """
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","

    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return [], [
            f"{path.name}: not valid UTF-8, skipped. Re-save it as UTF-8 "
            "(in Excel: Save As, CSV UTF-8) if you want it included."
        ]

    if not raw.strip():
        return [], [f"{path.name}: file is empty, skipped."]

    reader = csv.reader(io.StringIO(raw), delimiter=delimiter)

    try:
        header = next(reader)
    except StopIteration:
        return [], [f"{path.name}: file is empty, skipped."]

    # A header row of blanks or numbers is not a header - it is data, and using
    # it as labels would mislabel every row in the file.
    looks_like_header = any(
        cell.strip() and not cell.strip().replace(".", "", 1).isdigit()
        for cell in header
    )
    if not looks_like_header:
        return [], [
            f"{path.name}: first row looks like data rather than column names, "
            "skipped. Add a header row naming each column so rows can be "
            "rendered with their labels."
        ]

    labels = [cell.strip() or f"column_{position + 1}" for position, cell in enumerate(header)]

    documents: list[LoadedDocument] = []
    too_short = 0
    ragged = 0

    for row_number, values in enumerate(reader, start=1):
        if not any(value.strip() for value in values):
            continue

        if len(values) != len(labels):
            ragged += 1

        pairs = [
            f"{labels[position] if position < len(labels) else f'column_{position + 1}'}: {value.strip()}"
            for position, value in enumerate(values)
            if value.strip()
        ]

        text = " | ".join(pairs)

        if len(text) < MINIMUM_ROW_CHARACTERS:
            too_short += 1
            continue

        documents.append(
            LoadedDocument(source=path.name, path=path, text=text, row=row_number)
        )

    warnings: list[str] = []
    if ragged:
        warnings.append(
            f"{path.name}: {ragged} row(s) had a different number of fields than the "
            "header; extra fields were labelled by position."
        )
    if too_short:
        warnings.append(
            f"{path.name}: {too_short} row(s) held fewer than {MINIMUM_ROW_CHARACTERS} "
            "characters once labelled, and were skipped as too small to embed meaningfully."
        )
    if not documents:
        warnings.append(f"{path.name}: no usable data rows found, skipped.")

    return documents, warnings


def _report(
    folder: Path,
    candidates: list[Path],
    documents: list[LoadedDocument],
    warnings: list[str],
) -> None:
    """Print what was loaded, broken down by the unit each format produced."""
    total_characters = sum(len(document.text) for document in documents)
    pdf_pages = sum(1 for document in documents if document.page is not None)
    csv_rows = sum(1 for document in documents if document.row is not None)
    whole_files = len(documents) - pdf_pages - csv_rows

    units = []
    if whole_files:
        units.append(f"{whole_files} whole file(s)")
    if pdf_pages:
        units.append(f"{pdf_pages} PDF page(s)")
    if csv_rows:
        units.append(f"{csv_rows} CSV row(s)")

    extensions: dict[str, int] = {}
    for path in candidates:
        suffix = path.suffix.lower()
        extensions[suffix] = extensions.get(suffix, 0) + 1
    breakdown = ", ".join(
        f"{count} {suffix}" for suffix, count in sorted(extensions.items())
    )

    print(f"[loader] {folder}")
    print(f"[loader] {len(candidates)} file(s) found ({breakdown})")
    print(
        f"[loader] -> {len(documents)} document(s): {', '.join(units) or 'none'}, "
        f"{total_characters:,} characters"
    )

    for warning in warnings:
        print(f"[loader] warning: {warning}")
