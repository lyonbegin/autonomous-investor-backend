import copy,hashlib,json,pathlib,sys,tempfile,unittest
BASE=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from auto_discovery import AutoDiscoveryCoordinator,RuleSpecModel
SPEC=json.loads((BASE/'evidence'/'a5uitxrd.json').read_text())['cases'][0]['strategy_spec']
TEXT='Research article summary. Buy the top earnings surprise decile and short the bottom earnings surprise decile using published information.'
URL='https://example.org/review'
QUOTE='Buy the top earnings surprise decile and short the bottom earnings surprise decile'

class FakeSearch:
    def search(self,q):return {'status':'SEARCH_EXECUTED_METADATA_ONLY','results':[{'landing_page':URL}]}
class FakeReader:
    def read(self,url):return {'status':'FULL_TEXT_RETRIEVED','url':url,'body_text':TEXT,
                              'text_sha256':hashlib.sha256(TEXT.encode()).hexdigest()}
class FakeModel:
    def __init__(self,invalid=False):self.invalid=invalid
    def extract(self,sid,h,doc):
        spec=copy.deepcopy(SPEC)
        spec['source_id']=sid;spec['mode']='RESEARCH_ONLY';spec['source_evidence_url']=URL
        rule={'rule':'buy high surprise sell low surprise',
              'source_excerpt':QUOTE if not self.invalid else 'Buy the something else which does not occur in the document at all',
              'source_location':'example section'}
        spec['source_confirmed_rules']=[rule]
        return {'status':'MODEL_EXTRACTION_UNTRUSTED_PENDING_GATES',
                'candidates':[{'source_confirmed_rule_excerpts':[rule],'strategy_spec':spec}]}

class Tests(unittest.TestCase):
    def test_no_config_model_returns_no_fake_success(self):
        model=RuleSpecModel(endpoint='',model='',api_key='')
        self.assertEqual(model.extract('test',{}, {'url':URL,'body_text':TEXT})['status'],'BLOCKED_AI_MODEL_NOT_CONFIGURED')
    def test_offline_injected_web_model_generates_explicit_fixture_only(self):
        with tempfile.TemporaryDirectory() as td:
            h={'hypothesis_id':'H-TEST','search_queries':['earnings decile research']}
            o=AutoDiscoveryCoordinator(FakeSearch(),FakeReader(),FakeModel(),fixture_mode=True).run('a5uitxrd',[h],td)
            self.assertEqual(o['new_strategy_code_generated'],1)
            self.assertEqual(o['products'][0]['status'],'FIXTURE_ONLY_GENERATION')
            self.assertFalse(o['actual_autonomous_discovery_verified'])
            d=pathlib.Path(td)/'candidates'/o['products'][0]['case_key']
            self.assertTrue((d/'generated_strategy.py').exists())
            self.assertEqual(o['products'][0]['market_data_status'],'NOT_VERIFIED')
    def test_false_citation_prevents_generation(self):
        with tempfile.TemporaryDirectory() as td:
            o=AutoDiscoveryCoordinator(FakeSearch(),FakeReader(),FakeModel(True),fixture_mode=True).run('a5uitxrd',
                [{'hypothesis_id':'H-TEST','search_queries':['research']}],td)
            self.assertEqual(o['new_strategy_code_generated'],0)
            self.assertEqual(o['products'][0]['status'],'BLOCKED_UNGROUNDED_SOURCE_RULE')

if __name__=='__main__':unittest.main()

class DetailedReportTest(unittest.TestCase):
    def test_research_report_has_real_20_fields_and_marked_gaps(self):
        sys.path.insert(0,str(BASE/'src'))
        from detailed_reporting import build_case_report
        from research_v5 import run_v5
        disc=pathlib.Path('/mnt/data/TradingView_Recursive_33890_20261108.zip')
        src=pathlib.Path('/mnt/data/03_Strategy4428_통합3455_Pine원본_전수상태_20261109.zip')
        if not disc.exists() or not src.exists():self.skipTest('Actual user archive unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            run_v5(disc,src,'a5uitxrd',tmp,synthetic_input=BASE/'examples'/'earnings_synthetic_fixture.json')
            r=build_case_report(tmp,'a5uitxrd','PEAD-EVENT-DECILE-SPREAD')
            self.assertEqual(sum(k[:2].isdigit() for k in r),20)
            self.assertEqual(r['19_backtest_trades_charts']['real_backtest'],'REAL_BACKTEST_NOT_RUN')
            self.assertEqual(r['08_extra_12']['rows'],0)
            self.assertEqual(r['20_assessment']['status'],'RESEARCH_ONLY')
