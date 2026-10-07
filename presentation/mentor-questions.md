# Questions My Mentor Is Likely To Ask

Preparation notes, not a project record. The self-check in the brief is worded as
spoken questions, so each item below is a follow-up the first answer invites.

Read these aloud and answer without looking. Wherever you stall is the part that
needs more work.

Prepared answers for the self-check items and the follow-ups each one invites.
The README section is the written version; these are for saying out loud.

### On embeddings

**"So what actually makes two things land near each other?"**
The model was trained on an enormous amount of text and learned which words and
phrases appear in similar contexts. Nobody programmed the positions. That is why
it connects "sourdough" to "loaf from scratch" without being told they are
related.

**"Why 384 numbers?"**
That is just the output size of this particular model, `all-MiniLM-L6-v2`. A
larger model uses more numbers and captures finer distinctions, at more cost and
more storage. The important part is that the count never changes with the length
of the input.

**"Isn't this just a search index?"**
No. A search index stores words. This stores a position on a map of meaning,
which is why two passages can sit close together with no words in common.

**"Why did you write cosine similarity yourself instead of importing it?"**
The brief asked for the pipeline built manually, and I wanted to understand why
you divide by the length of both. Dividing cancels magnitude out, so a short
sentence and a long paragraph that mean the same thing still score as similar.
Length stops competing with meaning.

**"Your related sentences scored 0.62, not 0.95. Isn't that weak?"**
0.62 is strong for this model. What makes it meaningful is the 0.031 baseline
underneath it. The scores only mean something relative to each other — if I had
assumed "similar" meant above 0.8 I would have discarded every correct match.

### On chunking

**"Why 350 characters?"**
Measured, not guessed. I started at 500 from chunk-count statistics, then tested
real answer quality and found two failures. One passage was retrieved starting
mid-word, because the sentence had been cut in half and neither piece survived
whole. A larger size made it worse in the other direction: an eight-line section
about keeping an API key safe got absorbed into a 900-character chunk and its
meaning was diluted until it stopped matching the question. At 350 that section
occupies a chunk of its own. My notes are written in short sections with frequent
headings, so roughly 350 characters maps to about one section.

**"Would 350 be right for any project?"**
No. It is a property of how my documents are written. Long flowing prose with few
headings would want larger chunks. That is the real lesson — the right value
comes from the documents, not from a rule.

**"What does the overlap cost you?"**
About 1.26 times the storage, because roughly a quarter of what I save is a second
copy. It also raises the chunk count, which means more embedding calls and more
competition for the five retrieval slots, since two neighbouring chunks can both
come back for one question. Irrelevant at this size; it would matter at scale.

**"Why characters and not tokens?"**
Characters are observable. I can look at a 350-character chunk and see exactly
what is in it. Token counts need a tokenizer and make the link between the setting
and what I see on screen indirect. Token-based chunking is the better production
choice, because context limits are denominated in tokens.

### On the vector database

**"How does it find similar chunks?"**
It builds a layered graph where each chunk is linked to near neighbours, then
answers a query by walking that graph greedily toward the target, touching only a
small fraction of the data. Search time grows roughly logarithmically rather than
linearly.

**"So it is better than comparing everything?"**
Faster, not better. It is an *approximate* search — it skips comparisons on
purpose, and can miss a true nearest neighbour that a brute-force scan would
find. My earlier version was a Python list and a `for` loop, which was exact. I
adopted the database because the index survives restarting, not for speed: at 317
chunks the loop took about 15 milliseconds.

**"Did you verify the approximation does not cost you anything?"**
I measured it against the exact scan and got 10 out of 10 agreement. But I would
not present that as proof. At this corpus size the graph is small enough that the
walk reaches the right answers anyway. The approximation only starts costing
recall when the data is large enough that it must skip meaningful portions.

**"Why Chroma over Pinecone or FAISS?"**
Chroma runs in-process, persists to a folder, needs no account, and a reviewer
can run my repo without signing up for anything. Pinecone scales past one machine
but needs an account and a network round trip per query. FAISS is faster at scale
but stores no metadata, so citations would need a parallel bookkeeping layer I
would have to write and keep in sync.

### On generation and grounding

**"How do you know it is answering from my notes and not from training?"**
Two ways. `--show-prompt` prints the exact text sent to the model, so the claim
is inspectable rather than asserted. And I asked it the capital of Peru — a fact
the model certainly knows — and it declined, because the answer was not in the
retrieved passages.

**"What stops it inventing an answer?"**
The prompt explicitly permits refusal. Told only "answer from the context", a
model handed irrelevant passages still produces something, because refusing is
not an option it has been given. Told "if the passages do not contain the answer,
say so plainly", refusal becomes the compliant response.

**"Why not just reject low-similarity results?"**
I tried, and measured why it fails. A question with no answer scored 0.339 while
the weakest real answer scored 0.366. I swept thresholds across four questions:
any floor high enough to silence the unanswerable question also cut real answers
from the weaker ones down to two passages or none. The scores are not calibrated
across questions — a question worded like my notes scores high throughout, one
phrased differently scores low throughout even when its top hit is correct.

**"How did you test it?"**
Ten questions: eight with answers in the notes, two without. All eight were
answered with correct citations, both unanswerable ones were declined. I opened
the cited files to confirm each claim is really there. One answer was partial — it
recovered one of four numbered steps — and I recorded that rather than rounding up.
It is a small sample on a small corpus and I wrote the questions, so it is a real
result rather than a benchmark.

### On the project as a whole

**"Explain the pipeline in under a minute."**
Chunk, embed, store, retrieve, generate. My notes get cut into overlapping
350-character pieces. Each piece becomes 384 numbers and goes into a database
that searches by closeness. A question becomes 384 numbers using the same model,
the database returns the five closest pieces, those pieces go into a prompt that
says answer only from these and say so if they do not contain the answer, and the
reply comes back citing which pieces it used.

**"When would you use fine-tuning instead?"**
Fine-tuning changes how a model behaves — tone, format, style. RAG changes what
it knows. My notes change often and I need to verify answers against a source, so
RAG is right. If I wanted every reply in the voice of a terse code reviewer, that
is a fine-tuning job.

**"What would you do next?"**
Semantic chunking — splitting on topic shifts rather than fixed character counts.
Both of my chunking failures came from cuts landing in places that ignored the
meaning of the text, and that is exactly what semantic chunking addresses.

**"What is the weakest part?"**
The dataset is five documents and I wrote the test questions. Retrieval quality
on a few hundred chunks tells me the pipeline works, not that it works well. I
would want a larger corpus and questions written by someone else before trusting
the numbers.
