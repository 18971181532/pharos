"""Tests for persistent storage."""
import os
import unittest
from pharos.index import InvertedIndex
from pharos.models import Document
from pharos.storage import save_index, load_index, index_exists, delete_index
from tests.helpers import create_temp_project, cleanup_temp_project


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.root = create_temp_project({"a.py": "search engine index\n"})

    def tearDown(self):
        cleanup_temp_project(self.root)

    def _build_index(self):
        idx = InvertedIndex()
        idx.add_document(Document(
            doc_id=1, path="a.py", name="a.py", extension="py",
            language="python", size=20, mtime=1000.0,
            content="search engine index"))
        return idx

    def test_save_and_load(self):
        idx = self._build_index()
        save_index(idx, self.root)
        self.assertTrue(index_exists(self.root))
        restored = load_index(self.root)
        self.assertIsNotNone(restored)
        self.assertEqual(len(restored.documents), 1)
        self.assertGreater(restored.total_tokens(), 0)

    def test_load_missing_returns_none(self):
        self.assertIsNone(load_index(self.root))

    def test_delete(self):
        idx = self._build_index()
        save_index(idx, self.root)
        self.assertTrue(delete_index(self.root))
        self.assertFalse(index_exists(self.root))

    def test_default_index_dir(self):
        idx = self._build_index()
        idir = save_index(idx, self.root)
        self.assertTrue(os.path.isdir(os.path.join(self.root, ".pharos")))
        self.assertIn(".pharos", idir.replace("\\", "/"))

    def test_search_after_load(self):
        from pharos.engine import SearchEngine
        idx = self._build_index()
        save_index(idx, self.root)
        restored = load_index(self.root)
        engine = SearchEngine(restored)
        result = engine.search("search")
        self.assertGreater(result.total, 0)


if __name__ == "__main__":
    unittest.main()
