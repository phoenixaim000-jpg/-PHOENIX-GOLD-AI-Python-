import unittest
from phoenix_core.market_scanner import MarketObservation, rank_candidates


class ScannerTests(unittest.TestCase):
    def test_trend_rank_and_range_watch(self):
        xs = [MarketObservation("EURUSD", "TREND_UP", .9, .8, .5, .9, .02, .1, 2),
              MarketObservation("XAUUSD", "RANGE", .4, .5, .9, .8, .03, .1, 2)]
        r = rank_candidates(xs)
        self.assertEqual(r[0].symbol, "EURUSD")
        self.assertEqual(r[0].status, "TRADE_CANDIDATE")
        self.assertEqual(r[1].status, "WATCH_ONLY")

    def test_crash_and_stale_data_blocked(self):
        xs = [MarketObservation("BTCUSD", "CRASH", .9, .9, .8, .9, .02, .9, 2),
              MarketObservation("USDJPY", "TREND_UP", .8, .8, .5, .9, .02, .1, 500)]
        self.assertTrue(all(x.status == "BLOCKED" for x in rank_candidates(xs)))


if __name__ == "__main__":
    unittest.main()
