"""End-to-end no-truncation contracts for full TradingView world taxonomy.

Fixtures stand in for official HTML only in tests; no fixture prices are
presented as actual TradingView market data.
"""
import pytest
from fastapi.testclient import TestClient

from tv_mobile_web import server
from tv_mobile_web.market_taxonomy import (
    TYPES, FACETS, MarketTaxonomyStore, build_catalog, countries, hierarchy,
)

SAMPLE_HTML = """<html><body><table>
<thead><tr><th>Data source</th><th>Delayed data</th><th>Real time</th></tr></thead>
<tbody>
<tr><td>Korea Stock Exchange Stocks Funds KRX South Korea</td><td>20 min</td><td>optional</td></tr>
<tr><td>CME Group Futures Options CME USA</td><td>10 min</td><td>optional</td></tr>
<tr><td>Unclassified venue XYZ</td><td>N/A</td><td>N/A</td></tr>
</tbody></table></body></html>"""


def test_nine_types_and_every_cross_asset_facet_are_not_suppressed():
    assert len(TYPES) == 9
    assert {x[0] for x in TYPES} == {
        "stocks","funds","futures","forex","crypto",
        "indices","bonds","options","economy",
    }
    assert len(FACETS)==3
    assert {"commodities","derivatives","calendars"} == {x[0] for x in FACETS}
    assert next(x for x in TYPES if x[0]=="options")[3]
    assert next(x for x in TYPES if x[0]=="economy")[3]


def test_entire_iso_country_scope_retained_and_not_claimed_as_supported():
    result = countries()
    assert len(result)>=249
    assert len(result)==len({x["iso2"] for x in result})
    for code in ("KR","US","JP","IN","BR","DE","ZA","AE","AQ","NZ"):
        assert code in {x["iso2"] for x in result}
    assert all(c["tradingview_source_status"]=="NOT_YET_VERIFIED" for c in result)


def test_all_coverage_source_rows_preserved_including_unclassified():
    snapshot = build_catalog(SAMPLE_HTML,retrieved_at="2026-11-05T00:00:00Z")
    assert snapshot["raw_row_count"] == 3
    assert snapshot["source_row_count_confirmed_complete"] is False
    assert len(snapshot["records"]) == 3
    assert "Unclassified venue" in snapshot["records"][2]["display"]
    assert snapshot["records"][2]["asset_type_candidate_ids"] == []
    assert "options" in snapshot["records"][1]["asset_type_candidate_ids"]
    assert "stocks" in snapshot["records"][0]["asset_type_candidate_ids"]


def test_manual_store_persists_every_original_row_without_cropping(tmp_path):
    store = MarketTaxonomyStore(tmp_path)
    initial=store.read()
    assert initial["raw_row_count"]==0
    assert initial["source_refresh_state"]=="NOT_REQUESTED"
    saved=store.save(SAMPLE_HTML)
    assert saved["raw_row_count"]==3
    again=store.read()
    assert again["records"]==saved["records"]
    assert again["source_refresh_state"]=="SOURCE_SNAPSHOT_STORED"
    full=hierarchy(again)
    assert len(full["categories"])==9
    assert len(full["countries"])>=249
    assert full["source_row_count"]==3
    assert len(full["tradingview_source_records"])==3
    assert full["all_exchanges_verified"] is False
    assert full["all_tradingview_symbols_collected"] is False
    assert full["all_5y_daily_collected"] is False
    assert full["automation_cron_enabled"] is False


def test_no_source_rows_cannot_overwrite_good_snapshot(tmp_path):
    store=MarketTaxonomyStore(tmp_path)
    store.save(SAMPLE_HTML)
    previous=store.read()
    with pytest.raises(ValueError,match="COVERAGE_SITE_NO_PARSEABLE_RECORDS"):
        store.save("<html><body><h1>No source records available</h1></body></html>")
    assert store.read()["records"]==previous["records"]


def test_taxonomy_read_never_fetches_original_market_site(tmp_path,monkeypatch):
    store=MarketTaxonomyStore(tmp_path)
    monkeypatch.setattr(server,"_taxonomy_store",lambda:store)
    client=TestClient(server.app)
    response=client.get("/api/taxonomy")
    assert response.status_code==200
    obj=response.json()
    assert len(obj["categories"])==9
    assert len(obj["countries"])>=249
    assert obj["source_refresh_state"]=="NOT_REQUESTED"
    assert obj["source_row_count"]==0
    assert client.get("/api/taxonomy/source-status").json()["manual_only"] is True
    assert store.snapshot_path.is_file() is False


def test_manual_source_refresh_requires_click_not_admin_token(tmp_path,monkeypatch):
    store=MarketTaxonomyStore(tmp_path)
    monkeypatch.setattr(server,"_taxonomy_store",lambda:store)
    monkeypatch.setattr(server,"_last_manual_taxonomy_attempt",None)
    async def mock_refresh():
        return store.save(SAMPLE_HTML)
    monkeypatch.setattr(store,"refresh",mock_refresh)
    client=TestClient(server.app)
    assert client.get("/api/taxonomy").json()["source_row_count"]==0
    refreshed=client.post("/api/taxonomy/refresh")
    assert refreshed.status_code==200,refreshed.text
    assert refreshed.json()["records_preserved"]==3
    assert refreshed.json()["no_cron"] is True
    assert client.get("/api/taxonomy").json()["source_row_count"]==3
    # Public testing UI uses no login, but has a short upstream cooldown.
    assert client.post("/api/taxonomy/refresh").status_code==429



def test_shorter_source_snapshot_preserves_previous_provider_rows(tmp_path):
    store=MarketTaxonomyStore(tmp_path)
    previous=store.save(SAMPLE_HTML)
    shorter="""<table><tr><th>Data source</th></tr>
        <tr><td>Korea Stock Exchange Stocks Funds KRX South Korea</td></tr>
        </table>"""
    result=store.save(shorter,expansion={
        "attempted":True,"success":False,"reason":"SHOW_ALL_NOT_AVAILABLE",
    })
    assert result["latest_source_row_count"]==1
    assert result["earlier_source_rows_preserved"]==2
    assert result["raw_row_count"]==3
    old=[x for x in result["records"] if not x["seen_in_latest_source"]]
    assert len(old)==2
    assert all(x["historical_snapshot_only"] for x in old)
    assert store.read()["raw_row_count"]==3


def test_playwright_expanded_html_preferred_when_more_rows(tmp_path,monkeypatch):
    """Real site UI access is not used in tests; expansion metadata explicit."""
    import httpx
    store=MarketTaxonomyStore(tmp_path)
    first="""<table><tr><th>Data source</th></tr>
        <tr><td>Source A Stocks USA</td></tr></table>"""
    expanded="""<table><tr><th>Data source</th></tr>
        <tr><td>Source A Stocks USA</td></tr>
        <tr><td>Source B Options USA</td></tr>
        <tr><td>Source C Crypto Global</td></tr></table>"""
    class Resp:
        status_code=200
        text=first
        headers={"content-type":"text/html"}
        def raise_for_status(self):pass
    async def fake_get(self,url,*args,**kwargs):
        assert url=="https://www.tradingview.com/data-coverage/"
        return Resp()
    async def fake_expand(baseline):
        assert baseline==first
        return expanded,{"attempted":True,"success":True,
                         "initial_html_rows":1,"expanded_html_rows":3,
                         "show_all_clicked":True}
    monkeypatch.setattr(httpx.AsyncClient,"get",fake_get)
    monkeypatch.setattr(store,"_expand_page_via_ui",fake_expand)
    import asyncio
    r=asyncio.run(store.refresh())
    assert r["raw_row_count"]==3
    assert r["latest_source_row_count"]==3
    assert r["ui_expansion"]["show_all_clicked"] is True
    assert r["ui_expansion"]["success"] is True
    assert any(x["display"].startswith("Source B") for x in r["records"])
