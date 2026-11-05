"""Verify the real market menu crawler preserves ALL discovered categories.

The HTML here is a test fixture. It is never called original live market
coverage or mixed with price history.
"""
import pytest
from fastapi.testclient import TestClient

from tv_mobile_web import server
from tv_mobile_web.market_page_graph import (
    WorldMarketPageGraph, safe_path, discover, ROOT,
)

PAGE = """<!doctype html><html><head><title>Test Markets</title></head>
<body><main>
<a href="/markets/stocks-korea/">한국 주식</a>
<a href="/markets/stocks-usa/">United States stocks</a>
<a href="/markets/cryptocurrencies/">암호화폐</a>
<a href="/markets/futures/energy/">에너지 선물</a>
<a href="/markets/options/">옵션</a>
<a href="/markets/economy/">경제 지표</a>
<a href="/markets/stocks-usa/?sort=volume">거래량별 미국 주식</a>
<a href="/markets/strange-new-category/">새로운 미등록 자산 분류</a>
<a href="https://evil.invalid/markets/secrets/">악성 링크</a>
<a href="/scripts/">전략</a>
</main></body></html>"""


def test_market_path_allowlist_strips_queries_and_rejects_other_hosts():
    assert safe_path("/markets/stocks-usa/?sort=volume")=="/markets/stocks-usa/"
    assert safe_path("https://www.tradingview.com/markets/forex/")=="/markets/forex/"
    assert safe_path("https://evil.invalid/markets/stocks/") is None
    assert safe_path("/scripts/") is None


def test_no_new_market_subcategory_is_silently_discarded():
    links=discover(PAGE,ROOT)
    assert len(links)==8,links
    assert "/markets/strange-new-category/" in {path for path,_ in links}
    assert "/markets/options/" in {path for path,_ in links}
    assert "/markets/economy/" in {path for path,_ in links}
    assert any(label=="새로운 미등록 자산 분류" for _,label in links)


def test_resumable_market_graph_persists_all_nodes_and_backlog(tmp_path):
    graph=WorldMarketPageGraph(tmp_path)
    initial=graph.status()
    assert initial["pending_pages"]>=10
    assert initial["manual_click_only"]
    assert not initial["all_tradingview_asset_categories_complete"]
    links=discover(PAGE,ROOT)
    graph.store_result(ROOT,200,links)
    status=graph.status()
    assert status["fetched_pages"]==1
    assert status["source_edges"]==len(links)
    assert status["discovered_pages"]>=11
    assert not status["public_link_graph_exhausted"]
    rows=graph.get(limit=5000)["items"]
    assert any(x["path"]=="/markets/strange-new-category/" for x in rows)
    assert any(x["path"]=="/markets/stocks-usa/" for x in rows)
    again=WorldMarketPageGraph(tmp_path)
    assert again.status()["discovered_pages"]==status["discovered_pages"]
    assert again.get(query="strange")["total_count"]==1
    assert again.get(limit=1)["has_more"] is True


def test_failed_pages_are_visible_and_require_manual_retry(tmp_path):
    graph=WorldMarketPageGraph(tmp_path)
    graph.store_result("/markets/options/",403,[],error="ACCESS_BLOCKED")
    status=graph.status()
    assert status["failed_pages"]==1
    data=graph.get(query="options")
    assert data["items"][0]["error_code"]=="ACCESS_BLOCKED"
    assert graph.requeue_failed()==1
    assert graph.status()["failed_pages"]==0


def test_graph_api_get_only_reads_local_state(tmp_path,monkeypatch):
    graph=WorldMarketPageGraph(tmp_path)
    monkeypatch.setattr(server,"_market_graph",lambda:graph)
    client=TestClient(server.app)
    status=client.get("/api/taxonomy/pages/status")
    assert status.status_code==200
    assert status.json()["pending_pages"]>=10
    listing=client.get("/api/taxonomy/pages?limit=2&offset=0")
    assert listing.status_code==200
    assert len(listing.json()["items"])==2
    assert listing.json()["has_more"] is True
    assert graph.status()["fetched_pages"]==0


def test_graph_update_has_explicit_manual_limit_and_no_secret(tmp_path,monkeypatch):
    graph=WorldMarketPageGraph(tmp_path)
    monkeypatch.setattr(server,"_market_graph",lambda:graph)
    monkeypatch.setattr(server,"_market_graph_last_attempt",None)

    async def mocked(pages=10,pause_seconds=.45):
        graph.store_result(ROOT,200,discover(PAGE,ROOT))
        return {"processed":[{"path":ROOT,"code":200}],
                "summary":graph.status(),
                "full_content_completeness_verified":False}

    monkeypatch.setattr(graph,"manual_step",mocked)
    client=TestClient(server.app)
    assert client.post("/api/taxonomy/pages/refresh?pages=0").status_code==422
    response=client.post("/api/taxonomy/pages/refresh?pages=1")
    assert response.status_code==200,response.text
    assert response.json()["summary"]["fetched_pages"]==1
    assert response.json()["summary"]["source_edges"]==8
    assert client.post("/api/taxonomy/pages/refresh?pages=1").status_code==429
