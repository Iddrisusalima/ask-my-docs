---
title: "Memory is just re-sending: what building a CLI chat tool taught me about LLM cost"
published: false
tags: python, ai, llm, showdev
cover_image: https://raw.githubusercontent.com/Iddrisusalima/prompt-lab/main/docs/screenshots/memory-and-reset.png
---

I asked a chatbot my name. It told me. Ten seconds later it had no idea who I was.

Nothing about the model changed between those two questions. I deleted a list on
my own laptop, and the memory went with it, because that list *was* the memory.

This post is about what I found building Prompt Lab, a CLI chat tool for Google's
Gemini models that prints the tokens and cost of every reply. The code is
[on GitHub](https://github.com/Iddrisusalima/prompt-lab). I'm using the
`google-genai` SDK and `gemini-3.5-flash-lite`.

## Statelessness is the whole design constraint

Language models retain nothing between requests. No session, no history on the
server. So "memory" cannot live in the model, and it doesn't. It lives in a list
in your process, and it works by re-sending the entire conversation every time.

Which means memory and cost are the same thing. Every turn pays again for every
turn before it.

![Architecture of one conversation turn](https://raw.githubusercontent.com/Iddrisusalima/prompt-lab/main/docs/architecture.png)

Commands like `/reset` and `/stats` are intercepted before the network call, so
they cost nothing. Everything else appends to history, then the system instruction
plus the **entire** history goes to the API.

## Building the request

The history is a list of `types.Content`, each carrying a role:

```python
from google.genai import types

history: list[types.Content] = []

def add_turn(role: str, text: str) -> None:
    """role is "user" for my messages, "model" for the bot's replies."""
    history.append(
        types.Content(role=role, parts=[types.Part.from_text(text=text)])
    )
```

The first gotcha is here. **Gemini has no `role="system"`.** OpenAI passes the
system prompt as a message inside the list; Gemini passes it as configuration
*alongside* the list:

```python
def config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(system_instruction=system_prompt)

def send_once() -> tuple[str, types.GenerateContentResponseUsageMetadata]:
    response = client.models.generate_content(
        model=MODEL,
        contents=history,        # the whole conversation, every single time
        config=config(),
    )
    return (response.text or "").strip(), response.usage_metadata
```

That `contents=history` line is the entire memory mechanism. One turn looks like:

```python
add_turn("user", user_input)      # 1. append what I said
reply, usage = send_once()        # 2. send the WHOLE history
add_turn("model", reply)          # 3. append what it said
```

Step 3 is the one that's easy to miss. Skip it and the model never sees its own
previous answers, so it starts contradicting itself.

## Reading the bill

Usage rides along on the response object:

```python
usage = response.usage_metadata
usage.prompt_token_count       # input: my messages + system prompt + history
usage.candidates_token_count   # output: what the model generated
usage.total_token_count        # what you are actually billed on
```

Input and output are priced separately, so the cost function bills them at
different rates. Google publishes per million tokens:

```python
PRICING_PER_1M = {
    "gemini-3.5-flash-lite": (0.30, 2.50),   # (input, output) USD per 1M tokens
}

def cost_of(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * INPUT_PER_1M
        + output_tokens / 1_000_000 * OUTPUT_PER_1M
    )
```

Note the ratio: `2.50 / 0.30` means **output costs roughly 8x more per token than
input**. The `/stats` command prints the running bill split by direction:

![Session totals showing input and output tokens costed separately](https://raw.githubusercontent.com/Iddrisusalima/prompt-lab/main/docs/screenshots/session-stats.png)

In that session, 74% of the tokens were input, which is history being re-sent. But
look at the cost column: 156 output tokens cost $0.000390 while 451 input tokens
cost only $0.000135. A quarter of the tokens, three quarters of the price. That
gives you two independent levers, not one: trim history to cut input, and ask for
brevity to cut output.

## The measurement

The same four words, asked seconds apart, either side of a `/reset`:

![The same question asked either side of a reset, with token counts visible](https://raw.githubusercontent.com/Iddrisusalima/prompt-lab/main/docs/screenshots/memory-and-reset.png)

```text
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

822 input tokens down to 29. Twenty-eight times cheaper for an identical question.
The 822 wasn't my question. It was 44 messages of history being re-sent.

Across another session input went from 41 tokens on turn 1 to 654 by turn 18,
while my typed messages stayed the same length and the replies got *shorter*.
Growth is closer to quadratic than linear: turn 10 pays for turns 1 through 9
again.

## Two more gotchas

### `total_token_count` is not always input + output

I assumed it was addition. Testing `gemini-3.6-flash`, one request reported **4
input tokens, 2 output tokens, and a total of 62**. The missing 56 were internal
reasoning tokens, billed but never shown in the reply. Trust
`total_token_count`, not your own arithmetic.

### With streaming, usage arrives on the final chunk

Switching to `generate_content_stream()` doesn't break cost tracking, but the
usage data isn't there from the start. Keep the last one you're handed:

```python
for chunk in client.models.generate_content_stream(
    model=MODEL, contents=history, config=config()
):
    if chunk.text:
        print(chunk.text, end="", flush=True)
    if chunk.usage_metadata:
        usage = chunk.usage_metadata   # only the final chunk carries it
```

Streaming changes perceived speed, not price.

## Failing without corrupting state

Two things mattered here. First, status codes need different handling, because
retrying a rejected key is pointless while retrying a rate limit is sensible:

```python
if code in (400, 401, 403):
    return "Your API key was rejected. Check GEMINI_API_KEY for typos."
if code == 404:
    return (
        f"The model '{MODEL}' was not found. Your key is fine - a 404 means "
        "auth succeeded and only the model name is wrong."
    )
if code == 429:
    return "Rate limit or quota exceeded. Wait a minute and try again."
```

That 404 branch exists because I wasted half an hour assuming my key was broken. A
404 means authentication *succeeded*.

I triggered each of these deliberately rather than coding for them and hoping.
Here's an invalid key, reported and survived:

![An invalid API key producing a clear HTTP 401 message with zero turns in history](https://raw.githubusercontent.com/Iddrisusalima/prompt-lab/main/docs/screenshots/error-handling.png)

Two details in that output matter. The tool keeps running instead of exiting. And
the session totals report zero turns and zero messages in history, which proves
the rollback below actually fired.

Second, a failed request must not leave a half-finished conversation:

```python
try:
    reply, usage = send_once()
except errors.APIError as err:
    history.pop()        # roll back the user turn we just appended
    print(explain_api_error(err))
    continue
```

Without that `pop()`, history ends on an unanswered user turn, which breaks the
shape of the next request.

## What I'd fix next

`cost_of()` takes input and output, which means it misses thinking tokens
entirely. On a model that uses them, I'm under-reporting by roughly 10x. My code
contradicts my own write-up on that point.

History is also never trimmed. It only grows, so a long enough conversation will
stop fitting in the context window. The fix is dropping oldest turns in pairs to
keep roles alternating, or summarising the old prefix into one synthetic turn.

## Takeaway

Making a stateless model appear to remember means re-sending everything, and that
is exactly what you pay for.

If you're building on an LLM, print your token counts once and watch them climb.
It changes how you think about conversation length, system prompt size, and when
to throw history away.

Code, architecture notes and a day-by-day build log:
**[github.com/Iddrisusalima/prompt-lab](https://github.com/Iddrisusalima/prompt-lab)**
