"""Capital protection and profit-distribution policy.

This module is accounting logic only. It does not place orders or promise returns.
All amounts are integer JPY. Withdrawals require explicit human approval.
"""
from dataclasses import dataclass
from math import floor


@dataclass(frozen=True)
class CapitalPolicy:
    principal_per_unit_jpy: int = 150_000
    monthly_distribution_per_unit_jpy: int = 30_000
    starting_equity_jpy: int = 100_000
    minimum_equity_jpy: int = 100_000
    require_realized_profit: bool = True


@dataclass(frozen=True)
class DistributionDecision:
    eligible_units: int
    target_jpy: int
    available_jpy: int
    approved_limit_jpy: int
    post_withdrawal_equity_jpy: int
    reason: str


def evaluate_distribution(
    equity_jpy: int,
    realized_profit_this_month_jpy: int,
    policy: CapitalPolicy = CapitalPolicy(),
) -> DistributionDecision:
    """Calculate a conservative ceiling; never execute a withdrawal.

    One distribution unit requires 150k principal plus 30k distributable
    realized surplus, so a 180k equity buffer is needed per unit. The
    post-withdrawal balance must retain 150k for every eligible unit.
    """
    equity = max(0, int(equity_jpy))
    realized = max(0, int(realized_profit_this_month_jpy))
    principal = max(1, int(policy.principal_per_unit_jpy))
    distribution = max(0, int(policy.monthly_distribution_per_unit_jpy))

    # A unit is counted only when both principal and its 30k distribution
    # buffer are present before withdrawal.
    eligible_units = floor(equity / (principal + distribution))
    target = eligible_units * distribution
    protected_principal = eligible_units * principal
    surplus_after_protection = max(0, equity - protected_principal)
    available = min(target, surplus_after_protection, realized if policy.require_realized_profit else surplus_after_protection)
    available = max(0, available)

    if eligible_units == 0:
        reason = "証拠金が1口分の元本＋分配余力に未到達。利益は複利運用へ残す。"
    elif available < target:
        reason = "実現利益または安全余力が目標額に不足。全額引出しは行わない。"
    else:
        reason = "計算上の分配上限に到達。出金前に人が残高・証拠金維持率を確認する。"

    return DistributionDecision(
        eligible_units=eligible_units,
        target_jpy=target,
        available_jpy=available,
        approved_limit_jpy=available,
        post_withdrawal_equity_jpy=equity - available,
        reason=reason,
    )
