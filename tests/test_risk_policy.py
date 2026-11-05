import unittest
from phoenix_core.risk_policy import calculate_risk_budget, evaluate_order


class RiskPolicyTests(unittest.TestCase):
    def test_quarter_percent_budget(self):
        self.assertEqual(calculate_risk_budget(150000), 375)

    def test_valid_demo_order(self):
        r = evaluate_order(is_demo=True, balance_jpy=150000, daily_loss_pct=.1, drawdown_pct=.5,
            open_positions=0, trades_today=0, consecutive_losses=0, spread_points=5,
            max_spread_points=20, side="BUY", entry_price=100, stop_loss=99, take_profit=102)
        self.assertTrue(r.allowed)
        self.assertEqual(r.reward_risk_ratio, 2)

    def test_live_order_blocked(self):
        r = evaluate_order(is_demo=False, balance_jpy=150000, daily_loss_pct=0, drawdown_pct=0,
            open_positions=0, trades_today=0, consecutive_losses=0, spread_points=1,
            max_spread_points=20, side="BUY", entry_price=100, stop_loss=99, take_profit=102)
        self.assertFalse(r.allowed)

    def test_missing_stop_blocks(self):
        r = evaluate_order(is_demo=True, balance_jpy=150000, daily_loss_pct=0, drawdown_pct=0,
            open_positions=0, trades_today=0, consecutive_losses=0, spread_points=1,
            max_spread_points=20, side="BUY", entry_price=100, stop_loss=None, take_profit=102)
        self.assertFalse(r.allowed)

    def test_two_losses_block(self):
        r = evaluate_order(is_demo=True, balance_jpy=150000, daily_loss_pct=0, drawdown_pct=0,
            open_positions=0, trades_today=0, consecutive_losses=2, spread_points=1,
            max_spread_points=20, side="BUY", entry_price=100, stop_loss=99, take_profit=102)
        self.assertFalse(r.allowed)


if __name__ == "__main__":
    unittest.main()
