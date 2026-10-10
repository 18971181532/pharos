"""Tests for the search engine."""
import unittest
from pharos.index import InvertedIndex
from pharos.engine import SearchEngine
from pharos.models import Document


def doc(did, path, content, language="python"):
    return Document(
        doc_id=did, path=path, name=path.split("/")[-1], extension="py",
        language=language, size=len(content), mtime=1000.0 + did, content=content,
    )


class TestSearchEngine(unittest.TestCase):
    def setUp(self):
        self.idx = InvertedIndex()
        self.idx.add_document(doc(1, "config_parser.py",
            "Parse configuration files and load database settings. "
            "The parser handles JSON configuration."))
        self.idx.add_document(doc(2, "search_engine.py",
            "The search engine builds an inverted index and ranks documents "
            "using BM25 scoring for fast search."))
        self.idx.add_document(doc(3, "readme.md",
            "# Search Engine\nA fast local search engine with typo tolerance.",
            language="markdown"))
        self.engine = SearchEngine(self.idx)

    def test_basic_search(self):
        result = self.engine.search("search")
        self.assertGreater(result.total, 0)
        paths = [h.path for h in result.hits]
        self.assertIn("search_engine.py", paths)

    def test_ranking_relevance(self):
        # A document mentioning search twice should rank among top hits.
        result = self.engine.search("search")
        top_paths = [h.path for h in result.hits[:2]]
        self.assertTrue("search_engine.py" in top_paths or "readme.md" in top_paths)

    def test_boolean_and(self):
        result = self.engine.search("search engine")
        for hit in result.hits:
            # every result should contain both concepts
            self.assertIn(hit.path, {"search_engine.py", "readme.md"})

    def test_prohibition(self):
        result = self.engine.search("search -json")
        paths = [h.path for h in result.hits]
        self.assertNotIn("config_parser.py", paths)

    def test_field_search(self):
        result = self.engine.search("name:readme")
        paths = [h.path for h in result.hits]
        self.assertIn("readme.md", paths)

    def test_phrase_search(self):
        result = self.engine.search('"inverted index"')
        paths = [h.path for h in result.hits]
        self.assertIn("search_engine.py", paths)

    def test_wildcard_search(self):
        result = self.engine.search("pars*")
        paths = [h.path for h in result.hits]
        self.assertIn("config_parser.py", paths)

    def test_snippets_generated(self):
        result = self.engine.search("configuration")
        hit = next(h for h in result.hits if h.path == "config_parser.py")
        self.assertTrue(len(hit.snippets) > 0)
        self.assertTrue(any("[[" in s for s in hit.snippets))

    def test_matched_terms(self):
        result = self.engine.search("search")
        hit = result.hits[0]
        self.assertIn("search", hit.matched_terms)

    def test_no_results(self):
        result = self.engine.search("zzzznotpresent")
        self.assertEqual(result.total, 0)
        self.assertEqual(result.hits, [])

    def test_empty_query(self):
        result = self.engine.search("")
        self.assertEqual(result.total, 0)

    def test_fuzzy_correction(self):
        # "serch" is a typo for "search"; should suggest/return results.
        result = self.engine.search("serch")
        self.assertIsNotNone(result.corrected_query)
        self.assertGreater(result.total, 0)

    def test_timing_recorded(self):
        result = self.engine.search("search")
        self.assertGreaterEqual(result.took_ms, 0)

    def test_limit(self):
        result = self.engine.search("search", limit=1)
        self.assertLessEqual(len(result.hits), 1)

    def test_to_dict_serializable(self):
        result = self.engine.search("search")
        d = result.to_dict()
        self.assertIn("hits", d)
        self.assertIn("total", d)


class TestChineseSearch(unittest.TestCase):
    def setUp(self):
        self.idx = InvertedIndex()
        self.idx.add_document(doc(1, "notes.txt",
            "搜索引擎建立倒排索引，支持快速检索中文内容。"))
        self.idx.add_document(doc(2, "config.txt",
            "配置文件包含数据库连接信息。"))
        self.engine = SearchEngine(self.idx)

    def test_chinese_query(self):
        result = self.engine.search("搜索")
        self.assertGreater(result.total, 0)

    def test_chinese_index_query(self):
        result = self.engine.search("索引")
        paths = [h.path for h in result.hits]
        self.assertIn("notes.txt", paths)


if __name__ == "__main__":
    unittest.main()
