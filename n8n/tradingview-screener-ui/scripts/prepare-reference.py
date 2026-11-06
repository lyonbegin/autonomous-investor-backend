#!/usr/bin/env python3
"""Convert verified 2026-11-06 TradingView Playwright evidence into reproducible
UI fixtures, preserving exact scanner column ordering and returned values.
Fixtures are a fallback; live scanner requests remain the default.
"""
import argparse, json, pathlib, re, datetime
p=argparse.ArgumentParser()
p.add_argument('--evidence',default='evidence/requests_responses.json')
p.add_argument('--out',default='public/reference.json')
args=p.parse_args()
data=json.loads(pathlib.Path(args.evidence).read_text(encoding='utf-8'))
pages={'주식':'stock','ETF':'etf','채권':'bond'}
out={'source':'GitHub Actions Playwright captured scanner request and response JSON; 2026-11-06',
     'captured':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'products':{}}
for entry in data:
    page=pages.get(entry.get('page'))
    if not page or entry.get('status')!=200:continue
    if '/enum/ordered' in entry.get('url',''):
        enum=entry.get('response_json')
        if isinstance(enum,dict):out['products'].setdefault(page,{'tabs':{}})['enum']=enum
        continue
    if '/scan?' not in entry.get('url',''):continue
    action=entry.get('action','')
    if action=='initial':index=0
    else:
        match=re.match(r'column_tab_(\d+)_',action)
        if not match:continue
        index=int(match.group(1))
    request=entry.get('request_json')
    response=entry.get('response_json')
    if not request or not isinstance(response,dict) or not isinstance(response.get('data'),list):continue
    product=out['products'].setdefault(page,{'tabs':{}})
    product['tabs'][str(index)]={'columns':request['columns'],'request':request,
       'response':{'totalCount':response.get('totalCount'), 'data':response['data'][:40]}}
path=pathlib.Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
for prod,value in out['products'].items():
    print(prod,'tabs',len(value['tabs']),
          'initial rows',len(value['tabs'].get('0',{}).get('response',{}).get('data',[])))
assert all('0' in out['products'].get(product,{}).get('tabs',{}) for product in pages.values()),'Missing baseline captured fixtures'
