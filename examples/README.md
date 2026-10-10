# Pharos Examples

## Command-line walkthrough

```bash
# Index a project (skips .git, node_modules, build dirs automatically)
pharos index ~/code/myproject

# Re-index after pulling changes — only changed files are processed
pharos index ~/code/myproject

# Force a full rebuild
pharos index ~/code/myproject --rebuild

# Ignore generated directories
pharos index ~/code/myproject --exclude generated/ --exclude vendor/

# Plain-text results
pharos search "database connection" ~/code/myproject

# Machine-readable JSON (exit code 2 when there are no matches)
pharos search --json "auth token" ~/code/myproject

# Show vocabulary and index statistics
pharos stats ~/code/myproject
```

## Query cookbook

```bash
# Everything mentioning both parser and config
pharos search "parser config" .

# Either term
pharos search "parser OR lexer" .

# Discard test files from results
pharos search "login -test" .

# Only documentation
pharos search "path:md deployment" .

# A phrase that must appear together
pharos search '"connection pool"' .

# All identifiers starting with auth
pharos search "auth*" .

# Chinese: find files discussing the index
pharos search "索引" .
```

## Using the dashboard

```bash
pharos serve ~/code/myproject --port 8848
# open http://127.0.0.1:8848
```

- Type in the search bar and press Enter.
- Click any result to preview the file.
- Open **Overview** for index statistics and charts.
- **Terms** shows a clickable frequency cloud.
- The refresh button (↻) re-indexes without restarting.

## Embedding in Python

```python
from pharos.indexer import Indexer
from pharos.engine import SearchEngine
from pharos.storage import save_index, load_index

indexer = Indexer("./notes")
stats, changes = indexer.build()
print(changes)  # {'added': 12, 'updated': 0, 'unchanged': 0, 'removed': 0}

engine = SearchEngine(indexer.index)
result = engine.search("meeting notes", limit=10)
for hit in result.hits:
    print(round(hit.score, 2), hit.path)
```
