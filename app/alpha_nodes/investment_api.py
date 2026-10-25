"""Stock-investment workflow REST endpoints over existing engine module functions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.alpha_nodes.api import require_auth
from app.alpha_nodes.investment_flow import (
    ExecuteFlow, FlowDefinition, approve, create_workflow, events, get_run,
    get_workflow, list_workflows, palette, publish, start_run, update_workflow,
    validate,
)

router = APIRouter(prefix="/api/v1/alpha/investment", tags=["Investment node workflow"],
                   dependencies=[Depends(require_auth)])


class UpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    definition: FlowDefinition


class ApprovalRequest(BaseModel):
    approver: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=500)


@router.get("/node-types")
def node_types(engine: str | None = Query(None), status: str | None = Query(None)) -> dict:
    result = palette()
    items = [x for x in result["nodes"] if (not engine or x["engine"] == engine)
             and (not status or x["execution"] == status)]
    return {"count": len(items), "engine_count": result["engine_count"],
            "native_functions": result["native_functions"], "nodes": items,
            "live_orders": result["live_orders"]}


@router.post("/workflows/validate")
def validate_workflow(definition: FlowDefinition) -> dict:
    try:
        return validate(definition)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/workflows", status_code=201)
def create(definition: FlowDefinition) -> dict:
    try:
        return create_workflow(definition)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/workflows")
def workflows() -> dict:
    return list_workflows()


@router.get("/workflows/{workflow_id}")
def workflow(workflow_id: str, version: int | None = Query(None, ge=1)) -> dict:
    return get_workflow(workflow_id, version)


@router.put("/workflows/{workflow_id}")
def edit(workflow_id: str, data: UpdateRequest) -> dict:
    try:
        return update_workflow(workflow_id, data.definition, data.expected_version)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/workflows/{workflow_id}/versions/{version}/publish")
def publish_version(workflow_id: str, version: int) -> dict:
    return publish(workflow_id, version)


@router.post("/workflows/{workflow_id}/runs")
def execute(workflow_id: str, request: ExecuteFlow) -> dict:
    return start_run(workflow_id, request)


@router.get("/runs/{run_id}")
def run_details(run_id: str) -> dict:
    return get_run(run_id)


@router.get("/runs/{run_id}/events")
def run_events(run_id: str) -> dict:
    return events(run_id)


@router.post("/runs/{run_id}/nodes/{node_id}/approve")
def approve_node(run_id: str, node_id: str, body: ApprovalRequest) -> dict:
    return approve(run_id, node_id, approver=body.approver, note=body.note)


@router.get("/examples")
def examples() -> dict:
    """Sample *graph definitions* only; not live or simulated investment returns."""
    return {
        "examples": [
            {
                "name": "TradingView 공개 전략 → 원본 검증",
                "nodes": [
                    {"id": "scripts", "operation_id": "tradingview.service.api.script_catalog",
                     "arguments": {"script_type": "strategies", "limit": 1}},
                    {"id": "source", "operation_id": "tradingview.service.api.script_source"},
                    {"id": "approval", "operation_id": "control.approval"},
                ],
                "edges": [
                    {"id": "e1", "source": "scripts", "target": "source",
                     "target_input": "script_id_part",
                     "output_path": "result.items.0.script_id_part"},
                    {"id": "e2", "source": "source", "target": "approval"},
                ],
            },
            {
                "name": "두 독립 분석 → ALL 합류 → 사람 승인",
                "nodes": [
                    {"id": "market", "operation_id": "tradingview.service.api.script_catalog",
                     "arguments": {"script_type": "strategies", "limit": 5}},
                    {"id": "quant", "operation_id": "quantlab.service.api.quant_pipeline"},
                    {"id": "join", "operation_id": "control.join", "join": "ALL"},
                    {"id": "approval", "operation_id": "control.approval"},
                ],
                "edges": [
                    {"id": "left", "source": "market", "target": "join",
                     "target_input": "market_results", "output_path": "result"},
                    {"id": "right", "source": "quant", "target": "join",
                     "target_input": "quant_results", "output_path": "result"},
                    {"id": "approve", "source": "join", "target": "approval"},
                ],
            },
            {
                "name": "NautilusTrader 사전 주문 계획 (실제 제출 금지)",
                "nodes": [
                    {"id": "portfolio", "operation_id": "control.identity",
                     "arguments": {"target": {"$contract": "TargetPortfolio",
                        "strategy_id": "DEMO-ONLY", "as_of": "2026-10-25T00:00:00Z",
                        "weights": [{"instrument": "EXAMPLE", "weight": 0.1}]}}},
                    {"id": "preview", "operation_id": "orchestration.orchestration.runtime.plan_rebalance",
                     "arguments": {"equity": 1000.0, "prices": {"EXAMPLE": 100.0},
                                   "current_quantities": {"EXAMPLE": 0.0}}},
                    {"id": "human", "operation_id": "control.approval"},
                ],
                "edges": [
                    {"id": "p1", "source": "portfolio", "target": "preview",
                     "target_input": "target", "output_path": "result.target"},
                    {"id": "p2", "source": "preview", "target": "human"},
                ],
            },
        ],
        "warning": "No broker, account, capital allocation or Pine conversion is executed by example definitions.",
    }
