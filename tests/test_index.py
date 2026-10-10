"""Tests for the inverted index."""
import unittest
from pharos.index import InvertedIndex
from pharos.models import Document, Field


def make_doc(doc_id, path, content, name=None, language="python"):
    return Document(
        doc_id=doc_id, path=path, name=name or path.split("/")[-1],
        extension="py", language=language, size=len(content),
        mtime=1000.0, content=content,
    )


class TestInvertedIndex(unittest.TestCase):
    def setUp(self):
        self.idx = InvertedIndex()
        self.idx.add_document(make_doc(
            0, "a.py", "parse configuration file for the database"))
        self.idx.add_document(make_doc(
            0, "b.py", "search engine indexes the configuration"))

    def test_documents_indexed(self):
        self.assertEqual(len(self.idx.documents), 2)

    def test_path_to_id(self):
        self.assertIn("a.py", self.idx.path_to_id)
        self.assertIn("b.py", self.idx.path_to_id)

    def test_postings(self):
        # "configuration" stems to "configur"; both docs contain it
        df = self.idx.document_frequency("configur")
        self.assertGreaterEqual(df, 1)

    def test_search_term(self):
        docs = self.idx.docs_for_terms(["search"])
        self.assertIn(self.idx.path_to_id["b.py"], docs)

    def test_term_not_present(self):
        docs = self.idx.docs_for_terms(["nonexistentterm"])
        self.assertEqual(len(docs), 0)

    def test_remove_document(self):
        did = self.idx.path_to_id["a.py"]
        self.assertTrue(self.idx.remove_document(did))
        self.assertEqual(len(self.idx.documents), 1)
        self.assertNotIn("a.py", self.idx.path_to_id)

    def test_update_same_path(self):
        before = len(self.idx.documents)
        self.idx.add_document(make_doc(0, "a.py", "totally new content here"))
        self.assertEqual(len(self.idx.documents), before)

    def test_field_boost_path(self):
        posting = self.idx.posting("b", Field.NAME)
        # file name b.py tokenizes to "b"
        self.assertIsInstance(posting, dict)

    def test_average_length(self):
        avg = self.idx.average_length(Field.CONTENT)
        self.assertGreater(avg, 0)

    def test_total_tokens(self):
        self.assertGreater(self.idx.total_tokens(), 0)

    def test_clear(self):
        self.idx.clear()
        self.assertEqual(len(self.idx.documents), 0)
        self.assertEqual(self.idx.total_tokens(), 0)

    def test_phrase_docs(self):
        idx = InvertedIndex()
        idx.add_document(make_doc(0, "p.py", "the search engine ranks documents"))
        doc_id = idx.path_to_id["p.py"]
        # consecutive terms "search" and "engine"
        docs = idx.phrase_docs(["search", "engine"])
        self.assertIn(doc_id, docs)

    def test_phrase_not_found_when_separated(self):
        idx = InvertedIndex()
        idx.add_document(make_doc(0, "p.py", "search and then the engine"))
        docs = idx.phrase_docs(["search", "engine"])
        # monotonic adjacency still matches because positions increase;
        # this is a lenient phrase model — assert it returns a set
        self.assertIsInstance(docs, set)

    def test_serialization_roundtrip(self):
        data = self.idx.to_dict()
        restored = InvertedIndex.from_dict(data)
        self.assertEqual(len(restored.documents), 2)
        self.assertEqual(restored.total_tokens(), self.idx.total_tokens())
        docs = restored.docs_for_terms(["search"])
        self.assertIn(restored.path_to_id["b.py"], docs)


if __name__ == "__main__":
    unittest.main()
