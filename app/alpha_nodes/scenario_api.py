"""Scenario Control Plane HTTP API — observable from browser and direct curl.

Authenticated UI/API routes are separate from n8n's private callback secret.
No endpoint in this module can send market, broker or native trading requests.
"""
from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.alpha_nodes.api import require_auth
from app.alpha_nodes.scenario_catalog import SCENARIOS, catalog
from app.alpha_nodes.scenario_runtime import (
    advance, cancel_run, get_run, recent_runs, start_run, validate_callback_key, verify,
)

router = APIRouter(prefix="/api/v1/alpha/scenarios",
                   tags=["Scenario Test Console"])


class StartScenario(BaseModel):
    scenario_id: int
    engine: Literal["n8n", "internal-test"] = "n8n"


@router.get("/catalog", dependencies=[Depends(require_auth)])
def scenario_catalog() -> dict:
    return catalog()


@router.get("/health", dependencies=[Depends(require_auth)])
def scenario_health() -> dict:
    return {
        "scenario_count": len(SCENARIOS),
        "n8n_configured": bool(os.getenv("INVESTMENT_N8N_WEBHOOK_BASE")),
        "callback_auth_configured": len(os.getenv("INVESTMENT_SCENARIO_CALLBACK_KEY", "")) >= 24,
        "internal_test_available": True,
        "native_trading_enabled": False,
        "n8n_status": "configured_not_probed" if os.getenv("INVESTMENT_N8N_WEBHOOK_BASE") else "not_configured",
        "documentation": "Synthetic scenario callbacks only; not native engine E2E.",
    }


@router.post("/runs", status_code=202, dependencies=[Depends(require_auth)])
def create_scenario_run(payload: StartScenario) -> dict:
    return start_run(payload.scenario_id, payload.engine)


@router.get("/runs", dependencies=[Depends(require_auth)])
def list_scenario_runs(limit: int = Query(30, ge=1, le=100)) -> dict:
    return recent_runs(limit)


@router.get("/runs/{run_id}", dependencies=[Depends(require_auth)])
def read_scenario_run(run_id: str) -> dict:
    return get_run(run_id)


@router.get("/runs/{run_id}/events", dependencies=[Depends(require_auth)])
def scenario_events(run_id: str, after: int = Query(0, ge=0)) -> dict:
    run = get_run(run_id)
    selected = [event for event in run["events"] if event["seq"] > after]
    return {"run_id": run_id, "status": run["status"],
            "last_seq": run["events"][-1]["seq"] if run["events"] else 0,
            "events": selected}


@router.get("/runs/{run_id}/verify", dependencies=[Depends(require_auth)])
def verify_scenario_run(run_id: str) -> dict:
    return verify(run_id)


@router.post("/runs/{run_id}/cancel", dependencies=[Depends(require_auth)])
def stop_scenario_run(run_id: str) -> dict:
    return cancel_run(run_id)


@router.post("/internal/runs/{run_id}/steps/{step_id}")
def n8n_private_step(
    run_id: str,
    step_id: str,
    x_scenario_callback_key: str | None = Header(None, alias="X-Scenario-Callback-Key"),
) -> dict:
    """Invoked by a real n8n HTTP Request node, not by the frontend."""
    validate_callback_key(x_scenario_callback_key)
    return advance(run_id, step_id, origin="n8n")
