"""A string-keyed hash table using Horner hashing and separate chaining."""

from __future__ import annotations

from collections.abc import Iterator


class _Node:
    __slots__ = ("key", "value", "next")

    def __init__(self, key: str, value: str, next_node: _Node | None = None) -> None:
        self.key = key
        self.value = value
        self.next = next_node


class HashTable:
    """Store string keys and values without Python's built-in hash table."""

    def __init__(self, capacity: int = 8, max_load: float | None = 0.75) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("capacity must be an integer")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if max_load is not None:
            if isinstance(max_load, bool) or not isinstance(max_load, (int, float)):
                raise TypeError("max_load must be a positive number or None")
            if max_load <= 0:
                raise ValueError("max_load must be positive")

        self._buckets: list[_Node | None] = [None] * capacity
        self._size = 0
        self._max_load = max_load

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
        if self._max_load is not None and self._size / self.capacity > self._max_load:
            self._resize()

    def get(self, key: str) -> str:
        value, _ = self.get_with_probes(key)
        if value is None:
            raise KeyError(key)
        return value

    def get_with_probes(self, key: str) -> tuple[str | None, int]:
        """Return the value, if present, and the number of nodes compared."""
        if not isinstance(key, str):
            raise TypeError("key must be a string")

        node = self._buckets[self._bucket_index(key)]
        comparisons = 0
        while node is not None:
            comparisons += 1
            if node.key == key:
                return node.value, comparisons
            node = node.next
        return None, comparisons

    def iter_buckets(self) -> Iterator[tuple[int, tuple[tuple[str, str], ...]]]:
        """Yield each bucket index and its key-value pairs in chain order."""
        for bucket_index, head in enumerate(self._buckets):
            entries: list[tuple[str, str]] = []
            node = head
            while node is not None:
                entries.append((node.key, node.value))
                node = node.next
            yield bucket_index, tuple(entries)

    def horner_trace(self, key: str) -> tuple[tuple[str, int, int, int], ...]:
        """Return each character, prior hash, code point, and resulting hash."""
        if not isinstance(key, str):
            raise TypeError("key must be a string")

        value = 0
        steps: list[tuple[str, int, int, int]] = []
        for character in key:
            previous_value = value
            code_point = ord(character)
            value = (value * 31 + code_point) % self.capacity
            steps.append((character, previous_value, code_point, value))
        return tuple(steps)

    def get_with_trace(self, key: str) -> tuple[str | None, tuple[int, ...]]:
        """Return the value and the bucket index once per compared node."""
        if not isinstance(key, str):
            raise TypeError("key must be a string")

        index = self._bucket_index(key)
        node = self._buckets[index]
        checked: list[int] = []
        while node is not None:
            checked.append(index)
            if node.key == key:
                return node.value, tuple(checked)
            node = node.next
        return None, tuple(checked)

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


class LinearProbingHashTable:
    """Store string keys and values using wraparound linear probing."""

    def __init__(self, capacity: int = 8, max_load: float | None = 0.75) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("capacity must be an integer")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if max_load is not None:
            if isinstance(max_load, bool) or not isinstance(max_load, (int, float)):
                raise TypeError("max_load must be a positive number or None")
            if max_load <= 0:
                raise ValueError("max_load must be positive")

        self._slots: list[_Node | None] = [None] * capacity
        self._size = 0
        self._max_load = max_load

    @property
    def capacity(self) -> int:
        return len(self._slots)

    def __len__(self) -> int:
        return self._size

    def put(self, key: str, value: str) -> None:
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError("key and value must be strings")

        index = self._bucket_index(key)
        for _ in range(self.capacity):
            entry = self._slots[index]
            if entry is None:
                if (
                    self._max_load is not None
                    and (self._size + 1) / self.capacity > self._max_load
                ):
                    self._resize()
                    self.put(key, value)
                    return
                self._slots[index] = _Node(key, value)
                self._size += 1
                return
            if entry.key == key:
                entry.value = value
                return
            index = (index + 1) % self.capacity

        raise OverflowError("hash table is full")

    def get(self, key: str) -> str:
        value, _ = self.get_with_probes(key)
        if value is None:
            raise KeyError(key)
        return value

    def get_with_probes(self, key: str) -> tuple[str | None, int]:
        """Return the value, if present, and the number of slots checked."""
        value, checked = self.get_with_trace(key)
        return value, len(checked)

    def get_with_trace(self, key: str) -> tuple[str | None, tuple[int, ...]]:
        """Return the value and the slot indices checked in lookup order."""
        if not isinstance(key, str):
            raise TypeError("key must be a string")

        index = self._bucket_index(key)
        checked: list[int] = []
        for _ in range(self.capacity):
            checked.append(index)
            entry = self._slots[index]
            if entry is None:
                return None, tuple(checked)
            if entry.key == key:
                return entry.value, tuple(checked)
            index = (index + 1) % self.capacity
        return None, tuple(checked)

    def iter_buckets(self) -> Iterator[tuple[int, tuple[tuple[str, str], ...]]]:
        """Yield each slot index and its entry, if occupied."""
        for slot_index, entry in enumerate(self._slots):
            entries = () if entry is None else ((entry.key, entry.value),)
            yield slot_index, entries

    def horner_trace(self, key: str) -> tuple[tuple[str, int, int, int], ...]:
        """Return each character, prior hash, code point, and resulting hash."""
        if not isinstance(key, str):
            raise TypeError("key must be a string")

        value = 0
        steps: list[tuple[str, int, int, int]] = []
        for character in key:
            previous_value = value
            code_point = ord(character)
            value = (value * 31 + code_point) % self.capacity
            steps.append((character, previous_value, code_point, value))
        return tuple(steps)

    def _bucket_index(self, key: str) -> int:
        value = 0
        for character in key:
            value = (value * 31 + ord(character)) % self.capacity
        return value

    def _resize(self) -> None:
        old_slots = self._slots
        self._slots = [None] * (len(old_slots) * 2)
        self._size = 0

        for entry in old_slots:
            if entry is not None:
                self.put(entry.key, entry.value)
