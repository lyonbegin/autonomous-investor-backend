"""Evidence and rule-grounding checks for future automated scholarly search + model extraction.

The program validates exact string locations in genuinely retrieved documents.
Metadata/title hits never become source-confirmed executable trade rules.
"""
from __future__ import annotations
from html.parser import HTMLParser
import hashlib,re,urllib.parse,urllib.request, json
from datetime import datetime, timezone

class ArticleParser(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.ignore=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','nav','footer'):self.ignore+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','nav','footer') and self.ignore:self.ignore-=1
    def handle_data(self,data):
        if not self.ignore and data.strip():self.parts.append(data)
    def text(self):return ' '.join(' '.join(self.parts).split())


def normalize(text):return ' '.join(text.casefold().split())


def verify_rule_excerpt(doc_text,rule):
    """Require verbatim quote in retrieved content, avoiding invented page/citations."""
    excerpt=rule.get('source_excerpt')
    if not isinstance(excerpt,str) or len(excerpt)<30:
        return {'status':'BLOCKED_QUOTE_MISSING_OR_TOO_SHORT'}
    hay=normalize(doc_text);needle=normalize(excerpt)
    i=hay.find(needle)
    if i<0: return {'status':'BLOCKED_QUOTE_NOT_FOUND_IN_SOURCE'}
    return {'status':'EXACT_TEXT_QUOTE_FOUND','normalized_offset':i,'quote_sha256':hashlib.sha256(needle.encode()).hexdigest()}


class OpenAlexResearch:
    """Search for candidates via a public scholarly metadata API; no claim of full text."""
    def __init__(self,get=None):self.get=get or self._get
    @staticmethod
    def _get(url):
        req=urllib.request.Request(url,headers={'User-Agent':'ResearchEvidencePrototype/0.5','Accept':'application/json'})
        with urllib.request.urlopen(req,timeout=18) as f:return json.load(f)
    def search(self,query,n=5):
        if not query.strip() or n<1 or n>20: raise ValueError('query / n invalid')
        url='https://api.openalex.org/works?'+urllib.parse.urlencode({'search':query,'per-page':n})
        try:
            r=self.get(url)
            items=r['results']
            data=[{'title':x.get('title'),'doi':x.get('doi'),'publication_year':x.get('publication_year'),
                   'landing_page':(x.get('primary_location') or {}).get('landing_page_url'),
                   'open_access':(x.get('open_access') or {}).get('is_oa',False)} for x in items]
            return {'status':'SEARCH_EXECUTED_METADATA_ONLY','query':query,'provider':'OpenAlex',
                    'url':url,'executed_at_utc':datetime.now(timezone.utc).isoformat(),
                    'results':data,'rule_extraction_status':'NOT_PERFORMED'}
        except (ValueError,KeyError,TypeError,OSError,TimeoutError) as e:
            return {'status':'BLOCKED_EXTERNAL_RESEARCH','query':query,'provider':'OpenAlex',
                    'error':type(e).__name__+': '+str(e)[:150],'results':[]}

class EvidenceHTML:
    """Opt-in full-text retrieval from allowlisted HTTPS domains; no access bypass."""
    def __init__(self,fetch=None,allowed_hosts=None):
        self.fetch=fetch or self._fetch
        self.allowed_hosts=set(allowed_hosts or [])
    @staticmethod
    def _fetch(url):
        req=urllib.request.Request(url,headers={'User-Agent':'ResearchEvidencePrototype/0.5'})
        with urllib.request.urlopen(req,timeout=15) as f:
            if f.headers.get_content_type() not in ('text/html','text/plain'):raise ValueError('unsupported MIME')
            return f.read(1_000_001)
    def read(self,url):
        p=urllib.parse.urlsplit(url)
        if p.scheme!='https' or p.hostname not in self.allowed_hosts or p.username or p.password:
            return {'status':'BLOCKED_UNTRUSTED_OR_NONHTTPS_URL'}
        try:
            raw=self.fetch(url)
            if len(raw)>1_000_000:raise ValueError('oversized html')
            parser=ArticleParser();parser.feed(raw.decode('utf-8',errors='replace'))
            text=parser.text()
            return {'status':'FULL_TEXT_RETRIEVED','url':url,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
                    'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'body_text':text}
        except (OSError,ValueError,TimeoutError) as e:
            return {'status':'BLOCKED_SOURCE_RETRIEVAL','error':type(e).__name__+': '+str(e)[:150]}


def grounded_rule_batch(document,extractions):
    if document.get('status')!='FULL_TEXT_RETRIEVED':return {'status':'BLOCKED_NO_VERIFIED_FULL_TEXT','rules':[]}
    results=[]
    for proposed in extractions:
        proof=verify_rule_excerpt(document['body_text'],proposed)
        results.append({**proposed,'quote_verification':proof})
    if any(x['quote_verification']['status']!='EXACT_TEXT_QUOTE_FOUND' for x in results):
        return {'status':'BLOCKED_ONE_OR_MORE_UNGROUNDED_RULES','rules':results}
    return {'status':'QUOTES_TEXT_VERIFIED_NOT_SEMANTICALLY_APPROVED','rules':results}
