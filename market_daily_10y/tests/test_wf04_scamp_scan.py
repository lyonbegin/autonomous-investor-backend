from datetime import date, timedelta
import numpy as np
import pandas as pd
import pytest

from market_daily_10y.collector import Instrument, Store, ten_year_window
from market_daily_10y.wf04_scamp_scan import scan_candidates

ASOF=date(2026,11,4)
START,END=ten_year_window(ASOF)
A=Instrument("equity","NASDAQ","AAA","AAA","America/New_York")
B=Instrument("equity","NYSE","BBB","BBB","America/New_York")
C=Instrument("equity","TSE","CCC","CCC.T","Asia/Tokyo")
D=Instrument("equity","HKEX","DDD","DDD.HK","Asia/Hong_Kong")


def bars(seed, scale=1):
    days=pd.date_range(START,END-timedelta(days=1),freq="B")
    rng=np.random.default_rng(seed)
    price=scale*100*np.exp(np.cumsum(rng.normal(.0001,.018,len(days))))
    return pd.DataFrame({"date":days,"open":price,
                         "high":price*1.02,"low":price*.98,
                         "close":price,"volume":10000})


def test_real_batch_ranks_correlated_motif_above_independent(tmp_path):
    s=Store(tmp_path)
    s.save(A,bars(888),START,END)
    s.save(B,bars(888,3),START,END)
    s.save(C,bars(999),START,END)
    report=scan_candidates(s,A.key,[C.key,B.key,D.key],ASOF,
                           window=64,threshold=.5,top=2,threads=2)
    assert report["attempted"]==3
    assert report["scored"]==2
    assert report["blocked"]==1
    assert report["ranked"][0]["candidate_key"]==B.key
    assert report["ranked"][0]["best_correlation"]>.99
    assert report["excluded"][0]["candidate_key"]==D.key
    assert report["excluded"][0]["reason_code"]=="WF04_SOURCE_NOT_VERIFIED_AT_EXACT_ASOF"
    assert report["source"]=="EXISTING_LOCAL_VERIFIED_10Y_PARQUET_ONLY"
    assert report["trading_enabled"] is False


def test_batch_bounds_and_duplicate_candidate_collapse(tmp_path):
    s=Store(tmp_path)
    with pytest.raises(ValueError, match="WF04_BATCH_ANCHOR_IS_CANDIDATE"):
        scan_candidates(s,A.key,[A.key,B.key],ASOF)
    with pytest.raises(ValueError, match="WF04_BATCH_OUTSIDE_ALLOWED_RANGE"):
        scan_candidates(s,A.key,[],ASOF)
    s.save(A,bars(888),START,END)
    s.save(B,bars(888,3),START,END)
    result=scan_candidates(s,A.key,[B.key,B.key],ASOF,
                           window=32,threshold=.8)
    assert result["attempted"]==1
    assert result["scored"]==1
