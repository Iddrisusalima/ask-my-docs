# Learning Guardrails

These rules exist because the point of this project is comprehension, not
delivery speed. They override normal "be maximally helpful" instincts.

## No RAG frameworks

The brief is explicit: build the pipeline manually, do not reach for a framework
that hides the steps.

Do not add, import, or suggest: LangChain, LlamaIndex, Haystack, LangGraph,
EmbedChain, or any wrapper that bundles chunk/embed/store/retrieve into one
call.

Allowed, because each is a single visible layer rather than a hidden pipeline:

- `sentence-transformers` — the embedding model itself
- `openai` — direct API client
- `chromadb` — the vector database
- `pypdf` — PDF text extraction
- `numpy` — arithmetic

If a framework genuinely seems like the right answer, raise it with the user
and let them decide. Never install one silently.

## Write the mechanics out in full

Where a concept is being taught, prefer explicit code over a library call, and
comment the reasoning:

- cosine similarity is hand-written in `src/similarity.py`, not imported
- chunking is hand-written, not delegated to a text splitter
- the prompt that grounds answers in context is assembled visibly, not templated
  away

Optimising this code into something terse and clever is a regression. Clarity
beats elegance here.

## Do not write the user's explanations for them

Several deliverables must be in the user's own words:

- the README "What I Learned" section
- "what an embedding is" without using "vector" as a cop-out
- the plain-language description of semantic search
- the note on why splitting documents matters
- the comparison of the chosen vector DB against an alternative

For these, supply the raw material — measurements, results, tables, mechanical
facts — and, at most, a clearly labelled draft for the user to react to and
rewrite. Never present a finished paragraph as though it can be submitted as-is.
A mentor asking a follow-up question in the demo will expose borrowed wording
immediately.

Everything else — implementation code, docstrings, comments, setup instructions,
result tables — is fair game to write outright.

## Measure, then conclude

When the brief says to experiment (chunk size, overlap, top-k), actually run the
variations and record real numbers before drawing a conclusion. A plausible
sounding recommendation with no measurement behind it is worse than useless,
because the user cannot defend it when asked "why 500 and not 1000?".

## Keep the pipeline stages separable

Each stage should be runnable and inspectable on its own. The user needs to be
able to demo "here is what chunking produced", "here is what retrieval returned",
"here is the prompt that went to the model" as distinct steps in the video.
Avoid collapsing stages into one opaque function.
