import unittest
from phoenix_core.risk_policy import RiskLimits, calculate_risk_budget, evaluate_order

def order(**changes):
    args=dict(is_demo=True,balance_jpy=150000,daily_loss_pct=.1,drawdown_pct=.5,
              open_positions=0,trades_today=0,consecutive_losses=0,spread_points=5,
              max_spread_points=20,side="BUY",entry_price=100,stop_loss=99,take_profit=102)
    args.update(changes)
    return evaluate_order(**args)

class RiskTests(unittest.TestCase):
    def test_budget(self):
        self.assertEqual(calculate_risk_budget(100000),250)
        self.assertEqual(calculate_risk_budget(150000),375)
    def test_demo_passes(self):
        self.assertTrue(order().allowed)
    def test_live_blocked(self):
        self.assertFalse(order(is_demo=False).allowed)
    def test_missing_sl_tp_blocked(self):
        self.assertFalse(order(stop_loss=None).allowed)
        self.assertFalse(order(take_profit=None).allowed)
    def test_two_losses_daily_loss_and_drawdown_stop(self):
        self.assertFalse(order(consecutive_losses=2).allowed)
        self.assertFalse(order(daily_loss_pct=1.0).allowed)
        self.assertFalse(order(drawdown_pct=5.0).allowed)
    def test_spread_and_direction(self):
        self.assertFalse(order(spread_points=21).allowed)
        self.assertFalse(order(side="BAD").allowed)
    def test_cannot_relax_profile(self):
        with self.assertRaises(ValueError): RiskLimits(risk_per_trade_pct=.5)
        with self.assertRaises(ValueError): RiskLimits(max_daily_loss_pct=2.0)

if __name__=="__main__":
    unittest.main()
