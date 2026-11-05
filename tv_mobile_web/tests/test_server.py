"""No network or data faking in production. CI intercepts upstream in explicit tests."""
from __future__ import annotations
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from tv_mobile_web import server

client=TestClient(server.app)


def test_healthy_manual_only():
    value=client.get("/health")
    assert value.status_code==200
    assert value.json()["cron_enabled"] is False
    assert value.json()["collector_enabled"] is False
    assert value.json()["admin_token_required"] is False
    assert value.json()["synthetic_market_data"] is False


def test_full_app_feature_scope_not_reduced_to_markets():
    r=client.get("/api/app/catalog")
    assert r.status_code==200
    data=r.json()
    assert len(data["function_groups"])==26
    assert sum(x["count"] for x in data["function_groups"])==339
    assert data["function_groups"][0]["start"]==1
    assert data["function_groups"][-1]["end"]==339
    assert data["android_runtime_verified"] is False
    assert data["implementation_parity_verified"] is False
    assert len(data["markets"])>=14


def test_front_page_is_real_mobile_shell():
    r=client.get("/")
    assert r.status_code==200
    assert "하단 주요 메뉴" in r.text
    assert "app.js" in r.text


def test_market_lookup_forwards_unchanged_live_rows(monkeypatch):
    mock=AsyncMock(return_value={
        "source":"TradingView scanner","total_count":1000,
        "collected_at":"2026-11-05T08:05:00Z",
        "items":[{"ticker":"NASDAQ:AAPL","description":"Apple Inc.",
                  "close":234.51,"change":1.1,"volume":44444555}],
    })
    monkeypatch.setattr(server,"_tv_get",mock)
    r=client.get("/api/markets/america?limit=40&offset=10&order=volume")
    assert r.status_code==200,r.text
    body=r.json()
    assert body["items"][0]["ticker"]=="NASDAQ:AAPL"
    assert body["items"][0]["close"]==234.51
    assert body["complete_universe_verified"] is False
    assert body["price_history_verified"] is False
    args=mock.call_args
    assert args.args[0]=="/api/v1/tradingview/markets/america"
    assert args.args[1]["offset"]==10


@pytest.mark.parametrize("path",[
    "/api/markets/not-a-market",
    "/api/markets/korea?limit=1000",
    "/api/markets/korea?order=untrusted",
    "/api/markets/korea?offset=-1",
])
def test_invalid_market_requests_rejected(path):
    r=client.get(path)
    assert r.status_code in (404,422),r.text


def test_ideas_existing_upstream_adapter(monkeypatch):
    mock=AsyncMock(return_value={"items":[{"title":"Test fixture"}]})
    monkeypatch.setattr(server,"_tv_get",mock)
    data=client.get("/api/ideas?sort=recent&page=2").json()
    assert data["data"]["items"][0]["title"]=="Test fixture"
    assert data["site_like_or_comment_actions_live"] is False
    assert mock.call_args.args[0]=="/api/v1/tradingview/ideas/live"


def test_market_provider_down_returns_gateway_error_not_fake_prices(monkeypatch):
    async def unavailable(*args,**kwargs):
        import httpx
        raise httpx.ConnectError("fixture offline")
    monkeypatch.setattr(httpx.AsyncClient,"get",unavailable)
    r=client.get("/api/markets/korea")
    assert r.status_code==502
    assert r.json()["detail"]["code"]=="MARKET_SOURCE_UNAVAILABLE"
    assert "items" not in r.json()


def test_static_assets_are_readable():
    for name in ["app.js","style.css"]:
        r=client.get("/assets/"+name)
        assert r.status_code==200
        assert len(r.content)>500


def test_feature_ranges_are_audit_not_impl_success():
    doc=client.get("/api/features").json()
    assert doc["total_candidates"]==339
    assert doc["all_runtime_verified"] is False
    assert all(x["audit"]=="NOT_WEB_PARITY_VERIFIED" for x in doc["feature_ranges"])
