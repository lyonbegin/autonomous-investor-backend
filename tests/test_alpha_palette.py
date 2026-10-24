"""Visual node palette is derived from the verified real Python function inventory."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.alpha_nodes.inventory import OPERATIONS
from app.alpha_nodes.graph import GraphSpec, compile_graph

client = TestClient(app)
AUTH = {"Authorization": "Bearer node-palette-test"}


def test_palette_has_actual_function_ports_and_risk_gate(monkeypatch):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "node-palette-test")
    r = client.get("/api/v1/alpha/palette", headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["count"] == len(OPERATIONS) == 137
    node = next(x for x in r.json()["nodes"] if x["id"] == "orchestration.orchestration.runtime.plan_rebalance")
    ports = {p["id"]: p for p in node["ports"]}
    assert ports["target"]["direction"] == "input"
    assert ports["target"]["required"]
    assert ports["result"]["direction"] == "output"
    assert node["endpoint"].endswith("/runtime/plan_rebalance/execute")
    blocked = client.get("/api/v1/alpha/palette/nautilus.app.bridge.submit_order", headers=AUTH)
    assert blocked.status_code == 200
    assert blocked.json()["execution_gate"]["state"] == "blocked"
    assert blocked.json()["native_environment_verified"] is False


def test_palette_filters_and_graph_templates_have_valid_native_operation_ids(monkeypatch):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "node-palette-test")
    r = client.get("/api/v1/alpha/palette?engine=tradingview", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["count"] == 10
    assert all(n["role"] == "source" for n in r.json()["nodes"])
    r = client.get("/api/v1/alpha/graphs/templates", headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 3
    for template in r.json()["templates"]:
        graph = GraphSpec.model_validate(template["graph"])
        result = compile_graph(graph)
        assert result["valid"], template["key"]
        assert result["runnable"], template["key"]
    pine = next(x for x in r.json()["templates"] if x["key"] == "tradingview_open_strategy_to_source")
    assert pine["graph"]["nodes"][0]["arguments"]["script_type"] == "strategies"
    ref = pine["graph"]["nodes"][1]["arguments"]["script_id_part"]
    assert ref == {"$node": "strategy_catalog", "path": "result.items.0.script_id_part"}


def test_palette_is_authenticated(monkeypatch):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "node-palette-test")
    assert client.get("/api/v1/alpha/palette").status_code == 401
    assert client.get("/api/v1/alpha/graphs/templates").status_code == 401
