import unittest
from phoenix_core.capital_policy import decide_monthly_payout


class CompoundPolicyTests(unittest.TestCase):
    def test_under_reserve_payout_zero(self):
        r = decide_monthly_payout(account_balance_jpy=140000, monthly_realized_net_profit_jpy=50000, capital_units=1)
        self.assertEqual(r.suggested_payout_jpy, 0)
        self.assertEqual(r.retained_profit_jpy, 50000)

    def test_one_unit_cap_and_reserve(self):
        r = decide_monthly_payout(account_balance_jpy=180000, monthly_realized_net_profit_jpy=80000, capital_units=1)
        self.assertEqual(r.suggested_payout_jpy, 30000)
        self.assertEqual(180000 - r.suggested_payout_jpy, 150000)

    def test_six_units_cap(self):
        r = decide_monthly_payout(account_balance_jpy=1080000, monthly_realized_net_profit_jpy=180000, capital_units=6)
        self.assertEqual(r.suggested_payout_jpy, 180000)
        self.assertEqual(r.protected_capital_jpy, 900000)

    def test_limited_to_actual_net_profit(self):
        r = decide_monthly_payout(account_balance_jpy=1000000, monthly_realized_net_profit_jpy=25000, capital_units=6)
        self.assertEqual(r.suggested_payout_jpy, 25000)

    def test_loss_means_no_payout(self):
        r = decide_monthly_payout(account_balance_jpy=200000, monthly_realized_net_profit_jpy=-5000, capital_units=1)
        self.assertEqual(r.suggested_payout_jpy, 0)

    def test_prior_payout_reduces_remaining_cap(self):
        r = decide_monthly_payout(account_balance_jpy=190000, monthly_realized_net_profit_jpy=70000, capital_units=1, already_paid_this_month_jpy=10000)
        self.assertEqual(r.suggested_payout_jpy, 20000)


if __name__ == "__main__":
    unittest.main()
