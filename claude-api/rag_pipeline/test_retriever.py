"""Reproduces the lesson's worked RRF example, plus edge cases.

Run from claude-api/:  uv run python -m unittest discover -s rag_pipeline -v
"""

import unittest

from retriever import Retriever


class FakeIndex:
    """An index that returns a fixed ranking, to test fusion in isolation."""

    def __init__(self, ranking):
        self._ranking = ranking

    def add_document(self, document):
        pass

    def search(self, query_text, k=3):
        return [({"id": i}, 1.0 / (r + 1)) for r, i in enumerate(self._ranking)][:k]


# The lesson, query "INC-2023-Q4-011":
VECTOR = FakeIndex(["2", "7", "6"])  # Section 2 rank 1, Section 7 rank 2, Section 6 rank 3
BM25 = FakeIndex(["6", "2", "7"])    # Section 6 rank 1, Section 2 rank 2, Section 7 rank 3


class RRFTests(unittest.TestCase):
    def test_lesson_worked_example_with_k_rrf_1(self):
        # The lesson's prose uses k=1:  S2 = 1/2+1/3, S6 = 1/4+1/2, S7 = 1/3+1/4
        results = Retriever(VECTOR, BM25).search("INC-2023-Q4-011", k=3, k_rrf=1)
        scores = {doc["id"]: score for doc, score in results}
        self.assertEqual([doc["id"] for doc, _ in results], ["2", "6", "7"])
        self.assertAlmostEqual(scores["2"], 0.833, places=3)
        self.assertAlmostEqual(scores["6"], 0.750, places=3)
        self.assertAlmostEqual(scores["7"], 0.583, places=3)

    def test_default_k_rrf_60_gives_the_same_order(self):
        # The lesson's code defaults to 60 while its prose uses 1; the order holds either way.
        results = Retriever(VECTOR, BM25).search("INC-2023-Q4-011", k=3)
        self.assertEqual([doc["id"] for doc, _ in results], ["2", "6", "7"])

    def test_k_limits_results(self):
        self.assertEqual(len(Retriever(VECTOR, BM25).search("q", k=1)), 1)

    def test_document_found_by_only_one_index_is_still_returned(self):
        results = Retriever(FakeIndex(["a"]), FakeIndex(["b"])).search("q", k=5)
        self.assertEqual({doc["id"] for doc, _ in results}, {"a", "b"})

    def test_agreement_between_indexes_beats_a_single_first_place(self):
        # "x" is 1st in one index only; "y" is 2nd in both, so fusion should prefer "y".
        results = Retriever(FakeIndex(["x", "y"]), FakeIndex(["z", "y"])).search("q", k=3)
        self.assertEqual(results[0][0]["id"], "y")

    def test_single_index_keeps_its_order(self):
        results = Retriever(VECTOR).search("q", k=3)
        self.assertEqual([doc["id"] for doc, _ in results], ["2", "7", "6"])

    def test_no_indexes_is_an_error(self):
        with self.assertRaises(ValueError):
            Retriever()

    def test_add_document_reaches_every_index(self):
        seen = []

        class Spy(FakeIndex):
            def add_document(self, document):
                seen.append(document["id"])

        Retriever(Spy([]), Spy([])).add_document({"id": "d1"})
        self.assertEqual(seen, ["d1", "d1"])


if __name__ == "__main__":
    unittest.main()
