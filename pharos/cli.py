"""Command-line interface for Pharos."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from pharos import __version__
from pharos.engine import SearchEngine
from pharos.indexer import Indexer
from pharos.storage import default_index_dir, index_exists


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pharos",
        description="Pharos — zero-dependency local full-text search engine.",
    )
    parser.add_argument("--version", action="version",
                        version=f"pharos {__version__}")
    sub = parser.add_subparsers(dest="command")

    # index
    p_index = sub.add_parser("index", help="Build or update the search index")
    p_index.add_argument("path", help="Directory (or file) to index")
    p_index.add_argument("--rebuild", action="store_true",
                         help="Discard the existing index and rebuild")
    p_index.add_argument("--exclude", action="append", default=[],
                         help="Exclude paths containing this (repeatable)")
    p_index.add_argument("--json", action="store_true", help="JSON output")

    # search
    p_search = sub.add_parser("search", help="Search the index")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("path", nargs="?", default=".",
                          help="Indexed directory (default: current)")
    p_search.add_argument("-n", "--limit", type=int, default=20,
                          help="Maximum results")
    p_search.add_argument("--json", action="store_true", help="JSON output")
    p_search.add_argument("--no-fuzzy", action="store_true",
                          help="Disable typo-tolerant suggestions")

    # stats
    p_stats = sub.add_parser("stats", help="Show index statistics")
    p_stats.add_argument("path", nargs="?", default=".",
                         help="Indexed directory")
    p_stats.add_argument("--json", action="store_true", help="JSON output")

    # serve
    p_serve = sub.add_parser("serve", help="Start the web dashboard")
    p_serve.add_argument("path", nargs="?", default=".",
                         help="Indexed directory")
    p_serve.add_argument("--port", type=int, default=8848)
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--rebuild", action="store_true",
                         help="Rebuild the index before serving")

    return parser


def _human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.1f}{unit}" if unit != "B" else f"{num}B"
        num /= 1024
    return f"{num:.1f}GB"


def cmd_index(args) -> int:
    if not os.path.exists(args.path):
        print(f"error: path not found: {args.path}", file=sys.stderr)
        return 1
    indexer = Indexer(args.path)
    stats, changes = indexer.build(
        exclude_patterns=args.exclude,
        incremental=not args.rebuild,
    )
    if args.json:
        out = stats.to_dict()
        out["changes"] = changes
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    print("=" * 58)
    print("  PHAROS — Index Build")
    print("=" * 58)
    print(f"  Root:        {os.path.abspath(args.path)}")
    print(f"  Documents:   {stats.document_count}")
    print(f"  Tokens:      {stats.token_count}")
    print(f"  Unique terms:{stats.unique_terms}")
    print(f"  Size:        {_human_size(stats.total_size)}")
    print(f"  Time:        {stats.index_time:.2f}s")
    print("  Changes:     "
          f"+{changes['added']} added, ~{changes['updated']} updated, "
          f"={changes['unchanged']} unchanged, -{changes['removed']} removed")
    print(f"  Index dir:   {default_index_dir(os.path.abspath(args.path))}")
    print()
    print("  Languages:")
    for lang, count in list(stats.languages.items())[:8]:
        bar = "█" * min(30, count)
        print(f"    {lang:<12} {count:>4}  {bar}")
    return 0


def cmd_search(args) -> int:
    if not index_exists(args.path):
        print(f"error: no index found at {args.path}. Run 'pharos index' first.",
              file=sys.stderr)
        return 1
    indexer = Indexer(args.path)
    index = indexer.load()
    engine = SearchEngine(index)
    result = engine.search(args.query, limit=args.limit,
                           fuzzy=not args.no_fuzzy)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.hits else 2

    print("=" * 58)
    print(f"  PHAROS — Search: {args.query}")
    print("=" * 58)
    if result.corrected_query:
        print(f"  Did you mean: {result.corrected_query}")
    print(f"  {result.total} matches in {result.took_ms:.1f}ms")
    print()
    if not result.hits:
        print("  No results.")
        return 2
    for i, hit in enumerate(result.hits, 1):
        print(f"  {i:>2}. {hit.path}")
        print(f"      score={hit.score:.2f}  lang={hit.language}  "
              f"size={_human_size(hit.size)}")
        for snippet in hit.snippets[:2]:
            print(f"      {snippet}")
        print()
    return 0


def cmd_stats(args) -> int:
    if not index_exists(args.path):
        print(f"error: no index found at {args.path}.", file=sys.stderr)
        return 1
    indexer = Indexer(args.path)
    stats = indexer.stats()
    if args.json:
        print(json.dumps(stats.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print("=" * 58)
    print("  PHAROS — Index Statistics")
    print("=" * 58)
    print(f"  Root:         {os.path.abspath(stats.root)}")
    print(f"  Documents:    {stats.document_count}")
    print(f"  Tokens:       {stats.token_count}")
    print(f"  Unique terms: {stats.unique_terms}")
    print(f"  Total size:   {_human_size(stats.total_size)}")
    print()
    print("  Top terms:")
    for term, df in stats.top_terms[:12]:
        bar = "█" * min(30, df)
        print(f"    {term:<16} {df:>4}  {bar}")
    return 0


def cmd_serve(args) -> int:
    from pharos.server import serve
    return serve(args.path, host=args.host, port=args.port,
                 rebuild=args.rebuild)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    handlers = {
        "index": cmd_index,
        "search": cmd_search,
        "stats": cmd_stats,
        "serve": cmd_serve,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
