"""F01/F03/F05 API-backed persistence, versioning, race safety and audit tests."""
from __future__ import annotations

import concurrent.futures
import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.alpha_nodes import operations_core as ops

CLIENT = TestClient(app)
BASE = "/api/v1/ops"
HEAD = {"Authorization": "Bearer ops-internal-integration-key"}


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHA_NODE_API_KEY", "ops-internal-integration-key")
    monkeypatch.setenv("STRATEGY_OPERATIONS_DB_PATH", str(tmp_path / "operations.db"))


def seed(version="1", title="Public sample TradingView strategy"):
    return ops.ingest(
        {"script_id_part":"public-test-120","name":title,"author":"published-author",
         "script_type":"strategy","script_access":"open","version":version},
        {"ok":True,"source":"//@version=6\nstrategy('Example', overlay=true)\n"},
    )


def approve(version_id):
    response = CLIENT.post(BASE+"/strategies/"+version_id+"/approve",headers=HEAD,json={
        "reviewer":"verified-reviewer",
        "evidence":{"license_reviewed":True,"pine_compiler_passed":True,
                    "independent_backtest_passed":True,
                    "evidence_refs":["internal-research:experiment-TEST-123"]},
    })
    assert response.status_code==200,response.text
    return response.json()


def register(name="worker-a"):
    response=CLIENT.post(BASE+"/agents",headers=HEAD,json={
        "agent_id":name,"market_scope":"US","execution_mode":"paper"})
    assert response.status_code==201,response.text


def test_f01_real_upstream_catalog_source_incremental(monkeypatch):
    calls=[]
    def catalog(limit,offset,script_type):
        assert script_type=="strategies"
        calls.append(("catalog",limit,offset))
        return {"items":[
            {"script_id_part":"TV-A","name":"Alpha","author":"a","script_type":"strategy",
             "script_access":"open","version":"7"},
            {"script_id_part":"TV-B","name":"Only indicator","script_type":"indicator",
             "script_access":"protected","version":"1"},
        ],"total_count":2}
    def source(script_id_part,version):
        calls.append(("source",script_id_part))
        if script_id_part=="TV-A":
            return {"ok":True,"source":"//@version=6\nstrategy('Alpha')",
                    "version":"7","kind":"strategy"}
        return {"ok":False,"protected":True,"reason":"protected"}
    monkeypatch.setattr(ops.services,"script_catalog",catalog)
    monkeypatch.setattr(ops.services,"script_source",source)
    first=CLIENT.post(BASE+"/strategies/sync?limit=10&max_sources=2",headers=HEAD)
    assert first.status_code==200,first.text
    assert first.json()["added"]==2
    assert first.json()["mode"]=="REAL_UPSTREAM_METADATA"
    stored=CLIENT.get(BASE+"/strategies",headers=HEAD).json()["items"]
    assert len(stored)==2
    accessible=next(x for x in stored if x["strategy_id"]=="TV-A")
    assert accessible["eligibility"]=="PENDING_REVIEW"
    assert accessible["source_available"]==1
    protected=next(x for x in stored if x["strategy_id"]=="TV-B")
    assert protected["eligibility"]=="INELIGIBLE"
    second=CLIENT.post(BASE+"/strategies/sync?limit=10&max_sources=2",headers=HEAD)
    assert second.status_code==200
    assert second.json()["added"]==0
    assert calls.count(("source","TV-A"))==2
    with ops.db() as con:
        source_row=con.execute("SELECT * FROM strategy_source_artifacts").fetchone()
        assert source_row["source_text"].startswith("//@version=6")
        assert hashlib.sha256(source_row["source_text"].encode()).hexdigest()==source_row["sha256"]
    events=CLIENT.get(BASE+"/events",headers=HEAD).json()["events"]
    assert sum(e["type"]=="StrategyVersionCreated" for e in events)==2


def test_f01_upstream_failure_is_error_not_fake_strategy(monkeypatch):
    def broken(**kwargs):
        raise ConnectionError("offline upstream")
    monkeypatch.setattr(ops.services,"script_catalog",broken)
    r=CLIENT.post(BASE+"/strategies/sync?limit=1",headers=HEAD)
    assert r.status_code==502
    assert CLIENT.get(BASE+"/strategies",headers=HEAD).json()["count"]==0
    assert CLIENT.get(BASE+"/events",headers=HEAD).json()["events"][-1]["type"]=="SourceSyncFailed"


def test_protected_and_unreviewed_strategy_cannot_be_assigned():
    bad=ops.ingest({"script_id_part":"protected","name":"Locked","script_type":"strategy",
                   "script_access":"protected","version":"1"},
                   {"ok":False,"protected":True})
    register()
    a=CLIENT.post(BASE+"/assignments/claim",headers=HEAD,json={
        "agent_id":"worker-a","version_id":bad["version_id"],"slot_key":"paper:protected"})
    assert a.status_code==409
    before=seed()
    assert CLIENT.post(BASE+"/assignments/claim",headers=HEAD,json={
        "agent_id":"worker-a","version_id":before["version_id"],"slot_key":"paper:public-test-120"
    }).status_code==409
    premature=CLIENT.post(BASE+"/strategies/"+before["version_id"]+"/approve",headers=HEAD,json={
        "reviewer":"verified-reviewer",
        "evidence":{"license_reviewed":True,"pine_compiler_passed":False,
                    "independent_backtest_passed":True,"evidence_refs":["fixture"]}})
    assert premature.status_code==422
    approve(before["version_id"])
    assert CLIENT.get(BASE+"/strategies?status=APPROVED",headers=HEAD).json()["count"]==1


def test_automatic_claim_prevents_double_agent_assignment_across_threads():
    v=seed()
    approve(v["version_id"])
    for agent in ("worker-a","worker-b","worker-c"):
        register(agent)
    def job(_):
        return CLIENT.post(BASE+"/assignments/allocate-one",headers=HEAD).json()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        answers=list(pool.map(job,range(15)))
    assigned=[a for a in answers if a["assigned"]]
    assert len(assigned)==1
    state=CLIENT.get(BASE+"/agents",headers=HEAD).json()
    assert len(state["active_assignments"])==1
    assert state["active_assignments"][0]["epoch"]==1
    assert CLIENT.get(BASE+"/overview",headers=HEAD).json()["active_assignments"]==1


def test_fencing_heartbeat_and_reconciled_release():
    v=seed()
    approve(v["version_id"])
    register()
    result=CLIENT.post(BASE+"/assignments/claim",headers=HEAD,json={
        "agent_id":"worker-a","version_id":v["version_id"],
        "slot_key":"paper:public-test-120","lease_seconds":90})
    assert result.status_code==201,result.text
    assignment=result.json()
    aid=assignment["assignment_id"]
    assert CLIENT.post(BASE+f"/assignments/{aid}/heartbeat",headers=HEAD,json={
        "epoch":2,"lease_seconds":90}).status_code==409
    assert CLIENT.post(BASE+f"/assignments/{aid}/heartbeat",headers=HEAD,json={
        "epoch":1,"lease_seconds":90}).status_code==200
    assert CLIENT.post(BASE+f"/assignments/{aid}/release",headers=HEAD,json={
        "epoch":1,"reconciled_flat":False,"open_orders":0,
        "reconciliation_ref":"reconcile-01"}).status_code==409
    assert CLIENT.post(BASE+f"/assignments/{aid}/release",headers=HEAD,json={
        "epoch":1,"reconciled_flat":True,"open_orders":1,
        "reconciliation_ref":"reconcile-01"}).status_code==409
    assert CLIENT.post(BASE+f"/assignments/{aid}/release",headers=HEAD,json={
        "epoch":1,"reconciled_flat":True,"open_orders":0,
        "reconciliation_ref":"reconcile-01"}).status_code==200
    register("worker-b")
    assign2=CLIENT.post(BASE+"/assignments/claim",headers=HEAD,json={
        "agent_id":"worker-b","version_id":v["version_id"],
        "slot_key":"paper:public-test-120"}).json()
    assert assign2["epoch"]==2
    assert CLIENT.post(BASE+f"/assignments/{aid}/heartbeat",headers=HEAD,json={
        "epoch":1,"lease_seconds":90}).status_code==409


def test_critical_observation_halts_assignment_and_audits_idempotently():
    v=seed()
    approve(v["version_id"])
    register()
    a=CLIENT.post(BASE+"/assignments/allocate-one",headers=HEAD).json()["assignment"]
    event={"event_id":"obs-0001","event_type":"OrderSubmitted",
           "assignment_id":a["assignment_id"],"strategy_version_id":v["version_id"],
           "epoch":a["epoch"],"payload":{"client_order_id":"PAPER-NO-ORDER","qty":100,"risk_approved":False}}
    r=CLIENT.post(BASE+"/audit/observations",headers=HEAD,json=event)
    assert r.status_code==200,r.text
    assert r.json()["assignment_state"]=="HALTED"
    assert any(f["code"]=="unapproved_order" for f in r.json()["findings"])
    repeat=CLIENT.post(BASE+"/audit/observations",headers=HEAD,json=event)
    assert repeat.status_code==200
    assert repeat.json()["duplicate"] is True
    changed={**event,"payload":{"qty":500}}
    assert CLIENT.post(BASE+"/audit/observations",headers=HEAD,json=changed).status_code==409
    assert CLIENT.post(BASE+f"/assignments/{a['assignment_id']}/heartbeat",headers=HEAD,json={
        "epoch":a["epoch"]}).status_code==409
    findings=CLIENT.get(BASE+"/audit/findings",headers=HEAD).json()["items"]
    assert len(findings)==1
    emitted=CLIENT.get(BASE+"/events",headers=HEAD).json()["events"]
    assert any(e["type"]=="StrategySuspended" and e["flow"]=="F09" for e in emitted)
    assert not any(e["type"]=="OrderFilled" for e in emitted)


def test_version_pinning_and_stale_epoch_audit():
    original=seed(version="1")
    approve(original["version_id"])
    register()
    a=CLIENT.post(BASE+"/assignments/allocate-one",headers=HEAD).json()["assignment"]
    new=ops.ingest({"script_id_part":"public-test-120","name":"Public sample TradingView strategy",
                    "author":"published-author","script_type":"strategy","script_access":"open",
                    "version":"2"},{"ok":True,"source":"//@version=6\nstrategy('Example v2')"})
    assert new["version_id"]!=original["version_id"]
    assert new["eligibility"]=="PENDING_REVIEW"
    assert CLIENT.get(BASE+"/agents",headers=HEAD).json()["active_assignments"][0]["version_id"]==original["version_id"]
    r=CLIENT.post(BASE+"/audit/observations",headers=HEAD,json={
        "event_id":"evt-stale-version","event_type":"SignalGenerated",
        "assignment_id":a["assignment_id"],"strategy_version_id":new["version_id"],
        "epoch":a["epoch"]+1,"payload":{"signal":"BUY"}})
    assert r.status_code==200
    assert {x["code"] for x in r.json()["findings"]}=={"version_mismatch","stale_epoch"}


def test_expired_lease_audit_reconciliation_halts_once():
    v=seed()
    approve(v["version_id"])
    register()
    a=CLIENT.post(BASE+"/assignments/allocate-one",headers=HEAD).json()["assignment"]
    expired=(datetime.now(UTC)-timedelta(minutes=10)).isoformat()
    with ops.db(write=True) as con:
        con.execute("UPDATE assignments SET lease_expires_at=? WHERE assignment_id=?",
                    (expired,a["assignment_id"]))
    assert CLIENT.post(BASE+"/audit/reconcile",headers=HEAD).json()["halted"]==1
    assert CLIENT.post(BASE+"/audit/reconcile",headers=HEAD).json()["halted"]==0
    assert CLIENT.get(BASE+"/agents",headers=HEAD).json()["active_assignments"][0]["state"]=="HALTED"


def test_api_all_requires_bearer_and_never_exposes_order_submission():
    for url in ("/overview","/strategies","/agents","/audit/findings","/events"):
        assert CLIENT.get(BASE+url).status_code==401
    for path in ("/strategies/sync","/assignments/allocate-one","/audit/reconcile"):
        assert CLIENT.post(BASE+path).status_code==401
    openapi=CLIENT.get("/openapi.json").json()["paths"]
    assert BASE+"/strategies/sync" in openapi
    assert BASE+"/assignments/allocate-one" in openapi
    assert BASE+"/audit/observations" in openapi
    assert not any("place-order" in x or "submit-live" in x for x in openapi if x.startswith(BASE))
