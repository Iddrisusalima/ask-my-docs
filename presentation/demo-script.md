# Demo Video Script

Target: **3–4 minutes**. The brief asks for the ingestion step, two or three live
questions, and an explanation of what happens at each stage.

Six beats. Timings are a guide, not a stopwatch.

| # | Beat | Time |
| - | ---- | ---- |
| 1 | What it is | 0:00 – 0:25 |
| 2 | Ingestion | 0:25 – 1:05 |
| 3 | First question, answered and cited | 1:05 – 1:45 |
| 4 | Proving it is grounded | 1:45 – 2:25 |
| 5 | A question it cannot answer | 2:25 – 3:00 |
| 6 | The finding, and close | 3:00 – 3:40 |

---

## Before you record

Run these once so nothing surprises you mid-take:

```powershell
cd C:\Users\hp\Desktop\ASK-MY-DOCS
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:HF_HUB_OFFLINE = 1
$env:ANONYMIZED_TELEMETRY = 'False'
```

Checklist:

- [ ] Terminal font bumped up — 16pt or more, or it will be unreadable on video
- [ ] Terminal maximised, editor and browser closed
- [ ] Run `scripts/ask.py --question "test"` once first, so the embedding model is
      warm. Cold, it adds a silent 10-second pause while it loads.
- [ ] `notepad .env` closed. Your API key must not appear on screen.
- [ ] Have `docs/screenshots/architecture-overview.png` open in a separate window
      if you want to show the diagram at beat 1.

---

## Beat 1 — What it is  (0:00 – 0:25)

**On screen:** the architecture diagram, or just the terminal.

> "This is Ask My Docs. It answers questions about my own notes, using only
> passages it retrieves from those notes — not the model's general knowledge.
>
> Five stages: chunk, embed, store, retrieve, generate. I wrote each one by hand
> rather than using a framework, because the point was understanding them.
>
> The dataset is five of my own write-ups from a previous project, about eighty
> thousand characters of markdown."

Do not linger. The interesting part is live.

---

## Beat 2 — Ingestion  (0:25 – 1:05)

**Run:**

```powershell
.\venv\Scripts\python.exe scripts\ingest.py --folder sample-notes
```

**While it runs** — it takes 30 to 60 seconds, so talk through the steps as they
print:

> "Ingestion runs once, and again whenever my notes change.
>
> It reads the five files — there's the loader, 79,581 characters.
>
> Then it cuts them into chunks. 350 characters with 70 of overlap, which gives
> 317 chunks. I'll come back to why those numbers.
>
> Now it's embedding every chunk — turning each one into 384 numbers that
> describe its meaning. That's the slow part, about thirty seconds, and it runs
> on my machine rather than calling an API, so it's free.
>
> And indexing into Chroma, which takes under a second. Embedding dominates
> ingestion by about a hundred to one."

**When it prints the HNSW settings and the agreement check:**

> "It also checks itself here — it runs the same query through Chroma's index and
> through a brute-force scan that compares every chunk, and confirms they agree."

---

## Beat 3 — First question, answered and cited  (1:05 – 1:45)

**Run:**

```powershell
.\venv\Scripts\python.exe scripts\ask.py --question "what is the difference between training and inference?"
```

**Point at the retrieved passages first:**

> "Here's the retrieval step. My question has been turned into 384 numbers by the
> same model that indexed the chunks — it has to be the same one, or the numbers
> aren't comparable. Chroma returned the five closest passages, with their
> similarity scores.
>
> And here's the answer."

**Then point at the citations:**

> "Notice the sources. The numbers in the answer — one and three — map to
> specific passages, and each one names a real file and chunk. So I can open
> `project1-learnings.md` and check the claim myself.
>
> Two of these five are marked as unused. The model was offered them and didn't
> need them, which is a useful signal: if that kept happening I'd know top-k was
> set too high."

---

## Beat 4 — Proving it is grounded  (1:45 – 2:25)

This beat is what separates a demo from a claim.

**Run:**

```powershell
.\venv\Scripts\python.exe scripts\ask.py --question "what is a context window measured in?" --show-prompt
```

> "Saying 'the model only sees my notes' is a claim. This proves it.
>
> `--show-prompt` prints the exact text that would be sent, and stops without
> calling the API at all.
>
> There's the system prompt: answer using only the numbered passages, cite the
> ones you use, and if they don't contain the answer, say so plainly.
>
> And there are the passages themselves, numbered one to five — straight out of
> my notes. That's everything the model gets. Nothing else."

Scroll so the numbered passages are visible. That image is the point.

---

## Beat 5 — A question it cannot answer  (2:25 – 3:00)

**Run:**

```powershell
.\venv\Scripts\python.exe scripts\ask.py --question "What is the capital of Peru?"
```

> "Now the test I'd apply to any tool like this.
>
> It still returned five passages — a nearest-neighbour search always returns its
> closest matches, there's no such thing as 'nothing found'. But look at the
> scores: nothing clears 0.17.
>
> And the answer: *I can't find the answer to that in your notes.*
>
> That's the important bit. The model absolutely knows the capital of Peru. It
> refused because the answer wasn't in the passages it was given. Nothing is
> cited, because there was nothing to cite."

**If you have time:**

> "That behaviour comes from one clause in the prompt. Told only 'answer from the
> context', a model handed irrelevant passages still produces something, because
> refusing isn't an option it has. Giving it explicit permission to say 'I can't
> find this' is what makes refusal the compliant answer."

---

## Beat 6 — The finding, and close  (3:00 – 3:40)

Say this part even if you have to rush. It is the strongest thirty seconds
available to you.

> "One last thing — those chunk settings.
>
> I first picked 500 characters from chunk-count statistics. Then I tested real
> answer quality and two questions my notes clearly answer came back refused.
>
> One of them, retrieval had handed the model a passage starting mid-word —
> 'y 8x more per token' — because the sentence had been cut in half and neither
> piece survived whole. The model got a fragment and correctly declined.
>
> The other was the opposite problem: a short eight-line section got swallowed
> inside a larger chunk and its meaning was diluted until it stopped matching.
>
> 350 with 70 overlap fixed both. So that number isn't a default — it came from
> diagnosing two specific failures.
>
> Everything's on GitHub: the code, the measurements behind every setting, and
> the architecture diagrams. Thanks for watching."

---

## If you only have two minutes

Cut beats 1 and 2. Open on an already-indexed database and go straight to the
first question. Keep beats 3, 5 and 6 — answer with citations, the refusal, and
the chunk-size finding. Those three carry the project.

## Three things not to do

**Don't read this script aloud.** Know the six beats and talk. A read-aloud
script is audible and it undercuts the impression that you understand the work.

**Don't apologise for scope.** It's a CLI over five markdown files because the
brief said build it by hand. That's the assignment, not a shortfall.

**Don't skip beat 5.** Plenty of demos show a tool answering. Showing it decline
is rarer and it's the thing your mentor's self-check specifically asks about.
