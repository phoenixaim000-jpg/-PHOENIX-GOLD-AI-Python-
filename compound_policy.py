"""Conservative paper-only capital allocation and withdrawal rules.

No broker connection and no order placement. Monetary values are JPY.
The 30,000 JPY figure is a cap/target, not a promised or fixed yield.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple

D = Decimal

@dataclass(frozen=True)
class AllocationPolicy:
    capital_unit_jpy: Decimal = D("150000")
    withdrawal_threshold_jpy: Decimal = D("150000")
    monthly_withdrawal_cap_jpy: Decimal = D("30000")
    minimum_starting_equity_jpy: Decimal = D("100000")

class WithdrawalDecision(NamedTuple):
    eligible: bool
    amount_jpy: Decimal
    retained_profit_jpy: Decimal
    reason: str

def decide_monthly_withdrawal(
    equity_jpy: Decimal,
    realized_net_profit_jpy: Decimal,
    already_withdrawn_this_month_jpy: Decimal = D("0"),
    policy: AllocationPolicy = AllocationPolicy(),
) -> WithdrawalDecision:
    """Only realized net profit can be withdrawn; principal floor is preserved."""
    equity = D(equity_jpy)
    profit = max(D("0"), D(realized_net_profit_jpy))
    already = max(D("0"), D(already_withdrawn_this_month_jpy))
    remaining_cap = max(D("0"), policy.monthly_withdrawal_cap_jpy - already)

    if equity < policy.withdrawal_threshold_jpy:
        return WithdrawalDecision(False, D("0"), profit,
            "Equity below 150,000 JPY: retain realized profit and compound.")
    if remaining_cap <= 0:
        return WithdrawalDecision(False, D("0"), profit,
            "Monthly withdrawal cap already reached.")

    principal_floor = policy.withdrawal_threshold_jpy
    cash_above_floor = max(D("0"), equity - principal_floor)
    amount = min(profit, cash_above_floor, remaining_cap)
    retained = profit - amount

    if amount <= 0:
        return WithdrawalDecision(False, D("0"), profit,
            "No distributable realized profit above the preserved principal floor.")
    return WithdrawalDecision(True, amount, retained,
        "Eligible for user-approved withdrawal; no automatic transfer.")

def capital_units(equity_jpy: Decimal, policy: AllocationPolicy = AllocationPolicy()) -> int:
    """Count complete 150,000 JPY principal units; never count floating P/L."""
    return max(0, int(D(equity_jpy) // policy.capital_unit_jpy))

def max_monthly_withdrawal_capacity(equity_jpy: Decimal,
                                    policy: AllocationPolicy = AllocationPolicy()) -> Decimal:
    """Illustrative cap by complete units, not a return forecast."""
    return D(capital_units(equity_jpy, policy)) * policy.monthly_withdrawal_cap_jpy
