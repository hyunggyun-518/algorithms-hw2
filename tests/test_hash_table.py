import unittest

from src.hash_table import HashTable, LinearProbingHashTable

TABLE_TYPES = (HashTable, LinearProbingHashTable)


class HashTableTests(unittest.TestCase):
    def test_colliding_keys_remain_independently_retrievable(self):
        for table_type in TABLE_TYPES:
            with self.subTest(table=table_type.__name__):
                table = table_type()
                table.put("a", "first")
                table.put("i", "second")

                self.assertEqual(table.get("a"), "first")
                self.assertEqual(table.get("i"), "second")

    def test_updating_key_replaces_value_without_increasing_size(self):
        for table_type in TABLE_TYPES:
            with self.subTest(table=table_type.__name__):
                table = table_type()
                table.put("key", "before")
                table.put("key", "after")

                self.assertEqual(table.get("key"), "after")
                self.assertEqual(len(table), 1)

    def test_resize_preserves_entries_and_happens_above_load_threshold(self):
        for table_type in TABLE_TYPES:
            with self.subTest(table=table_type.__name__):
                table = table_type()
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
        chain_table = HashTable(capacity=2, max_load=None)
        for index in range(10):
            chain_table.put(f"key-{index}", f"value-{index}")
        self.assertEqual(chain_table.capacity, 2)
        self.assertEqual(len(chain_table), 10)

        linear_table = LinearProbingHashTable(capacity=2, max_load=None)
        linear_table.put("first", "one")
        linear_table.put("second", "two")
        self.assertEqual(linear_table.capacity, 2)
        self.assertEqual(len(linear_table), 2)
        with self.assertRaises(OverflowError):
            linear_table.put("third", "three")

    def test_lookup_reports_nodes_compared_for_hits_and_misses(self):
        for table_type in TABLE_TYPES:
            with self.subTest(table=table_type.__name__):
                table = table_type(capacity=3, max_load=None)
                table.put("b", "first")
                table.put("e", "second")

                if table_type is HashTable:
                    self.assertEqual(table.get_with_probes("e"), ("second", 1))
                    self.assertEqual(table.get_with_probes("b"), ("first", 2))
                    self.assertEqual(table.get_with_probes("h"), (None, 2))
                else:
                    self.assertEqual(table.get_with_probes("e"), ("second", 2))
                    self.assertEqual(table.get_with_probes("b"), ("first", 1))
                    self.assertEqual(table.get_with_probes("h"), (None, 3))

    def test_bucket_snapshot_and_horner_trace_expose_chain_details(self):
        table = HashTable(capacity=8, max_load=None)
        table.put("a", "1")
        table.put("i", "2")

        buckets = tuple(table.iter_buckets())

        self.assertEqual(buckets[1], (1, (("i", "2"), ("a", "1"))))
        self.assertEqual(table.horner_trace("a"), (("a", 0, 97, 1),))

    def test_linear_probing_wraps_from_last_slot_to_zero(self):
        table = LinearProbingHashTable(capacity=3, max_load=None)
        table.put("b", "first")
        table.put("e", "second")

        self.assertEqual(tuple(table.iter_buckets()), (
            (0, (("e", "second"),)),
            (1, ()),
            (2, (("b", "first"),)),
        ))
        self.assertEqual(table.get_with_trace("e"), ("second", (2, 0)))

    def test_full_linear_table_stops_after_one_cycle_for_missing_key(self):
        table = LinearProbingHashTable(capacity=3, max_load=None)
        for key in ("a", "b", "c"):
            table.put(key, key)

        value, probes = table.get_with_probes("missing")
        self.assertIsNone(value)
        self.assertEqual(probes, 3)
        self.assertEqual(table.get_with_trace("missing")[1], (0, 1, 2))


if __name__ == "__main__":
    unittest.main()
