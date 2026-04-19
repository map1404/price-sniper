"""
Minimal HTTP server for the Price Drop Sniper React frontend.

Routes:
- POST /api/analyze
- GET /health
- Serves built frontend from frontend/dist when available
"""

from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from agent import run_agent


ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "frontend" / "dist"


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


class PriceSniperHandler(BaseHTTPRequestHandler):
    server_version = "PriceSniperHTTP/1.0"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return

        if DIST_DIR.exists():
            self._serve_static(parsed.path)
            return

        self._send_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": "Frontend build not found. Start the React dev server with `npm run dev` in `frontend/`."
            },
        )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/analyze":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(raw_body.decode("utf-8"))
            product_url = str(payload.get("product_url", "")).strip()
            if not product_url:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "product_url is required"})
                return

            result = run_agent(product_url)
            self._send_json(HTTPStatus.OK, result)
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body"})
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def _serve_static(self, raw_path: str) -> None:
        relative = raw_path.lstrip("/") or "index.html"
        candidate = (DIST_DIR / relative).resolve()
        if not str(candidate).startswith(str(DIST_DIR.resolve())) or not candidate.exists() or candidate.is_dir():
            candidate = DIST_DIR / "index.html"

        if not candidate.exists():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Frontend asset not found"})
            return

        content_type, _ = mimetypes.guess_type(str(candidate))
        data = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_cors_headers()
        self.send_header("Content-Type", content_type or "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        data = _json_bytes(payload)
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    host = os.getenv("PRICE_SNIPER_HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("PRICE_SNIPER_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), PriceSniperHandler)
    print(f"Price Sniper API listening at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
