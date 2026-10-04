"""
Generate the Week 1 review deck for the mentor check-in.

Run it:
    python presentation/build_deck.py

Output:
    presentation/review-deck.pptx

Ten slides. Every number comes from a real run recorded in
notes/learning-log.md - if a figure is not in that file, it does not belong
on a slide.

Needs python-pptx, deliberately kept out of requirements.txt since the tool
itself does not need it:

    .\\venv\\Scripts\\python.exe -m pip install python-pptx==1.0.2

Slide 5 is intentionally left blank. "What an embedding is" has to be in the
presenter's own words - it is on the mentor's self-check list, and borrowed
phrasing will not survive a follow-up question.

Design rules for this deck, learned by looking at rendered output rather than
guessing:
  - one idea per slide, five bullets maximum
  - content blocks are vertically centred in the body area; a table stranded at
    the top of a 16:9 slide leaves an awkward void underneath
  - table borders are stripped and replaced with row banding, because gridlines
    add visual noise without adding information
  - the speaker notes carry the detail, not the slide
"""

from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Inches, Pt

# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

MARGIN = Inches(0.9)
CONTENT_WIDTH = SLIDE_WIDTH - (2 * MARGIN)

# Vertical band the body content lives in, between the title rule and the footer.
BODY_TOP = Inches(2.0)
BODY_BOTTOM = Inches(6.35)
BODY_HEIGHT = BODY_BOTTOM - BODY_TOP

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

NAVY = RGBColor(0x0F, 0x2A, 0x44)       # headings, table headers, title slide
NAVY_SOFT = RGBColor(0x1C, 0x4E, 0x7A)  # kickers, accents
TEAL = RGBColor(0x2E, 0x8B, 0x84)       # positive emphasis
AMBER = RGBColor(0xB5, 0x6E, 0x0C)      # highlighted table rows
ALERT = RGBColor(0xB3, 0x26, 0x1E)      # failures, outstanding work
INK = RGBColor(0x1B, 0x1B, 0x1B)        # body text
MUTED = RGBColor(0x6B, 0x72, 0x80)      # captions, footers
RULE = RGBColor(0xDD, 0xE3, 0xE8)       # hairlines
ROW_ALT = RGBColor(0xF7, 0xF9, 0xFB)    # table banding
ROW_FLAG = RGBColor(0xFD, 0xF4, 0xE6)   # highlighted row fill
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

BODY_FONT = "Segoe UI"
MONO_FONT = "Consolas"

DECK_LABEL = "Ask My Docs  ·  Weeks 1–2"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _strip_cell_borders(cell) -> None:
    """Remove a table cell's gridlines.

    python-pptx applies a bordered default table style, which on a slide full of
    numbers reads as clutter. Row banding carries the structure instead, so the
    lines are explicitly set to no-fill.

    The four line elements must appear first inside `tcPr` and in the order
    left, right, top, bottom, so they are inserted in reverse at position zero.
    """
    tc_pr = cell._tc.get_or_add_tcPr()

    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        for existing in tc_pr.findall(qn(tag)):
            tc_pr.remove(existing)

    for tag in reversed(("a:lnL", "a:lnR", "a:lnT", "a:lnB")):
        tc_pr.insert(
            0,
            parse_xml(f'<{tag} {nsdecls("a")} w="0" cap="flat" cmpd="sng" algn="ctr"><a:noFill/></{tag}>'),
        )


def _rectangle(slide, left, top, width, height, colour) -> None:
    """A flat filled rectangle with no outline or shadow."""
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = colour
    shape.line.fill.background()
    shape.shadow.inherit = False


class Deck:
    """Builds the deck. Four slide layouts, one consistent frame around them."""

    def __init__(self) -> None:
        self.presentation = Presentation()
        self.presentation.slide_width = SLIDE_WIDTH
        self.presentation.slide_height = SLIDE_HEIGHT
        self._blank = self.presentation.slide_layouts[6]
        self._number = 0

    # -- frame -------------------------------------------------------------

    def _new(self, numbered: bool = True):
        slide = self.presentation.slides.add_slide(self._blank)
        if numbered:
            self._number += 1
            self._page_furniture(slide)
        return slide

    def _textbox(self, slide, left, top, width, height):
        box = slide.shapes.add_textbox(left, top, width, height)
        frame = box.text_frame
        frame.word_wrap = True
        return frame

    def _page_furniture(self, slide) -> None:
        """The thin accent stripe down the left edge, plus the page number."""
        _rectangle(slide, Emu(0), Emu(0), Inches(0.17), SLIDE_HEIGHT, NAVY)

        frame = self._textbox(slide, SLIDE_WIDTH - Inches(3.4), Inches(6.85), Inches(2.5), Inches(0.35))
        paragraph = frame.paragraphs[0]
        paragraph.alignment = PP_ALIGN.RIGHT
        paragraph.text = f"{DECK_LABEL}   ·   {self._number}"
        paragraph.font.size = Pt(10)
        paragraph.font.color.rgb = MUTED
        paragraph.font.name = BODY_FONT

    def _heading(self, slide, title: str, kicker: str | None = None) -> None:
        top = Inches(0.62)

        if kicker:
            # Small filled chip, which reads as a label rather than stray text.
            chip_width = Inches(0.11 * len(kicker) + 0.42)
            _rectangle(slide, MARGIN, top, chip_width, Inches(0.28), NAVY_SOFT)

            frame = self._textbox(slide, MARGIN, top - Inches(0.02), chip_width, Inches(0.32))
            frame.margin_left = frame.margin_right = 0
            paragraph = frame.paragraphs[0]
            paragraph.alignment = PP_ALIGN.CENTER
            paragraph.text = kicker.upper()
            paragraph.font.size = Pt(11)
            paragraph.font.bold = True
            paragraph.font.color.rgb = WHITE
            paragraph.font.name = BODY_FONT
            top = top + Inches(0.45)

        frame = self._textbox(slide, MARGIN, top, CONTENT_WIDTH, Inches(0.72))
        paragraph = frame.paragraphs[0]
        paragraph.text = title
        paragraph.font.size = Pt(31)
        paragraph.font.bold = True
        paragraph.font.color.rgb = NAVY
        paragraph.font.name = BODY_FONT

        # Short accent rule, not a full-width line - lighter on the eye.
        rule_top = top + Inches(0.76)
        _rectangle(slide, MARGIN, rule_top, Inches(1.5), Pt(3), NAVY_SOFT)
        _rectangle(slide, MARGIN + Inches(1.5), rule_top + Pt(1), CONTENT_WIDTH - Inches(1.5), Pt(1), RULE)

    def _footnote(self, slide, text: str) -> None:
        frame = self._textbox(slide, MARGIN, Inches(6.55), CONTENT_WIDTH - Inches(2.6), Inches(0.6))
        paragraph = frame.paragraphs[0]
        paragraph.text = text
        paragraph.font.size = Pt(12)
        paragraph.font.italic = True
        paragraph.font.color.rgb = MUTED
        paragraph.font.name = BODY_FONT

    def _notes(self, slide, notes: str) -> None:
        slide.notes_slide.notes_text_frame.text = notes.strip()

    # -- layouts -----------------------------------------------------------

    def title_slide(self, title: str, subtitle: str, meta: str, notes: str) -> None:
        slide = self._new(numbered=False)

        _rectangle(slide, Emu(0), Emu(0), SLIDE_WIDTH, SLIDE_HEIGHT, NAVY)
        _rectangle(slide, MARGIN, Inches(2.55), Inches(1.9), Pt(5), TEAL)

        frame = self._textbox(slide, MARGIN, Inches(2.85), CONTENT_WIDTH, Inches(1.1))
        paragraph = frame.paragraphs[0]
        paragraph.text = title
        paragraph.font.size = Pt(54)
        paragraph.font.bold = True
        paragraph.font.color.rgb = WHITE
        paragraph.font.name = BODY_FONT

        frame = self._textbox(slide, MARGIN, Inches(3.95), CONTENT_WIDTH, Inches(0.6))
        paragraph = frame.paragraphs[0]
        paragraph.text = subtitle
        paragraph.font.size = Pt(21)
        paragraph.font.color.rgb = RGBColor(0xAE, 0xC6, 0xD8)
        paragraph.font.name = BODY_FONT

        frame = self._textbox(slide, MARGIN, Inches(5.5), CONTENT_WIDTH, Inches(0.8))
        paragraph = frame.paragraphs[0]
        paragraph.text = meta
        paragraph.font.size = Pt(13)
        paragraph.font.color.rgb = RGBColor(0x7C, 0x97, 0xAB)
        paragraph.font.name = BODY_FONT

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
        self._heading(slide, title, kicker)

        frame = self._textbox(slide, MARGIN, BODY_TOP, CONTENT_WIDTH, BODY_HEIGHT)
        frame.vertical_anchor = MSO_ANCHOR.TOP

        for position, (level, text) in enumerate(bullets):
            paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
            paragraph.level = level

            bold = text.startswith("**")
            clean = text.removeprefix("**")

            if not clean.strip():
                paragraph.text = ""
                paragraph.font.size = Pt(9)
                continue

            marker = "" if level == 0 and bold else ("•   " if level == 0 else "–   ")
            paragraph.text = f"{marker}{clean}"
            paragraph.font.size = Pt(20 if level == 0 else 17)
            paragraph.font.bold = bold
            paragraph.font.color.rgb = NAVY if bold else (INK if level == 0 else MUTED)
            paragraph.font.name = BODY_FONT
            paragraph.space_after = Pt(15)

        if footer:
            self._footnote(slide, footer)

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
        self._heading(slide, title, kicker)
        highlight_rows = highlight_rows or set()

        header_height = Inches(0.52)
        row_height = Inches(0.52)
        table_height = header_height + (row_height * len(rows))
        caption_height = Inches(0.58) if caption else Emu(0)

        # Centre the caption and table together as one block. Centring the table
        # alone strands the caption a long way above it, so the two stop reading
        # as related.
        block_height = caption_height + table_height
        top = BODY_TOP + Emu(int(max(0, BODY_HEIGHT - block_height) / 2))

        if caption:
            frame = self._textbox(slide, MARGIN, top, CONTENT_WIDTH, Inches(0.4))
            paragraph = frame.paragraphs[0]
            paragraph.text = caption
            paragraph.font.size = Pt(16)
            paragraph.font.color.rgb = MUTED
            paragraph.font.name = BODY_FONT
            top = top + caption_height

        shape = slide.shapes.add_table(len(rows) + 1, len(headers), MARGIN, top, CONTENT_WIDTH, table_height)
        table = shape.table
        table.rows[0].height = header_height
        for index in range(1, len(rows) + 1):
            table.rows[index].height = row_height

        if column_widths:
            total = sum(column_widths)
            for index, share in enumerate(column_widths):
                table.columns[index].width = Emu(int(CONTENT_WIDTH * (share / total)))

        for column, label in enumerate(headers):
            cell = table.cell(0, column)
            cell.text = label
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = cell.margin_right = Inches(0.16)
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.font.size = Pt(14)
            paragraph.font.bold = True
            paragraph.font.color.rgb = WHITE
            paragraph.font.name = BODY_FONT
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY
            _strip_cell_borders(cell)

        for row_index, row in enumerate(rows, start=1):
            flagged = (row_index - 1) in highlight_rows
            banded = row_index % 2 == 0

            for column, value in enumerate(row):
                cell = table.cell(row_index, column)
                cell.text = value
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                cell.margin_left = cell.margin_right = Inches(0.16)

                paragraph = cell.text_frame.paragraphs[0]
                paragraph.font.size = Pt(15)
                paragraph.font.bold = flagged
                paragraph.font.name = MONO_FONT if column > 0 else BODY_FONT
                paragraph.font.color.rgb = AMBER if flagged else INK

                cell.fill.solid()
                cell.fill.fore_color.rgb = ROW_FLAG if flagged else (ROW_ALT if banded else WHITE)
                _strip_cell_borders(cell)

        if footer:
            self._footnote(slide, footer)

        self._notes(slide, notes)

    def section_slide(self, label: str, title: str, points: list[str], notes: str) -> None:
        """A navy divider announcing a new week.

        Two weeks of material in one deck needs an unmistakable boundary,
        otherwise the audience loses track of which half they are being shown.
        """
        slide = self._new()

        _rectangle(slide, Emu(0), Emu(0), SLIDE_WIDTH, SLIDE_HEIGHT, NAVY)
        _rectangle(slide, MARGIN, Inches(2.45), Inches(1.9), Pt(5), TEAL)

        frame = self._textbox(slide, MARGIN, Inches(1.95), CONTENT_WIDTH, Inches(0.4))
        paragraph = frame.paragraphs[0]
        paragraph.text = label.upper()
        paragraph.font.size = Pt(15)
        paragraph.font.bold = True
        paragraph.font.color.rgb = TEAL
        paragraph.font.name = BODY_FONT

        frame = self._textbox(slide, MARGIN, Inches(2.75), CONTENT_WIDTH, Inches(1.0))
        paragraph = frame.paragraphs[0]
        paragraph.text = title
        paragraph.font.size = Pt(40)
        paragraph.font.bold = True
        paragraph.font.color.rgb = WHITE
        paragraph.font.name = BODY_FONT

        frame = self._textbox(slide, MARGIN, Inches(4.05), CONTENT_WIDTH, Inches(1.8))
        for position, point in enumerate(points):
            paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
            paragraph.text = f"•   {point}"
            paragraph.font.size = Pt(18)
            paragraph.font.color.rgb = RGBColor(0xAE, 0xC6, 0xD8)
            paragraph.font.name = BODY_FONT
            paragraph.space_after = Pt(11)

        self._notes(slide, notes)

    def prose_slide(
        self,
        title: str,
        sentences: list[str],
        notes: str,
        kicker: str | None = None,
        footer: str | None = None,
        banner: str | None = None,
    ) -> None:
        """Plain sentences rather than bullets, for text that has to read as prose.

        `banner` draws an amber strip above the text - used to mark the slide as a
        draft, so there is no chance of it being mistaken for finished work.
        """
        slide = self._new()
        self._heading(slide, title, kicker)

        top = BODY_TOP

        if banner:
            _rectangle(slide, MARGIN, top, CONTENT_WIDTH, Inches(0.42), ROW_FLAG)
            _rectangle(slide, MARGIN, top, Pt(5), Inches(0.42), AMBER)

            frame = self._textbox(slide, MARGIN + Inches(0.22), top + Inches(0.04), CONTENT_WIDTH - Inches(0.4), Inches(0.34))
            paragraph = frame.paragraphs[0]
            paragraph.text = banner
            paragraph.font.size = Pt(14)
            paragraph.font.bold = True
            paragraph.font.color.rgb = AMBER
            paragraph.font.name = BODY_FONT
            top = top + Inches(0.72)

        frame = self._textbox(slide, MARGIN, top, CONTENT_WIDTH, BODY_BOTTOM - top)
        for position, sentence in enumerate(sentences):
            paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
            paragraph.text = sentence
            paragraph.font.size = Pt(20)
            paragraph.font.color.rgb = INK
            paragraph.font.name = BODY_FONT
            paragraph.space_after = Pt(16)

        if footer:
            self._footnote(slide, footer)

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
        self._heading(slide, title, kicker)

        accent = colour or TEAL

        # Tinted panel behind the headline so the claim carries visual weight.
        _rectangle(slide, MARGIN, BODY_TOP, CONTENT_WIDTH, Inches(1.05), ROW_ALT)
        _rectangle(slide, MARGIN, BODY_TOP, Pt(5), Inches(1.05), accent)

        frame = self._textbox(slide, MARGIN + Inches(0.28), BODY_TOP + Inches(0.16), CONTENT_WIDTH - Inches(0.5), Inches(0.8))
        paragraph = frame.paragraphs[0]
        paragraph.text = headline
        paragraph.font.size = Pt(32)
        paragraph.font.bold = True
        paragraph.font.color.rgb = accent
        paragraph.font.name = BODY_FONT

        frame = self._textbox(slide, MARGIN, BODY_TOP + Inches(1.4), CONTENT_WIDTH, Inches(2.8))
        for position, line in enumerate(support):
            paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
            paragraph.text = line
            paragraph.font.size = Pt(18)
            paragraph.font.color.rgb = INK
            paragraph.font.name = BODY_FONT
            paragraph.space_after = Pt(14)

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
        "Weeks 1 and 2 review — embeddings, chunking, retrieval",
        "21 Sep – 4 Oct 2026     ·     A question-answering tool over my own notes, built without a framework",
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
            (1, "chunk   →   embed   →   store   →   retrieve   →   generate"),
            (0, "**Week 1 delivered the first two, plus a working search"),
            (0, "No LangChain or LlamaIndex — your brief asks for it built manually"),
        ],
        kicker="Overview",
        footer="Repo: ask-my-docs  ·  4 commits  ·  Python, a free local embedding model, no API key needed yet",
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
    deck.section_slide(
        "Week 1  ·  21–27 September",
        "Embeddings and chunking",
        [
            "Turn text into something a computer can compare",
            "Cut documents into pieces small enough to be useful",
            "Search them, with no database involved yet",
        ],
        notes="""
Short pause here. "First week was the two stages that come before anything
clever: turning text into numbers, and deciding how to cut documents up."

Four slides in this section.
        """,
    )

    # 5 -------------------------------------------------------------------
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
        kicker="W1 · Embeddings",
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
    deck.prose_slide(
        "What an embedding is",
        [
            "An embedding is what you get when a model reads text and turns it into a position "
            "on a map of meaning.",
            "Text that means similar things lands in nearby positions, even when the actual "
            "words are completely different.",
            "The model worked out the layout of that map during training, so nobody chose what "
            "each number stands for — and one number on its own tells you nothing.",
            "What carries the information is how close two pieces of text end up to each other.",
        ],
        kicker="W1 · Embeddings",
        banner="DRAFT — rewrite this in my own voice before presenting, then delete this strip",
        footer="Evidence: 7 characters and 196 characters both produce exactly 384 numbers; two sentences with no shared words scored 0.618",
        notes="""
THIS IS A DRAFT, NOT YOUR ANSWER. Read it, then say the same idea your way and
replace the text. Ten minutes with it will do.

Why it must be yours: your mentor's self-check asks you to explain an embedding
without falling back on the word "vector", and he will ask a follow-up. The usual
ones are "so what makes two things land near each other?" and "why 384 numbers?"
Wording you did not write is exactly where those questions land badly.

Answers worth having ready:
- What makes them land near each other? The model was trained on huge amounts of
  text and learned which words and phrases turn up in similar situations. Nobody
  programmed the positions.
- Why 384? That is just the size this particular model outputs. A bigger model
  uses more numbers and captures finer distinctions, at more cost. What matters is
  that the count never changes with the length of the input.
- Is it like a search index? No. A search index stores words. This stores a
  position, so two passages can be close together with no words in common.

If you have not rewritten it by the morning, say so honestly - "this is my
current phrasing, I'm still tightening it" - and then demo the script. Showing
the 0.618 score live proves the understanding better than a polished sentence.
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
        kicker="W1 · Chunking",
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
        kicker="W1 · Chunking",
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
        "I built search with no database at all",
        "The database is less accurate than my version",
        [
            "I embedded all 155 chunks into a plain Python list and searched it with a loop.",
            "My loop compares every chunk, so it cannot miss a match. It is exact.",
            "Chroma, which I add next week, deliberately skips most comparisons.",
            "It trades a small chance of missing a match for speed that holds up as notes grow.",
            "I assumed a real database meant better. It means faster, and slightly less reliable.",
        ],
        kicker="W1 · Search",
        colour=TEAL,
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
        kicker="W1 · Edge case",
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

    # 11 ------------------------------------------------------------------
    deck.section_slide(
        "Week 2  ·  28 September – 4 October",
        "Vector database and retrieval",
        [
            "Swap my Python list for a real database that survives restarts",
            "Turn a question into the passages that answer it",
            "Decide how many passages to fetch — by measuring, not guessing",
        ],
        notes="""
"Week two replaced the list with a real database, and built the retrieval step.
Three of the slides here resolve questions the first week left open."

That framing is worth saying out loud - it shows the weeks connect rather than
being two separate piles of work.
        """,
    )

    # 12 ------------------------------------------------------------------
    deck.bullets_slide(
        "What the database actually changed",
        [
            (0, "**171 chunks now live in a local database on disk, not in memory"),
            (0, "**The real win is not speed — it is that the index survives restarting"),
            (1, "Before: every run re-embedded all my notes first, about a minute of waiting"),
            (1, "Now: that cost is paid once, when my notes change"),
            (0, "**I had to set the distance measure by hand"),
            (1, "Chroma defaults to a different one that would not match Week 1's scores"),
            (0, "It also refuses to answer if the notes were indexed by a different model"),
        ],
        kicker="W2 · Database",
        footer="That last guard matters: querying with the wrong model returns confident nonsense and no error at all",
        notes="""
The honest framing: I did not adopt a database because my search was too slow. At
171 chunks my loop took 15 milliseconds. I adopted it because the index persists,
and because the brief asks for one.

On the distance measure, if he asks: Chroma's default is squared L2. I measured
it - for two unrelated directions it reports 2.0 where cosine reports 1.0. For my
model both rank the same way, so nothing would have looked broken. It would only
have bitten me later if I switched models. One line to remove the risk.

On the model guard: this is the nastiest failure in the whole pipeline, because
there is no symptom. Embeddings from two models are not comparable, but querying
across them raises nothing - you just get well-formed, meaningless results. So the
database records which model built it and refuses a mismatch.
        """,
    )

    # 13 ------------------------------------------------------------------
    deck.table_slide(
        "Does the shortcut cost accuracy? I measured it",
        ["question", "database", "my Week 1 loop", "same answers?"],
        [
            ["\"Why does overlap matter?\"", "11.6ms", "13.1ms", "5 of 5"],
            ["\"How many results should I fetch?\"", "3.5ms", "14.9ms", "5 of 5"],
        ],
        column_widths=[2.6, 0.9, 1.1, 1.0],
        kicker="W2 · Accuracy",
        caption="Week 1 said the database would be approximate. This is the check.",
        footer="100% agreement — but expected at this size, not proof that the shortcut is free",
        notes="""
This closes the loop on the Week 1 slide where I said the database would be less
accurate than my loop.

It agreed with my loop on every single result. But be careful how you present
that, because it is not the win it looks like: at 171 chunks the graph it walks is
small enough to reach the right answers anyway. The approximation only starts
costing accuracy when the data is large enough that it has to skip meaningful
parts. So this confirms I wired it up correctly - it does not prove approximate
search is free.

One more detail worth mentioning: the scores it returned matched my hand-written
calculation to four decimal places - 0.6690, 0.6070, 0.5247 on the same chunks.
Two independent implementations agreeing exactly is good evidence that neither my
arithmetic nor my configuration is wrong.
        """,
    )

    # 14 ------------------------------------------------------------------
    deck.table_slide(
        "How many passages should I fetch?",
        ["chunks fetched", "average relevance", "text sent", "wasted slots"],
        [
            ["3", "0.4296", "1,380 chars", "0.0"],
            ["5", "0.4034", "2,211 chars", "0.5"],
            ["10", "0.3681", "4,636 chars", "2.8"],
        ],
        highlight_rows={1},
        column_widths=[1.3, 1.4, 1.2, 1.1],
        kicker="W2 · Tuning",
        caption="Averaged over four questions. \"Wasted slots\" are neighbouring chunks returned twice.",
        footer="I chose 5 — still provisional until I test real answer quality in Week 3",
        notes="""
This is the "more context versus more noise" tradeoff with numbers on it.

Going from 3 to 10 costs 3.4 times the text for a 0.06 drop in average relevance.

The wasted slots column is the interesting one, and it connects back to chunking.
Because consecutive chunks overlap by 100 characters, sometimes two neighbours
both come back for the same question - so I am sending the model the same text
twice. At 10, nearly 3 of the 10 slots went on duplicates.

Why 5 and not 3: at 3 I was pulling from only two and a half documents on average,
which makes it too easy to miss a detail that fell just outside. 5 gets me three
sources and about 2,200 characters, which is a comfortable prompt size.
        """,
    )

    # 15 ------------------------------------------------------------------
    deck.table_slide(
        "The idea that did not survive testing",
        ["cut-off", "Q1", "Q2", "Q3", "Q4", "bad question"],
        [
            ["none", "5", "5", "5", "5", "5"],
            ["0.30", "5", "3", "5", "5", "2"],
            ["0.35", "5", "2", "2", "4", "0"],
            ["0.40", "5", "0", "0", "1", "0"],
        ],
        highlight_rows={2, 3},
        column_widths=[1.1, 0.6, 0.6, 0.6, 0.6, 1.2],
        kicker="W2 · Correction",
        caption="Week 1 suggested ignoring low scores. Numbers are passages kept per question.",
        footer="The cut-off that silences the bad question also strips real answers from Q2 and Q3",
        notes="""
This is the slide I would most want to be asked about, because it is where I
corrected my own mistake.

Week 1 ended with "just ignore anything below a certain score". Week 2 tested it
properly and it does not work. Read the 0.35 row: the bad question is finally
silenced, but questions 2 and 3 drop to two passages. At 0.40 they return nothing
at all, for questions my notes genuinely answer.

Be honest about the process here: my first version of this test used only question
1, which scores high on everything, and a 0.35 cut-off looked perfectly safe.
Sweeping all four is what exposed the conflict. A test built around the best case
is worse than no test, because it gives you false confidence.

Why it happens: the scores are not comparable between questions. A question worded
the way my notes are written scores high throughout; one worded differently scores
low throughout, even when its best match is exactly right.

So the cut-off ships switched off, and Week 3's prompt has to be the real defence -
the model needs permission to say it cannot find the answer.
        """,
    )

    # 16 ------------------------------------------------------------------
    deck.table_slide(
        "Where I stand after two weeks",
        ["item", "state"],
        [
            ["Embeddings, similarity, chunking with overlap", "done"],
            ["Chunk size and top-k chosen from measurements", "done"],
            ["Real database, retrieval, results logged to file", "done"],
            ["Add 5–10 of my own notes as the test set", "STILL TO DO"],
            ["Write my explanations in my own words", "STILL TO DO"],
            ["Week 3: generate answers, cite sources, README, video", "to come"],
        ],
        highlight_rows={3, 4},
        column_widths=[3.2, 1.1],
        kicker="Status",
        caption="Everything measured so far describes a stand-in dataset, not my own notes.",
        footer="Outstanding items are mine — and I still need your answer on the deadline",
        notes="""
Present this plainly, no softening.

The stand-in dataset is the thing to own up to. My notes folder is still empty, so
I measured against this project's own documentation. The numbers are real but they
describe the wrong documents, and I know it - the chunk count drifted from 159 to
171 during the week purely because I kept editing those files. Same code,
different numbers. That is exactly why a fixed dataset matters, and it is my first
job before Week 3.

Then close on the deadline question from slide 3. "So the one thing I need from
you is whether the deadline is 4 or 11 October." That makes the meeting useful
rather than just a report.
        """,
    )

    return deck


def main() -> int:
    output = Path(__file__).resolve().parent / "review-deck.pptx"
    deck = build()
    deck.save(output)

    print(f"Wrote {output}")
    print(f"  {len(deck.presentation.slides)} slides, all with speaker notes")
    print("\nSlide 6 carries a DRAFT strip: 'What an embedding is'.")
    print("Put it in your own words, then delete the strip.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
