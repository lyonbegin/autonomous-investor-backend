"""Runnable AlphaForge graphs across EXISTING Python engine functions."""
from __future__ import annotations

import sys
import time
import types

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer node-graph-test"}


@pytest.fixture(autouse=True)
def _config(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "node-graph-test")
    monkeypatch.setenv("ALPHA_GRAPH_DB_PATH", str(tmp_path / "alpha-run.sqlite3"))
    monkeypatch.delenv("ALPHA_ALLOW_RESEARCH", raising=False)
    monkeypatch.delenv("ALPHA_ALLOW_TRAINING", raising=False)


def target():
    return {
        "$contract": "TargetPortfolio",
        "strategy_id": "PINE-TARGET-101",
        "as_of": "2026-10-25T00:00:00Z",
        "weights": [{"instrument": "AAPL", "weight": 0.5}],
    }


def two_nodes(background=False):
    return {
        "name": "Nautilus pre-trade calculation — two real Python bridge calls",
        "background": background,
        "nodes": [
            {
                "id": "first",
                "operation_id": "orchestration.orchestration.runtime.plan_rebalance",
                "arguments": {
                    "target": target(),
                    "equity": 1000, "prices": {"AAPL": 100},
                    "current_quantities": {"AAPL": 1},
                },
            },
            {
                "id": "second",
                "operation_id": "orchestration.orchestration.runtime.plan_rebalance",
                "arguments": {
                    "target": target(),
                    "equity": 5000,
                    "prices": {"AAPL": 100},
                    "min_notional": {"$node": "first", "path": "result.0.notional_delta"},
                },
            },
        ],
    }


def call(path: str, payload):
    return client.post("/api/v1/alpha" + path, json=payload, headers=AUTH)


def test_graph_validation_returns_edges_and_execution_order():
    r = call("/graphs/validate", two_nodes())
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["valid"] and plan["runnable"]
    assert plan["node_count"] == 2
    assert plan["order"] == ["first", "second"]
    assert plan["edges"] == [{"source": "first", "target": "second"}]


def test_graph_executes_two_real_existing_python_functions_and_persists_io():
    r = call("/graphs/run", two_nodes())
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["status"] == "completed", payload
    a, b = payload["nodes"]
    assert [x["status"] for x in (a, b)] == ["completed", "completed"]
    assert a["output"]["result"][0]["quantity"] == 4
    assert b["inputs"]["arguments"]["min_notional"] == 400
    assert b["output"]["result"][0]["quantity"] == 25
    run_id = payload["run_id"]
    assert client.get("/api/v1/alpha/graphs/runs/" + run_id, headers=AUTH).json()["status"] == "completed"
    node = client.get("/api/v1/alpha/graphs/runs/" + run_id + "/nodes/second", headers=AUTH)
    assert node.status_code == 200
    assert node.json()["output"]["result"][0]["instrument"] == "AAPL"
    listing = client.get("/api/v1/alpha/graphs/runs?limit=10", headers=AUTH)
    assert listing.status_code == 200
    assert any(x["run_id"] == run_id for x in listing.json()["runs"])


def test_disallow_cyclic_or_unknown_dependencies():
    cycle = two_nodes()
    cycle["nodes"][0]["depends_on"] = ["second"]
    r = call("/graphs/validate", cycle)
    assert r.status_code == 422
    assert "cycle" in str(r.json()).lower()

    missing = two_nodes()
    missing["nodes"][0]["depends_on"] = ["unknown"]
    assert call("/graphs/validate", missing).status_code == 422

    unknown_op = two_nodes()
    unknown_op["nodes"][0]["operation_id"] = "nautilus.internal.no_such_method"
    assert call("/graphs/validate", unknown_op).status_code == 422


def test_blocked_order_submission_rejected_before_any_node_runs():
    config = two_nodes()
    config["nodes"].append({
        "id": "trade",
        "operation_id": "nautilus.app.bridge.submit_order",
        "arguments": {},
    })
    p = call("/graphs/validate", config)
    assert p.status_code == 200
    assert not p.json()["runnable"]
    assert p.json()["blocked"][0]["node_id"] == "trade"
    r = call("/graphs/run", config)
    assert r.status_code == 403
    assert not client.get("/api/v1/alpha/graphs/runs", headers=AUTH).json()["runs"]


def test_bad_reference_path_stops_flow_and_marks_other_nodes_skipped():
    graph = two_nodes()
    graph["nodes"][1]["arguments"]["min_notional"] = {
        "$node": "first", "path": "result.9999.nonexistent"
    }
    graph["nodes"].append({
        "id": "third",
        "operation_id": "orchestration.orchestration.runtime.plan_rebalance",
        "depends_on": ["second"],
        "arguments": {"target": target(), "equity": 1000, "prices": {"AAPL": 100}},
    })
    r = call("/graphs/run", graph)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["status"] == "failed"
    assert payload["nodes"][0]["status"] == "completed"
    assert payload["nodes"][1]["status"] == "failed"
    assert payload["nodes"][2]["status"] == "skipped"


def test_referenced_python_handle_passes_between_two_distinct_engine_modules(monkeypatch):
    base = types.ModuleType("vectorbt.portfolio.base")
    class FakePortfolio:
        @staticmethod
        def from_signals(close, entries, exits, **kwargs):
            return FakePortfolio()
        def stats(self, **kwargs):
            return {"trade_count": 7}
    base.Portfolio = FakePortfolio
    for mod in ("vectorbt", "vectorbt.portfolio"):
        monkeypatch.setitem(sys.modules, mod, types.ModuleType(mod))
    monkeypatch.setitem(sys.modules, "vectorbt.portfolio.base", base)
    graph = {
        "name": "VectorBT native object flowing from app wrapper to lab wrapper",
        "background": False,
        "nodes": [
            {
                "id": "portfolio",
                "operation_id": "vectorbt.app.bridge.from_signals",
                "arguments": {
                    "close": [10, 11, 12],
                    "entries": [True, False, False],
                    "exits": [False, False, True],
                },
            },
            {
                "id": "performance",
                "operation_id": "vectorbt.lab.bridge.stats",
                "arguments": {"portfolio": {"$node": "portfolio", "path": "result"}},
            },
        ],
    }
    r = call("/graphs/run", graph)
    assert r.status_code == 200, r.text
    response = r.json()
    assert response["status"] == "completed", response
    assert response["nodes"][1]["output"]["result"]["trade_count"] == 7


def test_background_graph_and_poll():
    r = call("/graphs/run", two_nodes(background=True))
    assert r.status_code == 200
    assert r.json()["status"] == "queued"
    run_id = r.json()["run_id"]
    status = None
    for _ in range(30):
        status = client.get(f"/api/v1/alpha/graphs/runs/{run_id}", headers=AUTH).json()
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.04)
    assert status["status"] == "completed", status


def test_graph_endpoints_require_authentication():
    assert client.post("/api/v1/alpha/graphs/validate", json=two_nodes()).status_code == 401
    assert client.post("/api/v1/alpha/graphs/run", json=two_nodes()).status_code == 401
    assert client.get("/api/v1/alpha/graphs/runs").status_code == 401
