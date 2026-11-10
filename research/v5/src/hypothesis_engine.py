"""Auditable economic hypothesis suggestions from actual Pine evidence + user market context.

This rule-based fallback is NOT autonomous AI research. It returns an explicit
research status and falsifiable queries; external citations must still be found.
No source ID is hard-coded, so one code path handles unrelated Pine originals.
"""
from __future__ import annotations
import re

METAL_SYMBOLS={'XPT':'platinum','XAU':'gold','XPD':'palladium','XAG':'silver'}


def infer_hypotheses(source_id, source_analysis, context=None):
    context=context or {}
    if source_analysis is None or source_analysis.get('status')!='SOURCE_STATIC_ANALYSIS_EXECUTED_NOT_PINE_AST':
        return {'status':'BLOCKED_SOURCE_ANALYSIS_MISSING','hypotheses':[]}
    calls=source_analysis['calls']
    earning=[x for x in calls if x['callee']=='request.earnings']
    candidates=[]
    if earning:
        line=earning[0]['start_line']
        candidates.append({
            'hypothesis_id':f'H-{source_id}-EARNINGS-UNDERREACTION',
            'economic_actors':'공시된 실적발표에 반응하는 주식투자자, 유동성 공급자 및 롱숏 참가자',
            'economic_mechanism':'공개 실적서프라이즈가 가격에 즉시 완전히 반영되지 않는다면 다음 기간의 장단 종목 상대수익률 차이가 생길 수 있음',
            'instrument_legs':['실적서프라이즈 상위 분위 개별주식 매수','동일 기간·업종의 하위 분위 개별주식 공매도'],
            'mechanism_type':'STATISTICAL_EVENT_RELATIVE_VALUE_NOT_ARBITRAGE',
            'expected_relation':'사전 정의한 시점의 상위 실적서프라이즈 종목 수익률 - 하위 종목 수익률 > 거래비용',
            'source_trace':[{'source_id':source_id,'start_line':line,'feature':'request.earnings'}],
            'original_vs_new':'ORIGINAL_HAS_EARNINGS_REFERENCE; MULTISTOCK_MARKET_NEUTRAL_LEGS_NOT_PROVEN_IN_PINE',
            'taxonomy_candidates':[{'id':'S085','relationship':'HYPOTHESIS_RESEARCH_CONNECTION_NOT_ORIGINAL_IMPLEMENTATION'}],
            'required_data':['실적 발표의 원래 공개시각','표준화 예상외실적(SUE)','상장폐지 포함 시장 유니버스',
                             '종목별 분봉/일봉·Bid/Ask·공매도 가능성','업종/베타·공시 이후 시점 정합성'],
            'falsification_conditions':['비용·공매도 비용 반영 후 샘플 외 초과수익 <= 0',
                                        '실적서프라이즈 정보가 매매시점보다 늦게 공개됨','중립화 후 신호 소멸'],
            'search_queries':['post earnings announcement drift top bottom earnings surprise decile long short paper',
                              'standardized unexpected earnings market neutral post earnings announcement drift review'],
            'research_status':'RULE_BASED_HYPOTHESIS_UNVERIFIED',
        })
    symbol=str(context.get('chart_symbol') or '').upper()
    hints=[(k,v) for k,v in METAL_SYMBOLS.items() if k in symbol]
    if hints:
        code,metal=hints[0]
        peer='gold' if metal!='gold' else 'platinum'
        candidates.append({
            'hypothesis_id':f'H-{source_id}-METALS-RELATIVE-VALUE',
            'economic_actors':'귀금속 생산·산업 수요자, 선물 시장 헤저, 차익·상대가치 트레이더',
            'economic_mechanism':f'{metal}과 {peer}의 산업수요·안전자산 수요 및 공급 차이는 선물 상대가격 변화를 유발할 수 있음',
            'instrument_legs':[f'{metal} 선물 거래 레그',f'{peer} 선물 반대 레그'],
            'mechanism_type':'CROSS_COMMODITY_RISK_BASIS_NOT_RISK_FREE',
            'expected_relation':'정규화된 선물 차이의 방향/계절성/위험 보정 수익이 비용을 초과하는지 검증',
            'source_trace':[{'source_id':source_id,'market_context_key':'chart_symbol','value':symbol,
                             'source_evidence_level':'EXTERNAL_PROJECT_CONTEXT_NOT_PINE_ORDER'}],
            'original_vs_new':'EXTERNAL_RESEARCH_HYPOTHESIS; NO_MULTILEG_EXECUTION_PROVEN_IN_ORIGINAL',
            'taxonomy_candidates':[{'id':'S014','relationship':'NOT_SAME_ECONOMIC_STRUCTURE_NO_DIRECT_MATCH'}],
            'required_data':['두 선물 월물별 동일 시각 Bid/Ask','승수·통화·거래소 거래시간','롤·수수료·증거금·대차 가능성'],
            'falsification_conditions':['동시 체결가능 스프레드가 모든 비용 후 양의 기대값을 갖지 않음',
                                        '선물 만기·롤·계약규격 차이로 경제적 비교 무효'],
            'search_queries':[f'{metal} {peer} futures intermarket spread trading exchange example',
                              f'{metal} {peer} seasonal futures pair trading research rules'],
            'research_status':'RULE_BASED_HYPOTHESIS_UNVERIFIED',
        })
    return {'status':'RULE_BASED_HYPOTHESES_PROPOSED_NOT_AI_NOT_PROFIT_PROVEN' if candidates else 'NO_ECONOMIC_HYPOTHESIS_PROPOSED',
            'source_id':source_id,'hypotheses':candidates,
            'disclaimer':'Source evidence leads only to research questions; no source Pine multi-leg parity asserted.'}


def map_taxonomy_87(rows,analysis,hypotheses):
    """87 official rows always returned; do not hallucinate the extra 12."""
    evidence_by_id={}
    for h in hypotheses.get('hypotheses',[]):
        for link in h['taxonomy_candidates']:
            tid=link['id'];evidence_by_id.setdefault(tid,[]).append({'hypothesis_id':h['hypothesis_id'],
                'relationship':link['relationship'],'source_trace':h['source_trace']})
    return [{'taxonomy_id':tid,'name':name,
             'relationship':'RESEARCH_LINK_NOT_CONFIRMED_TRADE' if tid in evidence_by_id else 'NO_SOURCE_EVIDENCE_YET',
             'source_and_hypothesis_justification':evidence_by_id.get(tid,[]),
             'decision':'NOT_ADOPTED_PENDING_EXTERNAL_VERIFICATION'}
            for tid,name in rows]
