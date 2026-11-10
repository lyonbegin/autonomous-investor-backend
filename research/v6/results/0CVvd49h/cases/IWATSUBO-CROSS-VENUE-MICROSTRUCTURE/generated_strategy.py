# GENERATED RESEARCH-ONLY STRATEGY. NOT PAPER OR LIVE ENABLED.
import json
"""Research-only multi-leg futures strategy engines. All examples use explicitly synthetic inputs.
No exchange connectivity, no live orders, no claim of paper-author replication.
"""

from datetime import datetime, timezone
import math
import statistics

class ResearchError(ValueError):
    pass


def positive(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise ResearchError('Missing/invalid positive '+name)
    return float(v)


def nonnegative(v,name):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v < 0:
        raise ResearchError('Missing/invalid nonnegative '+name)
    return float(v)


def validate_advanced_spec(s):
    if s.get('kind') not in ('ols_cointegration_reversion','relative_value_rsi','cross_venue_platinum_quotes'):
        raise ResearchError('Unknown research strategy family')
    if not s.get('source_confirmed_rules') or not isinstance(s.get('source_confirmed_rules'),list):
        raise ResearchError('Must identify sourced economics')
    if not s.get('research_assumptions') or not isinstance(s.get('research_assumptions'),list):
        raise ResearchError('Missing researcher-authored parameter assumptions')
    if s.get('mode') != 'RESEARCH_ONLY' or s.get('live_orders_enabled') is not False:
        raise ResearchError('Only research mode can be generated')
    p=s.get('parameters',{})
    if s['kind'] in ('ols_cointegration_reversion','relative_value_rsi'):
        for key in ('qty_y','qty_x','multiplier_y','multiplier_x','max_hold_bars','roundtrip_fee_per_contract_usd','slippage_per_side_per_contract_usd'):
            if key in ('roundtrip_fee_per_contract_usd','slippage_per_side_per_contract_usd'):nonnegative(p.get(key),key)
            else:positive(p.get(key),key)
        for key in ('qty_y','qty_x','max_hold_bars'):
            if int(p[key])!=p[key]:raise ResearchError('Integer quantity/holding required: '+key)
        if p.get('timeframe')!='1d':raise ResearchError('Synthetic daily research only')
        if s['kind']=='ols_cointegration_reversion':
            for key in ('training_bars','band_bars'):positive(p.get(key),key)
            if p['training_bars']<8 or p['band_bars']<5:raise ResearchError('Too little training')
            for key in ('entry_z','exit_z','stop_z'):positive(p.get(key),key)
            if not (0<p['exit_z']<p['entry_z']<p['stop_z']):raise ResearchError('Threshold order')
            positive(p.get('max_hedge_mismatch_fraction'),'max_hedge_mismatch_fraction')
        else:
            positive(p.get('rsi_bars'),'rsi_bars')
            if int(p['rsi_bars'])!=p['rsi_bars']:raise ResearchError('RSI window must be integer')
            if not (0<p.get('oversold',0)<50<p.get('overbought',100)<100):raise ResearchError('RSI levels')
    else:
        for k in ('ny_contract_oz','jp_contract_grams','ny_qty','jp_qty','fx_grams_per_troy_oz','estimated_roundtrip_fees_jpy','min_net_edge_jpy','max_venue_lag_seconds','max_hold_snapshots','max_weight_mismatch_fraction'):
            if k in ('estimated_roundtrip_fees_jpy','min_net_edge_jpy'):nonnegative(p.get(k),k)
            else:positive(p.get(k),k)
        for k in ('ny_qty','jp_qty','max_hold_snapshots'):
            if int(p[k])!=p[k]:raise ResearchError('Non-integer contracts')
        mismatch=abs(p['ny_contract_oz']*p['ny_qty']*p['fx_grams_per_troy_oz'] - p['jp_contract_grams']*p['jp_qty'])/(p['ny_contract_oz']*p['ny_qty']*p['fx_grams_per_troy_oz'])
        if mismatch>p['max_weight_mismatch_fraction']:raise ResearchError('Unhedged metal exposure too large')
    return True


def _sorted_bars(rows,syms):
    if not isinstance(rows,list) or len(rows)<4:raise ResearchError('Insufficient bars')
    times=[]
    for i,r in enumerate(rows):
        t=datetime.fromisoformat(r['timestamp'].replace('Z','+00:00'))
        if t.tzinfo is None:raise ResearchError('Timestamp must include timezone')
        times.append(t)
        for field in ('open','close'):
            for sym in syms:positive(r.get(field,{}).get(sym),f'{i}:{field}:{sym}')
    if times!=sorted(set(times)):raise ResearchError('Unsorted/duplicate timestamp')
    return times


def _leg_pnl(entry,exit,direction,s):
    p=s['parameters']
    gross=(exit['y']-entry['y'])*direction*p['qty_y']*p['multiplier_y'] - (exit['x']-entry['x'])*direction*p['qty_x']*p['multiplier_x']
    fee=2*p['roundtrip_fee_per_contract_usd']*(p['qty_y']+p['qty_x'])/2
    # fee is configured per contract round trip; separate per-side slippage
    slip=2*p['slippage_per_side_per_contract_usd']*(p['qty_y']+p['qty_x'])
    return round(gross,8),round(gross-fee-slip,8),round(fee+slip,8)


def _std(vals):
    if len(vals)<2:return 0.0
    return statistics.stdev(vals)


def _ohlc_execution(kind, spec, rows, decision):
    p=spec['parameters']; _sorted_bars(rows,['PL','HG'] if kind=='ols_cointegration_reversion' else ['PL','GC'])
    syms=('PL','HG') if kind=='ols_cointegration_reversion' else ('PL','GC')
    open_pos=None;trades=[];events=[]
    for i in range(len(rows)-1):
        signal=decision(i, rows)
        if open_pos is None:
            if signal['action'] not in ('ENTER_LONG_SPREAD','ENTER_SHORT_SPREAD'):continue
            direction=1 if signal['action']=='ENTER_LONG_SPREAD' else -1
            opening=rows[i+1]
            open_pos={'direction':direction,'index':i+1,'entry_timestamp':opening['timestamp'],'entry':{'y':opening['open'][syms[0]],'x':opening['open'][syms[1]]},'entry_signal':signal}
            events.append({'signal_time':rows[i]['timestamp'],'fill_time':opening['timestamp'],'action':signal['action'],'reason':signal.get('reason')})
        else:
            holding=i-open_pos['index']+1
            if signal['action']=='EXIT' or holding>=p['max_hold_bars']:
                closing=rows[i+1]
                exit_price={'y':closing['open'][syms[0]],'x':closing['open'][syms[1]]}
                gross,net,costs=_leg_pnl(open_pos['entry'],exit_price,open_pos['direction'],spec)
                legs=[{'symbol':syms[0],'side':'BUY' if open_pos['direction']==1 else 'SELL','contracts':p['qty_y'],'multiplier':p['multiplier_y']},
                      {'symbol':syms[1],'side':'SELL' if open_pos['direction']==1 else 'BUY','contracts':p['qty_x'],'multiplier':p['multiplier_x']}]
                trades.append({'entry_timestamp':open_pos['entry_timestamp'],'exit_timestamp':closing['timestamp'],'signal_timestamp':rows[i]['timestamp'],'legs':legs,'entry_prices':open_pos['entry'],'exit_prices':exit_price,'gross_pnl_usd':gross,'modeled_costs_usd':costs,'modeled_net_pnl_usd':net,'exit_reason':signal.get('reason') if signal['action']=='EXIT' else 'MAX_HOLD_BARS'})
                events.append({'signal_time':rows[i]['timestamp'],'fill_time':closing['timestamp'],'action':'EXIT','reason':trades[-1]['exit_reason']})
                open_pos=None
    return {'status':'SYNTHETIC_FUNCTIONAL_TEST_ONLY','family':kind,'trades':trades,'events':events,
            'open_position_at_end':open_pos is not None,'closed_trade_count':len(trades),
            'gross_pnl_usd':round(sum(t['gross_pnl_usd'] for t in trades),8),
            'modeled_net_pnl_usd':round(sum(t['modeled_net_pnl_usd'] for t in trades),8),
            'market_backtest':'REAL_BACKTEST_NOT_RUN','claim_replicates_paper':False}


def ols_reversion(spec,rows):
    validate_advanced_spec(spec);p=spec['parameters']
    n=int(p['training_bars']);w=int(p['band_bars']);_sorted_bars(rows,['PL','HG'])
    if len(rows)<n+w+3:raise ResearchError('Insufficient train+trade bars')
    xs=[float(r['close']['HG']) for r in rows[:n]];ys=[float(r['close']['PL']) for r in rows[:n]]
    xbar=statistics.mean(xs);ybar=statistics.mean(ys)
    denom=sum((x-xbar)**2 for x in xs)
    if denom<1e-10:raise ResearchError('Constant training hedge instrument')
    beta=sum((x-xbar)*(y-ybar) for x,y in zip(xs,ys))/denom
    if beta<=0:raise ResearchError('No positive beta estimated; candidate rejected')
    alpha=ybar-beta*xbar
    exposure_y=p['qty_y']*p['multiplier_y']*beta
    exposure_x=p['qty_x']*p['multiplier_x']
    mismatch=abs(exposure_y-exposure_x)/max(exposure_y,exposure_x)
    if mismatch>p['max_hedge_mismatch_fraction']:
        return {'status':'CANDIDATE_REJECTED_HEDGE_MISMATCH','hedge_beta':beta,'mismatch_fraction':mismatch,'trades':[],'market_backtest':'REAL_BACKTEST_NOT_RUN'}
    residual=[float(r['close']['PL'])-(alpha+beta*float(r['close']['HG'])) for r in rows]
    def decision(i,_):
        if i<n+w:return {'action':'HOLD'}
        old=residual[i-w:i]  # never include current signal close in reference band
        sd=_std(old)
        if sd<1e-9:return {'action':'HOLD'}
        z=(residual[i]-statistics.mean(old))/sd
        if abs(z)>=p['stop_z'] and i>n+w+1:return {'action':'EXIT','reason':'Z_STRESS_STOP'}
        if abs(z)<=p['exit_z']:return {'action':'EXIT','reason':'MEAN_REVERSION'}
        if z>=p['entry_z']:return {'action':'ENTER_SHORT_SPREAD','reason':'UPPER_15DAY_BAND'}
        if z<=-p['entry_z']:return {'action':'ENTER_LONG_SPREAD','reason':'LOWER_15DAY_BAND'}
        return {'action':'HOLD'}
    result=_ohlc_execution('ols_cointegration_reversion',spec,rows,decision)
    result.update({'hedge_beta_ols':round(beta,6),'hedge_intercept':round(alpha,6),'weight_mismatch_fraction':round(mismatch,6),
                   'academic_method_gap':'OLS proxy only: no SVM/ECM/Engle-Granger significance confirmation'})
    return result


def _rsi(seq,period):
    dif=[seq[j]-seq[j-1] for j in range(len(seq)-period,len(seq))]
    gains=sum(max(d,0) for d in dif)/period
    losses=sum(max(-d,0) for d in dif)/period
    if gains==0 and losses==0:return 50.
    if losses==0:return 100.
    return 100-100/(1+gains/losses)


def rsi_relative_value(spec,rows):
    validate_advanced_spec(spec);p=spec['parameters'];_sorted_bars(rows,['PL','GC'])
    win=int(p['rsi_bars'])
    spread=[float(r['close']['PL'])-float(r['close']['GC']) for r in rows]
    def decision(i,_):
        if i<win:return {'action':'HOLD'}
        value=_rsi(spread[:i+1],win)
        if p['oversold']<value<p['overbought'] and abs(value-50.)<=p.get('exit_midpoint_band',5):
            return {'action':'EXIT','reason':'RSI_MIDPOINT'}
        if value<=p['oversold']:return {'action':'ENTER_LONG_SPREAD','reason':'RSI_OVERSOLD'}
        if value>=p['overbought']:return {'action':'ENTER_SHORT_SPREAD','reason':'RSI_OVERBOUGHT'}
        return {'action':'HOLD'}
    result=_ohlc_execution('relative_value_rsi',spec,rows,decision)
    result.update({'spread_definition':'PL quote USD/oz minus GC quote USD/oz, 2 PL vs 1 GC matched ounce amount',
                   'academic_method_gap':'RSI(14)/30/70 are author research assumptions, not published RSI2 parameters'})
    return result


def _dt(x):
    d=datetime.fromisoformat(x.replace('Z','+00:00'))
    if d.tzinfo is None:raise ResearchError('Missing timezone')
    return d


def _quote(row,spec):
    p=spec['parameters']; now=_dt(row['timestamp'])
    for src in ('ny_observed_at','jp_observed_at','fx_observed_at'):
        lag=(now-_dt(row[src])).total_seconds()
        if not 0<=lag<=p['max_venue_lag_seconds']:raise ResearchError('Stale or future quote '+src)
    if not row.get('sessions_overlap'):raise ResearchError('Non-overlapping venues')
    if row.get('ny_contract_month')!=row.get('jp_contract_month'):raise ResearchError('Mismatched futures expiries')
    for k in ('ny_bid_usd_per_oz','ny_ask_usd_per_oz','jp_bid_jpy_per_g','jp_ask_jpy_per_g','fx_forward_bid_jpy_per_usd','fx_forward_ask_jpy_per_usd'):
        positive(row.get(k),k)
    if row['ny_bid_usd_per_oz']>row['ny_ask_usd_per_oz'] or row['jp_bid_jpy_per_g']>row['jp_ask_jpy_per_g'] or row['fx_forward_bid_jpy_per_usd']>row['fx_forward_ask_jpy_per_usd']:
        raise ResearchError('Crossed bid/ask')
    return row


def _theoretical_cash(row,spec,direction,opening):
    p=spec['parameters'];n=p['ny_qty']*p['ny_contract_oz'];j=p['jp_qty']*p['jp_contract_grams']
    if direction=='BUY_NY_SELL_JP':
        return j*row['jp_bid_jpy_per_g'] - n*row['ny_ask_usd_per_oz']*row['fx_forward_ask_jpy_per_usd'] if opening else n*row['ny_bid_usd_per_oz']*row['fx_forward_bid_jpy_per_usd']-j*row['jp_ask_jpy_per_g']
    return n*row['ny_bid_usd_per_oz']*row['fx_forward_bid_jpy_per_usd']-j*row['jp_ask_jpy_per_g'] if opening else j*row['jp_bid_jpy_per_g']-n*row['ny_ask_usd_per_oz']*row['fx_forward_ask_jpy_per_usd']


def cross_venue_quotes(spec,quotes):
    validate_advanced_spec(spec);p=spec['parameters']
    if not isinstance(quotes,list) or len(quotes)<2:raise ResearchError('Need multiple quote snapshots')
    times=[_dt(q['timestamp']) for q in quotes]
    if times!=sorted(set(times)):raise ResearchError('Nonmonotone quote timestamps')
    state=None;trades=[];events=[]
    for ix,q in enumerate(quotes):
        try: _quote(q,spec)
        except ResearchError as e:
            events.append({'timestamp':q.get('timestamp'),'status':'NO_SIGNAL_BAD_QUOTES','reason':str(e)});continue
        first=_theoretical_cash(q,spec,'BUY_NY_SELL_JP',True)
        second=_theoretical_cash(q,spec,'SELL_NY_BUY_JP',True)
        best=max(first,second)
        direction='BUY_NY_SELL_JP' if first>=second else 'SELL_NY_BUY_JP'
        net_entry=best-p['estimated_roundtrip_fees_jpy']
        if state is None:
            if net_entry>=p['min_net_edge_jpy']:
                state={'direction':direction,'entry_index':ix,'entry_time':q['timestamp'],'entry_cashflow_jpy':best}
                events.append({'timestamp':q['timestamp'],'action':'SIGNAL_ONLY_OPEN_RESEARCH','direction':direction,'edge_after_assumed_cost_jpy':round(net_entry,4)})
        else:
            duration=ix-state['entry_index']
            # Exit on compression of available reverse-side edge, or maximum snapshot duration.
            if best<=p['min_net_edge_jpy'] or duration>=p['max_hold_snapshots']:
                cashout=_theoretical_cash(q,spec,state['direction'],False)
                gross=state['entry_cashflow_jpy']+cashout
                net=gross-p['estimated_roundtrip_fees_jpy']
                trades.append({'entry_timestamp':state['entry_time'],'exit_timestamp':q['timestamp'],'direction':state['direction'],
                               'entry_cashflow_jpy':round(state['entry_cashflow_jpy'],4),'exit_cashflow_jpy':round(cashout,4),
                               'gross_quote_replay_pnl_jpy':round(gross,4),'modeled_net_quote_replay_pnl_jpy':round(net,4),
                               'execution_state':'UNEXECUTED_SYNTHETIC_QUOTE_REPLAY',
                               'qualification':'Not locked arbitrage: mismatched metal mass, forward settlement and leg-risk not fully modeled'})
                events.append({'timestamp':q['timestamp'],'action':'SIGNAL_ONLY_CLOSE_RESEARCH'})
                state=None
    return {'status':'SYNTHETIC_QUOTE_REPLAY_ONLY','trades':trades,'events':events,'open_position_at_end':state is not None,
            'closed_trade_count':len(trades),'modeled_net_quote_replay_pnl_jpy':round(sum(x['modeled_net_quote_replay_pnl_jpy'] for x in trades),4),
            'market_backtest':'REAL_BACKTEST_NOT_RUN','paper_execution':False,'live_orders_enabled':False,
            'risk_warnings':['Forward quote conversion is research proxy; actual FX hedge/settlement, lot transfer, borrow, margins and simultaneous fills unverified',
                             '1 NY(50oz) vs 3 Tokyo(500g) leaves residual metal exposure; not riskless arbitrage']}


def run_advanced(spec, data):
    if spec['kind']=='ols_cointegration_reversion':return ols_reversion(spec,data)
    if spec['kind']=='relative_value_rsi':return rsi_relative_value(spec,data)
    if spec['kind']=='cross_venue_platinum_quotes':return cross_venue_quotes(spec,data)
    raise ResearchError('Unsupported advanced strategy')

SPEC = json.loads('{"case_id": "IWATSUBO-CROSS-VENUE-MICROSTRUCTURE", "classification": {"new_taxonomy_proposal": "CROSS-VENUE-PLATINUM-FX-QUOTES", "status": "S014_RELATIONSHIP_NOT_SAME_ECONOMIC_STRUCTURE", "taxonomy_candidates": ["S014", "S006", "S012"]}, "hypothesis": "At overlapping sessions the executable two-way platinum prices can deviate enough to cover known FX/spread/fees; real transfer and hedging risks remain.", "instrument_info": {"FX": {"currency": "JPY per USD", "pair": "USD/JPY forward"}, "JP": {"currency": "JPY", "size": "500 g official contract, access unverified", "venue": "JPX/OSE Platinum Standard (historical TOCOM successor)"}, "NY": {"currency": "USD", "size": "50 troy oz", "venue": "NYMEX"}}, "kind": "cross_venue_platinum_quotes", "live_orders_enabled": false, "mode": "RESEARCH_ONLY", "parameters": {"estimated_roundtrip_fees_jpy": 8000, "fx_grams_per_troy_oz": 31.1034768, "jp_contract_grams": 500, "jp_qty": 3, "max_hold_snapshots": 3, "max_venue_lag_seconds": 3, "max_weight_mismatch_fraction": 0.05, "min_net_edge_jpy": 10000, "ny_contract_oz": 50, "ny_qty": 1}, "research_assumptions": [{"field": "contract_sizes", "value": "NY 50 troy oz against Tokyo 3 × 500 g", "why": "Lot approximation; historical/current venue specs must be checked, residual exposure exists"}, {"field": "fx", "value": "Forward bid/ask for synthetic quote replay", "why": "No actual forward contract hedge, cash flows proxy; not locked FX arbitrage"}, {"field": "entry_net_edge", "value": 10000, "why": "Net of illustrative 8000 JPY roundtrip fees, research threshold"}, {"field": "exit", "value": "Net entry edge compression or 3 snapshots", "why": "Developed exit rule; paper does not prescribe"}, {"field": "quote_max_age", "value": 3, "why": "Research quality gate; not paper executable policy"}], "source_confirmed_rules": [{"classification": "PAPER_FORMULA", "location": "Section 3, Equation (1) PROF", "rule": "The study defines two directions of platinum NYMEX–TOCOM quote arbitrage using NY/TO bid–ask and USD/JPY forward rate"}, {"classification": "PAPER_SCOPE", "location": "Abstract, Section 1, Section 3", "rule": "Study analyzes the connection of possible arbitrage opportunity to liquidity, not a guaranteed net-profit execution recipe"}], "source_evidence_url": "https://www.mdpi.com/1911-8074/15/12/593", "source_id": "0CVvd49h", "title": "NYMEX-Tokyo platinum dual-venue synchronized forward-FX adjusted executable quote spread scanner"}')

def run(data):
    return run_advanced(SPEC,data)
if __name__=='__main__':
    import sys
    if len(sys.argv)!=2: raise SystemExit('Usage: python generated_strategy.py input.json')
    with open(sys.argv[1],encoding='utf-8') as f: rows=json.load(f)
    print(json.dumps(run(rows),indent=2,ensure_ascii=False))
