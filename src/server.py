"""HTTP interface for the in-memory URL shortener."""

from __future__ import annotations

import argparse
import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlsplit

if __package__:
    from .base62 import decode
    from .shortener import URLShortener
else:
    from base62 import decode
    from shortener import URLShortener


class _JSONObject:
    def __init__(self, pairs: list[tuple[str, object]]) -> None:
        self._pairs = pairs

    def get(self, name: str) -> object | None:
        for key, value in reversed(self._pairs):
            if key == name:
                return value
        return None


class _ShortenerHTTPServer(HTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int]) -> None:
        self.shortener = URLShortener()
        super().__init__(address, _ShortenerRequestHandler)


class _ShortenerRequestHandler(BaseHTTPRequestHandler):
    server: _ShortenerHTTPServer

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/shorten":
            self._send_json(HTTPStatus.NOT_FOUND, (("error", "not found"),))
            return

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        is_form = content_type == "application/x-www-form-urlencoded"
        try:
            content_length = int(self.headers.get("Content-Length", ""))
            if content_length < 0:
                raise ValueError("invalid Content-Length")
            body = self.rfile.read(content_length)
            if is_form:
                form_fields = parse_qsl(
                    body.decode("utf-8"),
                    keep_blank_values=True,
                    strict_parsing=True,
                )
                url = next(
                    (value for name, value in reversed(form_fields) if name == "url"),
                    None,
                )
            else:
                payload = json.loads(body, object_pairs_hook=_JSONObject)
                url = payload.get("url") if isinstance(payload, _JSONObject) else None
        except (UnicodeDecodeError, ValueError) as error:
            self._send_input_error(HTTPStatus.BAD_REQUEST, str(error), is_form)
            return
        if not isinstance(url, str):
            self._send_input_error(
                HTTPStatus.BAD_REQUEST,
                "JSON or form body must contain a URL",
                is_form,
            )
            return

        try:
            code, is_new = self.server.shortener.shorten_with_status(url)
        except ValueError as error:
            self._send_input_error(HTTPStatus.BAD_REQUEST, str(error), is_form)
            return

        status = HTTPStatus.CREATED if is_new else HTTPStatus.OK
        if is_form:
            title = "짧은 링크가 준비되었습니다"
            message = "새 단축 링크를 만들었습니다." if is_new else "이미 등록된 URL입니다."
            content = (
                f"<p>{message}</p>"
                f"<p>원본 주소: <code>{html.escape(url)}</code></p>"
                f'<p>짧은 링크: <a href="/{html.escape(code, quote=True)}">'
                f"/{html.escape(code)}</a></p>"
                '<p><a href="/">다른 URL 줄이기</a> · <a href="/table">해시 테이블 보기</a></p>'
            )
            self._send_html(status, self._html_document(title, content))
            return

        self._send_json(
            status,
            (("code", code), ("short_url", f"/{code}")),
        )

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            content = (
                '<form action="/shorten" method="post">'
                '<label for="url">줄일 URL</label>'
                '<input id="url" name="url" type="url" placeholder="https://example.com" '
                'autocomplete="url" required>'
                '<button type="submit">줄이기</button>'
                "</form>"
                '<p><a href="/table">현재 해시 테이블 보기</a></p>'
            )
            self._send_html(
                HTTPStatus.OK,
                self._html_document("URL 단축기", content),
            )
            return
        if path == "/table":
            self._send_html(
                HTTPStatus.OK,
                self._html_document("해시 테이블", self._table_page()),
            )
            return
        if not path.startswith("/") or path.count("/") != 1:
            self._send_json(HTTPStatus.NOT_FOUND, (("error", "not found"),))
            return

        code = path[1:]
        try:
            decode(code)
            url = self.server.shortener.expand(code)
        except (KeyError, ValueError):
            self._send_json(HTTPStatus.NOT_FOUND, (("error", "not found"),))
            return

        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _table_page(self) -> str:
        buckets = tuple(self.server.shortener.iter_url_buckets())
        sections: list[str] = []
        entry_count = 0

        for bucket_index, entries in buckets:
            if not entries:
                sections.append(
                    f'<section class="bucket"><h2>칸 {bucket_index}</h2>'
                    '<p class="empty">비어 있음</p></section>'
                )
                continue

            nodes: list[str] = []
            for url, code in entries:
                entry_count += 1
                trace_steps = self.server.shortener.url_hash_trace(url)
                trace_rows = [
                    "<li><code>h<sub>{}</sub> = "
                    "({} × 31 + ord({} = {})) mod {} = {}</code></li>".format(
                        step_index,
                        previous_value,
                        html.escape(repr(character)),
                        code_point,
                        len(buckets),
                        value,
                    )
                    for step_index, (
                        character,
                        previous_value,
                        code_point,
                        value,
                    ) in enumerate(
                        trace_steps,
                        start=1,
                    )
                ]
                trace = (
                    "<details><summary>호너 해시 계산 보기</summary>"
                    "<p><code>h<sub>0</sub> = 0</code></p>"
                    f"<ol>{''.join(trace_rows)}</ol>"
                    f"<p>최종 버킷: {bucket_index}</p></details>"
                )
                safe_url = html.escape(url)
                safe_code = html.escape(code, quote=True)
                nodes.append(
                    '<article class="node">'
                    f"<h3>URL 키</h3><code class=\"url-key\">{safe_url}</code>"
                    f"<p>짧은 코드: <code>{safe_code}</code></p>"
                    f'<p>짧은 링크: <a href="/{safe_code}">/{safe_code}</a></p>'
                    f"{trace}</article>"
                )

            chain = '<span class="arrow" aria-label="다음 노드">&rarr;</span>'.join(nodes)
            chain += '<span class="arrow end">&rarr; null</span>'
            sections.append(
                f'<section class="bucket"><h2>칸 {bucket_index}</h2>'
                f'<div class="chain">{chain}</div></section>'
            )

        return (
            f"<p>버킷 {len(buckets)}개 · URL {entry_count}개</p>"
            '<p><a href="/">URL 단축기로 돌아가기</a></p>'
            f'<div class="buckets">{"".join(sections)}</div>'
        )

    @staticmethod
    def _html_document(title: str, content: str) -> str:
        safe_title = html.escape(title)
        return (
            "<!doctype html><html lang=\"ko\"><head>"
            '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{safe_title}</title>"
            "<style>"
            "body{font-family:system-ui,sans-serif;line-height:1.5;margin:0;background:#f4f6f8;color:#18212b}"
            "main{max-width:1000px;margin:2rem auto;padding:0 1rem}"
            "form,.bucket,.node{background:white;border:1px solid #d5dce3;border-radius:.6rem;padding:1rem}"
            "form{display:flex;gap:.75rem;align-items:center;flex-wrap:wrap}"
            "input{flex:1;min-width:16rem;padding:.65rem}button{padding:.65rem 1rem}"
            ".buckets{display:grid;gap:.75rem}.bucket h2{margin:.1rem 0 .75rem;font-size:1.1rem}"
            ".chain{display:flex;align-items:stretch;gap:.55rem;overflow-x:auto;padding:.25rem}"
            ".node{min-width:17rem;max-width:28rem;overflow-wrap:anywhere}"
            ".node h3{margin:.1rem 0;font-size:.95rem}.url-key{overflow-wrap:anywhere}"
            ".arrow{align-self:center;font-size:1.4rem;color:#526678;white-space:nowrap}"
            ".empty{color:#667}.node details{margin-top:.75rem}.node ol{padding-left:1.5rem}"
            "a{color:#075ca8}code{background:#eef2f5;padding:.1rem .25rem;border-radius:.2rem}"
            "</style></head><body><main>"
            f"<h1>{safe_title}</h1>{content}"
            "</main></body></html>"
        )

    def _send_html(self, status: HTTPStatus, body: str) -> None:
        encoded_body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded_body)))
        self.end_headers()
        self.wfile.write(encoded_body)

    def _send_input_error(self, status: HTTPStatus, message: str, is_form: bool) -> None:
        if is_form:
            content = (
                f'<p role="alert">{html.escape(message)}</p>'
                '<p><a href="/">돌아가기</a></p>'
            )
            self._send_html(status, self._html_document("요청을 처리할 수 없습니다", content))
        else:
            self._send_json(status, (("error", message),))

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        if code == HTTPStatus.NOT_IMPLEMENTED:
            self._send_json(
                HTTPStatus.METHOD_NOT_ALLOWED,
                (("error", "method not allowed"),),
            )
            return
        super().send_error(code, message, explain)

    def _send_json(
        self,
        status: HTTPStatus,
        fields: tuple[tuple[str, str], ...],
    ) -> None:
        members = (
            f"{json.dumps(key, ensure_ascii=False)}:"
            f"{json.dumps(value, ensure_ascii=False)}"
            for key, value in fields
        )
        body = ("{" + ",".join(members) + "}").encode("utf-8")
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
