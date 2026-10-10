"""Tests for the tokenizer."""
import unittest
from pharos.tokenizer import (
    split_identifier, tokenize, tokenize_with_positions,
    term_frequency, _stem, STOP_WORDS_EN,
)


class TestSplitIdentifier(unittest.TestCase):
    def test_camel_case(self):
        self.assertEqual(split_identifier("parseConfig"), ["parse", "config"])

    def test_pascal_case(self):
        self.assertEqual(split_identifier("ConfigLoader"), ["config", "loader"])

    def test_snake_case(self):
        self.assertEqual(split_identifier("load_database_settings"),
                         ["load", "database", "settings"])

    def test_acronym(self):
        parts = split_identifier("HTTPServer")
        self.assertIn("http", parts)
        self.assertIn("server", parts)

    def test_plain_word(self):
        self.assertEqual(split_identifier("search"), ["search"])

    def test_digits(self):
        self.assertIn("parse", split_identifier("parseV2"))


class TestStemmer(unittest.TestCase):
    def test_ing(self):
        self.assertEqual(_stem("running"), "runn")  # conservative strip

    def test_plural(self):
        self.assertEqual(_stem("indexes"), "index")

    def test_short_words_unchanged(self):
        self.assertEqual(_stem("go"), "go")
        self.assertEqual(_stem("the"), "the")


class TestTokenize(unittest.TestCase):
    def test_basic(self):
        terms = tokenize("Search the index")
        self.assertIn("search", terms)
        # stop word removed
        self.assertNotIn("the", terms)

    def test_code_identifier_expanded(self):
        terms = tokenize("parseConfigValue")
        self.assertIn("parse", terms)
        self.assertIn("config", terms)
        self.assertIn("value", terms)

    def test_lowercased(self):
        terms = tokenize("BM25 Ranking")
        joined = " ".join(terms)
        self.assertIn("rank", joined)

    def test_chinese_bigrams(self):
        terms = tokenize("搜索引擎")
        # unigrams + bigrams present
        self.assertIn("搜索", terms)
        self.assertIn("索引", terms)
        self.assertIn("索", terms)

    def test_chinese_search_matches(self):
        # A query bigram should appear in the indexed bigrams.
        doc_terms = tokenize("建立倒排索引")
        query_terms = tokenize("索引")
        for q in query_terms:
            self.assertIn(q, doc_terms)

    def test_positions_monotonic(self):
        pairs = tokenize_with_positions("parse config search")
        positions = [p for _, p in pairs]
        self.assertEqual(positions, sorted(positions))

    def test_positions_content(self):
        pairs = tokenize_with_positions("hello world")
        words = [t for t, _ in pairs]
        self.assertIn("hello", words)
        self.assertIn("world", words)

    def test_term_frequency(self):
        tf = term_frequency("index index index search")
        self.assertEqual(tf["index"], 3)

    def test_empty(self):
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize_with_positions(""), [])

    def test_stopwords(self):
        self.assertIn("return", STOP_WORDS_EN)
        terms = tokenize("return value")
        self.assertNotIn("return", terms)
        self.assertIn("value", terms)


if __name__ == "__main__":
    unittest.main()
