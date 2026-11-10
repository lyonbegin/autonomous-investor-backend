"""Live-search and AI adapters: usable in deployed environment, fail closed if offline.
Crossref metadata alone cannot prove trade rules. Model output alone cannot prove citations.
"""
from __future__ import annotations
import os, json, urllib.parse, urllib.request
from datetime import datetime,timezone

class ExternalResearchUnavailable(RuntimeError):pass

class CrossrefSearch:
    BASE='https://api.crossref.org/works'
    def __init__(self,fetch=None): self.fetch=fetch or self._fetch
    @staticmethod
    def _fetch(url):
        req=urllib.request.Request(url,headers={'User-Agent':'StockResearchEvidence/0.4 (academic metadata only)','Accept':'application/json'})
        with urllib.request.urlopen(req,timeout=15) as resp:return json.load(resp)
    def search(self,query,rows=5):
        if not query.strip():raise ValueError('query required')
        url=self.BASE+'?'+urllib.parse.urlencode({'query':query,'rows':int(rows)})
        try:
            response=self.fetch(url)
            items=response['message']['items']
            return {'status':'SEARCH_EXECUTED_METADATA_ONLY','executed_at_utc':datetime.now(timezone.utc).isoformat(),
                    'provider':'Crossref API','query':query,'url':url,
                    'results':[{'title':x.get('title',[''])[0] if x.get('title') else '', 'doi':x.get('DOI'),
                                'url':x.get('URL'),'publisher':x.get('publisher'),
                                'published':x.get('published',{})} for x in items],
                    'content_rules_verified':False}
        except (OSError,ValueError,KeyError,TimeoutError) as e:
            return {'status':'BLOCKED_EXTERNAL_RESEARCH','provider':'Crossref API','query':query,
                    'error':type(e).__name__+': '+str(e)[:180],'content_rules_verified':False}

class StructuredResearchModel:
    """Optional OpenAI-compatible JSON-response backend. No configured key => never fake AI output.
    Operator must opt in and configure a trusted API endpoint and model name.
    """
    def __init__(self,endpoint=None,model=None,api_key=None,post=None):
        self.endpoint=endpoint or os.getenv('RESEARCH_AI_ENDPOINT')
        self.model=model or os.getenv('RESEARCH_AI_MODEL')
        self.api_key=api_key or os.getenv('RESEARCH_AI_KEY')
        self.post=post or self._post
    @staticmethod
    def _post(url,body,api_key):
        request=urllib.request.Request(url,data=json.dumps(body).encode('utf-8'),
                headers={'Authorization':'Bearer '+api_key,'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request,timeout=50) as response:return json.load(response)
    def propose(self,source_analysis,market_context,taxonomy):
        if not all((self.endpoint,self.model,self.api_key)):
            return {'status':'BLOCKED_AI_MODEL_NOT_CONFIGURED','hypotheses':[]}
        if not self.endpoint.startswith('https://'):
            return {'status':'BLOCKED_INSECURE_MODEL_ENDPOINT','hypotheses':[]}
        instructions=("Generate research hypotheses as strict JSON object {'hypotheses': [...]} using only input evidence. "
          "For each hypothesis return id, economic_actors, instrument_legs, expected_pricing_relation, "
          "profit_mechanism, competing_explanations, required_market_data, falsification_conditions, "
          "source_trace, taxonomy_candidate_ids and search_queries. "
          "Do not say source Pine executes an inferred multi-leg trade without source line evidence. "
          "Do not fabricate citations, backtest performance, prices or contracts. Output may contain zero hypotheses. "
          "All unverified inferred claims must include limitations.")
        body={'model':self.model,'response_format':{'type':'json_object'},'temperature':0,
              'messages':[{'role':'system','content':instructions},
               {'role':'user','content':json.dumps({'pine':source_analysis,'market_context':market_context,
                            'taxonomy':taxonomy},ensure_ascii=False)}]}
        try:
            response=self.post(self.endpoint,body,self.api_key)
            raw=response['choices'][0]['message']['content']
            output=json.loads(raw)
            items=output.get('hypotheses')
            required={'id','economic_actors','instrument_legs','expected_pricing_relation',
                      'profit_mechanism','required_market_data','falsification_conditions','source_trace','search_queries'}
            if not isinstance(items,list) or any(not required.issubset(x) for x in items):
                return {'status':'BLOCKED_INVALID_MODEL_SCHEMA','hypotheses':[]}
            if any(not isinstance(x['search_queries'],list) or not x['source_trace'] for x in items):
                return {'status':'BLOCKED_UNGROUNDED_HYPOTHESIS','hypotheses':[]}
            return {'status':'AI_HYPOTHESES_GENERATED_UNVERIFIED','hypotheses':items,
                    'model':self.model,'evidence_and_market_check_required':True}
        except (OSError,ValueError,KeyError,IndexError,TypeError) as e:
            return {'status':'BLOCKED_AI_RESEARCH','hypotheses':[],'error':type(e).__name__+': '+str(e)[:180]}
