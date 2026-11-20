"""HTTP interface for the in-memory URL shortener."""

from __future__ import annotations

import argparse
import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, parse_qsl, urlsplit

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

    def __init__(self, address: tuple[str, int], strategy: str = "chaining") -> None:
        self.shortener = URLShortener(strategy)
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
        if self.server.shortener.strategy == "linear-probing":
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            search_keys = query.get("key")
            return self._linear_table_page(buckets, search_keys[0] if search_keys else None)

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

    def _linear_table_page(
        self,
        buckets: tuple[tuple[int, tuple[tuple[str, str], ...]], ...],
        search_key: str | None,
    ) -> str:
        sections: list[str] = []
        entry_count = 0

        for slot_index, entries in buckets:
            if not entries:
                body = '<p class="empty">비어 있음</p>'
            else:
                entry_count += 1
                url, code = entries[0]
                safe_url = html.escape(url)
                safe_code = html.escape(code, quote=True)
                body = (
                    '<article class="entry">'
                    f"<h3>URL 키</h3><code class=\"url-key\">{safe_url}</code>"
                    f"<p>짧은 코드: <code>{safe_code}</code></p>"
                    f'<p>짧은 링크: <a href="/{safe_code}">/{safe_code}</a></p>'
                    "</article>"
                )
            sections.append(
                f'<section class="slot"><h2>칸 {slot_index}</h2>{body}</section>'
            )

        form_value = "" if search_key is None else html.escape(search_key, quote=True)
        content = [
            f"<p>선형 탐지 · 칸 {len(buckets)}개 · URL {entry_count}개</p>",
            '<form action="/table" method="get">'
            '<label for="key">조회할 URL 키</label>'
            f'<input id="key" name="key" type="text" value="{form_value}">'
            '<button type="submit">조회</button></form>',
        ]
        if search_key is not None:
            content.append(self._linear_lookup_result(search_key, buckets))
        else:
            content.append("<p>URL 키를 입력하면 탐색 과정을 확인할 수 있습니다.</p>")
        content.extend(
            (
                '<p><a href="/">URL 단축기로 돌아가기</a></p>',
                f'<div class="slots">{"".join(sections)}</div>',
            )
        )
        return "".join(content)

    def _linear_lookup_result(
        self,
        key: str,
        buckets: tuple[tuple[int, tuple[tuple[str, str], ...]], ...],
    ) -> str:
        value, checked_slots = self.server.shortener.url_lookup_trace(key)
        hash_steps = self.server.shortener.url_hash_trace(key)
        start_index = hash_steps[-1][3] if hash_steps else 0
        trace_rows = [
            "<li><code>h<sub>{}</sub> = "
            "({} × 31 + ord({} = {})) mod {} = {}</code></li>".format(
                step_index,
                previous_value,
                html.escape(repr(character)),
                code_point,
                len(buckets),
                result,
            )
            for step_index, (character, previous_value, code_point, result) in enumerate(
                hash_steps,
                start=1,
            )
        ]
        checked_text = " → ".join(str(slot) for slot in checked_slots)
        if value is not None:
            outcome = (
                f"성공: 칸 {checked_slots[-1]}에서 키가 일치해 "
                f"코드 {html.escape(value)}를 찾았습니다."
            )
        elif len(checked_slots) < len(buckets):
            outcome = (
                f"실패: 칸 {checked_slots[-1]}이 비어 있어 키가 없음을 "
                "확정했습니다."
            )
        else:
            outcome = (
                f"실패: {len(buckets)}개 칸을 모두 확인하고 시작 칸 "
                f"{start_index}으로 돌아와 키가 없음을 확정했습니다."
            )

        return (
            '<section class="lookup-result"><h2>조회 과정</h2>'
            f"<p>조회 키: <code>{html.escape(key)}</code></p>"
            "<details open><summary>호너 해시 계산 보기</summary>"
            "<p><code>h<sub>0</sub> = 0</code></p>"
            f"<ol>{''.join(trace_rows)}</ol>"
            f"<p>시작 칸: {start_index}</p></details>"
            f"<p>확인한 칸 순서: <code>{checked_text}</code></p>"
            f"<p>{outcome}</p></section>"
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
            ".slots{display:grid;grid-template-columns:repeat(auto-fit,minmax(12rem,1fr));gap:.75rem}"
            ".slot,.lookup-result{background:white;border:1px solid #d5dce3;border-radius:.6rem;padding:1rem}"
            ".slot h2{margin:.1rem 0 .75rem;font-size:1.1rem}.entry{overflow-wrap:anywhere}"
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
    parser.add_argument(
        "--strategy",
        choices=("chaining", "linear-probing"),
        default="chaining",
        help="hash table collision strategy",
    )
    args = parser.parse_args()

    server = _ShortenerHTTPServer(("", args.port), args.strategy)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
