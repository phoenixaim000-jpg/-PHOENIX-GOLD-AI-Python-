# -PHOENIX-GOLD-AI-Python-
このプログラムは、2回連続の「全ポジション損切り」を検知した際にシステムをロックし、あなたの資産を物理的に保護します。


## Capital compounding policy (PAPER/DEMO only)
A broker-agnostic policy module has been added in `phoenix_capital_policy.py`.
It provides the same JPY 150,000 capital-unit / JPY 30,000 conditional monthly
ceiling and fail-closed risk checks used by the VISION project.
See [docs/CAPITAL_COMPOUNDING_POLICY.md](docs/CAPITAL_COMPOUNDING_POLICY.md)
and [config/capital_policy.paper.json](config/capital_policy.paper.json).

The legacy draft includes averaging and placeholder order logic. This new
module does not activate or repair those order paths. Integrate its gate and
validate broker-specific stop/risk calculations before any demo adapter is
enabled. Live trading and automatic withdrawals remain disabled.


## GOLD market filter
market_regime.py is the reusable VISION-style portion adopted here:
multi-timeframe trend agreement, range filtering, shock avoidance and candidate
ranking. PHOENIX GOLD should only consider an XAUUSD candidate when its selected
fast/slow timeframe data agree. This does not enable a trade or make a market
prediction certain. No 50x confidence multiplier or automatic averaging logic
has been copied into this new module.
