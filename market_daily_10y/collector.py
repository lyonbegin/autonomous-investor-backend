"""Independent rolling 10-year 1D global multi-asset market collector.

Every symbol uses the SAME absolute [start, end) calendar window, 1d bars.
No stale 2015–2017 fixtures. New strategies never trigger downloads.
Yahoo/yfinance only as a research starting point; check data usage rights.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, tempfile, time
from dataclasses import dataclass
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import numpy as np
import pandas as pd

ASSETS={'equity','etf','index','future','option','fx','crypto_spot',
        'crypto_future','commodity','bond','rate'}
COLS=['date','open','high','low','close','volume']


def ten_year_window(asof=None):
    end=asof or datetime.now(timezone.utc).date()
    try:start=end.replace(year=end.year-10)
    except ValueError:start=end.replace(year=end.year-10,day=28)
    return start,end


@dataclass(frozen=True)
class Instrument:
    asset_class:str
    exchange:str
    symbol:str
    vendor_symbol:str
    timezone:str
    calendar:str='weekday'
    contract_type:str='spot'

    def __post_init__(self):
        if self.asset_class not in ASSETS or self.calendar not in ('weekday','seven_day'):
            raise ValueError('INVALID_ASSET_OR_CALENDAR')
        for s in (self.exchange,self.symbol,self.vendor_symbol,self.timezone,self.contract_type):
            if not isinstance(s,str) or not s or len(s)>120 or '\x00' in s:
                raise ValueError('INVALID_INSTRUMENT_FIELD')
    @property
    def key(self):
        return ':'.join((self.asset_class,self.exchange,self.symbol,self.contract_type))
    @property
    def file_id(self):
        return hashlib.sha256(self.key.encode()).hexdigest()[:24]


def normalize(raw,start,end):
    if raw is None or raw.empty:raise ValueError('NO_DAILY_BARS')
    x=raw.copy()
    if 'date' not in [str(c).lower() for c in x.columns] and isinstance(x.index,pd.DatetimeIndex):
        x=x.reset_index()
    x.columns=[str(c).lower().replace(' ','_') for c in x.columns]
    if 'date' not in x and 'datetime' in x:x=x.rename(columns={'datetime':'date'})
    if not {'date','open','high','low','close'}.issubset(x):
        raise ValueError('DAILY_OHLC_REQUIRED')
    # Local exchange session date. Never shift a midnight daily bar to UTC.
    x['date']=pd.to_datetime(x['date'],errors='coerce').dt.date
    if 'volume' not in x:x['volume']=np.nan
    for name in COLS[1:]:x[name]=pd.to_numeric(x[name],errors='coerce')
    x=x.dropna(subset=['date','open','high','low','close'])
    valid=(np.isfinite(x[['open','high','low','close']]).all(axis=1)
           & (x['high']>=x[['open','low','close']].max(axis=1))
           & (x['low']<=x[['open','high','close']].min(axis=1))
           & (x[['open','high','low','close']].abs().max(axis=1)>0)
           & ~(x['volume'].notna() & (x['volume']<0)))
    x=x.loc[valid & (x['date']>=start) & (x['date']<end),COLS]
    x=x.sort_values('date').drop_duplicates('date',keep='last')
    if x.empty:raise ValueError('NO_VALID_DAILY_BARS_IN_WINDOW')
    x['date']=x['date'].map(str)
    return x.reset_index(drop=True)


def quality(inst,df,start,end):
    expected=((end-start).days if inst.calendar=='seven_day' else
              int(np.busday_count(start.isoformat(),end.isoformat())))
    first=date.fromisoformat(df.iloc[0].date)
    last=date.fromisoformat(df.iloc[-1].date)
    ratio=len(df)/expected
    reasons=[]
    if first>start+timedelta(days=32):reasons.append('NOT_FULL_TEN_YEAR_HISTORY')
    if last<end-timedelta(days=10):reasons.append('LAST_BAR_STALE')
    if ratio<0.80:reasons.append('TOO_MANY_DAILY_GAPS')
    return {'eligible':not reasons,'reasons':reasons,'rows':len(df),
            'first_date':str(first),'last_date':str(last),
            'coverage_ratio':round(ratio,4),'window_start':str(start),
            'window_end_exclusive':str(end),'timeframe':'1d'}


class Store:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'catalog.sqlite3'
        with sqlite3.connect(self.db) as con:
            con.execute('''CREATE TABLE IF NOT EXISTS instruments(
              key TEXT PRIMARY KEY,asset_class TEXT,exchange TEXT,symbol TEXT,
              vendor_symbol TEXT,timezone TEXT,calendar TEXT,contract_type TEXT,
              start TEXT,end_exclusive TEXT,first_date TEXT,last_date TEXT,
              rows INTEGER,coverage REAL,eligible INTEGER,reasons TEXT,
              sha256 TEXT,updated_at TEXT)''')

    def file(self,inst):
        return self.root/'daily'/inst.asset_class/(inst.file_id+'.parquet')

    def read(self,inst):
        p=self.file(inst)
        return pd.read_parquet(p) if p.exists() else pd.DataFrame(columns=COLS)

    def save(self,inst,new,start,end):
        current=self.read(inst)
        data=(normalize(pd.concat([current,new],ignore_index=True),start,end)
              if not current.empty else normalize(new,start,end))
        q=quality(inst,data,start,end)
        p=self.file(inst);p.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.sync-',suffix='.parquet',dir=p.parent)
        os.close(fd)
        try:
            data.to_parquet(tmp,index=False,compression='zstd')
            digest=hashlib.sha256(Path(tmp).read_bytes()).hexdigest()
            os.replace(tmp,p)
        finally:
            Path(tmp).unlink(missing_ok=True)
        with sqlite3.connect(self.db) as con:
            con.execute('''INSERT INTO instruments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET
               start=excluded.start,end_exclusive=excluded.end_exclusive,
               first_date=excluded.first_date,last_date=excluded.last_date,
               rows=excluded.rows,coverage=excluded.coverage,eligible=excluded.eligible,
               reasons=excluded.reasons,sha256=excluded.sha256,updated_at=excluded.updated_at''',
               (inst.key,inst.asset_class,inst.exchange,inst.symbol,inst.vendor_symbol,
                inst.timezone,inst.calendar,inst.contract_type,str(start),str(end),
                q['first_date'],q['last_date'],q['rows'],q['coverage_ratio'],
                int(q['eligible']),json.dumps(q['reasons']),digest,
                datetime.now(timezone.utc).isoformat()))
        return {'instrument':inst.key,**q,'sha256':digest}

    def status(self):
        with sqlite3.connect(self.db) as con:
            con.row_factory=sqlite3.Row
            rows=[dict(x) for x in con.execute(
                'SELECT * FROM instruments ORDER BY asset_class,exchange,symbol')]
        return {'stored':len(rows),'eligible':sum(x['eligible'] for x in rows),
                'total_rows':sum(x['rows'] for x in rows),'instruments':rows}

    def align(self,a,b,min_overlap=0.8):
        lookup={x['key']:x for x in self.status()['instruments']}
        aa,bb=lookup.get(a.key),lookup.get(b.key)
        if not aa or not bb or not aa['eligible'] or not bb['eligible']:
            raise ValueError('NOT_10Y_ELIGIBLE')
        if (aa['start'],aa['end_exclusive'])!=(bb['start'],bb['end_exclusive']):
            raise ValueError('WINDOW_MISMATCH')
        x=self.read(a)[['date','close']].rename(columns={'close':'left_close'})
        y=self.read(b)[['date','close']].rename(columns={'close':'right_close'})
        common=x.merge(y,on='date',validate='one_to_one',how='inner')
        ratio=len(common)/min(len(x),len(y))
        if ratio<min_overlap:raise ValueError('INSUFFICIENT_SHARED_TRADING_DATES')
        return common,{'common_dates':len(common),'overlap_ratio':round(ratio,4),
                       'filled_gaps':False,'start':aa['start'],
                       'end_exclusive':aa['end_exclusive']}


def yahoo_fetch(inst,start,end):
    import yfinance as yf
    frame=yf.Ticker(inst.vendor_symbol).history(
        start=str(start),end=str(end),interval='1d',auto_adjust=True,
        actions=False,prepost=False,timeout=20)
    return normalize(frame,start,end)


def sync(store,inst,start,end,fetcher=yahoo_fetch,retries=2):
    old=store.read(inst)
    since=start if old.empty else max(
        start,date.fromisoformat(old.iloc[-1].date)-timedelta(days=10))
    for attempt in range(retries+1):
        try:
            fresh=fetcher(inst,since,end)
            return {'status':'COLLECTED',**store.save(inst,fresh,start,end)}
        except Exception as exc:
            reason=f'{type(exc).__name__}: {str(exc)[:180]}'
            if attempt<retries:time.sleep(2*(attempt+1))
    return {'status':'FAILED','instrument':inst.key,'reason':reason}


def load_universe(path):
    data=pd.read_csv(path,dtype=str,keep_default_na=False)
    if not {'asset_class','exchange','symbol','vendor_symbol','timezone'}.issubset(data):
        raise ValueError('UNIVERSE_COLUMNS_MISSING')
    result={}
    for row in data.to_dict('records'):
        inst=Instrument(row['asset_class'],row['exchange'],row['symbol'],
                        row['vendor_symbol'],row['timezone'],
                        row.get('calendar') or 'weekday',row.get('contract_type') or 'spot')
        result[inst.key]=inst
    return list(result.values())


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',default=os.getenv('DAILY_POOL_ROOT','/data/market_daily_10y'))
    ap.add_argument('--universe',default=str(Path(__file__).parent/'universe.csv'))
    ap.add_argument('--asof',help='UTC exclusive end, e.g. 2026-11-04')
    ap.add_argument('--limit',type=int,default=int(os.getenv('DAILY_BATCH_LIMIT','20')))
    ap.add_argument('--asset')
    ap.add_argument('--status',action='store_true')
    ap.add_argument('--align',nargs=2)
    ap.add_argument('--pause',type=float,default=1.5)
    args=ap.parse_args(argv)
    store=Store(args.root)
    if args.status:
        print(json.dumps(store.status(),ensure_ascii=False,indent=2));return
    universe=load_universe(args.universe)
    if args.align:
        by_key={x.key:x for x in universe}
        joined,info=store.align(by_key[args.align[0]],by_key[args.align[1]])
        print(json.dumps({'info':info,'first_rows':joined.head(3).to_dict('records')},
                         ensure_ascii=False));return
    if args.asset:universe=[x for x in universe if x.asset_class==args.asset]
    start,end=ten_year_window(date.fromisoformat(args.asof) if args.asof else None)
    results=[]
    if args.limit<1:raise ValueError('BATCH_LIMIT_POSITIVE_REQUIRED')
    for inst in universe[:args.limit]:
        item=sync(store,inst,start,end)
        results.append(item)
        print(json.dumps(item,ensure_ascii=False),flush=True)
        if args.pause:time.sleep(args.pause)
    print(json.dumps({'status':'BATCH_FINISHED',
        'window_start':str(start),'window_end_exclusive':str(end),
        'timeframe':'1d','attempted':len(results),
        'eligible':sum(x.get('eligible',False) for x in results),
        'failed':sum(x['status']=='FAILED' for x in results),
        'worldwide_coverage_verified':False},
        ensure_ascii=False),flush=True)


if __name__=='__main__':main()
