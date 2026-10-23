from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query

from app.core.quant_lab import (
    create_experiment,
    get_experiment,
    list_experiments,
    pipeline_status,
    readiness,
    update_symbols,
)
from app.core.toss_market import TossApiError, TossConfigError, fetch_history, get_candles

router = APIRouter(prefix="/api/v1/quant", tags=["quant-lab"])


class ExperimentCreate(BaseModel):
    symbols: list[str] = Field(default_factory=list)


class SymbolUpdate(BaseModel):
    symbols: list[str] = Field(min_length=1)


@router.get("/readiness")
def quant_readiness() -> dict:
    return readiness()


@router.get("/pipeline")
def quant_pipeline() -> dict:
    return pipeline_status()


@router.post("/experiments/from-agent/{agent_id}")
def experiment_from_agent(agent_id: str, body: ExperimentCreate | None = None) -> dict:
    try:
        return create_experiment(agent_id, symbols=(body.symbols if body else []))
    except Exception as exc:
        if isinstance(exc, KeyError):
            raise HTTPException(status_code=404, detail=f"agent not found: {agent_id}") from exc
        raise HTTPException(status_code=502, detail=f"experiment registration failed: {type(exc).__name__}: {exc}") from exc


@router.get("/experiments")
def experiments(limit: int = Query(default=200, ge=1, le=1000)) -> dict:
    items = list_experiments(limit)
    return {"count": len(items), "items": items}


@router.get("/experiments/{experiment_id}")
def experiment_detail(experiment_id: str) -> dict:
    try:
        return get_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"experiment not found: {experiment_id}") from exc


@router.put("/experiments/{experiment_id}/symbols")
def experiment_symbols(experiment_id: str, body: SymbolUpdate) -> dict:
    try:
        return update_symbols(experiment_id, body.symbols)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"experiment not found: {experiment_id}") from exc


@router.get("/market-data/toss/candles")
def toss_candles(
    symbol: str,
    interval: str = Query(pattern="^(1m|1d)$"),
    count: int = Query(default=200, ge=1, le=200),
    before: str | None = None,
    adjusted: bool = True,
) -> dict:
    try:
        return get_candles(
            symbol,
            interval=interval,
            count=count,
            before=before,
            adjusted=adjusted,
        )
    except TossConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TossApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/market-data/toss/history")
def toss_history(
    symbol: str,
    interval: str = Query(pattern="^(1m|1d)$"),
    max_bars: int = Query(default=1000, ge=1, le=20000),
    adjusted: bool = True,
) -> dict:
    try:
        rows = fetch_history(
            symbol,
            interval=interval,
            max_bars=max_bars,
            adjusted=adjusted,
        )
        return {
            "symbol": symbol,
            "interval": interval,
            "count": len(rows),
            "candles": rows,
        }
    except TossConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TossApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
