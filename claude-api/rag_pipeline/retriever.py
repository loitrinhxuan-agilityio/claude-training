"""The lesson's Retriever: query every index, merge with reciprocal rank fusion.

RRF_score(d) = sum over indexes i of  1 / (k_rrf + rank_i(d))      (rank starts at 1)

Only RANKS are used, never raw scores, because a cosine similarity (0..1) and a
BM25 score (unbounded) live on different scales and cannot be added.
"""

from typing import List

from indexes import Document, SearchIndex, SearchResult


class Retriever:
    def __init__(self, *indexes: SearchIndex):
        if len(indexes) == 0:
            raise ValueError("At least one index must be provided")
        self._indexes = list(indexes)

    def add_document(self, document: Document) -> None:
        for index in self._indexes:
            index.add_document(document)

    def search(self, query_text: str, k: int = 3, k_rrf: int = 60, candidates: int = 20) -> List[SearchResult]:
        """Top `k` documents by fused score.

        k_rrf       RRF constant. Larger values flatten the gap between rank 1 and rank 2.
        candidates  how many results to pull from EACH index before fusing.
        """
        fused: dict = {}  # doc id -> [document, score]
        for index in self._indexes:
            for rank, (doc, _raw_score) in enumerate(index.search(query_text, k=candidates), start=1):
                entry = fused.setdefault(doc["id"], [doc, 0.0])
                entry[1] += 1.0 / (k_rrf + rank)
        # Python's sort is stable, so equal scores keep first-seen order.
        merged = sorted(fused.values(), key=lambda e: e[1], reverse=True)
        return [(doc, score) for doc, score in merged[:k]]
