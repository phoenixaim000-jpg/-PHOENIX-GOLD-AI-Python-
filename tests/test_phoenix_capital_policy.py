import unittest

from phoenix_capital_policy import (
    CapitalPolicy,
    evaluate_new_trade,
    plan_monthly_withdrawal,
)


class WithdrawalPlanTests(unittest.TestCase):
    def test_below_one_unit_reinvests_all_profit(self):
        plan = plan_monthly_withdrawal(100_000, 125_000, 25_000)
        self.assertEqual(plan.eligible_units, 0)
        self.assertEqual(plan.monthly_cap_jpy, 0)
        self.assertEqual(plan.withdrawable_jpy, 0)
        self.assertEqual(plan.retained_profit_jpy, 25_000)

    def test_one_unit_can_withdraw_up_to_30k(self):
        plan = plan_monthly_withdrawal(150_000, 180_000, 30_000)
        self.assertEqual(plan.eligible_units, 1)
        self.assertEqual(plan.protected_floor_jpy, 150_000)
        self.assertEqual(plan.withdrawable_jpy, 30_000)

    def test_six_units_allow_up_to_180k_when_profit_and_equity_support_it(self):
        plan = plan_monthly_withdrawal(900_000, 1_080_000, 180_000)
        self.assertEqual(plan.eligible_units, 6)
        self.assertEqual(plan.monthly_cap_jpy, 180_000)
        self.assertEqual(plan.withdrawable_jpy, 180_000)
        self.assertEqual(plan.closing_equity_jpy - plan.withdrawable_jpy, 900_000)

    def test_withdrawal_limited_by_surplus_over_protected_floor(self):
        plan = plan_monthly_withdrawal(150_000, 170_000, 30_000)
        self.assertEqual(plan.withdrawable_jpy, 20_000)
        self.assertEqual(plan.retained_profit_jpy, 10_000)

    def test_unrealized_or_negative_profit_cannot_be_withdrawn(self):
        plan = plan_monthly_withdrawal(150_000, 160_000, -5_000)
        self.assertEqual(plan.withdrawable_jpy, 0)
        self.assertEqual(plan.retained_profit_jpy, 0)

    def test_month_opening_units_fix_monthly_cap(self):
        # Crossing 150k during a month does not create a same-month allowance.
        plan = plan_monthly_withdrawal(149_000, 179_000, 30_000)
        self.assertEqual(plan.eligible_units, 0)
        self.assertEqual(plan.withdrawable_jpy, 0)


class RiskGateTests(unittest.TestCase):
    def setUp(self):
        self.base = dict(
            equity_jpy=100_000,
            day_start_equity_jpy=100_000,
            high_water_equity_jpy=100_000,
            proposed_risk_jpy=250,
        )

    def test_accepts_small_paper_trade(self):
        result = evaluate_new_trade(**self.base)
        self.assertTrue(result.allowed)
        self.assertEqual(result.max_trade_risk_jpy, 250)

    def test_blocks_live_mode(self):
        result = evaluate_new_trade(**self.base, mode="LIVE")
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "LIVE_DISABLED")

    def test_blocks_oversized_trade_risk(self):
        result = evaluate_new_trade(**{**self.base, "proposed_risk_jpy": 251})
        self.assertEqual(result.reason_code, "TRADE_RISK_LIMIT")

    def test_blocks_daily_loss_limit(self):
        result = evaluate_new_trade(**{**self.base, "equity_jpy": 99_000})
        self.assertEqual(result.reason_code, "DAILY_LOSS_LIMIT")

    def test_blocks_drawdown_limit(self):
        result = evaluate_new_trade(**{**self.base, "equity_jpy": 190_000, "high_water_equity_jpy": 200_000})
        self.assertEqual(result.reason_code, "DRAWDOWN_LIMIT")

    def test_blocks_two_consecutive_losses(self):
        result = evaluate_new_trade(**self.base, consecutive_losses=2)
        self.assertEqual(result.reason_code, "LOSS_STREAK_LOCK")

    def test_blocks_averaging_and_martingale(self):
        averaging = evaluate_new_trade(**self.base, is_averaging_order=True)
        martingale = evaluate_new_trade(**self.base, is_martingale_order=True)
        self.assertEqual(averaging.reason_code, "AVERAGING_DISABLED")
        self.assertEqual(martingale.reason_code, "MARTINGALE_DISABLED")

    def test_blocks_second_open_position(self):
        result = evaluate_new_trade(**self.base, open_positions=1)
        self.assertEqual(result.reason_code, "POSITION_LIMIT")

    def test_blocks_aggregate_open_risk_over_limit(self):
        result = evaluate_new_trade(**self.base, current_open_risk_jpy=751)
        self.assertEqual(result.reason_code, "AGGREGATE_RISK_LIMIT")


if __name__ == "__main__":
    unittest.main()
