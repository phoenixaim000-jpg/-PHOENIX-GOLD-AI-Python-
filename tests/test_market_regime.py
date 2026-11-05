import unittest

from market_regime import (
    Candle,
    analyze_market,
    analyze_multi_timeframe,
    scan_market_universe,
)


def rising_bars(count=70):
    bars = []
    for i in range(count):
        close = 100.0 + i * 0.8
        open_price = close - 0.2
        bars.append(Candle(open_price, close + 0.25, open_price - 0.25, close))
    return bars


def falling_bars(count=70):
    bars = []
    for i in range(count):
        close = 100.0 - i * 0.8
        open_price = close + 0.2
        bars.append(Candle(open_price, open_price + 0.25, close - 0.25, close))
    return bars


def range_bars(count=70):
    return [Candle(100.0, 100.5, 99.5, 100.0) for _ in range(count)]


class MarketRegimeTests(unittest.TestCase):
    def test_uptrend_and_breakout_are_detected(self):
        result = analyze_market(rising_bars())
        self.assertIn(result.regime, {"TREND_UP", "BREAKOUT_UP"})

    def test_downtrend_and_breakdown_are_detected(self):
        result = analyze_market(falling_bars())
        self.assertIn(result.regime, {"TREND_DOWN", "BREAKOUT_DOWN"})

    def test_flat_market_is_range(self):
        result = analyze_market(range_bars())
        self.assertEqual(result.regime, "RANGE")

    def test_insufficient_bars_are_no_trade(self):
        result = analyze_market(rising_bars(10))
        self.assertEqual(result.regime, "NO_TRADE")

    def test_large_candle_is_shock(self):
        bars = rising_bars()
        last = bars[-1]
        bars[-1] = Candle(last.open, last.close + 5.0, last.open - 5.0, last.close)
        result = analyze_market(bars)
        self.assertEqual(result.regime, "SHOCK")

    def test_multi_timeframe_requires_alignment(self):
        same_direction = analyze_multi_timeframe(rising_bars(), rising_bars())
        disagreement = analyze_multi_timeframe(rising_bars(), falling_bars())
        self.assertEqual(same_direction.signal, "LONG_CANDIDATE")
        self.assertEqual(disagreement.signal, "WAIT")

    def test_universe_scanner_only_returns_aligned_candidates(self):
        ranked = scan_market_universe({
            "XAUUSD": (rising_bars(), rising_bars()),
            "RANGE": (range_bars(), range_bars()),
            "CONFLICT": (rising_bars(), falling_bars()),
        })
        self.assertEqual([item.symbol for item in ranked], ["XAUUSD"])
        self.assertEqual(ranked[0].signal, "LONG_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
