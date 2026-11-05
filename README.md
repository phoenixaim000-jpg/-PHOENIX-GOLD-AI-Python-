# PHOENIX GOLD AI Python

## Audit status

The default-branch code is a prototype, not a completed MT5 auto-trader. The
legacy GOLD script contains a five-step averaging configuration and pseudo-code;
it does not reconcile actual closed trades, persist the loss lock, or verify
broker-side protection. Do not run the legacy scripts on a live account.

See [findings.md](findings.md) for the static audit and [docs/CAPITAL_COMPOUNDING_POLICY.md](docs/CAPITAL_COMPOUNDING_POLICY.md)
for the separate capital policy.

## Persistent loss guard (PAPER_ONLY)

`phoenix_gold_safety.py` is a broker-independent loss guard. It:
- counts each fully closed position once using a stable trade/position ID;
- counts net realized JPY P&L after all costs;
- locks new entries after two consecutive losing closed positions;
- also locks at the configured daily realized-loss threshold;
- persists state across restarts and fails closed if the state file is corrupt;
- requires an explicit manual reset phrase and review reason.

It does not connect to MetaTrader5, read account history, place/close orders,
or prove a broker stop-loss has executed. A future read-only adapter must
reconcile closed positions and call the guard. Do not connect it to an order
function until that adapter and its tests are reviewed.

## Run tests

Requires Python 3.11 or later. The policy and guard modules use only the
Python standard library.

```bash
python -m unittest discover -s tests -v
```

## Safety boundary

- PAPER_ONLY policy; no broker connection or order submission.
- No averaging, grid, martingale, or automatic restart after a lock.
- Never store MT5 passwords, API tokens, or account credentials in this repo.
- A stop-loss can slip or gap; no program can guarantee zero loss.
