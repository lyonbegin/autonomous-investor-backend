import unittest, pathlib,sys,copy,tempfile,json
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from auto_discovery_v6 import AutoDesignCoordinatorV6,ResearchDesignModel
from build_v6 import SPECS

ECONOMIC='Cross-market platinum futures prices in New York and Japan may diverge when local liquidity is temporarily low.'
URL='https://www.mdpi.com/1911-8074/15/12/593'

class Search:
    def search(self,q):return {'status':'SEARCH_EXECUTED_METADATA_ONLY','results':[{'landing_page':URL}]}
class Reader:
    def read(self,u):return {'status':'FULL_TEXT_RETRIEVED','body_text':ECONOMIC,'url':u,'text_sha256':'fixture-only'}
class Model:
    def __init__(self,mode='good'):self.mode=mode
    def design(self,source_id,hyp,doc):
        s=copy.deepcopy(SPECS['IWATSUBO-CROSS-VENUE-MICROSTRUCTURE']);s['source_id']=source_id;s['source_evidence_url']=doc['url']
        q=ECONOMIC if self.mode!='wrong_quote' else 'XXX not in real text: '#12
        if self.mode=='no_assumption':s['research_assumptions']=[]
        return {'status':'MODEL_DRAFT_UNTRUSTED','candidates':[{'strategy_spec':s,'economic_evidence_quotes':[{'source_excerpt':q,'source_location':'Intro'}]}]}

class TestAutonomousResearchAssumptionGate(unittest.TestCase):
    def test_literature_economic_mechanism_without_trading_recipe_can_generate(self):
        with tempfile.TemporaryDirectory() as d:
            c=AutoDesignCoordinatorV6(Search(),Reader(),Model(),fixture_mode=True)
            r=c.run('0CVvd49h',[{'hypothesis_id':'H1','search_queries':['cross venue platinum price divergence']}],d)
            self.assertEqual(r['generated_count'],1)
            self.assertEqual(r['products'][0]['status'],'FIXTURE_ONLY_DESIGN')
            self.assertTrue((pathlib.Path(d)/'cases'/r['products'][0]['case_key']/'generated_strategy.py').is_file())
    def test_change_only_source_id_reuses_same_generic_code_path(self):
        for source_id in ('0CVvd49h','02yfhjiz'):
            with tempfile.TemporaryDirectory() as d:
                r=AutoDesignCoordinatorV6(Search(),Reader(),Model(),fixture_mode=True).run(source_id,[{'hypothesis_id':'H1','search_queries':['test query']}],d)
                self.assertEqual(r['generated_count'],1)
                self.assertEqual(r['products'][0]['source_id'],source_id)
    def test_invented_quote_is_blocked_not_economic_research(self):
        with tempfile.TemporaryDirectory() as d:
            r=AutoDesignCoordinatorV6(Search(),Reader(),Model('wrong_quote'),fixture_mode=True).run('0CVvd49h',[{'hypothesis_id':'H','search_queries':['test']}],d)
            self.assertEqual(r['generated_count'],0)
            self.assertEqual(r['products'][0]['status'],'UNSUPPORTED_ECONOMIC_CLAIM')
    def test_research_assumption_missing_blocks_honesty_not_development_path(self):
        with tempfile.TemporaryDirectory() as d:
            r=AutoDesignCoordinatorV6(Search(),Reader(),Model('no_assumption'),fixture_mode=True).run('0CVvd49h',[{'hypothesis_id':'H','search_queries':['test']}],d)
            self.assertEqual(r['generated_count'],0)
            self.assertEqual(r['products'][0]['status'],'RESEARCH_ASSUMPTIONS_OR_MECHANISM_MISSING')
    def test_missing_ai_provider_marked_not_verified(self):
        m=ResearchDesignModel(endpoint=None,model=None,api_key=None)
        # Credential env may exist on runner; force absent explicitly by removing via monkey patch.
        self.assertIn(m.design('SOURCE','hypothesis',{'body_text':'source'})['status'],('MODEL_NOT_CONFIGURED','MODEL_GENERATION_ERROR','INVALID_MODEL_ENDPOINT'))

if __name__=='__main__':unittest.main()
