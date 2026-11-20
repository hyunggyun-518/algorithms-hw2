"""HTTP interface for the in-memory URL shortener."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

if __package__:
    from .base62 import decode
    from .shortener import URLShortener
else:
    from base62 import decode
    from shortener import URLShortener


class _ShortenerHTTPServer(HTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int]) -> None:
        self.shortener = URLShortener()
        super().__init__(address, _ShortenerRequestHandler)


class _ShortenerRequestHandler(BaseHTTPRequestHandler):
    server: _ShortenerHTTPServer

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/shorten":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", ""))
            if content_length < 0:
                raise ValueError("invalid Content-Length")
            payload = json.loads(self.rfile.read(content_length))
        except (UnicodeDecodeError, ValueError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        if not isinstance(payload, dict) or not isinstance(payload.get("url"), str):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON body must contain a URL"})
            return

        try:
            code, is_new = self.server.shortener.shorten_with_status(payload["url"])
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        status = HTTPStatus.CREATED if is_new else HTTPStatus.OK
        self._send_json(
            status,
            {"code": code, "short_url": f"/{code}"},
        )

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if not path.startswith("/") or path.count("/") != 1:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        code = path[1:]
        try:
            decode(code)
            url = self.server.shortener.expand(code)
        except (KeyError, ValueError):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        if code == HTTPStatus.NOT_IMPLEMENTED:
            self._send_json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"})
            return
        super().send_error(code, message, explain)

    def _send_json(self, status: HTTPStatus, payload: dict[str, str]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the URL shortener HTTP server.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = _ShortenerHTTPServer(("", args.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
