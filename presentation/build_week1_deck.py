"""
Generate the Week 1 review deck for the mentor check-in.

Run it:
    python presentation/build_week1_deck.py

Output:
    presentation/week1-review.pptx

Ten slides. Every number comes from a real run recorded in
notes/week1-learning-log.md - if a figure is not in that file, it does not belong
on a slide.

Needs python-pptx, deliberately kept out of requirements.txt since the tool
itself does not need it:

    .\\venv\\Scripts\\python.exe -m pip install python-pptx==1.0.2

Slide 5 is intentionally left blank. "What an embedding is" has to be in the
presenter's own words - it is on the mentor's self-check list, and borrowed
phrasing will not survive a follow-up question.

Design rules for this deck, learned the hard way:
  - one idea per slide, five bullets maximum
  - short lines; if a bullet wraps onto three lines it is a paragraph
  - the speaker notes carry the detail, not the slide
"""

from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Inches, Pt

# ---------------------------------------------------------------------------
# Look and feel
# ---------------------------------------------------------------------------

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x66, 0x66, 0x66)
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
GOOD = RGBColor(0x1E, 0x7B, 0x3C)
ALERT = RGBColor(0xB3, 0x2D, 0x2D)
RULE = RGBColor(0xD8, 0xD8, 0xD8)
BAND = RGBColor(0xF2, 0xF5, 0xF8)

BODY_FONT = "Segoe UI"
MONO_FONT = "Consolas"

MARGIN = Inches(0.85)
CONTENT_WIDTH = SLIDE_WIDTH - (2 * MARGIN)


class Deck:
    """Thin wrapper over python-pptx for the four layouts this deck needs."""

    def __init__(self) -> None:
        self.presentation = Presentation()
        self.presentation.slide_width = SLIDE_WIDTH
        self.presentation.slide_height = SLIDE_HEIGHT
        self._blank = self.presentation.slide_layouts[6]

    # -- building blocks ---------------------------------------------------

    def _new(self):
        return self.presentation.slides.add_slide(self._blank)

    def _textbox(self, slide, left, top, width, height):
        box = slide.shapes.add_textbox(left, top, width, height)
        frame = box.text_frame
        frame.word_wrap = True
        return frame

    def _heading(self, slide, title: str, kicker: str | None = None) -> Emu:
        top = Inches(0.5)

        if kicker:
            frame = self._textbox(slide, MARGIN, top, CONTENT_WIDTH, Inches(0.3))
            run = frame.paragraphs[0]
            run.text = kicker.upper()
            run.font.size = Pt(12)
            run.font.bold = True
            run.font.color.rgb = ACCENT
            run.font.name = BODY_FONT
            top = top + Inches(0.36)

        frame = self._textbox(slide, MARGIN, top, CONTENT_WIDTH, Inches(0.8))
        run = frame.paragraphs[0]
        run.text = title
        run.font.size = Pt(30)
        run.font.bold = True
        run.font.color.rgb = INK
        run.font.name = BODY_FONT

        line_top = top + Inches(0.78)
        line = slide.shapes.add_shape(1, MARGIN, line_top, CONTENT_WIDTH, Pt(1.5))
        line.fill.solid()
        line.fill.fore_color.rgb = RULE
        line.line.fill.background()
        line.shadow.inherit = False

        return line_top + Inches(0.34)

    def _notes(self, slide, notes: str) -> None:
        slide.notes_slide.notes_text_frame.text = notes.strip()

    def _footer(self, slide, text: str) -> None:
        frame = self._textbox(slide, MARGIN, Inches(6.6), CONTENT_WIDTH, Inches(0.5))
        run = frame.paragraphs[0]
        run.text = text
        run.font.size = Pt(12)
        run.font.italic = True
        run.font.color.rgb = MUTED
        run.font.name = BODY_FONT

    # -- slide types -------------------------------------------------------

    def title_slide(self, title: str, subtitle: str, meta: str, notes: str) -> None:
        slide = self._new()

        band = slide.shapes.add_shape(1, Emu(0), Inches(2.25), SLIDE_WIDTH, Inches(2.1))
        band.fill.solid()
        band.fill.fore_color.rgb = BAND
        band.line.fill.background()
        band.shadow.inherit = False

        for top, text, size, bold, colour in (
            (Inches(2.5), title, 46, True, INK),
            (Inches(3.45), subtitle, 20, False, ACCENT),
            (Inches(4.75), meta, 14, False, MUTED),
        ):
            frame = self._textbox(slide, MARGIN, top, CONTENT_WIDTH, Inches(0.9))
            run = frame.paragraphs[0]
            run.text = text
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = colour
            run.font.name = BODY_FONT

        self._notes(slide, notes)

    def bullets_slide(
        self,
        title: str,
        bullets: list[tuple[int, str]],
        notes: str,
        kicker: str | None = None,
        footer: str | None = None,
    ) -> None:
        """Bullets as (indent_level, text). Prefix with '**' for a bold lead-in."""
        slide = self._new()
        top = self._heading(slide, title, kicker)

        frame = self._textbox(slide, MARGIN, top, CONTENT_WIDTH, Inches(4.3))

        for position, (level, text) in enumerate(bullets):
            paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
            paragraph.level = level

            bold = text.startswith("**")
            clean = text.removeprefix("**")

            if not clean.strip():
                paragraph.text = ""
                paragraph.font.size = Pt(8)
                continue

            marker = "" if level == 0 and bold else ("•  " if level == 0 else "–  ")
            paragraph.text = f"{marker}{clean}"
            paragraph.font.size = Pt(20 if level == 0 else 17)
            paragraph.font.bold = bold
            paragraph.font.color.rgb = INK if level == 0 else MUTED
            paragraph.font.name = BODY_FONT
            paragraph.space_after = Pt(14)

        if footer:
            self._footer(slide, footer)

        self._notes(slide, notes)

    def table_slide(
        self,
        title: str,
        headers: list[str],
        rows: list[list[str]],
        notes: str,
        kicker: str | None = None,
        footer: str | None = None,
        highlight_rows: set[int] | None = None,
        column_widths: list[float] | None = None,
        caption: str | None = None,
    ) -> None:
        slide = self._new()
        top = self._heading(slide, title, kicker)
        highlight_rows = highlight_rows or set()

        if caption:
            frame = self._textbox(slide, MARGIN, top, CONTENT_WIDTH, Inches(0.4))
            run = frame.paragraphs[0]
            run.text = caption
            run.font.size = Pt(16)
            run.font.color.rgb = MUTED
            run.font.name = BODY_FONT
            top = top + Inches(0.55)

        row_count = len(rows) + 1
        height = Inches(0.46) * row_count
        shape = slide.shapes.add_table(row_count, len(headers), MARGIN, top, CONTENT_WIDTH, height)
        table = shape.table

        if column_widths:
            total = sum(column_widths)
            for index, share in enumerate(column_widths):
                table.columns[index].width = Emu(int(CONTENT_WIDTH * (share / total)))

        for column, label in enumerate(headers):
            cell = table.cell(0, column)
            cell.text = label
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.font.size = Pt(15)
            paragraph.font.bold = True
            paragraph.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            paragraph.font.name = BODY_FONT
            cell.fill.solid()
            cell.fill.fore_color.rgb = ACCENT

        for row_index, row in enumerate(rows, start=1):
            emphasise = (row_index - 1) in highlight_rows
            for column, value in enumerate(row):
                cell = table.cell(row_index, column)
                cell.text = value
                paragraph = cell.text_frame.paragraphs[0]
                paragraph.font.size = Pt(15)
                paragraph.font.bold = emphasise
                paragraph.font.name = MONO_FONT if column > 0 else BODY_FONT
                paragraph.font.color.rgb = ALERT if emphasise else INK
                cell.fill.solid()
                cell.fill.fore_color.rgb = BAND if emphasise else RGBColor(0xFF, 0xFF, 0xFF)

        if footer:
            self._footer(slide, footer)

        self._notes(slide, notes)

    def statement_slide(
        self,
        title: str,
        headline: str,
        support: list[str],
        notes: str,
        kicker: str | None = None,
        colour: RGBColor | None = None,
    ) -> None:
        slide = self._new()
        top = self._heading(slide, title, kicker)

        frame = self._textbox(slide, MARGIN, top + Inches(0.2), CONTENT_WIDTH, Inches(0.9))
        run = frame.paragraphs[0]
        run.text = headline
        run.font.size = Pt(36)
        run.font.bold = True
        run.font.color.rgb = colour or ALERT
        run.font.name = BODY_FONT

        frame = self._textbox(slide, MARGIN, top + Inches(1.4), CONTENT_WIDTH, Inches(3.3))
        for position, line in enumerate(support):
            paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
            paragraph.text = line
            paragraph.font.size = Pt(19)
            paragraph.font.color.rgb = INK
            paragraph.font.name = BODY_FONT
            paragraph.space_after = Pt(15)

        self._notes(slide, notes)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.presentation.save(str(path))


# ---------------------------------------------------------------------------
# The ten slides
# ---------------------------------------------------------------------------


def build() -> Deck:
    deck = Deck()

    # 1 -------------------------------------------------------------------
    deck.title_slide(
        "Ask My Docs",
        "Week 1 review — embeddings and chunking",
        "Mon 21 – Sun 27 Sep 2026   ·   A question-answering tool over my own notes, built without a framework",
        notes="""
Opening line, roughly:

"Week 1 was the groundwork - turning text into numbers, and cutting documents
into pieces. Both are working. I also found three things that changed how I plan
to build weeks 2 and 3."

Then be upfront: "Four things are still outstanding, all mine to finish, and
they're on the last slide."

Saying that at the start rather than the end makes everything in between more
credible.
        """,
    )

    # 2 -------------------------------------------------------------------
    deck.bullets_slide(
        "What the tool will do, and where I am",
        [
            (0, "**Goal: ask questions about my own notes, answered only from those notes"),
            (0, "Five stages, each written by hand:"),
            (1, "chunk  →  embed  →  store  →  retrieve  →  generate"),
            (0, "**Week 1 delivered the first two, plus a working search"),
            (0, "No LangChain or LlamaIndex — your brief asks for it built manually"),
        ],
        kicker="Overview",
        footer="Repo: ask-my-docs · 4 commits · Python, a free local embedding model, no API key needed yet",
        notes="""
Keep this to about 30 seconds. It is orientation, not content.

If he asks why no framework: a framework would have done all of week 1 in about
four lines and I would not be able to explain any of them. A week is the cost;
understanding the four lines is the benefit.
        """,
    )

    # 3 -------------------------------------------------------------------
    deck.bullets_slide(
        "One thing I need you to decide",
        [
            (0, "**The brief's dates are a week out"),
            (1, "It says start Mon 14 Sep, deadline Sun 4 Oct"),
            (1, "I actually started Mon 21 Sep"),
            (0, "**So my weeks are 21–27 Sep, 28 Sep–4 Oct, 5–11 Oct"),
            (0, "That puts your 4 Oct deadline at the end of my Week 2"),
            (0, "**Does the deadline move to 11 Oct, or stay at 4 Oct?"),
        ],
        kicker="Decision needed",
        footer="Your brief says adjusting scope is easy in week 1 and hard on the final Sunday — so I'm asking now",
        notes="""
Raise this early. If he holds 4 October you lose a whole week, and you both need
to know that at the start of the meeting, not the end.

Have the answer ready for "what would you cut?": the optional extras go first -
tuning top-k beyond a single comparison, and the Chroma-versus-Pinecone write-up.
What I would not cut is citations, the no-answer handling, or the demo video.
        """,
    )

    # 4 -------------------------------------------------------------------
    deck.table_slide(
        "Embeddings: does this actually work?",
        ["what I compared", "score"],
        [
            ["Three sentences that all mean \"I bake at weekends\"", "0.617"],
            ["Three sentences on unrelated topics", "0.031"],
            ["\"sourdough every weekend\" vs \"Saturdays, a loaf from scratch\"", "0.618"],
        ],
        highlight_rows={2},
        column_widths=[3.4, 0.8],
        kicker="Mon–Tue",
        caption="I chose a free local model (all-MiniLM-L6-v2) so re-running experiments costs nothing.",
        footer="The highlighted pair shares no useful words at all — a keyword search would score it near zero",
        notes="""
Spend your time on the highlighted row.

"Those two sentences share no useful words at all. One says sourdough and
weekend, the other says Saturdays and loaf from scratch. A keyword search scores
that pair near zero. The model scored it 0.618, purely from meaning. That is the
whole reason this project uses embeddings instead of search."

Why a local model, if asked: Wednesday needed the whole corpus re-embedded
repeatedly to compare chunk sizes. If I were paying per call I would have
hesitated to re-run experiments, and that hesitation is the thing I most needed
to avoid. OpenAI is wired up behind one setting if I want to compare later.

Why hand-write cosine similarity: your brief says build manually, and I wanted to
understand why you divide by the length of both - it cancels length out, so a
short sentence and a long paragraph that mean the same thing still match.
        """,
    )

    # 5 -------------------------------------------------------------------
    deck.bullets_slide(
        "What an embedding is — in my own words",
        [
            (0, "[ I fill this in before presenting ]"),
            (0, ""),
            (0, "**Your self-check: explain it without using \"vector\" as a cop-out"),
            (0, "What I have to work with:"),
            (1, "7 characters in and 196 characters in both give exactly 384 numbers out"),
            (1, "Two sentences with no shared words scored 0.618"),
            (1, "The numbers mean nothing alone — only their positions relative to each other"),
        ],
        kicker="Mon–Tue",
        footer="Left blank on purpose — this one has to be mine, or it falls apart when you ask a follow-up",
        notes="""
WRITE THIS YOURSELF BEFORE THE MEETING. Three or four sentences, in your voice,
replacing the placeholder line.

The bullets are your raw material, not the answer.

A shape to react to and then discard: an embedding model reads text and hands
back coordinates on a map of meaning, where things that mean similar things sit
close together. Say it your own way. He will ask a follow-up question, and that
is exactly where borrowed wording collapses.

If you genuinely run out of time, present the slide as unfinished and say so.
That is far better than reciting a sentence you cannot defend.
        """,
    )

    # 6 -------------------------------------------------------------------
    deck.table_slide(
        "Why chunking needs care: a fact that vanished",
        ["how I cut the document", "can the fact be found?"],
        [
            ["500 characters, no overlap", "NO — it is in no chunk"],
            ["500 characters, cut at sentence ends", "yes"],
            ["500 characters, with 100 overlapping", "yes"],
        ],
        highlight_rows={0},
        column_widths=[2.4, 1.6],
        kicker="Wed–Thu",
        caption="I hid one sentence so that a 500-character cut would land in the middle of it.",
        footer="Overlap means each chunk repeats the last 100 characters of the one before it",
        notes="""
This is the most important slide of the week. Go slowly.

Row 1: the sentence is in the document. It got split down the middle, so half is
in one chunk and half in the next. Neither half is complete enough to match a
question about it. So the fact is in my notes and my tool cannot find it - and
nothing anywhere reports an error. The answers just quietly get worse.

Then the subtle bit, which is the part worth knowing:

Row 2 fixes it by luck. My splitter looks backwards for a sentence ending, and
this time it found one before the fact. That only works when the text happens to
have punctuation in the right place.

Row 3 fixes it deliberately. Overlap does not depend on the text cooperating.
        """,
    )

    # 7 -------------------------------------------------------------------
    deck.table_slide(
        "Picking a chunk size",
        ["chunk size", "chunks", "what one chunk held"],
        [
            ["300 characters", "199", "one idea, nothing else"],
            ["500 characters", "155", "one idea + start of a table"],
            ["1500 characters", "50", "the idea, a whole table, 2 more sections"],
        ],
        highlight_rows={1},
        column_widths=[1.2, 0.8, 2.6],
        kicker="Wed–Thu",
        caption="Same document, cut three ways. Small chunks are precise; big chunks drag in clutter.",
        footer="My choice for now: 500 characters with 100 overlap — provisional until Week 2 tests it",
        notes="""
The tradeoff in one sentence: small chunks match precisely but may leave out
context the answer needs; big chunks carry their context along but dilute the
match, because one relevant sentence gets averaged in with paragraphs of
unrelated material.

That is the answer to your self-check question about why chunk size affects
quality.

Say "provisional" out loud. 500 with 100 overlap is defensible from what I have -
it held a complete thought without swallowing a whole table, and the overlap
rescued the fact from the previous slide. But the only real test is whether
answers are good, and that is next week. Every number I have so far is a stand-in
for that.

If asked about cost: the overlap means I store about 1.26 times my actual text,
because a quarter of what I save is a second copy. Irrelevant at this size.
        """,
    )

    # 8 -------------------------------------------------------------------
    deck.statement_slide(
        "Friday: I built search with no database at all",
        "The database is less accurate than my version",
        [
            "I embedded all 155 chunks into a plain Python list and searched it with a loop.",
            "My loop compares every chunk, so it cannot miss a match. It is exact.",
            "Chroma, which I add next week, deliberately skips most comparisons.",
            "It trades a small chance of missing a match for speed that holds up as notes grow.",
            "I assumed a real database meant better. It means faster, and slightly less reliable.",
        ],
        kicker="Fri",
        colour=GOOD,
        notes="""
This is your answer to "do I understand how a vector database finds similar
chunks". Most people answer by naming the algorithm. Answering by explaining that
the database is less accurate than brute force shows you actually understand what
it does.

Add: at 155 chunks my loop takes 15 milliseconds, so the database buys me nothing
on speed today. What it does buy me is that the index survives restarting - right
now every run re-embeds everything first, which takes 30 seconds before I can ask
anything.

That is a better reason to adopt it than speed, and it is the honest one.
        """,
    )

    # 9 -------------------------------------------------------------------
    deck.table_slide(
        "Asking a question my notes cannot answer",
        ["what I asked", "best score"],
        [
            ["\"What time does the corner shop close on Sundays?\"", "0.339"],
            ["The weakest score from a real, answerable question", "0.366"],
            ["Gap between them", "0.027"],
        ],
        highlight_rows={2},
        column_widths=[3.2, 1.0],
        kicker="Fri",
        caption="The search still returned five chunks. It always returns something.",
        footer="So cutting off low scores is necessary but not enough — Week 3's prompt must also allow \"I don't know\"",
        notes="""
This is your answer to the self-check item about handling a question with no good
answer, and it is the most useful thing I found all week.

Two points.

First, the search always returns results. There is no such thing as "no match" -
it hands back the closest five whatever you ask.

Second, the reason it scored 0.339: my question said Sundays, and the chunk it
found contains "Sun Oct 4" from a schedule. The model is right that those are
related in meaning. It has no idea whether being related actually answers the
question.

Now the conclusion. On Monday, related sentences scored 0.617 and unrelated ones
0.031, so a cut-off looked easy. Against a real set of notes the usable gap is
0.027 - twenty times narrower. With a few hundred chunks, something is always
somewhat close to anything you ask. So I need two defences: a score cut-off, and
a prompt that lets the model say it cannot find the answer.
        """,
    )

    # 10 ------------------------------------------------------------------
    deck.table_slide(
        "Where I stand, and what is left",
        ["item", "state"],
        [
            ["Embeddings working, similarity measured", "done"],
            ["Chunking with overlap, sizes compared", "done"],
            ["All chunks embedded and searchable", "done"],
            ["Add 5–10 of my own notes as the test set", "STILL TO DO"],
            ["Write my three explanations in my own words", "STILL TO DO"],
        ],
        highlight_rows={3, 4},
        column_widths=[3.0, 1.1],
        kicker="Status",
        caption="Next week: Chroma, retrieval, and tuning how many chunks to fetch per question.",
        footer="Both outstanding items are mine — nothing is blocked on anyone else",
        notes="""
Present this plainly, no softening.

Be honest about the test set: all my measurements so far ran against this
project's own documentation, because my notes folder is still empty. The numbers
are real but they describe the wrong documents. I need to re-run everything on my
own notes, and the README has to describe the set I actually ship.

The three explanations are: what an embedding is, why splitting documents
matters, and what semantic search means in plain language.

Close by handing him the decision from slide 3. "So the one thing I need from you
is the deadline - 4 October or 11 October?" That makes the meeting useful rather
than just a status report.
        """,
    )

    return deck


def main() -> int:
    output = Path(__file__).resolve().parent / "week1-review.pptx"
    deck = build()
    deck.save(output)

    slide_count = len(deck.presentation.slides)
    print(f"Wrote {output}")
    print(f"  {slide_count} slides, all with speaker notes")
    print("\nSlide 5 is intentionally unfinished: 'What an embedding is'.")
    print("Write it in your own words before presenting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
