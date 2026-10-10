"""The Pharos web server: REST API plus static dashboard."""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from pharos.engine import SearchEngine
from pharos.indexer import Indexer
from pharos.storage import index_exists

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class _State:
    """Shared, lazily-built server state."""

    def __init__(self, root: str):
        self.root = root
        self.indexer = Indexer(root)
        self.lock = threading.Lock()
        self._engine = None

    def ensure_indexed(self, rebuild: bool = False):
        with self.lock:
            if rebuild or not index_exists(self.root):
                self.indexer.build(incremental=not rebuild)
            self.indexer.load()
            self._engine = SearchEngine(self.indexer.index)
        return self

    @property
    def engine(self) -> SearchEngine:
        if self._engine is None:
            self.ensure_indexed()
        return self._engine


def _make_handler(state: _State):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Pharos/0.1"

        def log_message(self, fmt, *args):  # silence default logging
            return

        def _send_json(self, payload, status=200):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, rel_path: str):
            # Prevent path traversal.
            safe = os.path.normpath(rel_path).lstrip(os.sep)
            full = os.path.join(WEB_DIR, safe)
            if not os.path.abspath(full).startswith(os.path.abspath(WEB_DIR)):
                self.send_error(403)
                return
            if os.path.isdir(full) or safe == "":
                full = os.path.join(WEB_DIR, "index.html")
            if not os.path.exists(full):
                self.send_error(404)
                return
            ext = os.path.splitext(full)[1].lower()
            with open(full, "rb") as fh:
                body = fh.read()
            self.send_response(200)
            self.send_header("Content-Type",
                             _CONTENT_TYPES.get(ext, "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            try:
                if path == "/api/search":
                    q = params.get("q", [""])[0]
                    limit = int(params.get("limit", ["50"])[0])
                    fuzzy = params.get("fuzzy", ["1"])[0] != "0"
                    result = state.engine.search(q, limit=limit, fuzzy=fuzzy)
                    self._send_json(result.to_dict())
                    return

                if path == "/api/stats":
                    stats = state.indexer.compute_stats(state.indexer.index)
                    self._send_json(stats.to_dict())
                    return

                if path == "/api/terms":
                    df = state.indexer.index.term_document_frequencies()
                    top = sorted(df.items(), key=lambda kv: (-kv[1], kv[0]))
                    n = int(params.get("n", ["100"])[0])
                    self._send_json({"terms": [[t, d] for t, d in top[:n]]})
                    return

                if path == "/api/languages":
                    stats = state.indexer.compute_stats(state.indexer.index)
                    self._send_json({"languages": stats.languages})
                    return

                if path == "/api/file":
                    rel = params.get("path", [""])[0]
                    doc_id = state.indexer.index.path_to_id.get(rel)
                    if doc_id is None:
                        self._send_json({"error": "not found"}, 404)
                        return
                    doc = state.indexer.index.documents[doc_id]
                    self._send_json({
                        "path": doc.path, "name": doc.name,
                        "language": doc.language, "size": doc.size,
                        "content": doc.content[:200000],
                    })
                    return

                if path == "/api/refresh":
                    stats, changes = state.indexer.build(incremental=True)
                    state._engine = SearchEngine(state.indexer.index)
                    payload = stats.to_dict()
                    payload["changes"] = changes
                    self._send_json(payload)
                    return

                if path == "/api/health":
                    self._send_json({"status": "ok"})
                    return

                if path.startswith("/api/"):
                    self.send_error(404)
                    return

                self._send_static(path.lstrip("/"))
            except BrokenPipeError:
                pass
            except Exception as exc:  # never crash the dashboard
                self._send_json({"error": str(exc)}, 500)

    return Handler


def serve(root: str, host: str = "127.0.0.1", port: int = 8848,
          rebuild: bool = False) -> int:
    if not os.path.exists(root):
        print(f"error: path not found: {root}")
        return 1
    state = _State(root)
    print(f"Indexing {os.path.abspath(root)} ...")
    state.ensure_indexed(rebuild=rebuild)
    stats = state.indexer.compute_stats(state.indexer.index)
    print(f"Indexed {stats.document_count} documents, "
          f"{stats.unique_terms} unique terms.")

    httpd = ThreadingHTTPServer((host, port), _make_handler(state))
    url = f"http://{host}:{port}"
    print(f"Pharos dashboard running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        httpd.server_close()
    return 0
