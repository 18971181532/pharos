"""A small query language parser.

Supported syntax (case-insensitive operators)::

    foo bar            terms that should both match (implicit AND)
    foo OR bar         either term
    foo -bar           documents containing foo but not bar
    "exact phrase"     a phrase query
    path:readme        field-scoped term (path/name/tag/content)
    parse*             prefix wildcard
    (foo OR bar) baz   grouped boolean expression

The parser produces a tiny AST of :class:`Node` objects which the search
engine evaluates against the inverted index.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from pharos.models import Field
from pharos.tokenizer import tokenize

# Token types for the lexer.
_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<lparen>\() |
        (?P<rparen>\)) |
        (?P<phrase>"[^"]*") |
        (?P<term>[^\s()"]+)
    )
    """,
    re.VERBOSE,
)

FIELD_ALIASES = {
    "path": Field.PATH,
    "file": Field.PATH,
    "name": Field.NAME,
    "filename": Field.NAME,
    "tag": Field.TAGS,
    "tags": Field.TAGS,
    "content": Field.CONTENT,
    "body": Field.CONTENT,
    "text": Field.CONTENT,
}


@dataclass
class TermNode:
    """A single term, optional field scope and wildcard/phrase flags."""

    term: str
    field: Optional[Field] = None
    wildcard: bool = False
    phrase: bool = False
    required: bool = True     # MUST (default) vs SHOULD (OR)
    prohibited: bool = False # MUST NOT (leading -)

    def expanded_terms(self) -> List[str]:
        if self.phrase:
            return tokenize(self.term)
        return tokenize(self.term, keep_stopwords=True)


@dataclass
class BoolNode:
    """A boolean combination of child nodes."""

    must: List["Node"] = field(default_factory=list)
    should: List["Node"] = field(default_factory=list)
    must_not: List["Node"] = field(default_factory=list)


Node = object  # type alias conceptually: TermNode | BoolNode


def _make_term(raw: str) -> TermNode:
    """Build a TermNode from a raw lexer token (handles field:/prefix/-)."""
    prohibited = False
    if raw.startswith("-") and len(raw) > 1:
        prohibited = True
        raw = raw[1:]
    elif raw.startswith("+"):
        raw = raw[1:]

    scope_field: Optional[Field] = None
    # Field scoping: name:value
    field_match = re.match(r"^([A-Za-z]+):(.+)$", raw)
    if field_match and field_match.group(1).lower() in FIELD_ALIASES:
        scope_field = FIELD_ALIASES[field_match.group(1).lower()]
        raw = field_match.group(2)

    phrase = raw.startswith('"') and raw.endswith('"') and len(raw) >= 2
    if phrase:
        raw = raw[1:-1]

    wildcard = raw.endswith("*") and len(raw) > 1
    if wildcard:
        raw = raw[:-1]

    return TermNode(
        term=raw,
        field=scope_field,
        wildcard=wildcard,
        phrase=phrase,
        prohibited=prohibited,
    )


def _lex(query: str) -> List[str]:
    tokens: List[str] = []
    for m in _TOKEN_RE.finditer(query):
        if m.group("lparen"):
            tokens.append("(")
        elif m.group("rparen"):
            tokens.append(")")
        elif m.group("phrase"):
            tokens.append(m.group("phrase"))
        elif m.group("term"):
            tokens.append(m.group("term"))
    return tokens


class _Parser:
    """Recursive-descent parser.

    Grammar::

        expr    := or_expr
        or_expr := and_expr (OR and_expr)*
        and_expr:= unary (unary)*        # implicit AND
        unary   := '-' primary | primary
        primary := '(' expr ')' | TERM
    """

    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Optional[str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> Optional[str]:
        tok = self.peek()
        if tok is not None:
            self.pos += 1
        return tok

    def parse(self) -> Node:
        if not self.tokens:
            return BoolNode()
        return self.parse_or()

    def parse_or(self) -> Node:
        left = self.parse_and()
        while self.peek() and self.peek().upper() == "OR":
            self.next()
            right = self.parse_and()
            left = self._merge_or(left, right)
        return left

    @staticmethod
    def _merge_or(left: Node, right: Node) -> BoolNode:
        node = BoolNode()
        for child in (left, right):
            if isinstance(child, BoolNode) and not child.must_not:
                node.should.extend(child.should or child.must)
                node.must_not.extend(child.must_not)
            else:
                if isinstance(child, TermNode):
                    child.required = False
                node.should.append(child)
        return node

    def parse_and(self) -> Node:
        node = BoolNode()
        while self.peek() is not None and self.peek() not in (")",):
            tok = self.peek()
            if tok.upper() == "OR":
                break
            child = self.parse_unary()
            self._add(node, child)
        return node

    @staticmethod
    def _add(node: BoolNode, child: Node) -> None:
        if isinstance(child, TermNode):
            if child.prohibited:
                node.must_not.append(child)
            elif not child.required:
                node.should.append(child)
            else:
                node.must.append(child)
        elif isinstance(child, BoolNode):
            node.must.extend(child.must)
            node.should.extend(child.should)
            node.must_not.extend(child.must_not)

    def parse_unary(self) -> Node:
        tok = self.peek()
        if tok == "-":
            self.next()
            child = self.parse_primary()
            if isinstance(child, TermNode):
                child.prohibited = True
            return child
        return self.parse_primary()

    def parse_primary(self) -> Node:
        tok = self.next()
        if tok is None:
            return BoolNode()
        if tok == "(":
            inner = self.parse_or()
            if self.peek() == ")":
                self.next()
            return inner
        return _make_term(tok)


def _simplify(node: Node) -> Node:
    """Unwrap a BoolNode that holds a single positive clause."""
    if isinstance(node, BoolNode):
        if not node.should and not node.must_not and len(node.must) == 1:
            return node.must[0]
    return node


def parse_query(query: str) -> Node:
    """Parse a query string into an AST."""
    tokens = _lex(query.strip())
    if not tokens:
        return BoolNode()
    return _simplify(_Parser(tokens).parse())


def collect_terms(node: Node) -> List[TermNode]:
    """Flatten an AST into its leaf TermNodes."""
    out: List[TermNode] = []
    if isinstance(node, TermNode):
        out.append(node)
    elif isinstance(node, BoolNode):
        for child in node.must + node.should + node.must_not:
            out.extend(collect_terms(child))
    return out
