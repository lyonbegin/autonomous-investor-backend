# v6 – blocked case recovery: create strategies first, validate evidence honestly

## Verified implementation
- Three previously blocked 0CVvd49h external-research cases now each have `strategy_spec.json`, portable stdlib `generated_strategy.py`, executable fixture, detailed 20-section report, 87-row taxonomy comparison, and individual synthetic trade CSV.
- The base `src/advanced_runtime.py` and spec-driven generator `src/strategy_factory_v6.py` are case-ID agnostic; each strategy kind is decided by `spec.kind`. Missing source-specific paper parameters are fully declared developer assumptions.
- Source 13 / MASU+ Pine remains independent from all external multi-leg cases. We preserve the original Pine source and source-map in `results/0CVvd49h`.

## Run
```
python build_v6.py
python build_reports_v6.py
python -m unittest discover -s tests -v
python results/BAEK-2020-HG-PL-RESEARCH/generated_strategy.py fixtures/synthetic_daily_bars.json
python results/PSARADELLIS-PL-GC-RULES-RESEARCH/generated_strategy.py fixtures/synthetic_daily_bars.json
python results/IWATSUBO-CROSS-VENUE-MICROSTRUCTURE/generated_strategy.py fixtures/synthetic_quote_snapshots.json
```

## Provenance and limits
- Public academic sources:
  - Baek et al 2020: https://doi.org/10.3390/su12176791
  - Psaradellis et al: https://doi.org/10.1016/j.ijforecast.2021.10.002
  - Iwatsubo & Watkins 2022: https://doi.org/10.3390/jrfm15120593
- Official JPX/OSE 500g platinum standard: https://www.jpx.co.jp/english/derivatives/products/precious-metals/platinum-standard-futures/01.html
- v6 created RESEARCH-only strategies. Samples are synthetic generated fixtures with fictional prices, assumptions on transaction fees, no broker quotes and NO verified real-backtest/PAPER/LIVE claims.
- 87 catalog entries included in all 3 detailed reports; the original separate 12-entry list remains unverified and is not fabricated.
- The generator covers these 3 reusable strategy *families*; AI model-driven general economic inference and live autonomous literature search are NOT demonstrated by v6.
- V6 is non-destructive: v5 source and GitHub production deployments remain untouched unless specifically changed in a research branch.

## Key changed principle
See `RESEARCH_POLICY_V4_CORRECTION_20261110.md`: insufficient source rules call for creating a clearly labeled **developer-research strategy**, not blocking RESEARCH code generation. Real order eligibility remains gated separately.

## Updated v6 auto design gateway
`src/auto_discovery_v6.py` adds a reusable AI-assisted design route from independently verified *economic mechanisms* to new research-assumed rules. Unlike v5, it does **not** discard a case just because the source did not provide numeric trade entry/exit thresholds. Test `test_auto_discovery_v6.py` mocks the external research + AI provider, includes changed Strategy ID tests and ungrounded-quote rejections. It is *not* proof of live AI model discovery. A real authorized model endpoint and full-text sources must be connected separately.

## Public GitHub boundary
When published under `research/v6`, the user-supplied complete original Pine is excluded from public source. The local v6 ZIP includes authorized reference source for user reproduction. `build_reports_v6.py` needs the original analysis archive present locally; GitHub CI instead verifies the checked-in saved 20-section results without leaking the Pine source.
