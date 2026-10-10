"""Persistent on-disk storage for the index.

The index is stored as JSON inside a ``.pharos`` directory at the root of
the indexed tree (or a user-chosen location). Writes are atomic: data is
written to a temporary file then renamed, so a crashed build can never
leave a corrupt index behind.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Optional

from pharos.index import InvertedIndex

INDEX_DIRNAME = ".pharos"
INDEX_FILENAME = "index.json"
META_FILENAME = "meta.json"


def default_index_dir(root: str) -> str:
    return os.path.join(root, INDEX_DIRNAME)


def _atomic_write_json(path: str, data: dict) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".pharos-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_index(index: InvertedIndex, root: str,
               index_dir: Optional[str] = None,
               extra_meta: Optional[dict] = None) -> str:
    """Persist the index, returning the index directory used."""
    idir = index_dir or default_index_dir(root)
    os.makedirs(idir, exist_ok=True)
    _atomic_write_json(os.path.join(idir, INDEX_FILENAME), index.to_dict())
    meta = {"root": os.path.abspath(root), "version": 1}
    if extra_meta:
        meta.update(extra_meta)
    _atomic_write_json(os.path.join(idir, META_FILENAME), meta)
    return idir


def load_index(root: str, index_dir: Optional[str] = None
               ) -> Optional[InvertedIndex]:
    """Load an index, returning None if none exists or it is unreadable."""
    idir = index_dir or default_index_dir(root)
    path = os.path.join(idir, INDEX_FILENAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return InvertedIndex.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return None


def index_exists(root: str, index_dir: Optional[str] = None) -> bool:
    idir = index_dir or default_index_dir(root)
    return os.path.exists(os.path.join(idir, INDEX_FILENAME))


def delete_index(root: str, index_dir: Optional[str] = None) -> bool:
    idir = index_dir or default_index_dir(root)
    path = os.path.join(idir, INDEX_FILENAME)
    if os.path.exists(path):
        os.unlink(path)
        meta = os.path.join(idir, META_FILENAME)
        if os.path.exists(meta):
            os.unlink(meta)
        return True
    return False
