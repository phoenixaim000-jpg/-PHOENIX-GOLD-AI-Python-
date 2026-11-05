"""Rank normalized multi-asset observations; never places trades."""
from dataclasses import dataclass
from math import isfinite


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
    results = []
    for item in observations:
        reasons = []
        values = (item.trend_strength, item.momentum_strength, item.range_strength,
                  item.liquidity_score, item.spread_pct, item.volatility_shock,
                  item.data_age_seconds)
        if not item.symbol.strip():
            reasons.append("銘柄名が空です")
        if not all(isfinite(v) for v in values):
            reasons.append("入力データに非有限値があります")
        if any(not 0 <= v <= 1 for v in values[:4]):
            reasons.append("強度・流動性スコアは0から1の範囲で指定してください")
        if item.spread_pct < 0 or item.spread_pct > max_spread_pct:
            reasons.append("スプレッドが上限を超えています")
        if item.data_age_seconds < 0 or item.data_age_seconds > max_data_age_seconds:
            reasons.append("価格データが古いか時刻が不正です")
        if item.volatility_shock > max_volatility_shock:
            reasons.append("急変動のため新規取引を停止します")
        if item.liquidity_score < min_liquidity_score:
            reasons.append("流動性が不足しています")
        regime = item.regime.upper()
        if regime in {"BUBBLE", "CRASH", "SHOCK", "NO_TRADE"}:
            reasons.append(f"{regime} regime is blocked")
        elif regime not in {"TREND_UP", "TREND_DOWN", "RANGE"}:
            reasons.append("未対応の相場レジームです")

        score = (0.40 * item.trend_strength + 0.25 * item.momentum_strength
                 + 0.15 * item.range_strength + 0.20 * item.liquidity_score)                 if all(isfinite(v) for v in values[:4]) else 0.0
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
        results.append(RankedCandidate(item.symbol, regime, round(score, 4),
                                       status, tuple(reasons)))
    return sorted(results, key=lambda x: (-x.score, x.symbol))
