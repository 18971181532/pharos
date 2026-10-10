"""Tests for the indexer orchestration and CLI."""
import json
import os
import sys
import unittest
from io import StringIO

from pharos.indexer import Indexer
from pharos.engine import SearchEngine
from pharos.cli import build_parser, cmd_index, cmd_search, cmd_stats, main
from tests.helpers import (
    create_temp_project, cleanup_temp_project,
    SAMPLE_PYTHON, SAMPLE_MARKDOWN, SAMPLE_CHINESE,
)


class TestIndexer(unittest.TestCase):
    def setUp(self):
        self.root = create_temp_project({
            "config_parser.py": SAMPLE_PYTHON,
            "notes.md": SAMPLE_MARKDOWN,
            "chinese.txt": SAMPLE_CHINESE,
        })

    def tearDown(self):
        cleanup_temp_project(self.root)

    def test_build(self):
        indexer = Indexer(self.root)
        stats, changes = indexer.build()
        self.assertEqual(stats.document_count, 3)
        self.assertEqual(changes["added"], 3)
        self.assertGreater(stats.token_count, 0)
        self.assertGreater(stats.unique_terms, 0)

    def test_incremental_unchanged(self):
        indexer = Indexer(self.root)
        indexer.build()
        _, changes2 = indexer.build()
        self.assertEqual(changes2["added"], 0)
        self.assertEqual(changes2["unchanged"], 3)

    def test_incremental_update(self):
        indexer = Indexer(self.root)
        indexer.build()
        with open(os.path.join(self.root, "notes.md"), "w", encoding="utf-8") as fh:
            fh.write("brand new content about indexing\n")
        _, changes = indexer.build()
        self.assertEqual(changes["updated"], 1)

    def test_incremental_removal(self):
        indexer = Indexer(self.root)
        indexer.build()
        os.unlink(os.path.join(self.root, "notes.md"))
        _, changes = indexer.build()
        self.assertEqual(changes["removed"], 1)
        self.assertEqual(len(indexer.index.documents), 2)

    def test_rebuild(self):
        indexer = Indexer(self.root)
        indexer.build()
        stats, changes = indexer.build(incremental=False)
        self.assertEqual(stats.document_count, 3)

    def test_languages_in_stats(self):
        indexer = Indexer(self.root)
        stats, _ = indexer.build()
        self.assertIn("python", stats.languages)
        self.assertIn("markdown", stats.languages)

    def test_top_terms(self):
        indexer = Indexer(self.root)
        stats, _ = indexer.build()
        self.assertGreater(len(stats.top_terms), 0)

    def test_end_to_end_search(self):
        indexer = Indexer(self.root)
        indexer.build()
        engine = SearchEngine(indexer.index)
        result = engine.search("configuration")
        self.assertGreater(result.total, 0)

    def test_chinese_end_to_end(self):
        indexer = Indexer(self.root)
        indexer.build()
        engine = SearchEngine(indexer.index)
        result = engine.search("搜索")
        self.assertGreater(result.total, 0)


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.root = create_temp_project({
            "main.py": SAMPLE_PYTHON,
            "readme.md": SAMPLE_MARKDOWN,
        })

    def tearDown(self):
        cleanup_temp_project(self.root)

    def test_parser(self):
        parser = build_parser()
        args = parser.parse_args(["index", "/tmp"])
        self.assertEqual(args.command, "index")
        args = parser.parse_args(["search", "query", "/tmp"])
        self.assertEqual(args.command, "search")
        args = parser.parse_args(["stats", "/tmp"])
        self.assertEqual(args.command, "stats")

    def _run(self, argv):
        old = sys.stdout
        sys.stdout = StringIO()
        try:
            code = main(argv)
            out = sys.stdout.getvalue()
        finally:
            sys.stdout = old
        return code, out

    def test_index_then_search(self):
        code, out = self._run(["index", self.root])
        self.assertEqual(code, 0)
        self.assertIn("PHAROS", out)
        self.assertIn("Documents", out)

        code, out = self._run(["search", "configuration", self.root])
        self.assertEqual(code, 0)
        self.assertIn("main.py", out)

    def test_search_json(self):
        self._run(["index", self.root])
        code, out = self._run(["search", "--json", "configuration", self.root])
        data = json.loads(out)
        self.assertIn("hits", data)
        self.assertGreater(data["total"], 0)

    def test_stats(self):
        self._run(["index", self.root])
        code, out = self._run(["stats", self.root])
        self.assertEqual(code, 0)
        self.assertIn("Documents", out)

    def test_index_nonexistent(self):
        code, _ = self._run(["index", "/nonexistent/path/12345"])
        self.assertEqual(code, 1)

    def test_search_without_index(self):
        empty = create_temp_project({})
        try:
            code, _ = self._run(["search", "x", empty])
            self.assertEqual(code, 1)
        finally:
            cleanup_temp_project(empty)

    def test_no_command(self):
        code, out = self._run([])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
