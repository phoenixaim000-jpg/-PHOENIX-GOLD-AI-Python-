import unittest

from pyramiding import PyramidingConfig, evaluate_pyramid_add


class PyramidingTests(unittest.TestCase):
    def base(self, **overrides):
        args = dict(
            direction="LONG",
            average_entry_price=3000.0,
            last_add_price=3010.0,
            current_price=3020.0,
            atr=10.0,
            current_additions=0,
            equity_jpy=150_000,
            current_open_risk_jpy=750,
            proposed_add_risk_jpy=300,
            stop_loss_confirmed=True,
            market_data_fresh=True,
            mode="PAPER",
        )
        args.update(overrides)
        return evaluate_pyramid_add(**args)

    def test_all_conditions_allow_paper_add(self):
        result = self.base()
        self.assertTrue(result.allowed)
        self.assertEqual(result.additions_after_order, 1)
        self.assertEqual(result.proposed_total_open_risk_jpy, 1050)

    def test_rejects_adverse_or_not_profitable_move(self):
        self.assertEqual(self.base(current_price=2990).reason_code, "NOT_IN_PROFIT")

    def test_rejects_when_atr_step_not_reached(self):
        self.assertEqual(self.base(current_price=3015).reason_code, "ADD_STEP_NOT_REACHED")

    def test_rejects_missing_stop_confirmation(self):
        self.assertEqual(self.base(stop_loss_confirmed=False).reason_code, "STOP_NOT_CONFIRMED")

    def test_rejects_stale_market_data(self):
        self.assertEqual(self.base(market_data_fresh=False).reason_code, "STALE_DATA")

    def test_rejects_live_mode(self):
        self.assertEqual(self.base(mode="LIVE").reason_code, "LIVE_DISABLED")

    def test_rejects_aggregate_risk_over_limit(self):
        self.assertEqual(self.base(current_open_risk_jpy=1201).reason_code, "AGGREGATE_RISK_LIMIT")

    def test_rejects_add_risk_over_single_limit(self):
        self.assertEqual(self.base(proposed_add_risk_jpy=400).reason_code, "ADD_RISK_LIMIT")

    def test_rejects_max_additions(self):
        self.assertEqual(self.base(current_additions=2).reason_code, "MAX_ADDITIONS")

    def test_short_direction_uses_favorable_down_move(self):
        result = self.base(
            direction="SHORT",
            average_entry_price=3000,
            last_add_price=2990,
            current_price=2980,
        )
        self.assertTrue(result.allowed)

    def test_rejects_wrong_direction_price_move(self):
        self.assertEqual(
            self.base(direction="SHORT", average_entry_price=3000, last_add_price=2990, current_price=3020).reason_code,
            "NOT_IN_PROFIT",
        )

    def test_invalid_direction_rejected(self):
        with self.assertRaises(ValueError):
            self.base(direction="BUY")

    def test_invalid_risk_values_rejected(self):
        with self.assertRaises(ValueError):
            self.base(proposed_add_risk_jpy=-1)

    def test_non_finite_price_is_rejected(self):
        with self.assertRaises(ValueError):
            self.base(current_price=float("nan"))

    def test_invalid_config_rejected(self):
        with self.assertRaises(ValueError):
            PyramidingConfig(max_additions=-1)


if __name__ == "__main__":
    unittest.main()
