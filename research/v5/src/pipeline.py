"""v3 evidence-contract pipeline: actual codegen, provisional source/AI/search gates.

Case fixtures are explicitly operator-reviewed evidence, never mistaken for automated discovery.
No method fabricates the 12 missing taxonomy definitions or market backtests.
"""
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,json,pathlib,re,subprocess,sys,zipfile
from datetime import datetime,timezone
from pine_semantics import analyze
from strategy_codegen import generate
from external_research import StructuredResearchModel,CrossrefSearch

HERE=pathlib.Path(__file__).resolve().parents[1]
PINNED_SHA={'0CVvd49h':'06728ba8446771d2e45c63f2fca0d8cce378c96b445836f47c82e279285c1852'}
ID_PATTERN=re.compile(r'^[A-Za-z0-9_-]{4,40}$')

def dump(path,content):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(content,ensure_ascii=False,indent=2)+"\n",encoding='utf-8')

def load_discovery(archive,source_id):
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read('manifest.json'))
        with z.open('master.jsonl') as f:
            for line in f:
                d=json.loads(line)
                if d.get('id')==source_id:return d,manifest
    return None,manifest

def verify_pine(source_id,source_dir=None,source_archive=None):
    raw=None;location=None
    if source_dir:
        p=pathlib.Path(source_dir)/(source_id+'.pine')
        if p.is_file():raw=p.read_bytes();location=str(p)
    if raw is None and source_archive:
        with zipfile.ZipFile(source_archive) as z:
            # Supports either <ID>.pine or <ID>/source.pine; ambiguous variants are blocked.
            members=[n for n in z.namelist() if not n.endswith('/')]
            candidates=[n for n in members if pathlib.PurePosixPath(n).name==source_id+'.pine'
                or (source_id in pathlib.PurePosixPath(n).parts and pathlib.PurePosixPath(n).name in {'source.pine','pine.pine','script.pine'})]
            if len(candidates)>1:
                return {'status':'SOURCE_ARCHIVE_AMBIGUOUS','candidates':candidates[:10]},None
            if len(candidates)==1:
                raw=z.read(candidates[0]);location=str(source_archive)+'!'+candidates[0]
    if raw is None:return {'status':'SOURCE_MISSING','reason':'Discovery ZIP has metadata, not Pine code'},None
    digest=hashlib.sha256(raw).hexdigest()
    if source_id in PINNED_SHA and PINNED_SHA[source_id]!=digest:
        return {'status':'SOURCE_HASH_MISMATCH','path':location,'sha256':digest,'expected_sha256':PINNED_SHA[source_id]},None
    try:code=raw.decode('utf-8-sig')
    except UnicodeDecodeError:return {'status':'SOURCE_INVALID_ENCODING','path':location,'sha256':digest},None
    if '//@version' not in code:
        return {'status':'SOURCE_VERSION_UNVERIFIED','path':location,'sha256':digest},None
    return {'status':'SOURCE_HASH_MATCHED' if source_id in PINNED_SHA else 'SOURCE_FOUND_UNPINNED',
            'path':location,'sha256':digest,'bytes':len(raw)},code

def load_taxonomy(path):
    rows=[]
    with pathlib.Path(path).open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():continue
            tid,name=line.rstrip('\n').split('\t',1)
            rows.append((tid,name))
    if [x[0] for x in rows]!=[f'S{i:03}' for i in range(1,88)]:raise ValueError('Canonical 87 IDs must match S001-S087')
    if len({name for _,name in rows})!=87:raise ValueError('Duplicate taxonomy names')
    return rows

def taxonomy_report(out,source_exists,rows,extras=None):
    extra=[]
    if extras:
        with pathlib.Path(extras).open(encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    tid,name=line.strip().split('\t',1)
                    extra.append((tid,name))
        if len(extra)!=12 or len({i for i,_ in extra})!=12:
            raise ValueError('Extra canonical taxonomy requires 12 distinct original entries')
    all_rows=rows+extra
    with (out/'taxonomy_87x12.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['taxonomy_id','name','mapping_status','rationale','source_level']);w.writeheader()
        for tid,name in all_rows:
            w.writerow({'taxonomy_id':tid,'name':name,
                         'mapping_status':'NOT_EVALUATED',
                         'rationale':'Economic-mechanism evidence and exact original Pine required; no direct match claimed',
                         'source_level':'CANONICAL_87_FROM_20261108_REPORT' if tid.startswith('S') else 'EXTRA_CANONICAL_SUPPLIED'})
    return {'status':'CANONICAL_99_LOADED_NOT_CLASSIFIED' if extra else 'CANONICAL_87_LOADED_12_MISSING',
            'rows':len(all_rows),'87_source':'2026-11-08 canonical 87 strategy integrated report',
            'extra_12_status':'LOADED' if extra else 'CANONICAL_EXTRA_12_NOT_IDENTIFIED'}

def discover_research_queries(metadata,context):
    """Search queries are lexical prompts, NOT conclusions about economic trading."""
    title=(metadata or {}).get('title','')
    symbol=(context or {}).get('chart_symbol','')
    return {'status':'KEYWORD_QUERIES_PROPOSED_NOT_RESEARCH_EXECUTED',
            'queries':[s for s in [f'"{title}" multi-leg relative value financial research' if title else None,
                                  f'"{symbol}" futures cross market spread research' if symbol else None] if s],
            'risk':'Queries derived from source title/context only; they are not source-confirmed strategies'}

def case_to_artifacts(case,source_id,out,synthetic_bars=None):
    case_id=case.get('case_id','')
    if not re.fullmatch(r'[A-Za-z0-9-]{5,100}',case_id):raise ValueError('Invalid case ID')
    cdir=out/'cases'/case_id;cdir.mkdir(parents=True,exist_ok=True)
    ev=case['evidence']; dump(cdir/'evidence.json',ev)
    (cdir/'evidence_report.md').write_text(
        f"# {case_id} — 외부 자료\n\n출처: {ev['url']}\n\n근거 위치: {ev['location']}\n\n"
        f"원문 기반 거래 정보: {ev['trade_description']}\n\n"
        f"확인 수준: {ev['verified_status']} / 작성 방식: 사람이 웹 내용을 확인·등록(자동 발견 아님)\n",encoding='utf-8')
    spec=case.get('strategy_spec')
    if spec is None:
        dump(cdir/'execution_manifest.json',{'status':'RULE_EXTRACTION_INCOMPLETE','python':'NOT_GENERATED','market_backtest':'REAL_BACKTEST_NOT_RUN'})
        (cdir/'assessment.md').write_text('독립 거래 알고리즘의 필수 규칙·원문 인용이 불충분하여 코드 생성을 차단했습니다.\n',encoding='utf-8')
        return {'case_id':case_id,'status':'RULE_EXTRACTION_INCOMPLETE','source':ev['url']}
    if spec['source_id']!=source_id:raise ValueError('Case source ID mismatch')
    if len(spec['source_confirmed_rules'])<1 or any(not x.get('source_location') for x in spec['source_confirmed_rules']):
        raise ValueError('Ungrounded source rules')
    dump(cdir/'strategy_spec.json',spec)
    generated=generate(spec,cdir/'generated_strategy.py')
    source_map={'research_origin':'INDEPENDENT_EXTERNAL_CASE_NOT_ORIGINAL_PINE','source_id':source_id,
         'evidence_url':ev['url'],'evidence_location':ev['location'],
         'source_confirmed_rules':spec['source_confirmed_rules'],
         'research_assumptions':spec['research_assumptions'],
         'generated_family':spec['kind'],'validation_scope':'GENERAL_STRATEGY_FAMILY_ONLY'}
    dump(cdir/'source_map.json',source_map)
    cmd=[sys.executable,str(cdir/'generated_strategy.py')]
    if spec['kind'] in ('seasonal_futures_spread','earnings_decile_long_short'):
        if synthetic_bars:cmd.append(str(synthetic_bars))
        else: cmd=[]
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=15) if cmd else None
    output=json.loads(proc.stdout) if proc and proc.returncode==0 else None
    if output:dump(cdir/'functional_result.json',output)
    contract={**generated,'case_id':case_id,
          'functional_test_status':'FUNCTIONAL_EXECUTED' if output else 'FUNCTIONAL_NOT_EXECUTED',
          'functional_test_type':'SOURCE_WORKED_EXAMPLE' if spec['kind']=='worked_transaction' else 'SYNTHETIC_FIXTURE' if output else 'NOT_RUN',
          'exit_code':proc.returncode if proc else None,
          'test_stderr':proc.stderr[:400] if proc else None,
          'real_market_data_sha256':None,'real_backtest_status':'REAL_BACKTEST_NOT_RUN',
          'paper_status':'PAPER_NOT_RUN','ui_status':'NOT_DEPLOYED'}
    dump(cdir/'execution_manifest.json',contract)
    case_tests=cdir/'tests';case_tests.mkdir(exist_ok=True)
    # Exact generated output is checked against independently recorded evidence or a synthetic fixture.
    # These are independent per-case tests, not portfolio-performance proofs.
    fixture_name=None
    if spec['kind'] in ('seasonal_futures_spread','earnings_decile_long_short') and synthetic_bars:
        fixture_name='synthetic_bars.json'
        (case_tests/fixture_name).write_bytes(pathlib.Path(synthetic_bars).read_bytes())
    testtext=(
        'import unittest,sys,json,subprocess,pathlib\n'
        'CASE=pathlib.Path(__file__).resolve().parents[1]\n'
        'class CaseTest(unittest.TestCase):\n'
        '    def test_generated_executes(self):\n'
        '        cmd=[sys.executable,str(CASE/"generated_strategy.py")]\n'
    )
    if fixture_name:
        testtext+='        cmd.append(str(CASE/"tests"/"synthetic_bars.json"))\n'
    testtext+='        data=json.loads(subprocess.check_output(cmd))\n'
    if spec['kind']=='worked_transaction':
        expected=ev.get('source_reported_gross_pnl_usd')
        if expected is None:raise ValueError('Worked transaction requires independent referenced expected P&L')
        testtext+=f'        self.assertAlmostEqual(data["gross_pnl"],{float(expected)!r})\n'
        testtext+='        self.assertIsNone(data["net_pnl"])\n'
    elif spec['kind']=='earnings_decile_long_short':
        testtext+='        self.assertEqual(data["status"],"SYNTHETIC_FIXTURE_SIMULATION_ONLY")\n'
        testtext+='        self.assertEqual(len(data["trades"]),2)\n'
        testtext+='        self.assertIsNone(data["net_pnl_usd"])\n'
    else:
        testtext+='        self.assertEqual(data["status"],"SYNTHETIC_FIXTURE_SIMULATION_ONLY")\n'
        testtext+='        self.assertEqual(len(data["trades"]),1)\n'
        testtext+='        self.assertIsNone(data["trades"][0]["net_pnl"])\n'
    testtext+='        self.assertEqual(data["real_backtest_status"],"REAL_BACKTEST_NOT_RUN")\n'
    testtext+='if __name__=="__main__":unittest.main()\n'
    (case_tests/'test_strategy.py').write_text(testtext,encoding='utf-8')
    checks=f"- source rules: {len(spec['source_confirmed_rules'])}\n- assumptions: {len(spec['research_assumptions'])}\n"
    for rule in spec['source_confirmed_rules']:checks+=f"- 원문: {rule['rule']} — {rule['source_location']}\n"
    for ass in spec['research_assumptions']:checks+=f"- 개발가정: {ass['field']}={ass['value']} — {ass['basis']}\n"
    (cdir/'backtest_report.md').write_text('# 백테스트 검증\n\nREAL_BACKTEST_NOT_RUN: 동시 호가/실계약월·수수료·기간 입력 미확보.\n\n'
                        +('실행한 것은 **교육용 산술 예시**이며 거래 백테스트가 아닙니다.\n' if spec['kind']=='worked_transaction' else '실행한 것은 **합성 봉 기능시험**이며 논문/실시장 성과가 아닙니다.\n'),encoding='utf-8')
    (cdir/'assessment.md').write_text(f'# {case_id} 평가\n\n## 11~20 상세 대응\n'
         f'11. 원문: {ev["url"]}, {ev["location"]}\n\n12. 규칙·가정 분리\n{checks}\n'
         f'13. 레그 명세: {json.dumps(spec["legs"],ensure_ascii=False,indent=2)}\n\n'
         f'14. 로직: {spec["kind"]}, 실행 모델 상세는 generated_strategy.py 및 strategy_spec.json 참조\n\n'
         '15. 비용·마진: 미확보; worked 거래는 비용 이전 금액만 계산\n\n'
         '16. 실데이터: MISSING_DATA, 계약월·호가 미확인\n\n'
         '17. Python: generated_strategy.py 전체 포함\n\n'
         f'18. 기능실행: {contract["functional_test_status"]}, 실행코드 {contract["exit_code"]}\n\n'
         '19. 실데이터 백테스트·차트: REAL_BACKTEST_NOT_RUN\n\n'
         '20. 최종: RESEARCH_ONLY, PAPER/LIVE 차단, 저장/배포 미검증\n',encoding='utf-8')
    return {'case_id':case_id,'status':generated['status'],
            'functional_test_status':contract['functional_test_status'],
            'source':ev['url'],'generated_python_sha256':generated['code_sha256']}

def run(archive,source_id,out,catalog,source_dir=None,source_archive=None,evidence_dir=None,context_dir=None,
        extra_taxonomy=None,synthetic_bars=None,ai=False,crossref=False):
    if not ID_PATTERN.fullmatch(source_id):raise ValueError('unsafe ID')
    archive=pathlib.Path(archive);out=pathlib.Path(out)/source_id;out.mkdir(parents=True,exist_ok=True)
    discovery,manifest=load_discovery(archive,source_id)
    archive_sha=hashlib.sha256(archive.read_bytes()).hexdigest()
    source,code=verify_pine(source_id,source_dir,source_archive)
    semantics=analyze(code) if code is not None else None
    taxonomy=taxonomy_report(out,semantics is not None,load_taxonomy(catalog),extra_taxonomy)
    ctxfile=pathlib.Path(context_dir)/(source_id+'.json') if context_dir else None
    context=json.loads(ctxfile.read_text(encoding='utf-8')) if ctxfile and ctxfile.exists() else {}
    hints=discover_research_queries(discovery,context)
    hypotheses=StructuredResearchModel().propose(semantics,context,load_taxonomy(catalog)) if ai and semantics else {
        'status':'BLOCKED_SOURCE_MISSING_FOR_AI' if not semantics else 'AI_RESEARCH_NOT_REQUESTED', 'hypotheses':[]}
    if ai and not semantics:hypotheses['status']='BLOCKED_SOURCE_MISSING_FOR_AI'
    dump(out/'hypothesis_register.json',{'proposed_queries':hints,**hypotheses})
    searches=[]
    if crossref:
        for q in hints['queries']:searches.append(CrossrefSearch().search(q))
    if not searches:searches=[{'status':'SEARCH_NOT_EXECUTED','reason':'--crossref not enabled; external evidence fixture is manually checked'}]
    (out/'search_log.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in searches),encoding='utf-8')
    evidence_path=pathlib.Path(evidence_dir)/(source_id+'.json') if evidence_dir else None
    cases=[];origin_status='NO_VALID_EVIDENCE'
    if evidence_path and evidence_path.exists():
        ev=json.loads(evidence_path.read_text(encoding='utf-8'))
        if ev['source_id']!=source_id:raise ValueError('External evidence source mismatch')
        origin_status=ev['retrieval_method']
        for case in ev['cases']:
            cases.append(case_to_artifacts(case,source_id,out,synthetic_bars))
    dump(out/'evidence_index.json',{'status':origin_status,'automated_evidence_discovery':False,
                                    'source_versus_external_case':'SEPARATE','cases':cases})
    analysis={
       '01_original_identity':{'status':'DISCOVERY_FOUND' if discovery else 'DISCOVERY_NOT_FOUND','data':discovery,
                               'manifest_strategy_total':manifest['strategies']},
       '02_pine_functional_analysis':{'status':source['status'],'source':source,'static_analysis':semantics},
       '03_instruments':{'status':'CONTEXT_ONLY_NOT_CONTRACT_VERIFIED','context':context},
       '04_original_trade_rules':{'status':'STATIC_PARTIAL_ONLY' if semantics else 'BLOCKED_SOURCE_MISSING',
                                  'detected_orders':semantics['actual_strategy_orders_detected'] if semantics else None},
       '05_original_performance':{'status':'NOT_REPRODUCED'},
       '06_economic_provenance':{'status':'CONTEXT_RESEARCH_ONLY_NO_ORIGINAL_ECONOMIC_LINK_PROVEN'},
       '07_canonical_87':{'status':taxonomy['status'],'rows':87},
       '08_extra_12':{'status':taxonomy['extra_12_status']},
       '09_hypotheses':{'status':hypotheses['status'],'count':len(hypotheses.get('hypotheses',[]))},
       '10_external_research':{'status':searches[0]['status'],'manual_evidence_cases':len(cases)},
    }
    dump(out/'original_analysis.json',analysis)
    (out/'original_analysis.md').write_text('\n'.join(f'## {k}\n상태: {v["status"]}\n' for k,v in analysis.items()),encoding='utf-8')
    (out/'decision_log.md').write_text('## 판정\n원본과 외부 사례를 연결하는 범용 경제적 AI 연구 아직 미완성. '
        '사례 증거 수동 등록≠실검색 자동발굴. 합성·교육 예시≠실시세 백테스트. 87+12 정본 미완성.\n',encoding='utf-8')
    index={'source_id':source_id,'discovery_title':(discovery or {}).get('title'),'source_status':source['status'],
           'archive_sha256':archive_sha,'manifest_counts':{'strategies':manifest['strategies'],'indicators':manifest['indicators']},
           'taxonomy':taxonomy,'analysis_status':analysis['02_pine_functional_analysis']['status'],
           'ai_status':hypotheses['status'],'search_status':searches[0]['status'],
           'external_case_origin':origin_status,'external_cases':cases,
           'new_independent_strategy_count_auto_discovered':0,
           'real_backtest_status':'REAL_BACKTEST_NOT_RUN','ui_status':'NOT_DEPLOYED',
           'v3_acceptance':'NOT_PASSED','created_at_utc':datetime.now(timezone.utc).isoformat()}
    dump(out/'index.json',index)
    return index

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=pathlib.Path,required=True)
    parser.add_argument('--source-id',required=True)
    parser.add_argument('--out',type=pathlib.Path,default=HERE/'results')
    parser.add_argument('--catalog',type=pathlib.Path,default=HERE/'catalog'/'taxonomy_87.tsv')
    parser.add_argument('--source-dir',type=pathlib.Path)
    parser.add_argument('--source-archive',type=pathlib.Path)
    parser.add_argument('--evidence-dir',type=pathlib.Path)
    parser.add_argument('--context-dir',type=pathlib.Path)
    parser.add_argument('--extra-taxonomy',type=pathlib.Path)
    parser.add_argument('--synthetic-bars',type=pathlib.Path)
    parser.add_argument('--ai',action='store_true')
    parser.add_argument('--crossref',action='store_true')
    a=parser.parse_args()
    print(json.dumps(run(a.archive,a.source_id,a.out,a.catalog,a.source_dir,a.source_archive,
                         a.evidence_dir,a.context_dir,a.extra_taxonomy,a.synthetic_bars,a.ai,a.crossref),ensure_ascii=False,indent=2))
