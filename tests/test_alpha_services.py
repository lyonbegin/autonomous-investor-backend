"""Existing TradingView/Quant service entry points are real API boundaries."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.alpha_nodes import services
from app.alpha_nodes.inventory import OPERATIONS

client = TestClient(app)
AUTH = {"Authorization": "Bearer alpha-services-test"}


@pytest.fixture(autouse=True)
def auth(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "alpha-services-test")
    monkeypatch.setenv("ALPHA_GRAPH_DB_PATH", str(tmp_path / "service-graph.sqlite3"))
    monkeypatch.delenv("ALPHA_ALLOW_QUANT_WRITES", raising=False)


def native_call(name, payload):
    operation = next(x for x in OPERATIONS if x["id"] == name)
    return client.post(operation["endpoint"], headers=AUTH, json={"arguments": payload})


def test_real_service_modules_are_exposed_as_individual_native_function_urls():
    tv = [op for op in OPERATIONS if op["engine"] == "tradingview" and op["source"] == "service"]
    qt = [op for op in OPERATIONS if op["engine"] == "quantlab" and op["source"] == "service"]
    assert len(tv) == 10
    assert len(qt) == 10
    assert len(OPERATIONS) == 137
    assert {op["module"] for op in tv + qt} == {"api"}
    for op in tv + qt:
        assert op["endpoint"] in app.openapi()["paths"]


def test_tradingview_script_catalog_uses_verified_remote_path(monkeypatch):
    called = []
    def fake(service, path, *, query=None, method="GET", body=None):
        called.append((service, path, query, method))
        return {"items": [{"script_id_part": "open-123"}], "count": 1}
    monkeypatch.setattr(services, "_request", fake)
    result = native_call("tradingview.service.api.script_catalog", {"limit": 3, "script_type": "strategies"})
    assert result.status_code == 200, result.text
    assert result.json()["result"]["items"][0]["script_id_part"] == "open-123"
    assert called == [("tradingview", "/api/v1/tradingview/scripts/catalog",
                       {"limit": 3, "offset": 0, "script_type": "strategies"}, "GET")]


def test_quant_history_inputs_forward_to_existing_api(monkeypatch):
    calls = []
    def fake(service, path, *, query=None, method="GET", body=None):
        calls.append({"service": service, "path": path, "query": query})
        return {"bars": [{"timestamp": 1, "close": 100}], "provider": "test"}
    monkeypatch.setattr(services, "_request", fake)
    r = native_call("quantlab.service.api.quant_market_history",
                    {"symbol": "NASDAQ:AAPL", "horizon": "1d", "market": "america"})
    assert r.status_code == 200, r.text
    assert calls[0]["path"] == "/api/v1/quant/market-data/history"
    assert calls[0]["query"]["symbol"] == "NASDAQ:AAPL"
    assert r.json()["result"]["provider"] == "test"


def test_quant_execution_requires_separate_explicit_approval(monkeypatch):
    intercepted = []
    def fake(service, path, *, query=None, method="GET", body=None):
        intercepted.append((service, path, method, body))
        return {"experiment_id": "X1", "status": "READY"}
    monkeypatch.setattr(services, "_request", fake)
    args = {"experiment_id": "X1"}
    r = native_call("quantlab.service.api.quant_experiment_run", args)
    assert r.status_code == 403 and not intercepted
    monkeypatch.setenv("ALPHA_ALLOW_QUANT_WRITES", "true")
    r = native_call("quantlab.service.api.quant_experiment_run", args)
    assert r.status_code == 200, r.text
    assert intercepted[0][1] == "/api/v1/quant/experiments/X1/run"
    assert intercepted[0][2] == "POST"
    assert intercepted[0][3]["max_symbols"] == 5


def test_service_graph_binds_script_id_from_catalog_to_source(monkeypatch):
    calls = []
    def fake(service, path, *, query=None, method="GET", body=None):
        calls.append(path)
        if path == "/api/v1/tradingview/scripts/catalog":
            return {"items": [{"script_id_part": "open-456"}], "count": 1}
        if path == "/api/v1/tradingview/scripts/open-456/source":
            return {"ok": True, "script_id": "open-456", "source": "//@version=6"}
        raise AssertionError("unexpected service route " + path)
    monkeypatch.setattr(services, "_request", fake)
    graph = {
        "name": "TradingView script selection to Pine source — real API handler boundary",
        "background": False,
        "nodes": [
            {"id": "catalog", "operation_id": "tradingview.service.api.script_catalog",
             "arguments": {"limit": 1, "script_type": "strategies"}},
            {"id": "source", "operation_id": "tradingview.service.api.script_source",
             "arguments": {"script_id_part": {"$node": "catalog", "path": "result.items.0.script_id_part"}}}
        ],
    }
    r = client.post("/api/v1/alpha/graphs/run", headers=AUTH, json=graph)
    assert r.status_code == 200, r.text
    response = r.json()
    assert response["status"] == "completed", response
    assert response["nodes"][1]["output"]["result"]["source"] == "//@version=6"
    assert calls == ["/api/v1/tradingview/scripts/catalog",
                     "/api/v1/tradingview/scripts/open-456/source"]


def test_remote_origin_config_blocks_arbitrary_http_hosts(monkeypatch):
    monkeypatch.setenv("ALPHA_TRADINGVIEW_BASE", "http://untrusted.example.com")
    with pytest.raises(ValueError, match="HTTPS"):
        services._base("tradingview")


def test_external_identifier_cannot_override_remote_api_path():
    with pytest.raises(ValueError):
        services._segment("..")
    assert services._segment("SOME/ID") == "SOME%2FID"
