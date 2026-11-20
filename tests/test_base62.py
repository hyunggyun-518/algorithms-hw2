import unittest

from src.base62 import decode, encode


class Base62Tests(unittest.TestCase):
    def test_encode_zero_and_digit_order(self):
        self.assertEqual(encode(0), "0")
        self.assertEqual(encode(9), "9")
        self.assertEqual(encode(10), "a")
        self.assertEqual(encode(35), "z")
        self.assertEqual(encode(36), "A")
        self.assertEqual(encode(61), "Z")
        self.assertEqual(encode(62), "10")

    def test_decode_digit_order(self):
        self.assertEqual(decode("0"), 0)
        self.assertEqual(decode("a"), 10)
        self.assertEqual(decode("z"), 35)
        self.assertEqual(decode("A"), 36)
        self.assertEqual(decode("Z"), 61)
        self.assertEqual(decode("10"), 62)

    def test_round_trip_large_integers(self):
        for n in (1, 12345, 62**20 + 987654321):
            with self.subTest(n=n):
                self.assertEqual(decode(encode(n)), n)

    def test_encode_rejects_negative_and_non_integer(self):
        with self.assertRaises(ValueError):
            encode(-1)
        for n in (1.5, "12", True):
            with self.subTest(n=n), self.assertRaises(TypeError):
                encode(n)

    def test_decode_rejects_empty_and_invalid_input(self):
        with self.assertRaises(ValueError):
            decode("")
        with self.assertRaises(ValueError):
            decode("a_b")
        with self.assertRaises(TypeError):
            decode(12)


if __name__ == "__main__":
    unittest.main()
