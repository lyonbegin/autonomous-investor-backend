"""n8n scenario endpoints: actual step state transitions with synthetic investment events."""
from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.alpha_nodes import scenario_runtime as runtime
from app.alpha_nodes.scenario_catalog import SCENARIOS, catalog
from n8n_scenarios.build_workflows import workflow

client = TestClient(app)
AUTH = {"Authorization": "Bearer n8n-scenario-test-key"}
CALLBACK = {"X-Scenario-Callback-Key": "private-n8n-scenario-secret-of-32-chars"}


@pytest.fixture(autouse=True)
def config(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "n8n-scenario-test-key")
    monkeypatch.setenv("INVESTMENT_SCENARIO_DB_PATH", str(tmp_path / "n8n-scenarios.sqlite"))
    monkeypatch.setenv("INVESTMENT_SCENARIO_CALLBACK_KEY", CALLBACK["X-Scenario-Callback-Key"])
    monkeypatch.setenv("INVESTMENT_SCENARIO_STEP_DELAY_MS", "1")
    monkeypatch.delenv("INVESTMENT_N8N_WEBHOOK_BASE", raising=False)


def post(path, body=None, headers=AUTH):
    return client.post("/api/v1/alpha/scenarios" + path, json=body or {}, headers=headers)


def wait_for(run_id: str, timeout=6):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        response = client.get("/api/v1/alpha/scenarios/runs/" + run_id, headers=AUTH)
        assert response.status_code == 200, response.text
        result = response.json()
        if result["status"] in ("passed", "failed", "cancelled"):
            return result
        time.sleep(.025)
    raise AssertionError("scenario run did not complete: " + run_id)


@pytest.mark.parametrize("scenario_id", list(SCENARIOS))
def test_ten_internal_scenarios_full_end_to_end(scenario_id):
    response = post("/runs", {"scenario_id": scenario_id, "engine": "internal-test"})
    assert response.status_code == 202, response.text
    run = wait_for(response.json()["run_id"])
    assert run["status"] == "passed", (scenario_id, run["error"], run["verification"])
    assert run["engine"] == "internal-test"
    assert run["progress"] == run["total"] == len(SCENARIOS[scenario_id]["steps"])
    assert len(run["events"]) == run["total"]
    assert all(n["state"] == "success" for n in run["nodes"])
    assert all(event["origin"] == "internal-test" for event in run["events"])
    assert all(check["passed"] for check in run["verification"])
    assert run["state"]["live_orders_sent"] == 0
    verified = client.get("/api/v1/alpha/scenarios/runs/" + run["run_id"] + "/verify", headers=AUTH)
    assert verified.status_code == 200
    assert verified.json()["passed"] is True
    events = client.get("/api/v1/alpha/scenarios/runs/" + run["run_id"] + "/events?after=2", headers=AUTH).json()
    assert events["events"][0]["seq"] == 3
    assert len(events["events"]) == run["total"] - 2


def test_all_scenarios_have_real_graph_step_ids_and_ten_workflows():
    doc = catalog()
    assert doc["count"] == 10
    assert len(doc["flows"]) == 10
    for obj in doc["scenarios"]:
        imported = workflow(obj["scenario_id"])
        assert imported["id"] == f'INVESTSCENARIO{obj["scenario_id"]:02d}'
        assert len(imported["nodes"]) == obj["count"] + 1
        assert len(imported["connections"]) == obj["count"]
        assert imported["nodes"][0]["type"] == "n8n-nodes-base.webhook"
        assert imported["nodes"][0]["parameters"]["path"] == f'ai-investment-scenario-{obj["scenario_id"]:02d}'
        assert all(node["type"] == "n8n-nodes-base.httpRequest" for node in imported["nodes"][1:])
        for node, spec in zip(imported["nodes"][1:], obj["nodes"]):
            assert "/steps/" + spec["id"] in node["parameters"]["url"]
            assert node["parameters"]["url"].startswith("=")
            assert node["parameters"]["headerParameters"]["parameters"][0]["value"].startswith("={{")
        assert not any("submit_order" in str(x) or "submit_market_intent" in str(x)
                       for x in imported["nodes"])


def test_auth_required_and_n8n_unconfigured_is_fail_closed():
    assert client.get("/api/v1/alpha/scenarios/catalog").status_code == 401
    assert post("/runs", {"scenario_id": 1, "engine": "n8n"}).status_code == 503
    assert post("/runs", {"scenario_id": 999, "engine": "internal-test"}).status_code == 404
    health = client.get("/api/v1/alpha/scenarios/health", headers=AUTH)
    assert health.status_code == 200 and health.json()["native_trading_enabled"] is False


def _start_mocked_n8n_run(monkeypatch, scenario_id: int):
    monkeypatch.setenv("INVESTMENT_N8N_WEBHOOK_BASE", "http://n8n:5678/webhook")
    monkeypatch.setattr(runtime, "_trigger_n8n", lambda *_: None)
    result = post("/runs", {"scenario_id": scenario_id, "engine": "n8n"})
    assert result.status_code == 202, result.text
    return result.json()["run_id"]


def test_n8n_callback_step_uses_separate_secret_and_enforces_order(monkeypatch):
    run = _start_mocked_n8n_run(monkeypatch, 1)
    path = f"/internal/runs/{run}/steps"
    assert post(path + "/discover", headers=AUTH).status_code == 401
    assert post(path + "/screen", headers=CALLBACK).status_code == 409
    accepted = post(path + "/discover", headers=CALLBACK)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["progress"] == 1
    again = post(path + "/discover", headers=CALLBACK)
    assert again.status_code == 200 and again.json()["idempotent"]
    for item in SCENARIOS[1]["steps"][1:]:
        result = post(path + "/" + item["id"], headers=CALLBACK)
        assert result.status_code == 200, (item["id"], result.text)
    completed = client.get("/api/v1/alpha/scenarios/runs/" + run, headers=AUTH).json()
    assert completed["status"] == "passed"
    assert len(completed["events"]) == len(SCENARIOS[1]["steps"])
    assert all(e["origin"] == "n8n" for e in completed["events"])
    assert not any(e["origin"] == "internal-test" for e in completed["events"])


def test_n8n_callback_engine_mismatch_for_internal_run():
    run = post("/runs", {"scenario_id": 1, "engine": "internal-test"}).json()["run_id"]
    actual = post(f"/internal/runs/{run}/steps/discover", headers=CALLBACK)
    assert actual.status_code == 403


def test_cancel_run_prevents_further_n8n_callbacks(monkeypatch):
    run = _start_mocked_n8n_run(monkeypatch, 2)
    cancel = post("/runs/" + run + "/cancel")
    assert cancel.status_code == 200
    assert post(f"/internal/runs/{run}/steps/new_version", headers=CALLBACK).status_code == 409
    assert client.get("/api/v1/alpha/scenarios/runs/" + run, headers=AUTH).json()["status"] == "cancelled"


def test_critical_scenarios_state_expectations():
    cases = {
        3: lambda st: len(st["orders"]) == 1 and st["reserved"] == 8_000_000,
        4: lambda st: st["orders"]["O1"]["filled"] == 60 and
            st["orders"]["O1"]["reserved"] == 400_000,
        5: lambda st: len(st["jobs"]) == 3 and st["agents"]["A"]["positions"] == 10,
        6: lambda st: st["strategies"]["S101/v1"]["state"] == "SUSPENDED" and
            st["strategies"]["S101/v2"]["state"] == "AVAILABLE",
        7: lambda st: st["orders"]["O1"]["status"] == "ACKED",
        8: lambda st: st["agents"]["A"]["status"] == "FENCED" and
            st["agents"]["C"]["epoch"] > st["agents"]["A"]["epoch"],
        10: lambda st: st["agents"]["B"]["status"] == "IDLE" and
            st["strategies"]["S101/v1"]["state"] == "RETIRED",
    }
    for sid, predicate in cases.items():
        run_id = post("/runs", {"scenario_id": sid, "engine": "internal-test"}).json()["run_id"]
        outcome = wait_for(run_id)
        assert predicate(outcome["state"]), sid


def test_n8n_run_has_no_hidden_internal_fallback(monkeypatch):
    monkeypatch.setenv("INVESTMENT_N8N_WEBHOOK_BASE", "http://127.0.0.1:1/webhook")
    run = post("/runs", {"scenario_id": 1, "engine": "n8n"}).json()["run_id"]
    outcome = wait_for(run)
    assert outcome["status"] == "failed"
    assert "n8n webhook unavailable" in outcome["error"]
    assert outcome["progress"] == 0
    assert outcome["events"] == []
