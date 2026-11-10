import copy,json,os,pathlib,subprocess,sys,tempfile,unittest,zipfile
BASE=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from source_archive import PineArchive
from source_evidence import analyze_pine
from hypothesis_engine import infer_hypotheses,map_taxonomy_87
from evidence_gate import OpenAlexResearch,EvidenceHTML,verify_rule_excerpt,grounded_rule_batch
from strategy_codegen import generate
from strategy_runtime import earnings_decile_long_short,InvalidSpec
from pipeline import load_taxonomy
from research_v5 import run_v5

ARCHIVE=pathlib.Path('/mnt/data/03_Strategy4428_통합3455_Pine원본_전수상태_20261109.zip')
DISC=pathlib.Path('/mnt/data/TradingView_Recursive_33890_20261108.zip')
SPEC=json.loads((BASE/'evidence'/'a5uitxrd.json').read_text())['cases'][0]['strategy_spec']
BARS=json.loads((BASE/'examples'/'earnings_synthetic_fixture.json').read_text())

class V5Tests(unittest.TestCase):
    @unittest.skipUnless(ARCHIVE.exists(),'Actual source archive not mounted')
    def test_three_original_source_hash_and_line_counts(self):
        z=PineArchive(ARCHIVE)
        expected={'0CVvd49h':(1158,'06728ba8446771d2e45c63f2fca0d8cce378c96b445836f47c82e279285c1852'),
                  '02yfhjiz':(592,'81d0299b4ee1c60e87e88e8279d13c928a285a07a32658cd1cfcccee6d94a701'),
                  'a5uitxrd':(166,'d6ca7629bbdcec8f94ff8b1ca83d296b4211c037f509ca816c91771fd2383e05')}
        for sid,(lines,sha) in expected.items():
            with self.subTest(sid=sid):
                obj,source=z.load(sid)
                self.assertEqual(obj['status'],'SOURCE_SHA_VERIFIED')
                self.assertEqual(obj['sha256'],sha)
                self.assertEqual(obj['line_count'],lines)
                self.assertIn('strategy(',source)
    @unittest.skipUnless(ARCHIVE.exists(),'Source archive not mounted')
    def test_missing_original_is_not_substituted(self):
        self.assertEqual(PineArchive(ARCHIVE).load('zzzzzzzz')[0]['status'],'SOURCE_MISSING_OR_DUPLICATED')
    @unittest.skipUnless(ARCHIVE.exists(),'Source archive not mounted')
    def test_malicious_id_does_not_escape_zip(self):
        with self.assertRaises(ValueError):PineArchive(ARCHIVE).load('../../etc/passwd')
    def test_manifest_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=pathlib.Path(tmp)/'bad.zip';s='0CVvd49h';stem='strategies/'+s
            with zipfile.ZipFile(dest,'w') as z:
                z.writestr(stem+'/original/strategy.pine','//@version=6\nstrategy("tampered")\n')
                z.writestr(stem+'/manifest.json',json.dumps({'script_id':s,'pine_sha256':'ff'*32}))
            self.assertEqual(PineArchive(dest).load(s)[0]['status'],'MANIFEST_SHA_MISMATCH')
    def test_comments_and_multiline_calls_tracked_exactly(self):
        source='''//@version=6
strategy("xx")
/* strategy.entry("fake",strategy.long) */
if close>open
    strategy.entry(
        "real", strategy.long,
        qty=1)
// request.earnings(x)
request.security(syminfo.tickerid,"D",close)
'''
        a=analyze_pine(source)
        c=next(x for x in a['calls'] if x['callee']=='strategy.entry')
        self.assertEqual((c['start_line'],c['end_line']),(5,7))
        self.assertEqual(len(a['order_calls']),1)
        self.assertFalse([x for x in a['calls'] if x['callee']=='request.earnings'])
    @unittest.skipUnless(ARCHIVE.exists(),'Source archive not mounted')
    def test_actual_earnings_source_is_not_a_market_neutral_strategy(self):
        st,text=PineArchive(ARCHIVE).load('a5uitxrd')
        calls=analyze_pine(text)
        h=infer_hypotheses('a5uitxrd',calls)
        self.assertEqual(len(h['hypotheses']),1)
        self.assertEqual(h['hypotheses'][0]['taxonomy_candidates'][0]['id'],'S085')
        self.assertIn('NOT_PROVEN',h['hypotheses'][0]['original_vs_new'])
        tax=map_taxonomy_87(load_taxonomy(BASE/'catalog'/'taxonomy_87.tsv'),calls,h)
        self.assertEqual(len(tax),87)
        self.assertEqual([x for x in tax if x['relationship']=='RESEARCH_LINK_NOT_CONFIRMED_TRADE'][0]['taxonomy_id'],'S085')
    @unittest.skipUnless(ARCHIVE.exists(),'Source archive not mounted')
    def test_generic_non_event_original_is_not_forced_into_a_strategy(self):
        _,code=PineArchive(ARCHIVE).load('02yfhjiz')
        h=infer_hypotheses('02yfhjiz',analyze_pine(code))
        self.assertEqual(h['hypotheses'],[])
    def test_openalex_api_does_not_claim_rules_from_metadata(self):
        r=OpenAlexResearch(get=lambda url:{'results':[{'title':'Review','doi':'https://doi.org/10.1/xx','publication_year':2021,
            'primary_location':{'landing_page_url':'https://example.org'}}]}).search('post earnings')
        self.assertEqual(r['status'],'SEARCH_EXECUTED_METADATA_ONLY')
        self.assertEqual(r['rule_extraction_status'],'NOT_PERFORMED')
    def test_excerpt_rejects_fabricated_rule(self):
        doc={'status':'FULL_TEXT_RETRIEVED','body_text':'Research study: Buy the top surprise decile and short the bottom surprise decile.'}
        yes={'source_excerpt':'Buy the top surprise decile and short the bottom surprise decile'}
        no={'source_excerpt':'Use a stop loss of 3.5 percent and a 60 day exit in this market'}
        self.assertEqual(grounded_rule_batch(doc,[yes])['status'],'QUOTES_TEXT_VERIFIED_NOT_SEMANTICALLY_APPROVED')
        self.assertEqual(grounded_rule_batch(doc,[yes,no])['status'],'BLOCKED_ONE_OR_MORE_UNGROUNDED_RULES')
    def test_retrieval_untrusted_domain_blocked(self):
        client=EvidenceHTML(fetch=lambda url:b'<html><body>Research text</body></html>',allowed_hosts={'example.org'})
        self.assertEqual(client.read('http://example.org/source')['status'],'BLOCKED_UNTRUSTED_OR_NONHTTPS_URL')
        self.assertEqual(client.read('https://evil.invalid/x')['status'],'BLOCKED_UNTRUSTED_OR_NONHTTPS_URL')
        self.assertEqual(client.read('https://example.org/s')['status'],'FULL_TEXT_RETRIEVED')
    def test_event_decile_synthetic_next_open_and_cost_unknown(self):
        r=earnings_decile_long_short(SPEC,BARS)
        self.assertEqual(len(r['trades']),2)
        self.assertEqual(r['gross_pnl_usd'],110)
        self.assertEqual(r['trades'][0]['entry_date'],'2026-02-03')
        self.assertIsNone(r['net_pnl_usd'])
    def test_event_future_data_not_allowed_for_signal(self):
        bars=copy.deepcopy(BARS)
        for e in bars['events']:e['available_at']='2026-02-07T00:00:00Z'
        self.assertEqual(earnings_decile_long_short(SPEC,bars)['status'],'BLOCKED_NO_POST_PUBLICATION_BAR')
    def test_event_short_borrow_missing_cannot_pretend_fill(self):
        bars=copy.deepcopy(BARS);bars['events'][0]['borrow_available']=False
        r=earnings_decile_long_short(SPEC,bars)
        self.assertEqual(r['status'],'BLOCKED_INCOMPLETE_LEGS')
        self.assertEqual(r['trades'],[])
    def test_event_source_quote_and_assumption_always_separate(self):
        self.assertEqual(len(SPEC['source_confirmed_rules']),1)
        self.assertTrue(any(x['field']=='fill_timing' for x in SPEC['research_assumptions']))
        with tempfile.TemporaryDirectory() as td:
            path=pathlib.Path(td)/'generated.py';generate(SPEC,path)
            result=json.loads(subprocess.check_output([sys.executable,str(path),str(BASE/'examples'/'earnings_synthetic_fixture.json')]))
            self.assertEqual(result['gross_pnl_usd'],110)
    @unittest.skipUnless(DISC.exists() and ARCHIVE.exists(),'Actual original source archives unavailable')
    def test_actual_source_end_to_end_two_unrelated_ids(self):
        with tempfile.TemporaryDirectory() as td:
            a=run_v5(DISC,ARCHIVE,'0CVvd49h',td,synthetic_input=BASE/'examples'/'seasonal_synthetic_bars.json')
            b=run_v5(DISC,ARCHIVE,'a5uitxrd',td,synthetic_input=BASE/'examples'/'earnings_synthetic_fixture.json')
            self.assertNotEqual(a['pine_sha256'],b['pine_sha256'])
            self.assertEqual(a['source_status'],'SOURCE_SHA_VERIFIED')
            self.assertEqual(b['source_status'],'SOURCE_SHA_VERIFIED')
            self.assertEqual(len(a['external_cases']),5)
            self.assertEqual(len(b['external_cases']),1)
            self.assertEqual(b['external_cases'][0]['functional_test_status'],'FUNCTIONAL_EXECUTED')
            self.assertEqual((pathlib.Path(td)/'a5uitxrd'/'original.pine').exists(),True)
            self.assertEqual(b['taxonomy_87_checked'],87)
            self.assertEqual(b['v3_acceptance'],'NOT_PASSED')

if __name__=='__main__':unittest.main()
