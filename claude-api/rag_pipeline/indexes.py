"""Two search indexes with the SAME interface (the SearchIndex protocol).

That shared interface is the lesson's key design point: the Retriever can fuse
any number of indexes without knowing how each one works.
"""

import math
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Protocol, Tuple

Document = Dict[str, Any]
SearchResult = Tuple[Document, float]  # (document, raw score), best first


class SearchIndex(Protocol):
    def add_document(self, document: Document) -> None: ...

    def search(self, query_text: str, k: int = 3) -> List[SearchResult]:
        """Up to k results, best first. Documents the index cannot match at all
        are NOT returned, so they get no rank (and no RRF credit) from this index."""
        ...


# ------------------------------------------------------------------ tokenizing
_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_STOPWORDS = frozenset(
    "a an and are as at be by did do does for from had has have how i in into is it its of on or "
    "our that the their this to was we were what when where which who why will with".split()
)


def tokenize(text: str) -> List[str]:
    """Lowercase word tokens. Hyphenated IDs are kept whole AND split into parts,
    so 'INC-2023-Q4-011' matches both exactly and partially."""
    tokens: List[str] = []
    for tok in _TOKEN.findall(text.lower()):
        parts = [tok] + (tok.split("-") if "-" in tok else [])
        tokens.extend(p for p in parts if p not in _STOPWORDS)
    return tokens


def doc_text(document: Document) -> str:
    return f"{document['title']}\n{document['content']}"


# ------------------------------------------------------------------------ BM25
class BM25Index:
    """Lexical search (Okapi BM25): rewards rare shared words, so exact IDs and
    names score high; it knows nothing about meaning or synonyms."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self._docs: List[Document] = []
        self._tfs: List[Counter] = []
        self._lengths: List[int] = []

    def add_document(self, document: Document) -> None:
        tokens = tokenize(doc_text(document))
        self._docs.append(document)
        self._tfs.append(Counter(tokens))
        self._lengths.append(len(tokens))

    def search(self, query_text: str, k: int = 3) -> List[SearchResult]:
        if not self._docs:
            return []
        n = len(self._docs)
        avg_len = sum(self._lengths) / n
        scored = []
        for doc, tf, length in zip(self._docs, self._tfs, self._lengths):
            score = 0.0
            for term in set(tokenize(query_text)):
                if term not in tf:
                    continue
                df = sum(1 for other in self._tfs if term in other)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                f = tf[term]
                score += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * length / avg_len))
            if score > 0:
                scored.append((doc, score))
        return sorted(scored, key=lambda r: r[1], reverse=True)[:k]


# ---------------------------------------------------------------------- vector
class VectorIndex:
    """Semantic search: embed text into a vector, rank by cosine similarity.

    `embed` is any function str -> list[float]. In the course that is a call to an
    embeddings API; here it is pluggable so the pipeline runs offline.
    """

    def __init__(self, embed: Callable[[str], List[float]]):
        self._embed = embed
        self._docs: List[Document] = []
        self._vectors: List[List[float]] = []

    def add_document(self, document: Document) -> None:
        self._docs.append(document)
        self._vectors.append(self._embed(doc_text(document)))

    def search(self, query_text: str, k: int = 3) -> List[SearchResult]:
        q = self._embed(query_text)
        scored = [(doc, _cosine(q, v)) for doc, v in zip(self._docs, self._vectors)]
        scored = [r for r in scored if r[1] > 0]
        return sorted(scored, key=lambda r: r[1], reverse=True)[:k]


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
