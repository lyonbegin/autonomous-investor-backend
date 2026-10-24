"""Concrete HTTP endpoint for EVERY current app/lab engine bridge method.

Examples:
 POST /api/v1/alpha/modules/vectorbt/app/bridge/from_signals/execute
 POST /api/v1/alpha/modules/riskfolio/app/bridge/portfolio/execute
 POST /api/v1/alpha/modules/nautilus/lab/bridge/backtest_node/execute
 POST /api/v1/alpha/modules/orchestration/orchestration/runtime/plan_rebalance/execute

No dummy success results: native imports/calls are attempted; missing dependencies
and unsupported calls return real errors. Native live order submission is gated.
"""
from __future__ import annotations

import hmac
import os
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.alpha_nodes.inventory import ENGINES, OPERATIONS, OPERATION_MAP, module_inventory
from app.alpha_nodes.runtime import ExecuteRequest, get_job, handle_info, submit_invocation

router = APIRouter(prefix="/api/v1/alpha", tags=["AlphaForge engine function nodes"])


def require_auth(authorization: str | None = Header(None)) -> None:
    expected = os.environ.get("ALPHA_NODE_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="ALPHA_NODE_API_KEY not configured; execution API disabled")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    if not hmac.compare_digest(authorization.removeprefix("Bearer "), expected):
        raise HTTPException(status_code=401, detail="incorrect bearer token")


@router.get("/projects", dependencies=[Depends(require_auth)])
def projects() -> dict:
    rows = module_inventory()
    return {"count": len(ENGINES), "projects": [
        {
            "engine": engine,
            "module_count": len([m for m in rows if m["engine"] == engine]),
            "function_count": sum(m["function_count"] for m in rows if m["engine"] == engine),
        } for engine in ENGINES
    ], "orchestration_module_count": len([m for m in rows if m["engine"] == "orchestration"])}


@router.get("/modules", dependencies=[Depends(require_auth)])
def modules(engine: str | None = None, source: str | None = None) -> dict:
    rows = module_inventory()
    if engine:
        rows = [x for x in rows if x["engine"] == engine]
    if source:
        rows = [x for x in rows if x["source"] == source]
    return {"count": len(rows), "modules": rows}


@router.get("/operations", dependencies=[Depends(require_auth)])
def operations(engine: str | None = None, source: str | None = None,
               offset: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=1000)) -> dict:
    rows = [x for x in OPERATIONS if (not engine or x["engine"] == engine) and
            (not source or x["source"] == source)]
    return {"count": len(rows), "items": rows[offset:offset + limit]}


@router.get("/operations/{operation_id}", dependencies=[Depends(require_auth)])
def operation(operation_id: str) -> dict:
    op = OPERATION_MAP.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail="unknown operation")
    return op


@router.get("/handles/{handle}", dependencies=[Depends(require_auth)])
def handle_details(handle: str) -> dict:
    try:
        return handle_info(handle)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", dependencies=[Depends(require_auth)])
def job_status(job_id: str) -> dict:
    return get_job(job_id)


class ContractPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


@router.post("/contracts/{model_name}/validate", dependencies=[Depends(require_auth)])
def validate_contract(model_name: str, payload: ContractPayload) -> dict:
    from app.core import contracts
    permitted = {
        "EvidenceItem", "ResearchBundle", "Hypothesis", "ExperimentResult",
        "ModelScore", "ForecastQuantile", "Forecast", "PolicyAction",
        "Signal", "TargetWeight", "TargetPortfolio", "OrderIntent",
        "RiskDecision", "ExecutionReport",
    }
    if model_name not in permitted:
        raise HTTPException(status_code=404, detail="contract not available")
    from pydantic import ValidationError
    try:
        obj = getattr(contracts, model_name).model_validate(payload.data)
        return {"contract": model_name, "status": "validated", "value": obj.model_dump(mode="json")}
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc


def _make_executor(operation_id: str):
    async def execute(body: ExecuteRequest, _: None = Depends(require_auth)) -> dict[str, Any]:
        # Heavy sync methods execute off the event loop; a background flag
        # provides a pollable job instead of holding a long HTTP connection.
        import asyncio
        return await asyncio.to_thread(submit_invocation, operation_id, body)
    execute.__name__ = "alpha_exec_" + operation_id.replace(".", "_")
    return execute


for _op in OPERATIONS:
    router.add_api_route(
        _op["endpoint"].removeprefix("/api/v1/alpha"),
        _make_executor(_op["id"]),
        methods=["POST"],
        name=_op["id"],
        summary=f"{_op['engine']} · {_op['module']} · {_op['function']}",
        description=(
            f"Native callable from {_op['source_path']}:{_op['source_line']}.\n\n"
            f"Call kind: {_op['call_kind']}.\n\n"
            f"Native return annotation: {_op['output']}.\n\n"
            f"Guard: {_op['guard']}.\n\n"
            "Use JSON arguments for native parameters; use {$handle: 'id'} for "
            "non-JSON Python objects produced by a preceding node."
        ),
    )
