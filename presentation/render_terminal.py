"""
Render terminal sessions as PNG images, for the README and for sharing.

Run it:
    python presentation/render_terminal.py              # all sessions
    python presentation/render_terminal.py --only answer

Output goes to docs/screenshots/ as a .png plus the matching .txt transcript,
so every image can be traced back to the exact text it was drawn from.

Why generate rather than screen-grab: a real capture is frozen at whatever the
numbers were that day. These regenerate from live runs, so after retuning
anything the images can be rebuilt in one command instead of being retaken by
hand. The text is genuine output either way - nothing here is mocked up.

Needs Pillow, which is not in requirements.txt because the tool itself does not
need it:

    .\\venv\\Scripts\\python.exe -m pip install pillow
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "docs" / "screenshots"
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"

WRAP_AT = 96

# Terminal palette, roughly GitHub dark.
BACKDROP = (13, 17, 23)
TITLE_BAR = (33, 38, 45)
GREY = (139, 148, 158)
WHITE = (230, 237, 243)
GREEN = (63, 185, 80)
BLUE = (88, 166, 255)
AMBER = (210, 153, 34)
RED = (248, 81, 73)

FONT_SIZE = 15
LINE_HEIGHT = 23
PADDING = 24
TITLE_HEIGHT = 36

# (slug, caption, argv). Each runs for real; nothing is pre-baked.
SESSIONS: list[tuple[str, str, list[str]]] = [
    (
        "answer-with-citations",
        "A question answered from the notes, with its sources",
        ["scripts/ask.py", "--question", "what is the difference between training and inference?", "--no-log"],
    ),
    (
        "refusal",
        "A question the notes cannot answer - the tool declines instead of inventing",
        ["scripts/ask.py", "--question", "What is the capital of Peru?", "--no-log"],
    ),
    (
        "grounding-prompt",
        "The exact prompt sent to the model, printed without calling the API",
        ["scripts/ask.py", "--question", "what is a context window measured in?", "--show-prompt", "--no-log"],
    ),
    (
        "ingestion",
        "Ingestion: load, chunk, embed, index",
        ["scripts/ingest.py", "--folder", "sample-notes"],
    ),
    (
        "embeddings",
        "Related sentences score far above unrelated ones",
        ["scripts/embeddings.py"],
    ),
]

# Lines that are noise in an image rather than information.
SKIP_PATTERNS = [
    re.compile(r"loading local model"),
    re.compile(r"^\s*$\Z"),
]


def load_font(size: int):
    for name in ("consola.ttf", "CascadiaMono.ttf", "cour.ttf", "DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def run(argv: list[str]) -> list[str]:
    """Run a script and return its output lines."""
    environment = dict(os.environ)
    environment["HF_HUB_OFFLINE"] = "1"
    environment["ANONYMIZED_TELEMETRY"] = "False"
    environment["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        [str(PYTHON), *argv],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )

    combined = (completed.stdout or "") + (completed.stderr or "")
    lines = [
        line.rstrip()
        for line in combined.splitlines()
        if not any(pattern.search(line) for pattern in SKIP_PATTERNS)
    ]

    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    return lines


def wrap(lines: list[str]) -> list[str]:
    """Wrap long lines, keeping each line's indentation.

    Without this a generated answer becomes one very long line and the whole
    image scales down to unreadable inside a README.
    """
    out: list[str] = []

    for line in lines:
        if len(line) <= WRAP_AT:
            out.append(line)
            continue

        indent = len(line) - len(line.lstrip())
        wrapped = textwrap.wrap(
            line.strip(),
            width=max(20, WRAP_AT - indent),
            break_long_words=False,
            break_on_hyphens=False,
        )
        out.extend(" " * indent + part for part in wrapped)

    return out


def colour_for(line: str) -> tuple[int, int, int]:
    stripped = line.strip()

    if stripped and set(stripped) <= {"=", "-"}:
        return TITLE_BAR
    if stripped.startswith(("[ask]", "[loader]", "[pipeline]", "[retriever]", "[embedder]", "[log]")):
        return GREY
    if stripped.startswith("Q:"):
        return BLUE
    if stripped in ("ANSWER", "SOURCES") or stripped.startswith(("PART ", "STEP ", "SYSTEM PROMPT", "USER PROMPT")):
        return GREEN
    if "can't find the answer" in stripped or "NO CHUNK" in stripped:
        return RED
    if "cited" in stripped:
        return AMBER
    if re.match(r"^\[\d+\]", stripped):
        return GREY
    if re.match(r"^\d+\.\s+-?0?\.\d+", stripped):
        return GREY
    if stripped.startswith(("model:", "retrieved", "Model:", "Backend:")):
        return GREY
    return WHITE


def render(slug: str, caption: str, lines: list[str]) -> Path:
    lines = wrap(lines)
    font = load_font(FONT_SIZE)

    probe = Image.new("RGB", (10, 10))
    measure = ImageDraw.Draw(probe)
    widest = max([measure.textlength(line, font=font) for line in lines] or [200])

    width = int(widest + PADDING * 2) + 16
    height = TITLE_HEIGHT + PADDING * 2 + LINE_HEIGHT * len(lines)

    image = Image.new("RGB", (width, height), BACKDROP)
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, width, TITLE_HEIGHT], fill=TITLE_BAR)
    for index, colour in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        cx = 18 + index * 20
        draw.ellipse([cx - 6, TITLE_HEIGHT // 2 - 6, cx + 6, TITLE_HEIGHT // 2 + 6], fill=colour)

    label = "ask-my-docs"
    draw.text(
        ((width - measure.textlength(label, font=font)) / 2, TITLE_HEIGHT / 2 - FONT_SIZE / 2),
        label,
        font=font,
        fill=GREY,
    )

    y = TITLE_HEIGHT + PADDING
    for line in lines:
        draw.text((PADDING, y), line, font=font, fill=colour_for(line))
        y += LINE_HEIGHT

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUTPUT_DIR / f"{slug}.png"
    image.save(png)

    # Keep the transcript so each image is traceable to real text.
    (OUTPUT_DIR / f"{slug}.txt").write_text(
        f"# {caption}\n\n" + "\n".join(lines) + "\n", encoding="utf-8"
    )

    return png


def main() -> int:
    parser = argparse.ArgumentParser(description="Render terminal sessions to PNG.")
    parser.add_argument("--only", help="Render a single session by slug")
    arguments = parser.parse_args()

    if not PYTHON.exists():
        print(f"[error] venv interpreter not found at {PYTHON}")
        return 1

    chosen = [s for s in SESSIONS if not arguments.only or s[0] == arguments.only]

    if not chosen:
        print(f"[error] no session called {arguments.only!r}")
        print("        available: " + ", ".join(slug for slug, _, _ in SESSIONS))
        return 1

    for slug, caption, argv in chosen:
        print(f"running {slug} ...", end=" ", flush=True)
        lines = run(argv)

        if not lines:
            print("no output, skipped")
            continue

        png = render(slug, caption, lines)
        size = Image.open(png).size
        print(f"{png.relative_to(ROOT)}  {size[0]}x{size[1]}")

    print(f"\nwrote to {OUTPUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
