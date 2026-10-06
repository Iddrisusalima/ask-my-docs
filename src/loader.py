"""
Reading a folder of documents into plain text.

This is the least glamorous stage of the pipeline and the one most likely to
quietly ruin everything downstream. Retrieval can only ever be as good as the
text that reached it: if a PDF extracts as gibberish, no amount of chunk-size
tuning will rescue the answers.

Two design decisions worth understanding:

1. **A PDF becomes one document per page, not one per file.** Page numbers are
   captured here, at the only point in the pipeline where they are known for
   free. Try to recover "which page was this on?" later, from a character
   offset, and you are reverse-engineering information you threw away.

2. **One bad file must not kill the run.** A single scanned PDF with no text
   layer, sitting in a folder of ten good notes, should produce a warning naming
   the file - not a traceback that abandons the other nine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Extensions we know how to read. Anything else in the folder is ignored
# silently, so a stray .png or .docx is not treated as an error.
MARKDOWN_EXTENSIONS = {".md", ".markdown", ".txt"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = MARKDOWN_EXTENSIONS | PDF_EXTENSIONS


@dataclass(frozen=True)
class LoadedDocument:
    """One unit of text pulled off disk, with enough context to cite it later.

    Attributes:
        source: Filename as it will appear in a citation, e.g. "notes.md".
            Deliberately not the full path - absolute paths in citations are
            noise, and they leak the directory layout of the author's machine.
        path: Full path on disk, kept for debugging.
        text: The extracted text.
        page: 1-based page number for PDFs, None for markdown and text files.
    """

    source: str
    path: Path
    text: str
    page: int | None = None

    def describe(self) -> str:
        """Human-readable label, used in warnings and citations."""
        if self.page is None:
            return self.source
        return f"{self.source} p.{self.page}"


class DocumentLoadError(Exception):
    """The folder itself is unusable - wrong path, or nothing readable inside."""


def load_documents(folder: str | Path, verbose: bool = True) -> list[LoadedDocument]:
    """Read every supported document in a folder, including subfolders.

    Args:
        folder: Directory to read.
        verbose: Print a per-file summary and any warnings.

    Returns:
        LoadedDocument objects. PDFs contribute one entry per page that has
        extractable text; markdown and text files contribute exactly one entry.

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
        try:
            if path.suffix.lower() in PDF_EXTENSIONS:
                loaded, file_warnings = _load_pdf(path)
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


def _report(
    folder: Path,
    candidates: list[Path],
    documents: list[LoadedDocument],
    warnings: list[str],
) -> None:
    """Print what was loaded, and anything that went wrong."""
    total_characters = sum(len(document.text) for document in documents)
    pdf_pages = sum(1 for document in documents if document.page is not None)

    print(f"[loader] {folder}")
    print(
        f"[loader] {len(candidates)} file(s) found -> {len(documents)} document(s) "
        f"({pdf_pages} PDF page(s)), {total_characters:,} characters"
    )

    for warning in warnings:
        print(f"[loader] warning: {warning}")
