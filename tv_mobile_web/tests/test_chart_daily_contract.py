"""Protect the user's exact request: five calendar years of DAILY (1D) OHLCV.

These tests use explicit synthetic fixtures only for verification and never
report that fixture as collected TradingView market data.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from tv_mobile_web.chart_observer import TIMEFRAMES, chart_url, evaluate_history, five_year_start
from tv_mobile_web.chart_store import ChartHistoryStore
from tv_mobile_web.server import app

ASOF = date(2026, 11, 5)


def simulated_trading_dates():
    out = []
    d = five_year_start(ASOF)
    while d < ASOF:
        if d.weekday() < 5:
            t = int(datetime.combine(d, datetime.min.time(), timezone.utc).timestamp() * 1000)
            out.append({
                "time_ms": t,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 2000.0,
            })
        d += timedelta(days=1)
    return out


def test_only_one_daily_timeframe_and_five_year_url():
    assert TIMEFRAMES == {"1D": ("일봉", 86400)}
    assert chart_url("NASDAQ:AAPL", "1D") == (
        "https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL"
        "&interval=1D&range=60M")
    for interval in ("1", "5", "60", "120", "1W"):
        with pytest.raises(ValueError, match="UNSUPPORTED_CHART_TIMEFRAME"):
            chart_url("NASDAQ:AAPL", interval)


def test_app_options_are_daily_only():
    client = TestClient(app)
    result = client.get("/api/chart/options")
    assert result.status_code == 200
    assert result.json()["periods"] == [{"value": 5, "label": "최근 5년"}]
    assert result.json()["intervals"] == [{"value": "1D", "label": "일봉"}]
    assert result.json()["never_auto_collect"] is True


@pytest.mark.parametrize("minutes", ["1", "5", "15", "60", "240", "1W"])
def test_manual_endpoint_rejects_every_non_daily_frame_before_browser_starts(minutes):
    client = TestClient(app)
    response = client.post("/api/chart/collect", json={
        "symbol": "NASDAQ:AAPL", "years": 5, "interval": minutes,
    })
    assert response.status_code == 422


def test_actual_date_coverage_check_cannot_be_faked_by_300_daily_bars():
    history = simulated_trading_dates()
    all_days = evaluate_history(history, interval="1D", asof=ASOF)
    assert all_days["five_year_window_covered"] is True
    assert all_days["observed_count"] > 1000
    only_latest = evaluate_history(history[-300:], interval="1D", asof=ASOF)
    assert only_latest["five_year_window_covered"] is False
    assert only_latest["coverage_status"] == "PARTIAL_HISTORY"
    for interval in ("1", "5", "60"):
        with pytest.raises(ValueError, match="INVALID_HISTORY_PARAMETERS"):
            evaluate_history(history, interval=interval, asof=ASOF)


def test_private_store_saves_only_verified_daily_bars(tmp_path):
    store = ChartHistoryStore(tmp_path)
    bars = simulated_trading_dates()
    result = store.save_observation({
        "symbol": "NASDAQ:AAPL",
        "interval": "1D",
        "source": "TRADINGVIEW_PUBLIC_CHART_NORMAL_UI_PASSIVE_WEBSOCKET",
        "bars": bars,
    }, ASOF)
    assert result["saved"]
    assert result["bar_count"] == len(bars)
    assert result["five_year_extent_covered"]
    loaded = store.read("NASDAQ:AAPL")
    assert loaded["quality"]["observed_count"] == len(bars)
    assert loaded["bars"][0]["time_ms"] == bars[0]["time_ms"]
    assert loaded["metadata"]["interval"] == "1D"
    with pytest.raises(ValueError, match="STORE_ACCEPTS_DAILY_ONLY"):
        store.save_observation({
            "symbol": "NASDAQ:AAPL", "interval": "1",
            "source": "TRADINGVIEW_PUBLIC_CHART_NORMAL_UI_PASSIVE_WEBSOCKET",
            "bars": bars,
        }, ASOF)
    with pytest.raises(ValueError, match="UNVERIFIED_CHART_PROVENANCE"):
        store.save_observation({
            "symbol": "NASDAQ:AAPL", "interval": "1D",
            "source": "YAHOO_FAKE_OR_WIDGET",
            "bars": bars,
        }, ASOF)


def test_partial_refresh_keeps_previously_observed_five_year_data(tmp_path):
    store=ChartHistoryStore(tmp_path)
    bars=simulated_trading_dates()
    full={
        "symbol":"NASDAQ:AAPL",
        "interval":"1D",
        "source":"TRADINGVIEW_PUBLIC_CHART_NORMAL_UI_PASSIVE_WEBSOCKET",
        "bars":bars,
    }
    first=store.save_observation(full,ASOF)
    assert first["five_year_extent_covered"]
    # Some public TradingView chart loads only deliver latest 300 bars.
    # A subsequent manually initiated partial response must not erase 5Y.
    second=store.save_observation({**full,"bars":bars[-300:]},ASOF)
    assert second["bar_count"]==len(bars)
    assert second["five_year_extent_covered"]
    assert len(store.read("NASDAQ:AAPL")["bars"])==len(bars)


def test_corrupted_previous_chart_file_blocks_destructive_refresh(tmp_path):
    store=ChartHistoryStore(tmp_path)
    bars=simulated_trading_dates()
    payload={"symbol":"NASDAQ:AAPL","interval":"1D",
             "source":"TRADINGVIEW_PUBLIC_CHART_NORMAL_UI_PASSIVE_WEBSOCKET",
             "bars":bars}
    store.save_observation(payload,ASOF)
    file=store.file("NASDAQ:AAPL")
    file.write_bytes(file.read_bytes()+b"tampered")
    with pytest.raises(ValueError,match="CHART_STORED_SHA256_MISMATCH"):
        store.save_observation({**payload,"bars":bars[-300:]},ASOF)
    assert file.read_bytes().endswith(b"tampered")


def test_app_does_not_trigger_capture_on_chart_status_read(tmp_path,monkeypatch):
    from tv_mobile_web import server
    monkeypatch.setattr(server,"_history_store",lambda:ChartHistoryStore(tmp_path))
    client=TestClient(server.app)
    assert client.get("/api/chart/status?symbol=NASDAQ%3AAAPL").json()["state"]=="NOT_COLLECTED"
    assert client.get("/api/chart/totals").json()["stored_symbols"]==0
    assert client.get("/api/chart/history?symbol=NASDAQ%3AAAPL").status_code==404
    assert client.get("/api/chart/options").json()["never_auto_collect"] is True


def test_extreme_gaps_cannot_masquerade_as_five_year_data():
    bars=simulated_trading_dates()
    # Real first and last five-year dates, but all the middle years missing.
    sparse=bars[:25]+bars[-300:]
    assessed=evaluate_history(sparse,interval="1D",asof=ASOF,symbol="NASDAQ:AAPL")
    assert assessed["reaches_requested_start"] is True
    assert assessed["reaches_requested_end"] is True
    assert assessed["daily_date_coverage_ratio"]<.30
    assert assessed["five_year_window_covered"] is False
    assert assessed["coverage_status"]=="PARTIAL_HISTORY"


def test_crypto_five_year_calendar_uses_every_day():
    day=five_year_start(ASOF)
    bars=[]
    while day<ASOF:
        t=int(datetime.combine(day,datetime.min.time(),timezone.utc).timestamp()*1000)
        bars.append({"time_ms":t,"open":100.,"high":101.,"low":99.,
                     "close":100.,"volume":100.})
        day+=timedelta(days=1)
    x=evaluate_history(bars,interval="1D",asof=ASOF,symbol="BINANCE:BTCUSDT")
    assert x["calendar_assumption"]=="24x7"
    assert x["daily_date_coverage_ratio"]==1
    assert x["five_year_window_covered"] is True
