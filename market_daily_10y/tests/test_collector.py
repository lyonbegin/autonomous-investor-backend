from datetime import date,timedelta
import numpy as np
import pandas as pd
import pytest
from market_daily_10y.collector import (
 Instrument,Store,normalize,quality,ten_year_window,sync)

A=Instrument('equity','NASDAQ','AAPL','AAPL','America/New_York')
B=Instrument('equity','KRX','005930','005930.KS','Asia/Seoul')
C=Instrument('crypto_spot','GLOBAL','BTC','BTC-USD','UTC','seven_day')
START,END=ten_year_window(date(2026,11,4))


def prices(inst,missing=()):
    f='D' if inst.calendar=='seven_day' else 'B'
    dt=pd.date_range(START,END-timedelta(days=1),freq=f)
    if missing:dt=dt.drop(pd.to_datetime(list(missing)))
    close=np.linspace(100.,200.,len(dt))
    return pd.DataFrame({'date':dt,'open':close,
       'high':close+2,'low':close-2,'close':close+1,'volume':1000})


def test_fixed_ten_year_window():
    assert (str(START),str(END))==('2016-11-04','2026-11-04')


def test_short_history_not_eligible():
    q=quality(A,normalize(prices(A).tail(500),START,END),START,END)
    assert not q['eligible'] and 'NOT_FULL_TEN_YEAR_HISTORY' in q['reasons']


def test_original_exchange_local_date_preserved():
    f=prices(A).head(3)
    f['date']=pd.to_datetime(f['date']).dt.tz_localize('America/New_York')
    assert normalize(f,START,END).iloc[0]['date']==str(START)


def test_bad_ohlc_not_silently_saved():
    f=prices(A).head(3)
    f.loc[0,'high']=50
    assert len(normalize(f,START,END))==2


def test_exact_overlap_and_no_holiday_fill(tmp_path):
    p=Store(tmp_path)
    p.save(A,prices(A),START,END)
    p.save(B,prices(B,missing=['2026-01-05']),START,END)
    aligned,info=p.align(A,B)
    assert len(aligned)==len(prices(A))-1
    assert not info['filled_gaps']
    assert '2026-01-05' not in set(aligned.date)


def test_incremental_and_repeated_sync(tmp_path):
    p=Store(tmp_path)
    requested=[]
    def fetch(inst,s,e):
        requested.append(s)
        f=prices(inst)
        return f[pd.to_datetime(f.date).dt.date>=s]
    first=sync(p,A,START,END,fetcher=fetch,retries=0)
    assert first['eligible'] and requested[0]==START
    second=sync(p,A,START,END,fetcher=fetch,retries=0)
    assert second['eligible'] and requested[1]>START
    assert len(p.read(A))==len(prices(A))


def test_insufficient_history_blocks_alignment(tmp_path):
    p=Store(tmp_path)
    p.save(A,prices(A),START,END)
    p.save(B,prices(B).tail(400),START,END)
    with pytest.raises(ValueError,match='NOT_10Y_ELIGIBLE'):p.align(A,B)


def test_crypto_24_7_daily_calendar(tmp_path):
    p=Store(tmp_path)
    q=p.save(C,prices(C),START,END)
    assert q['eligible']
    assert len(p.read(C))>len(prices(A))


def test_different_collection_periods_never_compare(tmp_path):
    p=Store(tmp_path)
    p.save(A,prices(A),START,END)
    p.save(B,prices(B),START,END+timedelta(days=1))
    with pytest.raises(ValueError,match='WINDOW_MISMATCH'):p.align(A,B)
