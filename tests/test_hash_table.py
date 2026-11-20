import unittest

from src.hash_table import HashTable


class HashTableTests(unittest.TestCase):
    def test_colliding_keys_remain_independently_retrievable(self):
        table = HashTable()
        table.put("a", "first")
        table.put("i", "second")

        self.assertEqual(table.get("a"), "first")
        self.assertEqual(table.get("i"), "second")

    def test_updating_key_replaces_value_without_increasing_size(self):
        table = HashTable()
        table.put("key", "before")
        table.put("key", "after")

        self.assertEqual(table.get("key"), "after")
        self.assertEqual(len(table), 1)

    def test_resize_preserves_entries_and_happens_above_load_threshold(self):
        table = HashTable()
        self.assertEqual(table.capacity, 8)

        for index in range(6):
            table.put(f"key-{index}", f"value-{index}")
        self.assertEqual(table.capacity, 8)

        table.put("key-6", "value-6")
        self.assertEqual(table.capacity, 16)
        self.assertEqual(len(table), 7)
        for index in range(7):
            self.assertEqual(table.get(f"key-{index}"), f"value-{index}")


if __name__ == "__main__":
    unittest.main()
