"""v3 20-section truth-preserving report: source 01–10 and each case 11–20.

All detailed values are read from actual saved structured artifacts, not filled with invented
backtests. Marked gaps remain visible, rather than producing empty CSVs or phantom results.
"""
from __future__ import annotations
import json,pathlib,hashlib


def _read(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))


def build_case_report(root,source_id,case_id):
    root=pathlib.Path(root);d=root/source_id/'cases'/case_id
    source=_read(root/source_id/'original_analysis.json')
    t=_read(root/source_id/'hypothesis_register.json')
    e=_read(d/'evidence.json')
    manifest=_read(d/'execution_manifest.json')
    spec=_read(d/'strategy_spec.json') if (d/'strategy_spec.json').exists() else None
    functional=_read(d/'functional_result.json') if (d/'functional_result.json').exists() else None
    sha=source['01_original_identity']['verified_archive'].get('sha256')
    codesha=manifest.get('code_sha256')
    original_orders=source['04_original_trade_rules'].get('source_line_order_expressions',[])
    h=t.get('hypotheses',[])
    status='PYTHON_GENERATED_UNIT_FUNCTIONAL_EXECUTED_NOT_REAL_BACKTESTED' if functional else ('SOURCE_RULES_INSUFFICIENT' if spec is None else 'GENERATED_UNEXECUTED')
    result={
        '01_original_identity':{'strategy_id':source_id,'pine_sha256':sha,'original_code':'../../original.pine',
            'source_url':source['01_original_identity']['verified_archive'].get('source_url')},
        '02_original_pine_semantics':{'actual_order_call_count':len(original_orders),
            'actual_order_source_lines':[x['start_line'] for x in original_orders],
            'pinescript_parity':'NOT_TESTED','scope':'CALL_SITES_ONLY'},
        '03_instruments':{'original_instrument_context':source.get('03_instruments',{}),
            'independent_legs':spec.get('legs') if spec else None,
            'instrument_contract_validation':'NOT_VERIFIED_WITH_LIVE_EXCHANGE_AND_BROKER'},
        '04_original_trading_rules':{'original_order_sites':[{'line':x['start_line'],'callee':x['callee']} for x in original_orders],
            'case_rules_are_not_original_pine':'EXTERNAL_RESEARCH_SEPARATE'},
        '05_original_performance':{'status':'NOT_REPRODUCED','claimed_paper_or_example_returns_are_not_our_results':True},
        '06_economic_mechanism':{'candidate_hypotheses':h,'case_external_context':e.get('trade_description')},
        '07_taxonomy_87':{'file':'../../taxonomy_87x12.csv','rows':87,'status':'ROW_LEVEL_RESEARCH_LINKS_NOT_EXECUTION_PROOF'},
        '08_extra_12':{'status':'MISSING_CANONICAL_SOURCE','rows':0},
        '09_research_hypotheses':{'count':len(h),'falsification_conditions':[x['falsification_conditions'] for x in h]},
        '10_research_search_log':{'file':'../../search_log.jsonl',
            'programmatic_external_search':'NOT_EXECUTED',
            'manually_reviewed_reference':e.get('verified_status')},
        '11_independent_external_case':{'case_id':case_id, 'url':e.get('url'),
            'publisher':e.get('publisher'),'location':e.get('location'),
            'evidence_type':e.get('evidence_type'),'source_verification_state':e.get('verified_status')},
        '12_confirmed_vs_assumed':{'source_confirmed_rules':spec.get('source_confirmed_rules',[]) if spec else [],
            'research_assumptions':spec.get('research_assumptions',[]) if spec else [],
            'status':'SEPARATED' if spec else 'RULES_INSUFFICIENT'},
        '13_trade_structure':{'strategy_kind':spec['kind'] if spec else None,
            'legs':spec.get('legs') if spec else None,
            'tradeable_contracts_confirmed_by_broker':False},
        '14_executable_logic':{'implementation_kind':spec['kind'] if spec else None,
            'parameters':spec.get('parameters',{}) if spec else None,
            'code_file':'generated_strategy.py' if codesha else None,
            'fills_model':'RESEARCH_ASSUMPTION_NEXT_OBSERVED_OPEN' if spec and spec['kind']!='worked_transaction' else 'WORKED_SOURCE_PRICES_ONLY' if spec else None,
            'reentry_and_multileg_risks':'FULL_REAL_BROKER_EXECUTION_NOT_TESTED'},
        '15_risk_costs_pnl':{'gross_example':functional.get('gross_pnl') or functional.get('gross_pnl_usd') if functional else None,
            'worked_leg_details':functional.get('leg_results') if functional else None,
            'fixture_trades':functional.get('trades') if functional else None,
            'pnl_formula':'SUM[(exit_price-entry_price) * direction * quantity * multiplier] less actual costs',
            'costs_status':'UNKNOWN_UNLESS_EXPLICITLY_SPECIFIED',
            'financing_margin_market_impact':'NOT_VERIFIED',
            'net_pnl':None},
        '16_market_data':{'source_market_data_sha256':None, 'real_market_data':'MISSING',
            'only_synthetic_or_worked_source_example':bool(functional),
            'required_data':spec.get('data_required') if spec else None},
        '17_python_source':{'code_file':'generated_strategy.py' if codesha else None,
            'code_sha256':codesha,'spec_file':'strategy_spec.json' if spec else None,
            'source_map_file':'source_map.json' if spec else None,
            'generated_not_republished_to_git':True},
        '18_tests_and_equality':{'functional_test_status':manifest.get('functional_test_status'),
            'functional_test_type':manifest.get('functional_test_type'),
            'code_exit':manifest.get('exit_code'),'test_script':'tests/test_strategy.py' if codesha else None,
            'source_semantic_equivalence':'NOT_VERIFIED','market_backtest':'NOT_RUN'},
        '19_backtest_trades_charts':{'real_backtest':'REAL_BACKTEST_NOT_RUN',
            'real_trades_csv':'NOT_GENERATED','equity_csv':'NOT_GENERATED','chart_json':'NOT_GENERATED',
            'functional_fixture':'functional_result.json' if functional else None},
        '20_assessment':{'status':'RESEARCH_ONLY' if spec else 'RULE_EXTRACTION_INCOMPLETE',
            'validated_rule_trace':'EXTERNAL_CASE_NOT_ORIGINAL_PINE',
            'adopted_in_catalog':False,'PAPER':'NOT_ENABLED','LIVE':'BLOCKED','web_ui':'NOT_DEPLOYED',
            'v3_complete':False},
        'case_status':status
    }
    (d/'v3_20_sections.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    body=[f'# {case_id} — v3 20항목 전체 상세 근거',
          '', f'> 판정: **{status}**. 원본 Pine과 외부 다자산 거래는 별개입니다.',
          '', '산출물은 거래 권유나 검증된 실수익이 아닙니다.']
    for key,value in result.items():
        if key=='case_status':continue
        body.extend(['',f'## {key}',
                     '```json',json.dumps(value,ensure_ascii=False,indent=2),'```'])
    (d/'v3_20_sections.md').write_text('\n'.join(body)+'\n',encoding='utf-8')
    return result


def generate_source_case_reports(root,source_id):
    source_root=pathlib.Path(root)/source_id
    cases=source_root/'cases'
    done=[]
    if cases.exists():
        for d in sorted(cases.iterdir()):
            if d.is_dir() and (d/'evidence.json').exists():
                done.append((d.name,build_case_report(root,source_id,d.name)['case_status']))
    return done
