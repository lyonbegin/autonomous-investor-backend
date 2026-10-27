"""Authenticated read/run API for synthetic, non-trading scenario walkthroughs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.alpha_nodes.api import require_auth
from app.alpha_nodes.scenario_simulator import catalog, detail, start, snapshot, events_after
from app.alpha_nodes.n8n_gateway import dispatch, state as n8n_state

router=APIRouter(prefix="/api/v1/alpha/scenarios",
                 tags=["Synthetic operational flow simulation"],
                 dependencies=[Depends(require_auth)])


@router.get("")
def list_scenarios() -> dict:
    return catalog()


@router.get("/infra")
def n8n_infrastructure() -> dict:
    return n8n_state()


@router.post("/{scenario_id}/dispatch", status_code=202)
def launch_via_n8n(scenario_id: str, interval_ms: int = Query(160, ge=0, le=1500)) -> dict:
    return dispatch(scenario_id, interval_ms=interval_ms)


@router.get("/{scenario_id}")
def get_scenario(scenario_id: str) -> dict:
    return detail(scenario_id)


@router.post("/{scenario_id}/runs",status_code=202)
def start_scenario(scenario_id: str, interval_ms: int = Query(160,ge=0,le=1500)) -> dict:
    return start(scenario_id,interval_ms=interval_ms)


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    return snapshot(run_id)


@router.get("/runs/{run_id}/events")
def get_events(run_id: str, after: int = Query(0,ge=0)) -> dict:
    return events_after(run_id, after=after)
