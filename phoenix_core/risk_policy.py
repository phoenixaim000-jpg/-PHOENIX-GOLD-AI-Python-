"""Fail-closed pre-trade checks. No broker order is sent here."""
from dataclasses import dataclass
from math import floor, isfinite
from typing import Optional


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade_pct: float = 0.25
    max_daily_loss_pct: float = 1.0
    max_drawdown_pct: float = 5.0
    max_open_positions: int = 1
    max_trades_per_day: int = 5
    max_consecutive_losses: int = 2
    min_reward_risk: float = 1.5
    allow_live: bool = False
    allow_averaging: bool = False
    allow_grid: bool = False
    allow_martingale: bool = False


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...]
    risk_budget_jpy: int
    reward_risk_ratio: Optional[float]


def calculate_risk_budget(balance_jpy: int, limits: RiskLimits = RiskLimits()) -> int:
    if not isinstance(balance_jpy, int) or balance_jpy < 0:
        raise ValueError("balance_jpy must be a non-negative integer")
    return floor(balance_jpy * limits.risk_per_trade_pct / 100)


def evaluate_order(*, is_demo: bool, balance_jpy: int, daily_loss_pct: float,
                   drawdown_pct: float, open_positions: int, trades_today: int,
                   consecutive_losses: int, spread_points: float,
                   max_spread_points: float, side: str, entry_price: float,
                   stop_loss: Optional[float], take_profit: Optional[float],
                   limits: RiskLimits = RiskLimits()) -> RiskDecision:
    reasons: list[str] = []
    rr: Optional[float] = None
    budget = calculate_risk_budget(balance_jpy, limits)
    values = (daily_loss_pct, drawdown_pct, spread_points, max_spread_points, entry_price)
    if not all(isfinite(v) for v in values):
        reasons.append("価格またはリスク指標が有限値ではありません")
    if not is_demo and not limits.allow_live:
        reasons.append("ライブ取引は禁止。デモ口座で検証してください")
    if daily_loss_pct >= limits.max_daily_loss_pct:
        reasons.append("日次損失上限に到達しています")
    if drawdown_pct >= limits.max_drawdown_pct:
        reasons.append("最大ドローダウン上限に到達しています")
    if open_positions >= limits.max_open_positions:
        reasons.append("同時保有ポジション数の上限です")
    if trades_today >= limits.max_trades_per_day:
        reasons.append("当日取引回数の上限です")
    if consecutive_losses >= limits.max_consecutive_losses:
        reasons.append("連敗停止条件に到達しています")
    if spread_points < 0 or max_spread_points <= 0 or spread_points > max_spread_points:
        reasons.append("スプレッド条件を満たしていません")
    if budget <= 0 or not (0 < limits.risk_per_trade_pct <= 0.5):
        reasons.append("1取引リスク予算の設定が許容範囲外です")
    if limits.allow_averaging or limits.allow_grid or limits.allow_martingale:
        reasons.append("ナンピン・グリッド・マーチンゲールは禁止です")

    if stop_loss is None or take_profit is None:
        reasons.append("発注前の損切り・利確価格が不足しています")
    elif all(isfinite(v) for v in (entry_price, stop_loss, take_profit)):
        if side.upper() == "BUY":
            risk, reward = entry_price - stop_loss, take_profit - entry_price
        elif side.upper() == "SELL":
            risk, reward = stop_loss - entry_price, entry_price - take_profit
        else:
            risk = reward = -1.0
            reasons.append("売買方向は BUY または SELL のみです")
        if risk <= 0 or reward <= 0:
            reasons.append("損切り・利確価格が売買方向に対して不正です")
        else:
            rr = reward / risk
            if rr < limits.min_reward_risk:
                reasons.append("リスクリワード比が最低基準未満です")
    else:
        reasons.append("損切り・利確価格が有限値ではありません")

    return RiskDecision(not reasons, tuple(reasons), budget, rr)
