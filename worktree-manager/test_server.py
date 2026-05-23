"""
Test server for exercising Command Center stop/restart/close behaviour.
Simulates a slow-starting service: prints warmup dots for 20 s, then
serves HTTP on port 18888.

  GET /rpc?method=<name>  →  {"ok": true, "method": "<name>", "ts": <unix_ts>}

Usage:
    python3.14 test_server.py
Then:
    curl "http://localhost:18888/rpc?method=ping"
"""

import http.server
import json
import time
import urllib.parse

PORT = 18888
WARMUP_SECONDS = 20
TICK = 5


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        method = params.get("method", ["unknown"])[0]
        body = json.dumps({"ok": True, "method": method, "ts": int(time.time())}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[request] {fmt % args}", flush=True)


def _warmup():
    elapsed = 0
    print(f"[startup] Warming up for {WARMUP_SECONDS}s …", flush=True)
    while elapsed < WARMUP_SECONDS:
        time.sleep(TICK)
        elapsed += TICK
        remaining = WARMUP_SECONDS - elapsed
        print(f"[startup] {elapsed}s elapsed … {remaining}s remaining", flush=True)


def main():
    _warmup()
    print(f"[startup] Server ready — listening on http://localhost:{PORT}", flush=True)
    print(f"[startup] Try: curl \"http://localhost:{PORT}/rpc?method=ping\"", flush=True)
    server = http.server.HTTPServer(("", PORT), _Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
