import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from market_daily_10y import markets_api as api
from market_daily_10y.collector import Instrument, Store, ten_year_window

A=Instrument("equity","NASDAQ","AAPL","AAPL","America/New_York")
B=Instrument("crypto_spot","GLOBAL","BTCUSD","BTC-USD","UTC","seven_day")


def create_bars(asof, *, seven_day=False):
    start,end=ten_year_window(asof)
    days=pd.date_range(start,end-timedelta(days=1),
                       freq="D" if seven_day else "B")
    prices=100*np.exp(np.cumsum(np.full(len(days),.0002)))
    return pd.DataFrame({
        "date":days,"open":prices,"high":prices*1.02,"low":prices*.98,
        "close":prices,"volume":1000,
    })


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api,"ROOT",tmp_path)
    monkeypatch.setattr(api,"_asof",lambda:date(2026,11,4))
    monkeypatch.setattr(api,"_job",{"state":"idle","attempted":0,"completed":0,"failed":0})
    monkeypatch.setenv("MARKET_UPDATE_TOKEN","testing-secret")
    dest=tmp_path/"universe"
    dest.mkdir()
    (dest/"world.csv").write_text(
        "asset_class,exchange,symbol,vendor_symbol,timezone,calendar,contract_type\n"
        "equity,NASDAQ,AAPL,AAPL,America/New_York,weekday,spot\n"
        "crypto_spot,GLOBAL,BTCUSD,BTC-USD,UTC,seven_day,spot\n",encoding="utf-8")
    return TestClient(api.app)


def test_real_catalog_reports_missing_separately_from_stored(client):
    summary=client.get("/api/markets/summary").json()
    assert summary["totals"]["listed"]==2
    assert summary["totals"]["stored_files"]==0
    assert summary["totals"]["eligible_10y_any_snapshot"]==0
    assert summary["cron_enabled"] is False
    assert summary["universe_complete_worldwide"] is False
    items=client.get("/api/markets/instruments?category=equity").json()
    assert items["total"]==1
    assert items["items"][0]["status"]=="미확보"
    assert items["items"][0]["rows"]==0
    assert client.get("/api/markets/bars",params={"key":A.key},
                      headers={"Authorization":"Bearer testing-secret"}).status_code==404


def test_saved_real_parquet_visible_only_after_authorized_read(client):
    root=api.ROOT
    start,end=ten_year_window(date(2026,11,4))
    Store(root).save(A,create_bars(end),start,end)
    summary=client.get("/api/markets/summary").json()
    assert summary["totals"]["stored_files"]==1
    assert summary["totals"]["eligible_10y_any_snapshot"]==1
    assert summary["groups"]["equity"]["eligible"]==1
    assert client.get("/api/markets/bars",params={"key":A.key}).status_code==403
    r=client.get("/api/markets/bars",params={"key":A.key},
                 headers={"Authorization":"Bearer testing-secret"})
    assert r.status_code==200,r.text
    obj=r.json()
    assert obj["rows"]>2000
    assert obj["bars"][0]["date"]=="2016-11-04"
    assert obj["bars"][-1]["date"]=="2026-11-03"
    assert obj["sha256"]
    assert obj["bars"][0]["close"]>0


def test_no_fabricated_bars_when_catalog_missing(client):
    assert client.get("/api/markets/instruments?category=economy").json()["total"]==0
    assert client.get("/api/markets/bars",params={"key":"index:UNKNOWN:NOPE:index"},
                 headers={"Authorization":"Bearer testing-secret"}).status_code==404
    r=client.get("/markets/")
    assert r.status_code==200
    assert "10년 일봉" in r.text
    assert "업데이트" in r.text


def test_corrupt_saved_parquet_refused(client):
    store=Store(api.ROOT)
    start,end=ten_year_window(date(2026,11,4))
    store.save(A,create_bars(end),start,end)
    f=store.file(A)
    f.write_bytes(f.read_bytes()+b"tamper")
    r=client.get("/api/markets/bars",params={"key":A.key},
                 headers={"Authorization":"Bearer testing-secret"})
    assert r.status_code==409


def test_manual_update_is_only_triggered_on_authorized_post(client,monkeypatch):
    calls=[]
    def fake_sync(store,inst,start,end):
        calls.append((inst.key,start,end))
        data=create_bars(end,seven_day=inst.asset_class=="crypto_spot")
        q=store.save(inst,data,start,end)
        return {"status":"COLLECTED",**q}
    monkeypatch.setattr(api,"sync",fake_sync)
    assert not calls
    # Viewing a page, summary, chart status never triggers Yahoo requests.
    client.get("/markets/")
    client.get("/api/markets/summary")
    assert not calls
    assert client.post("/api/markets/update",
                       json={"scope":"instrument","key":A.key}).status_code==403
    assert not calls
    r=client.post("/api/markets/update",
        headers={"Authorization":"Bearer testing-secret"},
        json={"scope":"instrument","key":A.key})
    assert r.status_code==202,r.text
    for _ in range(80):
        state=client.get("/api/markets/update-status").json()
        if state["state"]!="running":
            break
        time.sleep(.05)
    assert state["state"]=="completed",state
    assert state["attempted"]==1
    assert state["completed"]==1
    assert calls[0][0]==A.key
    assert Store(api.ROOT).status()["stored"]==1


def test_updates_reject_invalid_symbol_and_unregistered_category(client):
    h={"Authorization":"Bearer testing-secret"}
    assert client.post("/api/markets/update",json={"scope":"instrument",
                       "key":"other:missing"},headers=h).status_code==404
    assert client.post("/api/markets/update",json={"scope":"category",
                       "category":"unknown"},headers=h).status_code==422
    assert client.post("/api/markets/update",json={"scope":"category",
                       "category":"economy"},headers=h).status_code==409
