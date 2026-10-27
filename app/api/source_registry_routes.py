from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.source_registry import (
    list_quant_handoff_agents,
    batch_create_agents_from_discovery,
    agent_factory_queue_status,
    batch_discover_pending_candidates,
    create_agents_from_discovery,
    discovery_leaderboard,
    discovery_queue_status,
    discover_candidate_horizons,
    get_source,
    list_candidate_discovery,
    list_sources,
    sync_tradingview_sources,
)

router = APIRouter(prefix="/api/v1", tags=["strategy-sources"])


@router.post("/strategy-sources/sync")
def strategy_sources_sync(limit: int = Query(default=2000, ge=1, le=10000)) -> dict:
    return sync_tradingview_sources(limit=limit)


@router.get("/strategy-sources")
def strategy_sources(
    source_kind: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict:
    items = list_sources(source_kind=source_kind, limit=limit)
    return {"count": len(items), "items": items}


@router.get("/strategy-sources/{registry_source_id:path}")
def strategy_source_detail(registry_source_id: str) -> dict:
    item = get_source(registry_source_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"strategy source not found: {registry_source_id}")
    return item


@router.get("/horizon-discovery/queue-status")
def horizon_discovery_queue_status() -> dict:
    return discovery_queue_status()


@router.post("/horizon-discovery/batch")
def horizon_discovery_batch(
    limit: int = Query(default=100, ge=1, le=1000),
    max_markets: int = Query(default=3, ge=1, le=10),
) -> dict:
    return batch_discover_pending_candidates(limit=limit, max_markets=max_markets)


@router.get("/horizon-discovery/leaderboard")
def horizon_discovery_leaderboard(
    limit: int = Query(default=100, ge=1, le=1000),
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
) -> dict:
    items = discovery_leaderboard(limit=limit, min_score=min_score)
    return {"count": len(items), "items": items}


@router.post("/horizon-discovery/{candidate_id}")
def horizon_discovery_run(
    candidate_id: str,
    max_markets: int = Query(default=3, ge=1, le=10),
) -> dict:
    try:
        return discover_candidate_horizons(candidate_id, max_markets=max_markets)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"candidate not found: {candidate_id}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"horizon discovery failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/horizon-discovery/{candidate_id}")
def horizon_discovery_results(candidate_id: str) -> dict:
    items = list_candidate_discovery(candidate_id)
    return {"candidate_id": candidate_id, "count": len(items), "items": items}


@router.post("/agent-factory/{candidate_id}")
def agent_factory(
    candidate_id: str,
    min_score: float = Query(default=72.0, ge=0.0, le=100.0),
    max_agents: int = Query(default=12, ge=1, le=100),
) -> dict:
    try:
        return create_agents_from_discovery(
            candidate_id,
            min_score=min_score,
            max_agents=max_agents,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"candidate not found: {candidate_id}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"agent factory failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/agent-factory/batch/status")
def agent_factory_batch_status(
    min_score: float = Query(default=72.0, ge=0.0, le=100.0),
) -> dict:
    return agent_factory_queue_status(min_score=min_score)


@router.post("/agent-factory-batch")
def agent_factory_batch(
    limit_candidates: int = Query(default=100, ge=1, le=1000),
    min_score: float = Query(default=72.0, ge=0.0, le=100.0),
    max_agents_per_candidate: int = Query(default=12, ge=1, le=100),
) -> dict:
    return batch_create_agents_from_discovery(
        limit_candidates=limit_candidates,
        min_score=min_score,
        max_agents_per_candidate=max_agents_per_candidate,
    )


@router.get("/quant-handoff/agents")
def quant_handoff_agents(
    limit: int = Query(default=100, ge=1, le=1000),
    min_score: float = Query(default=72.0, ge=0.0, le=100.0),
) -> dict:
    items = list_quant_handoff_agents(limit=limit, min_score=min_score)
    return {"count": len(items), "items": items}
