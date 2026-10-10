"""Tests for fuzzy matching."""
import unittest
from pharos.fuzzy import levenshtein, similarity_ratio, suggest, best_correction


class TestLevenshtein(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(levenshtein("abc", "abc"), 0)

    def test_empty(self):
        self.assertEqual(levenshtein("", "abc"), 3)
        self.assertEqual(levenshtein("abc", ""), 3)

    def test_substitution(self):
        self.assertEqual(levenshtein("cat", "car"), 1)

    def test_insertion(self):
        self.assertEqual(levenshtein("cat", "cats"), 1)

    def test_deletion(self):
        self.assertEqual(levenshtein("cats", "cat"), 1)

    def test_completely_different(self):
        self.assertEqual(levenshtein("abc", "xyz"), 3)

    def test_max_distance_shortcut(self):
        d = levenshtein("a", "abcdefghij", max_distance=2)
        self.assertGreater(d, 2)


class TestSimilarity(unittest.TestCase):
    def test_same(self):
        self.assertEqual(similarity_ratio("hello", "hello"), 1.0)

    def test_close(self):
        self.assertGreater(similarity_ratio("search", "serch"), 0.7)

    def test_both_empty(self):
        self.assertEqual(similarity_ratio("", ""), 1.0)


class TestSuggest(unittest.TestCase):
    def test_typo(self):
        vocab = ["search", "index", "engine", "result", "query"]
        out = suggest("serch", vocab)
        self.assertIn("search", out)

    def test_no_match(self):
        vocab = ["aaa", "bbb"]
        out = suggest("zzzzzzzz", vocab)
        self.assertEqual(out, [])

    def test_ranked(self):
        vocab = ["config", "configure", "configuration"]
        out = suggest("configg", vocab)
        self.assertTrue(len(out) >= 1)


class TestBestCorrection(unittest.TestCase):
    def test_correction_found(self):
        df = {"search": 10, "index": 8, "engine": 5}
        corrected = best_correction(["serch"], df)
        self.assertIsNotNone(corrected)
        self.assertIn("search", corrected)

    def test_no_correction_needed(self):
        df = {"search": 10}
        self.assertIsNone(best_correction(["search"], df))


if __name__ == "__main__":
    unittest.main()
