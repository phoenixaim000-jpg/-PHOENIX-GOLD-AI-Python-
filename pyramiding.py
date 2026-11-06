"""Risk-gated pyramiding policy for PHOENIX GOLD.

Pyramiding means adding to a profitable position as price moves favorably.
This module only evaluates an add-on request; it never connects to a broker,
changes stops, or submits orders. All cash-risk inputs must be independently
calculated by a broker-aware adapter and include fees, slippage and JPY FX.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class PyramidingConfig:
    max_additions: int = 2
    add_step_atr: float = 1.0
    max_aggregate_open_risk_bps: int = 100
    max_single_add_risk_bps: int = 25

    def __post_init__(self) -> None:
        if self.max_additions < 0:
            raise ValueError("max_additions must be >= 0")
        if not isfinite(self.add_step_atr) or self.add_step_atr <= 0:
            raise ValueError("add_step_atr must be > 0")
        if not 1 <= self.max_single_add_risk_bps <= self.max_aggregate_open_risk_bps <= 10_000:
            raise ValueError("risk limits must satisfy 1 <= single <= aggregate <= 10000")


@dataclass(frozen=True)
class PyramidingDecision:
    allowed: bool
    reason_code: str
    message: str
    additions_after_order: int
    proposed_total_open_risk_jpy: int
    max_aggregate_open_risk_jpy: int
    max_single_add_risk_jpy: int


def evaluate_pyramid_add(
    *,
    direction: str,
    average_entry_price: float,
    last_add_price: float,
    current_price: float,
    atr: float,
    current_additions: int,
    equity_jpy: int,
    current_open_risk_jpy: int,
    proposed_add_risk_jpy: int,
    stop_loss_confirmed: bool,
    market_data_fresh: bool,
    mode: str = "PAPER",
    config: PyramidingConfig | None = None,
) -> PyramidingDecision:
    """Evaluate one favorable-move add-on; does not place or modify an order."""
    cfg = config or PyramidingConfig()
    if direction not in {"LONG", "SHORT"}:
        raise ValueError("direction must be LONG or SHORT")

    numeric = {
        "average_entry_price": average_entry_price,
        "last_add_price": last_add_price,
        "current_price": current_price,
        "atr": atr,
    }
    for name, value in numeric.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError(f"{name} must be a finite number")
    if any(value <= 0 for value in numeric.values()):
        raise ValueError("prices and ATR must be greater than zero")

    integers = {
        "current_additions": current_additions,
        "equity_jpy": equity_jpy,
        "current_open_risk_jpy": current_open_risk_jpy,
        "proposed_add_risk_jpy": proposed_add_risk_jpy,
    }
    for name, value in integers.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    max_total = equity_jpy * cfg.max_aggregate_open_risk_bps // 10_000
    max_add = equity_jpy * cfg.max_single_add_risk_bps // 10_000
    proposed_total = current_open_risk_jpy + proposed_add_risk_jpy

    def deny(code: str, message: str) -> PyramidingDecision:
        return PyramidingDecision(
            False, code, message, current_additions, proposed_total, max_total, max_add
        )

    if mode.upper() not in {"PAPER", "PAPER_ONLY", "DEMO"}:
        return deny("LIVE_DISABLED", "PAPER/DEMO以外では追加を許可しません。")
    if equity_jpy <= 0:
        return deny("INVALID_EQUITY", "有効証拠金が0円以下です。")
    if not market_data_fresh:
        return deny("STALE_DATA", "価格データが古いため追加を見送ります。")
    if not stop_loss_confirmed:
        return deny("STOP_NOT_CONFIRMED", "既存分と追加分の損切り保護を確認できないため追加禁止です。")
    if current_additions >= cfg.max_additions:
        return deny("MAX_ADDITIONS", "ピラミッディング追加回数の上限です。")
    if proposed_add_risk_jpy <= 0 or proposed_add_risk_jpy > max_add:
        return deny("ADD_RISK_LIMIT", "追加分の想定損失額が1回あたりの上限を超えています。")
    if proposed_total > max_total:
        return deny("AGGREGATE_RISK_LIMIT", "追加後の合計想定損失額が証拠金比の上限を超えます。")

    favorable = current_price > average_entry_price if direction == "LONG" else current_price < average_entry_price
    if not favorable:
        return deny("NOT_IN_PROFIT", "既存ポジションが利益方向に進んでいないため追加禁止です。")

    step = atr * cfg.add_step_atr
    moved_enough = (
        current_price >= last_add_price + step
        if direction == "LONG"
        else current_price <= last_add_price - step
    )
    if not moved_enough:
        return deny("ADD_STEP_NOT_REACHED", "前回追加価格から所定のATR幅が進んでいません。")

    return PyramidingDecision(
        True,
        "PAPER_PYRAMID_ADD_APPROVED",
        "利益方向・追加間隔・損切り確認・合計リスク条件を満たしました。発注承認や利益保証ではありません。",
        current_additions + 1,
        proposed_total,
        max_total,
        max_add,
    )
