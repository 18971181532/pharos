"""Pharos — a zero-dependency local full-text search engine.

Pharos builds an inverted index over your files and ranks matches with
BM25. It understands source code identifiers, handles Chinese text with
bigram tokenization, tolerates typos, and ships with an interactive
search dashboard.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
