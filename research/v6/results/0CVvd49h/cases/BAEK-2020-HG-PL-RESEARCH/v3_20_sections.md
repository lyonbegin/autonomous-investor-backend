# BAEK-2020-HG-PL-RESEARCH | 20항목 연구전략 개발 결과
**판정:** 전략 코드 생성·합성 기능실행 완료 / 실제 거래 가능성·성과 미검증
**원문:** https://www.mdpi.com/2071-1050/12/17/6791
**코드 SHA:** `4d7b4a050c09d19846822da9d582b9f4dcf5233d4872ba8f69097d2c0af0a11a`
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
      "price_unit": "USD per troy oz"
    },
    "HG": {
      "venue": "COMEX",
      "multiplier_lb": 25000,
      "price_unit": "USD per lb"
    }
  },
  "venue_contract_permissions": "BROKER_CHECK_REQUIRED",
  "unit_normalization": "Signal +: SELL 2 PL (NYMEX, 50 troy oz each) and BUY 1 HG (COMEX, 25,000 lb each). Signal -: reverse sides. Hedge beta fitted on 40 training bars; integer-lot hedge mismatch must be <=35% in current prototype."
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
  "who_and_why": "A pair of metal futures may have a time-varying common driver; temporary pricing deviations may revert. Short deviation and simultaneously hedge related futures. This is a risky relative-value position, not risk-free arbitrage.",
  "hypothesis": "Standardized spread mean reverts after metal supply/demand dislocations; reject if historical cointegration/ADF fails, beta unstable, integer hedge mismatch exceeds limit or cost-adjusted OOS edge nonpositive."
}
```

## 07_existing_87_mapping
```json
{
  "file": "taxonomy_87.csv",
  "mapping_rows": 87,
  "relevant_candidate_ids": [
    "S045",
    "S028"
  ],
  "mapping_confidence": "INDIRECT_RESEARCH_ANALOGY; NOT VERIFIED IMPLEMENTATION",
  "new_taxonomy_proposal": "METALS-HG-PL-COINT-REVERSION"
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
  "hypothesis": "Standardized spread mean reverts after metal supply/demand dislocations; reject if historical cointegration/ADF fails, beta unstable, integer hedge mismatch exceeds limit or cost-adjusted OOS edge nonpositive.",
  "falsification": "No stable relation, out-of-sample expected net edge <= 0 after true trading costs, non-executable contract or stale quotes"
}
```

## 10_web_search_and_selection
```json
{
  "research_status": "WEB_RESEARCH_MANUAL_VERIFIED_NOT_AUTONOMOUS_MODEL_DISCOVERY",
  "doi": "10.3390/su12176791",
  "url": "https://www.mdpi.com/2071-1050/12/17/6791",
  "automatic_search_log": "NOT_EXECUTED"
}
```

## 11_independent_published_case
```json
{
  "authors": "Seungho Baek, Mina Glambosky, Seok Hee Oh, Jeong Lee",
  "publisher": "Sustainability",
  "year": 2020,
  "doi": "10.3390/su12176791",
  "url": "https://www.mdpi.com/2071-1050/12/17/6791",
  "paper_locations": [
    {
      "rule": "Study selects pairs and tests cointegration using Engle-Granger/ECM; SVR hedge ratio",
      "location": "Section 2.4, Systemic Trading Architecture and Trading Strategy and Hedge Ratio from SVM",
      "classification": "PAPER_METHOD"
    },
    {
      "rule": "Signals at deviation beyond a 15-day moving average with standard-deviation band; pairs opened simultaneously, exited on reverting to mean",
      "location": "Section 2.4, Strategy and Hedge Ratio from SVM",
      "classification": "PAPER_METHOD"
    }
  ]
}
```

## 12_confirmed_rules_vs_developer_assumptions
```json
{
  "SOURCE_CONFIRMED": [
    {
      "rule": "Study selects pairs and tests cointegration using Engle-Granger/ECM; SVR hedge ratio",
      "location": "Section 2.4, Systemic Trading Architecture and Trading Strategy and Hedge Ratio from SVM",
      "classification": "PAPER_METHOD"
    },
    {
      "rule": "Signals at deviation beyond a 15-day moving average with standard-deviation band; pairs opened simultaneously, exited on reverting to mean",
      "location": "Section 2.4, Strategy and Hedge Ratio from SVM",
      "classification": "PAPER_METHOD"
    }
  ],
  "DEVELOPER_CREATED": [
    {
      "field": "underlyings",
      "value": "HG + PL",
      "why": "Illustrative metal futures pairing. Specific HG-PL pair is not claimed as a tested study pair"
    },
    {
      "field": "hedge_method",
      "value": "training-only OLS",
      "why": "Stdlib proxy for SVM regression / ECM; not equivalently cointegration-tested"
    },
    {
      "field": "entry_z",
      "value": 1.5,
      "why": "Developer threshold; paper text supports band but not this numeric multiple"
    },
    {
      "field": "exit_z",
      "value": 0.35,
      "why": "Quantified mean-reversion exit threshold supplied by developer"
    },
    {
      "field": "stop_z",
      "value": 5.0,
      "why": "Capital/risk research assumption"
    },
    {
      "field": "execution",
      "value": "next daily bar open; fixed contract sizes; explicit assumed fees",
      "why": "Not asserted as source instructions"
    }
  ]
}
```

## 13_real_leg_structure
```json
{
  "legs": "Signal +: SELL 2 PL (NYMEX, 50 troy oz each) and BUY 1 HG (COMEX, 25,000 lb each). Signal -: reverse sides. Hedge beta fitted on 40 training bars; integer-lot hedge mismatch must be <=35% in current prototype.",
  "instrument_detail": {
    "PL": {
      "venue": "NYMEX",
      "multiplier_oz": 50,
      "price_unit": "USD per troy oz"
    },
    "HG": {
      "venue": "COMEX",
      "multiplier_lb": 25000,
      "price_unit": "USD per lb"
    }
  },
  "contract_access": "NOT_BROKER_VERIFIED"
}
```

## 14_entry_exit_algorithm
```json
{
  "logic": "Fit OLS PL_close[t] ≈ alpha + beta HG_close[t] on first 40 bars, freeze alpha/beta. spread_t=PL_t-alpha-beta HG_t; z_t=(spread_t-mean(spread_[t-15:t]))/sample_std(spread_[t-15:t]). At completed t bar, z>=1.5 enters SHORT spread next open, z<=-1.5 LONG; exit when |z|<=0.35, stop |z|>=5 or 7 bars; never same close fill. ADF/SVR/ECM are NOT implemented.",
  "parameters": {
    "timeframe": "1d",
    "training_bars": 40,
    "band_bars": 15,
    "entry_z": 1.5,
    "exit_z": 0.35,
    "stop_z": 5.0,
    "max_hold_bars": 7,
    "qty_y": 2,
    "qty_x": 1,
    "multiplier_y": 50,
    "multiplier_x": 25000,
    "max_hedge_mismatch_fraction": 0.35,
    "roundtrip_fee_per_contract_usd": 8,
    "slippage_per_side_per_contract_usd": 2
  },
  "signal_vs_fill": "NEXT_OPEN"
}
```

## 15_risk_cost_and_pnl
```json
{
  "risk": "PL gamma is not matched with HG; commodity relationship breaks; inferred OLS beta is not proven cointegration. Integer hedge mismatch and rollover risk. Hard signal stop in z does not cap gap loss; no actual broker margin or liquidation logic.",
  "formula": "USD gross = side_PL*2*50*(PL_exit-PL_entry) - side_PL*1*25000*(HG_exit-HG_entry). Example LONG spread +$10/oz PL and +$0.01/lb HG => +$1,000-$250=+$750 gross. Subtract assumed $24 round-trip commission + $12 slippage = +$714 modeled, BEFORE margin/funding/roll.",
  "synthetic_trade_count": 7,
  "functional_results_file": "synthetic_functional_result.json",
  "market_return_claim": "NONE"
}
```

## 16_real_market_data
```json
{
  "required": "Need official PL/HG futures same session daily bars, historical contract month & roll, contract multipliers, OI/volume; independent synchronized dates and next-open prices, market fees/margins. Fixture is deterministic SYNTHETIC 120 rows.",
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
  "code_sha256": "4d7b4a050c09d19846822da9d582b9f4dcf5233d4872ba8f69097d2c0af0a11a",
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
  "case_id": "BAEK-2020-HG-PL-RESEARCH",
  "paper_doi": "10.3390/su12176791",
  "code_sha256": "4d7b4a050c09d19846822da9d582b9f4dcf5233d4872ba8f69097d2c0af0a11a",
  "in_existing_87": "INDIRECT_RESEARCH_CANDIDATE",
  "new_taxonomy_proposal": "METALS-HG-PL-COINT-REVERSION",
  "additional_12": "MISSING_CANONICAL_SOURCE",
  "db": "NOT_PERSISTED",
  "web": "NOT_DEPLOYED",
  "PAPER": false,
  "LIVE": false
}
```
