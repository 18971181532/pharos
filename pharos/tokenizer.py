"""Text analysis and tokenization.

The tokenizer is code-aware: it splits identifiers written in
``camelCase``, ``PascalCase`` and ``snake_case`` into their component
words so that searching ``parse`` matches ``parseConfig`` and
``config_parser``.

Chinese (and other CJK) text has no spaces between words, so adjacent
Han characters are emitted as overlapping bigrams, which is a robust
language-agnostic approach for short queries without a dictionary.

A small Porter-style suffix stemmer reduces inflected forms
(``running`` -> ``run``) for better recall.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Character classes
# ---------------------------------------------------------------------------

# A contiguous run of latin/digit characters (identifiers and words).
_LATIN_RUN = re.compile(r"[A-Za-z0-9]+")
# A single CJK ideograph.
_CJK_CHAR = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_SPLIT_BOUNDARY = re.compile(
    r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+"
)

# Common English stop words (high frequency, low discriminating value).
STOP_WORDS_EN = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if",
    "in", "into", "is", "it", "no", "not", "of", "on", "or", "such", "that",
    "the", "their", "then", "there", "these", "they", "this", "to", "was",
    "will", "with", "from", "you", "your", "we", "our", "us", "do", "does",
    "did", "has", "have", "had", "can", "could", "would", "should", "may",
    "might", "must", "shall", "than", "so", "too", "very", "just", "also",
    "about", "above", "after", "again", "all", "am", "any", "because",
    "been", "before", "being", "below", "between", "both", "each", "few",
    "he", "her", "here", "hers", "herself", "him", "himself", "his", "how",
    "i", "its", "itself", "me", "more", "most", "my", "myself", "nor",
    "now", "off", "only", "once", "other", "out", "over", "own", "same",
    "she", "some", "through", "under", "until", "up", "what", "when",
    "where", "which", "while", "who", "whom", "why", "within", "without",
    "def", "self", "return", "none", "true", "false", "null", "class",
}

# A handful of very common Chinese function words / characters.
STOP_WORDS_CJK = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会",
    "着", "没有", "看", "好", "自己", "这", "那", "他", "她", "它",
    "们", "把", "被", "让", "给", "对", "为", "与", "及", "等", "中",
}

# Minimum length for a latin token to be kept (single letters are usually
# noise, except when they are meaningful code identifiers we still index
# them separately in the raw pass).
_MIN_LATIN_LEN = 2


def split_identifier(token: str) -> List[str]:
    """Split a camelCase / PascalCase / snake_case identifier into words.

    >>> split_identifier("parseConfigValue")
    ['parse', 'config', 'value']
    >>> split_identifier("HTTPServer")
    ['http', 'server']
    >>> split_identifier("config_parser")
    ['config', 'parser']
    """
    parts: List[str] = []
    # Underscores / hyphens / dots act as hard separators.
    for chunk in re.split(r"[_\-.\s]+", token):
        if not chunk:
            continue
        found = _SPLIT_BOUNDARY.findall(chunk)
        if found:
            parts.extend(p.lower() for p in found if p)
        else:
            parts.append(chunk.lower())
    return parts


def _stem(word: str) -> str:
    """A compact suffix stripper (Porter-lite).

    Intentionally conservative: it only removes a few common inflectional
    suffixes and guards against over-stemming short words.
    """
    w = word
    for suffix in ("ingly", "edly", "ation", "tions", "iveness", "fulness",
                   "ousness", "ically", "izing", "izing"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            return w[: -len(suffix)]
    for suffix in ("ing", "edly", "edly", "tion", "ness", "ment", "able",
                   "ible", "ful", "ous", "ive", "ize", "ise", "ally",
                   "edly", "est", "ies", "ied"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            stem = w[: -len(suffix)]
            if suffix == "ies" and len(stem) >= 1:
                return stem + "y"
            if suffix == "ied" and len(stem) >= 1:
                return stem + "y"
            return stem
    if len(w) > 4 and w.endswith("ed"):
        return w[:-2]
    if len(w) > 5 and w.endswith("es"):
        return w[:-2]
    if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _cjk_bigrams(run: str) -> List[str]:
    """Return overlapping bigrams for a run of CJK characters.

    Single characters are also emitted so one-character queries still work.
    """
    grams: List[str] = []
    chars = list(run)
    for ch in chars:
        if ch not in STOP_WORDS_CJK:
            grams.append(ch)
    for i in range(len(chars) - 1):
        bg = chars[i] + chars[i + 1]
        grams.append(bg)
    return grams


def tokenize(text: str, *, stem: bool = True,
             keep_stopwords: bool = False) -> List[str]:
    """Tokenize text into normalized index terms with order preserved.

    Returns a list of terms; latin words are lowercased (and optionally
    stemmed), identifiers are split into component words, and CJK text is
    expanded into bigrams.
    """
    terms: List[str] = []
    if not text:
        return terms

    # Walk the text, distinguishing latin runs from CJK runs.
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if _CJK_CHAR.match(ch):
            # Gather a contiguous CJK run, skipping embedded punctuation.
            j = i
            run = []
            while j < n and (_CJK_CHAR.match(text[j]) or text[j].isdigit()):
                run.append(text[j])
                j += 1
            run_str = "".join(run)
            for g in _cjk_bigrams(run_str):
                if g in STOP_WORDS_CJK and not keep_stopwords:
                    continue
                terms.append(g)
            i = j
            continue

        m = _LATIN_RUN.match(text, i)
        if m:
            raw = m.group(0)
            words = split_identifier(raw)
            # Also keep the whole lowercased identifier for exact recall.
            if len(words) > 1:
                words.append(raw.lower())
            for w in words:
                if len(w) < _MIN_LATIN_LEN and not w.isdigit():
                    # Keep single-letter code tokens only if standalone raw.
                    if w != raw.lower():
                        continue
                if w in STOP_WORDS_EN and not keep_stopwords:
                    continue
                terms.append(_stem(w) if stem else w)
            i = m.end()
            continue
        i += 1
    return terms


def tokenize_with_positions(text: str, *, stem: bool = True
                            ) -> List[Tuple[str, int]]:
    """Tokenize, returning ``(term, character_offset)`` pairs.

    Offsets point at the start of each term in the original text and are
    used for phrase queries and snippet highlighting.
    """
    out: List[Tuple[str, int]] = []
    if not text:
        return out

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if _CJK_CHAR.match(ch):
            start = i
            j = i
            chars = []
            while j < n and (_CJK_CHAR.match(text[j]) or text[j].isdigit()):
                chars.append(text[j])
                j += 1
            # unigrams with positions
            for k, c in enumerate(chars):
                if _CJK_CHAR.match(c) and c not in STOP_WORDS_CJK:
                    out.append((c, start + k))
            for k in range(len(chars) - 1):
                out.append((chars[k] + chars[k + 1], start + k))
            i = j
            continue

        m = _LATIN_RUN.match(text, i)
        if m:
            raw = m.group(0)
            words = split_identifier(raw)
            if len(words) > 1:
                words.append(raw.lower())
            for w in words:
                if len(w) < _MIN_LATIN_LEN and not w.isdigit():
                    if w != raw.lower():
                        continue
                if w in STOP_WORDS_EN:
                    continue
                term = _stem(w) if stem else w
                out.append((term, m.start()))
            i = m.end()
            continue
        i += 1
    return out


def term_frequency(text: str) -> Dict[str, int]:
    """Compute a raw term-frequency map for a piece of text."""
    tf: Dict[str, int] = {}
    for term in tokenize(text):
        tf[term] = tf.get(term, 0) + 1
    return tf
