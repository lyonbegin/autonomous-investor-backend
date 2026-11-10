# Saved research strategies — verified Python chart component reuse

## Source and purpose
Reused the **LOWER Python chart** rendering logic from:
- \`lyonbegin/autonomous-investor-backend\`
- commit \`1c26e090ee1ffcc8b549f70df843d4e2fa616d4f\`
- \`public_frontend/src/components/DddsSharedChartCompare.tsx\`, \`PythonPlot\` lines 49–109.
- Both the source chart and the reuse use \`lightweight-charts\`, actual OHLCV input, Python-calculated plot values, synchronized visible timestamps.

This is *not* the older stock screener price chart. The old 7-screener is reused for **card/grid/pills layout only**.

New component: \`n8n/tradingview-screener-ui/src/strategy-python-chart.jsx\`

## API/data contract before showing any chart
The React component takes a **Python execution result**, not an arbitrary strategy title or OHLCV alone:

\`\`\`json
{
  "execution_status": "EXECUTED_REAL_MARKET_DATA",
  "strategy_id": "XPT-CASE-01",
  "strategy_version": "sha256:<published strategy-version sha>",
  "python_sha256": "<64 lowercase hexadecimal>",
  "source_dataset_sha256": "<64 lowercase hexadecimal>",
  "symbol": "NYMEX:PL",
  "timeframe": "1D",
  "bars": [
    {"timestamp": 1794268800000, "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0}
  ],
  "plots": {
    "PL/GC spread": [null],
    "Spread z-score": [null]
  },
  "fills": [
    {"timestamp": 1794268800000, "side": "BUY", "leg": "PLZ6", "quantity": 2, "price": 0}
  ],
  "source_provenance": {
    "paper_url": "https://...",
    "sample_start": "YYYY-MM-DD",
    "sample_end": "YYYY-MM-DD",
    "bar_provider": "<real historical exchange feed>",
    "backtest_status": "UNVERIFIED"
  }
}
\`\`\`

**The JSON above is a shape illustration; its dates/prices are NOT real market data.** A chart must never be rendered from it. In real responses \`bars\` must contain **at least two actual bars**, and plot arrays must match the exact bar count.

For two-leg trades, store every leg in \`fills\` and distinguish \`futures_contract\`, expiry, exchange, trading currency, multiplier, commission, slippage, and roll information in the canonical DB record. The card/chart shown for one symbol MUST NOT be mistaken for a complete pair strategy, whose secondary-leg chart and spread/equity panel require separate linked components.

Required DB identity:
- \`research_strategies\`: own strategy ID, title, detailed economic mechanism, source paper and original TradingView ID(s), S001–S087 + R01–R12 links, adoption judgement.
- \`strategy_python_versions\`: strategy/version source code, SHA256, dependencies, entrypoint, authored timestamp, generator provenance; immutable once used in a run.
- \`strategy_market_datasets\`: ticker/exchange/contract month/timeframe/range/feed/license, dataset SHA256, available bars.
- \`strategy_backtest_runs\`: strategy version + dataset + settings + Python runtime SHA + results; status only when actually executed.
- \`strategy_plot_points\`: per-time-bar Python outputs, indexed by strategy run and bar timestamp.
- \`strategy_fills\`: fills with leg, order, time, side, quantity, price, fees and slippage.

## Integration steps
1. Create a NEW research strategy list/page, e.g. \`/research-strategies/\`; do **not** modify the current 7-screener production site without its existing regression test suite.
2. Strategy cards must call a **real** DB-backed catalog API for title, description, market, date range, approval level, source paper, and latest verified run ID.
3. A selected card calls a run-results API; backend must fetch exactly the stored Python SHA and the matching real dataset, run in an isolated, resource-limited worker and persist *code/inputs/outputs* before returning a result.
4. Pass the *stored run's* JSON to \`<StrategyPythonChart result={run} />\`. No local pretend calculation and no generic EMA fallback.
5. Show paper's original sample period **separately** from any post-publication experiment period; show exact contract expiries for futures.
6. On failures, render explicit unavailability, never synthetic data.
7. For verification, compare same market/time bar, signals, both legs' fills, equity, costs and order timestamps with paper evidence; annotate \`PAPER_REPRODUCED\` only after reproducing.
8. For actual futures strategies show at least: contract-leg OHLCV graph, derived spread/indicator graph, individual leg trades/markers, normalized PnL/equity and drawdown. The current component only covers **one symbol's OHLCV+Python overlays+fills**. Additional panels are still needed.

## What was implemented in this branch
- Source-based reusable Python chart component in GitHub.
- Dynamic indicator names, immutable Python & dataset hashes, strict real-data data provenance, timestamp/bar alignment, fill markers, window handling.
- Not implemented: production DB migrations/API, strategy-list page, live chart render verified by browser, backtests reproducing the published papers.
- This branch intentionally does not alter the live screener deployment.
