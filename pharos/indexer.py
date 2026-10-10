"""High-level indexing orchestration and statistics."""
from __future__ import annotations

import time
from collections import Counter
from typing import List, Optional, Tuple

from pharos.collector import collect
from pharos.index import InvertedIndex
from pharos.models import IndexStats
from pharos.storage import load_index, save_index
from pharos.tokenizer import tokenize


class Indexer:
    """Builds, incrementally updates and queries an index for a root."""

    def __init__(self, root: str, index_dir: Optional[str] = None):
        self.root = root
        self.index_dir = index_dir
        self.index: Optional[InvertedIndex] = None

    def load(self) -> InvertedIndex:
        if self.index is None:
            self.index = load_index(self.root, self.index_dir) or InvertedIndex()
        return self.index

    # ------------------------------------------------------------------
    def build(self, *, exclude_patterns=None, incremental: bool = True
              ) -> Tuple[IndexStats, dict]:
        """Index the root.

        With ``incremental`` enabled, unchanged files (same size and mtime)
        are skipped and files that vanished are removed.
        """
        start = time.perf_counter()
        if incremental:
            index = self.load()
        else:
            index = InvertedIndex()
        self.index = index

        seen_paths = set()
        added, updated, unchanged, skipped = 0, 0, 0, 0

        for doc in collect(self.root, exclude_patterns):
            seen_paths.add(doc.path)
            existing_id = index.path_to_id.get(doc.path)
            if existing_id is not None:
                existing = index.documents[existing_id]
                if existing.size == doc.size and abs(existing.mtime - doc.mtime) < 0.001:
                    unchanged += 1
                    continue
                index.add_document(doc)
                updated += 1
            else:
                index.add_document(doc)
                added += 1

        removed = 0
        if incremental:
            gone = [p for p in list(index.path_to_id) if p not in seen_paths]
            for path in gone:
                did = index.path_to_id[path]
                if index.remove_document(did):
                    removed += 1

        stats = self.compute_stats(index, time.perf_counter() - start)
        save_index(index, self.root, self.index_dir,
                   extra_meta={"document_count": stats.document_count})
        changes = {"added": added, "updated": updated,
                   "unchanged": unchanged, "removed": removed}
        return stats, changes

    # ------------------------------------------------------------------
    def compute_stats(self, index: InvertedIndex, index_time: float = 0.0
                      ) -> IndexStats:
        stats = IndexStats(root=self.root, index_time=index_time)
        stats.document_count = len(index.documents)
        stats.token_count = index.total_tokens()
        stats.unique_terms = len(index.postings["content"])

        lang_counter: Counter = Counter()
        ext_counter: Counter = Counter()
        total_size = 0
        for doc in index.documents.values():
            lang_counter[doc.language] += 1
            if doc.extension:
                ext_counter[doc.extension] += 1
            total_size += doc.size
        stats.languages = dict(lang_counter.most_common())
        stats.extensions = dict(ext_counter.most_common())
        stats.total_size = total_size

        df = index.term_document_frequencies()
        stats.top_terms = sorted(df.items(), key=lambda kv: (-kv[1], kv[0]))[:25]
        return stats

    def stats(self) -> IndexStats:
        index = self.load()
        return self.compute_stats(index)
