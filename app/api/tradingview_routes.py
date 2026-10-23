from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.tradingview import (
    collect_ideas,
    collect_market,
    collect_scripts,
    complete_missing_script_assets,
    backfill_tradingview_source,
    create_agent_plans,
    create_candidate_from_idea,
    create_candidate_from_script,
    fetch_script_source,
    fetch_source_detail,
    get_agent_plan,
    list_agent_plans,
    list_agent_universe,
    resolve_agent_universe,
    script_source_completion_status,
    list_candidates,
    list_collector_states,
    list_market_snapshots,
    list_stored_ideas,
    list_stored_scripts,
)

router = APIRouter(prefix="/api/v1/tradingview", tags=["tradingview"])

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
) -> dict:
    try:
        return collect_scripts(
            page=page,
            sort=sort,
            topic=topic,
            editors_picks=editors_picks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TradingView scripts collection failed: {type(exc).__name__}: {exc}",
        ) from exc


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

@router.get("/candidates")
def candidates(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    items = list_candidates(limit)
    return {"count": len(items), "items": items}


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
