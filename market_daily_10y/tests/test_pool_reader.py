from datetime import date, timedelta
import numpy as np
import pandas as pd
import pytest

from market_daily_10y.collector import Instrument, Store, ten_year_window
from market_daily_10y.pool_reader import eligible_manifest, export_pair

ASOF=date(2026,11,4)
START,END=ten_year_window(ASOF)
A=Instrument('equity','NASDAQ','AAPL','AAPL','America/New_York')
B=Instrument('equity','TSE','7203','7203.T','Asia/Tokyo')


def bars(omitted=None):
    days=pd.date_range(START,END-timedelta(days=1),freq='B')
    if omitted is not None:
        days=days.drop(pd.to_datetime(omitted))
    px=np.linspace(100.,200.,len(days))
    return pd.DataFrame({'date':days,'open':px,'high':px+2,
                         'low':px-2,'close':px,'volume':1000})


def test_identical_asof_manifest_rejects_stale_even_if_eligible(tmp_path):
    store=Store(tmp_path)
    store.save(A,bars(),START,END)
    store.save(B,bars(),START,END)
    report=eligible_manifest(store,ASOF)
    assert report['ready']==2
    assert all(x['end_exclusive']=='2026-11-04' for x in report['instruments'])
    assert report['downloaded_new_bars'] is False
    new_asof=ASOF+timedelta(days=1)
    report=eligible_manifest(store,new_asof)
    assert report['ready']==0
    assert report['excluded']['WRONG_TEN_YEAR_SNAPSHOT']==2


def test_digest_corruption_blocks_pool_handoff(tmp_path):
    store=Store(tmp_path)
    store.save(A,bars(),START,END)
    file=store.file(A)
    file.write_bytes(file.read_bytes()+b'CORRUPTION')
    report=eligible_manifest(store,ASOF)
    assert report['ready']==0
    assert report['excluded']['DIGEST_MISMATCH']==1


def test_pair_export_uses_actual_common_trading_dates(tmp_path):
    store=Store(tmp_path)
    store.save(A,bars(),START,END)
    missing=['2026-01-05','2026-01-06']
    store.save(B,bars(missing),START,END)
    output=tmp_path/'shared.parquet'
    item=export_pair(store,A.key,B.key,ASOF,output)
    df=pd.read_parquet(output)
    assert item['common_dates']==len(bars())-2
    assert set(missing).isdisjoint(df['date'])
    assert df['date'].is_unique
    assert not item['filled_gaps']
    assert item['sha256']


def test_pair_rejects_wrong_asof_and_unapproved_short_history(tmp_path):
    store=Store(tmp_path)
    store.save(A,bars(),START,END)
    store.save(B,bars().tail(200),START,END)
    with pytest.raises(ValueError,match='WF04_INPUT_NOT_SNAPSHOT_ELIGIBLE'):
        export_pair(store,A.key,B.key,ASOF,tmp_path/'bad.parquet')
    with pytest.raises(ValueError,match='WF04_INPUT_NOT_SNAPSHOT_ELIGIBLE'):
        export_pair(store,A.key,A.key,ASOF+timedelta(days=1),tmp_path/'stale.parquet')
