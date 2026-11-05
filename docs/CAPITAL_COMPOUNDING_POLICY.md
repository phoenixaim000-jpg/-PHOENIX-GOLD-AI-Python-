# Capital compounding and withdrawal policy

## Purpose
This policy gives the account a protected compounding path from JPY 100,000 while defining a conditional discretionary-withdrawal ceiling. It does not promise returns or create a fixed monthly salary.

## One unit and monthly ceiling
- One capital unit: JPY 150,000.
- Monthly discretionary-use ceiling per eligible unit: JPY 30,000.
- Eligible units are calculated from **equity at the beginning of the month**: floor(opening equity / 150,000).
- When opening equity is below JPY 150,000, eligible units and the monthly withdrawal ceiling are zero. Positive profits remain in the account for compounding.
- The unit count is fixed for that month. Crossing a unit threshold mid-month does not expand the same month's ceiling.

## Withdrawal calculation
The proposed withdrawal is the lowest of:
1. Monthly ceiling = eligible units × JPY 30,000.
2. Positive net realized trading profit for the month, after commissions, swaps/funding and other costs.
3. Closing equity before withdrawal minus the protected opening unit floor (eligible units × JPY 150,000).

The calculation is a **proposal only**. It never sends a transfer. The user must verify the broker statement, taxes, fees, deposits/withdrawals, and approve any withdrawal manually. Floating/unrealized P&L is not eligible.

Examples:
- Opening JPY 100,000: 0 units; even if the month is profitable, the allowance is JPY 0 and profits are retained.
- Opening JPY 150,000; closing JPY 180,000; net realized profit JPY 30,000: up to JPY 30,000 can be proposed, leaving JPY 150,000.
- Opening JPY 900,000; closing JPY 1,080,000; net realized profit JPY 180,000: up to JPY 180,000 can be proposed, leaving JPY 900,000.
- Opening JPY 900,000 but net realized profit only JPY 50,000: the proposal is at most JPY 50,000, not JPY 180,000.

The JPY 30,000-per-JPY-150,000 figure implies a 20% monthly return if fully used. This is an aggressive target, not a reliable or sustainable return assumption. Losses, gaps, slippage, margin close-out and broker execution can still reduce capital.

## Conservative trading gate (initial defaults)
- Risk at stop per trade: 0.25% of equity (JPY 250 at JPY 100,000; JPY 375 at JPY 150,000).
- Daily loss stop: 1% of day-start equity.
- Drawdown stop: 5% from equity high-water mark.
- Aggregate open risk: 1% of current equity.
- Maximum simultaneous positions: 1.
- Stop new entries after 2 consecutive losses.
- Averaging, grid, martingale and confidence-based lot multipliers: disabled.
- Live trading and automatic withdrawals: disabled.
- If the broker minimum volume would exceed the JPY risk budget, skip the trade. Never round volume upward to force an entry.

Risk estimates must include contract size, tick value, stop distance, spread, commission, swap/funding and realistic slippage. A broker adapter must convert those values to JPY correctly. This module intentionally does not guess broker-specific contract specifications.

## Integration boundary
Call `evaluate_new_trade()` immediately before any order request. Pass the estimated loss at the initial stop in JPY, total risk already open, current position count, the day-start equity, the equity high-water mark, and the current loss streak. The broker adapter must place broker-side SL/TP with the initial order and verify the broker's fill/retcode and protection state. No entry is allowed when the guard cannot be evaluated.

Call `plan_monthly_withdrawal()` only at monthly close using statement-verified closing equity and net realized P&L. It returns a proposal, not a transfer instruction.

## Validation required before any real funds
1. Unit tests pass.
2. Broker-specific contract-value and JPY conversion tests pass.
3. Historical, out-of-sample and walk-forward checks show costs and drawdown.
4. Demo operation for at least 8 weeks and preferably 100+ completed trades.
5. Reconcile every order, fill, SL/TP and account statement.
6. Obtain explicit manual approval before a separately reviewed, tiny live pilot.

No test or backtest proves future profitability. A stop order may fill at a worse price during gaps or fast markets.
