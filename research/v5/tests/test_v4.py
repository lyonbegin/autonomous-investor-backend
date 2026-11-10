import sys, unittest, json, subprocess, pathlib, tempfile, zipfile, csv
BASE=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from pine_semantics import analyze
from strategy_runtime import InvalidSpec,worked_transaction,seasonal_spread,validate_spec
from strategy_codegen import generate
from external_research import CrossrefSearch,StructuredResearchModel
from pipeline import run,load_taxonomy,verify_pine

AR=pathlib.Path('/mnt/data/TradingView_Recursive_33890_20261108.zip')
SOURCE=json.loads((BASE/'evidence'/'0CVvd49h.json').read_text())
CASES=SOURCE['cases']

class Tests(unittest.TestCase):
    def test_pine_order_lines_not_comments(self):
        code='''//@version=6
strategy("Hello")
// strategy.entry("fake", strategy.long)
/*
strategy.close("block")
*/
if close>open
    strategy.entry("buy",strategy.long)
request.security(syminfo.tickerid,"60",close)
'''
        p=analyze(code)
        self.assertEqual(p['version'],6)
        self.assertEqual(p['declaration'],'strategy')
        self.assertEqual([x['line'] for x in p['features'] if x['category']=='entry'],[8])
        self.assertEqual(p['security'][0]['line'],9)
        self.assertEqual(p['status'],'PARTIAL_STATIC_ANALYSIS')
    def test_pine_indicator_no_fake_order(self):
        p=analyze('//@version=5\nindicator("a")\n// strategy.order(x,y)\nplot(close)')
        self.assertFalse(p['actual_strategy_orders_detected'])
    def test_cme_contract_arithmetic(self):
        s=CASES[0]['strategy_spec']; v=worked_transaction(s)
        self.assertEqual(v['leg_results'][0]['gross_pnl'],6800)
        self.assertEqual(v['leg_results'][1]['gross_pnl'],-1230)
        self.assertEqual(v['gross_pnl'],5570)
        self.assertIsNone(v['net_pnl'])
        self.assertEqual(v['real_backtest_status'],'REAL_BACKTEST_NOT_RUN')
    def test_chan_assumptions_and_separate_months(self):
        s=CASES[1]['strategy_spec']
        self.assertEqual([x['contract_month'].split(';')[0] for x in s['legs']],['July','June'])
        self.assertTrue(any(x['field']=='entry_after' for x in s['research_assumptions']))
        bars=json.loads((BASE/'examples'/'seasonal_synthetic_bars.json').read_text())
        res=seasonal_spread(s,bars)
        self.assertEqual(len(res['trades']),1)
        self.assertEqual(res['trades'][0]['entry'],'2026-03-02')
        self.assertEqual(res['trades'][0]['exit'],'2026-04-16')
        self.assertEqual(res['trades'][0]['gross_pnl'],1600)
        self.assertIsNone(res['trades'][0]['net_pnl'])
    def test_missing_leg_price_fail_closed(self):
        s=CASES[1]['strategy_spec'];bars=json.loads((BASE/'examples'/'seasonal_synthetic_bars.json').read_text())
        bars[2]['open'].pop('GC')
        r=seasonal_spread(s,bars)
        self.assertEqual(r['trades'],[])
        self.assertTrue(any(x.get('status')=='BLOCKED_MISSING_LEG_PRICE' for x in r['events']))
    def test_noninteger_contract_rejected(self):
        s=json.loads(json.dumps(CASES[0]['strategy_spec']))
        s['legs'][0]['quantity']=1.5
        with self.assertRaises(InvalidSpec):validate_spec(s)
    def test_missing_provenance_rejected(self):
        s=json.loads(json.dumps(CASES[0]['strategy_spec']))
        s['source_confirmed_rules']=[]
        with self.assertRaises(InvalidSpec):validate_spec(s)
    def test_generator_two_families_and_output(self):
        with tempfile.TemporaryDirectory() as temp:
            a=pathlib.Path(temp)/'a.py';b=pathlib.Path(temp)/'b.py'
            va=generate(CASES[0]['strategy_spec'],a)
            vb=generate(CASES[1]['strategy_spec'],b)
            self.assertNotEqual(va['code_sha256'],vb['code_sha256'])
            ra=json.loads(subprocess.check_output([sys.executable,str(a)]))
            rb=json.loads(subprocess.check_output([sys.executable,str(b),str(BASE/'examples'/'seasonal_synthetic_bars.json')]))
            self.assertEqual(ra['gross_pnl'],5570)
            self.assertEqual(rb['trades'][0]['gross_pnl'],1600)
    def test_taxonomy_87_exact_and_not_99(self):
        rows=load_taxonomy(BASE/'catalog'/'taxonomy_87.tsv')
        self.assertEqual(len(rows),87)
        self.assertEqual(rows[13],('S014','국제 금 중량·품질·보관지역 프리미엄'))
        self.assertEqual(rows[-1][0],'S087')
    def test_crossref_metadata_only_no_trade_claims(self):
        def stub(url):return {'message':{'items':[{'title':['Test'], 'URL':'https://doi.org/10.foo/bar','DOI':'10.foo/bar'}]}}
        result=CrossrefSearch(fetch=stub).search('cointegration gold platinum')
        self.assertEqual(result['status'],'SEARCH_EXECUTED_METADATA_ONLY')
        self.assertFalse(result['content_rules_verified'])
    def test_crossref_offline_reporting(self):
        def fail(url):raise OSError('network unavailable')
        self.assertEqual(CrossrefSearch(fetch=fail).search('options')['status'],'BLOCKED_EXTERNAL_RESEARCH')
    def test_ai_unconfigured_never_fakes_hypotheses(self):
        self.assertEqual(StructuredResearchModel(endpoint='',model='',api_key='').propose({}, {},[])['status'],'BLOCKED_AI_MODEL_NOT_CONFIGURED')
    def test_ai_schema_validated(self):
        def stub(url,body,key):return {'choices':[{'message':{'content':'{"hypotheses":[{"id":"x","search_queries":[]}]}'}}]}
        result=StructuredResearchModel(endpoint='https://test.invalid/v1/chat/completions',model='m',api_key='t',post=stub).propose({}, {},[])
        self.assertEqual(result['status'],'BLOCKED_INVALID_MODEL_SCHEMA')
    @unittest.skipUnless(AR.exists(),'User discovery ZIP not mounted')
    def test_two_real_ids_same_pipeline_independent_outcomes(self):
        with tempfile.TemporaryDirectory() as td:
            a=run(AR,'0CVvd49h',td,BASE/'catalog'/'taxonomy_87.tsv',evidence_dir=BASE/'evidence',
                  context_dir=BASE/'examples'/'contexts',synthetic_bars=BASE/'examples'/'seasonal_synthetic_bars.json')
            b=run(AR,'02yfhjiz',td,BASE/'catalog'/'taxonomy_87.tsv')
            self.assertNotEqual(a['discovery_title'],b['discovery_title'])
            self.assertEqual(len(a['external_cases']),5)
            self.assertEqual(b['external_cases'],[])
            for item in (a,b):
                self.assertEqual(item['source_status'],'SOURCE_MISSING')
                self.assertEqual(item['taxonomy']['status'],'CANONICAL_87_LOADED_12_MISSING')
                self.assertEqual(item['v3_acceptance'],'NOT_PASSED')
            with (pathlib.Path(td)/'0CVvd49h'/'taxonomy_87x12.csv').open(encoding='utf-8-sig') as f:
                self.assertEqual(len(list(csv.DictReader(f))),87)
    def test_source_checksum_missing_cannot_claim_match(self):
        status,code=verify_pine('0CVvd49h')
        self.assertEqual(status['status'],'SOURCE_MISSING')
        self.assertIsNone(code)

if __name__=='__main__':unittest.main()
