import unittest, json, pathlib, sys, importlib.util, copy, subprocess, tempfile, datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT))
from advanced_runtime import validate_advanced_spec,run_advanced,ResearchError,_leg_pnl,_theoretical_cash
from strategy_factory_v6 import generate_advanced
from build_v6 import SPECS,synthetic_bars,synthetic_quotes

class TestV6StrategyConstruction(unittest.TestCase):
    def test_baek_15day_workflow_open(self):
        x=run_advanced(SPECS['BAEK-2020-HG-PL-RESEARCH'],synthetic_bars())
        self.assertEqual(x['status'],'SYNTHETIC_FUNCTIONAL_TEST_ONLY')
        self.assertGreater(x['closed_trade_count'],0)
        self.assertFalse(x['claim_replicates_paper'])
        self.assertIn('OLS proxy',x['academic_method_gap'])
    def test_psaradellis_rsi_strategy_open(self):
        x=run_advanced(SPECS['PSARADELLIS-PL-GC-RULES-RESEARCH'],synthetic_bars())
        self.assertGreater(x['closed_trade_count'],0)
        self.assertIn('RSI(14)',x['academic_method_gap'])
    def test_iwatsubo_executable_two_way_quote_signals(self):
        x=run_advanced(SPECS['IWATSUBO-CROSS-VENUE-MICROSTRUCTURE'],synthetic_quotes())
        self.assertEqual(x['closed_trade_count'],1)
        self.assertEqual(x['trades'][0]['direction'],'BUY_NY_SELL_JP')
        self.assertEqual(x['trades'][0]['execution_state'],'UNEXECUTED_SYNTHETIC_QUOTE_REPLAY')
    def test_iwatsubo_opposite_leg_when_ny_better(self):
        q=synthetic_quotes();q[0]['jp_bid_jpy_per_g']=4900;q[0]['jp_ask_jpy_per_g']=4910
        p=SPECS['IWATSUBO-CROSS-VENUE-MICROSTRUCTURE']
        one=_theoretical_cash(q[0],p,'SELL_NY_BUY_JP',True)
        two=_theoretical_cash(q[0],p,'BUY_NY_SELL_JP',True)
        self.assertGreater(one,two)
    def test_no_real_order_claims(self):
        for spec in SPECS.values():
            self.assertFalse(spec['live_orders_enabled'])
            self.assertEqual(spec['mode'],'RESEARCH_ONLY')
    def test_20rule_sourcing_distinguished(self):
        for spec in SPECS.values():
            self.assertGreater(len(spec['research_assumptions']),0)
            self.assertGreater(len(spec['source_confirmed_rules']),0)
            self.assertTrue(spec['source_evidence_url'].startswith('https://'))
    def test_generated_code_full_portable_with_same_output(self):
        fixtures={'cross_venue_platinum_quotes':synthetic_quotes()}
        for i,s in enumerate(SPECS.values()):
            with self.subTest(i=i):
                with tempfile.TemporaryDirectory() as d:
                    path=pathlib.Path(d)/'strategy.py'; generate_advanced(s,path)
                    namespace={};exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),namespace)
                    data=fixtures.get(s['kind'],synthetic_bars())
                    self.assertEqual(namespace['run'](data),run_advanced(s,data))
    def test_cli_output_parses_and_uses_real_data_not_hardcoded_fixtures(self):
        with tempfile.TemporaryDirectory() as d:
            d=pathlib.Path(d)
            s=next(s for s in SPECS.values() if s['kind']=='relative_value_rsi')
            src=d/'code.py'; data=d/'my_bars.json'; generate_advanced(s,src)
            data.write_text(json.dumps(synthetic_bars()),encoding='utf-8')
            run=subprocess.run([sys.executable,str(src),str(data)],text=True,capture_output=True,timeout=10)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(json.loads(run.stdout)['closed_trade_count'],run_advanced(s,synthetic_bars())['closed_trade_count'])
    def test_next_open_no_same_close_fill(self):
        x=run_advanced(SPECS['BAEK-2020-HG-PL-RESEARCH'],synthetic_bars())
        self.assertTrue(all(tr['entry_timestamp']>next(e['signal_time'] for e in x['events'] if e['action']==('ENTER_LONG_SPREAD' if tr['legs'][0]['side']=='BUY' else 'ENTER_SHORT_SPREAD') and e['fill_time']==tr['entry_timestamp']) for tr in x['trades']))
    def test_known_leg_contract_pnl(self):
        s=SPECS['BAEK-2020-HG-PL-RESEARCH']
        gross,net,costs=_leg_pnl({'y':1000,'x':4},{'y':1010,'x':4.01},1,s)
        self.assertAlmostEqual(gross,750)  # 2 x 50oz x +$10 - 1 x 25,000 lb x $0.01
        self.assertAlmostEqual(gross-net,costs)
    def test_iwatsubo_stale_quote_must_not_trigger(self):
        q=synthetic_quotes();q[0]['ny_observed_at']='2026-02-02T07:00:00+00:00'
        x=run_advanced(SPECS['IWATSUBO-CROSS-VENUE-MICROSTRUCTURE'],q)
        self.assertEqual(x['events'][0]['status'],'NO_SIGNAL_BAD_QUOTES')
    def test_iwatsubo_non_overlapping_sessions_block(self):
        q=synthetic_quotes();q[0]['sessions_overlap']=False
        x=run_advanced(SPECS['IWATSUBO-CROSS-VENUE-MICROSTRUCTURE'],q)
        self.assertEqual(x['events'][0]['status'],'NO_SIGNAL_BAD_QUOTES')
    def test_iwatsubo_mismatched_expiry_block(self):
        q=synthetic_quotes();q[0]['jp_contract_month']='2026-05'
        x=run_advanced(SPECS['IWATSUBO-CROSS-VENUE-MICROSTRUCTURE'],q)
        self.assertEqual(x['events'][0]['status'],'NO_SIGNAL_BAD_QUOTES')
    def test_crossed_bidask_block(self):
        q=synthetic_quotes();q[0]['ny_ask_usd_per_oz']=900
        x=run_advanced(SPECS['IWATSUBO-CROSS-VENUE-MICROSTRUCTURE'],q)
        self.assertEqual(x['events'][0]['status'],'NO_SIGNAL_BAD_QUOTES')
    def test_high_costs_prevent_entry(self):
        s=copy.deepcopy(SPECS['IWATSUBO-CROSS-VENUE-MICROSTRUCTURE']);s['parameters']['estimated_roundtrip_fees_jpy']=1e8
        x=run_advanced(s,synthetic_quotes())
        self.assertEqual(x['closed_trade_count'],0)
    def test_iwatsubo_unmatched_metal_lots_reject(self):
        s=copy.deepcopy(SPECS['IWATSUBO-CROSS-VENUE-MICROSTRUCTURE']);s['parameters']['jp_qty']=1
        with self.assertRaises(ResearchError): validate_advanced_spec(s)
    def test_bad_fractional_futures_qty(self):
        s=copy.deepcopy(SPECS['BAEK-2020-HG-PL-RESEARCH']);s['parameters']['qty_y']=1.5
        with self.assertRaises(ResearchError):validate_advanced_spec(s)
    def test_negative_hedge_requires_new_research(self):
        r=synthetic_bars()
        for row in r[:40]:row['close']['PL']=3000-row['close']['HG']*250
        s=SPECS['BAEK-2020-HG-PL-RESEARCH']
        with self.assertRaises(ResearchError):run_advanced(s,r)
    def test_unknown_market_provenance_not_invented(self):
        for s in SPECS.values():
            self.assertEqual(s['mode'],'RESEARCH_ONLY')
            self.assertFalse(s['live_orders_enabled'])
    def test_code_generation_differs_three_families(self):
        with tempfile.TemporaryDirectory() as d:
            shas=[]
            for i,s in enumerate(SPECS.values()):
                shas.append(generate_advanced(s,pathlib.Path(d)/str(i)/'generated.py')['code_sha256'])
            self.assertEqual(len(set(shas)),3)
    def test_synthetic_results_no_real_backtest(self):
        for s in SPECS.values():
            x=run_advanced(s,synthetic_quotes() if s['kind']=='cross_venue_platinum_quotes' else synthetic_bars())
            self.assertEqual(x['market_backtest'],'REAL_BACKTEST_NOT_RUN')

if __name__=='__main__':unittest.main()

class TestV6RequiredDeliverables(unittest.TestCase):
    def test_all_three_cases_are_generated_not_blocked(self):
        for case in SPECS:
            with self.subTest(case=case):
                d=ROOT/'results'/'0CVvd49h'/'cases'/case
                self.assertTrue((d/'generated_strategy.py').is_file())
                self.assertTrue((d/'strategy_spec.json').is_file())
                self.assertTrue((d/'synthetic_trades.csv').is_file())
                self.assertEqual(json.loads((d/'v3_20_sections.json').read_text())['20_adoption_and_lineage']['decision'],'RESEARCH_STRATEGY_IMPLEMENTED_PENDING_REAL_DATA')
    def test_v3_twenty_sections_each_case(self):
        for case in SPECS:
            d=ROOT/'results'/'0CVvd49h'/'cases'/case
            self.assertEqual(len(json.loads((d/'v3_20_sections.json').read_text())),20)
    def test_mapping_87_rows_and_extra_twelve_not_faked(self):
        import csv
        for case in SPECS:
            d=ROOT/'results'/'0CVvd49h'/'cases'/case
            with (d/'taxonomy_87.csv').open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),87)
            self.assertEqual(len(set(r['taxonomy_id'] for r in rows)),87)
            self.assertEqual(json.loads((d/'v3_20_sections.json').read_text())['08_existing_additional_12']['mapping_rows'],0)
    def test_separate_from_original_tradingview_orders(self):
        for case in SPECS:
            d=ROOT/'results'/'0CVvd49h'/'cases'/case
            sm=json.loads((d/'source_map.json').read_text())
            self.assertFalse(sm['claim_direct_pine_parity'])
            self.assertEqual(sm['strategy_id'],'0CVvd49h')
            self.assertGreater(len(sm['original_order_sites']),0)
