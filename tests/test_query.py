"""Tests for the query parser."""
import unittest
from pharos.query import parse_query, collect_terms, TermNode, BoolNode
from pharos.models import Field


class TestTermParsing(unittest.TestCase):
    def test_single_term(self):
        ast = parse_query("search")
        self.assertIsInstance(ast, TermNode)
        self.assertEqual(ast.term, "search")

    def test_implicit_and(self):
        ast = parse_query("search engine")
        self.assertIsInstance(ast, BoolNode)
        self.assertEqual(len(ast.must), 2)

    def test_or(self):
        ast = parse_query("search OR find")
        self.assertIsInstance(ast, BoolNode)
        self.assertGreaterEqual(len(ast.should), 2)

    def test_prohibition(self):
        ast = parse_query("search -test")
        leaves = collect_terms(ast)
        prohibited = [t for t in leaves if t.prohibited]
        self.assertEqual(len(prohibited), 1)
        self.assertEqual(prohibited[0].term, "test")

    def test_phrase(self):
        ast = parse_query('"exact phrase here"')
        self.assertIsInstance(ast, TermNode)
        self.assertTrue(ast.phrase)
        self.assertEqual(ast.term, "exact phrase here")

    def test_field_scope(self):
        ast = parse_query("path:readme")
        self.assertIsInstance(ast, TermNode)
        self.assertEqual(ast.field, Field.PATH)

    def test_name_field_alias(self):
        ast = parse_query("filename:config")
        self.assertEqual(ast.field, Field.NAME)

    def test_wildcard(self):
        ast = parse_query("parse*")
        self.assertTrue(ast.wildcard)
        self.assertEqual(ast.term, "parse")

    def test_grouping(self):
        ast = parse_query("(a OR b) c")
        self.assertIsInstance(ast, BoolNode)
        # c must be present
        must_terms = collect_terms(BoolNode(must=ast.must))
        self.assertTrue(any(t.term == "c" for t in must_terms) or
                        any(t.term == "c" for t in collect_terms(ast)))

    def test_empty_query(self):
        ast = parse_query("")
        self.assertIsInstance(ast, BoolNode)

    def test_collect_terms(self):
        ast = parse_query("a b OR c -d")
        terms = collect_terms(ast)
        names = {t.term for t in terms}
        self.assertEqual(names, {"a", "b", "c", "d"})


if __name__ == "__main__":
    unittest.main()
