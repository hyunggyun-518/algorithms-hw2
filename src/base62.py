"""Base62 encoding and decoding utilities."""

_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE = len(_ALPHABET)


def encode(n: int) -> str:
    """Convert a non-negative integer to its base62 representation."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("n must be an integer")
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return "0"

    digits = []
    while n:
        n, remainder = divmod(n, _BASE)
        digits.append(_ALPHABET[remainder])
    return "".join(reversed(digits))


def decode(s: str) -> int:
    """Convert a base62 string to a non-negative integer."""
    if not isinstance(s, str):
        raise TypeError("s must be a string")
    if not s:
        raise ValueError("s must not be empty")

    n = 0
    for character in s:
        digit = _ALPHABET.find(character)
        if digit == -1:
            raise ValueError(f"invalid base62 character: {character!r}")
        n = n * _BASE + digit
    return n
