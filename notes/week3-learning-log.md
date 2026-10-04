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

### The dataset is finally real

`sample-notes/` now holds **5 of my own notes** — my Project 1 write-ups:
`project1-build-log.md`, `project1-overview.md`, `project1-learnings.md`,
`project1-blog-post.md`, `project1-screenshots.md`. 79,581 characters.

Checked for secrets and personal details before committing, since the folder goes
to a public repo: no API keys, no email addresses, no phone numbers.

Good choice of dataset for a second reason — the notes are about prompt
engineering and token economics, so the questions I ask have real answers I can
verify by opening the file.

### Ten questions, rated

Settings: chunk size 350, overlap 70, top-k 5, no score floor,
`gemini-3.5-flash-lite`.

| # | question | result | cited | verdict |
| - | -------- | ------ | ----- | ------- |
| 1 | What does it mean that the API is stateless? | answered | [2][3] | **good** |
| 2 | What is the difference between training and inference? | answered | [1][3][4][5] | **good** |
| 3 | What do roles do in a chat request? | answered | [1] | **good** |
| 4 | Why is the total token count not always input plus output? | answered | [1][5] | **good** |
| 5 | What is a context window measured in? | answered | [1][2][3] | **good** |
| 6 | When streaming, when does token usage arrive? | answered | [3][4][5] | **good** |
| 7 | How much influence does the system instruction have? | answered | [2][5] | **good** |
| 8 | How did I keep my API key safe? | answered | [4] | **partial** — got the `.gitignore` point, missed the other three steps |
| 9 | What is the capital of Peru? | refused | — | **correct refusal** |
| 10 | How do I fix a leaking radiator? | refused | — | **correct refusal** |

**8 of 8 answerable questions answered with correct citations. 2 of 2 controls
refused.** I opened the cited files and checked: every citation genuinely
contains the claim.

### How I got there — the iteration loop the brief predicted

The first run was **not** 8 of 8. At the documented 500/100 setting, two
questions were refused that my notes clearly answer. Diagnosing those produced
the two most useful findings of the week.

**Failure 1 — "Why are input and output tokens priced differently?"**

The answer exists at `project1-build-log.md` line 415: *"Output tokens cost about
8x more than input tokens. $2.50 versus $0.30 per..."*. But the passage retrieval
handed the model began **mid-word**:

```
y 8x more per token than
input**. The `/stats` command prints...
```

That is "...roughl**y 8x** more per token" with its opening sliced off into the
previous chunk. The model received an incoherent fragment and refused. At top-k
10 the clean statement still never appeared — no chunk contained it whole.

**This is Week 1's boundary problem, resurfacing where it finally costs an
answer.** In Week 1 I demonstrated it with a planted sentence in a test document.
Here it happened by itself, on my real notes, and the symptom was not a missing
chunk — it was a refusal that looked like the tool working correctly.

Re-ingesting at 900/300 fixed the fragment, and the answer changed to:

> "I can't find the answer to that in your notes. The notes state that input and
> output are priced differently [2][3], but they do not explain *why* the pricing
> difference exists."

Which is **correct** — and my question was the faulty part. My notes record
*that* the prices differ, not *why* Google sets them that way. Rule 4 of the
system prompt ("give the part they support and say what is missing") produced
exactly the right behaviour. Lesson: when an answer looks wrong, check the
question before blaming the pipeline.

**Failure 2 — "How did I keep my API key safe?"**

My notes answer this in four numbered steps under a heading literally called
"How I keep the key safe". At both 500/100 and 900/300 the tool refused, and
retrieval returned a passage about token counts and history resets instead.

The cause is the opposite of failure 1. That section is only eight lines long. At
900 characters it gets absorbed into a chunk dominated by surrounding material,
and its meaning is diluted until it no longer matches a question about key
safety. **That is the "large chunks dilute the match" tradeoff from Week 1,
biting in the other direction.**

At 350/70 the section occupies a chunk of its own, and the tool answers:

> "You kept your API key safe by writing `.gitignore` before the key existed on
> disk [4]."

Correct, though partial — it got one of four steps.

### The decision: chunk size 350, overlap 70

Changed from the provisional 500/100 chosen in Week 1.

| setting | Q1 (token pricing) | Q8 (key safety) |
| ------- | ------------------ | --------------- |
| 500 / 100 | refused — mid-word fragment | refused |
| 900 / 300 | correct partial answer | refused — diluted |
| **350 / 70** | fine | **answered** |

Why smaller won on my notes: they are written in short sections with frequent
headings. Each heading introduces a distinct idea, and a 350-character chunk maps
roughly to one of those sections. At 900 characters a chunk spans several
sections and its embedding becomes an average of unrelated ideas.

**This is why the Week 1 choice had to stay provisional.** 500/100 was defensible
from chunk-count statistics, which is all I had then. Answer quality on real
notes is a different measurement and it pointed somewhere else. The brief said
this iteration loop was normal and expected; it was.

Honest limitation: 350/70 is tuned to how *my* notes are written. Someone with
long flowing prose and few headings would likely need larger chunks. The right
answer is a property of the documents, not a universal constant.

### Still open from this round

- Q8 returns one of four steps. Worth testing whether top-k 7 or 8 recovers the
  rest, now that chunks are smaller and each holds less.
- Several answers cite only 1 of 5 passages. With smaller chunks, a slightly
  higher top-k may now be the better setting — the earlier argument against 10
  was measured at 500/100 and may no longer hold.

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
