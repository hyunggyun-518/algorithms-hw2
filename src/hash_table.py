"""A string-keyed hash table using Horner hashing and separate chaining."""

from __future__ import annotations


class _Node:
    __slots__ = ("key", "value", "next")

    def __init__(self, key: str, value: str, next_node: _Node | None = None) -> None:
        self.key = key
        self.value = value
        self.next = next_node


class HashTable:
    """Store string keys and values without Python's built-in hash table."""

    def __init__(self) -> None:
        self._buckets: list[_Node | None] = [None] * 8
        self._size = 0

    @property
    def capacity(self) -> int:
        return len(self._buckets)

    def __len__(self) -> int:
        return self._size

    def put(self, key: str, value: str) -> None:
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError("key and value must be strings")

        index = self._bucket_index(key)
        node = self._buckets[index]
        while node is not None:
            if node.key == key:
                node.value = value
                return
            node = node.next

        self._buckets[index] = _Node(key, value, self._buckets[index])
        self._size += 1
        if self._size / self.capacity > 0.75:
            self._resize()

    def get(self, key: str) -> str:
        if not isinstance(key, str):
            raise TypeError("key must be a string")

        node = self._buckets[self._bucket_index(key)]
        while node is not None:
            if node.key == key:
                return node.value
            node = node.next
        raise KeyError(key)

    def _bucket_index(self, key: str) -> int:
        value = 0
        for character in key:
            value = (value * 31 + ord(character)) % self.capacity
        return value

    def _resize(self) -> None:
        old_buckets = self._buckets
        self._buckets = [None] * (len(old_buckets) * 2)

        for head in old_buckets:
            node = head
            while node is not None:
                next_node = node.next
                index = self._bucket_index(node.key)
                node.next = self._buckets[index]
                self._buckets[index] = node
                node = next_node
