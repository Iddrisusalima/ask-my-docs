# What I Learned

The conceptual write-up for [Prompt Lab](../README.md). Everything here is in my
own words, and every number quoted is from my own terminal rather than from
documentation.

For the day-by-day build log, including every bug I hit, see
[`BUILD-LOG.md`](../BUILD-LOG.md).

## Contents

- [Tokens](#tokens)
- [Context windows](#context-windows)
- [Roles](#roles)
- [Training vs inference](#training-vs-inference)
- [The idea that tied it all together](#the-idea-that-tied-it-all-together)
- [Provider comparison](#provider-comparison)

---

## Tokens

A token is a chunk of text the model treats as a single unit. It is not a word and
not a letter but something in between: common short words are usually one token,
longer or unusual words get split into several pieces, and punctuation and spaces
count too. A rough rule for English is about 4 characters per token, so roughly
750 words comes to about 1,000 tokens.

Tokens matter because they are the model's only unit of measurement. The model
never sees text, it sees a sequence of token IDs. So tokens are simultaneously what
the context window is measured in and what you are billed for, in both directions.

### Surprise 1: input and output are priced differently

For `gemini-3.5-flash-lite`, input is $0.30 per million tokens and output is
$2.50 — output costs roughly **8x more per token**.

This shows up clearly in my own session totals. Across 23 turns:

| | Tokens | Share of tokens | Cost | Share of cost |
| --- | --- | --- | --- | --- |
| Input | 8,982 | 92.5% | $0.002695 | 60% |
| Output | 725 | 7.5% | $0.001813 | 40% |

Output was 7.5% of my tokens but 40% of my bill. The practical consequence is that
there are **two independent levers** for controlling cost, and they are not the
same lever: trim history to reduce input, and instruct the model to be brief to
reduce output.

### Surprise 2: total is not always input + output

I assumed `total_token_count` was just the two added together. It is not.

Testing `gemini-3.6-flash`, a request reported **4 input tokens and 2 output
tokens, but a total of 62**. The missing 56 were internal "thinking" tokens:
reasoning the model performed, billed to me, and never shown in the reply.

On `gemini-3.5-flash-lite` the arithmetic is transparent — 15 + 62 = 77 — which is
partly why I chose it. While learning to read a bill, I wanted a bill I could
verify by hand.

The lesson generalises: **trust `total_token_count`, not your own addition.**

---

## Context windows

The context window is the maximum number of tokens the model can consider at once.
It covers the system instruction, the entire conversation history, and the reply
being generated. For `gemini-3.5-flash-lite` that limit is around one million
tokens.

The part that clicked for me is that the context window is a hard ceiling on a
number that **only ever grows**. Because memory works by resending the whole
transcript, history accumulates every turn and never shrinks on its own.
Eventually a long enough conversation stops fitting, and at that point you have to
start dropping or summarising old turns.

The window is not the model's memory. It is the size of the desk you are allowed to
spread your papers on.

Interestingly, my own tool explained this back to me correctly during testing:

> A context window is the maximum amount of text—measured in tokens—that an AI
> model can read, remember, and process at one time. If your conversation gets
> longer than this window, the AI will start forgetting the earliest parts of the
> chat!

---

## Roles

A role is a label attached to each message telling the model **who said it**.
Without those labels the model would receive one undifferentiated block of text
and have no way to tell my words from its own.

| Concept | OpenAI calls it | Gemini calls it |
| --- | --- | --- |
| Standing instructions / persona | a message with `role="system"` | `system_instruction`, a **config field outside the message list** |
| What I typed | `role="user"` | `role="user"` |
| What the model said before | `role="assistant"` | `role="model"` |

This difference tripped me up and is worth stating plainly: **in Gemini there is no
`role="system"`.** The system instruction travels as configuration alongside the
conversation, not as a turn inside it. The concept is identical to OpenAI's, only
the packaging differs.

### The request payload, in full

A chat API call is not magic. It is a system instruction plus an ordered list of
labelled messages:

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

### Proving how much power sits in the system instruction

I sent the identical question `What is 15 + 27?` under three different system
instructions, changing nothing else:

| Persona | Reply | In | Out |
| --- | --- | --- | --- |
| Helpful assistant | `15 + 27 = 42.` | 43 | 11 |
| Grumpy pirate | Spat tobacco on the deck, called me a lily-livered landlubber, insulted my brain, *then* conceded forty-two | 60 | 161 |
| Strict teacher | Refused to answer at all: "can you add the ones digits (5 and 7) together first?" | 62 | 24 |

The teacher **would not say 42**. That is not a change of tone, it is a change in
what the tool *does* — produced by one sentence, with no code modified.

Two things the token counts taught me here:

- **Input tokens differed (43 / 60 / 62) despite identical messages.** The system
  instruction is itself billed as input, on every single request. A long elaborate
  persona is a tax you pay every turn for the entire conversation, not a one-off
  setup cost.
- **Output ranged from 11 to 161 tokens.** Personality is a line item.

### The accident that proved roles and history are separate channels

Later, using the persona library, I switched from `pirate` to `teacher`
mid-conversation. The teacher's first words were:

> "Put that cutlass away this instant and sit up straight!"

I had never mentioned a cutlass to the teacher. The *pirate* had, two turns
earlier. Switching persona replaces the system instruction but **keeps the
history**, so the new persona could see everything the old one said and reacted to
it in character.

One line of output, demonstrating that the system instruction and the conversation
history are two genuinely independent inputs.

---

## Training vs inference

**Training** happened once, in the past, and is finished. The model was fed an
enormous amount of text and slowly adjusted billions of internal numbers, called
weights, until it became good at predicting which token comes next. That took
months and enormous computing power. Those weights are now frozen.

**Inference** is what happens when I use it. Nothing learns and nothing is saved.
My prompt is split into tokens, pushed forward through the frozen weights once, and
the model emits the single most likely next token. That token is appended to the
input, and the process repeats to produce the token after it, until the model emits
a stop signal.

A detail that makes this concrete: running the same prompt twice gives differently
worded replies, and the output token count changes (60 one run, 62 the next). The
model is predicting token by token, not retrieving a stored answer.

---

## The idea that tied it all together

The model is completely stateless. It remembers nothing once a request finishes. So
"memory" does not live in the model — it lives in a Python list on my machine, and
it works by re-sending the whole transcript every single time.

**The bot never recalled my name. It re-read me saying it.**

### The evidence

This is the clearest thing I produced. The same four words, asked seconds apart,
either side of a `/reset`:

```
You: what is my name
Bot: Your name is Salima!
  [turn 22]  history: 44 msgs  |  tokens  in: 822   out: 6

You: /reset
History cleared. Dropped 44 messages.

You: what is my name
Bot: I don't have access to your personal information, so I don't know your name
     yet! What should I call you?
  [turn 23]  history: 2 msgs   |  tokens  in: 29    out: 27
```

First time it knew. Second time it did not. Nothing about the model changed
between those two requests — I deleted a list on my own laptop, and the "memory"
went with it.

And the price tag: **input tokens fell from 822 to 29, a 28x drop.** The 822 was
not my question; my question was four words. The 822 was 44 messages of history
being re-sent so the model could appear to remember. That is what memory costs,
stated as a number.

### Why longer conversations cost more

Because every request carries the entire transcript, the same early messages get
paid for again on every subsequent turn. My Day 3 test showed input tokens climbing
across five turns while my typed messages stayed roughly the same length:

| Turn | Messages in history | Tokens sent |
| --- | --- | --- |
| 1 | 2 | 41 |
| 2 | 4 | 74 |
| 3 | 6 | 142 |
| 4 | 8 | 220 |
| 5 | 10 | 295 |

A later, accidentally long session made the curve even clearer — input grew from
about 30 tokens to 654 by turn 18, roughly **20x**, while the replies were getting
*shorter*.

So cost does not grow linearly with conversation length, it grows closer to the
**square** of it. Turn 10 pays for turns 1 through 9 all over again.

### What to do about it

- **Trim or summarise old turns** once history gets long. This is what `/reset` is
  for, and why it is a cost control rather than just tidiness.
- **Keep the system instruction tight**, since it is billed on every single turn.
- **Ask for brevity**, because output is the expensive direction at roughly 8x.

---

## Provider comparison

Why I chose Gemini, and what I found out about the alternatives.

| | Free tier | Notes |
| --- | --- | --- |
| **Google Gemini** | Genuinely free, no card required | What I used. Free-tier content may be used to improve Google's products; paid-tier content is not. |
| **OpenAI** | Payment method required up front | Would have cost money on day one. |
| **Anthropic (Claude)** | Payment method required up front | Same. |

Gemini was the only one of the three I could start with at zero cost, which for a
learning project settled it.

### Model availability is not what the API tells you

Two findings worth recording, because both cost me time:

1. **`client.models.list()` is optimistic.** It listed `gemini-2.5-flash` and
   `gemini-2.5-flash-lite` as available. Both return **HTTP 404** when actually
   called, because they are retired for new accounts. The only reliable test of a
   model is calling it.
2. **A 404 is not an auth failure.** When `gemini-2.5-flash` failed, my first
   instinct was that my key was broken. It was not. `404` means authentication
   *succeeded* and only the model name was wrong. A bad key returns `401` or `403`.
   My tool now says this explicitly in its error message, because it is the kind
   of distinction that saves half an hour.

### Pricing across the models I tested

| Model | Input / 1M | Output / 1M | Note |
| --- | --- | --- | --- |
| `gemini-3.5-flash-lite` | $0.30 | $2.50 | My default. Transparent token accounting. |
| `gemini-3.6-flash` | $1.50 | $7.50 | Bills hidden thinking tokens. |
| `gemini-3.5-flash` | $1.50 | $9.00 | |

Source: [Google's official pricing page](https://ai.google.dev/gemini-api/docs/pricing),
checked 9 September 2026. Batch-tier rates are roughly half of standard.

---

## Self-check

The questions my brief said I should be able to answer without looking anything up.

**What is a token?** A chunk of text the model treats as one unit, roughly 4
characters of English. The model never sees text, only token IDs. Tokens are both
what the context window is measured in and what I am billed for.

**What is the difference between the system, user, and assistant roles?** `user` is
what I typed, `assistant` (called `model` in Gemini) is what the model said on
earlier turns, and the system instruction is standing guidance that shapes every
reply rather than being a turn in the conversation. In Gemini it is a config field,
not a message.

**Why is sending the full conversation history how memory works?** Because the
model is stateless and retains nothing between requests. The labelled list I send
is the entire world it can see, so re-reading is the only mechanism available.

**Why do longer conversations cost more?** Every turn re-sends everything before
it, so early messages are paid for repeatedly. Growth is closer to quadratic than
linear. I measured input tokens going from 30 to 654 across 18 turns without my
messages getting any longer.

**Does my tool survive a bad or missing API key?** Yes, and I tested both. A
missing key exits with code 1 and plain-English instructions. An invalid key
reports HTTP 401, explains where to get a fresh one, and keeps running.
