from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from market_daily_10y.collector import Instrument, Store, ten_year_window
from market_daily_10y.wf04_scamp import prepare_series, run_wf04, scamp_ab_matches


ASOF=date(2026,11,4)
START,END=ten_year_window(ASOF)
A=Instrument("equity","NASDAQ","AAPL","AAPL","America/New_York")
B=Instrument("equity","TSE","7203","7203.T","Asia/Tokyo")


def data(multiplier=1.0):
    dates=pd.date_range(START,END-timedelta(days=1),freq="B")
    rng=np.random.default_rng(20261105)
    returns=rng.normal(0.0001,0.012,len(dates))
    close=multiplier*100.0*np.exp(np.cumsum(returns))
    return pd.DataFrame({
        "date":dates,"open":close,
        "high":close*1.01,"low":close*.99,"close":close,"volume":10000,
    })


def test_real_pyscamp_abjoin_correlations_match_numpy():
    import pyscamp
    assert callable(pyscamp.abjoin)
    rng=np.random.default_rng(777)
    a=rng.normal(size=250).astype(np.float64)
    b=a.copy()
    dates=[f"day-{i:04d}" for i in range(len(a))]
    result=scamp_ab_matches(a,b,dates,32,threshold=0.98,top=2,threads=2)
    assert len(result)>0
    assert result[0]["correlation"]>0.999
    assert result[0]["left_start"] == result[0]["right_start"]
    assert result[0]["same_calendar_window"]


def test_scamp_end_to_end_exact_ten_year_parquet_and_motif(tmp_path):
    store=Store(tmp_path)
    store.save(A,data(),START,END)
    store.save(B,data(3),START,END)
    result=run_wf04(store,A.key,B.key,ASOF,window=50,threshold=.95,top=3,threads=2)
    assert result["engine"]=="pyscamp.abjoin"
    assert result["engine_version"]!="injected_test_backend"
    assert result["aligned_common_trading_days"]>2000
    assert result["feature_points"]>2000
    assert result["status"]=="MATCHES_FOUND"
    assert result["results"][0]["correlation"]>0.99
    assert result["left_parquet_sha256"]
    assert result["right_parquet_sha256"]
    assert not result["downloaded_bars_in_wf04"]
    assert not result["evaluation_is_predictive_backtest"]


def test_stale_instrument_rejected_before_computation(tmp_path):
    store=Store(tmp_path)
    store.save(A,data(),START,END)
    store.save(B,data(3),START,END)
    with pytest.raises(ValueError,match="WF04_SOURCE_NOT_VERIFIED_AT_EXACT_ASOF"):
        run_wf04(store,A.key,B.key,ASOF+timedelta(days=1))
    with pytest.raises(ValueError,match="WF04_REQUIRES_DIFFERENT_INSTRUMENTS"):
        run_wf04(store,A.key,A.key,ASOF)


def test_corrupt_source_must_not_execute_scamp(tmp_path):
    store=Store(tmp_path)
    store.save(A,data(),START,END)
    store.save(B,data(3),START,END)
    store.file(B).write_bytes(store.file(B).read_bytes()+b"CORRUPT")
    with pytest.raises(ValueError,match="WF04_SOURCE_NOT_VERIFIED_AT_EXACT_ASOF"):
        run_wf04(store,A.key,B.key,ASOF)


def test_invalid_motif_window_and_nonpositive_prices_blocked():
    with pytest.raises(ValueError,match="SCAMP_INVALID_SUBSEQUENCE_LENGTH"):
        scamp_ab_matches(np.ones(20),np.ones(20),list(range(20)),21)
    df=pd.DataFrame({"date":["2026-01-02","2026-01-05"],
                     "left_close":[3.,-4.],"right_close":[2.,1.]})
    with pytest.raises(ValueError,match="SCAMP_NONPOSITIVE"):
        prepare_series(df)
