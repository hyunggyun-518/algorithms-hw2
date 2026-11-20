import json
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src.base62 import encode
from src.shortener import URLShortener


class ShortenerTests(unittest.TestCase):
    def setUp(self):
        self.shortener = URLShortener()

    def test_first_code_is_base62_encoding_of_one(self):
        self.assertEqual(self.shortener.shorten("https://example.com/first"), encode(1))

    def test_surrounding_whitespace_is_removed_and_url_is_preserved(self):
        url = "https://example.com/path?q=one#part"

        code = self.shortener.shorten(f"  {url}  ")

        self.assertEqual(self.shortener.expand(code), url)

    def test_empty_malformed_unsupported_and_hostless_urls_are_rejected(self):
        for url in ("", "   ", "not-a-url", "ftp://example.com/path", "https:///path"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.shortener.shorten(url)

    def test_duplicate_url_reuses_code_without_consuming_an_id(self):
        first_url = "https://example.com/first"
        second_url = "https://example.com/second"

        first_code = self.shortener.shorten(first_url)
        self.assertEqual(self.shortener.shorten(first_url), first_code)

        self.assertEqual(self.shortener.shorten(second_url), encode(2))

    def test_distinct_urls_receive_distinct_codes(self):
        first_code = self.shortener.shorten("https://example.com/one")
        second_code = self.shortener.shorten("https://example.com/two")

        self.assertNotEqual(first_code, second_code)

    def test_unknown_code_and_non_string_code_are_rejected(self):
        with self.assertRaises(KeyError):
            self.shortener.expand("not-registered")
        with self.assertRaises(TypeError):
            self.shortener.expand(123)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class ShortenerHTTPTests(unittest.TestCase):
    project_root = Path(__file__).resolve().parents[1]

    def setUp(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.opener = build_opener(_NoRedirectHandler())
        self._start_server()

    def tearDown(self):
        self._stop_server()

    def _start_server(self):
        self.server = subprocess.Popen(
            [
                sys.executable,
                str(self.project_root / "src" / "server.py"),
                "--port",
                str(self.port),
            ],
            cwd=self.project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                self.fail("server exited before accepting connections")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.1):
                    return
            except OSError:
                time.sleep(0.05)
        self.fail("server did not start listening")

    def _stop_server(self):
        server = getattr(self, "server", None)
        if server is None or server.poll() is not None:
            return
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)

    def _request(self, method, path, body=None):
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=3) as response:
                return response.status, response.headers, response.read()
        except HTTPError as response:
            return response.code, response.headers, response.read()

    def test_post_creates_new_url_then_returns_existing_code_for_duplicate(self):
        body = b'{"url":"https://example.com/repeated"}'

        new_status, _, new_body = self._request("POST", "/shorten", body)
        duplicate_status, _, duplicate_body = self._request("POST", "/shorten", body)
        new_result = json.loads(new_body)
        duplicate_result = json.loads(duplicate_body)

        self.assertEqual(new_status, 201)
        self.assertEqual(duplicate_status, 200)
        self.assertEqual(new_result["code"], duplicate_result["code"])
        self.assertEqual(new_result["short_url"], f'/{new_result["code"]}')

    def test_get_redirects_to_original_url(self):
        url = "https://example.com/path?q=one#part"
        _, _, body = self._request("POST", "/shorten", json.dumps({"url": url}).encode())
        code = json.loads(body)["code"]

        status, headers, _ = self._request("GET", f"/{code}")

        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], url)

    def test_invalid_json_and_url_return_json_400_responses(self):
        for body in (b"{", b'{"url":"ftp://example.com"}'):
            with self.subTest(body=body):
                status, headers, response_body = self._request("POST", "/shorten", body)

                self.assertEqual(status, 400)
                self.assertIn("application/json", headers.get("Content-Type", ""))
                self.assertTrue(json.loads(response_body))

    def test_unknown_and_invalid_codes_return_404(self):
        for path in ("/not-registered", "/invalid!"):
            with self.subTest(path=path):
                status, _, _ = self._request("GET", path)
                self.assertEqual(status, 404)

    def test_unknown_route_returns_404_and_unsupported_method_returns_405(self):
        self.assertEqual(self._request("GET", "/unknown/path")[0], 404)
        self.assertEqual(self._request("DELETE", "/shorten")[0], 405)

    def test_restarting_server_discards_in_memory_data(self):
        url = "https://example.com/temporary"
        _, _, body = self._request("POST", "/shorten", json.dumps({"url": url}).encode())
        code = json.loads(body)["code"]
        self._stop_server()
        self._start_server()

        status, _, _ = self._request("GET", f"/{code}")

        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
