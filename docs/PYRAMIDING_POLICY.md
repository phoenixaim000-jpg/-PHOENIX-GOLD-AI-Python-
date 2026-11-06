# PHOENIX GOLD — Pyramiding policy (PAPER/DEMO only)

## Definition

Pyramiding adds exposure only after the existing position has moved in the
profitable direction. It is not averaging down into a losing position.

## Implemented policy module

`pyramiding.py` evaluates a proposed add-on and returns an allow/deny decision.
It does not connect to MT5, place orders, resize positions, or move broker stops.

Default limits:
- At most 2 add-ons after the initial position.
- Each add-on must be at most 0.25% of equity in estimated cash risk.
- Total open risk after the add-on must be at most 1.00% of equity.
- Price must move favorably by at least 1 ATR from the last add-on price.
- Existing position must be profitable relative to its average entry.
- Stop-loss protection must be confirmed by the caller for all legs.
- Market data must be fresh.
- LIVE mode is rejected.

## Adapter requirements before any execution integration

The adapter must calculate JPY risk from the broker's actual XAUUSD contract size,
tick size/value, account currency, stop distance, commission, swap, spread and
slippage. It must independently confirm broker-side stop-loss protection for
every position/leg and reconcile partial fills and netting/hedging account mode.
If any field is unknown, stale or inconsistent, reject the add-on.

Do not infer that a returned `allowed=True` is a broker order approval. The
function is a PAPER/DEMO policy gate only. It cannot guarantee a stop fill or
prevent gap/slippage losses.
