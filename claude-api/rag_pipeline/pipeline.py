"""Wire the corpus, the two indexes and the Retriever together."""

from corpus import SECTIONS
from embedders import concept_embed
from indexes import BM25Index, VectorIndex
from retriever import Retriever


def build():
    """Returns (vector_index, bm25_index, hybrid_retriever), all loaded with SECTIONS.
    The hybrid shares the same two index objects, so documents are indexed once."""
    vector, bm25 = VectorIndex(concept_embed), BM25Index()
    for section in SECTIONS:
        vector.add_document(section)
        bm25.add_document(section)
    return vector, bm25, Retriever(vector, bm25)
