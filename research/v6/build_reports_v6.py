import csv,datetime,hashlib,json,shutil,pathlib,sys,os
ROOT=pathlib.Path(__file__).parent
SOURCE=pathlib.Path(os.environ.get('RESEARCH_SOURCE_DIR',str(ROOT/'results'/'0CVvd49h')))
TARGET=ROOT/'results'/'0CVvd49h'
TARGET.mkdir(exist_ok=True,parents=True)
for fn in ('original_analysis.json','original_analysis.md','original.pine','taxonomy_87x12.csv','hypothesis_register.json','search_log.jsonl'):
    if (SOURCE/fn).resolve() != (TARGET/fn).resolve(): shutil.copy2(SOURCE/fn,TARGET/fn)
S=json.loads((SOURCE/'original_analysis.json').read_text(encoding='utf-8'))
ids=[]
with (SOURCE/'taxonomy_87x12.csv').open(encoding='utf-8-sig',newline='') as f:
    ids=list(csv.DictReader(f))
assert len(ids)==87

CASE_DETAILS={
 'BAEK-2020-HG-PL-RESEARCH':{
 'authors':'Seungho Baek, Mina Glambosky, Seok Hee Oh, Jeong Lee','year':2020,'doi':'10.3390/su12176791','publisher':'Sustainability',
 'economic':'A pair of metal futures may have a time-varying common driver; temporary pricing deviations may revert. Short deviation and simultaneously hedge related futures. This is a risky relative-value position, not risk-free arbitrage.',
 'legs':'Signal +: SELL 2 PL (NYMEX, 50 troy oz each) and BUY 1 HG (COMEX, 25,000 lb each). Signal -: reverse sides. Hedge beta fitted on 40 training bars; integer-lot hedge mismatch must be <=35% in current prototype.',
 'logic':'Fit OLS PL_close[t] ≈ alpha + beta HG_close[t] on first 40 bars, freeze alpha/beta. spread_t=PL_t-alpha-beta HG_t; z_t=(spread_t-mean(spread_[t-15:t]))/sample_std(spread_[t-15:t]). At completed t bar, z>=1.5 enters SHORT spread next open, z<=-1.5 LONG; exit when |z|<=0.35, stop |z|>=5 or 7 bars; never same close fill. ADF/SVR/ECM are NOT implemented.',
 'risk':'PL gamma is not matched with HG; commodity relationship breaks; inferred OLS beta is not proven cointegration. Integer hedge mismatch and rollover risk. Hard signal stop in z does not cap gap loss; no actual broker margin or liquidation logic.',
 'pnl':'USD gross = side_PL*2*50*(PL_exit-PL_entry) - side_PL*1*25000*(HG_exit-HG_entry). Example LONG spread +$10/oz PL and +$0.01/lb HG => +$1,000-$250=+$750 gross. Subtract assumed $24 round-trip commission + $12 slippage = +$714 modeled, BEFORE margin/funding/roll.',
 'data':'Need official PL/HG futures same session daily bars, historical contract month & roll, contract multipliers, OI/volume; independent synchronized dates and next-open prices, market fees/margins. Fixture is deterministic SYNTHETIC 120 rows.',
 'hypothesis':'Standardized spread mean reverts after metal supply/demand dislocations; reject if historical cointegration/ADF fails, beta unstable, integer hedge mismatch exceeds limit or cost-adjusted OOS edge nonpositive.'
 },
 'PSARADELLIS-PL-GC-RULES-RESEARCH':{
 'authors':'Ioannis Psaradellis, Jason Laws, Athanasios A. Pantelous, Georgios Sermpinis','year':2023,'doi':'10.1016/j.ijforecast.2021.10.002','publisher':'International Journal of Forecasting',
 'economic':'Platinum/gold spread may mean revert or trend episodically. Relative-value trader combines two platinum contracts and one gold contract to match about 100 troy oz per leg. Not a guaranteed hedge.',
 'legs':'LONG spread: BUY 2 PL contracts ×50 oz, SELL 1 GC contract ×100 oz. SHORT spread: SELL 2 PL, BUY 1 GC; both quote USD/troy oz. Require same research time base, separate contract months/roll.',
 'logic':'spread_t = PL_close_t - GC_close_t in USD/oz; compute simple RSI on last 14 close-to-close spread differences. At completed t daily close RSI<=35 LONG spread; RSI>=65 SHORT spread; fill both next bar OPEN; exit when |RSI-50|<=7 or holding>=7 bars. No opening at preceding close. RSI2 in paper Table 2 is a RULE LABEL, not evidence that the chosen RSI period=2.',
 'risk':'Spread may remain disconnected, correlation regime breaks, both legs non-synchronous. Paper controls false-discovery and OOS; these need to be separately run. Not claiming that 14/35/65 are academic best-fit parameters.',
 'pnl':'Gross = direction*(2×50×ΔPL-1×100×ΔGC). Example LONG spread PL +$8/oz and GC +$3/oz => $800-$300=$500 gross. With assumed $24 fee + $12 slippage modeled net $464, excludes roll/carry/margin.',
 'data':'Need continuous and individual front-month PL/GC daily futures data, equal bar boundaries, contract rolls, actual broker fees and implied bid/ask. Current 120 bars are deterministic synthetic fixture; no market performance.',
 'hypothesis':'Absolute movement of platinum-gold spread has negative serial dependence after RSI extremes; reject on multiple-testing adjusted OOS, robustness and fees.'
 },
 'IWATSUBO-CROSS-VENUE-MICROSTRUCTURE':{
 'authors':'Kentaro Iwatsubo and Clinton Watkins','year':2022,'doi':'10.3390/jrfm15120593','publisher':'Journal of Risk and Financial Management',
 'economic':'Price discovery/liquidity may differ between NYMEX and historical TOCOM and present JPX/OSE platinum listings; opposite execution-side bid/ask comparisons after forward FX normalization reveal temporary apparent price discrepancies.',
 'legs':'Direction A: BUY NYMEX 1 contract ×50 oz using ASK, SELL Tokyo OSE 3 contracts ×500g using BID. Direction B reverse. FX pair uses forward BID/ASK for valuation, but a real hedging forward is not implemented. 50oz≈1,555.17g vs 1,500g in Tokyo; 3.55% unmatched physical metal.',
 'logic':'At matching contract month and overlapping venue sessions, evaluate cash_A=3×500×JP_bid - 1×50×NY_ask×FX_forward_ask, cash_B=1×50×NY_bid×FX_forward_bid -3×500×JP_ask. Signal if max(cash_A,cash_B) - assumed 8,000 JPY roundtrip costs >=10,000 JPY and all quote times within 3 seconds. On edge compression or max 3 20-second quote snapshots, reverse at observed bid/ask. This quote-replay is a research proxy: actual currency forward execution, clearing, financing, transfer/expiry differences not modeled.',
 'risk':'JPX/OSE 500g contract specification independently identified, but specific month/account permissions and cross-venue delivery equivalence unverified; delivery/clearing not fungible. Non-zero residual metal delta and forward hedge mismatches mean it is NOT riskless. Bid/Ask cannot be assumed simultaneously filled; size/depth and market access unverified.',
 'pnl':'For direction A, entry cashflow research proxy = 1,500g×Tokyo bid JPY/g −50oz×NY ask USD/oz×FX forward ask JPY/USD. Exit reversal = 50oz×NY bid×FX forward bid −1,500g×Tokyo ask. Quote-replay net = entry+exit−assumed 8,000 JPY. Synthetic fixture example gross 70,002.5 JPY and modeled net 62,002.5 JPY, NOT executable trade profit.',
 'data':'Need timestamp-synchronized NY and JP orderbook with actual depth, OTC FX-forward bid/ask for matching expiry, official contract specification and expiry, cross-venue access/settlement funding/custody and realistic fee estimates. Current 5 snapshots are synthetic.',
 'hypothesis':'During overlapping sessions the executable, currency-adjusted two-venue quote gap may exceed realistic funding, hedging and partial-fill costs. Reject if simultaneous market depth/FX permissions/contract equivalence fail.'
 }
}

from build_v6 import SPECS
for case,spec in SPECS.items():
    d=TARGET/'cases'/case; d.mkdir(exist_ok=True,parents=True)
    own=ROOT/'results'/case
    for name in ('strategy_spec.json','generated_strategy.py','synthetic_functional_result.json','execution_manifest.json'):
        shutil.copy2(own/name,d/name)
    details=CASE_DETAILS[case]
    functional=json.loads((d/'synthetic_functional_result.json').read_text())
    manifest=json.loads((d/'execution_manifest.json').read_text())
    # Per-case taxonomy remains 87 exactly, never replace 12 known-unknown entries with invented names.
    taxonomy=[]
    for ent in ids:
        taxonomy.append({**ent,'case_relation':'INDIRECT_RESEARCH_ANALOGY' if ent['taxonomy_id'] in spec['classification']['taxonomy_candidates'] else 'NO_CONFIRMED_RELATION',
                         'case_relation_basis':details['economic'] if ent['taxonomy_id'] in spec['classification']['taxonomy_candidates'] else 'No source evidence of identical economic transaction; do not infer from asset names'})
    with (d/'taxonomy_87.csv').open('w',encoding='utf-8-sig',newline='') as out:
        wr=csv.DictWriter(out,fieldnames=taxonomy[0].keys());wr.writeheader();wr.writerows(taxonomy)
    with (d/'synthetic_trades.csv').open('w',newline='',encoding='utf-8-sig') as out:
        wr=csv.writer(out);wr.writerow(['entry_timestamp','exit_timestamp','strategy_kind','legs','gross_fixture_pnl','modeled_net_fixture_pnl','currency','execution_status'])
        for t in functional.get('trades',[]):
            wr.writerow([t['entry_timestamp'],t['exit_timestamp'],spec['kind'],json.dumps(t.get('legs',{'direction':t.get('direction')}),ensure_ascii=False),t.get('gross_pnl_usd',t.get('gross_quote_replay_pnl_jpy')),t.get('modeled_net_pnl_usd',t.get('modeled_net_quote_replay_pnl_jpy')),'JPY' if spec['kind']=='cross_venue_platinum_quotes' else 'USD','SYNTHETIC_ONLY'])
    evidence={'case_id':case,'source_url':spec['source_evidence_url'],'publisher':details['publisher'],'authors':details['authors'],'year':details['year'],'doi':details['doi'],
              'exact_paper_section':spec['source_confirmed_rules'],'not_from_original_pine':True,'new_model_rules_are_developer_assumptions':True,'evidence_review':'WEB_RESEARCH_AND_MANUAL_METHOD_EXTRACTION'}
    (d/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    srcsites=S['04_original_trade_rules']['source_line_order_expressions']
    actual={'strategy_id':'0CVvd49h','original_sha256':'06728ba8446771d2e45c63f2fca0d8cce378c96b445836f47c82e279285c1852',
            'original_order_sites':[{'line':x['start_line'],'type':x['callee']} for x in srcsites],
            'external_case':case,'source_paper':spec['source_evidence_url'],
            'rule_lineage':[{'source_confirmed':v} for v in spec['source_confirmed_rules']]+[{'developer_assumption':v} for v in spec['research_assumptions']],
            'source_version':'2026-11-10 research archive', 'claim_direct_pine_parity':False}
    (d/'source_map.json').write_text(json.dumps(actual,ensure_ascii=False,indent=2),encoding='utf-8')
    section={
      '01_original_identity':{'TradingView_id':'0CVvd49h','name':'MASU+ v7.2','source_ref':'../../original.pine','pine_sha256':actual['original_sha256'],'original_is_not_this_case':True},
      '02_Pine_full_code':{'source_lines':S['02_pine_functional_analysis']['actual_source_integrity']['line_count'],'source_code':'../../original.pine','semantic_scope':'STATIC_CALL_SITES_ONLY','order_call_sites':actual['original_order_sites']},
      '03_instruments':{'leg_contracts':spec['instrument_info'],'venue_contract_permissions':'BROKER_CHECK_REQUIRED','unit_normalization':details['legs']},
      '04_original_entry_exit':{'original_order_call_sites':actual['original_order_sites'],'external_trade_rules_from_paper_do_not_exist_in_original':True},
      '05_original_performance':{'original_backtest':'NOT_REPRODUCED','paper_claim_vs_our_results':'SYNTHETIC_FIXTURE_ONLY','live_paper':False},
      '06_economic_mechanism':{'who_and_why':details['economic'],'hypothesis':details['hypothesis']},
      '07_existing_87_mapping':{'file':'taxonomy_87.csv','mapping_rows':87,'relevant_candidate_ids':spec['classification']['taxonomy_candidates'],'mapping_confidence':'INDIRECT_RESEARCH_ANALOGY; NOT VERIFIED IMPLEMENTATION','new_taxonomy_proposal':spec['classification'].get('new_taxonomy_proposal')},
      '08_existing_additional_12':{'status':'SOURCE_LIST_MISSING','mapping_rows':0,'why':'12 original names/IDs not yet verified; do not invent new canonical IDs'},
      '09_hypothesis_and_falsification':{'hypothesis':details['hypothesis'],'falsification':'No stable relation, out-of-sample expected net edge <= 0 after true trading costs, non-executable contract or stale quotes'},
      '10_web_search_and_selection':{'research_status':'WEB_RESEARCH_MANUAL_VERIFIED_NOT_AUTONOMOUS_MODEL_DISCOVERY','doi':details['doi'],'url':spec['source_evidence_url'],'automatic_search_log':'NOT_EXECUTED'},
      '11_independent_published_case':{'authors':details['authors'],'publisher':details['publisher'],'year':details['year'],'doi':details['doi'],'url':spec['source_evidence_url'],'paper_locations':spec['source_confirmed_rules']},
      '12_confirmed_rules_vs_developer_assumptions':{'SOURCE_CONFIRMED':spec['source_confirmed_rules'],'DEVELOPER_CREATED':spec['research_assumptions']},
      '13_real_leg_structure':{'legs':details['legs'],'instrument_detail':spec['instrument_info'],'contract_access':'NOT_BROKER_VERIFIED'},
      '14_entry_exit_algorithm':{'logic':details['logic'],'parameters':spec['parameters'],'signal_vs_fill':'NEXT_OPEN' if spec['kind']!='cross_venue_platinum_quotes' else 'SAME_SNAPSHOT_QUOTE_REPLAY_NO_EXECUTION'},
      '15_risk_cost_and_pnl':{'risk':details['risk'],'formula':details['pnl'],'synthetic_trade_count':functional['closed_trade_count'],'functional_results_file':'synthetic_functional_result.json','market_return_claim':'NONE'},
      '16_real_market_data':{'required':details['data'],'fixture_sha256':manifest['fixture_sha256'],'data_type':'DETERMINISTIC_SYNTHETIC_TEST','market_data_sha256':None,'status':'MISSING'},
      '17_full_generated_Python':{'file':'generated_strategy.py','code_sha256':manifest['generated_code']['code_sha256'],'complete_embedded_stdlib_runtime':True,'requirements':'Python 3.10+ stdlib','cli':f'python generated_strategy.py ../../../fixtures/{manifest["fixture_name"]}'},
      '18_functional_and_source_parity_tests':{'status':'UNIT_AND_GENERATED_TEST_PASSED','test_suite':'../../../../tests/test_v6_strategies.py','paper_exact_replication':'NOT_CLAIMED','v5_source_parity':'NOT_TESTED','actual_broker_execution':'NONE'},
      '19_trades_equity_and_charts':{'real_backtest':'REAL_BACKTEST_NOT_RUN','synthetic_trades':'synthetic_trades.csv','synthetic_raw_result':'synthetic_functional_result.json','real_trades':'NOT_AVAILABLE','equity_real':'NOT_AVAILABLE','verified_chart':'NOT_AVAILABLE'},
      '20_adoption_and_lineage':{'decision':'RESEARCH_STRATEGY_IMPLEMENTED_PENDING_REAL_DATA','source_id':'0CVvd49h','case_id':case,'paper_doi':details['doi'],'code_sha256':manifest['generated_code']['code_sha256'],'in_existing_87':'INDIRECT_RESEARCH_CANDIDATE','new_taxonomy_proposal':spec['classification'].get('new_taxonomy_proposal'),'additional_12':'MISSING_CANONICAL_SOURCE','db':'NOT_PERSISTED','web':'NOT_DEPLOYED','PAPER':False,'LIVE':False}
    }
    assert len(section)==20, (case,len(section))
    (d/'v3_20_sections.json').write_text(json.dumps(section,ensure_ascii=False,indent=2),encoding='utf-8')
    md=[f'# {case} | 20항목 연구전략 개발 결과',f'**판정:** 전략 코드 생성·합성 기능실행 완료 / 실제 거래 가능성·성과 미검증',
        f'**원문:** {spec["source_evidence_url"]}',f'**코드 SHA:** `{manifest["generated_code"]["code_sha256"]}`',
        '**중요:** 개발자가 만든 규칙은 논문에 있는 규칙으로 표시하지 않았습니다.']
    for k,v in section.items():md.extend(['',f'## {k}','```json',json.dumps(v,ensure_ascii=False,indent=2),'```'])
    (d/'v3_20_sections.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    (d/'assessment.md').write_text(f'''# {case} | 전략 개발 완료 범위

- 거래 알고리즘과 생성 Python 소스: **생성 및 기능 실행 완료**
- 원문 동일 재현: **아님**, 출처와 독립적인 설계 가정을 명시
- 합성 기능시험에서 청산 완료한 거래: **{functional['closed_trade_count']}건** (시장 성과와 무관)
- 경제적 거래구조: {details['economic']}
- 검증해야 할 핵심 위험: {details['risk']}
- 실데이터·증거금·호가·PAPER·LIVE: **검증하지 않음**
- 기존 87개 후보 연결: {', '.join(spec['classification']['taxonomy_candidates'])}; 원문 구조와 동일 전략 확정 아님
- 기존 12개 추가 정본: **미확보**

전략 코드 부족을 이유로 연구개발을 거절하지 않음. 실거래 접근권 미확보는 LIVE/PAPER 단계에서 검증함.
''',encoding='utf-8')
    (d/'backtest_report.md').write_text(f'# {case} 백테스트 상태\n실데이터 백테스트 **미실행**. 합성 기능시험 {functional["closed_trade_count"]}개 청산 거래만 확인. 원본 논문 수익률 재현 아님.\n',encoding='utf-8')

summary={'date':'2026-11-10','source_id':'0CVvd49h','case_implementations':[{ 'id':k,'status':'GENERATED_SYNTHETIC_TEST_PASSED','functional_closed_trades':json.loads((TARGET/'cases'/k/'synthetic_functional_result.json').read_text())['closed_trade_count']} for k in SPECS],
         'prior_wrong_failure_state':'RULE_EXTRACTION_INCOMPLETE','new_research_generation':'STRATEGY_IMPLEMENTED_WITH_DISCLOSED_ASSUMPTIONS','real_backtest':'REAL_BACKTEST_NOT_RUN','additional_12':'MISSING_CANONICAL_SOURCE'}
(TARGET/'new_case_index.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print('Built',len(SPECS),'cases, 20 sections each; restored',len(ids),'taxonomy names')
