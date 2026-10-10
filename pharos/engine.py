"""The search engine: query evaluation, BM25 ranking and snippets."""
from __future__ import annotations

import math
import re
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from pharos.fuzzy import best_correction
from pharos.index import InvertedIndex
from pharos.models import Field, Hit, SearchResult
from pharos.query import BoolNode, TermNode, collect_terms, parse_query
from pharos.tokenizer import tokenize

# Field length normalization weights and static boosts. Paths and file
# names are short but highly meaningful, so they get a strong boost.
FIELD_BOOST = {
    Field.PATH: 3.0,
    Field.NAME: 4.0,
    Field.TAGS: 2.0,
    Field.CONTENT: 1.0,
}

# BM25 tuning constants.
BM25_K1 = 1.5
BM25_B = 0.75

SNIPPET_RADIUS = 48
MAX_SNIPPETS = 3
MAX_RESULTS = 200


class SearchEngine:
    """Evaluates queries against an :class:`InvertedIndex`."""

    def __init__(self, index: InvertedIndex):
        self.index = index

    # ------------------------------------------------------------------
    # Candidate retrieval per term
    # ------------------------------------------------------------------
    def _term_candidates(self, node: TermNode
                         ) -> Tuple[Dict[int, float], Set[str], Field]:
        """Return (doc_id -> partial score, matched terms, effective field)."""
        field = node.field or Field.CONTENT
        scores: Dict[int, float] = defaultdict(float)
        matched: Set[str] = set()
        idx = self.index

        if node.phrase:
            terms = node.expanded_terms()
            target_field = field
            docs = idx.phrase_docs(terms, target_field)
            for did in docs:
                scores[did] += 2.0 * FIELD_BOOST[target_field]
            matched.update(terms)
            return scores, matched, target_field

        terms = node.expanded_terms()
        search_fields = [field]
        # Content queries also lightly match path/name so file names rank.
        if field == Field.CONTENT:
            search_fields = [Field.CONTENT, Field.NAME, Field.PATH]

        for term in terms:
            for f in search_fields:
                posting = idx.posting(term, f)
                if not posting:
                    if node.wildcard:
                        posting = self._prefix_posting(term, f)
                if not posting:
                    continue
                n_docs = max(len(idx.documents), 1)
                df = len(posting)
                idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
                avg_len = idx.average_length(f) or 1.0
                for did, p in posting.items():
                    tf = p["tf"]
                    dl = idx.lengths[did][f.value] or avg_len
                    norm = 1 - BM25_B + BM25_B * (dl / avg_len)
                    bm25 = idf * ((tf * (BM25_K1 + 1)) / (tf + BM25_K1 * norm))
                    scores[did] += bm25 * FIELD_BOOST[f]
                    matched.add(term)
        return scores, matched, field

    def _prefix_posting(self, prefix: str, field: Field) -> Dict[int, dict]:
        merged: Dict[int, dict] = defaultdict(lambda: {"tf": 0, "positions": []})
        for term, posting in self.index.postings[field.value].items():
            if term.startswith(prefix):
                for did, p in posting.items():
                    merged[did]["tf"] += p["tf"]
                    merged[did]["positions"].extend(p["positions"])
        return dict(merged)

    # ------------------------------------------------------------------
    # Boolean evaluation
    # ------------------------------------------------------------------
    def _eval(self, node, context: Dict[int, float],
              matched_terms: Dict[int, Set[str]]):
        if isinstance(node, TermNode):
            scores, terms, _ = self._term_candidates(node)
            for did, score in scores.items():
                context[did] = context.get(did, 0.0) + score
                matched_terms[did].update(terms)
            return set(scores.keys())

        if isinstance(node, BoolNode):
            must_sets = []
            should_sets = []
            for child in node.must:
                must_sets.append(self._eval(child, context, matched_terms))
            for child in node.should:
                should_sets.append(self._eval(child, context, matched_terms))
            not_sets = []
            for child in node.must_not:
                not_sets.append(self._eval(child, context, matched_terms))

            if must_sets:
                result = set.intersection(*must_sets) if len(must_sets) > 1 else set(must_sets[0])
            elif should_sets:
                result = set.union(*should_sets)
            else:
                result = set()
            if should_sets:
                # Pure OR node already produced union; mixed queries keep
                # must docs but also require at least one should match.
                if not must_sets:
                    result = set.union(*should_sets)
            for ns in not_sets:
                result -= ns
            return result
        return set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search(self, query: str, *, limit: int = 50,
               fuzzy: bool = True) -> SearchResult:
        start = time.perf_counter()
        result = SearchResult(query=query)
        query = (query or "").strip()
        if not query:
            result.took_ms = (time.perf_counter() - start) * 1000
            return result

        ast = parse_query(query)
        leaves = collect_terms(ast)
        result.terms = [t.term for t in leaves if not t.prohibited]

        context: Dict[int, float] = {}
        matched_terms: Dict[int, Set[str]] = defaultdict(set)
        candidate_ids = self._eval(ast, context, matched_terms)

        # Typo tolerance: if nothing matched, suggest a correction.
        if not candidate_ids and fuzzy and leaves:
            df_map = self.index.term_document_frequencies(Field.CONTENT)
            raw_terms = tokenize(query)
            correction = best_correction(raw_terms, df_map)
            if correction:
                result.corrected_query = correction
                corrected_ast = parse_query(correction)
                context = {}
                matched_terms = defaultdict(set)
                candidate_ids = self._eval(corrected_ast, context, matched_terms)
                result.terms = raw_terms

        ranked = sorted(
            candidate_ids,
            key=lambda did: (context.get(did, 0.0),
                             self.index.documents[did].mtime),
            reverse=True,
        )[: min(limit, MAX_RESULTS)]

        for did in ranked:
            doc = self.index.documents[did]
            snippets = self._make_snippets(doc.content, matched_terms.get(did, set()))
            result.hits.append(Hit(
                doc_id=did,
                path=doc.path,
                name=doc.name,
                language=doc.language,
                score=context.get(did, 0.0),
                snippets=snippets,
                matched_terms=sorted(matched_terms.get(did, set())),
                size=doc.size,
                mtime=doc.mtime,
            ))
        result.total = len(candidate_ids)
        result.took_ms = (time.perf_counter() - start) * 1000
        return result

    # ------------------------------------------------------------------
    # Snippets
    # ------------------------------------------------------------------
    def _make_snippets(self, content: str, terms: Set[str]) -> List[str]:
        if not content or not terms:
            return []
        lower = content.lower()
        # Locate the earliest occurrences of any matched term.
        positions: List[int] = []
        for term in terms:
            needle = term.lower()
            idx = lower.find(needle)
            if idx >= 0:
                positions.append(idx)
        positions.sort()
        if not positions:
            return []

        snippets: List[str] = []
        used_ranges: List[Tuple[int, int]] = []
        for pos in positions:
            start = max(0, pos - SNIPPET_RADIUS)
            end = min(len(content), pos + SNIPPET_RADIUS)
            if any(not (end < rs or start > re_) for rs, re_ in used_ranges):
                continue
            used_ranges.append((start, end))
            text = content[start:end].replace("\n", " ").strip()
            text = re.sub(r"\s+", " ", text)
            if start > 0:
                text = "…" + text
            if end < len(content):
                text = text + "…"
            text = self._highlight(text, terms)
            snippets.append(text)
            if len(snippets) >= MAX_SNIPPETS:
                break
        return snippets

    @staticmethod
    def _highlight(text: str, terms: Set[str]) -> str:
        if not terms:
            return text
        ordered = sorted(terms, key=len, reverse=True)
        pattern = "|".join(re.escape(t) for t in ordered if t)
        if not pattern:
            return text
        return re.sub(
            f"({pattern})",
            r"[[\1]]",
            text,
            flags=re.IGNORECASE,
        )
