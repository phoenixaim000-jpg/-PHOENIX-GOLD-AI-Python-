# PHOENIX GOLD AI — safe compound policy prototype

This branch adds a **paper-only** capital and withdrawal policy module.

## Intended rule
- Starting equity reference: 100,000 JPY (demo/paper operation first).
- One capital unit: 150,000 JPY.
- When account equity is below 150,000 JPY, no monthly withdrawal is eligible; positive realized net profit is retained in the account for compounding.
- At/above 150,000 JPY, a withdrawal may be considered only from realized net profit, after costs, capped at 30,000 JPY per unit per month. The principal floor is preserved.
- Withdrawals are not automatic. User review and broker/account verification are required.
- Complete units illustrate capacity: 6 units / 900,000 JPY gives an illustrative cap of 180,000 JPY per month, **not a forecast or guarantee**.

## Safety
- Paper-only; live trading disabled.
- 0.25% indicative risk per trade, 1% total open risk, 1% daily loss stop, 5% high-water drawdown stop, 2 consecutive losses stop.
- No martingale, grid, or averaging down. Existing averaging code is not imported into this safety path.
- Reject trades if broker minimum lot exceeds the risk budget.
- No guaranteed profit, no fixed monthly yield, and a stop-loss may execute at a worse price in gaps/slippage.

## Files
- `compound_policy.py`: deterministic JPY allocation and withdrawal calculation.
- `config/compound_policy.paper.json`: configuration reference.
- `tests/test_compound_policy.py`: boundary and cap tests.

This module is not yet wired into the existing MT5 strategy or broker execution code.
