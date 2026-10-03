# Presentation Script — Weeks 1 and 2

Plain-language notes for `weeks1-2-review.pptx`. For each slide: what it shows,
what to say, and the question most likely to come back at you.

Read this once tonight and once on Saturday morning. Don't memorise it — the aim
is that you understand it well enough to say it your own way.

**The whole project in one sentence:** it finds the relevant part of your own
notes, then asks a language model to answer using only that.

**The five stages, in order:** chunk → embed → store → retrieve → generate.
Weeks 1 and 2 built the first four.

---

## Slide 1 — Title

**Shows:** project name, and that this covers both weeks.

**Say:**
> "This is Ask My Docs. It answers questions about my own notes, using only what
> it finds in those notes. I'm covering two weeks today. The first week was
> turning text into something a computer can compare, and cutting documents into
> useful pieces. The second week was storing those pieces in a real database and
> building the search. I also want to flag four things that are still
> outstanding, which are on the last slide."

Saying what's unfinished at the start makes everything else more credible.

---

## Slide 2 — What the tool will do, and where I am

**Shows:** the five stages, and that no framework was used.

**Say:**
> "The pipeline has five stages: chunk, embed, store, retrieve, generate. Cut the
> documents up, turn each piece into numbers, store those numbers, find the
> closest ones to a question, then let a model answer from them. I've built the
> first four. I wrote each stage by hand rather than using a framework like
> LangChain, because the brief asks for that."

**If he asks "why not use a framework?"**
> "It would have done all of week one in about four lines, and I wouldn't be able
> to explain any of them."

---

## Slide 3 — One thing I need you to decide

**Shows:** the brief's dates are a week out.

**Say:**
> "Before I start — the brief says the project runs from 14 September to 4
> October. I actually started on the 21st. So my three weeks are 21 to 27
> September, 28 September to 4 October, and 5 to 11 October. That puts your 4
> October deadline at the end of my second week. I need to know whether it moves
> to the 11th or stays at the 4th."

**If he says "it stays at 4 October"** — have this ready:
> "Then I'd cut the optional extras: no further top-k tuning, and I'd shorten the
> database comparison write-up. I'd keep the citations, the handling for
> unanswerable questions, and the demo video."

---

## Slide 4 — Divider: Week 1

**Say:** "First week — embeddings and chunking." Then move on. It's a signpost.

---

## Slide 5 — Embeddings: does this actually work?

**Shows:** three scores. 0.617, 0.031, and 0.618 highlighted.

**The idea first:** an embedding turns a piece of text into a position on a map
of meaning. Things that mean similar things sit close together. The score is how
close two pieces are — 1.0 is identical, 0.0 is unrelated.

**Say:**
> "Before building anything else I had to check that this actually works. I took
> three sentences that all mean 'I bake at weekends' and three sentences on
> completely unrelated topics — a tax deadline, Saturn's moons, rebooting a
> router. The related ones scored 0.617 against each other. The unrelated ones
> scored 0.031.
>
> The highlighted row is the one that convinced me. 'I bake sourdough bread every
> weekend' and 'Most Saturdays you will find me making a loaf from scratch'
> scored 0.618. Those two sentences share no meaningful words at all. A keyword
> search would score that pair near zero. The model got it purely from meaning."

**If he asks "why is 0.617 good when it isn't near 1.0?"** — this is the most
likely follow-up:
> "Because of the 0.031 underneath it. The scores only mean something relative to
> each other. If I'd assumed 'similar' meant above 0.8, I'd have thrown away
> every correct match. So I rank results against each other instead of using a
> fixed cut-off."

**If he asks "why write cosine similarity yourself?"**
> "The brief says build it manually. And I wanted to understand why you divide by
> the length of both — it cancels length out, so a short sentence and a long
> paragraph that mean the same thing still match."

---

## Slide 6 — What an embedding is

**Shows:** a four-sentence explanation, with an amber DRAFT strip across the top.

**This slide is yours.** Read the draft out loud, change anything that doesn't
sound like you, then delete the amber strip. The draft currently says:

> An embedding is what you get when a model reads text and turns it into a
> position on a map of meaning. Text that means similar things lands in nearby
> positions, even when the actual words are completely different. The model
> worked out the layout of that map during training, so nobody chose what each
> number stands for — and one number on its own tells you nothing. What carries
> the information is how close two pieces of text end up to each other.

**The three follow-ups he is most likely to ask:**

*What makes two things land near each other?*
> "The model was trained on a huge amount of text and learned which words and
> ideas appear in similar situations. Nobody programmed the positions."

*Why 384 numbers?*
> "That's just the size this model outputs. A bigger model uses more numbers and
> captures finer distinctions, but costs more. The important part is that the
> count never changes — seven characters and two hundred characters both give 384."

*Isn't this just a search index?*
> "No. A search index stores words. This stores a position. That's why two
> passages can be close together with no words in common."

---

## Slide 7 — Why chunking needs care: a fact that vanished

**Shows:** three ways of cutting a document. The first says the fact is in no chunk.

**Why chunking exists at all:** an embedding is always the same size. A whole
document gets squeezed into the same amount of space as one sentence, so
everything it discusses gets averaged together and it stops matching any one
topic sharply. Cutting it into pieces means each piece keeps its own meaning.

**Say — this is your strongest slide, go slowly:**
> "I wanted to test what happens when a cut lands in the wrong place. So I hid one
> sentence in a document, positioned so that a 500-character cut would slice
> through the middle of it.
>
> With no overlap, half the sentence ended up in one chunk and half in the next.
> Neither half was complete enough to match a question about it. So the fact was
> in my notes, and my tool could not find it — and nothing reported an error
> anywhere. The answers just quietly get worse.
>
> The second row fixed it by luck. My splitter looks backwards a short distance
> for a sentence ending, and this time it found one before the fact. That only
> works when the text happens to have punctuation in the right place.
>
> The third row fixed it deliberately. Overlap means each chunk repeats the last
> 100 characters of the one before it, so any short fact survives whole
> somewhere. That doesn't depend on the text cooperating."

**If he asks "what does overlap cost?"**
> "About 1.26 times the storage, because roughly a quarter of what I save is a
> second copy. Irrelevant at this size."

---

## Slide 8 — Picking a chunk size

**Shows:** the same document cut at 300, 500 and 1500 characters.

**Say:**
> "I took one document and cut it three ways. At 300 characters a piece held one
> idea and nothing else. At 500 it held the idea plus the start of an unrelated
> table. At 1500 it held the idea, a whole table, and two further sections.
>
> That's the trade-off. Small pieces match precisely but might leave out context
> the answer needs. Big pieces carry their context along but dilute the match,
> because one relevant sentence gets averaged in with paragraphs about something
> else.
>
> I went with 500 characters and 100 overlap. It held a complete thought without
> swallowing a whole table, and the overlap rescued the fact from the last slide.
> But I'm calling it provisional — the only real test is whether answers are
> good, and that's week three."

**If he asks "why characters and not tokens?"**
> "Characters are something I can see. I can look at a 500-character chunk and
> know exactly what's in it. Tokens need a separate tool to count and make that
> link indirect. Token-based is the better production choice because context
> limits are measured in tokens, and I note that in the README."

---

## Slide 9 — I built search with no database at all

**Shows:** the claim that the database is less accurate than this version.

**Say:**
> "At the end of week one I embedded all my chunks into a plain Python list and
> searched it with a loop, comparing the question against every single chunk.
>
> I did that deliberately before touching a database. Because my loop compares
> everything, it cannot miss a match — it's exact. Chroma, the database I added in
> week two, deliberately skips most comparisons to go faster. So it's actually
> less accurate than my loop, not more.
>
> I'd assumed a real database meant better. It means faster, and slightly less
> reliable. Knowing which way that trade runs is the whole reason I wrote the loop
> first."

**If he asks "so why use a database at all?"**
> "At 171 chunks my loop takes 15 milliseconds, so not for speed. The real benefit
> is that the index survives restarting. Before, every run re-embedded all my
> notes first, which took about a minute before I could ask anything."

---

## Slide 10 — Asking a question my notes cannot answer

**Shows:** 0.339, 0.366, and the 0.027 gap between them.

**Say:**
> "I tested a question my notes definitely cannot answer — what time does the
> corner shop close on Sundays. It still returned five passages, because this kind
> of search always returns its closest matches. There's no such thing as 'nothing
> found'.
>
> Its best score was 0.339. It matched a passage containing 'Sun Oct 4' from a
> schedule, because my question said Sundays. The model is right that those are
> related in meaning — it just has no idea whether being related actually answers
> anything.
>
> Here's the problem. The weakest score from a question my notes genuinely do
> answer was 0.366. That's a gap of 0.027. On slide 5 the gap looked like 0.617
> versus 0.031, so ignoring low scores seemed easy. Against a real set of notes
> it's twenty times narrower, because with a few hundred pieces something is
> always a bit close to anything you ask."

**Then set up Week 2:**
> "So I need two defences: a score cut-off, and a prompt that lets the model say
> it cannot find the answer. I tested the cut-off in week two and I'll come back
> to that."

---

## Slide 11 — Divider: Week 2

**Say:**
> "Week two replaced the list with a real database and built the retrieval step.
> Three of these slides answer questions week one left open."

---

## Slide 12 — What the database actually changed

**Shows:** four points about Chroma.

**Say:**
> "171 chunks now live in a database on disk instead of in memory. The real win
> isn't speed — it's that the index survives restarting, so the minute of
> embedding is paid once when my notes change, not every time I ask something.
>
> I had to set the distance measure by hand. Chroma defaults to a different one
> that wouldn't match the scores from week one.
>
> It also refuses to answer if the notes were indexed by a different model than
> the one asking."

**If he asks about that last point:**
> "That's the nastiest failure in the whole pipeline, because there's no symptom.
> Numbers from two different models aren't comparable, but querying across them
> doesn't raise an error — you just get confident, well-formed, meaningless
> results. So the database records which model built it and refuses a mismatch."

**If he asks about the distance measure:**
> "Chroma's default is squared L2. I measured it — for two unrelated directions it
> reports 2.0 where cosine reports 1.0. For my model both happen to rank the same
> way, so nothing would have looked broken. It would only have bitten me if I
> switched models later. One line to remove the risk."

---

## Slide 13 — Does the shortcut cost accuracy? I measured it

**Shows:** Chroma vs the week 1 loop, on two questions. Same answers both times.

**Say:**
> "On slide 9 I said the database would be less accurate than my loop. This is
> the check. I ran the same questions through both and compared the results. It
> agreed on all five passages, both times.
>
> But I want to be careful about that result, because it's not the win it looks
> like. At 171 chunks the structure it searches is small enough that it reaches
> the right answers anyway. The approximation only starts costing accuracy when
> the data is big enough that it has to skip meaningful parts. So this confirms I
> wired it up correctly — it doesn't prove the shortcut is free."

**Worth adding:**
> "The scores also matched my hand-written calculation to four decimal places —
> 0.6690, 0.6070, 0.5247 on the same chunks. Two independent implementations
> agreeing exactly is good evidence neither my arithmetic nor my configuration is
> wrong."

---

## Slide 14 — How many passages should I fetch?

**Shows:** 3, 5 and 10 compared on relevance, text sent, and wasted slots.

**Say:**
> "This is how many passages to grab per question. Going from 3 to 10 costs 3.4
> times the text for a 0.06 drop in average relevance.
>
> The last column is the interesting one, and it links back to chunking. Because
> consecutive chunks overlap by 100 characters, sometimes two neighbours both come
> back for the same question — so I'd be sending the model the same text twice. At
> 10, nearly 3 of the 10 slots went on duplicates.
>
> I chose 5. At 3 I was pulling from only two and a half documents on average,
> which makes it too easy to miss a detail that fell just outside. 5 gives me
> three sources and about 2,200 characters, which is a comfortable prompt size.
> Still provisional until I test real answer quality."

---

## Slide 15 — The idea that did not survive testing

**Shows:** cut-off levels against four real questions plus one bad question.

**Say — and own the mistake, it's the strongest thing you can do:**
> "Week one ended with the idea of just ignoring anything below a certain score.
> Week two tested it properly, and it doesn't work.
>
> Read the 0.35 row. The bad question is finally silenced — zero passages. But
> questions 2 and 3 drop to two passages each. At 0.40 they return nothing at all,
> for questions my notes genuinely answer.
>
> And I should be honest about how I found this. My first version of the test used
> only question 1, which scores high on everything, and a 0.35 cut-off looked
> perfectly safe. Sweeping all four questions is what exposed the conflict. A test
> built around the best case is worse than no test, because it gives you false
> confidence.
>
> The reason it happens: the scores aren't comparable between questions. A
> question worded the way my notes are written scores high throughout. One worded
> differently scores low throughout, even when its best match is exactly right.
>
> So the cut-off ships switched off, and week three's prompt has to be the real
> defence — the model needs permission to say it can't find the answer."

---

## Slide 16 — Where I stand after two weeks

**Shows:** three things done, two outstanding, week 3 to come.

**Say — plainly, no softening:**
> "Three stages are done: embeddings and similarity, chunking with overlap, and
> the database with retrieval and logging. Chunk size and top-k were both chosen
> from measurements rather than guesses.
>
> Two things are outstanding and both are mine. I need to put five to ten of my
> own notes in as the test set, and I need to write my explanations in my own
> words.
>
> I should be straight about the test set. My notes folder is still empty, so
> everything I've measured ran against this project's own documentation. The
> numbers are real but they describe the wrong documents — and I know it, because
> the chunk count drifted from 159 to 171 during the week purely because I kept
> editing those files. Same code, different numbers. That's exactly why a fixed
> dataset matters, and it's my first job before week three.
>
> Week three is generating the answers, citing sources, the README and the video."

**Close by returning to slide 3:**
> "So the one thing I need from you is the deadline — 4 or 11 October?"

---

## If you get stuck

Three sentences that rescue most situations:

- *"Let me show you"* — then run `scripts\05_retrieve.py --question "..."` live.
- *"I measured that, let me find the number"* — it's in `notes/week1-learning-log.md`
  or `notes/week2-learning-log.md`.
- *"I don't know yet, that's week three"* — true for anything about answer quality,
  citations, or the prompt.

## Live demo commands

Setup, once per terminal session:

```powershell
[Console]::OutputEncoding=[Text.Encoding]::UTF8; $env:HF_HUB_OFFLINE=1; $env:ANONYMIZED_TELEMETRY='False'
```

Then one at a time:

```powershell
# embeddings: 384 numbers, and the 0.617 vs 0.031 result   (~20s)
.\venv\Scripts\python.exe scripts\01_embedding_basics.py

# chunking: the fact lost at a boundary is in Part 3       (~15s)
.\venv\Scripts\python.exe scripts\02_chunking_demo.py --folder .kiro

# a live question - best moment, because it is unrehearsed  (~5s)
.\venv\Scripts\python.exe scripts\05_retrieve.py --question "why does chunk overlap matter?"
```

`--folder .kiro` is there because `sample-notes/` is still empty. Say that out
loud when it appears on screen, before he asks.
