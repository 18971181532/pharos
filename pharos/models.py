"""Data models for Pharos."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Field(str, Enum):
    """Indexed document fields."""

    PATH = "path"
    NAME = "name"
    CONTENT = "content"
    TAGS = "tags"


@dataclass
class Document:
    """A single indexed file."""

    doc_id: int
    path: str                     # path relative to the indexed root, forward slashes
    name: str                     # file name
    extension: str                # without leading dot, lowercased
    language: str                 # detected language / type
    size: int = 0                 # bytes
    mtime: float = 0.0            # modification timestamp
    content: str = ""             # raw text content
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "path": self.path,
            "name": self.name,
            "extension": self.extension,
            "language": self.language,
            "size": self.size,
            "mtime": self.mtime,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        return cls(
            doc_id=data["doc_id"],
            path=data["path"],
            name=data["name"],
            extension=data.get("extension", ""),
            language=data.get("language", "unknown"),
            size=data.get("size", 0),
            mtime=data.get("mtime", 0.0),
            content=data.get("content", ""),
            tags=data.get("tags", []),
        )


@dataclass
class Hit:
    """A single search result."""

    doc_id: int
    path: str
    name: str
    language: str
    score: float
    snippets: List[str] = field(default_factory=list)
    matched_terms: List[str] = field(default_factory=list)
    size: int = 0
    mtime: float = 0.0


@dataclass
class SearchResult:
    """The result of a search query."""

    query: str
    hits: List[Hit] = field(default_factory=list)
    total: int = 0
    took_ms: float = 0.0
    corrected_query: Optional[str] = None
    terms: List[str] = field(default_factory=list)
    mode: str = "bm25"

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "total": self.total,
            "took_ms": round(self.took_ms, 2),
            "corrected_query": self.corrected_query,
            "terms": self.terms,
            "mode": self.mode,
            "hits": [
                {
                    "path": h.path,
                    "name": h.name,
                    "language": h.language,
                    "score": round(h.score, 3),
                    "snippets": h.snippets,
                    "matched_terms": h.matched_terms,
                    "size": h.size,
                    "mtime": h.mtime,
                }
                for h in self.hits
            ],
        }


@dataclass
class IndexStats:
    """Statistics describing the state of an index."""

    root: str = ""
    document_count: int = 0
    token_count: int = 0
    unique_terms: int = 0
    total_size: int = 0
    languages: Dict[str, int] = field(default_factory=dict)
    extensions: Dict[str, int] = field(default_factory=dict)
    top_terms: List[tuple] = field(default_factory=list)  # (term, df)
    index_time: float = 0.0

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "document_count": self.document_count,
            "token_count": self.token_count,
            "unique_terms": self.unique_terms,
            "total_size": self.total_size,
            "languages": self.languages,
            "extensions": self.extensions,
            "top_terms": [[t, df] for t, df in self.top_terms],
            "index_time": round(self.index_time, 3),
        }
