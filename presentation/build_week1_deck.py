"""
Generate the Week 1 review deck for the mentor check-in.

Run it:
    python presentation/build_week1_deck.py

Output:
    presentation/week1-review.pptx

Not part of the RAG pipeline. Needs python-pptx, which is deliberately kept out
of requirements.txt - the tool itself does not need it, and a reviewer cloning
the repo should not have to install it to run the project:

    .\\venv\\Scripts\\python.exe -m pip install python-pptx==1.0.2

Every figure in this deck comes from a real run recorded in
notes/week1-learning-log.md. If a number here is not in that file, it does not
belong in the deck.

One slide is deliberately left blank: "What an embedding is". That explanation
has to be in the presenter's own words - it is on the mentor's self-check list,
and borrowed phrasing will not survive a follow-up question.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
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
    """Thin wrapper over python-pptx for the handful of layouts this deck needs."""

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
        """Draw the slide title and return the vertical offset to continue from."""
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

        return line_top + Inches(0.3)

    def _notes(self, slide, notes: str) -> None:
        slide.notes_slide.notes_text_frame.text = notes.strip()

    # -- slide types -------------------------------------------------------

    def title_slide(self, title: str, subtitle: str, meta: str, notes: str) -> None:
        slide = self._new()

        band = slide.shapes.add_shape(1, Emu(0), Inches(2.25), SLIDE_WIDTH, Inches(2.1))
        band.fill.solid()
        band.fill.fore_color.rgb = BAND
        band.line.fill.background()
        band.shadow.inherit = False

        frame = self._textbox(slide, MARGIN, Inches(2.5), CONTENT_WIDTH, Inches(1.0))
        run = frame.paragraphs[0]
        run.text = title
        run.font.size = Pt(46)
        run.font.bold = True
        run.font.color.rgb = INK
        run.font.name = BODY_FONT

        frame = self._textbox(slide, MARGIN, Inches(3.45), CONTENT_WIDTH, Inches(0.6))
        run = frame.paragraphs[0]
        run.text = subtitle
        run.font.size = Pt(20)
        run.font.color.rgb = ACCENT
        run.font.name = BODY_FONT

        frame = self._textbox(slide, MARGIN, Inches(4.75), CONTENT_WIDTH, Inches(0.6))
        run = frame.paragraphs[0]
        run.text = meta
        run.font.size = Pt(14)
        run.font.color.rgb = MUTED
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
        """Bullets as (indent_level, text). Text starting with '**' renders bold."""
        slide = self._new()
        top = self._heading(slide, title, kicker)

        frame = self._textbox(slide, MARGIN, top, CONTENT_WIDTH, Inches(4.4))

        for position, (level, text) in enumerate(bullets):
            paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
            paragraph.level = level

            bold = text.startswith("**")
            clean = text.removeprefix("**")

            if not clean.strip():
                # Deliberate spacer: no text, and crucially no bullet glyph.
                paragraph.text = ""
                paragraph.font.size = Pt(10)
                continue

            marker = "" if level == 0 and bold else ("•  " if level == 0 else "–  ")
            paragraph.text = f"{marker}{clean}"
            paragraph.font.size = Pt(19 if level == 0 else 16)
            paragraph.font.bold = bold
            paragraph.font.color.rgb = INK if level == 0 else MUTED
            paragraph.font.name = BODY_FONT
            paragraph.space_after = Pt(11)

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
    ) -> None:
        slide = self._new()
        top = self._heading(slide, title, kicker)
        highlight_rows = highlight_rows or set()

        row_count = len(rows) + 1
        height = Inches(0.42) * row_count
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
            paragraph.font.size = Pt(14)
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
                paragraph.font.size = Pt(13)
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
        """One large claim, with smaller supporting lines beneath it."""
        slide = self._new()
        top = self._heading(slide, title, kicker)

        frame = self._textbox(slide, MARGIN, top + Inches(0.2), CONTENT_WIDTH, Inches(0.9))
        run = frame.paragraphs[0]
        run.text = headline
        run.font.size = Pt(34)
        run.font.bold = True
        run.font.color.rgb = colour or ALERT
        run.font.name = BODY_FONT

        frame = self._textbox(slide, MARGIN, top + Inches(1.35), CONTENT_WIDTH, Inches(3.4))
        for position, line in enumerate(support):
            paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
            paragraph.text = line
            paragraph.font.size = Pt(17)
            paragraph.font.color.rgb = INK
            paragraph.font.name = BODY_FONT
            paragraph.space_after = Pt(12)

        self._notes(slide, notes)

    def _footer(self, slide, text: str) -> None:
        frame = self._textbox(slide, MARGIN, Inches(6.62), CONTENT_WIDTH, Inches(0.5))
        run = frame.paragraphs[0]
        run.text = text
        run.font.size = Pt(12)
        run.font.italic = True
        run.font.color.rgb = MUTED
        run.font.name = BODY_FONT

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.presentation.save(str(path))


# ---------------------------------------------------------------------------
# The deck
# ---------------------------------------------------------------------------


def build() -> Deck:
    deck = Deck()

    deck.title_slide(
        "Ask My Docs",
        "Project 2 · Week 1 review · Embeddings & chunking foundations",
        "Week 1: Mon 21 – Sun 27 Sep 2026   |   Building the RAG pipeline manually, no framework",
        notes="""
Keep this short. One sentence on what the project is, then move.

"Week 1 was about the two stages that come before anything clever happens:
turning text into numbers, and deciding how to cut documents up. I have working
code for both, and three results that changed how I plan to build weeks 2 and 3."

Then say what is NOT done, up front, so it doesn't look like you're hiding it:
the test dataset and three written explanations. Volunteering that early buys
credibility for everything after it.
        """,
    )

    deck.bullets_slide(
        "What I'm building",
        [
            (0, "A tool that answers questions about my own notes, using only passages retrieved from them"),
            (0, "**Five stages, each written by hand:"),
            (1, "chunk → embed → store → retrieve → generate"),
            (0, "No LangChain, no LlamaIndex — the brief asks for the pipeline built manually"),
            (1, "Building it once by hand is what makes every future shortcut make sense"),
            (0, "Week 1 delivers the first two stages, plus a working search with no database in it"),
        ],
        kicker="Context",
        footer="Repo: ask-my-docs · 4 commits · Python 3.12, local embedding model, no API key needed yet",
        notes="""
The "no framework" point matters to your mentor - it's in his brief. Say it
explicitly.

If asked why no framework: a framework would have done all of week 1 in about
four lines, and I would not be able to explain any of them. The cost of the
manual version is a week; the benefit is that I now know what the four lines do.
        """,
    )

    deck.bullets_slide(
        "One correction before I start",
        [
            (0, "**The brief's dates are off by a week"),
            (1, "It says the project starts Mon 14 Sep and is due Sun 4 Oct"),
            (1, "Week 1 actually began Mon 21 Sep"),
            (0, "**Shifting each week forward by one:"),
            (1, "Week 1 — 21–27 Sep · embeddings & chunking  (this review)"),
            (1, "Week 2 — 28 Sep–4 Oct · vector database & retrieval"),
            (1, "Week 3 — 5–11 Oct · generation, citations, submission"),
            (0, "That puts the printed 4 Oct deadline at the end of Week 2 — I need a decision on which date holds"),
        ],
        kicker="Question for you",
        footer="Your brief says adjusting scope is easy in week 1 and hard on the final Sunday — hence raising it now",
        notes="""
Raise this first, not last. If he holds 4 October firm you lose a whole week and
week 3 has to be cut down, and you both need to know that today.

Have a fallback ready so you're not just presenting a problem: if 4 Oct is firm,
the cut is the optional extras - citations stay, the no-answer handling stays,
the polish and demo video stay. What goes is any top-k tuning beyond a single
comparison.
        """,
    )

    # ---------------- Mon-Tue ----------------

    deck.bullets_slide(
        "Embeddings: what I built",
        [
            (0, "**Provider chosen: Sentence Transformers, all-MiniLM-L6-v2, 384 dimensions, running locally"),
            (0, "Free, no API key, works offline after a one-time 90 MB download"),
            (0, "**Why local rather than the OpenAI API — and this is a project-management reason, not a technical one:"),
            (1, "Wednesday needed the whole corpus re-embedded repeatedly to compare chunk sizes"),
            (1, "Week 2 will do it again for top-k"),
            (1, "Per-call billing makes you hesitate to re-run an experiment, and hesitation is what this project cannot afford"),
            (0, "OpenAI embeddings are wired up behind one setting, so switching is a one-line change"),
        ],
        kicker="Mon–Tue",
        footer="src/embedder.py — nothing else in the project knows which backend is active",
        notes="""
The reasoning is the interesting part, not the choice. Anyone can pick a model;
explaining that you picked it to keep experiments free is the sign you thought
about the week ahead.

If he asks about quality: MiniLM is smaller and weaker than text-embedding-3-small.
For a few hundred chunks of my own notes that has not been the limiting factor -
chunk size and top-k matter far more. And I can switch in one line to test that
claim.
        """,
    )

    deck.table_slide(
        "Embeddings: the measurement",
        ["comparison", "cosine similarity"],
        [
            ["A1 vs A2  — sourdough / loaf from scratch", "0.6178"],
            ["A1 vs A3  — sourdough / weekend baking", "0.6082"],
            ["A2 vs A3  — loaf from scratch / weekend baking", "0.6254"],
            ["B1 vs B2  — tax deadline / Saturn's moons", "-0.0190"],
            ["B1 vs B3  — tax deadline / router reboot", "0.1112"],
            ["B2 vs B3  — Saturn's moons / router reboot", "0.0009"],
            ["Group A average (related)", "0.6172"],
            ["Group B average (unrelated)", "0.0310"],
        ],
        highlight_rows={6, 7},
        column_widths=[3.2, 1.0],
        kicker="Mon–Tue",
        footer="Cosine similarity written by hand in src/similarity.py — dot product ÷ both magnitudes, no library shortcut",
        notes="""
Walk one row, not all eight. Best choice is A1 vs A2.

"I bake sourdough bread every weekend" against "Most Saturdays you will find me
making a loaf from scratch". Those two share no useful keywords at all. Keyword
search scores that pair near zero. The model gave it 0.62, purely from meaning.

If he asks why you hand-wrote cosine similarity: the brief says build manually,
and I wanted to understand why you divide by both magnitudes - it cancels length
out, so a short sentence and a long paragraph that mean the same thing still
score as similar.
        """,
    )

    deck.statement_slide(
        "The result that reframed my thinking",
        "0.62, not 0.95",
        [
            "Related sentences scored 0.617. I expected \"similar\" to mean \"close to 1.0\".",
            "What makes 0.617 meaningful is the 0.031 baseline sitting underneath it.",
            "A sensible-looking filter — \"keep anything above 0.8\" — would have discarded every correct match.",
            "So: rank candidates against each other. Never filter on a threshold that feels right.",
            "These scores are only comparable within one model. Change the model and every number changes.",
        ],
        kicker="Mon–Tue",
        colour=ACCENT,
        notes="""
This is your strongest week-1 slide. It shows you drew a design conclusion from
a measurement rather than just reporting the measurement.

It also sets up Friday, where this conclusion gets tested against a real corpus
and turns out to be even more important than it looks here.
        """,
    )

    deck.bullets_slide(
        "What an embedding is — in my own words",
        [
            (0, "[ TO WRITE BEFORE PRESENTING ]"),
            (1, "Your self-check asks me to explain this without using \"vector\" as a cop-out"),
            (1, "Constraint I'm holding myself to: explainable to someone who has never seen the word"),
            (0, ""),
            (0, "Evidence I can draw on:"),
            (1, "A 7-character input and a 196-character input both produce exactly 384 numbers"),
            (1, "Two sentences with no shared keywords scored 0.62 against each other"),
            (1, "The numbers mean nothing on their own — only their positions relative to each other"),
        ],
        kicker="Mon–Tue",
        footer="Deliberately left blank — this one has to be mine, or it will not survive your follow-up question",
        notes="""
FILL THIS IN YOURSELF BEFORE PRESENTING. Do not present the slide as-is.

The bullets underneath are the raw material, not the answer. Write three or four
sentences in your own voice and replace the placeholder line. If you present this
blank, say plainly that you are still working on the phrasing rather than
pretending the slide is finished.

A rough shape to react to, not to copy: an embedding model reads text and returns
coordinates on a map of meaning, where things that mean similar things sit near
each other. Find your own way to say it - he will ask a follow-up, and the
follow-up is where borrowed wording falls apart.
        """,
    )

    # ---------------- Wed-Thu ----------------

    deck.bullets_slide(
        "Chunking: what I built",
        [
            (0, "**src/loader.py — reads .md, .txt and .pdf from a folder, including subfolders"),
            (1, "PDFs become one document per page, so page numbers survive into citations later"),
            (1, "One unreadable file warns by name and is skipped; it never aborts the run"),
            (0, "**src/chunker.py — fixed-size character windows with overlap"),
            (1, "Cut points scan backwards a short distance for a paragraph break, then a sentence end, then any space"),
            (1, "So chunks never split a word in half, and prefer to break between ideas"),
            (0, "Each chunk carries its source, index, character offset and page — citations need all four"),
        ],
        kicker="Wed–Thu",
        footer="Verified on an 11-page PDF: 11 pages → 11 documents → 21 chunks, cited as gen-ai-brochure.pdf#1 (p.2)",
        notes="""
Keep this slide brief - it's the "yes, the code exists" slide. The next one is
the one worth spending time on.

If he asks why characters rather than tokens: characters are directly observable,
I can look at a 500-character chunk and see exactly what is in it. Token-based
chunking is the better production choice because context limits are counted in
tokens, and I note that in the README.
        """,
    )

    deck.table_slide(
        "The failure that chunk tuning exists to prevent",
        ["configuration", "chunks", "is the fact retrievable?"],
        [
            ["500 size / 0 overlap, hard cuts", "2", "NO CHUNK CONTAINS IT"],
            ["500 / 0, softened boundaries", "2", "yes — 1 chunk"],
            ["500 / 100, softened boundaries", "3", "yes — 1 chunk"],
        ],
        highlight_rows={0},
        column_widths=[2.4, 0.7, 1.6],
        kicker="Wed–Thu",
        footer="A 73-character fact planted at chars 460–533 of a test document, straddling the 500 boundary",
        notes="""
This is the centrepiece of Wednesday. Spend real time here.

Row 1: the fact is present in the document, split across two chunks, and
therefore whole in neither. No question can retrieve it. Each half is too
incomplete to score well. And nothing in the system reports a problem - the
answers just quietly get worse. That is the worst kind of bug.

Row 2 versus row 3 is the subtle bit, and the part I'd lead with if he pushes:
row 2 fixes it by luck, because the splitter happened to find a sentence break
before the fact. That only works when your text has punctuation near the
boundary. Row 3 fixes it on purpose. Overlap does not depend on the text
cooperating.
        """,
    )

    deck.table_slide(
        "Chunk size and overlap: what each setting costs",
        ["size", "overlap", "chunks", "mean len", "min", "stored chars", "duplication"],
        [
            ["300", "0", "199", "279.4", "50", "55,598", "1.00x"],
            ["300", "60", "252", "279.0", "72", "70,298", "1.26x"],
            ["500", "0", "124", "448.4", "23", "55,598", "1.00x"],
            ["500", "100", "155", "454.2", "112", "70,398", "1.27x"],
            ["800", "160", "96", "727.5", "292", "69,838", "1.26x"],
            ["1500", "300", "50", "1370.0", "348", "68,498", "1.23x"],
        ],
        highlight_rows={3},
        column_widths=[0.6, 0.7, 0.7, 0.9, 0.6, 1.0, 1.0],
        kicker="Wed–Thu",
        footer="Corpus: 7 markdown files, 55,598 characters — an interim stand-in, not my final dataset",
        notes="""
Three things to point at, then move on. Don't read the table.

One: at zero overlap, characters in equals characters out exactly - 55,598 both
sides. That's a sanity check that the splitter neither loses nor invents text.

Two: 20% overlap consistently costs about 1.26x storage. A quarter of what I
embed is a duplicate of something already stored.

Three: the min column at 500/0 is 23 characters. That's a leftover file tail
carrying almost no meaning. If my notes include lots of short files I'll get lots
of near-useless tail chunks - something to watch for when I swap in the real
dataset.
        """,
    )

    deck.bullets_slide(
        "Why chunk size changes answer quality",
        [
            (0, "**One passage from a 15,500-character file, chunked three ways:"),
            (1, "300 chars → one tight idea, nothing else"),
            (1, "500 chars → that idea, plus the start of an unrelated table"),
            (1, "1500 chars → the idea, the whole table, and two further sections"),
            (0, "**Small chunks match precisely but may drop the context the answer needs"),
            (0, "**Large chunks carry context along and dilute the match"),
            (1, "One relevant sentence, averaged in with paragraphs of unrelated material"),
            (0, "No universally correct value — it depends on how the notes are written"),
        ],
        kicker="Wed–Thu",
        footer="Provisional: CHUNK_SIZE=500, CHUNK_OVERLAP=100 — held provisionally until Week 2 tests it with real questions",
        notes="""
This is the answer to his self-check question "can I explain why chunk size
affects the quality of retrieved context". Say the tradeoff out loud: precision
versus context.

Say "provisional" deliberately. 500/100 is defensible from the evidence I have -
it held a complete thought without swallowing an unrelated table, and 100 of
overlap rescued the planted fact. But retrieval quality against real questions is
the only test that matters, and that's next week. Every number I have so far is a
proxy.
        """,
    )

    # ---------------- Friday ----------------

    deck.bullets_slide(
        "Friday: a search engine with no database in it",
        [
            (0, "**Embedded every chunk and kept the results in a plain Python list"),
            (1, "155 chunks · 384 numbers each · 59,520 numbers · 29.9s to embed on CPU"),
            (1, "Each entry holds three things: the numbers, the chunk text, its source"),
            (0, "**Search is a for loop over the cosine similarity function from Monday"),
            (1, "Embedding the question: ~27ms — a fixed cost, does not grow"),
            (1, "Scanning all 155 chunks: ~15ms — this is the part that grows"),
            (0, "Deliberately built before touching Chroma, so I know exactly which loop it replaces"),
        ],
        kicker="Fri",
        footer="A vector database stores the same three things — the only difference is how it searches them",
        notes="""
The point of Friday is not the code, it's what the code taught you. Set that up
here and deliver it on the next slide.

Worth mentioning: my first version timed question-embedding and store-scanning
together and divided by chunk count. Embedding is a fixed cost - 65% of the total
at this size - so that inflated the per-comparison figure about 3x and made my
scaling projection wrong. Mixing a fixed cost into a per-item measurement makes
small corpora look slow and large ones look fast.
        """,
    )

    deck.statement_slide(
        "What the database actually buys us",
        "It is less correct, and far faster",
        [
            "My for loop compares every chunk, so it cannot miss a match. It is exact by construction.",
            "Chroma's index is approximate — it deliberately skips most comparisons.",
            "It trades a small chance of missing a true match for search time that barely grows with corpus size.",
            "Projected scan on my loop: 15ms now · 1.5s at 100x · 147s at 10,000x.",
            "I had assumed \"real database\" meant \"better\". It means a different point on a speed/accuracy trade.",
        ],
        kicker="Fri",
        colour=GOOD,
        notes="""
This is your answer to "do I understand how a vector database finds similar
chunks". Most people answer that question by naming HNSW. Answering it by saying
the database is less accurate than a brute-force scan shows you actually
understand the mechanism.

At 155 chunks the loop is instant and Chroma would be pure overhead. I'm adopting
it next week because the brief asks for it and because persistence across restarts
is genuinely useful - not because my search was too slow.
        """,
    )

    deck.table_slide(
        "Testing a question with no answer in the notes",
        ["question", "best score", "what it matched"],
        [
            ["\"What time does the corner shop close on Sundays?\"", "0.3386", "a schedule containing \"Sun Oct 4\""],
            ["Lowest score from a legitimate question", "0.3655", "a genuinely relevant passage"],
            ["Margin between them", "0.0269", "≈ 20x narrower than Monday suggested"],
        ],
        highlight_rows={2},
        column_widths=[2.6, 0.8, 1.8],
        kicker="Fri",
        footer="Monday's clean 0.617-vs-0.031 gap does not survive contact with a real corpus",
        notes="""
This is the most useful thing I found all week, and it directly answers his
self-check item about handling a question with no good answer.

The scan still returned three chunks. A linear scan always returns its top-k -
there is no such thing as "no result".

The top hit scored 0.34 because the question says Sundays and that chunk contains
Sun Oct 4. The model is doing its job: those really are related in meaning. It has
no concept of whether the relation answers the question.

Then the conclusion: a score floor does separate good from bad here, but by only
0.027. With a few hundred chunks, something is always somewhat close to anything.
So a floor is necessary but not sufficient - the prompt in week 3 has to give the
model permission to refuse. Two independent defences, because neither is reliable
alone.
        """,
    )

    deck.bullets_slide(
        "Semantic search versus keyword search",
        [
            (0, "Question deliberately phrased to avoid the vocabulary of its own answer:"),
            (1, "\"Why would splitting a document in the wrong place lose information?\""),
            (0, "**Overlap between the two top-3 result lists: 0 of 3"),
            (0, "**Every keyword result tied at exactly 0.2857"),
            (1, "It found the same shallow word-hit count everywhere and could not rank between them"),
            (1, "Its ordering was arbitrary; the semantic scores were distinct and ordered"),
            (0, "Honest limit: disagreeing proves they rank differently, not that one ranked better"),
            (1, "Judging that means reading the chunks — worth redoing on my own notes"),
        ],
        kicker="Fri",
        footer="The keyword baseline exists for contrast only — it is not part of the pipeline",
        notes="""
The tied scores are the detail worth pointing out. It's not that keyword search
ranked badly - it couldn't rank at all. Three chunks, identical score, arbitrary
order.

Include the honest limit. If you claim semantic search "won" and he asks you to
justify it from these three results, you can't - the corpus is specification
boilerplate, not notes. Saying so first is stronger than being caught out.
        """,
    )

    # ---------------- Wrap ----------------

    deck.bullets_slide(
        "Two bugs found by actually running it",
        [
            (0, "**A single → character crashed the script"),
            (1, "The Windows console defaults to cp1252 and cannot encode arrows, em dashes or curly quotes"),
            (1, "The chunking was correct — the crash came from trying to display the result"),
            (1, "Fixed by switching output to UTF-8 with a replacement character as fallback"),
            (1, "This would have hit my own notes on the very first run"),
            (0, "**An infinite-loop risk in the boundary softener"),
            (1, "Cutting backwards for a natural break could return a point before the overlap ended"),
            (1, "Guarded, then verified on a 2,000-character string containing no whitespace at all"),
        ],
        kicker="Fri",
        footer="Also verified: overlap ≥ chunk size rejected · missing folder · empty folder · whitespace-only chunks dropped",
        notes="""
Include this slide. It's evidence you ran the code against awkward input rather
than only the happy path, and mentors trust a presenter who volunteers their own
bugs.

The UTF-8 one has a nice moral: the logic was right and the display was wrong,
which is a category of bug I'd not have found without real documents containing
real punctuation.
        """,
    )

    deck.table_slide(
        "Where Week 1 actually stands",
        ["deliverable", "state"],
        [
            ["Embeddings generated, dimensionality shown", "done"],
            ["Similar vs unrelated cosine comparison", "done — 0.617 vs 0.031"],
            ["Chunking, fixed size with overlap", "done"],
            ["Chunk size / overlap experiments", "done on interim corpus"],
            ["Every chunk embedded and held in memory", "done — 155 chunks"],
            ["5–10 of my own notes in sample-notes/", "OUTSTANDING"],
            ["\"What an embedding is\" in my own words", "OUTSTANDING"],
            ["\"Why splitting matters\" in my own words", "OUTSTANDING"],
            ["\"What semantic search means\" in my own words", "OUTSTANDING"],
        ],
        highlight_rows={5, 6, 7, 8},
        column_widths=[2.8, 1.4],
        kicker="Status",
        footer="All four outstanding items are mine to write — no blockers on anyone else",
        notes="""
Do not soften this. Present it plainly.

The dataset is the real blocker: every number in this deck describes an interim
corpus of the project's own documentation, used because sample-notes was still
empty. The sweep has to be re-run on the notes I actually ship, and the README has
to describe that dataset.

One honest detail if he asks why I used that stand-in: it's a poor benchmark
beyond being the wrong data, because it's self-modifying - editing the project
docs changes the thing being measured. An earlier run reported 53,852 characters
and 149 chunks; after I edited three files the same command reported 55,598 and
155. Chunk counts are a property of the corpus, not the settings.
        """,
    )

    deck.bullets_slide(
        "Week 2 plan, and what I need from you",
        [
            (0, "**Mon–Tue — index the chunks into Chroma, configured for cosine distance"),
            (1, "The L2 default would rank differently from everything measured this week"),
            (0, "**Wed–Thu — retrieval: embed the question, return top-k with scores, compare k of 3, 5, 10"),
            (0, "**Fri — log every retrieval to a file, and compare Chroma against one alternative"),
            (0, "**Two decisions I need from you:"),
            (1, "Does the deadline stay 4 October, or move to 11 October with the corrected calendar?"),
            (1, "Is there anything you would rather I cut if it stays at 4 October?"),
        ],
        kicker="Next",
        footer="Widening the no-answer test is my first priority — Week 3's refusal behaviour depends on that 0.027 margin",
        notes="""
End by handing him the two decisions. It's a short, concrete ask and it makes the
meeting useful rather than just a status report.

If he asks what you'd cut: top-k tuning beyond a single 3-vs-10 comparison, and
the Chroma-versus-Pinecone write-up. What I would not cut is citations, the
no-answer handling, or the demo video - those are the parts that show the pipeline
works end to end.
        """,
    )

    return deck


def main() -> int:
    output = Path(__file__).resolve().parent / "week1-review.pptx"
    deck = build()
    deck.save(output)

    slide_count = len(deck.presentation.slides)
    with_notes = sum(
        1
        for slide in deck.presentation.slides
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip()
    )

    print(f"Wrote {output}")
    print(f"  {slide_count} slides, {with_notes} with speaker notes")
    print("\nOne slide is intentionally unfinished: 'What an embedding is - in my own words'.")
    print("Fill it in before presenting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
