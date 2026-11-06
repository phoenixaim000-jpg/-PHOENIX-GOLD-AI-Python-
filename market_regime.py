"""Broker-agnostic multi-timeframe market regime analysis.

The module produces ranked candidates only. It never opens a position.
Feed it validated OHLC candles from a broker/data adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Mapping, Sequence, Tuple


@dataclass(frozen=True)
class Candle:
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class MarketAnalysis:
    regime: str
    atr: float
    trend_efficiency: float
    ema_separation_atr: float
    reason: str


@dataclass(frozen=True)
class MultiTimeframeDecision:
    signal: str
    priority_score: float
    fast: MarketAnalysis
    slow: MarketAnalysis
    reason: str


@dataclass(frozen=True)
class RankedCandidate:
    symbol: str
    signal: str
    priority_score: float
    reason: str


def _validate_candles(candles: Sequence[Candle]) -> None:
    if not candles:
        raise ValueError("candle sequence is empty")
    for index, candle in enumerate(candles):
        values = (candle.open, candle.high, candle.low, candle.close)
        if not all(isinstance(value, (int, float)) for value in values):
            raise ValueError(f"candle {index} contains a non-numeric price")
        if candle.low <= 0 or candle.high < candle.low:
            raise ValueError(f"candle {index} has invalid high/low prices")
        if candle.high < max(candle.open, candle.close):
            raise ValueError(f"candle {index} high is below open/close")
        if candle.low > min(candle.open, candle.close):
            raise ValueError(f"candle {index} low is above open/close")


def _ema(values: Sequence[float], period: int) -> float:
    alpha = 2.0 / (period + 1.0)
    result = float(values[0])
    for value in values[1:]:
        result = alpha * float(value) + (1.0 - alpha) * result
    return result


def _true_ranges(candles: Sequence[Candle]) -> list[float]:
    ranges = []
    previous_close = candles[0].close
    for candle in candles:
        ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        )
        previous_close = candle.close
    return ranges


def analyze_market(
    candles: Sequence[Candle],
    *,
    fast_ema_period: int = 20,
    slow_ema_period: int = 50,
    lookback: int = 20,
    shock_multiple: float = 2.5,
) -> MarketAnalysis:
    """Classify a completed-candle series as trend, breakout, range, shock or wait."""
    if fast_ema_period <= 1 or slow_ema_period <= fast_ema_period or lookback < 5:
        raise ValueError("EMA periods/lookback are invalid")
    if shock_multiple <= 1:
        raise ValueError("shock_multiple must be greater than 1")
    _validate_candles(candles)

    minimum_bars = max(slow_ema_period + 2, lookback + 2)
    if len(candles) < minimum_bars:
        return MarketAnalysis(
            "NO_TRADE", 0.0, 0.0, 0.0,
            f"最低{minimum_bars}本の確定足が必要です。"
        )

    closes = [float(c.close) for c in candles]
    tr = _true_ranges(candles)
    baseline_atr = mean(tr[-(lookback + 1):-1])
    current_tr = tr[-1]
    if baseline_atr <= 0:
        return MarketAnalysis("NO_TRADE", 0.0, 0.0, 0.0, "ATRを計算できません。")

    if current_tr > baseline_atr * shock_multiple:
        return MarketAnalysis(
            "SHOCK", baseline_atr, 0.0, 0.0,
            "直近足の値幅が平常時ATRの閾値を超えています。新規取引を見送ります。"
        )

    fast_ema = _ema(closes, fast_ema_period)
    slow_ema = _ema(closes, slow_ema_period)
    net_move = abs(closes[-1] - closes[-(lookback + 1)])
    path_length = sum(abs(closes[i] - closes[i - 1]) for i in range(len(closes) - lookback, len(closes)))
    efficiency = net_move / path_length if path_length > 0 else 0.0
    separation = abs(fast_ema - slow_ema) / baseline_atr
    previous = candles[-(lookback + 1):-1]
    previous_high = max(c.high for c in previous)
    previous_low = min(c.low for c in previous)
    last_close = closes[-1]

    if fast_ema > slow_ema and last_close > fast_ema and efficiency >= 0.30 and last_close > previous_high:
        return MarketAnalysis("BREAKOUT_UP", baseline_atr, efficiency, separation, "上位EMA方向と高値更新が一致しています。候補のみ。")
    if fast_ema < slow_ema and last_close < fast_ema and efficiency >= 0.30 and last_close < previous_low:
        return MarketAnalysis("BREAKOUT_DOWN", baseline_atr, efficiency, separation, "下位EMA方向と安値更新が一致しています。候補のみ。")
    if fast_ema > slow_ema and last_close > fast_ema and efficiency >= 0.30 and separation >= 0.10:
        return MarketAnalysis("TREND_UP", baseline_atr, efficiency, separation, "上昇トレンド条件を満たしています。候補のみ。")
    if fast_ema < slow_ema and last_close < fast_ema and efficiency >= 0.30 and separation >= 0.10:
        return MarketAnalysis("TREND_DOWN", baseline_atr, efficiency, separation, "下降トレンド条件を満たしています。候補のみ。")
    if efficiency < 0.25 and separation < 0.25:
        return MarketAnalysis("RANGE", baseline_atr, efficiency, separation, "方向性が弱いレンジとして新規取引を見送ります。")
    return MarketAnalysis("WAIT", baseline_atr, efficiency, separation, "方向条件が一致しないため見送ります。")


def analyze_multi_timeframe(
    fast_timeframe: Sequence[Candle],
    slow_timeframe: Sequence[Candle],
) -> MultiTimeframeDecision:
    """Require both timeframes to agree; shock/range/conflict means WAIT."""
    fast = analyze_market(fast_timeframe)
    slow = analyze_market(slow_timeframe)
    up = {"TREND_UP", "BREAKOUT_UP"}
    down = {"TREND_DOWN", "BREAKOUT_DOWN"}

    if fast.regime == "SHOCK" or slow.regime == "SHOCK":
        signal, reason = "WAIT", "いずれかの時間足が急変相場です。新規取引は禁止します。"
    elif fast.regime in up and slow.regime in up:
        signal, reason = "LONG_CANDIDATE", "短期・上位時間足の上昇方向が一致しています。発注ではありません。"
    elif fast.regime in down and slow.regime in down:
        signal, reason = "SHORT_CANDIDATE", "短期・上位時間足の下降方向が一致しています。発注ではありません。"
    else:
        signal, reason = "WAIT", "時間足の方向が不一致、レンジ、または判定待ちです。"

    score = min(fast.trend_efficiency, slow.trend_efficiency) * min(
        fast.ema_separation_atr, slow.ema_separation_atr
    ) if signal != "WAIT" else 0.0
    return MultiTimeframeDecision(signal, score, fast, slow, reason)


def scan_market_universe(
    universe: Mapping[str, Tuple[Sequence[Candle], Sequence[Candle]]],
) -> list[RankedCandidate]:
    """Rank aligned symbols. priority_score is a sorting aid, not win probability."""
    ranked = []
    for symbol, timeframes in universe.items():
        if not symbol or len(timeframes) != 2:
            continue
        decision = analyze_multi_timeframe(timeframes[0], timeframes[1])
        if decision.signal in {"LONG_CANDIDATE", "SHORT_CANDIDATE"}:
            ranked.append(RankedCandidate(
                symbol=symbol,
                signal=decision.signal,
                priority_score=decision.priority_score,
                reason=decision.reason,
            ))
    return sorted(ranked, key=lambda item: item.priority_score, reverse=True)
