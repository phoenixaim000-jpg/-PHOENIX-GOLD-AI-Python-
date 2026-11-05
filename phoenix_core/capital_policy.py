"""Profit distribution rules that protect the configured capital reserve."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CapitalPolicy:
    capital_per_unit_jpy: int = 150_000
    monthly_payout_cap_per_unit_jpy: int = 30_000

    def __post_init__(self):
        if self.capital_per_unit_jpy <= 0 or self.monthly_payout_cap_per_unit_jpy < 0:
            raise ValueError("Invalid capital policy")


@dataclass(frozen=True)
class PayoutDecision:
    capital_units: int
    protected_capital_jpy: int
    monthly_payout_cap_jpy: int
    suggested_payout_jpy: int
    retained_profit_jpy: int
    eligible: bool
    reason: str


def decide_monthly_payout(*, account_balance_jpy: int,
                          monthly_realized_net_profit_jpy: int,
                          capital_units: int,
                          already_paid_this_month_jpy: int = 0,
                          policy: CapitalPolicy = CapitalPolicy()) -> PayoutDecision:
    """Suggest payout only from realized net profit and above the protected reserve.

    Integer JPY only. Does not execute a broker withdrawal or bank transfer.
    Unrealized P/L cannot be used as payout source.
    """
    values = (account_balance_jpy, monthly_realized_net_profit_jpy,
              capital_units, already_paid_this_month_jpy)
    if any(not isinstance(v, int) for v in values):
        raise TypeError("All amounts and capital_units must be integers")
    if account_balance_jpy < 0 or capital_units < 1 or already_paid_this_month_jpy < 0:
        raise ValueError("Balance, payout history and capital units are out of range")

    reserve = capital_units * policy.capital_per_unit_jpy
    monthly_cap = capital_units * policy.monthly_payout_cap_per_unit_jpy
    cap_remaining = max(0, monthly_cap - already_paid_this_month_jpy)
    profit_remaining = max(0, monthly_realized_net_profit_jpy - already_paid_this_month_jpy)
    above_reserve = max(0, account_balance_jpy - reserve)
    payout = min(cap_remaining, profit_remaining, above_reserve)
    retained = max(0, monthly_realized_net_profit_jpy - already_paid_this_month_jpy - payout)

    if account_balance_jpy < reserve:
        reason = "維持証拠金未満のため出金せず複利へ回します"
    elif monthly_realized_net_profit_jpy <= already_paid_this_month_jpy:
        reason = "当月の出金可能な確定純利益がありません"
    elif payout == 0:
        reason = "維持額・確定利益・月間上限の条件を満たしていません"
    elif payout < cap_remaining:
        reason = "条件を満たす範囲だけ一部出金できます"
    else:
        reason = "全条件を満たしています。人が出金額を最終確認してください"

    return PayoutDecision(capital_units, reserve, monthly_cap, payout, retained,
                          payout > 0, reason)
