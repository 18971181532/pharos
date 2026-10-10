"""File discovery and reading.

Walks a directory tree, skips VCS/build/dependency directories, detects
text files, reads them with encoding fallbacks, and maps extensions to a
language label used in the dashboard.
"""
from __future__ import annotations

import os
from typing import Dict, Iterator, Optional

from pharos.models import Document

# Directories that are never indexed.
SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv",
    "env", ".env", "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    ".idea", ".vscode", "target", "bin", "obj", ".next", ".nuxt",
    "vendor", "third_party", ".pharos", ".cache", "coverage",
}

# Extensions we know how to read as text, mapped to a language.
EXTENSION_LANGUAGE: Dict[str, str] = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hh": "cpp", ".cs": "csharp",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
    ".swift": "swift", ".scala": "scala", ".sh": "shell", ".bash": "shell",
    ".zsh": "shell", ".ps1": "powershell",
    ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss",
    ".sass": "scss", ".less": "css", ".vue": "vue", ".svelte": "svelte",
    ".xml": "xml", ".svg": "xml", ".sql": "sql",
    ".json": "json", ".jsonl": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini", ".conf": "config",
    ".md": "markdown", ".markdown": "markdown", ".rst": "rst",
    ".txt": "text", ".text": "text", ".log": "log",
    ".csv": "csv", ".tsv": "csv",
    ".dockerfile": "docker", "dockerfile": "docker",
    ".makefile": "make", "makefile": "make",
    ".gradle": "gradle", ".groovy": "groovy",
    ".lua": "lua", ".pl": "perl", ".pm": "perl", ".r": "r", ".dart": "dart",
    ".ex": "elixir", ".exs": "elixir", ".erl": "erlang", ".hs": "haskell",
    ".clj": "clojure", ".tf": "terraform", ".proto": "protobuf",
    ".bat": "batch", ".cmd": "batch",
    ".gitignore": "config", ".editorconfig": "config",
}

# Whole filenames that should be treated as text even without an extension.
SPECIAL_FILENAMES = {
    "dockerfile": "docker", "makefile": "make", "rakefile": "ruby",
    "license": "text", "readme": "text", "changelog": "text",
    ".gitignore": "config", ".bashrc": "shell", ".zshrc": "shell",
    "gemfile": "ruby", "pipfile": "toml",
}

MAX_FILE_SIZE = 2 * 1024 * 1024  # skip files larger than 2 MiB


def detect_language(path: str) -> Optional[str]:
    """Return the language for a path, or None if not indexable."""
    name = os.path.basename(path).lower()
    if name in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[name]
    _, ext = os.path.splitext(name)
    if not ext:
        return None
    return EXTENSION_LANGUAGE.get(ext)


def _read_text(path: str) -> Optional[str]:
    """Read a file as text, trying several encodings."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size > MAX_FILE_SIZE or size == 0:
        return None
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            with open(path, "r", encoding=encoding, errors="strict") as fh:
                return fh.read()
        except (UnicodeDecodeError, LookupError):
            continue
        except OSError:
            return None
    # Last resort: replace undecodable bytes.
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def iter_files(root: str, exclude_patterns=None) -> Iterator[str]:
    """Yield absolute file paths under root, applying skip rules."""
    exclude_patterns = exclude_patterns or []
    if os.path.isfile(root):
        yield root
        return

    for current, dirs, files in os.walk(root):
        parts = current.replace("\\", "/").split("/")
        dirs[:] = [
            d for d in dirs
            if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for fn in sorted(files):
            full = os.path.join(current, fn)
            norm = os.path.relpath(full, root).replace("\\", "/")
            if any(pat in norm for pat in exclude_patterns):
                continue
            yield full


def collect(root: str, exclude_patterns=None) -> Iterator[Document]:
    """Discover and read indexable documents under root."""
    doc_id = 0
    for full in iter_files(root, exclude_patterns):
        language = detect_language(full)
        if language is None:
            continue
        content = _read_text(full)
        if content is None:
            continue
        try:
            stat = os.stat(full)
        except OSError:
            continue
        rel = os.path.relpath(full, root).replace("\\", "/")
        name = os.path.basename(full)
        _, ext = os.path.splitext(name)
        doc_id += 1
        yield Document(
            doc_id=doc_id,
            path=rel,
            name=name,
            extension=ext.lstrip(".").lower(),
            language=language,
            size=stat.st_size,
            mtime=stat.st_mtime,
            content=content,
        )
