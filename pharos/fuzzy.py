"""Fuzzy matching and typo-tolerant "did you mean" suggestions."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional


def levenshtein(a: str, b: str, *, max_distance: Optional[int] = None) -> int:
    """Compute the Levenshtein edit distance between two strings.

    Uses two rolling rows for O(n) memory. When ``max_distance`` is given
    and the true distance provably exceeds it, returns early with a value
    greater than ``max_distance`` (an admissible shortcut).
    """
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    # Swap so that b is the shorter string (inner loop).
    if la < lb:
        a, b = b, a
        la, lb = lb, la

    if max_distance is not None and la - lb > max_distance:
        return max_distance + 1

    previous = list(range(lb + 1))
    for i in range(1, la + 1):
        current = [i] + [0] * lb
        row_min = current[0]
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ca == b[j - 1] else 1
            current[j] = min(
                previous[j] + 1,       # deletion
                current[j - 1] + 1,    # insertion
                previous[j - 1] + cost,  # substitution
            )
            if current[j] < row_min:
                row_min = current[j]
        if max_distance is not None and row_min > max_distance:
            return max_distance + 1
        previous = current
    return previous[lb]


def similarity_ratio(a: str, b: str) -> float:
    """Return a 0..1 similarity ratio based on edit distance."""
    if not a and not b:
        return 1.0
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    return 1.0 - levenshtein(a, b) / max_len


def suggest(term: str, vocabulary: Iterable[str], *,
            max_results: int = 3, min_ratio: float = 0.6
            ) -> List[str]:
    """Suggest vocabulary terms close to ``term``.

    Candidates are ranked by edit distance, with a length-prefix guard to
    keep the search cheap on large vocabularies.
    """
    term = term.lower()
    tlen = len(term)
    scored = []
    for candidate in vocabulary:
        cl = len(candidate)
        # Cheap length filter; allow one extra char of difference per 3.
        if abs(cl - tlen) > max(2, tlen // 3):
            continue
        # Require sharing the first character (typos rarely move the head).
        if cl and tlen and candidate[0] != term[0]:
            continue
        allowed = max(1, tlen // 3)
        dist = levenshtein(term, candidate, max_distance=allowed)
        ratio = 1.0 - dist / max(cl, tlen, 1)
        if ratio >= min_ratio:
            scored.append((ratio, candidate))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, c in scored[:max_results]]


def best_correction(terms: List[str], document_frequency: Dict[str, int],
                    ) -> Optional[str]:
    """Build a corrected query string for unknown terms.

    Returns None when every term already exists in the vocabulary.
    """
    corrected: List[str] = []
    changed = False
    for term in terms:
        if term in document_frequency:
            corrected.append(term)
            continue
        # Prefer suggestions that occur frequently in the corpus.
        candidates = suggest(term, document_frequency.keys(), max_results=5)
        if candidates:
            best = max(candidates, key=lambda c: document_frequency.get(c, 0))
            corrected.append(best)
            changed = True
        else:
            corrected.append(term)
    return " ".join(corrected) if changed else None
