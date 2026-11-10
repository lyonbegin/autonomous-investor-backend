"""Stdlib-only leg P&L and synthetic seasonal execution; not a live trading adapter."""
from __future__ import annotations
from datetime import date
import math

class InvalidSpec(ValueError): pass

def validate_spec(spec):
    if spec.get('kind') not in {'worked_transaction','seasonal_futures_spread','earnings_decile_long_short'}:
        raise InvalidSpec('Unsupported strategy kind')
    if not isinstance(spec.get('source_confirmed_rules'),list) or not spec['source_confirmed_rules']:
        raise InvalidSpec('source_confirmed_rules must be non-empty and traceable')
    if not isinstance(spec.get('research_assumptions'),list):
        raise InvalidSpec('research_assumptions must be explicit')
    if spec['kind']=='earnings_decile_long_short':
        params=spec.get('parameters',{})
        for key in ('notional_per_leg_usd','hold_bars','decile_fraction'):
            val=params.get(key)
            if isinstance(val,bool) or not isinstance(val,(float,int)) or val<=0 or not math.isfinite(val):
                raise InvalidSpec('Invalid event parameter: '+key)
        if params['hold_bars']!=int(params['hold_bars']):raise InvalidSpec('hold_bars must be integer')
        if not 0<params['decile_fraction']<=0.2:raise InvalidSpec('decile_fraction out of accepted research range')
        if not spec.get('source_evidence_url'):raise InvalidSpec('Missing external research source')
        return True
    legs=spec.get('legs')
    if not isinstance(legs,list) or len(legs)<2: raise InvalidSpec('At least two independent legs required')
    names=set()
    for leg in legs:
        if leg.get('symbol') in names:raise InvalidSpec('Duplicate leg symbol')
        names.add(leg.get('symbol'))
        if leg.get('side') not in ('BUY','SELL'):raise InvalidSpec('Invalid leg side')
        for field in ('quantity','multiplier'):
            v=leg.get(field)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or v<=0 or not math.isfinite(v):raise InvalidSpec('Invalid '+field)
        if int(leg['quantity'])!=leg['quantity']:raise InvalidSpec('Futures contracts must be integer quantities')
        if not leg.get('venue') or not leg.get('contract_month'):raise InvalidSpec('Venue/contract_month required')
    if spec['kind']=='seasonal_futures_spread':
        for k in ('entry_after','exit_after'):
            try: date.fromisoformat('2024-'+spec['parameters'][k])
            except (ValueError,TypeError,KeyError) as e:raise InvalidSpec('Invalid '+k) from e
    if spec['kind']=='worked_transaction':
        for leg in legs:
            for k in ('entry_price','exit_price'):
                v=leg.get(k)
                if isinstance(v,bool) or not isinstance(v,(float,int)) or v<=0 or not math.isfinite(v):raise InvalidSpec('Missing positive worked price '+k)
    return True

def leg_pnl(leg,entry_price,exit_price):
    direction=1 if leg['side']=='BUY' else -1
    return direction*int(leg['quantity'])*float(leg['multiplier'])*(float(exit_price)-float(entry_price))

def worked_transaction(spec):
    validate_spec(spec)
    if spec['kind']!='worked_transaction':raise InvalidSpec('Wrong spec kind')
    items=[{'symbol':leg['symbol'],'gross_pnl':round(leg_pnl(leg,leg['entry_price'],leg['exit_price']),8)} for leg in spec['legs']]
    gross=round(sum(x['gross_pnl'] for x in items),8)
    return {'status':'SOURCE_WORKED_EXAMPLE_ONLY','leg_results':items,'gross_pnl':gross,
            'net_pnl':None,'cost_status':'NOT_ESTABLISHED',
            'real_backtest_status':'REAL_BACKTEST_NOT_RUN'}

def seasonal_spread(spec,rows):
    """Research fixture only: bars are sorted {date:ISO, open: {symbol: price}}.
    Calendar trigger is observed at day-end; fill at NEXT supplied row open, never same row.
    This is an illustrative, year-local event simulator, NOT venue-realistic execution.
    """
    validate_spec(spec)
    if spec['kind']!='seasonal_futures_spread':raise InvalidSpec('Wrong spec kind')
    if len(rows)<3:raise InvalidSpec('At least 3 bars')
    dates=[date.fromisoformat(x['date']) for x in rows]
    if dates!=sorted(set(dates)):raise InvalidSpec('Dates must be unique and increasing')
    state={}; trades=[]; events=[]; blocked_entry_years=set()
    for ix in range(len(rows)-1):
        d=dates[ix]; next_row=rows[ix+1]
        entry_date=date.fromisoformat(f"{d.year}-{spec['parameters']['entry_after']}")
        exit_date=date.fromisoformat(f"{d.year}-{spec['parameters']['exit_after']}")
        if not entry_date<exit_date: raise InvalidSpec('Cross-year windows unsupported')
        if d.year not in state and d.year not in blocked_entry_years and d>=entry_date and d<exit_date:
            prices=next_row.get('open',{})
            if not all(leg['symbol'] in prices for leg in spec['legs']):
                events.append({'date':next_row['date'],'status':'BLOCKED_MISSING_LEG_PRICE'});blocked_entry_years.add(d.year);continue
            state[d.year]={'entry_date':next_row['date'],'price':{k:float(v) for k,v in prices.items()}}
            events.append({'date':next_row['date'],'action':'ENTRY_NEXT_OPEN','year':d.year})
        elif d.year in state and not state[d.year].get('closed') and d>=exit_date:
            prices=next_row.get('open',{})
            if not all(leg['symbol'] in prices for leg in spec['legs']):
                events.append({'date':next_row['date'],'status':'BLOCKED_MISSING_LEG_PRICE'});continue
            enter=state[d.year]
            legs=[{'symbol':leg['symbol'],'gross_pnl':leg_pnl(leg,enter['price'][leg['symbol']],prices[leg['symbol']])} for leg in spec['legs']]
            gross=sum(x['gross_pnl'] for x in legs)
            # Caller-supplied explicit fee model, not silently zero under unknown real data.
            fee=spec['parameters'].get('roundtrip_fees_usd')
            trades.append({'entry':enter['entry_date'],'exit':next_row['date'],'legs':legs,'gross_pnl':gross,
                           'net_pnl':round(gross-float(fee),8) if fee is not None else None,
                           'cost_status':'ASSUMED_FEE' if fee is not None else 'UNKNOWN'})
            enter['closed']=True
            events.append({'date':next_row['date'],'action':'EXIT_NEXT_OPEN','year':d.year})
    return {'status':'SYNTHETIC_FIXTURE_SIMULATION_ONLY','trades':trades,'events':events,
            'open_unclosed_years':[yr for yr,st in state.items() if not st.get('closed')],
            'real_backtest_status':'REAL_BACKTEST_NOT_RUN'}


def earnings_decile_long_short(spec, data):
    """Synthetic single-event cross-section: rank by public SUE and buy top/sell bottom.

    Only next available bar is used for fill. This does not imply real short availability,
    quote quality, liquidity or cost validation; it is *not* a market backtest.
    """
    validate_spec(spec)
    if spec['kind']!='earnings_decile_long_short':raise InvalidSpec('Wrong spec kind')
    if not isinstance(data,dict) or 'events' not in data or 'bars' not in data:raise InvalidSpec('Missing event/price series')
    events=data['events'];bars=data['bars']; params=spec['parameters']
    dates=[date.fromisoformat(x['date']) for x in bars]
    if dates!=sorted(set(dates)):raise InvalidSpec('Daily bars must be strictly increasing')
    if len(events)<10:raise InvalidSpec('At least 10 independently supplied event scores for decile research')
    symbols=[x['symbol'] for x in events]
    if len(set(symbols))!=len(symbols):raise InvalidSpec('Duplicate event instruments')
    for event in events:
        if not isinstance(event['sue'],(int,float)) or not math.isfinite(event['sue']):
            raise InvalidSpec('Finite standardized unexpected earnings required')
    latest_announcement=max(date.fromisoformat(e['available_at'][:10]) for e in events)
    first=next((i for i,d in enumerate(dates) if d>latest_announcement),None)
    if first is None:return {'status':'BLOCKED_NO_POST_PUBLICATION_BAR','trades':[], 'real_backtest_status':'REAL_BACKTEST_NOT_RUN'}
    end=first+int(params['hold_bars'])
    if end>=len(bars):return {'status':'BLOCKED_INSUFFICIENT_HOLD_PERIOD','trades':[], 'real_backtest_status':'REAL_BACKTEST_NOT_RUN'}
    # Deterministic, no looking at future returns in stock ranking.
    order=sorted(events,key=lambda x:(x['sue'],x['symbol']))
    k=max(1,int(len(events)*float(params['decile_fraction'])))
    if k*2>len(events):raise InvalidSpec('Overlapping top and bottom portfolios')
    selected=[(e,'SELL') for e in order[:k]]+[(e,'BUY') for e in order[-k:]]
    missing=[];trades=[]
    for ev,side in selected:
        sym=ev['symbol']
        if side=='SELL' and ev.get('borrow_available') is not True:
            missing.append('BORROW_UNCONFIRMED:'+sym);continue
        prices=[]
        for row in (bars[first],bars[end]):
            value=row.get('open',{}).get(sym)
            if not isinstance(value,(float,int)) or not math.isfinite(value) or value<=0:
                missing.append('INVALID_OR_MISSING_OPEN:'+sym);break
            prices.append(float(value))
        if len(prices)!=2:continue
        qty=math.floor(float(params['notional_per_leg_usd'])/prices[0])
        if qty<1:missing.append('INSUFFICIENT_NOTIONAL:'+sym);continue
        pnl=qty*(prices[1]-prices[0])*(1 if side=='BUY' else -1)
        trades.append({'symbol':sym,'side':side,'sue':ev['sue'],'shares':qty,'entry_date':str(dates[first]),
                       'exit_date':str(dates[end]),'entry_open':prices[0],'exit_open':prices[1],
                       'gross_pnl_usd':round(pnl,8),'net_pnl_usd':None})
    if missing or len(trades)!=2*k:
        return {'status':'BLOCKED_INCOMPLETE_LEGS','reasons':missing,'trades':[],
                'real_backtest_status':'REAL_BACKTEST_NOT_RUN'}
    return {'status':'SYNTHETIC_FIXTURE_SIMULATION_ONLY','selected_count':2*k,
            'gross_pnl_usd':round(sum(x['gross_pnl_usd'] for x in trades),8),
            'net_pnl_usd':None,'cost_status':'FEES_AND_BORROW_NOT_VERIFIED',
            'trades':trades, 'signal_date':str(latest_announcement),
            'real_backtest_status':'REAL_BACKTEST_NOT_RUN',
            'risk_controls':'SYMBOL_BORROW_RESEARCH_FIXTURE_ONLY_NOT_BROKER_VERIFIED'}
