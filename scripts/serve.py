#!/usr/bin/env python3
"""Static dev server for web/ with caching disabled.

python3 -m http.server sends no Cache-Control, so Chrome on the phone heuristically caches the ES modules
and keeps running old code after an edit (docs/LESSONS.md L13). Usage: python3 scripts/serve.py [port]
"""
import functools, http.server, sys
from pathlib import Path

class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def log_message(self, *a):
        pass

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
web = Path(__file__).resolve().parent.parent / "web"
class Server(http.server.ThreadingHTTPServer):
    request_queue_size = 128   # ES modules open ~10 connections at once; the default backlog of 5 resets some (LESSONS L27)
    daemon_threads = True

Server(("127.0.0.1", port), functools.partial(NoCache, directory=str(web))).serve_forever()
