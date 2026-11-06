# Practice: A multi-index RAG pipeline

Companion to the lesson
[A multi-index RAG pipeline](https://academy.claude.com/courses/building-with-the-claude-api/a-multi-index-rag-pipeline)
(*Building with the Claude API*, lesson 38).

**Idea from the lesson:** semantic (vector) search and lexical (BM25) search fail in
opposite ways. Put both behind one interface, send the query to both, and merge the
rankings with **reciprocal rank fusion (RRF)**:

```
RRF_score(d) = sum over indexes i of  1 / (k_rrf + rank_i(d))
```

RRF uses ranks, not raw scores, because cosine similarity and BM25 scores are on
different scales and cannot be added.

| File | What it is |
|---|---|
| `corpus.py` | 10-section fictional Q4 report. Plants IDs (`INC-2023-Q4-011`, `INC-2023-Q3-004`) and synonym traps ("attrition" vs "turnover") |
| `indexes.py` | `SearchIndex` protocol, `BM25Index`, `VectorIndex`, shared tokenizer |
| `embedders.py` | Offline **stand-in** embedder (concept lexicon), see the note below |
| `retriever.py` | The lesson's `Retriever`, completed (the lesson shows only a skeleton) |
| `pipeline.py` | Builds both indexes + the hybrid retriever over the corpus |
| `test_retriever.py` | Unit tests incl. the lesson's worked RRF example (0.833 / 0.75 / 0.583) |
| `eval_retrieval.py` | Compares vector vs BM25 vs hybrid on 10 queries: hit@1, hit@3, MRR |
| `ask.py` | Full RAG: retrieve top sections, then Claude answers with citations |

## Run it (from `claude-api/`)

```bash
PYTHONPATH=rag_pipeline uv run python -m unittest discover -s rag_pipeline -v   # offline
uv run python rag_pipeline/eval_retrieval.py --verbose                           # offline
uv run python rag_pipeline/ask.py "what happened with INC-2023-Q4-011?"         # 1 Haiku call
```

The first two need no API key. Only `ask.py` calls Claude.

## About the embedder (read this)

The course uses a real embeddings API. Anthropic does not offer one, and this
project has only an Anthropic key, so `embedders.py` is a **toy stand-in**: hand-made
concepts, one dimension each. It imitates two properties of real embeddings
(paraphrases land close together; identifiers carry no meaning) but it is not a
semantic model, and its eval numbers say nothing about real embedding quality.

To use a real model, pass any `str -> list[float]` function:

```python
vector = VectorIndex(my_embed_fn)   # e.g. a wrapper around an embeddings provider
```

Hybrid results with a real embedder will differ from the stand-in's.

## What I observed (stand-in embedder, 10 queries)

The 8 unit tests pass (including the lesson's 0.833 / 0.75 / 0.583 example).
`eval_retrieval.py`:

| method | hit@1 | hit@3 | MRR | missed entirely |
|---|---|---|---|---|
| vector | 8/10 | 8/10 | 0.80 | 2 |
| bm25 | 6/10 | 7/10 | 0.68 | 2 |
| hybrid (k_rrf=60 and 1) | 8/10 | 10/10 | 0.90 | 0 |

- Vector found nothing for the two exact-ID-only queries (rows 1-2); BM25 found nothing
  for the two pure paraphrases (rows 8-9). Hybrid recovered all four, so it never
  missed. That is the lesson's point.
- **Hybrid is not a free win.** Row 5 ("who broke into our systems...") was #1 for
  vector alone but #2 for hybrid, because BM25 ranked the right section 4th and pulled
  a wrong one up. Row 1 landed #2 in every method that found it (section 6 also
  contains that ID).
- Hybrid's hit@1 only ties vector (8/10); the gains are in hit@3 and MRR.
- Caveat: toy embedder, a corpus and queries I wrote, and my own relevance labels. Treat
  this as an illustration of the mechanism, not a benchmark.

## What to look for

- **The unit test is the lesson.** Section 2 is 1st in one index and 2nd in the other,
  so it wins on agreement. The lesson's prose uses `k=1` but its code defaults to
  `k_rrf=60`; the test checks both give the same order.
- **Read the eval table by row, not only by the summary.** Look for queries where vector
  misses an exact ID, where BM25 misses a paraphrase, and, importantly, whether
  hybrid ever does *worse* than the better single index. Fusion is not guaranteed to win.
- Relevance judgments (the "want" column) are mine and some are arguable, for example
  the Q4 incident ID appears in two sections. Disagree and change them.

## Exercises

1. Run the tests, then change `k_rrf` in `test_retriever.py` to 0 and 1000. How does the
   gap between rank 1 and rank 2 change, and when does the order flip?
2. For `"what happened with INC-2023-Q4-011?"`, run `eval_retrieval.py --verbose` and
   explain each method's top 3 from the section text.
3. Add a query where you expect hybrid to lose. Does it?
4. Add a third index (the lesson's `???Index`): for example a `TitleIndex` that matches
   only section titles. Pass it to `Retriever(vector, bm25, title)` with no change to
   `Retriever`. What does that prove about the shared interface?
5. Weighted RRF: give BM25 weight 2. Does it fix ID queries without breaking paraphrases?
6. Replace `concept_embed` with a real embedding model and re-run the eval.
7. Combine with the evaluation practice: grade `ask.py` answers with a model grader.
   Does a better retrieval rank translate into better answers?

## Next lesson

[Extended thinking](https://academy.claude.com/courses/building-with-the-claude-api/extended-thinking)
