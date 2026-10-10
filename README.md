# Pharos — Local Full-Text Search Engine

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-orange.svg)](#)

**Pharos** is a zero-dependency, pure-Python local search engine. Point it at a folder and it builds an inverted index, ranks matches with **BM25**, understands source-code identifiers, handles **Chinese text** via bigram tokenization, tolerates typos, and serves an interactive search dashboard — all with the standard library alone.

Like the Lighthouse of Alexandria (the Pharos of the ancient world), it lights the way to what you are looking for.

## Why Pharos?

- `grep`/`ripgrep` match strings; Pharos understands **relevance** — it ranks thousands of files by how well they match.
- Searching `parse` finds `parseConfig`, `ConfigParser`, and `config_parser` automatically.
- Typing `serch` still finds `search` thanks to edit-distance correction.
- Works on English **and Chinese** content with no dictionaries or models.
- Everything runs locally and offline; nothing is uploaded.

## Features

### Search
- **BM25 ranking** with per-field length normalization
- **Boolean query language**: implicit AND, `OR`, `-exclude`, parentheses
- **Phrase queries**: `"exact phrase"`
- **Field scoping**: `path:readme`, `name:config`, `tag:...`
- **Prefix wildcards**: `parse*`
- **Typo tolerance**: Levenshtein-based "did you mean" suggestions
- **Highlighted snippets** with match context

### Text analysis
- **Code-aware tokenizer** splits `camelCase`, `PascalCase`, `snake_case`
- **CJK bigrams** for Chinese/Japanese/Korean text (no dictionary needed)
- Conservative Porter-style **stemming** (`indexes` to `index`)
- English + Chinese **stop-word** removal
- Position tracking for phrase matching and highlighting

### Indexing
- **Incremental builds** — unchanged files skipped by size/mtime
- Detects added, updated and removed files
- **Atomic, crash-safe** JSON persistence in `.pharos/`
- 40+ text/code formats recognized
- Encoding fallbacks (UTF-8, GB18030, Latin-1)

### Dashboard
- Instant search with ranked results and highlighted snippets
- File preview modal
- Index statistics cards
- Top-terms bar chart, language donut, term-frequency cloud
- One-click re-indexing

## Installation

```bash
pip install -e .
```

Or run without installing:

```bash
python -m pharos index /path/to/code
```

## Quick Start

```bash
# 1. Build the index
pharos index /path/to/your/project

# 2. Search
pharos search configuration /path/to/your/project

# 3. Open the dashboard
pharos serve /path/to/your/project --port 8848
# -> http://127.0.0.1:8848
```

## Query Syntax

| Query | Meaning |
|-------|---------|
| `search engine` | documents containing both terms |
| `search OR find` | either term |
| `search -test` | contains `search`, not `test` |
| `"inverted index"` | exact phrase |
| `path:readme search` | `search` only in files whose path matches `readme` |
| `name:config` | match on file name |
| `parse*` | prefix wildcard (`parse`, `parser`, `parseConfig`...) |
| `(a OR b) -c` | grouped boolean logic |

Code identifiers are tokenized automatically, so `config parser` matches
`ConfigParser`, `config_parser.py`, and `parseConfig()`.

## CLI Reference

```
pharos index PATH [--rebuild] [--exclude PATTERN] [--json]
pharos search QUERY [PATH] [-n LIMIT] [--json] [--no-fuzzy]
pharos stats [PATH] [--json]
pharos serve [PATH] [--port 8848] [--host 127.0.0.1] [--rebuild]
```

## Architecture

```
pharos/
├── tokenizer.py    # code-aware + CJK bigram tokenization, stemming, stop-words
├── fuzzy.py        # Levenshtein distance and spell correction
├── index.py        # inverted index: postings, term frequency, positions
├── collector.py    # file discovery, encoding detection, language mapping
├── query.py        # recursive-descent query parser -> boolean AST
├── engine.py       # BM25 ranking, boolean evaluation, snippet highlighting
├── indexer.py      # orchestration: incremental builds + statistics
├── storage.py      # atomic JSON persistence
├── cli.py          # index / search / stats / serve commands
├── server.py       # ThreadingHTTPServer REST API + static dashboard
└── web/            # zero-dependency Canvas 2D dashboard
```

### How ranking works

Each field (content, path, name, tags) has its own postings lists and a
boost — file names weigh heavily because they are short and meaningful.
For every query term Pharos computes the BM25 score with k1 = 1.5 and
b = 0.75, summed across fields and terms. Boolean operators first
constrain the candidate set; BM25 then orders it.

### Chinese tokenization

Because Chinese has no spaces between words, Pharos emits overlapping
character bigrams plus unigrams. This is dictionary-free, robust to
domain vocabulary, and works well for the short queries typical of code
and note search.

## Programmatic API

```python
from pharos.indexer import Indexer
from pharos.engine import SearchEngine

indexer = Indexer("/path/to/project")
indexer.build()                       # incremental after the first run

engine = SearchEngine(indexer.index)
result = engine.search('path:config parser OR loader')

for hit in result.hits:
    print(hit.score, hit.path)
    for snippet in hit.snippets:
        print("  ", snippet)
```

## Design Principles

- **Zero dependencies** — only the Python standard library.
- **Local & private** — indexing and search never touch the network.
- **Incremental** — re-indexing a large tree is fast.
- **Crash-safe** — the on-disk index is written atomically.
- **Polyglot** — 40+ file formats, English and CJK text.

## License

MIT — see [LICENSE](LICENSE).
