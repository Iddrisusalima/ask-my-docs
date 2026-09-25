"""
Writing retrieval results to a file so quality can be reviewed later.

Terminal output scrolls away. Judging whether retrieval is any good means
comparing many questions against each other, noticing that one source dominates
every result, or spotting that scores collapsed after a settings change - none of
which is possible from whatever happens to still be on screen.

Three decisions about the format:

- **Append, never overwrite.** The value is in accumulating runs over days.
- **Record the configuration alongside the results.** A score is meaningless
  without knowing the chunk size, top-k and model that produced it. A log of
  scores with no settings is a log of numbers that cannot be compared.
- **Truncate chunk text to a preview.** Full chunks would make the file
  unreadable, and the point is to skim for problems. The chunk id is recorded, so
  the full text is always one lookup away.

Logs go to a gitignored directory: this is working material, not a deliverable.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.retriever import RetrievedChunk

DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "retrieval.log"
PREVIEW_WIDTH = 100


class RetrievalLog:
    """Appends retrieval results to a text file.

    Args:
        directory: Where to write. Created if it does not exist.
        filename: Log file name within that directory.

    Example:
        >>> log = RetrievalLog()
        >>> log.write("why does overlap matter?", results, {"top_k": 5})
    """

    def __init__(self, directory: str | Path = DEFAULT_LOG_DIR, filename: str = DEFAULT_LOG_FILE):
        self.directory = Path(directory)
        self.path = self.directory / filename

    def write(
        self,
        question: str,
        results: list[RetrievedChunk],
        configuration: dict | None = None,
    ) -> Path:
        """Append one question and its results to the log.

        Args:
            question: The question asked.
            results: What retrieval returned, in order.
            configuration: Settings in play - model, chunk size, top-k. Recorded
                so results from different runs remain comparable.

        Returns:
            Path to the log file.
        """
        self.directory.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "=" * 78,
            f"[{timestamp}]  {question}",
        ]

        if configuration:
            settings = "  ".join(f"{key}={value}" for key, value in sorted(configuration.items()))
            lines.append(f"  config: {settings}")

        if not results:
            # Worth logging loudly. An empty result set is a finding, not an
            # absence of data - it means the floor rejected everything.
            lines.append("  NO RESULTS - nothing cleared the relevance floor")
        else:
            scores = [result.score for result in results]
            lines.append(
                f"  {len(results)} result(s)  best={max(scores):.4f}  "
                f"worst={min(scores):.4f}  spread={max(scores) - min(scores):.4f}"
            )
            for rank, result in enumerate(results, start=1):
                lines.append(
                    f"  {rank:>2}. {result.score:.4f}  {result.citation():<30} "
                    f"{result.chunk.preview(PREVIEW_WIDTH)}"
                )

        lines.append("")

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

        return self.path

    def entry_count(self) -> int:
        """How many questions are recorded, for confirming writes landed."""
        if not self.path.exists():
            return 0
        return self.path.read_text(encoding="utf-8").count("=" * 78)
