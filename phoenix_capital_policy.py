"""Capital compounding and fail-closed risk controls for PHOENIX/VISION.

This module is deliberately broker-agnostic. It calculates JPY budgets and
withdrawal plans; it does not submit, modify, or close broker orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CapitalPolicy:
    capital_unit_jpy: int = 150_000
    monthly_allowance_per_unit_jpy: int = 30_000
    risk_per_trade_bps: int = 25          # 0.25%
    max_daily_loss_bps: int = 100         # 1.00%
    max_drawdown_bps: int = 500           # 5.00%
    max_aggregate_open_risk_bps: int = 100  # 1.00%
    max_open_positions: int = 1
    max_consecutive_losses: int = 2
    allow_averaging: bool = False
    allow_grid: bool = False
    allow_martingale: bool = False

    def __post_init__(self) -> None:
        positive = (
            "capital_unit_jpy",
            "monthly_allowance_per_unit_jpy",
            "risk_per_trade_bps",
            "max_daily_loss_bps",
            "max_drawdown_bps",
            "max_aggregate_open_risk_bps",
            "max_open_positions",
            "max_consecutive_losses",
        )
        for name in positive:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.risk_per_trade_bps > self.max_aggregate_open_risk_bps:
            raise ValueError("single-trade risk cannot exceed aggregate open-risk limit")


@dataclass(frozen=True)
class WithdrawalPlan:
    opening_equity_jpy: int
    closing_equity_jpy: int
    net_realized_profit_jpy: int
    eligible_units: int
    protected_floor_jpy: int
    monthly_cap_jpy: int
    surplus_above_floor_jpy: int
    withdrawable_jpy: int
    retained_profit_jpy: int
    reason: str


def _require_non_negative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer JPY amount")


def plan_monthly_withdrawal(
    opening_equity_jpy: int,
    closing_equity_jpy: int,
    net_realized_profit_jpy: int,
    policy: Optional[CapitalPolicy] = None,
) -> WithdrawalPlan:
    """Calculate a monthly cap; never initiate an actual bank/broker transfer.

    Eligible units are fixed from opening equity. Profit must be realized and
    net of commission, swap/funding, and other trading costs. Closing equity
    is measured before the proposed withdrawal and should exclude new deposits.
    """
    p = policy or CapitalPolicy()
    _require_non_negative_int("opening_equity_jpy", opening_equity_jpy)
    _require_non_negative_int("closing_equity_jpy", closing_equity_jpy)
    if isinstance(net_realized_profit_jpy, bool) or not isinstance(net_realized_profit_jpy, int):
        raise ValueError("net_realized_profit_jpy must be an integer JPY amount")

    units = opening_equity_jpy // p.capital_unit_jpy
    protected_floor = units * p.capital_unit_jpy
    monthly_cap = units * p.monthly_allowance_per_unit_jpy
    surplus = max(0, closing_equity_jpy - protected_floor)
    positive_realized_profit = max(0, net_realized_profit_jpy)
    withdrawable = min(monthly_cap, surplus, positive_realized_profit)
    retained = max(0, positive_realized_profit - withdrawable)

    if units == 0:
        reason = "月初証拠金が1口未満のため、出金枠は0円。利益は再投資対象です。"
    elif positive_realized_profit == 0:
        reason = "出金対象となる確定純利益がありません。"
    elif surplus == 0:
        reason = "出金後に維持すべき元本防衛ラインを超える余剰がありません。"
    elif withdrawable < monthly_cap:
        reason = "確定純利益または元本防衛ライン上の余剰額が月間上限未満です。"
    else:
        reason = "確定純利益と元本防衛ラインを確認した月間上限内の出金候補です。"

    return WithdrawalPlan(
        opening_equity_jpy=opening_equity_jpy,
        closing_equity_jpy=closing_equity_jpy,
        net_realized_profit_jpy=net_realized_profit_jpy,
        eligible_units=units,
        protected_floor_jpy=protected_floor,
        monthly_cap_jpy=monthly_cap,
        surplus_above_floor_jpy=surplus,
        withdrawable_jpy=withdrawable,
        retained_profit_jpy=retained,
        reason=reason,
    )


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason_code: str
    message: str
    max_trade_risk_jpy: int
    max_daily_loss_jpy: int
    max_drawdown_jpy: int
    max_aggregate_open_risk_jpy: int


def evaluate_new_trade(
    *,
    equity_jpy: int,
    day_start_equity_jpy: int,
    high_water_equity_jpy: int,
    proposed_risk_jpy: int,
    current_open_risk_jpy: int = 0,
    open_positions: int = 0,
    consecutive_losses: int = 0,
    mode: str = "PAPER",
    is_averaging_order: bool = False,
    is_martingale_order: bool = False,
    is_grid_order: bool = False,
    market_data_fresh: bool = True,
    spread_within_limit: bool = True,
    policy: Optional[CapitalPolicy] = None,
) -> RiskDecision:
    """Fail-closed pre-trade gate. Risk amounts must already be estimated in JPY.

    Broker-specific tick values, contract size, stop distance, fees and slippage
    must be included by the adapter before calling this function. Never round a
    too-large minimum broker lot upward to force an order through this gate.
    """
    p = policy or CapitalPolicy()
    values = {
        "equity_jpy": equity_jpy,
        "day_start_equity_jpy": day_start_equity_jpy,
        "high_water_equity_jpy": high_water_equity_jpy,
        "proposed_risk_jpy": proposed_risk_jpy,
        "current_open_risk_jpy": current_open_risk_jpy,
        "open_positions": open_positions,
        "consecutive_losses": consecutive_losses,
    }
    for name, value in values.items():
        _require_non_negative_int(name, value)

    max_trade = equity_jpy * p.risk_per_trade_bps // 10_000
    max_daily = day_start_equity_jpy * p.max_daily_loss_bps // 10_000
    max_dd = high_water_equity_jpy * p.max_drawdown_bps // 10_000
    max_open = equity_jpy * p.max_aggregate_open_risk_bps // 10_000

    def deny(code: str, message: str) -> RiskDecision:
        return RiskDecision(False, code, message, max_trade, max_daily, max_dd, max_open)

    if mode.upper() not in {"PAPER", "PAPER_ONLY", "DEMO"}:
        return deny("LIVE_DISABLED", "ライブ口座への新規発注は無効です。PAPER/DEMO検証のみ許可します。")
    if equity_jpy <= 0 or day_start_equity_jpy <= 0 or high_water_equity_jpy <= 0:
        return deny("INVALID_EQUITY", "証拠金・日初残高・最高残高のいずれかが0です。")
    if proposed_risk_jpy <= 0:
        return deny("INVALID_RISK", "損切りまでの想定損失額が0円以下です。")
    if not market_data_fresh:
        return deny("STALE_DATA", "価格データが古い、または更新確認できないため見送ります。")
    if not spread_within_limit:
        return deny("SPREAD_TOO_WIDE", "スプレッドが上限を超えているため見送ります。")
    if is_averaging_order and not p.allow_averaging:
        return deny("AVERAGING_DISABLED", "ナンピン・買い下がり・売り上がりは禁止です。")
    if is_grid_order and not p.allow_grid:
        return deny("GRID_DISABLED", "グリッド注文は禁止です。")
    if is_martingale_order and not p.allow_martingale:
        return deny("MARTINGALE_DISABLED", "マーチンゲール・倍掛けは禁止です。")
    if open_positions >= p.max_open_positions:
        return deny("POSITION_LIMIT", "同時保有ポジション数の上限です。")
    if consecutive_losses >= p.max_consecutive_losses:
        return deny("LOSS_STREAK_LOCK", "連続損失上限に達しました。新規発注を停止します。")
    if day_start_equity_jpy - equity_jpy >= max_daily:
        return deny("DAILY_LOSS_LIMIT", "日次損失上限に達しました。")
    if high_water_equity_jpy - equity_jpy >= max_dd:
        return deny("DRAWDOWN_LIMIT", "最高残高からのドローダウン上限に達しました。")
    if proposed_risk_jpy > max_trade:
        return deny("TRADE_RISK_LIMIT", "1回の想定損失額が証拠金比の上限を超えています。")
    if current_open_risk_jpy + proposed_risk_jpy > max_open:
        return deny("AGGREGATE_RISK_LIMIT", "保有中を含む合計想定損失額が上限を超えます。")

    return RiskDecision(
        True,
        "PAPER_APPROVED",
        "リスク条件内です。これはPAPER/DEMOの判定であり、注文成立や利益を保証しません。",
        max_trade,
        max_daily,
        max_dd,
        max_open,
    )
