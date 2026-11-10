"""Executable evidence-first run for actual Pine archive; no fictional AI discovery.

P00 original metadata -> P02 verified source + static line-evidence -> P03 cautious
hypothesis -> P04 externally reviewed examples (separate from automatic searches)
-> P05 evidence-backed specs -> P06 generated stdlib code + fixture tests.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,pathlib,tempfile,sys
from datetime import datetime,timezone
from source_archive import PineArchive
from source_evidence import analyze_pine
from hypothesis_engine import infer_hypotheses,map_taxonomy_87
from pipeline import run,load_taxonomy,dump
from evidence_gate import OpenAlexResearch,EvidenceHTML
from auto_discovery import AutoDiscoveryCoordinator, RuleSpecModel

HERE=pathlib.Path(__file__).resolve().parents[1]

def _write_taxonomy(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['taxonomy_id','name','relationship','source_and_hypothesis_justification','decision'])
        w.writeheader()
        for x in rows:w.writerow({**x,'source_and_hypothesis_justification':json.dumps(x['source_and_hypothesis_justification'],ensure_ascii=False)})


def run_v5(discovery_archive,pine_archive,source_id,root=HERE/'results',catalog=HERE/'catalog'/'taxonomy_87.tsv',
            context_dir=HERE/'examples'/'contexts',evidence_dir=HERE/'evidence',synthetic_input=None,
            auto_search=False,allowed_hosts=None):
    adapter=PineArchive(pine_archive)
    src,code=adapter.load(source_id)
    base=pathlib.Path(root)/source_id
    base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        source_dir=pathlib.Path(tmp)
        if code is not None:
            (source_dir/(source_id+'.pine')).write_bytes(code.encode('utf-8'))
        result=run(discovery_archive,source_id,root,catalog,source_dir=source_dir,
                   context_dir=context_dir,evidence_dir=evidence_dir,synthetic_bars=synthetic_input)
    # v4 baseline is not silently replaced: extended, grounded analysis added here.
    semantic=analyze_pine(code) if code is not None else None
    ctxpath=pathlib.Path(context_dir)/(source_id+'.json') if context_dir else None
    context=json.loads(ctxpath.read_text(encoding='utf-8')) if ctxpath and ctxpath.is_file() else {}
    hyp=infer_hypotheses(source_id,semantic,context)
    tax=map_taxonomy_87(load_taxonomy(catalog),semantic,hyp)
    _write_taxonomy(base/'taxonomy_87x12.csv',tax)
    dump(base/'hypothesis_register.json',hyp)
    auto_research=None
    if auto_search and hyp['hypotheses']:
        auto_research=AutoDiscoveryCoordinator(OpenAlexResearch(),
            EvidenceHTML(allowed_hosts=allowed_hosts or []),RuleSpecModel()).run(source_id,hyp['hypotheses'],base/'automatic_research')
    if code is not None:
        # Local-only raw Pine artifact for user audit, NOT published to GitHub.
        (base/'original.pine').write_bytes(code.encode('utf-8'))
    old=json.loads((base/'original_analysis.json').read_text(encoding='utf-8'))
    old['01_original_identity']['verified_archive']=src
    old['02_pine_functional_analysis']={'status':semantic['status'] if semantic else src['status'],
        'actual_source_integrity':src,'source_call_analysis':semantic}
    old['04_original_trade_rules']={'status':'STATIC_ORDER_CALLS_IDENTIFIED_NOT_EXECUTION_RECONSTRUCTED' if semantic else 'NO_SOURCE',
        'source_line_order_expressions':semantic['order_calls'] if semantic else []}
    old['06_economic_provenance']={'status':'EVIDENCE_GROUNDED_RESEARCH_HYPOTHESES_NOT_PROVEN_TRADE',
        'source_context':context,'hypotheses':hyp['hypotheses']}
    old['07_canonical_87']={'status':'ALL_87_ASSESSED_WITH_EVIDENCE_LEVELS','rows':87,
        'research_link_count':sum(x['relationship']=='RESEARCH_LINK_NOT_CONFIRMED_TRADE' for x in tax)}
    old['08_extra_12']={'status':'CANONICAL_EXTRA_12_NOT_IDENTIFIED_DO_NOT_INVENT'}
    old['09_hypotheses']={'status':hyp['status'],'count':len(hyp['hypotheses']), 'generator':'DETERMINISTIC_GROUNDED_RULES_NOT_LLM'}
    old['10_external_research']={'status':'MANUALLY_REVIEWED_EXTERNAL_WEB_REFERENCES' if result['external_cases'] else 'NOT_EXECUTED',
      'automated_external_search':'NOT_EXECUTED_NO_NETWORK_PROVIDER_CONFIG','external_case_count':len(result['external_cases'])}
    dump(base/'original_analysis.json',old)
    excerpts=[]
    if semantic:
        for call in semantic['calls']:
            if call['callee'].startswith(('strategy.','request.')):
                expr=call['source_expression'].replace('\n',' ')
                excerpts.append(f"- L{call['start_line']}-{call['end_line']} `{call['callee']}`: `{expr[:260]}`")
    lines=[f'# 원본 {source_id} Pine 전체 분석 (v5, 정적 근거)','','## 01 출처·해시',
           f"- 상태: `{src['status']}`",f"- 원본 SHA-256: `{src.get('sha256','UNAVAILABLE')}`",
           f"- 아카이브 SHA-256: `{src.get('archive_sha256','UNAVAILABLE')}`",
           f"- 원본 위치: `{src.get('source_member','UNAVAILABLE')}`",
           f"- 공개 참조 URL: {src.get('source_url','UNAVAILABLE')}",
           f"- 실제 Pine 행수: {src.get('line_count','UNAVAILABLE')}",
           '', '## 02 정확한 소스 줄 번호를 가진 함수 호출',
           *excerpts,'',
           '경고: 함수 호출 검출은 제어흐름·주문체결 재현 및 Pine/Python 의미동등성 증명이 아닙니다.',
           '', '## 03 시장/상품',f'기존 자료상 시장 문맥(실계약 검증 아님): {json.dumps(context,ensure_ascii=False)}',
           '', '## 04 원본 주문 코드',
           f"Pine이 실제 수행한 것으로 확정 가능한 것은 호출 존재뿐입니다. 호출 수: {len(semantic['order_calls']) if semantic else 0}; 모든 주문·리스크 플래그는 정적 잠정 기록입니다.",
           '', '## 05 원본 성과', '실제 원본과 동일한 데이터의 TradingView/독립 backtest 검증 미실행.',
           '', '## 06 경제적 수익 메커니즘 — 가설, 원본 코드와 분리',
           *[f"- {h['hypothesis_id']}: {h['economic_mechanism']} / 반증: {'; '.join(h['falsification_conditions'])}" for h in hyp['hypotheses']],
           '', '## 07 기존 87개 전수 매핑',
           f"정본 87건 전수 행 존재. 근거 있는 연구 연결 후보: {sum(x['relationship']=='RESEARCH_LINK_NOT_CONFIRMED_TRADE' for x in tax)}건. 분류 미수행 = 자동승인 아님.",
           '', '## 08 추가 12개', '원래 추가 12개 정본 미확보: 임의 명칭·ID 보충 금지.',
           '', '## 09 연구 가설', f"총 {len(hyp['hypotheses'])}개 규칙기반 가설. AI 자동 연구 실행 아님.",
           '', '## 10 외부 검색',
           '이번 보고의 웹 근거는 별도 수동 검증 자료이며 프로그램에서 외부 검색 API를 실호출하지 않았습니다.',
           '', '## 최종 단계 판정',
           'SOURCE_SHA_VERIFIED / SOURCE_STATIC_ANALYSIS_EXECUTED / RULE_BASED_HYPOTHESES / REAL_BACKTEST_NOT_RUN / UI_NOT_DEPLOYED / V3_NOT_PASSED']
    (base/'original_analysis.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    logpath=base/'search_log.jsonl'
    logs=[{'status':'SEARCH_NOT_EXECUTED_BY_ENGINE','provider':'NONE_OFFLINE',
           'query':q,'hypothesis_id':h['hypothesis_id'],'generated_from_pine_sha':src.get('sha256'),
           'note':'Queries are reproducible, but external search was not run from this process.'}
          for h in hyp['hypotheses'] for q in h['search_queries']]
    logpath.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in logs) or
                       json.dumps({'status':'SEARCH_NOT_EXECUTED_BY_ENGINE','reason':'No grounded hypotheses'})+'\n',encoding='utf-8')
    result.update({'source_status':src['status'],'pine_sha256':src.get('sha256'),
       'source_line_count':src.get('line_count'), 'static_call_count':semantic['call_count'] if semantic else None,
       'strategy_order_calls':len(semantic['order_calls']) if semantic else None,
       'hypotheses_count':len(hyp['hypotheses']), 'hypotheses_status':hyp['status'],
       'taxonomy_87_checked':len(tax),'taxonomy_12_status':'MISSING_CANONICAL',
       'search_status':'SEARCH_ATTEMPTED_AUTOMATICALLY_SEE_AUTO_LOG' if auto_search else 'SEARCH_NOT_EXECUTED_BY_ENGINE',
       'auto_research':auto_research,
       'original_source_code_local':'original.pine' if code is not None else None,
       'real_backtest_status':'REAL_BACKTEST_NOT_RUN', 'v3_acceptance':'NOT_PASSED'})
    dump(base/'index.json',result)
    (base/'decision_log.md').write_text(f'# 원본 {source_id} 판정\n\n'
      f"- 원본 SHA 검증: {src['status']}\n"
      f"- Pine 정적 분석: {semantic['status'] if semantic else 'NOT_EXECUTED'}\n"
      f"- 기존 87개: 전수 판별(자동 거래 연결 주장 없음), 추가 12개: 정본 미확보\n"
      f"- 경제적 가설: {len(hyp['hypotheses'])}건, 규칙 기반·반증 조건 있음\n"
      f"- 실외부 AI 검색/원문 자동추출: 미실행\n"
      f"- 독립 사례: 수동 근거 기반 {len(result['external_cases'])}건\n"
      '- 실데이터 백테스트·PAPER·LIVE·배포: 미실행\n'
      '- v3 전체 합격: NOT_PASSED\n',encoding='utf-8')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--discovery',type=pathlib.Path,required=True)
    ap.add_argument('--pine-archive',type=pathlib.Path,required=True)
    ap.add_argument('--source-id',required=True)
    ap.add_argument('--out',type=pathlib.Path,default=HERE/'results')
    ap.add_argument('--synthetic-input',type=pathlib.Path)
    ap.add_argument('--auto-search',action='store_true',help='Network + configured AI required, otherwise accurately blocked')
    ap.add_argument('--allowed-host',action='append',default=[],help='Allowlisted HTTPS host for research full text')
    opts=ap.parse_args()
    print(json.dumps(run_v5(opts.discovery,opts.pine_archive,opts.source_id,opts.out,
         synthetic_input=opts.synthetic_input,auto_search=opts.auto_search,allowed_hosts=opts.allowed_host),ensure_ascii=False,indent=2))
