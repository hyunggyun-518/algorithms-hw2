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

    def test_none_max_load_keeps_capacity_fixed(self):
        table = HashTable(capacity=2, max_load=None)

        for index in range(10):
            table.put(f"key-{index}", f"value-{index}")

        self.assertEqual(table.capacity, 2)
        self.assertEqual(len(table), 10)

    def test_lookup_reports_nodes_compared_for_hits_and_misses(self):
        table = HashTable(capacity=1, max_load=None)
        table.put("first", "one")
        table.put("second", "two")

        self.assertEqual(table.get_with_probes("second"), ("two", 1))
        self.assertEqual(table.get_with_probes("first"), ("one", 2))
        self.assertEqual(table.get_with_probes("missing"), (None, 2))


if __name__ == "__main__":
    unittest.main()
