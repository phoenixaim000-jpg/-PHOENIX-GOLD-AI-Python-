import json
import tempfile
import unittest
from pathlib import Path

from phoenix_gold_safety import (
    LossGuardConfig,
    PersistentLossGuard,
    RESET_CONFIRMATION,
    SafetyStateError,
)


class PersistentLossGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "guard-state.json"
        self.guard = PersistentLossGuard(
            self.path, LossGuardConfig(2, 1500), initialize_new_state=True
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_closed_losses_lock_new_entries(self):
        self.guard.record_closed_trade("p1", -200, "2026-11-06")
        result = self.guard.record_closed_trade("p2", -100, "2026-11-06")
        self.assertFalse(result.allowed)
        self.assertTrue(result.locked)
        self.assertEqual(result.consecutive_losses, 2)

    def test_restart_preserves_lock(self):
        self.guard.record_closed_trade("p1", -100, "2026-11-06")
        self.guard.record_closed_trade("p2", -100, "2026-11-06")
        restarted = PersistentLossGuard(self.path, LossGuardConfig(2, 1500))
        self.assertTrue(restarted.status().locked)
        self.assertFalse(restarted.status().allowed)

    def test_duplicate_trade_id_is_idempotent(self):
        self.guard.record_closed_trade("p1", -100, "2026-11-06")
        result = self.guard.record_closed_trade("p1", -100, "2026-11-06")
        self.assertEqual(result.consecutive_losses, 1)
        self.assertEqual(result.daily_net_pnl_jpy, -100)

    def test_profit_resets_consecutive_loss_streak(self):
        self.guard.record_closed_trade("p1", -100, "2026-11-06")
        result = self.guard.record_closed_trade("p2", 50, "2026-11-06")
        self.assertEqual(result.consecutive_losses, 0)
        self.assertTrue(result.allowed)

    def test_daily_realized_loss_limit_locks(self):
        result = self.guard.record_closed_trade("p1", -1500, "2026-11-06")
        self.assertTrue(result.locked)
        self.assertFalse(result.allowed)

    def test_daily_pnl_rolls_on_new_trading_day_but_loss_streak_remains(self):
        self.guard.record_closed_trade("p1", -200, "2026-11-05")
        result = self.guard.record_closed_trade("p2", 10, "2026-11-06")
        self.assertEqual(result.daily_net_pnl_jpy, 10)
        self.assertEqual(result.consecutive_losses, 0)

    def test_missing_state_fails_closed(self):
        self.path.unlink()
        with self.assertRaises(SafetyStateError):
            PersistentLossGuard(self.path)

    def test_corrupt_state_fails_closed(self):
        self.path.write_text("{broken json", encoding="utf-8")
        with self.assertRaises(SafetyStateError):
            PersistentLossGuard(self.path)

    def test_reset_requires_exact_phrase_and_review_reason(self):
        self.guard.record_closed_trade("p1", -100, "2026-11-06")
        self.guard.record_closed_trade("p2", -100, "2026-11-06")
        with self.assertRaises(PermissionError):
            self.guard.reset_after_review("yes", "reviewed losses")
        with self.assertRaises(ValueError):
            self.guard.reset_after_review(RESET_CONFIRMATION, "short")
        result = self.guard.reset_after_review(RESET_CONFIRMATION, "Reviewed broker statement and risk settings.")
        self.assertTrue(result.allowed)
        self.assertEqual(result.consecutive_losses, 0)

    def test_invalid_pnl_and_trade_id_are_rejected(self):
        with self.assertRaises(ValueError):
            self.guard.record_closed_trade("", -100, "2026-11-06")
        with self.assertRaises(ValueError):
            self.guard.record_closed_trade("p1", 1.5, "2026-11-06")


if __name__ == "__main__":
    unittest.main()
