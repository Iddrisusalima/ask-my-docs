# Requirements — Ask My Docs

## Introduction

Ask My Docs is a command-line RAG tool that answers questions about a folder of
the user's own PDF and markdown notes. It answers from retrieved passages of
those notes only, and tells the user which document each answer came from.

Every stage is built explicitly — document loading, chunking, embedding, vector
storage, retrieval, and grounded generation — because the project's purpose is
for the user to understand the pipeline, not to assemble it from a framework.

Requirements below are grouped by capability and cover all three weeks. Each
acceptance criterion is testable by running the tool.

### Scope boundaries

Out of scope for this project: a web or GUI frontend, multi-user support,
incremental re-indexing of changed files only, OCR of scanned PDFs, reranking
models, hybrid keyword+semantic search, and conversational follow-up memory.
These are worth knowing about and can be named in the README as possible
extensions, but must not consume Week 3 time.

---

## Requirement 1 — Embedding generation

**User story:** As a learner, I want to convert any text into an embedding
through a single interface, so that I can swap embedding providers without
rewriting the rest of the pipeline.

### Acceptance criteria

1.1. WHEN a non-empty string is embedded THEN the system SHALL return a
fixed-length sequence of floating point numbers.

1.2. WHEN texts of differing lengths are embedded with the same model THEN the
system SHALL return sequences of identical length.

1.3. WHEN `EMBEDDING_BACKEND` is `local` THEN the system SHALL use a Sentence
Transformers model running on the user's machine and SHALL require no API key.

1.4. WHEN `EMBEDDING_BACKEND` is `openai` THEN the system SHALL call the OpenAI
embeddings API, and IF `OPENAI_API_KEY` is absent THEN the system SHALL raise an
error naming the missing variable and offering the local backend as an
alternative.

1.5. WHEN `EMBEDDING_BACKEND` holds an unrecognised value THEN the system SHALL
raise an error listing the supported values.

1.6. WHEN an empty or whitespace-only string is embedded THEN the system SHALL
raise an error rather than returning a meaningless embedding.

1.7. WHEN multiple texts are embedded together THEN the system SHALL issue one
batched operation and SHALL return results in the same order as the inputs.

1.8. WHEN the embedding model is used for the first time in a process THEN the
system SHALL load it lazily, so that importing the module stays fast.

---

## Requirement 2 — Semantic similarity measurement

**User story:** As a learner, I want to compare two embeddings myself, so that I
understand what "relevance" actually means numerically rather than trusting a
library.

### Acceptance criteria

2.1. The system SHALL compute cosine similarity from its own arithmetic — dot
product divided by the product of both magnitudes — and SHALL NOT import a
similarity function from a third-party library.

2.2. WHEN two embeddings of differing length are compared THEN the system SHALL
raise an error explaining that the inputs likely came from different models.

2.3. WHEN either embedding has zero magnitude THEN the system SHALL raise an
error explaining that a zero vector has no direction.

2.4. WHEN an embedding is compared against itself THEN the system SHALL return
a similarity of 1.0 within floating point tolerance.

2.5. The system SHALL provide an all-pairs comparison over a set of embeddings,
returning a square matrix.

2.6. WHEN sentences on a shared topic are compared against mutually unrelated
sentences THEN the within-topic average similarity SHALL exceed the unrelated
average by a clearly visible margin.

---

## Requirement 3 — Document loading

**User story:** As a user, I want the tool to read my own notes folder, so that
answers come from my material rather than a curated sample.

### Acceptance criteria

3.1. WHEN given a folder path THEN the system SHALL discover all `.md`, `.markdown`,
`.txt`, and `.pdf` files within it, including files in subfolders.

3.2. WHEN a PDF is loaded THEN the system SHALL extract its text page by page
and SHALL retain the page number alongside each extracted passage.

3.3. WHEN a markdown or text file is loaded THEN the system SHALL read it as
UTF-8, and IF decoding fails THEN the system SHALL report the offending filename
and continue with the remaining files.

3.4. WHEN a PDF yields no extractable text, as with a scanned image THEN the
system SHALL warn that the file was skipped and name it, rather than failing
silently or crashing.

3.5. WHEN the target folder does not exist THEN the system SHALL raise an error
stating the resolved path it attempted.

3.6. WHEN the target folder exists but contains no supported files THEN the
system SHALL report this clearly, naming the extensions it does support.

3.7. WHEN a document is loaded THEN the system SHALL record its source filename,
so that citations can name it later.

---

## Requirement 4 — Chunking

**User story:** As a learner, I want to split documents into overlapping
fixed-size pieces, so that retrieval returns a precise passage instead of a
whole document.

### Acceptance criteria

4.1. WHEN a document is chunked with a given size and overlap THEN the system
SHALL produce chunks of at most that size in characters.

4.2. WHEN overlap is greater than zero THEN each chunk after the first SHALL
begin with the final `overlap` characters of the preceding chunk.

4.3. WHEN overlap is greater than or equal to chunk size THEN the system SHALL
raise an error, because such a configuration cannot advance through the text.

4.4. WHEN a document is shorter than the chunk size THEN the system SHALL return
it as a single chunk.

4.5. WHEN chunking produces a chunk that is empty or whitespace-only THEN the
system SHALL discard it, so that it never reaches the embedder.

4.6. WHEN a chunk is created THEN the system SHALL attach its source filename,
its index within the document, and its character offset, and for PDFs its page
number.

4.7. The system SHALL expose chunk size and overlap as parameters so that
different values can be compared empirically.

4.8. WHEN chunk boundaries are chosen THEN the system SHALL prefer to break at a
paragraph or sentence boundary near the target size, rather than mid-word,
provided that doing so stays within the size limit.

---

## Requirement 5 — Vector storage

**User story:** As a user, I want my embedded chunks kept in a real vector
database, so that retrieval stays fast as my notes grow and survives a restart.

### Acceptance criteria

5.1. The system SHALL persist embeddings and their chunk text to a local Chroma
database on disk, requiring no API key or network service.

5.2. WHEN chunks are indexed THEN the system SHALL store, for each chunk, its
embedding, its text, and its source metadata together.

5.3. WHEN the ingestion step runs against a collection that already holds data
THEN the system SHALL replace the existing collection rather than appending
duplicates.

5.4. WHEN ingestion completes THEN the system SHALL report the number of
documents processed and chunks indexed.

5.5. WHEN the embedding model changes THEN stored embeddings become invalid, and
the system SHALL record which model produced a collection so that the mismatch
can be detected and reported rather than silently returning nonsense.

5.6. WHEN a query is issued against an empty or missing collection THEN the
system SHALL report that ingestion has not been run yet and name the command to
run it.

---

## Requirement 6 — Retrieval

**User story:** As a user, I want my question matched against the most relevant
passages in my notes, so that the answer is grounded in the right material.

### Acceptance criteria

6.1. WHEN a question is submitted THEN the system SHALL embed it with the same
model used for the indexed chunks.

6.2. WHEN retrieving THEN the system SHALL return the top-k most similar chunks,
ordered from most to least similar.

6.3. WHEN retrieval returns results THEN the system SHALL expose each chunk's
similarity score alongside its text and source, so that relevance can be
inspected rather than assumed.

6.4. The system SHALL accept top-k as a parameter, so that 3, 5, and 10 can be
compared.

6.5. WHEN the requested top-k exceeds the number of chunks in the collection
THEN the system SHALL return all available chunks without error.

6.6. WHEN a relevance floor is configured AND no chunk meets it THEN the system
SHALL return an empty result set, so that "nothing relevant found" is
distinguishable from "here are the least bad matches".

---

## Requirement 7 — Retrieval quality logging

**User story:** As a learner, I want retrieval results written to a file, so that
I can review match quality later instead of losing it when the terminal scrolls.

### Acceptance criteria

7.1. WHEN a question is answered THEN the system SHALL append to a log file the
timestamp, the question, the configuration used, and each retrieved chunk with
its score and source.

7.2. The system SHALL write logs to a gitignored directory, so that review
material never becomes repository noise.

7.3. WHEN the log directory does not exist THEN the system SHALL create it.

7.4. Logged chunk text SHALL be truncated to a readable preview length rather
than dumping full chunks, so the log stays skimmable.

---

## Requirement 8 — Grounded answer generation

**User story:** As a user, I want answers built from my retrieved notes rather
than the model's general knowledge, so that I can trust what the tool tells me
about my own material.

### Acceptance criteria

8.1. WHEN generating an answer THEN the system SHALL assemble a prompt
containing the retrieved chunks as context, visibly and inspectably in the
source code.

8.2. The prompt SHALL instruct the model to answer only from the provided
context and to state plainly when the context is insufficient.

8.3. WHEN the retrieved context contains a fact that contradicts common
knowledge THEN the system SHALL answer from the context.

8.4. WHEN a question is asked whose answer appears nowhere in the notes THEN the
system SHALL say it cannot find the answer in the provided documents, and SHALL
NOT fabricate one.

8.5. WHEN the assembled context would exceed the configured character budget
THEN the system SHALL include chunks in similarity order until the budget is
reached, and SHALL report how many were omitted.

8.6. The system SHALL support printing the exact assembled prompt on request,
so that the grounding step can be demonstrated rather than described.

8.7. WHEN the LLM API call fails THEN the system SHALL report the failure
clearly and SHALL NOT lose the user's question or the retrieved context.

---

## Requirement 9 — Source citations

**User story:** As a user, I want each answer to name the document it came from,
so that I can verify it against the original note.

### Acceptance criteria

9.1. WHEN an answer is produced THEN the system SHALL display the source
filename and chunk identifier for every chunk that informed it.

9.2. WHEN a cited source is from a PDF THEN the citation SHALL include the page
number.

9.3. The system SHALL number the context passages in the prompt and instruct the
model to reference those numbers, so that citations map to specific passages
rather than a general list of consulted files.

9.4. WHEN displaying citations THEN the system SHALL include each source's
similarity score.

---

## Requirement 10 — Command-line interface

**User story:** As a user, I want to ingest my notes and ask questions from the
terminal, so that the tool is usable and demonstrable without extra setup.

### Acceptance criteria

10.1. The system SHALL provide an ingestion command that loads, chunks, embeds,
and indexes a folder of documents.

10.2. The system SHALL provide a query command accepting a question, either as
an argument for one-shot use or interactively in a loop.

10.3. The ingestion and query commands SHALL accept chunk size, overlap, and
top-k as options, defaulting to the values chosen through experiment.

10.4. WHEN any command fails THEN the system SHALL exit with a non-zero status
and print an actionable message rather than a traceback.

10.5. Each pipeline stage SHALL be runnable and inspectable on its own, so that
the demo video can show chunking, retrieval, and generation as distinct steps.

---

## Requirement 11 — Learning artifacts

**User story:** As a learner, I want my findings recorded as I go, so that the
README and the demo rest on real measurements rather than recollection.

### Acceptance criteria

11.1. The system SHALL maintain a per-week learning log under `notes/`.

11.2. WHEN a parameter is tuned THEN the log SHALL record the values tried and
what was observed, not only the value chosen.

11.3. The log SHALL contain the user's own explanations of: what an embedding is
without using the word "vector"; what semantic search means in plain language;
why splitting documents matters; and how the chosen vector database compares to
one alternative.

11.4. Prose that the user must be able to defend verbally SHALL be written by
the user. Automated assistance may supply measurements, tables, and clearly
labelled drafts only.

---

## Requirement 12 — Submission package

**User story:** As a learner, I want the repository to stand on its own, so that
my mentor can run it and assess it without asking me questions.

### Acceptance criteria

12.1. The repository SHALL be pushed to a public or shared-access GitHub
repository named `ask-my-docs`.

12.2. The repository SHALL include a `sample-notes/` folder of non-sensitive
documents sufficient to run the tool end to end.

12.3. The README SHALL include: a one-paragraph description of the tool and the
dataset used; setup instructions covering how to add your own documents; a
"What I Learned" section covering embeddings, chunking, and the RAG pipeline;
the chosen chunk size and top-k values with the reasoning behind them; and a
screenshot of a real question with its answer and cited source.

12.4. The repository SHALL NOT contain API keys, `.env`, the virtual
environment, the vector database, or the model cache.

12.5. WHEN a reviewer follows the README setup steps on a clean machine THEN the
tool SHALL run without further instruction.

12.6. A 3–4 minute demo video SHALL show the ingestion step and 2–3 live
questions, explaining what happens at each pipeline stage.
