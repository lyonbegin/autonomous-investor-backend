from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query

from app.core.quant_lab import (
    run_quant_handoff,
    quant_handoff_status,
    create_experiment,
    get_experiment,
    list_experiment_results,
    list_experiments,
    pipeline_status,
    run_experiment,
    readiness,
    update_symbols,
)
from app.core.toss_market import TossApiError, TossConfigError, fetch_history, get_candles
from app.core.macro_data import latest_macro_snapshot, macro_series, refresh_macro

router = APIRouter(prefix="/api/v1/quant", tags=["quant-lab"])


class ExperimentCreate(BaseModel):
    symbols: list[str] = Field(default_factory=list)


class SymbolUpdate(BaseModel):
    symbols: list[str] = Field(min_length=1)


class QuantHandoffRun(BaseModel):
    limit_candidates: int = Field(default=25, ge=1, le=500)
    max_agents_per_candidate: int = Field(default=12, ge=1, le=100)
    max_experiments: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=72.0, ge=0.0, le=100.0)
    run_ready: bool = True
    max_symbols: int = Field(default=3, ge=1, le=20)
    commission_bps: float = Field(default=5.0, ge=0.0, le=100.0)
    slippage_bps: float = Field(default=2.0, ge=0.0, le=100.0)


class ExperimentRun(BaseModel):
    max_symbols: int = Field(default=5, ge=1, le=20)
    commission_bps: float = Field(default=5.0, ge=0.0, le=100.0)
    slippage_bps: float = Field(default=2.0, ge=0.0, le=100.0)


@router.get("/handoff/status")
def handoff_status(
    min_score: float = Query(default=72.0, ge=0.0, le=100.0),
) -> dict:
    try:
        return quant_handoff_status(min_score=min_score)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"quant handoff status failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.post("/handoff/run")
def handoff_run(body: QuantHandoffRun | None = None) -> dict:
    params = body or QuantHandoffRun()
    try:
        return run_quant_handoff(
            limit_candidates=params.limit_candidates,
            max_agents_per_candidate=params.max_agents_per_candidate,
            max_experiments=params.max_experiments,
            min_score=params.min_score,
            run_ready=params.run_ready,
            max_symbols=params.max_symbols,
            commission_bps=params.commission_bps,
            slippage_bps=params.slippage_bps,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"quant handoff run failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/readiness")
def quant_readiness() -> dict:
    return readiness()


@router.post("/macro/refresh")
def macro_refresh() -> dict:
    try:
        return refresh_macro()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"macro refresh failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/macro/snapshot")
def macro_snapshot() -> dict:
    return latest_macro_snapshot()


@router.get("/macro/series/{series_id}")
def macro_series_data(
    series_id: str,
    limit: int = Query(default=120, ge=1, le=5000),
) -> dict:
    return macro_series(series_id, limit=limit)


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


@router.post("/experiments/{experiment_id}/run")
def experiment_run(experiment_id: str, body: ExperimentRun | None = None) -> dict:
    params = body or ExperimentRun()
    try:
        return run_experiment(
            experiment_id,
            max_symbols=params.max_symbols,
            commission_bps=params.commission_bps,
            slippage_bps=params.slippage_bps,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"experiment not found: {experiment_id}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail=f"experiment execution failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/experiments/{experiment_id}/results")
def experiment_results(experiment_id: str) -> dict:
    try:
        get_experiment(experiment_id)
        items = list_experiment_results(experiment_id)
        return {"experiment_id": experiment_id, "count": len(items), "items": items}
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
