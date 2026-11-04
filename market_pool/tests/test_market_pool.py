import io
import zipfile
import pandas as pd
import pytest

from market_pool import Instrument,MarketPool,intraday_to_daily
from market_pool.sources import import_global_eod,binance_zip_to_frame

def test_all_market_asset_categories(tmp_path):
    p=MarketPool(tmp_path)
    classes=["equity","etf","index","future","option","fx","crypto_spot",
             "crypto_future","commodity","bond","rate"]
    for kind in classes:
        p.register(Instrument(kind,"TEST","X","unused","X"))
    assert p.coverage()["registered"]==11
    assert p.coverage()["populated"]==0

def test_idempotent_daily_upsert(tmp_path):
    p=MarketPool(tmp_path)
    x=Instrument("equity","NASDAQ","AAPL","yahoo","AAPL")
    frame=pd.DataFrame([{"date":"2026-01-02","open":100,"high":102,"low":99,
                        "close":101,"volume":1234},
                        {"date":"2026-01-05","open":101,"high":103,"low":100,
                         "close":102,"volume":555}])
    a=p.ingest(x,frame,source="test")
    b=p.ingest(x,frame,source="test")
    assert a["total_rows"]==2 and b["total_rows"]==2
    assert p.coverage()["total_stored_rows"]==2
    updated=frame.iloc[[1]].copy()
    updated.loc[1,"close"]=102.5
    p.ingest(x,updated,source="correction")
    assert p.read(x).iloc[-1]["close"]==102.5

def test_reject_invalid_high_low_and_missing_volume(tmp_path):
    p=MarketPool(tmp_path)
    x=Instrument("fx","FX","EURUSD","yahoo","EURUSD=X")
    a=p.ingest(x,pd.DataFrame([
       {"date":"2026-01-02","open":1.2,"high":1.3,"low":1.1,"close":1.25},
       {"date":"2026-01-03","open":1.2,"high":1.0,"low":1.1,"close":1.25}
    ]),source="test")
    assert a["accepted"]==1 and a["rejected"]==1

def test_real_plotly_apple_historical_fixture(tmp_path):
    p=MarketPool(tmp_path)
    x=Instrument("equity","NASDAQ","AAPL","yahoo","AAPL")
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/"fixtures"/"REAL_plotly_AAPL_2015_2017.csv"
    a=p.ingest(x,pd.read_csv(path),source="plotly-MIT-original-csv")
    assert a["total_rows"]==506
    assert a["first_date"]=="2015-02-17"
    assert a["last_date"]=="2017-02-16"
    assert p.coverage()["populated"]==1

def test_existing_global_eod_import(tmp_path):
    p=MarketPool(tmp_path/"pool")
    csvfile=tmp_path/"source.csv"
    csvfile.write_text(
       "Symbol,Date,Open,High,Low,Close,Volume\n"
       "NASDAQ.MSFT,2026-01-02,300,310,295,305,3000\n"
       "KRX.005930,2026-01-02,60000,61000,58000,59000,3000\n",
       encoding="utf8")
    import_global_eod(p,csvfile)
    assert p.coverage()["populated"]==2

def test_session_local_intraday(tmp_path):
    df=pd.DataFrame({
      "timestamp":["2026-03-03T23:00:00Z","2026-03-04T14:00:00Z"],
      "open":[10,11],"high":[12,13],"low":[9,10],
      "close":[11,12],"volume":[100,150]
    })
    day=intraday_to_daily(df,timezone_name="America/New_York")
    assert day.iloc[0]["date"]=="2026-03-03"
    assert day.iloc[1]["date"]=="2026-03-04"
    session=intraday_to_daily(df,timezone_name="America/New_York",rollover_hour=18)
    assert session.iloc[0]["date"]=="2026-03-04"

def test_binance_ms_and_us_timestamps():
    def zip_csv(ts):
        target=io.BytesIO()
        with zipfile.ZipFile(target,"w") as zf:
            zf.writestr("BTCUSDT-1d.csv",f"{ts},10,11,9,10.5,100,0,0,0,0,0,0\n")
        return target.getvalue()
    assert binance_zip_to_frame(zip_csv(1735689600000)).iloc[0]["date"]=="2025-01-01"
    assert binance_zip_to_frame(zip_csv(1735689600000000)).iloc[0]["date"]=="2025-01-01"

def test_unsupported_assets_do_not_create_fake_data(tmp_path):
    pool=MarketPool(tmp_path)
    x=Instrument("option","VENDOR_REQUIRED","EXPIRED_SPX","unavailable","SPX")
    pool.register(x)
    assert pool.coverage()["populated"]==0
