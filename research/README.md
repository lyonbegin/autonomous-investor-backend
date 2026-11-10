# TradingView economic-opportunity research bootstrap (2026-11-10)

This is an **isolated research branch**, derived from `feature/wf02-bridge-real-ddds-verified-site-20261104`. No changes to original Drive sources, verified UI, production Railway services or existing TradingView execution claims.

## Verified shared sources
- [Drive master folder](https://drive.google.com/drive/folders/12qg-4dnm8Nty5vfXYNDI5TGT65dhJR6h)
- Recursive discovery archive: [33,890 entries](https://drive.google.com/file/d/1paEFQweyJ2qByHyoGsGMV3l8GXfDqDXq/view), archive SHA-256 `4785953639ed21d19187d7d8d3bac7edc63b4352e1f189669526ef4c3961a925`. Contains 4,428 Strategy and 29,462 Indicator records.
- Pine archive: [3,455 files](https://drive.google.com/file/d/1_aTCwgV1Yze6xx3HlWK1QHCXkGyVAuLz/view), archive SHA-256 `1f1a2f1b7f1ba5c188ad4d129ce8153621cb873a537b76f45e2ff9eaf97d8d08`.
- Generated Python shard archive SHA-256 `17a2957e6416752f605d80d621780317ace97aa569837a15c9e0b1f3b3ea44f2`.
- Original 33,890 XLSX `TradingView_33890_Strategy_Indicator_전체목록_20261109.xlsx`: **NOT PRESENT** in shared folder.
- Full `전체자동연구개발_작업지시서_20261110`: **NOT PRESENT** in shared folder.
- Original 3,393 sequential-order ledger: **NOT FOUND** in listed files/ZIP indexes; do **not** invent a "next" original ID. Preserve its order when obtained.
- Prior reported generated-Python total 2,840; physically verified 875+1,941=2,816 `conversion/generated.py` files, 24 unexplained; **do not** overwrite old accounting without reconciliation.
- Pine version-recheck 607 included within Pine-available 3,455; not additive. Library-hold 62 excluded from sequential 3,393.

## Method validation: ledger #13, 0CVvd49h
Published [MASU+ v7.2](https://www.tradingview.com/script/0CVvd49h-MASU-v7-2-NW-ELM-BOS/), Pine v6, original code SHA-256 `06728ba8446771d2e45c63f2fca0d8cce378c96b445836f47c82e279285c1852`, 1,158 lines, verified against Pine archive manifest and original code bytes.

Pine has directional long/short order logic using EMA, BOS, mean-reversion and filters on the chart symbol. `request.security` MTF reads the chart symbol. This **does not** prove the source implements a two-leg platinum-gold futures strategy.

External cases are in `research/cases/0CVvd49h.json`. CME shows a 2-PL-long / 1-GC-short **illustrative trade** with gross $5,570 (2 × 50oz × ($1,056.40-$988.40) minus 100oz × ($1,244.20-$1,231.90)). It does NOT prescribe rolling z-scores. The standalone `research/intermarket.py` z-score entry/exit rules are DEVELOPMENT ASSUMPTIONS to test, not CME or MASU+ rules.

## Validation boundaries
- `python -m unittest discover -s research/tests -v` tests arithmetic and synthetic control-flow ONLY.
- No provider-attributed synchronized real PL/GC OHLCV dataset has been verified in this change. Therefore NO verified market backtest, profit figure, parity claim, live order placement, or production deployment.
- Real data input must be backed by an independently verified provenance and SHA-256. Backtest reports must track `strategy_id`, `original_pine_sha256`, `generated_python_sha256`, `market_data_sha256`, `run_id`; no results should be shown as verified until they exist.
- Existing verified screen and its lower PythonPlot chart are to be REUSED after validated result storage; do not replace with a generic screener chart. Current route has a DDDS-specific execution/hash gate; this branch does not bypass it.
- GitHub Actions artifact uploads are ephemeral. Publish durable result records only after separately configured DB/S3 or committed immutable result objects, with acknowledgement and hashes.
