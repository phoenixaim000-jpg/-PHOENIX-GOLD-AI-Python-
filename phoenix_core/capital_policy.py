"""Reserve-protected payout suggestions. No transfers or broker withdrawals."""
from dataclasses import dataclass

@dataclass(frozen=True)
class CapitalPolicy:
    capital_per_unit_jpy: int = 150_000
    monthly_payout_cap_per_unit_jpy: int = 30_000

    def __post_init__(self):
        if type(self.capital_per_unit_jpy) is not int or self.capital_per_unit_jpy <= 0:
            raise ValueError("capital_per_unit_jpy must be a positive integer")
        if type(self.monthly_payout_cap_per_unit_jpy) is not int or self.monthly_payout_cap_per_unit_jpy < 0:
            raise ValueError("monthly payout cap must be a non-negative integer")

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
                          capital_units: int = 1,
                          already_paid_this_month_jpy: int = 0,
                          policy: CapitalPolicy = CapitalPolicy()) -> PayoutDecision:
    """Use cumulative closed-trade net P/L after fees; floating P/L is excluded.

    capital_units is an explicit committed-capital setting, not inferred from
    floating equity. Six units protect 900,000 JPY and cap payout at 180,000 JPY.
    """
    values = (account_balance_jpy, monthly_realized_net_profit_jpy,
              capital_units, already_paid_this_month_jpy)
    if any(type(value) is not int for value in values):
        raise TypeError("all amounts and capital_units must be integers")
    if account_balance_jpy < 0 or capital_units < 1 or already_paid_this_month_jpy < 0:
        raise ValueError("balance, payout history, or capital units are out of range")
    if not isinstance(policy, CapitalPolicy):
        raise TypeError("policy must be CapitalPolicy")

    reserve = capital_units * policy.capital_per_unit_jpy
    monthly_cap = capital_units * policy.monthly_payout_cap_per_unit_jpy
    cap_remaining = max(0, monthly_cap - already_paid_this_month_jpy)
    profit_remaining = max(0, monthly_realized_net_profit_jpy - already_paid_this_month_jpy)
    balance_above_reserve = max(0, account_balance_jpy - reserve)
    payout = min(cap_remaining, profit_remaining, balance_above_reserve)
    retained = max(0, monthly_realized_net_profit_jpy - already_paid_this_month_jpy - payout)

    if account_balance_jpy < reserve:
        reason = "維持証拠金未満のため出金せず、確定利益を口座内に残します"
    elif payout == 0:
        reason = "確定純利益・維持額超過残高・月間上限の条件を満たしていません"
    elif payout < cap_remaining:
        reason = "条件を満たす範囲だけ一部出金を提案できます"
    else:
        reason = "上限内の出金候補です。人が出金額を最終確認してください"
    return PayoutDecision(capital_units, reserve, monthly_cap, payout, retained,
                          payout > 0, reason)
