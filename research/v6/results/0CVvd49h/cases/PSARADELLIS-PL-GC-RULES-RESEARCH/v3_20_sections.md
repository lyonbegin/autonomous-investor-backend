# PSARADELLIS-PL-GC-RULES-RESEARCH | 20항목 연구전략 개발 결과
**판정:** 전략 코드 생성·합성 기능실행 완료 / 실제 거래 가능성·성과 미검증
**원문:** https://research-portal.st-andrews.ac.uk/en/publications/technical-analysis-spread-trading-and-data-snooping-control/
**코드 SHA:** `fe276c534b472f9572e262218ec02cff508de3aa0ec3e9b0d653fcdc5d4c3b62`
**중요:** 개발자가 만든 규칙은 논문에 있는 규칙으로 표시하지 않았습니다.

## 01_original_identity
```json
{
  "TradingView_id": "0CVvd49h",
  "name": "MASU+ v7.2",
  "source_ref": "../../original.pine",
  "pine_sha256": "06728ba8446771d2e45c63f2fca0d8cce378c96b445836f47c82e279285c1852",
  "original_is_not_this_case": true
}
```

## 02_Pine_full_code
```json
{
  "source_lines": 1158,
  "source_code": "../../original.pine",
  "semantic_scope": "STATIC_CALL_SITES_ONLY",
  "order_call_sites": [
    {
      "line": 780,
      "type": "strategy.entry"
    },
    {
      "line": 786,
      "type": "strategy.exit"
    },
    {
      "line": 788,
      "type": "strategy.exit"
    },
    {
      "line": 794,
      "type": "strategy.entry"
    },
    {
      "line": 800,
      "type": "strategy.exit"
    },
    {
      "line": 802,
      "type": "strategy.exit"
    },
    {
      "line": 816,
      "type": "strategy.entry"
    },
    {
      "line": 820,
      "type": "strategy.exit"
    },
    {
      "line": 827,
      "type": "strategy.entry"
    },
    {
      "line": 831,
      "type": "strategy.exit"
    }
  ]
}
```

## 03_instruments
```json
{
  "leg_contracts": {
    "PL": {
      "venue": "NYMEX",
      "multiplier_oz": 50,
      "price_unit": "USD per oz"
    },
    "GC": {
      "venue": "COMEX",
      "multiplier_oz": 100,
      "price_unit": "USD per oz"
    }
  },
  "venue_contract_permissions": "BROKER_CHECK_REQUIRED",
  "unit_normalization": "LONG spread: BUY 2 PL contracts ×50 oz, SELL 1 GC contract ×100 oz. SHORT spread: SELL 2 PL, BUY 1 GC; both quote USD/troy oz. Require same research time base, separate contract months/roll."
}
```

## 04_original_entry_exit
```json
{
  "original_order_call_sites": [
    {
      "line": 780,
      "type": "strategy.entry"
    },
    {
      "line": 786,
      "type": "strategy.exit"
    },
    {
      "line": 788,
      "type": "strategy.exit"
    },
    {
      "line": 794,
      "type": "strategy.entry"
    },
    {
      "line": 800,
      "type": "strategy.exit"
    },
    {
      "line": 802,
      "type": "strategy.exit"
    },
    {
      "line": 816,
      "type": "strategy.entry"
    },
    {
      "line": 820,
      "type": "strategy.exit"
    },
    {
      "line": 827,
      "type": "strategy.entry"
    },
    {
      "line": 831,
      "type": "strategy.exit"
    }
  ],
  "external_trade_rules_from_paper_do_not_exist_in_original": true
}
```

## 05_original_performance
```json
{
  "original_backtest": "NOT_REPRODUCED",
  "paper_claim_vs_our_results": "SYNTHETIC_FIXTURE_ONLY",
  "live_paper": false
}
```

## 06_economic_mechanism
```json
{
  "who_and_why": "Platinum/gold spread may mean revert or trend episodically. Relative-value trader combines two platinum contracts and one gold contract to match about 100 troy oz per leg. Not a guaranteed hedge.",
  "hypothesis": "Absolute movement of platinum-gold spread has negative serial dependence after RSI extremes; reject on multiple-testing adjusted OOS, robustness and fees."
}
```

## 07_existing_87_mapping
```json
{
  "file": "taxonomy_87.csv",
  "mapping_rows": 87,
  "relevant_candidate_ids": [
    "S028",
    "S045"
  ],
  "mapping_confidence": "INDIRECT_RESEARCH_ANALOGY; NOT VERIFIED IMPLEMENTATION",
  "new_taxonomy_proposal": "METALS-PL-GC-RSI-SPREAD"
}
```

## 08_existing_additional_12
```json
{
  "status": "SOURCE_LIST_MISSING",
  "mapping_rows": 0,
  "why": "12 original names/IDs not yet verified; do not invent new canonical IDs"
}
```

## 09_hypothesis_and_falsification
```json
{
  "hypothesis": "Absolute movement of platinum-gold spread has negative serial dependence after RSI extremes; reject on multiple-testing adjusted OOS, robustness and fees.",
  "falsification": "No stable relation, out-of-sample expected net edge <= 0 after true trading costs, non-executable contract or stale quotes"
}
```

## 10_web_search_and_selection
```json
{
  "research_status": "WEB_RESEARCH_MANUAL_VERIFIED_NOT_AUTONOMOUS_MODEL_DISCOVERY",
  "doi": "10.1016/j.ijforecast.2021.10.002",
  "url": "https://research-portal.st-andrews.ac.uk/en/publications/technical-analysis-spread-trading-and-data-snooping-control/",
  "automatic_search_log": "NOT_EXECUTED"
}
```

## 11_independent_published_case
```json
{
  "authors": "Ioannis Psaradellis, Jason Laws, Athanasios A. Pantelous, Georgios Sermpinis",
  "publisher": "International Journal of Forecasting",
  "year": 2023,
  "doi": "10.1016/j.ijforecast.2021.10.002",
  "url": "https://research-portal.st-andrews.ac.uk/en/publications/technical-analysis-spread-trading-and-data-snooping-control/",
  "paper_locations": [
    {
      "rule": "Paper evaluates thousands of technical trading rules on daily spread pairs and controls data snooping",
      "location": "Methods / Introduction; manuscript pp. 1-7",
      "classification": "PAPER_METHOD"
    },
    {
      "rule": "Platinum-gold spread listed, with RSI2 as best rule label in study Table 2",
      "location": "Accepted manuscript Table 2, appendix p.39",
      "classification": "PAPER_CLASSIFICATION"
    },
    {
      "rule": "2 platinum contracts against 1 gold contract for equal underlying ounces",
      "location": "Accepted manuscript footnote 6, p.7",
      "classification": "PAPER_CONTRACT_NORMALIZATION"
    }
  ]
}
```

## 12_confirmed_rules_vs_developer_assumptions
```json
{
  "SOURCE_CONFIRMED": [
    {
      "rule": "Paper evaluates thousands of technical trading rules on daily spread pairs and controls data snooping",
      "location": "Methods / Introduction; manuscript pp. 1-7",
      "classification": "PAPER_METHOD"
    },
    {
      "rule": "Platinum-gold spread listed, with RSI2 as best rule label in study Table 2",
      "location": "Accepted manuscript Table 2, appendix p.39",
      "classification": "PAPER_CLASSIFICATION"
    },
    {
      "rule": "2 platinum contracts against 1 gold contract for equal underlying ounces",
      "location": "Accepted manuscript footnote 6, p.7",
      "classification": "PAPER_CONTRACT_NORMALIZATION"
    }
  ],
  "DEVELOPER_CREATED": [
    {
      "field": "rsi_bars",
      "value": 14,
      "why": "RSI2 is paper rule ID, not confirmed 2-period RSI; research chooses 14"
    },
    {
      "field": "oversold/overbought",
      "value": [
        35,
        65
      ],
      "why": "Independently designed thresholds; not paper-validated optimum"
    },
    {
      "field": "exit_midpoint_band",
      "value": 7,
      "why": "Developer-chosen mean reversion exit"
    },
    {
      "field": "execution",
      "value": "next daily open; max 7 bars, assumed fees/slippage",
      "why": "Simulator design, no paper strategy replication"
    }
  ]
}
```

## 13_real_leg_structure
```json
{
  "legs": "LONG spread: BUY 2 PL contracts ×50 oz, SELL 1 GC contract ×100 oz. SHORT spread: SELL 2 PL, BUY 1 GC; both quote USD/troy oz. Require same research time base, separate contract months/roll.",
  "instrument_detail": {
    "PL": {
      "venue": "NYMEX",
      "multiplier_oz": 50,
      "price_unit": "USD per oz"
    },
    "GC": {
      "venue": "COMEX",
      "multiplier_oz": 100,
      "price_unit": "USD per oz"
    }
  },
  "contract_access": "NOT_BROKER_VERIFIED"
}
```

## 14_entry_exit_algorithm
```json
{
  "logic": "spread_t = PL_close_t - GC_close_t in USD/oz; compute simple RSI on last 14 close-to-close spread differences. At completed t daily close RSI<=35 LONG spread; RSI>=65 SHORT spread; fill both next bar OPEN; exit when |RSI-50|<=7 or holding>=7 bars. No opening at preceding close. RSI2 in paper Table 2 is a RULE LABEL, not evidence that the chosen RSI period=2.",
  "parameters": {
    "timeframe": "1d",
    "rsi_bars": 14,
    "oversold": 35,
    "overbought": 65,
    "exit_midpoint_band": 7,
    "max_hold_bars": 7,
    "qty_y": 2,
    "qty_x": 1,
    "multiplier_y": 50,
    "multiplier_x": 100,
    "roundtrip_fee_per_contract_usd": 8,
    "slippage_per_side_per_contract_usd": 2
  },
  "signal_vs_fill": "NEXT_OPEN"
}
```

## 15_risk_cost_and_pnl
```json
{
  "risk": "Spread may remain disconnected, correlation regime breaks, both legs non-synchronous. Paper controls false-discovery and OOS; these need to be separately run. Not claiming that 14/35/65 are academic best-fit parameters.",
  "formula": "Gross = direction*(2×50×ΔPL-1×100×ΔGC). Example LONG spread PL +$8/oz and GC +$3/oz => $800-$300=$500 gross. With assumed $24 fee + $12 slippage modeled net $464, excludes roll/carry/margin.",
  "synthetic_trade_count": 13,
  "functional_results_file": "synthetic_functional_result.json",
  "market_return_claim": "NONE"
}
```

## 16_real_market_data
```json
{
  "required": "Need continuous and individual front-month PL/GC daily futures data, equal bar boundaries, contract rolls, actual broker fees and implied bid/ask. Current 120 bars are deterministic synthetic fixture; no market performance.",
  "fixture_sha256": "0b715469f60245185499f9f97253daf139bbacbdb4108a7c9c58e709ed0792de",
  "data_type": "DETERMINISTIC_SYNTHETIC_TEST",
  "market_data_sha256": null,
  "status": "MISSING"
}
```

## 17_full_generated_Python
```json
{
  "file": "generated_strategy.py",
  "code_sha256": "fe276c534b472f9572e262218ec02cff508de3aa0ec3e9b0d653fcdc5d4c3b62",
  "complete_embedded_stdlib_runtime": true,
  "requirements": "Python 3.10+ stdlib",
  "cli": "python generated_strategy.py ../../../fixtures/synthetic_daily_bars.json"
}
```

## 18_functional_and_source_parity_tests
```json
{
  "status": "UNIT_AND_GENERATED_TEST_PASSED",
  "test_suite": "../../../../tests/test_v6_strategies.py",
  "paper_exact_replication": "NOT_CLAIMED",
  "v5_source_parity": "NOT_TESTED",
  "actual_broker_execution": "NONE"
}
```

## 19_trades_equity_and_charts
```json
{
  "real_backtest": "REAL_BACKTEST_NOT_RUN",
  "synthetic_trades": "synthetic_trades.csv",
  "synthetic_raw_result": "synthetic_functional_result.json",
  "real_trades": "NOT_AVAILABLE",
  "equity_real": "NOT_AVAILABLE",
  "verified_chart": "NOT_AVAILABLE"
}
```

## 20_adoption_and_lineage
```json
{
  "decision": "RESEARCH_STRATEGY_IMPLEMENTED_PENDING_REAL_DATA",
  "source_id": "0CVvd49h",
  "case_id": "PSARADELLIS-PL-GC-RULES-RESEARCH",
  "paper_doi": "10.1016/j.ijforecast.2021.10.002",
  "code_sha256": "fe276c534b472f9572e262218ec02cff508de3aa0ec3e9b0d653fcdc5d4c3b62",
  "in_existing_87": "INDIRECT_RESEARCH_CANDIDATE",
  "new_taxonomy_proposal": "METALS-PL-GC-RSI-SPREAD",
  "additional_12": "MISSING_CANONICAL_SOURCE",
  "db": "NOT_PERSISTED",
  "web": "NOT_DEPLOYED",
  "PAPER": false,
  "LIVE": false
}
```
