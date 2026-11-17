import unittest

from lab9.stats import pass_at_k, pass_hat_k


class TestPassK(unittest.TestCase):

    def test_all_success(self):
        for k in (1, 3, 5):
            self.assertEqual(pass_at_k(5, 5, k), 1.0)
            self.assertEqual(pass_hat_k(5, 5, k), 1.0)

    def test_all_failure(self):
        for k in (1, 3, 5):
            self.assertEqual(pass_at_k(5, 0, k), 0.0)
            self.assertEqual(pass_hat_k(5, 0, k), 0.0)

    def test_partial_success(self):
        self.assertAlmostEqual(pass_at_k(5, 3, 1), 0.6)
        self.assertAlmostEqual(pass_at_k(5, 3, 3), 1.0)
        self.assertAlmostEqual(pass_hat_k(5, 3, 1), 0.6)
        self.assertAlmostEqual(pass_hat_k(5, 3, 3), 0.1)
        self.assertEqual(pass_hat_k(5, 3, 5), 0.0)

    def test_invalid_inputs(self):
        for fn in (pass_at_k, pass_hat_k):
            for args in ((5, 3, 6), (5, 6, 1), (0, 0, 1),
                         (5, -1, 1), (5, 3, 0)):
                with self.assertRaises(ValueError):
                    fn(*args)

    def test_ordering(self):
        for c in range(6):
            self.assertLessEqual(
                pass_hat_k(5, c, 5),
                pass_at_k(5, c, 1)
            )
            self.assertLessEqual(
                pass_at_k(5, c, 1),
                pass_at_k(5, c, 5)
            )


if __name__ == "__main__":
    unittest.main()
