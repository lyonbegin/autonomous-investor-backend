from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.tradingview import list_agent_plans, list_candidates

router = APIRouter(prefix="/api/v1/public", tags=["public"])


def _strategy_view(candidate: dict, agents: list[dict]) -> dict:
    statuses: dict[str, int] = {}
    horizons: list[str] = []
    markets: list[str] = []
    countries: list[str] = []
    for agent in agents:
        status = str(agent.get("status") or "UNKNOWN")
        statuses[status] = statuses.get(status, 0) + 1
        horizon = str(agent.get("fixed_horizon") or "")
        market = str(agent.get("market") or "")
        country = str(agent.get("country") or "")
        if horizon and horizon not in horizons:
            horizons.append(horizon)
        if market and market not in markets:
            markets.append(market)
        if country and country not in countries:
            countries.append(country)
    return {
        "candidate_id": candidate.get("candidate_id"),
        "source_kind": candidate.get("source_kind"),
        "source_id": candidate.get("source_id"),
        "name": candidate.get("name"),
        "category": candidate.get("category"),
        "domain": candidate.get("domain"),
        "logic": candidate.get("logic"),
        "candidate_horizons": candidate.get("candidate_horizons") or [],
        "status": candidate.get("status"),
        "created_at": candidate.get("created_at"),
        "agent_count": len(agents),
        "agent_statuses": statuses,
        "active_agent_count": sum(
            statuses.get(x, 0)
            for x in ("PAPER", "SHADOW", "SMALL_LIVE", "LIVE", "RESEARCH", "BACKTEST")
        ),
        "fixed_horizons": horizons,
        "markets": markets,
        "countries": countries,
        "agents": agents,
    }


@router.get("/strategies")
def public_strategies(
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = None,
    source_kind: str | None = None,
) -> dict:
    candidates = list_candidates(limit=limit)
    all_agents = list_agent_plans(limit=1000)
    by_candidate: dict[str, list[dict]] = {}
    for agent in all_agents:
        by_candidate.setdefault(str(agent.get("candidate_id") or ""), []).append(agent)

    items = []
    for candidate in candidates:
        if status and str(candidate.get("status") or "").upper() != status.upper():
            continue
        if source_kind and str(candidate.get("source_kind") or "").lower() != source_kind.lower():
            continue
        items.append(
            _strategy_view(
                candidate,
                by_candidate.get(str(candidate.get("candidate_id") or ""), []),
            )
        )
    return {"count": len(items), "items": items}


@router.get("/strategies/{candidate_id}")
def public_strategy(candidate_id: str) -> dict:
    candidates = list_candidates(limit=500)
    candidate = next((x for x in candidates if str(x.get("candidate_id")) == candidate_id), None)
    if candidate is None:
        raise HTTPException(status_code=404, detail="strategy not found")
    agents = list_agent_plans(candidate_id=candidate_id, limit=1000)
    return _strategy_view(candidate, agents)


@router.get("/agents")
def public_agents(
    limit: int = Query(default=200, ge=1, le=1000),
    status: str | None = None,
) -> dict:
    rows = list_agent_plans(limit=limit)
    if status:
        rows = [x for x in rows if str(x.get("status") or "").upper() == status.upper()]
    return {"count": len(rows), "items": rows}


@router.get("/agents/{agent_id}")
def public_agent(agent_id: str) -> dict:
    rows = list_agent_plans(limit=1000)
    agent = next((x for x in rows if str(x.get("agent_id")) == agent_id), None)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    candidate_id = str(agent.get("candidate_id") or "")
    candidate = next(
        (x for x in list_candidates(limit=500) if str(x.get("candidate_id")) == candidate_id),
        None,
    )
    return {"agent": agent, "strategy": candidate}
