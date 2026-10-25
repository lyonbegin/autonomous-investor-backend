#!/usr/bin/env python3
"""F01/F03/F05 actual n8n published-webhook -> queue worker -> real DB proof.

Only the TradingView HTTP upstream is CI-fixtured. No market feed or broker order
is issued. This test verifies real Python API state transitions behind n8n.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from urllib import request

BASE="http://127.0.0.1:8000"
N8N="http://127.0.0.1:5678"
TOKEN=os.environ["CI_SCENARIO_TOKEN"]


def api(path,method="GET",data=None):
    raw=json.dumps(data if data is not None else {}).encode() if method!="GET" else None
    rq=request.Request(BASE+path,data=raw,method=method,
                       headers={"Content-Type":"application/json","Authorization":"Bearer "+TOKEN})
    with request.urlopen(rq,timeout=20) as response:
        return json.loads(response.read())


def hook(key):
    rq=request.Request(N8N+"/webhook/ai-ops-"+key,data=b"{}",method="POST",
                       headers={"Content-Type":"application/json"})
    with request.urlopen(rq,timeout=20) as r:
        assert r.status==200,(key,r.status)
        return json.loads(r.read())


def main():
    # Actual n8n worker calls a real FastAPI F01 service which uses the
    # loopback fixture's real HTTP catalog+source endpoints.
    result=hook("f01")
    assert result["count"]==2,result
    versions=api("/api/v1/ops/strategies")["items"]
    assert len(versions)==2
    pine=next(x for x in versions if x["strategy_id"]=="CI-REAL-HTTP-PINE-1")
    locked=next(x for x in versions if x["strategy_id"]=="CI-PROTECTED-PINE-2")
    assert pine["eligibility"]=="PENDING_REVIEW" and pine["source_available"]==1
    assert locked["eligibility"]=="INELIGIBLE" and locked["source_available"]==0
    print("REAL_N8N_F01_UPSTREAM_HTTP_AND_REGISTRY_PASS",flush=True)

    # Only in this ephemeral CI can the synthetic backtest proof be attested:
    # production deployments require verified external validation evidence.
    approved=api("/api/v1/ops/strategies/"+pine["latest_version_id"]+"/approve","POST",{
        "reviewer":"ci-fixture-only",
        "evidence":{"license_reviewed":True,"pine_compiler_passed":True,
                    "independent_backtest_passed":True,
                    "evidence_refs":["CI_SYNTHETIC_EVIDENCE_NOT_FOR_REAL_TRADING"]},
    })
    assert approved["eligibility"]=="APPROVED"
    api("/api/v1/ops/agents","POST",{"agent_id":"ci-agent-one","market_scope":"US","execution_mode":"paper"})
    r3=hook("f03")
    active=r3["active_assignments"]
    assert len(active)==1 and active[0]["agent_id"]=="ci-agent-one",r3
    a=active[0]
    assert a["version_id"]==pine["latest_version_id"] and a["epoch"]==1
    assert api("/api/v1/ops/agents")["active_assignments"][0]["state"]=="ACTIVE"
    print("REAL_N8N_F03_ATOMIC_PAPER_ASSIGNMENT_PASS",flush=True)

    valid=api("/api/v1/ops/audit/observations","POST",{
        "event_id":"CI-SIGNAL-0001","event_type":"SignalGenerated",
        "assignment_id":a["assignment_id"],"strategy_version_id":a["version_id"],
        "epoch":a["epoch"],"payload":{"signal":"HOLD"}})
    assert valid["findings"]==[]
    with sqlite3.connect(os.environ["STRATEGY_OPERATIONS_DB_PATH"]) as conn:
        conn.execute("UPDATE assignments SET lease_expires_at=? WHERE assignment_id=?",
                     ((datetime.now(UTC)-timedelta(minutes=3)).isoformat(),a["assignment_id"]))
    findings=hook("f05")
    assert findings["count"]>=1,findings
    assert any(f["code"]=="lease_expired" for f in findings["items"])
    halted=api("/api/v1/ops/agents")["active_assignments"]
    assert halted[0]["state"]=="HALTED",halted
    assert api("/api/v1/ops/audit/reconcile","POST")["halted"]==0
    print("REAL_N8N_F05_LEASE_AUDIT_HALT_PASS",flush=True)

    snapshot=api("/api/v1/ops/overview")
    assert snapshot["counts"]["strategy_registry"]==2
    assert snapshot["counts"]["strategy_versions"]==2
    assert snapshot["counts"]["assignments"]==1
    assert snapshot["counts"]["audit_findings"]>=1
    ev=api("/api/v1/ops/events?limit=100")["events"]
    assert {"F01","F02","F03","F05"} <= {e["flow"] for e in ev}
    with open("/tmp/n8n-operational-e2e.json","w") as f:
        json.dump({"status":"PASS","workflows":["F01","F03","F05"],
                   "operations":snapshot,"events":len(ev),
                   "upstream":"EXPLICIT_LOCAL_HTTP_FIXTURE_NOT_LIVE_TRADINGVIEW"},f,indent=2)
    print("REAL_N8N_THREE_OPERATIONS_ALL_PASS",flush=True)


if __name__=="__main__":
    main()
