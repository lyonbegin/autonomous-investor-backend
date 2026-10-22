from __future__ import annotations

import platform
from datetime import UTC, datetime

from fastapi import APIRouter

from app import __version__
from app.core.architecture import ARCHITECTURE
from app.core.contracts import (
    ExecutionReport,
    Forecast,
    ExperimentResult,
    Hypothesis,
    ModelScore,
    OrderIntent,
    PolicyAction,
    ResearchBundle,
    RiskDecision,
    Signal,
    TargetPortfolio,
)
from app.core.integrations import SPECS, probe, probe_all

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "service": "autonomous-investor-backend",
        "version": __version__,
        "time": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
    }


@router.get("/api/v1/architecture", tags=["system"])
def architecture() -> dict:
    return ARCHITECTURE


@router.get("/api/v1/integrations", tags=["integrations"])
def integrations(probe_runtime: bool = True) -> dict:
    rows = probe_all() if probe_runtime else [spec.__dict__ for spec in SPECS]
    return {"count": len(rows), "integrations": rows}


@router.get("/api/v1/integrations/{key}", tags=["integrations"])
def integration(key: str) -> dict:
    for spec in SPECS:
        if spec.key == key:
            return probe(spec)
    return {"key": key, "found": False}


@router.get("/api/v1/contracts", tags=["contracts"])
def contracts() -> dict:
    models = [
        ResearchBundle,
        ModelScore,
        Forecast,
        PolicyAction,
        Hypothesis,
        OrderIntent,
        ExperimentResult,
        Signal,
        TargetPortfolio,
        RiskDecision,
        ExecutionReport,
    ]
    return {model.__name__: model.model_json_schema() for model in models}
