"""The inverted index.

For every indexed field and term we keep a *postings list* mapping
document ids to term frequency and the positions at which the term
occurs. Positions enable phrase queries; per-field postings enable field
boosts and ``path:`` queries.

The implementation is deliberately dependency-free: postings are plain
dicts/lists that serialize directly to JSON.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

from pharos.models import Document, Field
from pharos.tokenizer import tokenize, tokenize_with_positions

# Posting: doc_id -> {"tf": int, "positions": [int]}
Posting = Dict[str, dict]


class InvertedIndex:
    """An in-memory inverted index over documents."""

    def __init__(self) -> None:
        # field -> term -> {doc_id: {"tf": n, "positions": [...]}}
        self.postings: Dict[str, Dict[str, Dict[int, dict]]] = {
            f.value: defaultdict(dict) for f in Field
        }
        # doc_id -> field -> token count (document length per field)
        self.lengths: Dict[int, Dict[str, int]] = defaultdict(
            lambda: {f.value: 0 for f in Field}
        )
        self.documents: Dict[int, Document] = {}
        # path -> doc_id, used for incremental updates
        self.path_to_id: Dict[str, int] = {}
        self._next_id = 1

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------
    def add_document(self, doc: Document) -> int:
        """Index a document, returning its doc_id.

        If a document with the same path already exists it is replaced.
        """
        existing = self.path_to_id.get(doc.path)
        if existing is not None:
            self.remove_document(existing)

        doc.doc_id = self._next_id
        self._next_id += 1
        self.documents[doc.doc_id] = doc
        self.path_to_id[doc.path] = doc.doc_id

        self._index_field(doc, Field.PATH, doc.path)
        self._index_field(doc, Field.NAME, doc.name)
        self._index_field(doc, Field.CONTENT, doc.content)
        self._index_field(doc, Field.TAGS, " ".join(doc.tags))
        return doc.doc_id

    def _index_field(self, doc: Document, field: Field, text: str) -> None:
        if not text:
            return
        pairs = tokenize_with_positions(text)
        field_postings = self.postings[field.value]
        seen_positions: Dict[str, List[int]] = defaultdict(list)
        for term, pos in pairs:
            seen_positions[term].append(pos)
        for term, positions in seen_positions.items():
            field_postings[term][doc.doc_id] = {
                "tf": len(positions),
                "positions": positions,
            }
        self.lengths[doc.doc_id][field.value] = len(pairs)

    def remove_document(self, doc_id: int) -> bool:
        doc = self.documents.pop(doc_id, None)
        if doc is None:
            return False
        self.path_to_id.pop(doc.path, None)
        for field in Field:
            fp = self.postings[field.value]
            empty_terms = []
            for term, posting in fp.items():
                if doc_id in posting:
                    del posting[doc_id]
                    if not posting:
                        empty_terms.append(term)
            for term in empty_terms:
                del fp[term]
        self.lengths.pop(doc_id, None)
        return True

    def clear(self) -> None:
        self.postings = {f.value: defaultdict(dict) for f in Field}
        self.lengths = defaultdict(lambda: {f.value: 0 for f in Field})
        self.documents.clear()
        self.path_to_id.clear()
        self._next_id = 1

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    def document_frequency(self, term: str,
                           field: Field = Field.CONTENT) -> int:
        return len(self.postings[field.value].get(term, {}))

    def posting(self, term: str, field: Field = Field.CONTENT
                ) -> Dict[int, dict]:
        return self.postings[field.value].get(term, {})

    def docs_for_terms(self, terms: Iterable[str],
                       field: Field = Field.CONTENT
                       ) -> Dict[int, Set[str]]:
        """Return doc_id -> set of matched terms for the given terms."""
        result: Dict[int, Set[str]] = defaultdict(set)
        for term in terms:
            for doc_id in self.postings[field.value].get(term, {}):
                result[doc_id].add(term)
        return result

    def all_terms(self, field: Field = Field.CONTENT) -> List[str]:
        return list(self.postings[field.value].keys())

    def term_document_frequencies(self, field: Field = Field.CONTENT
                                  ) -> Dict[str, int]:
        return {term: len(post) for term, post in
                self.postings[field.value].items()}

    def average_length(self, field: Field = Field.CONTENT) -> float:
        values = [lengths[field.value] for lengths in self.lengths.values()]
        values = [v for v in values if v > 0]
        return sum(values) / len(values) if values else 0.0

    def total_tokens(self, field: Field = Field.CONTENT) -> int:
        return sum(lengths[field.value] for lengths in self.lengths.values())

    # ------------------------------------------------------------------
    # Phrase matching
    # ------------------------------------------------------------------
    def phrase_docs(self, phrase_terms: List[str],
                    field: Field = Field.CONTENT) -> Set[int]:
        """Find documents containing terms consecutively (a phrase)."""
        if not phrase_terms:
            return set()
        first = self.posting(phrase_terms[0], field)
        candidates = set(first.keys())
        for term in phrase_terms[1:]:
            candidates &= set(self.posting(term, field).keys())
            if not candidates:
                return set()

        matches: Set[int] = set()
        for doc_id in candidates:
            base_positions = self.posting(phrase_terms[0], field)[doc_id]["positions"]
            for start in base_positions:
                ok = True
                # Terms may not map 1:1 to characters for CJK bigrams, so
                # we require each subsequent term to begin at or after the
                # previous position (monotonic adjacency).
                cursor = start
                for term in phrase_terms[1:]:
                    positions = self.posting(term, field)[doc_id]["positions"]
                    nxt = next((p for p in positions if p >= cursor), None)
                    if nxt is None:
                        ok = False
                        break
                    cursor = nxt
                if ok:
                    matches.add(doc_id)
                    break
        return matches

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "next_id": self._next_id,
            "documents": {str(did): doc.to_dict()
                          for did, doc in self.documents.items()},
            "postings": {
                field: {
                    term: {str(did): p for did, p in posting.items()}
                    for term, posting in terms.items()
                }
                for field, terms in self.postings.items()
            },
            "lengths": {str(did): lengths for did, lengths in self.lengths.items()},
            "path_to_id": self.path_to_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InvertedIndex":
        idx = cls()
        idx._next_id = data.get("next_id", 1)
        idx.documents = {
            int(did): Document.from_dict(ddoc)
            for did, ddoc in data.get("documents", {}).items()
        }
        idx.path_to_id = data.get("path_to_id", {})
        for field in Field:
            fdata = data.get("postings", {}).get(field.value, {})
            converted = {}
            for term, posting in fdata.items():
                converted[term] = {int(did): p for did, p in posting.items()}
            idx.postings[field.value] = defaultdict(dict, converted)
        idx.lengths = defaultdict(
            lambda: {f.value: 0 for f in Field},
            {int(did): lengths for did, lengths in data.get("lengths", {}).items()},
        )
        return idx
