"""Rank normalized market observations; never places trades."""
from dataclasses import dataclass
from math import isfinite

def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)

@dataclass(frozen=True)
class MarketObservation:
    symbol: str
    regime: str
    trend_strength: float
    momentum_strength: float
    range_strength: float
    liquidity_score: float
    spread_pct: float
    volatility_shock: float
    data_age_seconds: float

@dataclass(frozen=True)
class RankedCandidate:
    symbol: str
    regime: str
    score: float
    status: str
    reasons: tuple[str, ...]

def rank_candidates(observations: list[MarketObservation], *,
                    max_spread_pct: float = 0.10,
                    max_data_age_seconds: float = 120.0,
                    max_volatility_shock: float = 0.85,
                    min_liquidity_score: float = 0.20,
                    min_candidate_score: float = 0.60) -> list[RankedCandidate]:
    limits = (max_spread_pct, max_data_age_seconds, max_volatility_shock,
              min_liquidity_score, min_candidate_score)
    if not all(finite_number(x) for x in limits):
        raise ValueError("scanner thresholds must be finite")
    if max_spread_pct < 0 or max_data_age_seconds <= 0:
        raise ValueError("spread/data-age thresholds are invalid")
    if not 0 <= max_volatility_shock <= 1 or not 0 <= min_liquidity_score <= 1 or not 0 <= min_candidate_score <= 1:
        raise ValueError("normalized thresholds must be in [0, 1]")
    results = []
    for item in observations:
        reasons = []
        symbol_ok = isinstance(item.symbol, str) and bool(item.symbol.strip())
        if not symbol_ok:
            reasons.append("銘柄名が空または不正です")
        regime = item.regime.upper() if isinstance(item.regime, str) else "INVALID"
        values = (item.trend_strength, item.momentum_strength, item.range_strength,
                  item.liquidity_score, item.spread_pct, item.volatility_shock,
                  item.data_age_seconds)
        if not all(finite_number(x) for x in values):
            reasons.append("入力データに有限の数値ではない項目があります")
        normalized = values[:4]
        score_ok = all(finite_number(x) and 0 <= x <= 1 for x in normalized)
        if all(finite_number(x) for x in normalized) and not score_ok:
            reasons.append("強度・流動性スコアは0から1の範囲が必要です")
        if finite_number(item.spread_pct) and (item.spread_pct < 0 or item.spread_pct > max_spread_pct):
            reasons.append("スプレッドが上限を超えています")
        if finite_number(item.data_age_seconds) and (item.data_age_seconds < 0 or item.data_age_seconds > max_data_age_seconds):
            reasons.append("価格データが古いか時刻が不正です")
        if finite_number(item.volatility_shock):
            if not 0 <= item.volatility_shock <= 1:
                reasons.append("急変動スコアが0から1の範囲外です")
            elif item.volatility_shock > max_volatility_shock:
                reasons.append("急変動を検知したため新規取引を停止します")
        if finite_number(item.liquidity_score) and item.liquidity_score < min_liquidity_score:
            reasons.append("流動性が不足しています")
        if regime in {"BUBBLE", "CRASH", "SHOCK", "NO_TRADE"}:
            reasons.append(f"{regime}: 新規取引をブロック")
        elif regime not in {"TREND_UP", "TREND_DOWN", "RANGE"}:
            reasons.append("未対応の相場レジームです")
        score = (0.40 * item.trend_strength + 0.25 * item.momentum_strength
                 + 0.15 * item.range_strength + 0.20 * item.liquidity_score) if score_ok else 0.0
        if reasons:
            status = "BLOCKED"
        elif regime == "RANGE":
            status = "WATCH_ONLY"
            reasons.append("レンジ専用戦略の検証完了まで監視のみ")
        elif score < min_candidate_score:
            status = "WATCH_ONLY"
            reasons.append("候補スコアが最低基準未満です")
        else:
            status = "TRADE_CANDIDATE"
        results.append(RankedCandidate(item.symbol if symbol_ok else "",
                                       regime, round(score, 4), status, tuple(reasons)))
    return sorted(results, key=lambda x: (-x.score, x.symbol))
