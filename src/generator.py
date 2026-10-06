"""
Turning retrieved passages into a grounded, cited answer.

This is the last stage of the pipeline, and the one where a RAG tool either earns
trust or quietly loses it. Retrieval can be perfect and the answer still wrong,
because the model is free to ignore what it was given and reply from its own
general knowledge instead. Nothing in the plumbing prevents that. Only the prompt
does.

Three decisions shape this module.

**The prompt is assembled in plain sight.** No template engine, no library. The
text sent to the model is built by `build_prompt`, which you can read top to
bottom and print before sending. If the answers go wrong, the first question is
always "what did the model actually receive?", and that has to be answerable.

**Passages are numbered.** The context arrives as [1], [2], [3] and the model is
told to cite those markers. Numbering gives it something precise to point at;
asking it to "say which files you used" produces vague gestures at the whole set.
The numbers are then resolved back to real filenames for display.

**The model is given permission to refuse.** This is the part that is easy to get
wrong. Told only "answer from the context", a model handed irrelevant passages
will still produce something - it has no acceptable alternative. Told "if the
context does not contain the answer, say so plainly", refusing becomes the
compliant response.

That matters because of what retrieval tuning measured. A question with no answer in the
notes still scored 0.339, against 0.366 for the weakest genuine answer - a gap of
0.027. No score threshold can separate those reliably, so the relevance floor
ships switched off and this prompt carries the weight instead.

`build_prompt` is a pure function: question and chunks in, prompt string out,
nothing else touched. That is what lets the demo show the exact prompt without
spending an API call, and it is why citations can be drawn from the passages that
genuinely fitted the budget rather than everything retrieved.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from src.retriever import RetrievedChunk

load_dotenv()

# How much retrieved text may go into one prompt. At the chosen top-k of 5 and
# 500-character chunks, a full set is around 2,500 characters, so this leaves
# comfortable headroom while still capping a pathological case.
DEFAULT_CHAR_BUDGET = 6000

DEFAULT_CHAT_MODEL = "gpt-4o-mini"

# The instruction that does the real work. Worth reading as prose rather than
# configuration - every clause is here for a reason.
SYSTEM_PROMPT = """\
You answer questions about a specific person's personal notes.

Rules you must follow:

1. Answer using ONLY the numbered passages provided. Do not use anything you know
   from outside them, even if you are confident it is correct.
2. Cite the passages you used, by their numbers, like [1] or [2][3]. Cite only
   passages that genuinely support what you wrote.
3. If the passages do not contain the answer, say so plainly - for example:
   "I can't find the answer to that in your notes." Do not guess, do not fill
   gaps from general knowledge, and do not apologise at length.
4. If the passages only partly answer the question, give the part they support
   and say explicitly what is missing.
5. Keep the answer short. Two or three sentences is usually right.

The passages come from the user's own notes, so the facts in them take priority
over anything you believe to be true in general."""


@dataclass
class Answer:
    """A generated answer, with everything needed to verify it.

    Attributes:
        text: What the model wrote.
        used_chunks: The passages that actually fitted into the prompt, in the
            order they were numbered. Position 0 is passage [1].
        prompt: The exact user-side prompt that was sent.
        model: Which model produced the answer.
        omitted: How many retrieved chunks did not fit the character budget.
    """

    text: str
    used_chunks: list[RetrievedChunk] = field(default_factory=list)
    prompt: str = ""
    model: str = ""
    omitted: int = 0

    def citations(self) -> list[tuple[int, RetrievedChunk]]:
        """Passage number paired with its chunk, for displaying sources."""
        return list(enumerate(self.used_chunks, start=1))

    def cited_numbers(self) -> list[int]:
        """Passage numbers the model actually referenced in its text.

        Lets the display distinguish passages the model leaned on from passages
        it was offered and ignored - useful when judging whether top-k is too
        high.
        """
        found = []
        for number in range(1, len(self.used_chunks) + 1):
            if f"[{number}]" in self.text:
                found.append(number)
        return found


def build_prompt(
    question: str,
    chunks: list[RetrievedChunk],
    char_budget: int = DEFAULT_CHAR_BUDGET,
) -> tuple[str, list[RetrievedChunk], int]:
    """Assemble the user-side prompt from retrieved passages.

    Pure function - no network, no state. Call it to inspect exactly what the
    model will receive.

    Chunks are added in the order given (most similar first) until the budget
    runs out, so if anything is dropped it is always the least relevant material.

    Args:
        question: The user's question.
        chunks: Retrieved passages, most relevant first.
        char_budget: Maximum characters of passage text to include.

    Returns:
        The prompt, the chunks that fitted, and how many were omitted.

    Raises:
        ValueError: If the question is empty.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Cannot build a prompt for an empty question.")

    used: list[RetrievedChunk] = []
    spent = 0

    for chunk in chunks:
        length = len(chunk.chunk.text)
        if used and spent + length > char_budget:
            # Keep going rather than breaking: a later chunk may be short enough
            # to fit where this one did not.
            continue
        if spent + length > char_budget and not used:
            # Pathological case - a single chunk larger than the whole budget.
            # Better to truncate it than to send no context at all.
            used.append(chunk)
            spent += length
            break
        used.append(chunk)
        spent += length

    omitted = len(chunks) - len(used)

    if not used:
        body = (
            "No passages were retrieved from the notes for this question.\n\n"
            "Tell the user plainly that you cannot find the answer in their notes."
        )
    else:
        blocks = []
        for number, chunk in enumerate(used, start=1):
            # The source label is included so the model can be specific if it
            # wants to, but the numbers are what it is told to cite.
            blocks.append(
                f"[{number}] (from {chunk.chunk.citation()})\n{chunk.chunk.text.strip()}"
            )
        body = "PASSAGES FROM THE USER'S NOTES:\n\n" + "\n\n".join(blocks)

    prompt = f"{body}\n\n---\n\nQUESTION: {question.strip()}\n\nANSWER (cite passages by number):"

    return prompt, used, omitted


def generate_answer(
    question: str,
    chunks: list[RetrievedChunk],
    char_budget: int = DEFAULT_CHAR_BUDGET,
    model: str | None = None,
) -> Answer:
    """Send the assembled prompt to a chat model and return its answer.

    Args:
        question: The user's question.
        chunks: Retrieved passages, most relevant first.
        char_budget: Maximum characters of passage text to include.
        model: Chat model name. Defaults to OPENAI_CHAT_MODEL in .env.

    Returns:
        The answer, together with the prompt and the passages behind it.

    Raises:
        ImportError: If the openai package is not installed.
        RuntimeError: If no API key is configured, or the API call fails.
    """
    prompt, used, omitted = build_prompt(question, chunks, char_budget)
    model_name = model or os.getenv("OPENAI_CHAT_MODEL", DEFAULT_CHAT_MODEL)

    client = _build_client()

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            # Low but not zero. Grounded summarising does not benefit from
            # creativity, and higher values make the model likelier to drift
            # beyond the passages it was given.
            temperature=0.2,
        )
    except Exception as exc:
        # The question and the retrieved context are the expensive parts to
        # reproduce, so they are preserved in the error for the caller to retry.
        raise RuntimeError(
            f"The chat model call failed: {exc.__class__.__name__}: {exc}\n"
            "The question and retrieved passages are unaffected - check your API "
            "key, your credit balance, and your network, then try again."
        ) from exc

    text = (response.choices[0].message.content or "").strip()

    return Answer(
        text=text,
        used_chunks=used,
        prompt=prompt,
        model=model_name,
        omitted=omitted,
    )


def _build_client():
    """Create the chat client.

    Uses the OpenAI client, but honours OPENAI_BASE_URL so that any
    OpenAI-compatible endpoint works unchanged - Groq, Together, a local Ollama
    server, and others all speak the same protocol. That keeps the choice of
    provider a configuration detail rather than a code change.
    """
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - environment problem
        raise ImportError(
            "Answer generation needs the openai package. Install it with:\n"
            "  pip install openai==1.59.6"
        ) from exc

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()

    if not api_key:
        raise RuntimeError(
            "No OPENAI_API_KEY found in your .env file.\n"
            "Add a key, or point OPENAI_BASE_URL at an OpenAI-compatible endpoint "
            "such as Groq or a local Ollama server.\n"
            "To inspect the prompt without calling any model, run:\n"
            "  python scripts/06_ask.py --question \"...\" --show-prompt"
        )

    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)
