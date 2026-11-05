import unittest
from capital_policy import CapitalPolicy, evaluate_distribution


class CapitalPolicyTests(unittest.TestCase):
    def test_100k_reinvests_all(self):
        d = evaluate_distribution(100_000, 50_000)
        self.assertEqual(d.approved_limit_jpy, 0)
        self.assertEqual(d.post_withdrawal_equity_jpy, 100_000)

    def test_150k_does_not_withdraw(self):
        d = evaluate_distribution(150_000, 30_000)
        self.assertEqual(d.approved_limit_jpy, 0)

    def test_one_unit_needs_180k_and_realized_profit(self):
        d = evaluate_distribution(180_000, 30_000)
        self.assertEqual(d.eligible_units, 1)
        self.assertEqual(d.approved_limit_jpy, 30_000)
        self.assertEqual(d.post_withdrawal_equity_jpy, 150_000)

    def test_no_unrealized_profit_distribution(self):
        d = evaluate_distribution(180_000, 0)
        self.assertEqual(d.approved_limit_jpy, 0)

    def test_six_units(self):
        d = evaluate_distribution(1_080_000, 180_000)
        self.assertEqual(d.eligible_units, 6)
        self.assertEqual(d.target_jpy, 180_000)
        self.assertEqual(d.approved_limit_jpy, 180_000)
        self.assertEqual(d.post_withdrawal_equity_jpy, 900_000)

    def test_partial_realized_profit_caps_distribution(self):
        d = evaluate_distribution(1_080_000, 75_000)
        self.assertEqual(d.approved_limit_jpy, 75_000)
        self.assertEqual(d.post_withdrawal_equity_jpy, 1_005_000)


if __name__ == "__main__":
    unittest.main()
