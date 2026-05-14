from __future__ import annotations

import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            self.send_json({
                "ok": True,
                "message": "ParkFinder UI server is running. Ontario Parks access is performed only by Playwright Chromium.",
            })
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def send_json(self, payload, status=200):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def explain_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "connection refused" in lowered or "errno 111" in lowered:
        return (
            "ParkFinder could not connect to the local UI server. Start it with "
            "`python3 -m parkfinder.server` and open http://127.0.0.1:8000. Original error: "
            f"{message}"
        )
    return message


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("ParkFinder UI running at http://127.0.0.1:8000")
    print("Ontario Parks is accessed only by the Playwright recorder: python3 -m parkfinder.playwright_recorder")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
