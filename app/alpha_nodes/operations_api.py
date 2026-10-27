"""Operations API for F01 strategy discovery, F03 exclusive PAPER claims and F05 independent audit."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.alpha_nodes.api import require_auth
from app.alpha_nodes import operations_core as core

router = APIRouter(prefix="/api/v1/ops",tags=["Persistent strategy and agent operations"],
                   dependencies=[Depends(require_auth)])


class ReviewEvidence(BaseModel):
    license_reviewed: bool
    pine_compiler_passed: bool
    independent_backtest_passed: bool
    evidence_refs: list[str] = Field(min_length=1, max_length=20)


class ReviewRequest(BaseModel):
    reviewer: str = Field(min_length=2,max_length=100)
    evidence: ReviewEvidence


class AgentRequest(BaseModel):
    agent_id: str = Field(min_length=1,max_length=80,pattern=r"^[A-Za-z0-9_-]+$")
    market_scope: str = Field(default="US",min_length=2,max_length=40)
    execution_mode: str = Field(default="paper",pattern=r"^paper$")


class ClaimRequest(BaseModel):
    agent_id: str = Field(min_length=1,max_length=80)
    version_id: str = Field(min_length=8,max_length=100)
    slot_key: str = Field(min_length=3,max_length=120)
    lease_seconds: int = Field(default=90,ge=5,le=3600)


class HeartbeatRequest(BaseModel):
    epoch: int = Field(ge=1)
    lease_seconds: int = Field(default=90,ge=5,le=3600)


class ReleaseRequest(BaseModel):
    epoch: int = Field(ge=1)
    reconciled_flat: bool
    open_orders: int = Field(ge=0)
    reconciliation_ref: str = Field(min_length=3,max_length=200)


class ObservationRequest(BaseModel):
    event_id: str = Field(min_length=4,max_length=128)
    event_type: str
    assignment_id: str = Field(min_length=1,max_length=100)
    strategy_version_id: str = Field(min_length=8,max_length=100)
    epoch: int = Field(ge=1)
    payload: dict = Field(default_factory=dict)


@router.get("/overview")
def get_overview() -> dict:
    return core.overview()


@router.post("/strategies/sync")
def sync_catalog(limit: int = Query(30,ge=1,le=100),
                 offset: int = Query(0,ge=0,le=100000),
                 max_sources: int = Query(5,ge=0,le=10),
                 refresh_live: bool = Query(False)) -> dict:
    return core.sync(limit=limit,offset=offset,max_sources=max_sources,refresh_live=refresh_live)


@router.get("/strategies")
def strategies(status: str | None = None,limit: int = Query(100,ge=1,le=500)) -> dict:
    return core.strategy_list(status,limit)


@router.post("/strategies/{version_id}/approve")
def approve(version_id: str, body: ReviewRequest) -> dict:
    return core.approve(version_id,body.reviewer,body.evidence.model_dump())


@router.post("/agents",status_code=201)
def agents_register(body: AgentRequest) -> dict:
    return core.register_agent(body.agent_id,body.market_scope,body.execution_mode)


@router.get("/agents")
def agents() -> dict:
    return core.agent_list()


@router.post("/assignments/claim",status_code=201)
def manual_claim(body: ClaimRequest) -> dict:
    return core.claim(body.agent_id,body.version_id,body.slot_key,body.lease_seconds)


@router.post("/assignments/allocate-one")
def automated_claim() -> dict:
    return core.allocate_one()


@router.post("/assignments/{assignment_id}/heartbeat")
def assign_heartbeat(assignment_id: str,body: HeartbeatRequest) -> dict:
    return core.heartbeat(assignment_id,body.epoch,body.lease_seconds)


@router.post("/assignments/{assignment_id}/release")
def assign_release(assignment_id: str,body: ReleaseRequest) -> dict:
    return core.release(assignment_id,body.epoch,flat=body.reconciled_flat,
                        open_orders=body.open_orders,reconciliation_ref=body.reconciliation_ref)


@router.post("/audit/observations")
def audit_observe(body: ObservationRequest) -> dict:
    return core.observe(event_id=body.event_id,event_type=body.event_type,
                        assignment_id=body.assignment_id,version_id=body.strategy_version_id,
                        epoch=body.epoch,payload=body.payload)


@router.post("/audit/reconcile")
def audit_reconcile() -> dict:
    return core.audit_reconcile()


@router.get("/audit/findings")
def audit_findings(limit: int = Query(100,ge=1,le=500)) -> dict:
    return core.audit_list(limit)


@router.get("/events")
def events(after: int = Query(0,ge=0),limit: int = Query(100,ge=1,le=500)) -> dict:
    return core.read_events(after,limit)
