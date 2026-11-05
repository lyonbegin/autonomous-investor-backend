"""10-row, random-access server pagination. Nothing is truncated in storage.

Use 249 ISO countries, 417 source fixture records and >2,340 saved market
paths so users can jump directly to page 234 with no preceding page fetch.
Fixture provider names and market paths are not live TradingView quotes.
"""
from fastapi.testclient import TestClient

from tv_mobile_web import server
from tv_mobile_web.market_taxonomy import MarketTaxonomyStore
from tv_mobile_web.market_page_graph import WorldMarketPageGraph, ROOT

client=TestClient(server.app)


def test_overview_metadata_contains_no_full_list(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"_taxonomy_store",lambda:MarketTaxonomyStore(tmp_path))
    r=client.get("/api/taxonomy/overview")
    assert r.status_code==200,r.text
    d=r.json()
    assert len(d["categories"])==9
    assert d["country_total"]>=249
    assert d["listing_page_size"]==10
    assert "countries" not in d
    assert "tradingview_source_records" not in d
    assert d["all_5y_daily_collected"] is False


def test_iso_country_server_pagination_and_direct_last_page():
    first=client.get("/api/taxonomy/countries?page=1").json()
    second=client.get("/api/taxonomy/countries?page=2").json()
    last=client.get("/api/taxonomy/countries?page=25").json()
    assert first["page"]==1
    assert first["page_size"]==10
    assert first["total_count"]>=249
    assert len(first["items"])==10
    assert len(second["items"])==10
    assert first["items"]!=second["items"]
    assert len(last["items"])==9
    assert last["total_pages"]==25
    assert client.get("/api/taxonomy/countries?page=0").status_code==422
    assert client.get("/api/taxonomy/countries?page=234").json()["items"]==[]
    filtered=client.get("/api/taxonomy/countries?q=Korea&page=1").json()
    assert filtered["total_count"]>=2
    assert all("korea" in item["name"].lower() for item in filtered["items"])


def test_provider_417_rows_preserved_but_response_contains_only_10(tmp_path,monkeypatch):
    store=MarketTaxonomyStore(tmp_path)
    html="<table><tr><th>Data source</th><th>Price</th></tr>"
    html+="".join(f"<tr><th>Venue {i:03d} Stocks</th><td>Free</td></tr>"
                  for i in range(417))
    html+="</table>"
    store.save(html)
    monkeypatch.setattr(server,"_taxonomy_store",lambda:store)
    p1=client.get("/api/taxonomy/sources?page=1").json()
    p4=client.get("/api/taxonomy/sources?page=4").json()
    p42=client.get("/api/taxonomy/sources?page=42").json()
    assert p1["total_matches"]==417
    assert p1["page_size"]==10
    assert p1["total_pages"]==42
    assert len(p1["items"])==10
    assert len(p4["items"])==10
    assert p4["items"][0]["display"]=="Venue 030 Stocks"
    assert len(p42["items"])==7
    assert p42["items"][-1]["display"]=="Venue 416 Stocks"
    assert store.read()["raw_row_count"]==417
    assert client.get("/api/taxonomy/sources?page=0").status_code==422


def test_market_links_can_jump_directly_to_page_234_without_prefetching(tmp_path,monkeypatch):
    graph=WorldMarketPageGraph(tmp_path)
    items=[(f"/markets/test-{i:05d}/",f"Market {i:05d}")
           for i in range(2500)]
    graph.store_result(ROOT,200,items)
    monkeypatch.setattr(server,"_market_graph",lambda:graph)
    p=client.get("/api/taxonomy/pages?limit=10&page=234").json()
    assert p["total_count"]>=2500
    assert p["page"]==234
    assert p["page_size"]==10
    assert p["total_pages"]>=250
    assert len(p["items"])==10
    first=client.get("/api/taxonomy/pages?limit=10&page=1").json()
    assert len(first["items"])==10
    assert p["items"]!=first["items"]
    assert graph.status()["discovered_pages"]>=2500
    assert graph.status()["manual_click_only"] is True


def test_market_scanner_default_size_10_without_source_rewrite(monkeypatch):
    from unittest.mock import AsyncMock
    mock=AsyncMock(return_value={
       "items":[{"ticker":f"NASDAQ:S{i}"} for i in range(10)],
       "total_count":2450,
    })
    monkeypatch.setattr(server,"_tv_get",mock)
    p=client.get("/api/markets/america?offset=2330")
    assert p.status_code==200
    assert p.json()["limit"]==10
    assert len(p.json()["items"])==10
    assert mock.call_args.args[1]["limit"]==10
    assert mock.call_args.args[1]["offset"]==2330
