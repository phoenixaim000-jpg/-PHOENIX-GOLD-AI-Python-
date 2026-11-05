# Compounding and capital-protection policy

## User's intended money flow
- Start simulation from JPY 100,000.
- Treat JPY 150,000 as one protected principal unit.
- A unit's aspirational monthly free-cash target is JPY 30,000.
- Below the distribution gate, keep profits in the account and compound; do not withdraw.
- Six principal units (JPY 900,000) correspond to an aspirational JPY 180,000 monthly target.

## Conservative distribution gate
A full JPY 30,000 distribution must not reduce the protected principal below JPY 150,000. Therefore one unit needs JPY 180,000 equity before a full distribution. Six units need JPY 1,080,000 before a full JPY 180,000 distribution, leaving JPY 900,000.

The program calculates a ceiling only. It caps the ceiling by realized profit for the current month and available equity. It never initiates a bank/broker withdrawal. A person must approve any withdrawal after checking margin level, open risk, fees, taxes, and broker restrictions.

## Trading safety gates
- PAPER_ONLY by default; live trading disabled.
- Risk per trade default 0.25% of equity; daily loss stop 1%; high-water drawdown stop 5%.
- One open position, at most five entries/day, lock after three consecutive losses.
- No martingale, grid, averaging down, confidence-based lot multiplier, or forced minimum-lot rounding.
- Every live order would need broker-side SL/TP and verified execution/protection; this repository change does not enable live trading.

## Important reality check
JPY 30,000/month from JPY 150,000 is a 20% monthly target, not a predictable or low-risk yield. Six units scaling the target to JPY 180,000/month is arithmetic, not evidence that returns scale linearly. Losses, volatility, fees, spread, swaps, slippage, gaps, taxes, and changing market regimes can prevent distributions or reduce principal.

## Integration status
The policy module is deliberately separate from order execution. Integrate only after reviewing the existing EA, reconciling account balance/equity/realized P&L definitions, and passing tests plus demo validation. Never use this module to size positions or infer a safe lot without broker contract specifications.
