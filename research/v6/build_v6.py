from __future__ import annotations
import sys, json, math, datetime, csv, hashlib, importlib.util, copy
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'src'))
from strategy_factory_v6 import generate_advanced

SPECS = {
 'BAEK-2020-HG-PL-RESEARCH': {
  'source_id':'0CVvd49h','case_id':'BAEK-2020-HG-PL-RESEARCH',
  'kind':'ols_cointegration_reversion','mode':'RESEARCH_ONLY','live_orders_enabled':False,
  'title':'HG-PL 15-day rolling spread: OLS pilot adapting Baek ECM/SVR methodology',
  'source_evidence_url':'https://www.mdpi.com/2071-1050/12/17/6791',
  'source_confirmed_rules':[
   {'rule':'Study selects pairs and tests cointegration using Engle-Granger/ECM; SVR hedge ratio','location':'Section 2.4, Systemic Trading Architecture and Trading Strategy and Hedge Ratio from SVM','classification':'PAPER_METHOD'},
   {'rule':'Signals at deviation beyond a 15-day moving average with standard-deviation band; pairs opened simultaneously, exited on reverting to mean','location':'Section 2.4, Strategy and Hedge Ratio from SVM','classification':'PAPER_METHOD'}],
  'research_assumptions':[
    {'field':'underlyings','value':'HG + PL','why':'Illustrative metal futures pairing. Specific HG-PL pair is not claimed as a tested study pair'},
    {'field':'hedge_method','value':'training-only OLS','why':'Stdlib proxy for SVM regression / ECM; not equivalently cointegration-tested'},
    {'field':'entry_z','value':1.5,'why':'Developer threshold; paper text supports band but not this numeric multiple'},
    {'field':'exit_z','value':0.35,'why':'Quantified mean-reversion exit threshold supplied by developer'},
    {'field':'stop_z','value':5.,'why':'Capital/risk research assumption'},
    {'field':'execution','value':'next daily bar open; fixed contract sizes; explicit assumed fees','why':'Not asserted as source instructions'}],
  'instrument_info':{'PL':{'venue':'NYMEX','multiplier_oz':50,'price_unit':'USD per troy oz'},'HG':{'venue':'COMEX','multiplier_lb':25000,'price_unit':'USD per lb'}},
  'parameters':{'timeframe':'1d','training_bars':40,'band_bars':15,'entry_z':1.5,'exit_z':0.35,'stop_z':5.0,'max_hold_bars':7,
                'qty_y':2,'qty_x':1,'multiplier_y':50,'multiplier_x':25000,
                'max_hedge_mismatch_fraction':0.35,'roundtrip_fee_per_contract_usd':8,'slippage_per_side_per_contract_usd':2},
  'classification':{'taxonomy_candidates':['S045','S028'],'new_taxonomy_proposal':'METALS-HG-PL-COINT-REVERSION','status':'RESEARCH_ANALOGY_NOT_VERIFIED_MAPPED'},
  'hypothesis':'Deviation of dynamically estimated HG/PL price relationship may mean revert after common metal-market shocks; not guaranteed.'
 },
 'PSARADELLIS-PL-GC-RULES-RESEARCH': {
  'source_id':'0CVvd49h','case_id':'PSARADELLIS-PL-GC-RULES-RESEARCH',
  'kind':'relative_value_rsi','mode':'RESEARCH_ONLY','live_orders_enabled':False,
  'title':'Platinum-Gold ounce-neutral RSI spread mean-reversion research rule',
  'source_evidence_url':'https://research-portal.st-andrews.ac.uk/en/publications/technical-analysis-spread-trading-and-data-snooping-control/',
  'source_confirmed_rules':[
   {'rule':'Paper evaluates thousands of technical trading rules on daily spread pairs and controls data snooping','location':'Methods / Introduction; manuscript pp. 1-7','classification':'PAPER_METHOD'},
   {'rule':'Platinum-gold spread listed, with RSI2 as best rule label in study Table 2','location':'Accepted manuscript Table 2, appendix p.39','classification':'PAPER_CLASSIFICATION'},
   {'rule':'2 platinum contracts against 1 gold contract for equal underlying ounces','location':'Accepted manuscript footnote 6, p.7','classification':'PAPER_CONTRACT_NORMALIZATION'}],
  'research_assumptions':[
   {'field':'rsi_bars','value':14,'why':'RSI2 is paper rule ID, not confirmed 2-period RSI; research chooses 14'},
   {'field':'oversold/overbought','value':[35,65],'why':'Independently designed thresholds; not paper-validated optimum'},
   {'field':'exit_midpoint_band','value':7,'why':'Developer-chosen mean reversion exit'},
   {'field':'execution','value':'next daily open; max 7 bars, assumed fees/slippage','why':'Simulator design, no paper strategy replication'}],
  'instrument_info':{'PL':{'venue':'NYMEX','multiplier_oz':50,'price_unit':'USD per oz'},'GC':{'venue':'COMEX','multiplier_oz':100,'price_unit':'USD per oz'}},
  'parameters':{'timeframe':'1d','rsi_bars':14,'oversold':35,'overbought':65,'exit_midpoint_band':7,'max_hold_bars':7,
                'qty_y':2,'qty_x':1,'multiplier_y':50,'multiplier_x':100,
                'roundtrip_fee_per_contract_usd':8,'slippage_per_side_per_contract_usd':2},
  'classification':{'taxonomy_candidates':['S028','S045'],'new_taxonomy_proposal':'METALS-PL-GC-RSI-SPREAD','status':'RESEARCH_ANALOGY_NOT_VERIFIED_MAPPED'},
  'hypothesis':'Platinum-gold price divergence may revert; RSI extremes of the ounce-normalized spread are a testable indicator, with FDR/walk-forward checks required.'
 },
 'IWATSUBO-CROSS-VENUE-MICROSTRUCTURE': {
  'source_id':'0CVvd49h','case_id':'IWATSUBO-CROSS-VENUE-MICROSTRUCTURE',
  'kind':'cross_venue_platinum_quotes','mode':'RESEARCH_ONLY','live_orders_enabled':False,
  'title':'NYMEX-Tokyo platinum dual-venue synchronized forward-FX adjusted executable quote spread scanner',
  'source_evidence_url':'https://www.mdpi.com/1911-8074/15/12/593',
  'source_confirmed_rules':[
   {'rule':'The study defines two directions of platinum NYMEX–TOCOM quote arbitrage using NY/TO bid–ask and USD/JPY forward rate','location':'Section 3, Equation (1) PROF','classification':'PAPER_FORMULA'},
   {'rule':'Study analyzes the connection of possible arbitrage opportunity to liquidity, not a guaranteed net-profit execution recipe','location':'Abstract, Section 1, Section 3','classification':'PAPER_SCOPE'}],
  'research_assumptions':[
   {'field':'contract_sizes','value':'NY 50 troy oz against Tokyo 3 × 500 g','why':'Lot approximation; historical/current venue specs must be checked, residual exposure exists'},
   {'field':'fx','value':'Forward bid/ask for synthetic quote replay','why':'No actual forward contract hedge, cash flows proxy; not locked FX arbitrage'},
   {'field':'entry_net_edge','value':10000,'why':'Net of illustrative 8000 JPY roundtrip fees, research threshold'},
   {'field':'exit','value':'Net entry edge compression or 3 snapshots','why':'Developed exit rule; paper does not prescribe'},
   {'field':'quote_max_age','value':3,'why':'Research quality gate; not paper executable policy'}],
  'instrument_info':{'NY':{'venue':'NYMEX','size':'50 troy oz','currency':'USD'},'JP':{'venue':'JPX/OSE Platinum Standard (historical TOCOM successor)','size':'500 g official contract, access unverified','currency':'JPY'},'FX':{'pair':'USD/JPY forward','currency':'JPY per USD'}},
  'parameters':{'ny_contract_oz':50,'jp_contract_grams':500,'ny_qty':1,'jp_qty':3,
                'fx_grams_per_troy_oz':31.1034768,'estimated_roundtrip_fees_jpy':8000,
                'min_net_edge_jpy':10000,'max_venue_lag_seconds':3,'max_hold_snapshots':3,
                'max_weight_mismatch_fraction':0.05},
  'classification':{'taxonomy_candidates':['S014','S006','S012'],'new_taxonomy_proposal':'CROSS-VENUE-PLATINUM-FX-QUOTES','status':'S014_RELATIONSHIP_NOT_SAME_ECONOMIC_STRUCTURE'},
  'hypothesis':'At overlapping sessions the executable two-way platinum prices can deviate enough to cover known FX/spread/fees; real transfer and hedging risks remain.'
 }
}

def synthetic_bars(n=120):
    start=datetime.datetime(2026,1,1,tzinfo=datetime.timezone.utc)
    rows=[]
    for i in range(n):
        # Decoupled spikes only in synthetic exercise region; no prices are real market observations
        hg=4.0+0.045*math.sin(i/5.8)+0.0025*i
        residual=3.0*math.sin(i/4.5)+1.5*math.cos(i/8)
        if i in (66,67,84,85,101):residual+=7.0 if i in (66,67,101) else -7.0
        pl=250*hg+50+residual
        gc=pl+185+10*math.sin(i/5.3)+4*math.cos(i/2.7)
        rows.append({'timestamp':(start+datetime.timedelta(days=i)).isoformat(),
                     'open':{'HG':round(hg+.003,5),'PL':round(pl+.5,5),'GC':round(gc-.25,5)},
                     'close':{'HG':round(hg,5),'PL':round(pl,5),'GC':round(gc,5)}})
    return rows

def synthetic_quotes():
    base=datetime.datetime(2026,2,2,8,0,0,tzinfo=datetime.timezone.utc)
    jps=[(5060,5070),(5050,5060),(5010,5020),(4997,5005),(5000,5010)]
    out=[]
    for i,(bid,ask) in enumerate(jps):
        now=base+datetime.timedelta(seconds=20*i)
        obs=(now-datetime.timedelta(seconds=0.5)).isoformat()
        out.append({'timestamp':now.isoformat(),'ny_observed_at':obs,'jp_observed_at':obs,'fx_observed_at':obs,
                    'ny_contract_month':'2026-04','jp_contract_month':'2026-04','sessions_overlap':True,
                    'ny_bid_usd_per_oz':999.,'ny_ask_usd_per_oz':1000.,'jp_bid_jpy_per_g':bid,'jp_ask_jpy_per_g':ask,
                    'fx_forward_bid_jpy_per_usd':149.95,'fx_forward_ask_jpy_per_usd':150.05})
    return out


def dump(obj,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')


def main():
    from advanced_runtime import run_advanced
    bars=synthetic_bars(); quotes=synthetic_quotes()
    dump(bars,root/'fixtures'/'synthetic_daily_bars.json')
    dump(quotes,root/'fixtures'/'synthetic_quote_snapshots.json')
    all_results={}
    for case_id,spec in SPECS.items():
        specpath=root/'specs'/f'{case_id}.json';dump(spec,specpath)
        out=root/'results'/case_id
        out.mkdir(exist_ok=True,parents=True)
        dump(spec,out/'strategy_spec.json')
        code=generate_advanced(spec,out/'generated_strategy.py')
        input_data=quotes if spec['kind']=='cross_venue_platinum_quotes' else bars
        ret=run_advanced(spec,input_data)
        dump(ret,out/'synthetic_functional_result.json')
        dump({'case_id':case_id,'source_id':'0CVvd49h','source_paper_url':spec['source_evidence_url'],
              'source_confirmed_rules':spec['source_confirmed_rules'],'developer_assumptions':spec['research_assumptions'],
              'generated_code':code,'mode':'RESEARCH_ONLY','source_claim':'NOT_PAPER_REPLICATION',
              'real_backtest':'REAL_BACKTEST_NOT_RUN','fixture_name':'synthetic_quote_snapshots.json' if spec['kind']=='cross_venue_platinum_quotes' else 'synthetic_daily_bars.json',
              'fixture_sha256':hashlib.sha256(json.dumps(input_data,sort_keys=True).encode()).hexdigest(),
              'requirements':['Python 3.10+ stdlib'],'live_orders_enabled':False},out/'execution_manifest.json')
        all_results[case_id]={'result':ret['status'],'trades':ret.get('closed_trade_count'),'code_sha256':code['code_sha256']}
    dump(all_results,root/'run_summary.json')
    print(json.dumps(all_results,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
