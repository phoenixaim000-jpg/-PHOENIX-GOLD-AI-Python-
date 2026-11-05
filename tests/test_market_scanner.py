import unittest
from phoenix_core.market_scanner import MarketObservation, rank_candidates

def item(symbol="XAUUSD",regime="TREND_UP",**changes):
    v=dict(trend_strength=.9,momentum_strength=.8,range_strength=.5,liquidity_score=.9,
           spread_pct=.02,volatility_shock=.1,data_age_seconds=2)
    v.update(changes)
    return MarketObservation(symbol,regime,**v)

class ScannerTests(unittest.TestCase):
    def test_trend_candidate_and_range_watch(self):
        r=rank_candidates([item(),item("EURUSD","RANGE",trend_strength=.4,momentum_strength=.5,range_strength=.9,liquidity_score=.8)])
        self.assertEqual(r[0].status,"TRADE_CANDIDATE")
        self.assertEqual(r[1].status,"WATCH_ONLY")
    def test_bubble_crash_shock_blocked(self):
        r=rank_candidates([item(regime="BUBBLE"),item("BTCUSD","CRASH"),item("GOLD","SHOCK")])
        self.assertTrue(all(x.status=="BLOCKED" for x in r))
    def test_stale_wide_spread_shock_blocked(self):
        r=rank_candidates([item(data_age_seconds=500),item(spread_pct=.5),item(volatility_shock=.95)])
        self.assertTrue(all(x.status=="BLOCKED" for x in r))
    def test_negative_shock_and_nan_blocked(self):
        self.assertEqual(rank_candidates([item(volatility_shock=-.1)])[0].status,"BLOCKED")
        self.assertEqual(rank_candidates([item(trend_strength=float("nan"))])[0].status,"BLOCKED")
    def test_bad_thresholds_rejected(self):
        with self.assertRaises(ValueError): rank_candidates([],max_volatility_shock=1.2)

if __name__=="__main__":
    unittest.main()
