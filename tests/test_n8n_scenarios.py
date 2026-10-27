"""Run all ten synthetic workflows over actual FastAPI endpoints."""
from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.alpha_nodes.scenario_simulator import SCENARIOS

BASE="/api/v1/alpha/scenarios"
HEADERS={"Authorization":"Bearer scenario-unit-test-key"}
client=TestClient(app)


@pytest.fixture(autouse=True)
def configure(monkeypatch,tmp_path):
    monkeypatch.setenv("ALPHA_NODE_API_KEY","scenario-unit-test-key")
    monkeypatch.setenv("SCENARIO_DB_PATH",str(tmp_path/"scenarios.sqlite3"))


def wait_for(run_id,timeout=6):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        r=client.get(BASE+"/runs/"+run_id,headers=HEADERS)
        assert r.status_code==200,r.text
        result=r.json()
        if result["status"] in ("completed","failed","interrupted"):
            return result
        time.sleep(0.03)
    raise AssertionError("scenario run did not finish: "+run_id)


def test_catalog_is_exactly_ten_and_every_flow_is_referenced():
    r=client.get(BASE,headers=HEADERS)
    assert r.status_code==200
    data=r.json()
    assert data["count"]==10
    assert set(data["flows"])=={"F%02d"%i for i in range(1,11)}
    assert set(x["id"] for x in data["scenarios"])==set(SCENARIOS)
    assert all(x["mode"]=="SYNTHETIC_SIMULATION" for x in data["scenarios"])


@pytest.mark.parametrize("scenario_id",list(SCENARIOS))
def test_simulation_executes_every_step_and_records_io(scenario_id):
    d=client.get(BASE+"/"+scenario_id,headers=HEADERS)
    assert d.status_code==200
    assert d.json()["steps"]
    started=client.post(BASE+"/"+scenario_id+"/runs?interval_ms=0",headers=HEADERS)
    assert started.status_code==202,started.text
    run_id=started.json()["run_id"]
    result=wait_for(run_id)
    assert result["status"]=="completed",result
    assert result["completed_steps"]==result["total_steps"]==len(SCENARIOS[scenario_id]["steps"])
    assert result["progress_pct"]==100
    assert result["mode"]=="SYNTHETIC_SIMULATION"
    assert len(result["events"])==2*result["total_steps"]
    assert all(ev["status"] in ("running","success") for ev in result["events"])
    assert result["events"][-1]["status"]=="success"
    for i,item in enumerate(SCENARIOS[scenario_id]["steps"]):
        done=result["events"][i*2+1]
        assert done["flow"]==item["flow"]
        assert done["inputs"]==item["inputs"]
        assert done["outputs"]==item["outputs"]
        assert done["next_flows"]==item["next_flows"]
    events=client.get(BASE+"/runs/"+run_id+"/events?after="+str(result["events"][0]["sequence"]),headers=HEADERS)
    assert events.status_code==200
    assert len(events.json()["events"])==2*result["total_steps"]-1


def test_scenario_poll_progresses_over_real_time():
    started=client.post(BASE+"/04-partial-fill/runs?interval_ms=50",headers=HEADERS)
    assert started.status_code==202
    run_id=started.json()["run_id"]
    beginning=client.get(BASE+"/runs/"+run_id,headers=HEADERS).json()
    assert beginning["status"] in ("queued","running")
    final=wait_for(run_id)
    assert final["status"]=="completed"
    assert final["completed_steps"]==7


def test_simulator_is_authenticated_and_does_not_expose_trade_endpoints():
    assert client.get(BASE).status_code==401
    assert client.post(BASE+"/01-new-strategy/runs").status_code==401
    assert client.get(BASE+"/runs/not-a-run",headers=HEADERS).status_code==404
    assert client.post(BASE+"/missing/runs",headers=HEADERS).status_code==404
    assert client.post(BASE+"/01-new-strategy/runs?interval_ms=5000",headers=HEADERS).status_code==422
    for scenario in SCENARIOS.values():
        assert all("submit_order" not in str(step) and "submit_market_intent" not in str(step)
                   for step in scenario["steps"])


def test_unrelated_runs_can_progress_independently():
    ids=[]
    for key in ("05-long-backtest","08-agent-crash"):
        r=client.post(BASE+"/"+key+"/runs?interval_ms=20",headers=HEADERS)
        assert r.status_code==202
        ids.append(r.json()["run_id"])
    results=[wait_for(i) for i in ids]
    assert all(x["status"]=="completed" for x in results)
    assert results[0]["scenario_id"]!=results[1]["scenario_id"]
