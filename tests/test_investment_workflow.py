"""Investment workflow executes actual DAG dependencies, never just painted lines."""
from __future__ import annotations

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.alpha_nodes import investment_flow as flow

client = TestClient(app)
AUTH = {"Authorization": "Bearer investment-workflow-api-tests"}
BASE = "/api/v1/alpha/investment"


@pytest.fixture(autouse=True)
def config(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "investment-workflow-api-tests")
    monkeypatch.setenv("INVESTMENT_FLOW_DB_PATH", str(tmp_path / "test-invest.sqlite3"))
    monkeypatch.setenv("INVESTMENT_FLOW_PARALLELISM", "3")
    monkeypatch.delenv("ALPHA_ALLOW_RESEARCH", raising=False)
    monkeypatch.delenv("ALPHA_ALLOW_TRAINING", raising=False)


def post(uri, payload=None):
    return client.post(BASE + uri, json=payload or {}, headers=AUTH)


def definition(join="ALL", quorum=1):
    return {
        "name": "Two independent analysts, one Nautilus workflow join",
        "nodes": [
            {"id": "a", "operation_id": "control.identity", "arguments": {"value": 10}},
            {"id": "b", "operation_id": "control.identity", "arguments": {"value": 20}},
            {"id": "c", "operation_id": "control.join", "join": join, "quorum": quorum},
        ],
        "edges": [
            {"id": "a_c", "source": "a", "target": "c",
             "target_input": "first", "output_path": "result.value"},
            {"id": "b_c", "source": "b", "target": "c",
             "target_input": "second", "output_path": "result.value"},
        ],
    }


def create_and_run(definition, mode="dry_run"):
    created = post("/workflows", definition)
    assert created.status_code == 201, created.text
    ident = created.json()["workflow_id"]
    if mode == "research":
        publish_response = post(f"/workflows/{ident}/versions/1/publish")
        assert publish_response.status_code == 200, publish_response.text
    out = post(f"/workflows/{ident}/runs", {"mode": mode})
    assert out.status_code == 200, out.text
    return ident, out.json()


def node_states(out):
    return {n["node_id"]: n["state"] for n in out["nodes"]}


def test_twelve_engines_and_137_function_nodes_preserved():
    response = client.get(BASE + "/node-types", headers=AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["engine_count"] == 12
    assert payload["native_functions"] == 137
    assert payload["count"] == 140
    nautilus = client.get(BASE + "/node-types?engine=nautilus", headers=AUTH).json()
    assert nautilus["count"] >= 10
    assert any(x["operation_id"] == "nautilus.app.bridge.submit_order"
               and x["execution"] != "ready" for x in nautilus["nodes"])


def test_parallel_analysts_join_with_real_data_bindings():
    _, result = create_and_run(definition())
    assert result["state"] == "completed", json.dumps(result, ensure_ascii=False)
    assert node_states(result) == {"a": "success", "b": "success", "c": "success"}
    join = next(n for n in result["nodes"] if n["node_id"] == "c")
    assert join["inputs"] == {"first": 10, "second": 20}
    assert join["output"]["result"]["received"] == {"first": 10, "second": 20}
    assert result["events"] and result["snapshot_sha256"]


def test_graph_truly_runs_independent_nodes_in_parallel(monkeypatch):
    original = flow._call
    mutex = threading.Lock()
    occupancy = {"active": 0, "peak": 0}
    def slow(node, incoming, outcomes, mode):
        if node.id in ("a", "b"):
            with mutex:
                occupancy["active"] += 1
                occupancy["peak"] = max(occupancy["peak"], occupancy["active"])
            time.sleep(0.12)
            with mutex:
                occupancy["active"] -= 1
        return original(node, incoming, outcomes, mode)
    monkeypatch.setattr(flow, "_call", slow)
    _, result = create_and_run(definition())
    assert result["state"] == "completed"
    assert occupancy["peak"] == 2


def test_version_save_publish_and_optimistic_conflict():
    made = post("/workflows", definition()).json()
    wid = made["workflow_id"]
    updated = client.put(BASE + f"/workflows/{wid}", headers=AUTH,
                         json={"expected_version": 1, "definition": definition("ANY")})
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    old = client.get(BASE + f"/workflows/{wid}?version=1", headers=AUTH).json()
    assert old["definition"]["nodes"][2]["join"] == "ALL"
    conflict = client.put(BASE + f"/workflows/{wid}", headers=AUTH,
                          json={"expected_version": 1, "definition": definition("ALL")})
    assert conflict.status_code == 409
    pub = post(f"/workflows/{wid}/versions/2/publish")
    assert pub.status_code == 200 and pub.json()["published_version"] == 2
    assert client.get(BASE + f"/workflows/{wid}", headers=AUTH).json()["published_version"] == 2


def test_ANY_ignores_failed_optional_branch_and_keeps_downstream():
    g = definition("ANY")
    g["nodes"][1]["optional"] = True
    original = flow._call
    def synthetic_failure(node, incoming, outcomes, mode):
        if node.id == "b":
            raise ValueError("one independent source is unavailable")
        return original(node, incoming, outcomes, mode)
    flow._call = synthetic_failure
    try:
        _, result = create_and_run(g)
    finally:
        flow._call = original
    assert node_states(result)["a"] == "success"
    assert node_states(result)["b"] == "failed"
    assert node_states(result)["c"] == "success"
    assert result["state"] == "completed"


def test_QUORUM_two_of_three_and_all_settled():
    g = definition("QUORUM", 2)
    g["nodes"].append({"id": "d", "operation_id": "control.identity", "optional": True})
    g["edges"].append({"id": "d_c", "source": "d", "target": "c",
                       "target_input": "third", "output_path": "result"})
    original = flow._call
    def failure(node, incoming, outcomes, mode):
        if node.id == "d":
            raise RuntimeError("optional failed")
        return original(node, incoming, outcomes, mode)
    flow._call = failure
    try:
        _, result = create_and_run(g)
    finally:
        flow._call = original
    assert result["state"] == "completed"
    assert node_states(result)["c"] == "success"
    g["nodes"][2]["join"] = "ALL_SETTLED"
    flow._call = failure
    try:
        _, result2 = create_and_run(g)
    finally:
        flow._call = original
    assert node_states(result2)["c"] == "success"


def test_FAILED_required_branch_blocks_only_its_downstream():
    g = definition()
    g["nodes"].append({"id": "unrelated", "operation_id": "control.identity"})
    original = flow._call
    def broken(node, incoming, outcomes, mode):
        if node.id == "a":
            raise ValueError("upstream failure")
        return original(node, incoming, outcomes, mode)
    flow._call = broken
    try:
        _, result = create_and_run(g)
    finally:
        flow._call = original
    assert node_states(result) == {"a": "failed", "b": "success",
                                   "c": "skipped", "unrelated": "success"}
    assert result["state"] == "partial_failure"


def test_condition_branch_deactivates_irrelevant_path():
    g = definition("ANY")
    g["edges"][0]["when"] = {"path": "result.value", "op": "gt", "value": 100}
    _, result = create_and_run(g)
    assert node_states(result)["c"] == "success"
    join = next(n for n in result["nodes"] if n["node_id"] == "c")
    assert join["inputs"] == {"second": 20}


def test_manual_approval_pauses_and_resumes_on_human_action():
    g = definition()
    g["nodes"].append({"id": "approval", "operation_id": "control.approval"})
    g["nodes"].append({"id": "after", "operation_id": "control.identity"})
    g["edges"].extend([
        {"id": "c_approval", "source": "c", "target": "approval"},
        {"id": "approval_after", "source": "approval", "target": "after"},
    ])
    _, r = create_and_run(g)
    assert r["state"] == "waiting_approval"
    assert node_states(r)["approval"] == "waiting_approval"
    assert node_states(r)["after"] == "waiting"
    approval = post(f'/runs/{r["run_id"]}/nodes/approval/approve',
                    {"approver": "internal-test-operator", "note": "paper only"})
    assert approval.status_code == 200, approval.text
    assert approval.json()["state"] == "completed"
    assert node_states(approval.json())["after"] == "success"
    assert any(e["kind"] == "manual_approval" for e in approval.json()["events"])


def test_unknown_native_operations_and_invalid_edges_are_rejected():
    bad = definition()
    bad["nodes"][0]["operation_id"] = "not.real.engine.method"
    assert post("/workflows/validate", bad).status_code == 422
    bad = definition()
    bad["edges"][0]["source"] = "ghost"
    assert post("/workflows/validate", bad).status_code == 422
    bad = definition()
    bad["edges"].append({"id": "cycle", "source": "c", "target": "a"})
    assert post("/workflows/validate", bad).status_code == 422
    bad = definition()
    bad["edges"][1]["target_input"] = "first"
    assert post("/workflows/validate", bad).status_code == 422


def test_actual_Nautilus_trade_node_is_restricted_even_if_human_approves():
    g = {"name": "Blocked real trade", "nodes": [
        {"id": "trade", "operation_id": "nautilus.app.bridge.submit_market_intent"}]}
    assessment = post("/workflows/validate", g)
    assert assessment.status_code == 200
    assert assessment.json()["warnings"][0]["state"] == "restricted"
    created = post("/workflows", g).json()
    post(f'/workflows/{created["workflow_id"]}/versions/1/publish')
    research = post(f'/workflows/{created["workflow_id"]}/runs', {"mode": "research"})
    assert research.status_code == 403
    assert "submit_market_intent" in str(research.json())


def test_research_mode_invokes_existing_native_rebalance_not_broker():
    target = {"$contract": "TargetPortfolio", "strategy_id": "TEST",
              "as_of": "2026-10-25T00:00:00Z",
              "weights": [{"instrument": "AAPL", "weight": 0.5}]}
    g = {"name": "Nautilus order plan no submission", "nodes": [
        {"id": "plan",
         "operation_id": "orchestration.orchestration.runtime.plan_rebalance",
         "arguments": {"target": target, "equity": 1000, "prices": {"AAPL": 100},
                       "current_quantities": {"AAPL": 1}}}
    ]}
    _, result = create_and_run(g, mode="research")
    assert result["state"] == "completed", result
    assert result["nodes"][0]["output"]["result"][0]["quantity"] == 4


def test_idempotency_same_version_and_key():
    response = post("/workflows", definition()).json()
    wid = response["workflow_id"]
    payload = {"mode": "dry_run", "idempotency_key": "duplicate-request-123"}
    one = post(f"/workflows/{wid}/runs", payload).json()
    two = post(f"/workflows/{wid}/runs", payload).json()
    assert one["run_id"] == two["run_id"]


def test_existing_examples_are_valid_and_no_trade_submitted():
    r = client.get(BASE + "/examples", headers=AUTH)
    assert r.status_code == 200
    for example in r.json()["examples"]:
        assert post("/workflows/validate", example).status_code == 200, example["name"]
        assert all("submit_order" not in str(node) and "submit_market_intent" not in str(node)
                   for node in example["nodes"])


def test_execution_metadata_and_authentication():
    assert client.get(BASE + "/node-types").status_code == 401
    assert client.get(BASE + "/workflows").status_code == 401
    assert client.post(BASE + "/workflows", json=definition()).status_code == 401
    g, r = create_and_run(definition())
    path = BASE + f'/runs/{r["run_id"]}/events'
    response = client.get(path, headers=AUTH)
    assert response.status_code == 200 and response.json()["count"] > 0



def test_native_research_requires_published_workflow():
    wid = post("/workflows", definition()).json()["workflow_id"]
    result = post(f"/workflows/{wid}/runs", {"mode": "research"})
    assert result.status_code == 403
    assert "published" in result.text.lower()


def test_delete_workflow_keeps_completed_run_history():
    wid, run = create_and_run(definition())
    deleted = client.delete(BASE + f"/workflows/{wid}", headers=AUTH)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["historical_run_audit_preserved"] is True
    assert client.get(BASE + f"/workflows/{wid}", headers=AUTH).status_code == 404
    audit = client.get(BASE + f'/runs/{run["run_id"]}', headers=AUTH)
    assert audit.status_code == 200
    assert audit.json()["state"] == "completed"
