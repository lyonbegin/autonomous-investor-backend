"""Offline regression tests; no network, auth, WebSocket forging or proxying."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from browser_worker.market_chart_5y import (
    TIMEFRAMES, chart_url, evaluate_history, five_year_start,
)
from browser_worker.market_chart_5y_api import app


ASOF=date(2026,11,5)


def make_bars(start:date,end:date,spacing=1,skip_weekends=True):
    result=[]
    day=start
    while day<end:
        if not skip_weekends or day.weekday()<5:
            t=int(datetime.combine(day,datetime.min.time(),
                                   timezone.utc).timestamp()*1000)
            result.append({"time_ms":t,"open":99.,"high":101.,
                           "low":98.,"close":100.,"volume":12345.})
        day+=timedelta(days=spacing)
    return result


def make_minute_bars(day:date,count=390):
    begin=datetime.combine(day,datetime.min.time(),timezone.utc)
    return [{"time_ms":int((begin+timedelta(minutes=m)).timestamp()*1000),
             "open":100.,"high":101.,"low":99.,"close":100.,"volume":20.}
            for m in range(count)]


def test_correct_five_year_calendar_including_leap_day():
    assert five_year_start(ASOF)==date(2021,11,5)
    assert five_year_start(date(2024,2,29))==date(2019,2,28)


def test_supported_tradingview_timeframes_are_explicit_and_complete():
    assert set(TIMEFRAMES)=={"1","3","5","15","30","60","120","240","1D","1W"}
    assert chart_url("NASDAQ:AAPL","1D").endswith("symbol=NASDAQ%3AAAPL&interval=1D")
    assert chart_url("BINANCE:BTCUSDT","5").endswith("symbol=BINANCE%3ABTCUSDT&interval=5")


@pytest.mark.parametrize("bad",[
    "http://localhost/admin","NASDAQ:AAPL&evil=1",
    "NASDAQ:AAPL?interval=1","AAPL","../secret",
])
def test_user_cannot_supply_arbitrary_urls_or_query_strings(bad):
    with pytest.raises(ValueError,match="INVALID_EXCHANGE_PREFIXED_SYMBOL"):
        chart_url(bad,"1D")
    with pytest.raises(ValueError,match="INVALID_EXCHANGE_PREFIXED_SYMBOL"):
        chart_url(bad,"1")


def test_five_year_daily_observed_range_is_verified():
    bars=make_bars(five_year_start(ASOF),ASOF)
    q=evaluate_history(bars,interval="1D",asof=ASOF)
    assert q["five_year_window_covered"] is True
    assert q["interval_verified"] is True
    assert q["observed_count"]>1000
    assert q["requested_start"]=="2021-11-05"
    assert q["requested_end_exclusive"]=="2026-11-05"
    assert q["market_sessions_filled"] is False


def test_last_300_daily_bars_must_be_flagged_partial():
    bars=make_bars(five_year_start(ASOF),ASOF)[-300:]
    q=evaluate_history(bars,interval="1D",asof=ASOF)
    assert q["coverage_status"]=="PARTIAL_HISTORY"
    assert q["reaches_requested_start"] is False
    assert q["observed_count"]==300


def test_one_week_of_real_one_minute_bars_cannot_claim_five_years():
    bars=make_minute_bars(date(2026,11,3))
    q=evaluate_history(bars,interval="1",asof=ASOF)
    assert q["interval_verified"] is True
    assert q["five_year_window_covered"] is False
    assert q["observed_count"]==390


def test_daily_data_cannot_masquerade_as_minute_data():
    bars=make_bars(five_year_start(ASOF),ASOF)
    q=evaluate_history(bars,interval="1",asof=ASOF)
    assert q["interval_verified"] is False
    assert q["five_year_window_covered"] is False


def test_invalid_or_duplicate_bars_are_rejected_not_filled():
    bars=make_bars(date(2026,10,1),ASOF)
    bars.append(dict(bars[-1]))  # duplicate time
    bars.append({"time_ms":int(datetime(2026,10,15,tzinfo=timezone.utc).timestamp()*1000),
                 "open":100,"high":98,"low":99,"close":100,"volume":1})
    q=evaluate_history(bars,interval="1D",asof=ASOF)
    assert q["observed_count"]==len(bars)-2
    assert q["market_sessions_filled"] is False


def test_ui_chart_options_does_not_start_collection():
    client=TestClient(app)
    status=client.get("/health")
    assert status.status_code==200
    assert status.json()["scheduled_ingestion"] is False
    res=client.get("/v1/research/chart/options")
    assert res.status_code==200
    names={x["value"]:x["label"] for x in res.json()["timeframes"]}
    assert names["1"]=="1분"
    assert names["1D"]=="일봉"
    assert res.json()["periods"]==[{"value":"5Y","label":"최근 5년"}]


def test_invalid_chart_inputs_do_not_launch_browser():
    client=TestClient(app)
    bad=client.post("/v1/research/chart/observe",
                    json={"symbol":"http://localhost","interval":"1D"})
    assert bad.status_code==422
    bad_interval=client.post("/v1/research/chart/observe",
                    json={"symbol":"NASDAQ:AAPL","interval":"25"})
    assert bad_interval.status_code==422
    wrong_period=client.post("/v1/research/chart/observe",
                    json={"symbol":"NASDAQ:AAPL","interval":"1D","years":10})
    assert wrong_period.status_code==422
