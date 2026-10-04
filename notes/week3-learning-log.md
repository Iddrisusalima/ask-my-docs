# Week 3 Learning Log — Generation, Citations, Submission

Week 3 runs **Mon 5 Oct – Sun 11 Oct 2026** under the corrected calendar.
Deadline still to be confirmed with mentor.

---

## Mon–Tue — Connect retrieval to generation

Code: `src/generator.py`, `scripts/06_ask.py`

```powershell
.\venv\Scripts\python.exe scripts\06_ask.py --question "why does chunk overlap matter?"
.\venv\Scripts\python.exe scripts\06_ask.py --question "..." --show-prompt
```

### No new API key needed

Project 1 used **Gemini**, and that key was still in `prompt-lab/.env`. The brief
says to reuse the Project 1 chat setup, so I did.

Google exposes an OpenAI-compatible endpoint
([docs](https://ai.google.dev/gemini-api/docs/openai)), which meant zero code
changes — only three values in `.env`:

```
OPENAI_API_KEY=<the Gemini key from Project 1>
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_CHAT_MODEL=gemini-3.5-flash-lite
```

Worth understanding why that worked: most providers have settled on OpenAI's
chat-completions protocol, so the client library is interchangeable. Groq,
Together and a local Ollama server all work the same way. The provider is now a
configuration detail, not an architectural decision — and that is only true
because the generator never hardcoded a URL.

_Content from the Google documentation was rephrased for compliance with licensing restrictions._

### The prompt is assembled in plain sight

`build_prompt()` is a **pure function** — question and passages in, prompt string
out, nothing else touched. Two things that buys:

1. `--show-prompt` prints the exact text the model would receive and stops,
   without spending a call. "The model only sees my notes" is a claim; the
   printed prompt is evidence. This is what I will demo in the video.
2. Citations come from the passages that actually *fitted the budget*, not
   everything retrieved. If those two lists ever diverged, every citation would
   be wrong.

Passages arrive numbered `[1]`–`[5]`, each labelled with its source. The model is
told to cite the numbers. Asking it to "say which files you used" produces vague
gestures at the whole set; numbers give it something precise to point at.

### The clause that does the real work

Rule 3 of the system prompt:

> If the passages do not contain the answer, say so plainly — for example: "I
> can't find the answer to that in your notes." Do not guess, do not fill gaps
> from general knowledge.

Without that, a model handed irrelevant passages still produces something,
because refusing is not an option it has been given. With it, refusing becomes
the compliant response.

This is the direct consequence of Week 2's measurement. A question with no answer
scored 0.3386 while the weakest genuine answer scored 0.3655 — a gap of 0.027.
No score threshold separates those reliably, so `MIN_SCORE` ships off and the
prompt carries the weight.

### First real answer

Question: *"why does chunk overlap matter?"*

> Overlap acts as a defense against a fact being severed at a boundary; without
> it, a sentence split across two chunks might be retrievable through neither
> **[3]**. Additionally, when overlap is greater than zero, each chunk after the
> first begins with the final `overlap` characters of the preceding chunk **[1]**.

| passage | cited | score | source |
| ------- | ----- | ----- | ------ |
| [1] | **yes** | 0.7329 | `requirements.md#14` |
| [2] | no | 0.6006 | `tasks.md#12` |
| [3] | **yes** | 0.5923 | `design.md#11` |
| [4] | no | 0.5545 | `design.md#39` |
| [5] | no | 0.5429 | `requirements.md#15` |

Both citations are correct — I opened those files and the claims are genuinely
there.

**But 3 of 5 passages went unused**, and the script now reports that. If it keeps
happening, top-k of 5 is higher than it needs to be. That is a measurement I
could not have taken before this week: Week 2 could only count how many passages
*looked* relevant, not how many actually got used.

### The no-answer test — the self-check item

| question | top score | answer |
| -------- | --------- | ------ |
| "What time does the corner shop close on Sundays?" | 0.3386 | *"I can't find the answer to that in your notes."* |
| "What is the capital of Peru?" | 0.1207 | *"I can't find the answer to that in your notes."* |

The Peru question is the stronger test, and worth explaining out loud. The model
**certainly knows** the capital of Peru from its general training. It refused
anyway. That proves the grounding instruction is working, rather than merely
proving that retrieval found nothing — a distinction the corner shop test alone
cannot make.

Also note the display flags "the model cited nothing", which is the right
behaviour: a refusal should cite nothing, and an *answer* that cites nothing is a
warning sign worth checking.

---

## Wed — Add source citations

_(partly done as part of Mon–Tue; still to verify across more questions)_

- [x] passage numbers resolved back to filename and chunk id
- [x] PDF citations carry the page number, e.g. `notes.pdf#3 (p.2)`
- [x] similarity score shown beside each source
- [x] cited vs offered-but-unused marked separately
- [ ] open the source files and confirm every citation across 10 questions

---

## Thu — Test and refine

_(not started)_

### Ten questions, rated

| # | question | answer quality | notes |
| - | -------- | -------------- | ----- |

---

## Fri–Sat — Polish and document

_(not started)_

### README checklist, from the brief

- [ ] one paragraph on what the tool does and the dataset used
- [ ] setup instructions, including how to add your own documents
- [ ] "What I Learned" — embeddings, chunking, the pipeline, **in my own words**
- [ ] chosen chunk size and top-k, with the reasoning
- [ ] screenshot of a real question, answer and cited source

### Demo video, 3–4 minutes

- [ ] show ingestion
- [ ] ask 2–3 questions live
- [ ] explain what happens at each stage

---

## Blocking everything

`sample-notes/` is **still empty**. Every number in all three learning logs
describes this project's own documentation. Before the README screenshot and the
ten-question test, that folder needs 5–10 of my own non-sensitive notes — the
brief requires it committed so the mentor can run the tool unmodified.
