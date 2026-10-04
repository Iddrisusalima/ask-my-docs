# Prompt Lab — Project 1 Notes

**Author:** Iddrisu Salima
**Goal:** Build a CLI chat tool that talks to an AI model, remembers the
conversation, and reports tokens and cost after every reply.

| | |
| --- | --- |
| Provider | Google Gemini |
| Model | `gemini-3.5-flash-lite` |
| Language | Python 3.12.5 |
| SDK | `google-genai==2.22.0` |
| Secrets | `python-dotenv==1.2.3`, key in git-ignored `.env` |

**Why Gemini:** it's the only one of the three suggested providers with a
genuinely free tier. OpenAI and Anthropic both require a payment method before
your first call.

---

# Day 1 (Mon Sep 7) — Setup & First API Call

**Status: complete.** All five requirements from the brief are met and verified.

## Requirements checklist

| Requirement | How I met it |
| --- | --- |
| Install Python | Already had 3.12.5 (brief needs 3.10+) |
| Free API key, not committed | Gemini key from AI Studio, verified invisible to git |
| Store key in `.env`, load with dotenv | `load_dotenv()` at the top of the script |
| Smallest script: one message, one reply | `single_turn.py` |
| Read what "inference" means | Written up below in my own words |

## What I built

```
prompt-lab/
├── .gitignore        # protects .env and venv/ from being committed
├── .env              # my real key — git-ignored, never leaves my machine
├── .env.example      # safe template with no real values, this one IS committed
├── requirements.txt  # pinned exact versions so the project is reproducible
├── single_turn.py    # one message in, one reply out
├── BUILD-LOG.md      # this file
└── venv/             # virtual environment
```

## How to run it

```powershell
cd C:\Users\hp\Desktop\prompt-lab
.\venv\Scripts\python.exe single_turn.py
```

## Terminal output (proof it works)

```
--- You asked (gemini-3.5-flash-lite) ---
In two sentences, explain what an API is to a complete beginner.

--- Model replied ---
An API, or Application Programming Interface, is like a waiter in a restaurant
who takes your order from the menu, delivers it to the kitchen, and brings the
food back to your table. In the digital world, it acts as a messenger that lets
different software programs talk to each other and share information seamlessly.

--- Token usage ---
prompt_token_count=15   candidates_token_count=62   total_token_count=77
```

Something I noticed: running the same prompt twice gives differently worded
replies, and the output token count changes (60 one run, 62 the next). The model
is predicting token by token, not retrieving a stored answer.

## Error handling (already working on Day 1)

With no key present, the tool exits cleanly with exit code 1 and no stack trace:

```
No API key found.
Fix: copy .env.example to .env, then paste your real key into GEMINI_API_KEY.
Get a free key at https://aistudio.google.com/apikey
```

This is one of the Day 7 self-check boxes ticked early.

## How I keep the key safe

1. Wrote `.gitignore` **before** the key existed on disk. Order matters — a file
   already tracked by git keeps being tracked even if you add it to `.gitignore`
   later.
2. Verified with `git check-ignore -v .env`, which confirmed the match came from
   line 2 of `.gitignore`.
3. Verified `git status` cannot see `.env` at all.
4. Committed `.env.example` instead, so anyone cloning knows which variables to
   set without ever seeing my values.

## Four problems I hit, and what each one taught me

**1. `.env` was in the wrong folder.**
I saved it inside `venv/`, but `load_dotenv()` looks in the script's own
directory. The key was never loaded. Moved it to the project root.
*Lesson:* `.env` belongs next to the script that reads it.

**2. `gemini-2.5-flash` returned 404.**
The error said the model is no longer available to new users. The valuable part
is the status code: **404 means my key authenticated fine** and only the model
name was wrong. A bad or missing key returns 401 or 403 instead.
*Lesson:* read the status code before assuming your key is broken.

**3. `client.models.list()` gave me a misleading answer.**
It listed `gemini-2.5-flash` as available even though actually calling it failed.
*Lesson:* the only reliable test of a model is calling it.

**4. Hidden "thinking" tokens are billed.**
Probing `gemini-3.6-flash`, I got 4 input + 2 output tokens but a **total of 62**.
The missing 56 were internal reasoning tokens — charged, but never shown in the
reply. On `gemini-3.5-flash-lite` the math is transparent: 15 + 62 = 77.
*Lesson:* `total_token_count` is the number you actually pay for, and it is not
always input + output. I chose the transparent model so Day 4's cost calculations
stay honest.

## In my own words: what is inference?

**Training** happened once, in the past, and is finished. The model was fed an
enormous amount of text and slowly adjusted billions of internal numbers, called
weights, until it became good at predicting which token comes next. That took
months and enormous computing power. Those weights are now frozen.

**Inference** is what happens when I use it. Nothing learns and nothing is saved.
My prompt is split into tokens, pushed forward through the frozen weights once,
and the model emits the single most likely next token. That new token gets
appended to the input, and the whole process repeats to produce the token after
it. This continues until the model produces a stop signal.

So when I run `single_turn.py`, the chain is: my text travels over HTTPS to
Google's servers → it gets tokenized → it passes through the frozen network once
per output token → the assembled text comes back, with a token receipt attached.

Two consequences that shape the rest of this project:

- **The model has no memory whatsoever.** It does not know what I asked one
  second ago. On Day 3 I will "give it memory" by resending the entire
  conversation with every single request. That is the whole trick.
- **I pay per token in both directions.** The response object already carries the
  bill in `usage_metadata`, which is why I print it even on Day 1.

Those two facts are linked, and the link is the core insight of this project: if
memory means resending everything every time, then each turn of a conversation
costs more than the one before it.

---

# Day 2 (Tue Sep 8) — Roles & System Prompts

**Status: complete.** Script: `inspect_request.py`

- [x] Add a system prompt to give the bot a personality
- [x] Print the full request payload before sending it
- [x] Change the system prompt 3 times and record how replies change
- [x] Write 3–4 sentences on what "role" means in the API

## An important difference between Gemini and the brief

My brief describes the roles as **system, user, assistant**. That is OpenAI's
naming. Gemini does it slightly differently, and it tripped me up:

| Concept | OpenAI calls it | Gemini calls it |
| --- | --- | --- |
| Standing instructions / persona | a message with `role="system"` | `system_instruction`, a **config field outside the message list** |
| What I typed | `role="user"` | `role="user"` |
| What the model said before | `role="assistant"` | `role="model"` |

So in Gemini there is no `role="system"` at all. The system prompt travels as
configuration alongside the conversation, not as a turn inside it. The concept is
identical, only the packaging differs.

## The request payload, printed before sending

This is the whole thing. A chat API call is not magic — it is a system
instruction plus an ordered list of labelled messages.

```json
{
  "model": "gemini-3.5-flash-lite",
  "system_instruction": "You are a helpful assistant. Answer clearly and briefly.",
  "contents": [
    { "role": "user",  "text": "Hi! I am learning to code." },
    { "role": "model", "text": "That is great. What are you working on?" },
    { "role": "user",  "text": "What is 15 + 27?" }
  ]
}
```

## Experiment: 3 system prompts, identical messages

I sent the exact same three messages each time. **Only the system prompt
changed.** The final user message was always `What is 15 + 27?`

| System prompt | Reply | In tokens | Out tokens |
| --- | --- | --- | --- |
| Helpful assistant, clear and brief | `15 + 27 = 42.` | 43 | 11 |
| Grumpy 18th-century pirate | Spat tobacco on the deck, called me a lily-livered landlubber, insulted my brain, *then* said forty-two | 60 | 161 |
| Strict teacher, never give the answer | "Let's use our place value columns—can you add the ones digits (5 and 7) together first?" | 62 | 24 |

### What I learned from the numbers

**The persona changed behaviour, not just tone.** The teacher genuinely refused
to answer 42 at all and asked a question back instead. That is a real change in
what the tool *does*, from one sentence of instruction. No code changed between
those three runs.

**Input tokens were different every time (43 / 60 / 62) even though my messages
were identical.** This surprised me. The reason is that the system prompt is
itself billed as input tokens, on every single request. A long, detailed persona
is a tax you pay on every turn for the whole conversation.

**Output tokens varied wildly (11 / 161 / 24).** The pirate used about 14x the
output tokens of the plain assistant to answer the same maths question, because
personality means more words. Personality is not free.

## In my own words: what does "role" mean in the API?

A role is a label attached to each message telling the model **who said it**. The
model receives one flat list of text and would otherwise have no way to tell my
words apart from its own. `user` marks what I typed, and `model` (called
`assistant` by OpenAI) marks what the model said on earlier turns. The system
instruction is separate again: it is not a turn in the conversation but a standing
rule that shapes every reply, which is why it sets persona and behaviour rather
than contributing to the back-and-forth.

The practical consequence is that roles are how a stateless model reconstructs a
conversation. Because it keeps no memory between calls, the labelled list I send
is the *entire* world it can see — which is exactly the mechanism I use on Day 3
to build memory.

---

# Day 3 (Wed Sep 9) — Conversation Memory

**Status: complete.** Script: `chat.py` — this is now the main tool.

- [x] Loop that keeps asking for input until the user types `exit`
- [x] Store every user and model message in a list
- [x] Send the whole history with each new request
- [x] Test: tell the bot my name, then ask for it 3 messages later

## How the memory actually works

There are only three moving parts, and they fit in a loop:

```python
history = []                      # the ENTIRE memory of the bot

add_turn("user", user_input)      # 1. append what I said
response = send()                 # 2. send the WHOLE history
add_turn("model", reply)          # 3. append what the bot said
```

Step 3 is the one that's easy to forget. If I only append my own messages, the
bot cannot remember its own answers and starts contradicting itself.

## The memory test (passed)

I told it my name, asked **three** unrelated questions, then asked for the name
back. It recalled my name, what I was learning, *and* all three topics I had
asked about.

```
You: My name is Salima and I am learning Python. Please remember my name.
Bot: Nice to meet you, Salima! I've got your name saved.
  [turn 1]  messages in history: 2  | tokens sent: 41   received: 26

You: What is a variable?
Bot: Think of a variable as a labeled box where you can store data...
  [turn 2]  messages in history: 4  | tokens sent: 74   received: 60

You: What is a for loop?
Bot: A `for` loop is a way to repeat a block of code for a sequence of items...
  [turn 3]  messages in history: 6  | tokens sent: 142  received: 71

You: What is a function?
Bot: A function is a reusable block of code designed to perform a specific task...
  [turn 4]  messages in history: 8  | tokens sent: 220  received: 62

You: What is my name, and what am I learning?
Bot: Your name is Salima, and you are learning Python! You've already asked
     about variables, for loops, and functions—you're making great progress.
  [turn 5]  messages in history: 10 | tokens sent: 295  received: 33
```

## The number that matters

Look at **tokens sent** down that column:

| Turn | Messages in history | Tokens sent |
| --- | --- | --- |
| 1 | 2 | 41 |
| 2 | 4 | 74 |
| 3 | 6 | 142 |
| 4 | 8 | 220 |
| 5 | 10 | 295 |

My messages were all short and roughly the same length, yet the tokens I sent
grew more than **7x** across five turns. Nothing about turn 5's question was
expensive — the expense was the four turns of history dragged along with it.

This is the answer to the self-check question "why do longer conversations cost
more?" Every turn resends everything that came before, so cost grows roughly with
the square of the conversation length, not linearly. A 50-turn chat is not 10x a
5-turn chat, it is far worse.

It also shows why context windows exist as a hard limit. The history only grows,
so eventually it will not fit, and I would have to start trimming old turns.

## In my own words: why is resending history the same as memory?

The model is completely stateless. When a request finishes, the model retains
nothing — no session, no record that I ever spoke to it. So "memory" cannot live
inside the model, and it does not: it lives in my `history` list, on my machine.

Every time I send a request, I hand over the full transcript, labelled by role, as
if to a stranger who has never met me. The model reads that transcript, infers
what is going on, and answers the last message in context. It feels like
remembering, but it is really re-reading. The bot did not recall my name on turn
5 — it re-read me stating it on turn 1, because I shipped that sentence along with
every single request in between.

That is why the cost grows: memory and token count are the same thing.

## One small bug I fixed

When input is piped into the script for a scripted demo, the terminal does not
echo what was typed, so transcripts came out with blank `You:` lines. Fixed by
checking `sys.stdin.isatty()` and echoing the input manually when it is not a
terminal.

---

# Day 4 (Thu Sep 10) — Token Counting & Cost

**Status: complete.** Extended `chat.py`.

- [x] Locate the token usage field in the response object
- [x] Print prompt, completion, and total tokens after every reply
- [x] Research per-token pricing for input vs output
- [x] Calculate and print estimated cost per response

## Where the token usage lives

It rides along on the response object itself, in `usage_metadata`:

```python
usage = response.usage_metadata
usage.prompt_token_count      # what I sent (my messages + system prompt + history)
usage.candidates_token_count  # what the model generated
usage.total_token_count        # what I am actually billed on
```

`total_token_count` is the one to trust. It is **not always** input + output —
see the thinking-token trap I hit on Day 1.

## Pricing for `gemini-3.5-flash-lite`

| | Price per 1M tokens | Price per 1K tokens | Source | Checked |
| --- | --- | --- | --- | --- |
| Input | $0.30 | $0.0003 | [Google's official pricing page](https://ai.google.dev/gemini-api/docs/pricing) | 2026-09-09 |
| Output | $2.50 | $0.0025 | same | 2026-09-09 |

**Watch the units.** My brief asks for per-1K pricing, but Google publishes
per-1M. Per-1K is just the per-1M figure divided by 1000. Cross-checked the
official page against five independent trackers and they all agree on
$0.30 / $2.50.

**Honesty note:** I am on the **free tier**, where Google charges $0.00. So the
costs my tool prints are what the conversation *would* cost at paid-tier rates.
That is still the number worth learning to watch, and my tool labels it plainly
rather than pretending I am being billed.

Note also that the Batch tier is half price ($0.15 / $1.25), and that free-tier
usage may be used to improve Google's products, which paid usage is not.

## The formula

```python
cost = (input_tokens  / 1_000_000 * 0.30)   # input rate
     + (output_tokens / 1_000_000 * 2.50)   # output rate
```

## Real output from my tool

```
You: Hi, I am Salima.
  [turn 1]  history: 2 messages  |  tokens  in: 32   out: 20  total: 52
  cost this turn: $0.000060  (free tier: actually $0.00)

You: Explain what a token is in one sentence.
  [turn 2]  history: 4 messages  |  tokens  in: 63   out: 32  total: 95
  cost this turn: $0.000099  (free tier: actually $0.00)

You: Now explain a context window in one sentence.
  [turn 3]  history: 6 messages  |  tokens  in: 106  out: 28  total: 134
  cost this turn: $0.000102  (free tier: actually $0.00)

You: What is my name?
  [turn 4]  history: 8 messages  |  tokens  in: 141  out: 6   total: 147
  cost this turn: $0.000057  (free tier: actually $0.00)
```

I print 6 decimal places on purpose. At 2 decimals every turn reads `$0.00`,
which teaches nothing.

## Two things the cost figures revealed

**Output tokens cost about 8x more than input tokens.** $2.50 versus $0.30 per
million. On turn 1, my 32 input tokens cost $0.0000096 while the model's 20
output tokens cost $0.00005 — so 20 tokens of reply cost roughly 5x what 32
tokens of prompt did. Making the bot chatty is far more expensive than giving it
a long prompt.

**Turn 4 was my cheapest turn despite having the largest history.** It had 141
input tokens, the most of any turn, but only 6 output tokens ("Your name is
Salima!"). Short replies dominate the saving early on. But input creeps up every
single turn and never comes down, so in a long conversation the growing history
eventually becomes the main cost even if every reply stays short.

## In my own words: what is a token?

A token is a chunk of text the model treats as one unit. It is not a word and not
a letter — it sits in between. Common short words are usually one token, while
longer or unusual words get split into several pieces, and punctuation and spaces
count too. A rough rule of thumb for English is about 4 characters per token, so
roughly 750 words comes to about 1,000 tokens.

Tokens matter because they are the model's only unit of measurement. The model
does not see text, it sees a sequence of token IDs. So tokens are simultaneously
what the context window is measured in, and what I am billed for in both
directions.

## In my own words: why do longer conversations cost more?

Because memory is resending. Every request carries the entire transcript so far,
so the same early messages get paid for again on every subsequent turn. My Day 3
run showed input tokens climbing 41 → 74 → 142 → 220 → 295 while my typed
messages stayed roughly the same length.

That means cost does not grow linearly with conversation length, it grows closer
to the square of it. Turn 10 pays for turns 1 through 9 all over again. The system
prompt is included in that toll on every single turn too, which is why a long
elaborate persona is a permanent tax rather than a one-off cost.

The practical mitigations are trimming or summarising old turns once history gets
long, keeping the system prompt tight, and telling the model to be brief since
output is the expensive direction.

## Windows encoding gotcha (again)

Even with `sys.stdout.reconfigure(encoding="utf-8")` in the script, piping output
through PowerShell showed em-dashes as `ΓÇö`. The Python side was fine — PowerShell
was decoding the bytes with the wrong codepage. Fix, run once per terminal
session:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

Two different encoding bugs with two different causes: Day 2's was Python writing
cp1252, this one was PowerShell reading the wrong codepage.

---

# Day 5 (Fri Sep 11) — Polish & Error Handling

**Status: complete.** `chat.py` rewritten.

- [x] Running cumulative token and cost totals for the session
- [x] Handle bad API key, network failure, rate limits
- [x] Clear CLI formatting (ANSI colours plus spacing)
- [x] A `/reset` command to clear history

## Commands I added

| Command | What it does |
| --- | --- |
| `/reset` | Clears conversation history. Keeps cost totals, because those tokens were already spent. |
| `/stats` | Shows running session totals on demand. |
| `/help` | Lists the commands. |
| `exit` | Quits, printing the final bill. |

## Proof `/reset` really works

This is the part I liked. Before the reset the bot knew my name; immediately
after, it genuinely did not. That is evidence rather than a claim:

```
You: My name is Salima.
Bot: Nice to meet you, Salima! How can I help you with your coding journey today?
  [turn 1]  history: 2 msgs  |  tokens  in: 31  out: 19  total: 50

You: What is my name?
Bot: Your name is Salima! What would you like to code today?
  [turn 2]  history: 4 msgs  |  tokens  in: 57  out: 14  total: 71

You: /reset
History cleared. Dropped 4 messages. The bot no longer knows anything we discussed.
Session cost totals are kept -- those tokens were already spent.

You: What is my name?
Bot: I don't have access to your personal information, so I don't know your
     name yet! What should I call you?
  [turn 3]  history: 2 msgs  |  tokens  in: 30  out: 27  total: 57
```

Notice input tokens dropped from 57 back to 30 after the reset. Clearing history
made the next request cheaper — memory and cost really are the same thing.

## Failures I deliberately triggered

Every one of these was actually forced and observed, not just coded for.

| Failure | How I forced it | What the user sees |
| --- | --- | --- |
| Missing key | Copied `chat.py` to a folder with no `.env` | `Error: No API key found.` plus fix instructions, exit code 1, no traceback |
| Bad key | Set `GEMINI_API_KEY` to an invalid value | `Your API key was rejected (HTTP 401)` plus where to get a fresh one. Tool keeps running. |
| Unknown model | Set `GEMINI_MODEL=gemini-does-not-exist` | `The model ... was not found (HTTP 404)` and explicitly notes the key is fine. Also warned that no pricing was on file. |
| No network | Pointed the client at a dead port (`127.0.0.1:1`) | `Network problem. Could not reach Google.` Confirmed the SDK raises `httpx.ConnectError` and my handler catches it. |
| Rate limit | Not triggered on purpose — I did not want to burn my daily quota | Handled in code: HTTP 429 gives a "wait a minute and try again" message |
| Empty reply | Not triggered | Handled: safety-filter blocks give a "try rephrasing" message rather than crashing |

## Design decisions worth explaining

**A failed request must not corrupt history.** When a call fails I call
`history.pop()` to remove the user message I had just appended. Without this, the
history would end on an unanswered user turn, which breaks the shape of the next
request. The bad-key test confirmed history stayed at 0 messages after the
failure.

**Different status codes need different responses.** Retrying a rejected key is
pointless; retrying a 429 or a 500 is sensible. So the error handler branches on
the code rather than printing one generic message:

| Code | Meaning | Right response |
| --- | --- | --- |
| 400 / 401 / 403 | key rejected | fix the key, do not retry |
| 404 | model name wrong, **key is fine** | change the model |
| 429 | rate limit or quota | wait, then retry |
| 500+ | Google's problem | retry shortly |

**`/reset` keeps the cost totals.** Clearing memory does not un-spend money. It
would be dishonest accounting to zero the bill.

**Colours switch themselves off when piped.** `sys.stdout.isatty()` decides
whether to emit ANSI codes, because escape sequences written into a text file are
just garbage.

**Costs print to 6 decimal places.** At 2 decimals every turn reads `$0.00`,
which teaches nothing.

**A catch-all `except Exception` sits last.** Specific handlers come first, but
the tool should never hard-crash on something I failed to anticipate.

## A bug I found by using my own tool

While testing interactively I pressed **Ctrl+V** to paste a message. In a Windows
console that does not paste — it inserts a literal `\x16` control character. The
terminal showed `^V`, and the bot kept replying "It looks like your message came
through empty, Salima!"

The real problem was that `\x16` is not whitespace, so `.strip()` left it alone
and my code treated the input as valid. Every accidental paste therefore sent a
meaningless request to Google **and paid for it**, dragging the whole history
along for nothing.

Fix: filter out non-printable characters before checking whether the input is
empty, and if it is, explain why and skip the API call entirely.

```python
user_input = "".join(ch for ch in raw if ch.isprintable() or ch == "\t").strip()
```

The tool now says the input was empty, points out that Ctrl+V does not paste in a
Windows console, and confirms nothing was sent so it cost nothing. Rejected input
does not increment the turn counter either.

**To paste in a Windows terminal, right-click instead of pressing Ctrl+V.**

## Real cost data from that accidental long session

Because the blank messages kept the conversation going, I ended up with an
18-turn session — a much better illustration of the cost curve than my earlier
short tests:

| Turn | Messages in history | Tokens sent | Session total |
| --- | --- | --- | --- |
| 1 | 2 | ~30 | ~$0.00007 |
| 16 | 32 | 596 | $0.002724 (5,223 tokens) |
| 17 | 34 | 628 | $0.002970 (5,874 tokens) |
| 18 | 36 | 654 | $0.003234 (6,555 tokens) |

Input tokens per request grew roughly **20x**, from about 30 to 654, purely from
accumulated history. My messages never got longer. By turn 18 each individual
reply cost about 4x what turn 1 cost, and the replies themselves were getting
*shorter* (27 output tokens).

This is the cost curve made concrete: the growth is in the input, it is caused by
memory, and it never levels off on its own. It is also a practical argument for
the `/reset` command — clearing history is not just tidiness, it is the brake on
a bill that otherwise only climbs.

## The clearest evidence in the whole project

Continuing that long session, I asked the same question either side of a `/reset`.
This is the transcript I will use in my demo video, because the contrast is
starker than any short test:

```
You: what is a token
Bot: In AI, a token is a chunk of text—usually a word or part of a word—that
     language models use to process and generate language.
  [turn 19]  history: 38 msgs  |  tokens  in: 687  out: 6   total: 693
  this turn: $0.000221   session so far: $0.003455  (7,248 tokens)

You: what is a context window
Bot: A context window is the maximum amount of text—measured in tokens—that an
     AI model can read, remember, and process at one time. If your conversation
     gets longer than this window, the AI will start forgetting the earliest
     parts of the chat!
  [turn 20]  history: 40 msgs  |  tokens  in: 699  out: 60  total: 759
  this turn: $0.000360   session so far: $0.003814  (8,007 tokens)

You: what is my name
Bot: Your name is Salima!
  [turn 22]  history: 44 msgs  |  tokens  in: 822  out: 6   total: 828
  this turn: $0.000262   session so far: $0.004431  (9,651 tokens)

You: /reset
History cleared. Dropped 44 messages. The bot no longer knows anything we discussed.
Session cost totals are kept -- those tokens were already spent.

You: what is my name
Bot: I don't have access to your personal information, so I don't know your name
     yet! What should I call you?
  [turn 23]  history: 2 msgs   |  tokens  in: 29   out: 27  total: 56
  this turn: $0.000076   session so far: $0.004507  (9,707 tokens)
```

### Why this is the proof

The same four words, `what is my name`, asked seconds apart. First time it knew.
Second time it did not. Nothing about the model changed between those two
requests — I deleted a Python list on my own laptop, and the "memory" went with
it. That is as direct a demonstration as I can give that the model is stateless
and the memory was never inside it.

And the price tag: **input tokens fell from 822 to 29, a 28x drop.** The 822 was
not my question, my question was four words. The 822 was 44 messages of history
being re-sent so the model could appear to remember. That is exactly what memory
costs, stated as a number.

Session total for the whole conversation: 9,707 tokens, $0.004507 at paid rates
(and $0.00 actual, on the free tier).

### A nice accident

On turn 20 the bot correctly explained context windows as text measured in tokens
that the model can process at once, adding that once a conversation outgrows the
window the earliest parts get forgotten. My tool explained the concept my tool
demonstrates.

---

# Day 6 (Sat Sep 12) — Stretch Goals

**Status: all three complete.**

- [x] Streaming, so replies appear word by word
- [x] A `--model` flag to switch models from the command line
- [x] A small persona library of system prompts to switch between

## 1. Streaming

Used `client.models.generate_content_stream(...)` instead of
`generate_content(...)`, printing each chunk the moment it arrives with
`print(chunk.text, end="", flush=True)`.

The thing I had to check first: **does streaming break cost tracking?** It does
not. The usage numbers still come back, they just arrive on the **final chunk**
rather than all at once, so I keep the last one I am given:

```python
for chunk in client.models.generate_content_stream(...):
    if chunk.text:
        print(chunk.text, end="", flush=True)
    if chunk.usage_metadata:
        usage = chunk.usage_metadata   # only the final chunk carries it
```

A test prompt came back in **18 chunks** with usage intact (13 in, 374 out, 387
total).

Worth being clear about what streaming does and does not change: it does **not**
make anything cheaper, and it does not make the model faster. The model produces
tokens one at a time either way. Streaming only stops me waiting for the whole
reply before seeing any of it. It is a perceived-speed change, not a cost change,
which is why the tool says exactly that when you toggle it.

Toggle with `/stream`, or start with it off using `--no-stream`.

## 2. Command line flags

Used `argparse`. Flags override `.env`, so `.env` holds my defaults and the flags
are for one-off experiments.

```
--model NAME      pick a model, e.g. --model gemini-3.6-flash
--persona NAME    start with a persona, e.g. --persona pirate
--no-stream       wait for the full reply instead of streaming
--list-models     show models my key can use, then exit
```

`--list-models` also marks which models I have no pricing on file for, and
repeats the warning that the list is optimistic. That warning earned itself:
**`gemini-2.5-flash-lite` appears in the list but returns 404 when called**,
retired for new accounts exactly like `gemini-2.5-flash` was on Day 1. My error
handler caught it cleanly and pointed me at `--list-models`.

## 3. Persona library

Five system prompts in a dict: `tutor`, `pirate`, `teacher`, `terse`,
`rubberduck`. `/persona` lists them with the current one starred, and
`/persona NAME` switches.

### The experiment: identical question, three personas

I asked `What is 15 + 27?` three times in one session, switching persona between
each.

| Persona | Reply | In | Out | Cost |
| --- | --- | --- | --- | --- |
| `pirate` | Spat tobacco on the deck, invoked Blackbeard's rotting ghost, called me a lazy barnacle, scratched the sum in the grime with a cutlass, then conceded **42** | 40 | 175 | $0.000450 |
| `teacher` | "We do not just blurt out answers here." Asked me to break 27 into tens and ones. Never said 42. | 229 | 55 | $0.000206 |
| `terse` | `42` | 292 | 2 | $0.000093 |

**An 87x difference in output tokens for the same question.** The pirate cost
about 5x what the terse persona cost. Personality is a line item.

### The accidental best moment

After switching from `pirate` to `teacher`, the teacher opened with:

> "Put that cutlass away this instant and sit up straight!"

I had never mentioned a cutlass. The *pirate* had, two turns earlier. Switching
persona changes the system instruction but **keeps the history**, so the new
persona could see everything the old one had said and reacted to it in character.

That accidentally demonstrates the whole architecture in one line: the system
instruction and the conversation history are two separate channels. I swapped one
and left the other, and the reply proved both were present.

## Also added

`/stats` now breaks the bill down by direction and states what share of tokens
were input:

```
    input tokens    :     561   $0.000168
    output tokens   :     232   $0.000580
    total tokens    :     793
    estimated cost  : $0.000748  (free tier: actually $0.00)
    71% of those tokens were input -- that is the cost of memory.
```

That last line is the lesson of the whole project, printed automatically every
time.

---

# Day 7 (Sun Sep 13) — Review, Document & Submit

- [x] Remove leftover debug prints, add comments
- [x] Write `README.md` (description, setup, What I Learned, screenshot, stretch goals)
- [x] Push to a public GitHub repo named `prompt-lab`
- [x] Confirm the key never entered git history: `git log --all -- .env` returns nothing
- [x] Record a 2–3 minute demo video explaining token and cost tracking
- [ ] Send mentor the repo link and video link

## Submission links

| | |
| --- | --- |
| Repo | https://github.com/Iddrisusalima/prompt-lab |
| Demo video | https://www.loom.com/share/95d80e1c0e304b8c943ec364485cb061 |

## How I verified the key never leaked

Three independent checks, because "I think it's fine" is not verification:

1. `git log --all -- .env` returns nothing — the file was never committed on any
   branch, so it is absent from history, not merely absent from `HEAD`.
2. `git ls-files` lists `.env.example` but **not** `.env` — it was never tracked
   in the first place, which is what made check 1 come back clean.
3. `git check-ignore -v .env` reports `.gitignore:2:.env` — the ignore rule that
   kept it untracked, quoted with the line number that matched.

The order matters. Writing `.gitignore` *before* the key existed on disk is what
made this work; a file already tracked keeps being tracked no matter what you add
to `.gitignore` afterwards.

## Final self-check (must answer without looking anything up)

- [ ] What is a token?
- [ ] What is the difference between the system, user, and assistant roles?
- [ ] Why is sending the full conversation history how memory works?
- [ ] Why do longer conversations cost more?
- [ ] Does my tool survive a bad or missing API key?
