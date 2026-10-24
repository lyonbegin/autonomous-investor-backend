from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.corporate_bonds import corporate_bond_backfill, corporate_bond_status, corporate_bond_coverage_audit, repair_corporate_bond_phase

from app.core.tradingview import (
    collect_ideas,
    complete_missing_idea_assets,
    idea_completion_status,
    collect_market,
    compact_market_storage,
    storage_stats,
    collect_scripts,
    complete_missing_script_assets,
    backfill_tradingview_source,
    build_pending_strategy_candidates,
    candidate_build_status,
    create_agent_plans,
    create_candidate_from_idea,
    create_candidate_from_script,
    fetch_script_source,
    fetch_source_detail,
    get_candidate,
    get_agent_plan,
    list_agent_plans,
    list_agent_universe,
    resolve_agent_universe,
    search_stored_scripts,
    set_agent_status,
    list_agent_status_history,
    script_source_completion_status,
    list_candidates,
    list_collector_states,
    list_market_snapshots,
    list_market_universe,
    reset_market_backfill,
    market_universe_counts,
    market_backfill_state,
    backfill_market_universe,
    bond_prefix_backfill_state,
    backfill_corporate_bond_universe,
    list_stored_ideas,
    list_stored_scripts,
)

router = APIRouter(prefix="/api/v1/tradingview", tags=["tradingview"])

class AgentStatusUpdate(BaseModel):
    status: str = Field(min_length=1)
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)


@router.post("/backfill/{kind}")
def backfill_source(
    kind: str,
    pages: int = Query(default=1, ge=1, le=25),
    fetch_details: bool = True,
    fetch_pine: bool = True,
) -> dict:
    try:
        return backfill_tradingview_source(
            kind,
            pages=pages,
            fetch_details=fetch_details,
            fetch_pine=fetch_pine,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView backfill failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/backfill")
def backfill_status() -> dict:
    items = list_collector_states()
    return {"count": len(items), "items": items}



@router.get("/ideas/live")
def ideas_live(
    sort: str = Query(default="trending"),
    page: int = Query(default=1, ge=1),
    lang: str = Query(default="ko", min_length=2, max_length=10),
) -> dict:
    try:
        return collect_ideas(sort=sort, page=page, lang=lang)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TradingView ideas collection failed: {type(exc).__name__}: {exc}") from exc


@router.get("/ideas")
def ideas_stored(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    items = list_stored_ideas(limit=limit)
    return {"count": len(items), "items": items}


@router.get("/ideas/completion")
def ideas_completion() -> dict:
    return idea_completion_status()


@router.post("/ideas/complete-missing")
def ideas_complete_missing(
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict:
    try:
        return complete_missing_idea_assets(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView missing idea assets backfill failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/ideas/{idea_id}/full")
def idea_full(idea_id: str, force: bool = False) -> dict:
    try:
        return fetch_source_detail("idea", idea_id, force=force)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"idea not found: {idea_id}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView idea detail collection failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.post("/ideas/{idea_id}/candidate")
def idea_to_candidate(idea_id: str) -> dict:
    try:
        return create_candidate_from_idea(idea_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"idea not found: {idea_id}") from exc


@router.get("/markets/corporate-bonds/full-backfill/coverage")
def corporate_bonds_full_backfill_coverage() -> dict:
    try:
        return corporate_bond_coverage_audit()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView corporate bond coverage audit failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/markets/corporate-bonds/full-backfill/state")
def corporate_bonds_full_backfill_state() -> dict:
    return corporate_bond_status()


@router.post("/markets/corporate-bonds/full-backfill/repair")
def corporate_bonds_full_backfill_repair(
    phase: str = Query(default="yield"),
) -> dict:
    try:
        return repair_corporate_bond_phase(phase=phase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView corporate bond repair failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.post("/markets/corporate-bonds/full-backfill")
def corporate_bonds_full_backfill(
    max_tasks: int = Query(default=64, ge=1, le=128),
    pages_per_task: int = Query(default=60, ge=1, le=500),
    force_new: bool = False,
) -> dict:
    try:
        return corporate_bond_backfill(
            max_tasks=max_tasks,
            pages_per_task=pages_per_task,
            force_new=force_new,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView corporate bond full backfill failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/markets/storage/stats")
def market_storage_stats() -> dict:
    return storage_stats()


@router.post("/markets/storage/compact")
def market_storage_compact() -> dict:
    try:
        return compact_market_storage()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView market storage compaction failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/markets/backfill/state")
def markets_backfill_state() -> dict:
    items = market_backfill_state()
    return {"count": len(items), "items": items}


@router.get("/markets/backfill/counts")
def markets_backfill_counts() -> dict:
    items = market_universe_counts()
    return {"count": len(items), "items": items}


@router.post("/markets/{market}/reset-backfill")
def market_backfill_reset(market: str) -> dict:
    try:
        return reset_market_backfill(market)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/markets/corporate-bonds/prefix-backfill/state")
def corporate_bond_prefix_state() -> dict:
    return bond_prefix_backfill_state()


@router.post("/markets/corporate-bonds/prefix-backfill")
def corporate_bond_prefix_backfill(
    max_prefixes: int = Query(default=500, ge=1, le=5000),
) -> dict:
    try:
        return backfill_corporate_bond_universe(max_prefixes=max_prefixes)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView corporate bond prefix backfill failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.post("/markets/{market}/backfill")
def market_backfill(
    market: str,
    chunks: int = Query(default=5, ge=1, le=250),
    page_size: int = Query(default=1000, ge=100, le=1000),
) -> dict:
    try:
        return backfill_market_universe(market, chunks=chunks, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView market universe backfill failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/markets/{market}/stored")
def market_stored_universe(
    market: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="volume"),
    sort_order: str = Query(default="desc"),
) -> dict:
    try:
        return list_market_universe(
            market,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/markets/{market}")
def market_live(
    market: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="volume"),
    sort_order: str = Query(default="desc"),
) -> dict:
    try:
        return collect_market(market, limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TradingView market collection failed: {type(exc).__name__}: {exc}") from exc




@router.get("/scripts/live")
def scripts_live(
    page: int = Query(default=1, ge=1),
    sort: str = Query(default="latest_popular"),
    topic: str | None = None,
    editors_picks: bool = False,
    script_type: str = Query(default="all"),
) -> dict:
    try:
        return collect_scripts(
            page=page,
            sort=sort,
            topic=topic,
            editors_picks=editors_picks,
            script_type=script_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView scripts collection failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/scripts/search")
def scripts_search(
    q: str = Query(min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    items = search_stored_scripts(q, limit=limit)
    return {"query": q, "count": len(items), "items": items}


@router.get("/scripts")
def scripts_stored(limit: int = Query(default=200, ge=1, le=1000)) -> dict:
    items = list_stored_scripts(limit=limit)
    return {"count": len(items), "items": items}


@router.get("/scripts/completion")
def scripts_completion() -> dict:
    return script_source_completion_status()


@router.post("/scripts/complete-missing")
def scripts_complete_missing(
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict:
    try:
        return complete_missing_script_assets(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView missing script assets backfill failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/scripts/{script_id_part}/full")
def script_full(script_id_part: str, force: bool = False) -> dict:
    try:
        return fetch_source_detail("script", script_id_part, force=force)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"script not found: {script_id_part}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView script detail collection failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/scripts/{script_id_part}/source")
def script_source(script_id_part: str, version: str = "last") -> dict:
    try:
        return fetch_script_source(script_id_part, version=version)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView Pine source fetch failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/scripts/{script_id_part}/source-info")
def script_source_info(script_id_part: str, version: str = "last") -> dict:
    try:
        result = fetch_script_source(script_id_part, version=version)
        if not result.get("ok"):
            return result
        return {
            key: value
            for key, value in result.items()
            if key != "source"
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView Pine source fetch failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.post("/scripts/{script_id_part}/candidate")
def script_to_candidate(script_id_part: str, fetch_source: bool = True) -> dict:
    try:
        return create_candidate_from_script(script_id_part, fetch_source=fetch_source)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"script not found: {script_id_part}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView script candidate conversion failed: {type(exc).__name__}: {exc}",
        ) from exc



@router.get("/markets/{market}/stored")
def market_stored(
    market: str,
    limit: int = Query(default=100, ge=1, le=1000),
    latest_only: bool = True,
) -> dict:
    try:
        items = list_market_snapshots(market, limit=limit, latest_only=latest_only)
        return {
            "market": market,
            "count": len(items),
            "latest_only": latest_only,
            "items": items,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/candidates/build-status")
def candidates_build_status() -> dict:
    return candidate_build_status()


@router.post("/candidates/build")
def candidates_build(
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict:
    try:
        return build_pending_strategy_candidates(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView candidate batch build failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/candidates")
def candidates(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    items = list_candidates(limit)
    return {"count": len(items), "items": items}


@router.get("/candidates/{candidate_id}")
def candidate_detail(candidate_id: str) -> dict:
    try:
        return get_candidate(candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"candidate not found: {candidate_id}") from exc


@router.post("/candidates/{candidate_id}/agent-plans")
def candidate_to_agents(candidate_id: str, max_markets: int = Query(default=3, ge=1, le=10)) -> dict:
    try:
        items = create_agent_plans(candidate_id, max_markets=max_markets)
        return {
            "candidate_id": candidate_id,
            "count": len(items),
            "invariant": "Agent = Origin Source × Fixed Horizon × Market Universe",
            "items": items,
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"candidate not found: {candidate_id}") from exc


@router.post("/agent-plans/{agent_id}/status")
def agent_plan_status(agent_id: str, body: AgentStatusUpdate) -> dict:
    try:
        return set_agent_status(
            agent_id,
            body.status,
            reason=body.reason,
            metadata=body.metadata,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"agent plan not found: {agent_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agent-plans/{agent_id}/status-history")
def agent_plan_status_history(agent_id: str) -> dict:
    try:
        items = list_agent_status_history(agent_id)
        return {"agent_id": agent_id, "count": len(items), "items": items}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"agent plan not found: {agent_id}") from exc


@router.post("/agent-plans/{agent_id}/resolve-universe")
def agent_plan_resolve_universe(
    agent_id: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    try:
        return resolve_agent_universe(agent_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"agent plan not found: {agent_id}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"universe resolution failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.get("/agent-plans/{agent_id}/universe")
def agent_plan_universe(agent_id: str) -> dict:
    items = list_agent_universe(agent_id)
    return {"agent_id": agent_id, "count": len(items), "items": items}


@router.get("/agent-plans/{agent_id}")
def agent_plan_detail(agent_id: str) -> dict:
    item = get_agent_plan(agent_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"agent plan not found: {agent_id}")
    return item


@router.get("/agent-plans")
def agent_plans(
    candidate_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    items = list_agent_plans(candidate_id=candidate_id, limit=limit)
    return {"count": len(items), "items": items}
