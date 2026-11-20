"""In-memory URL shortening backed by custom hash tables."""

from __future__ import annotations

from urllib.parse import urlsplit

if __package__:
    from .base62 import encode
    from .hash_table import HashTable
else:
    from base62 import encode
    from hash_table import HashTable


class URLShortener:
    """Create stable base62 codes and expand them to their original URLs."""

    def __init__(self) -> None:
        self._url_to_code = HashTable()
        self._code_to_url = HashTable()
        self._next_id = 1

    def shorten(self, url: str) -> str:
        code, _ = self.shorten_with_status(url)
        return code

    def shorten_with_status(self, url: str) -> tuple[str, bool]:
        """Return the code and whether this call created a new mapping."""
        normalized_url = self._validated_url(url)

        try:
            return self._url_to_code.get(normalized_url), False
        except KeyError:
            code = encode(self._next_id)
            self._code_to_url.put(code, normalized_url)
            self._url_to_code.put(normalized_url, code)
            self._next_id += 1
            return code, True

    def expand(self, code: str) -> str:
        if not isinstance(code, str):
            raise TypeError("code must be a string")
        return self._code_to_url.get(code)

    @staticmethod
    def _validated_url(url: str) -> str:
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        normalized_url = url.strip()
        if not normalized_url:
            raise ValueError("url must not be empty")

        try:
            parsed = urlsplit(normalized_url)
            hostname = parsed.hostname
            parsed.port
        except ValueError as error:
            raise ValueError(f"invalid URL: {url!r}") from error

        if parsed.scheme not in ("http", "https") or not hostname:
            raise ValueError(f"invalid URL: {url!r}")
        return normalized_url
