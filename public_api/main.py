from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

TV_API = os.getenv("TRADINGVIEW_API", "https://autonomous-investor-tradingview-production.up.railway.app").rstrip("/")
QUANT_API = os.getenv("QUANT_API", "https://autonomous-investor-quant-lab-production.up.railway.app").rstrip("/")

app = FastAPI(title="Autonomous Investor Public API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


async def _get(base: str, path: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        r = await client.get(base + path, headers={"User-Agent": "AUTONOMOUS-INVESTOR-PUBLIC/1.0"})
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"upstream {r.status_code}: {path}")
    return r.json()


def _metrics(exp: dict[str, Any] | None) -> dict[str, Any] | None:
    if not exp:
        return None
    summary = exp.get("validation_summary") or {}
    items = summary.get("items") or []
    holdouts = []
    for item in items:
        metrics = (((item.get("validation") or {}).get("holdout") or {}).get("metrics") or {})
        if metrics:
            holdouts.append(metrics)
    if not holdouts:
        return {
            "experiment_status": exp.get("status"),
            "strategy_engine": exp.get("strategy_engine"),
            "blocked_reason": exp.get("blocked_reason"),
            "promotion": summary.get("promotion"),
        }
    avg = lambda key: sum(float(x.get(key) or 0) for x in holdouts) / max(1, len(holdouts))
    return {
        "experiment_status": exp.get("status"),
        "strategy_engine": exp.get("strategy_engine"),
        "promotion": summary.get("promotion"),
        "holdout_return_pct": round(avg("net_return") * 100, 2),
        "max_drawdown_pct": round(avg("max_drawdown") * 100, 2),
        "trade_sharpe": round(avg("trade_sharpe"), 3),
        "win_rate_pct": round(avg("win_rate") * 100, 1),
        "trade_count": int(sum(int(x.get("trade_count") or 0) for x in holdouts)),
        "pass_ratio": summary.get("pass_ratio"),
    }


async def _bundle(limit: int = 300) -> dict[str, Any]:
    candidates, agents, handoff, sources, experiments = await _parallel(
        (TV_API, f"/api/v1/tradingview/candidates?limit={min(limit,500)}"),
        (TV_API, f"/api/v1/tradingview/agent-plans?limit={min(limit*4,1000)}"),
        (TV_API, f"/api/v1/quant-handoff/agents?limit={min(limit*4,1000)}&min_score=0"),
        (TV_API, f"/api/v1/strategy-sources?limit={min(limit*2,1000)}"),
        (QUANT_API, f"/api/v1/quant/experiments?limit={min(limit*4,1000)}"),
    )
    return {
        "candidates": candidates.get("items") or [],
        "agents": agents.get("items") or [],
        "handoff": handoff.get("items") or [],
        "sources": sources.get("items") or [],
        "experiments": experiments.get("items") or [],
    }


async def _parallel(*pairs: tuple[str, str]) -> list[dict[str, Any]]:
    import asyncio
    return list(await asyncio.gather(*[_get(base, path) for base, path in pairs]))


def _index(bundle: dict[str, Any]) -> dict[str, Any]:
    candidates = {x.get("candidate_id"): x for x in bundle["candidates"]}
    sources = {x.get("source_id"): x for x in bundle["sources"]}
    handoff = {x.get("agent_id"): x for x in bundle["handoff"]}

    agents_by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in bundle["agents"]:
        agent = dict(raw)
        agent.update({k: v for k, v in (handoff.get(agent.get("agent_id")) or {}).items() if v is not None})
        agents_by_candidate[str(agent.get("candidate_id"))].append(agent)

    exp_by_agent: dict[str, dict[str, Any]] = {}
    for exp in bundle["experiments"]:
        aid = str(exp.get("agent_id") or "")
        current = exp_by_agent.get(aid)
        if current is None or str(exp.get("updated_at") or "") > str(current.get("updated_at") or ""):
            exp_by_agent[aid] = exp

    return {
        "candidates": candidates,
        "sources": sources,
        "agents_by_candidate": agents_by_candidate,
        "experiments": exp_by_agent,
    }


def _agent_view(agent: dict[str, Any], candidate: dict[str, Any] | None, exp: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "agent_id": agent.get("agent_id"),
        "candidate_id": agent.get("candidate_id"),
        "strategy_name": (candidate or {}).get("name"),
        "fixed_horizon": agent.get("fixed_horizon"),
        "market": agent.get("market"),
        "country": agent.get("country"),
        "universe": agent.get("universe"),
        "status": agent.get("status"),
        "fit_score": agent.get("fit_score"),
        "market_score": agent.get("market_score"),
        "horizon_score": agent.get("horizon_score"),
        "source_score": agent.get("source_score"),
        "target_score": agent.get("target_score"),
        "rationale": agent.get("rationale"),
        "experiment_id": (exp or {}).get("experiment_id"),
        "experiment_status": (exp or {}).get("status"),
        "strategy_engine": (exp or {}).get("strategy_engine"),
        "blocked_reason": (exp or {}).get("blocked_reason"),
        "performance": _metrics(exp),
    }


def _strategy_view(candidate: dict[str, Any], idx: dict[str, Any]) -> dict[str, Any]:
    source = idx["sources"].get(candidate.get("source_id")) or {}
    raw_agents = idx["agents_by_candidate"].get(str(candidate.get("candidate_id")), [])
    agents = [
        _agent_view(a, candidate, idx["experiments"].get(str(a.get("agent_id"))))
        for a in raw_agents
    ]
    completed = [a for a in agents if a.get("performance") and a["performance"].get("holdout_return_pct") is not None]
    best = max(completed, key=lambda x: x["performance"]["holdout_return_pct"]) if completed else None
    return {
        "candidate_id": candidate.get("candidate_id"),
        "name": candidate.get("name"),
        "category": candidate.get("category"),
        "domain": candidate.get("domain"),
        "logic": candidate.get("logic"),
        "candidate_horizons": candidate.get("candidate_horizons") or [],
        "status": candidate.get("status"),
        "created_at": candidate.get("created_at"),
        "source_kind": candidate.get("source_kind"),
        "source_id": candidate.get("source_id"),
        "source_name": source.get("source_name") or candidate.get("name"),
        "source_url": source.get("source_url"),
        "author": (source.get("metadata") or {}).get("author"),
        "source_symbol": (source.get("metadata") or {}).get("symbol"),
        "source_interval": (source.get("metadata") or {}).get("interval"),
        "pine_version": (source.get("metadata") or {}).get("pine_version"),
        "source_version": source.get("source_version"),
        "agent_count": len(agents),
        "agents": agents,
        "best_performance": best.get("performance") if best else None,
        "research_state": {
            "ready": sum(1 for a in agents if a.get("experiment_status") == "READY"),
            "blocked": sum(1 for a in agents if str(a.get("experiment_status") or "").startswith("BLOCKED")),
            "completed": len(completed),
            "research": sum(1 for a in agents if a.get("status") == "RESEARCH"),
        },
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "autonomous-investor-public-api"}


@app.get("/api/public/ideas")
async def ideas(
    page: int = Query(default=1, ge=1),
    sort: str = Query(default="recent"),
) -> dict[str, Any]:
    return await _get(TV_API, f"/api/v1/tradingview/ideas/live?page={page}&sort={sort}&lang=ko")


@app.get("/api/public/strategies")
async def strategies(
    limit: int = Query(default=100, ge=1, le=300),
    category: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    bundle = await _bundle(limit=max(limit, 100))
    idx = _index(bundle)
    items = [_strategy_view(c, idx) for c in bundle["candidates"]]
    if category:
        items = [x for x in items if x.get("category") == category]
    if status:
        items = [x for x in items if any(a.get("status") == status for a in x["agents"])]
    return {"count": min(len(items), limit), "items": items[:limit]}


@app.get("/api/public/strategies/{candidate_id}")
async def strategy(candidate_id: str) -> dict[str, Any]:
    bundle = await _bundle(limit=300)
    idx = _index(bundle)
    candidate = idx["candidates"].get(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="strategy not found")
    return _strategy_view(candidate, idx)


@app.get("/api/public/agents")
async def agents(limit: int = Query(default=200, ge=1, le=500)) -> dict[str, Any]:
    bundle = await _bundle(limit=300)
    idx = _index(bundle)
    rows = []
    for cid, group in idx["agents_by_candidate"].items():
        candidate = idx["candidates"].get(cid)
        for agent in group:
            rows.append(_agent_view(agent, candidate, idx["experiments"].get(str(agent.get("agent_id")))))
    rows.sort(key=lambda x: (float(x.get("fit_score") or 0), str(x.get("agent_id") or "")), reverse=True)
    return {"count": min(len(rows), limit), "items": rows[:limit]}


@app.get("/api/public/agents/{agent_id}")
async def agent(agent_id: str) -> dict[str, Any]:
    bundle = await _bundle(limit=300)
    idx = _index(bundle)
    for cid, group in idx["agents_by_candidate"].items():
        for raw in group:
            if raw.get("agent_id") == agent_id:
                return _agent_view(raw, idx["candidates"].get(cid), idx["experiments"].get(agent_id))
    raise HTTPException(status_code=404, detail="agent not found")


@app.get("/api/public/markets/{market}")
async def market(
    market: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="volume"),
    sort_order: str = Query(default="desc"),
) -> dict[str, Any]:
    return await _get(
        TV_API,
        f"/api/v1/tradingview/markets/{market}?limit={limit}&offset={offset}&sort_by={sort_by}&sort_order={sort_order}",
    )


@app.get("/api/public/summary")
async def summary() -> dict[str, Any]:
    bundle = await _bundle(limit=300)
    idx = _index(bundle)
    strategies = [_strategy_view(c, idx) for c in bundle["candidates"]]
    agent_rows = [a for s in strategies for a in s["agents"]]
    return {
        "strategy_count": len(strategies),
        "agent_count": len(agent_rows),
        "ready_experiments": sum(1 for a in agent_rows if a.get("experiment_status") == "READY"),
        "blocked_experiments": sum(1 for a in agent_rows if str(a.get("experiment_status") or "").startswith("BLOCKED")),
        "completed_performance": sum(1 for a in agent_rows if a.get("performance") and a["performance"].get("holdout_return_pct") is not None),
        "markets": sorted({str(a.get("market")) for a in agent_rows if a.get("market")}),
        "invariant": "Agent = immutable strategy source × fixed horizon × market universe",
    }


@app.post("/api/public/self-test")
async def self_test() -> dict[str, Any]:
    result = await summary()
    print(
        "PUBLIC_SELF_TEST",
        {
            "strategy_count": result.get("strategy_count"),
            "agent_count": result.get("agent_count"),
            "ready_experiments": result.get("ready_experiments"),
            "completed_performance": result.get("completed_performance"),
        },
        flush=True,
    )
    return {"status": "ok", **result}
