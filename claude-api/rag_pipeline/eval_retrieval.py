"""Does hybrid retrieval actually beat each index alone? Measure it.

Each query has ONE section I judge to be the right answer. For every method we
record the rank of that section, then report hit@1, hit@3 and MRR.

Run from claude-api/:
    uv run python rag_pipeline/eval_retrieval.py
    uv run python rag_pipeline/eval_retrieval.py --verbose     # show every method's top 3
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import build  # noqa: E402

# (query, expected section id, what the query tests)
QUERIES = [
    ("what happened with INC-2023-Q4-011?", "2", "exact ID (appears in sections 2 and 6)"),
    ("INC-2023-Q3-004 summary", "10", "exact ID, a near-miss of the Q4 one"),
    ("customer tickets caused by INC-2023-Q4-011", "6", "exact ID + topic words"),
    ("Project Phoenix stability", "2", "named project, words match literally"),
    ("who broke into our systems and took customer data?", "10", "paraphrase: no shared words"),
    ("why did the order service crash after the release?", "2", "paraphrase of the outage"),
    ("are we exposed to lawsuits over the vendor agreement?", "5", "paraphrase + misleading word 'vendor'"),
    ("how healthy are our finances and will profits grow?", "3", "paraphrase: no shared words"),
    ("employee turnover and remote work", "4", "synonyms: attrition / hybrid"),
    ("emissions targets", "9", "easy for both"),
]

METHODS = ["vector", "bm25", "hybrid k=60", "hybrid k=1"]


def ranked_ids(method, vector, bm25, hybrid, query):
    if method == "vector":
        results = vector.search(query, k=10)
    elif method == "bm25":
        results = bm25.search(query, k=10)
    elif method == "hybrid k=60":
        results = hybrid.search(query, k=10, k_rrf=60)
    else:
        results = hybrid.search(query, k=10, k_rrf=1)
    return [doc["id"] for doc, _ in results]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    vector, bm25, hybrid = build()
    ranks = {m: [] for m in METHODS}  # rank of the expected section; None = not retrieved

    print(f"{'#':<3}{'query':<54}{'want':>5}" + "".join(f"{m:>13}" for m in METHODS))
    for n, (query, want, note) in enumerate(QUERIES, 1):
        row = ""
        for m in METHODS:
            ids = ranked_ids(m, vector, bm25, hybrid, query)
            rank = ids.index(want) + 1 if want in ids else None
            ranks[m].append(rank)
            row += f"{('#' + str(rank)) if rank else '-':>13}"
            if args.verbose:
                print(f"     {m:<12} top3={ids[:3]}")
        print(f"{n:<3}{query[:52]:<54}{want:>5}{row}")
        if args.verbose:
            print(f"     ({note})")

    print(f"\n{'method':<14}{'hit@1':>8}{'hit@3':>8}{'MRR':>8}{'missed':>9}")
    for m in METHODS:
        r, n = ranks[m], len(QUERIES)
        hit1 = sum(1 for x in r if x == 1)
        hit3 = sum(1 for x in r if x and x <= 3)
        mrr = sum(1 / x for x in r if x) / n
        print(f"{m:<14}{hit1:>5}/{n:<2}{hit3:>5}/{n:<2}{mrr:>8.2f}{sum(x is None for x in r):>9}")
    print("\n'-' / missed = the expected section was not retrieved at all by that method.")


if __name__ == "__main__":
    main()
