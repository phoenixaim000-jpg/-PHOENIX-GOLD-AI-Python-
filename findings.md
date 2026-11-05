# PHOENIX GOLD AI — Audit Findings

**Audit scope:** repository default branch `main` and the current review branch.
**Audit type:** static source inspection. No MT5 terminal, broker account, market feed, or live order was connected.
**Date:** 2026-11-06
**Disposition:** unsafe for live trading; demo execution is also not yet integrated.

## Executive summary

The repository is a small prototype, not a complete MT5 trading system. It contains draft Python scripts and explanatory snippets. The existing two-loss stop is not connected to actual closed-deal history, is not persisted across process restarts, and does not prevent the current draft from being mistaken for a working risk control. The GOLD script describes averaging up to five times, but the body is only placeholder logic; it does not actually implement order execution or loss accounting.

The review branch adds a broker-agnostic capital policy and market-regime classifier. These are standalone modules: they are not wired into the legacy MT5 scripts, do not fetch live data, and do not submit orders. Passing their unit tests does not validate an EA or broker execution.

## Findings

| ID | Severity | File / area | Evidence and impact | Recommended action |
|---|---|---|---|---|
| GOLD-001 | Critical | `PHOENIX GOLD AI (Python)ナンピン` | `MAX_NANPIN_COUNT = 5` and `NANPIN_GAP = 2.0` advertise averaging into adverse movement. This can expand exposure and margin use while a position is losing. | Do not execute this legacy script. Keep averaging/grid disabled in server-side policy and reject those order intents. |
| GOLD-002 | Critical | GOLD and BTC prototype scripts | `consecutive_losses` is initialized to zero, but no active MT5 history/deal reconciliation increments it. The two-loss stop therefore does not currently observe actual closed losses. | Add an idempotent closed-trade ledger adapter; only count reconciled, fully closed position results net of fees. |
| GOLD-003 | Critical | GOLD and BTC prototype scripts | `is_active` and loss count exist only in process memory. Restarting the program resets them. | Persist lock state atomically; corrupt/missing state must fail closed; require a documented manual review to clear a lock. |
| GOLD-004 | High | BTC prototype | `signal = "BUY"` is a fixed dummy signal. No validated strategy or live market analysis produces it. | Remove from execution path; signal-only research until data and strategy tests exist. |
| GOLD-005 | High | GOLD prototype | `logic_nanpin_order()` contains comments and pseudo-code; no actual position manager, stop placement, order result check, or fill reconciliation exists. | Do not represent as an operational EA. Implement broker adapter separately after broker contract details are known. |
| GOLD-006 | High | BTC prototype | The MT5 order call is commented out. The script sends a notification about a signal but does not place or verify an order. | Label as notification prototype, not automatic trading. |
| GOLD-007 | High | Both prototypes | MT5 initialization failure calls `quit()`; there is no structured shutdown, terminal-state health check, or reconnect policy. | Add controlled lifecycle management and explicit health state in a future adapter. |
| GOLD-008 | Medium | Both prototypes | LINE Notify URL is embedded and the request has no timeout, response validation, or retry policy. The token is only a placeholder in the checked source, not a usable secret. | Use a supported notification provider via environment variables; timeout and redact secrets. Never commit real tokens. |
| GOLD-009 | Medium | Repository | No `requirements.txt`, `pyproject.toml`, or complete setup/run guide exists on `main`. `.gitignore` appears Android/Gradle-oriented rather than Python-focused. | Add pinned/declared optional dependencies and Python ignore rules after adapter scope is selected. |
| GOLD-010 | Medium | `aggressive_mode.py` | The file contains only the literal text `VISION-FX-EA-GEMINI`, not executable Python. | Treat as a placeholder/reference marker; do not import or execute it. |
| GOLD-011 | Medium | Review-branch `phoenix_capital_policy.py` | The policy is a pure calculation/gate. It expects risk already converted to JPY and does not fetch broker tick values, contract size, positions, or account equity. | Keep it disconnected from order placement until broker-specific adapters and conversion tests exist. |
| GOLD-012 | Medium | Review-branch `market_regime.py` | It analyzes supplied OHLC candles only. It does not verify timestamps, candle closure, stale feed, spread, sessions, or source identity itself. | Make the data adapter validate freshness and completed bars; preserve source/time/environment metadata. |

## Confirmed repository inventory (default branch)

- `.gitignore`
- `README.md`
- `aggressive_mode.py`
- Two long-named Python prototype/snippet files, including the GOLD averaging draft and BTC/USD draft

The default branch did not contain a frontend HTML dashboard, FastAPI service, backend API, database, MT5 adapter package, test suite, or deployment/server configuration at the time of inspection. No `Math.random()`, `positions` array, HTML mock balance, or browser-side deposit/withdrawal implementation was found because no HTML frontend is present in this repository inventory.

## Existing review-branch additions

The review branch contains `phoenix_capital_policy.py`, `market_regime.py`, paper configuration, documentation, tests, and a GitHub Actions workflow. These are useful foundations but remain disconnected from the original MT5 prototype scripts. The workflow runs Python unit tests only; it does not test MT5, broker APIs, UI/API behavior, or live-order isolation.

## Required next phases

1. Replace the unpersisted two-loss flag with a durable, idempotent loss lock.
2. Keep the lock and risk gate independent of any broker order function.
3. Add a read-only MT5 adapter for account, symbol metadata, open positions, and closed-deal reconciliation.
4. Add a PAPER/DEMO simulator and prove no LIVE request can be reached from its configuration.
5. Only after the broker is named, implement contract/tick-value/JPY risk conversion and server-side SL/TP verification.
6. Add API/UI only if the actual dashboard/frontend exists or is supplied; do not invent one.
7. Keep live mode disabled pending separate security review and explicit approval.

## Reproduction / verification

- Static inspection: read the listed files from `main` and review branch.
- Search targets: `MAX_NANPIN_COUNT`, `NANPIN_GAP`, `consecutive_losses`, `is_active`, `signal = "BUY"`, commented `execute_trade`, and MT5 initialization.
- No live order, deposit, withdrawal, broker login, or external notification was attempted.
- Existing review-branch GitHub Actions reported 24 passing unit tests for the standalone policy/scanner at its recorded run. This is not evidence that the legacy scripts or a broker adapter are safe.
