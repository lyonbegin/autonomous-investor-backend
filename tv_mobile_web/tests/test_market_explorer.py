"""Global multi-asset UI data contracts, with no fabricated production prices."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from tv_mobile_web import server
from tv_mobile_web.chart_store import ChartHistoryStore
from tv_mobile_web.market_explorer import RANKINGS, SUPPORTED_MARKETS

client = TestClient(server.app)


def test_catalog_covers_all_existing_scanner_asset_classes():
    response = client.get("/api/explore/catalog")
    assert response.status_code == 200
    data = response.json()
    assert len(data["categories"]) == 7
    classes = {r["asset_class"] for r in data["categories"]}
    assert classes == {"equity", "etf", "crypto", "fx", "futures", "bonds", "indices"}
    assert data["scanner_market_count"] == len(SUPPORTED_MARKETS) == 14
    assert data["verified_global_full_listings"] is False
    assert data["scheduled_collection_enabled"] is False
    assert all(set(m["markets"]) <= SUPPORTED_MARKETS for m in data["categories"])


def test_stored_market_returns_only_existing_source_rows(monkeypatch):
    mock = AsyncMock(return_value={
        "items": [{"ticker": "NASDAQ:AAPL", "close": 150.75,
                   "sector": "Electronic Technology"}],
        "total_count": 8899,
    })
    monkeypatch.setattr(server, "_tv_get", mock)
    result = client.get("/api/explore/stored/america?limit=100&offset=300")
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["items"][0]["close"] == 150.75
    assert data["total_count"] == 8899
    assert data["complete_universe_verified"] is False
    args = mock.call_args.args
    assert args[0] == "/api/v1/tradingview/markets/america/stored"
    assert args[1]["limit"] == 100
    assert args[1]["offset"] == 300


@pytest.mark.parametrize("url", [
    "/api/explore/stored/nonexistent",
    "/api/explore/stored/etf?limit=10000",
    "/api/explore/ranking/unknown/volume",
    "/api/explore/ranking/forex/impossible",
    "/api/explore/search?q=A",
    "/api/explore/search?q=Apple&pages_per_market=999",
])
def test_invalid_global_queries_are_rejected(url):
    assert client.get(url).status_code in (404, 422)


@pytest.mark.parametrize("ranking,sort_field,direction", [
    ("volume", "volume", "desc"),
    ("gainers", "change", "desc"),
    ("losers", "change", "asc"),
    ("volatility", "Volatility.D", "desc"),
    ("market_cap", "market_cap_basic", "desc"),
])
def test_market_ranking_uses_source_sort_not_fake_computation(
    monkeypatch, ranking, sort_field, direction,
):
    mock = AsyncMock(return_value={
        "items": [{"ticker": "NASDAQ:AAPL", "change": 2.5}],
        "total_count": 2000,
        "source": "REAL_TEST_FIXTURE",
    })
    monkeypatch.setattr(server, "_tv_get", mock)
    value = client.get(f"/api/explore/ranking/america/{ranking}").json()
    assert value["items"][0]["change"] == 2.5
    assert value["all_markets_exhaustive"] is False
    assert mock.call_args.args[1]["sort_by"] == sort_field
    assert mock.call_args.args[1]["sort_order"] == direction


def test_cross_market_search_reports_unsearched_pages(monkeypatch):
    async def fake_fetch(path, params):
        if "/america/" in path:
            return {"items": [
                {"ticker": "NASDAQ:AAPL", "description": "Apple"},
                {"ticker": "NASDAQ:MSFT", "description": "Microsoft"},
            ]}
        return {"items": []}
    monkeypatch.setattr(server, "_tv_get", fake_fetch)
    result = client.get("/api/explore/search?q=AAPL&market=america")
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["items"][0]["ticker"] == "NASDAQ:AAPL"
    assert value["partial_search"] is False
    assert value["worldwide_complete"] is False
    assert value["prices_automatically_downloaded"] is False


def test_search_matching_full_page_discloses_partial_universe(monkeypatch):
    rows = [{"ticker": f"NASDAQ:ALPHA{i:04}", "name": "ABC"} for i in range(1000)]
    mock = AsyncMock(return_value={"items": rows, "total_count": 100000})
    monkeypatch.setattr(server, "_tv_get", mock)
    result = client.get("/api/explore/search?q=ALPHA&market=america&limit=20").json()
    assert len(result["items"]) == 20
    assert result["matches_in_scanned_pages"] == 1000
    assert result["partial_search"] is True
    assert result["markets"][0]["rows_scanned"] == 1000


def test_detail_joins_existing_row_and_actual_history_status(tmp_path, monkeypatch):
    async def mock(path, params):
        return {"items": [{"ticker": "NASDAQ:AAPL", "close": 142.91,
                            "RSI": 61, "sector": "Hardware"}]}
    monkeypatch.setattr(server, "_tv_get", mock)
    monkeypatch.setattr(server, "_history_store", lambda: ChartHistoryStore(tmp_path))
    data = client.get("/api/explore/symbol?market=america&symbol=NASDAQ%3AAAPL").json()
    assert data["fundamentals"]["close"] == 142.91
    assert data["five_year_daily"]["state"] == "NOT_COLLECTED"
    assert data["no_synthetic_fundamentals"] is True
    assert data["scan_is_exhaustive"] is True


def test_source_errors_never_become_prices(monkeypatch):
    async def offline(path, params):
        raise server.HTTPException(502, "EXISTING_UPSTREAM_OFFLINE")
    monkeypatch.setattr(server, "_tv_get", offline)
    r = client.get("/api/explore/search?q=APPLE&market=america")
    assert r.status_code == 200
    obj = r.json()
    assert obj["items"] == []
    assert obj["markets"][0]["errors"]
    assert obj["partial_search"] is True
