"""AlphaForge node API contract tests against actual existing bridge boundaries.

No 12-engine installation, brokerage account, or TradingView token required.
Native mock is used only for isolated routing; production never returns a fake
result when the native package is absent.
"""
from __future__ import annotations

import sys
import types
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.alpha_nodes.inventory import ENGINES, OPERATIONS, build_inventory, module_inventory
from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer node-contract-tests"}


@pytest.fixture(autouse=True)
def _auth(monkeypatch):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "node-contract-tests")
    monkeypatch.delenv("ALPHA_ALLOW_TRAINING", raising=False)
    monkeypatch.delenv("ALPHA_ALLOW_RESEARCH", raising=False)


def post(path, arguments=None, **options):
    return client.post(path, json={"arguments": arguments or {}, **options}, headers=AUTH)


def test_twelve_engine_projects_are_registered():
    r = client.get("/api/v1/alpha/projects", headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 12
    assert {x["engine"] for x in r.json()["projects"]} == set(ENGINES)
    assert all(x["module_count"] == 2 for x in r.json()["projects"])


def test_all_existing_public_app_and_lab_methods_get_distinct_routes():
    assert len(OPERATIONS) >= 75
    assert len(OPERATIONS) == len(build_inventory())
    paths = {x.path for x in app.routes if x.path.startswith("/api/v1/alpha/modules/")}
    for spec in OPERATIONS:
        assert spec["endpoint"] in paths, spec["id"]
    ids = [x["id"] for x in OPERATIONS]
    assert len(ids) == len(set(ids))
    assert all(x["source_path"] and x["inputs"] is not None for x in OPERATIONS)


def test_function_metadata_contains_actual_signature():
    r = client.get("/api/v1/alpha/operations/nautilus.app.bridge.submit_market_intent", headers=AUTH)
    assert r.status_code == 200, r.text
    meta = r.json()
    assert meta["guard"] == "TRADE_BLOCKED"
    assert meta["function"] == "submit_market_intent"
    assert "intent" in {x["name"] for x in meta["inputs"]}
    assert meta["source_line"] > 0


def test_function_execute_requires_valid_token(monkeypatch):
    path = "/api/v1/alpha/modules/orchestration/orchestration/runtime/plan_rebalance/execute"
    assert client.post(path, json={}).status_code == 401
    assert client.post(path, json={}, headers={"Authorization": "Bearer invalid"}).status_code == 401
    monkeypatch.delenv("ALPHA_NODE_API_KEY")
    assert client.post(path, json={}, headers=AUTH).status_code == 503


def test_runtime_rebalance_uses_existing_function_and_contract():
    path = "/api/v1/alpha/modules/orchestration/orchestration/runtime/plan_rebalance/execute"
    target = {
        "$contract": "TargetPortfolio",
        "strategy_id": "PIN-001",
        "as_of": "2026-10-25T00:00:00Z",
        "weights": [{"instrument": "AAPL", "weight": 0.5}],
    }
    r = post(path, {"target": target, "equity": 1000, "prices": {"AAPL": 100},
                    "current_quantities": {"AAPL": 1}})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["status"] == "completed"
    assert payload["result"][0]["instrument"] == "AAPL"
    assert payload["result"][0]["side"] == "buy"
    assert payload["result"][0]["quantity"] == 4.0


def test_native_object_handle_pipes_between_engine_nodes(monkeypatch):
    fake_base = types.ModuleType("vectorbt.portfolio.base")
    class Portfolio:
        @staticmethod
        def from_signals(close, entries, exits, **kwargs):
            assert close == [10, 11, 12]
            return Portfolio()
        def stats(self, **kwargs):
            return {"trades": 2, "origin": "native fake for routing test"}
    fake_base.Portfolio = Portfolio
    for key in ["vectorbt", "vectorbt.portfolio"]:
        monkeypatch.setitem(sys.modules, key, types.ModuleType(key))
    monkeypatch.setitem(sys.modules, "vectorbt.portfolio.base", fake_base)

    created = post("/api/v1/alpha/modules/vectorbt/app/bridge/from_signals/execute",
                   {"close": [10, 11, 12], "entries": [True, False, False],
                    "exits": [False, False, True]})
    assert created.status_code == 200, created.text
    handle = created.json()["result"]["$handle"]
    r = post("/api/v1/alpha/modules/vectorbt/lab/bridge/stats/execute",
             {"portfolio": {"$handle": handle}})
    assert r.status_code == 200, r.text
    assert r.json()["result"]["trades"] == 2


def test_all_native_order_submission_is_disabled():
    for operation in ["nautilus.app.bridge.market_order", "nautilus.app.bridge.submit_order",
                      "nautilus.app.bridge.submit_market_intent",
                      "nautilus.lab.bridge.market_order",
                      "nautilus.lab.bridge.submit_order",
                      "orchestration.orchestration.pipeline.nautilusexecutioncoordinator-submit"]:
        op = next(x for x in OPERATIONS if x["id"] == operation)
        r = post(op["endpoint"], {})
        assert r.status_code == 403, (operation, r.text)


def test_heavy_research_training_requires_explicit_enablement():
    for opid in ["finrobot.app.bridge.research", "rdagent.app.bridge.run",
                 "sb3.app.bridge.learn", "rllib.app.bridge.train"]:
        op = next(x for x in OPERATIONS if x["id"] == opid)
        r = post(op["endpoint"])
        assert r.status_code == 403, (opid, r.text)


def test_validate_pydantic_contracts():
    r = post("/api/v1/alpha/contracts/TargetPortfolio/validate")  # invalid request: no fields
    assert r.status_code == 422
    r = client.post("/api/v1/alpha/contracts/TargetPortfolio/validate",
                    json={"data": {"strategy_id": "X", "as_of": "2026-10-25T01:00:00Z",
                                   "weights": [{"instrument": "A", "weight": 0.5}]}},
                    headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["value"]["weights"][0]["instrument"] == "A"


def test_unavailable_native_module_never_returns_dummy_success(monkeypatch):
    from app.alpha_nodes import runtime
    original_import = runtime.importlib.import_module
    def unavailable(name):
        if name == "app.integrations.vectorbt":
            raise ModuleNotFoundError("missing native engine wrapper")
        return original_import(name)
    monkeypatch.setattr(runtime.importlib, "import_module", unavailable)
    r = post("/api/v1/alpha/modules/vectorbt/app/bridge/from_orders/execute",
             {"close": [100, 101]})
    assert r.status_code == 424, r.text


def test_missing_or_expired_handle_is_explicit_error():
    r = post("/api/v1/alpha/modules/vectorbt/lab/bridge/stats/execute",
             {"portfolio": {"$handle": "not-a-real-handle"}})
    assert r.status_code == 422, r.text
