"""Fail-closed order prechecks. This module never sends broker orders."""
from dataclasses import dataclass
from math import floor, isfinite
from typing import Optional

def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)

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

    def __post_init__(self):
        if not finite_number(self.risk_per_trade_pct) or not 0 < self.risk_per_trade_pct <= 0.25:
            raise ValueError("risk_per_trade_pct must be in (0, 0.25]")
        if not finite_number(self.max_daily_loss_pct) or not 0 < self.max_daily_loss_pct <= 1.0:
            raise ValueError("max_daily_loss_pct must be in (0, 1.0]")
        if not finite_number(self.max_drawdown_pct) or not 0 < self.max_drawdown_pct <= 5.0:
            raise ValueError("max_drawdown_pct must be in (0, 5.0]")
        if type(self.max_open_positions) is not int or self.max_open_positions != 1:
            raise ValueError("max_open_positions is fixed at 1 in this paper profile")
        if type(self.max_trades_per_day) is not int or not 1 <= self.max_trades_per_day <= 5:
            raise ValueError("max_trades_per_day must be between 1 and 5")
        if type(self.max_consecutive_losses) is not int or not 1 <= self.max_consecutive_losses <= 2:
            raise ValueError("max_consecutive_losses must be 1 or 2")
        if not finite_number(self.min_reward_risk) or self.min_reward_risk < 1.5:
            raise ValueError("min_reward_risk must be at least 1.5")
        if any(type(x) is not bool for x in (self.allow_live, self.allow_averaging, self.allow_grid, self.allow_martingale)):
            raise ValueError("risk switches must be booleans")

@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...]
    risk_budget_jpy: int
    reward_risk_ratio: Optional[float]

def calculate_risk_budget(balance_jpy: int, limits: RiskLimits = RiskLimits()) -> int:
    if type(balance_jpy) is not int or balance_jpy < 0:
        raise ValueError("balance_jpy must be a non-negative integer")
    return floor(balance_jpy * limits.risk_per_trade_pct / 100)

def evaluate_order(*, is_demo: bool, balance_jpy: int, daily_loss_pct: float,
                   drawdown_pct: float, open_positions: int, trades_today: int,
                   consecutive_losses: int, spread_points: float,
                   max_spread_points: float, side: str, entry_price: float,
                   stop_loss: Optional[float], take_profit: Optional[float],
                   limits: RiskLimits = RiskLimits()) -> RiskDecision:
    reasons, rr = [], None
    if type(balance_jpy) is not int or balance_jpy < 0:
        budget = 0
        reasons.append("口座残高が不正です")
    else:
        budget = calculate_risk_budget(balance_jpy, limits)
    if type(is_demo) is not bool:
        reasons.append("口座種別を確認できません")
    elif not is_demo and not limits.allow_live:
        reasons.append("ライブ取引は禁止。デモ口座で検証してください")
    counters = (open_positions, trades_today, consecutive_losses)
    if any(type(x) is not int or x < 0 for x in counters):
        reasons.append("ポジション数・取引回数・連敗数が不正です")
    else:
        if open_positions >= limits.max_open_positions:
            reasons.append("同時保有ポジション数の上限です")
        if trades_today >= limits.max_trades_per_day:
            reasons.append("当日取引回数の上限です")
        if consecutive_losses >= limits.max_consecutive_losses:
            reasons.append("連敗停止条件に到達しています")
    metrics = (daily_loss_pct, drawdown_pct, spread_points, max_spread_points, entry_price)
    if not all(finite_number(x) for x in metrics):
        reasons.append("価格またはリスク指標が有限の数値ではありません")
    else:
        if daily_loss_pct < 0 or drawdown_pct < 0 or spread_points < 0 or max_spread_points <= 0:
            reasons.append("損失率・ドローダウン・スプレッドの入力範囲が不正です")
        if daily_loss_pct >= limits.max_daily_loss_pct:
            reasons.append("日次損失上限に到達しています")
        if drawdown_pct >= limits.max_drawdown_pct:
            reasons.append("最大ドローダウン上限に到達しています")
        if spread_points > max_spread_points:
            reasons.append("スプレッド条件を満たしていません")
        if entry_price <= 0:
            reasons.append("エントリー価格が不正です")
    if budget <= 0:
        reasons.append("リスク予算が0円です")
    if limits.allow_averaging or limits.allow_grid or limits.allow_martingale:
        reasons.append("ナンピン・グリッド・マーチンゲールは禁止です")
    if stop_loss is None or take_profit is None:
        reasons.append("発注前の損切り・利確価格が不足しています")
    elif not all(finite_number(x) for x in (entry_price, stop_loss, take_profit)):
        reasons.append("損切り・利確価格が有限の数値ではありません")
    elif stop_loss <= 0 or take_profit <= 0:
        reasons.append("損切り・利確価格は正の値が必要です")
    elif isinstance(side, str) and side.upper() == "BUY":
        risk, reward = entry_price - stop_loss, take_profit - entry_price
        if risk <= 0 or reward <= 0:
            reasons.append("BUYの損切り・利確価格が不正です")
        else:
            rr = reward / risk
    elif isinstance(side, str) and side.upper() == "SELL":
        risk, reward = stop_loss - entry_price, entry_price - take_profit
        if risk <= 0 or reward <= 0:
            reasons.append("SELLの損切り・利確価格が不正です")
        else:
            rr = reward / risk
    else:
        reasons.append("売買方向は BUY または SELL のみです")
    if rr is not None and rr < limits.min_reward_risk:
        reasons.append("リスクリワード比が最低基準未満です")
    return RiskDecision(not reasons, tuple(reasons), budget, rr)
