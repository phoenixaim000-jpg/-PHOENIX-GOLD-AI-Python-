import unittest
from phoenix_core.capital_policy import decide_monthly_payout

class CompoundPolicyTests(unittest.TestCase):
    def test_100k_start_compounds_without_payout(self):
        r=decide_monthly_payout(account_balance_jpy=100000,monthly_realized_net_profit_jpy=12000)
        self.assertEqual(r.suggested_payout_jpy,0)
        self.assertEqual(r.retained_profit_jpy,12000)
    def test_below_reserve_no_payout(self):
        r=decide_monthly_payout(account_balance_jpy=149999,monthly_realized_net_profit_jpy=50000)
        self.assertEqual(r.suggested_payout_jpy,0)
    def test_at_reserve_no_payout(self):
        r=decide_monthly_payout(account_balance_jpy=150000,monthly_realized_net_profit_jpy=50000)
        self.assertEqual(r.suggested_payout_jpy,0)
    def test_partial_payout_preserves_reserve(self):
        r=decide_monthly_payout(account_balance_jpy=160000,monthly_realized_net_profit_jpy=20000)
        self.assertEqual(r.suggested_payout_jpy,10000)
        self.assertEqual(160000-r.suggested_payout_jpy,150000)
    def test_one_unit_capped_at_30k(self):
        r=decide_monthly_payout(account_balance_jpy=180000,monthly_realized_net_profit_jpy=80000)
        self.assertEqual(r.suggested_payout_jpy,30000)
    def test_six_units_capped_at_180k(self):
        r=decide_monthly_payout(account_balance_jpy=1080000,monthly_realized_net_profit_jpy=180000,capital_units=6)
        self.assertEqual(r.suggested_payout_jpy,180000)
        self.assertEqual(r.protected_capital_jpy,900000)
    def test_realized_profit_only(self):
        r=decide_monthly_payout(account_balance_jpy=1000000,monthly_realized_net_profit_jpy=25000,capital_units=6)
        self.assertEqual(r.suggested_payout_jpy,25000)
    def test_monthly_loss_means_zero(self):
        r=decide_monthly_payout(account_balance_jpy=200000,monthly_realized_net_profit_jpy=-5000)
        self.assertEqual(r.suggested_payout_jpy,0)
    def test_prior_payout_reduces_cap(self):
        r=decide_monthly_payout(account_balance_jpy=190000,monthly_realized_net_profit_jpy=70000,already_paid_this_month_jpy=10000)
        self.assertEqual(r.suggested_payout_jpy,20000)
    def test_reject_non_integer(self):
        with self.assertRaises(TypeError):
            decide_monthly_payout(account_balance_jpy=150000,monthly_realized_net_profit_jpy=10000.5)

if __name__=="__main__":
    unittest.main()
