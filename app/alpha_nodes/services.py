"""Typed read-only connectors to the EXISTING TradingView and Quant Lab APIs.

No user-controlled base URL or arbitrary path is accepted. Endpoint paths below
were verified against tradingview-service/app/api/tradingview_routes.py and
quant-lab-control/app/api/quant_routes.py. Writes are opt-in and separately
gated by Alpha's native dispatcher.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from typing import Any


def _base(service: str) -> tuple[str, dict[str, str]]:
    if service == "tradingview":
        uri = os.getenv("ALPHA_TRADINGVIEW_BASE", "https://autonomous-investor-tradingview-production.up.railway.app")
        token = os.getenv("ALPHA_TRADINGVIEW_TOKEN", "")
    elif service == "quant":
        uri = os.getenv("ALPHA_QUANT_BASE", "https://autonomous-investor-quant-lab-production.up.railway.app")
        token = os.getenv("ALPHA_QUANT_TOKEN", "")
    else:
        raise ValueError("unknown service")
    uri = uri.rstrip("/")
    parsed = urlsplit(uri)
    # Avoid accidental HTTP credential disclosure and unexpected SSRF.
    if not (
        (parsed.scheme == "https" and parsed.hostname)
        or (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"})
    ) or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("service base URL must be HTTPS (or loopback HTTP for tests)")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    return uri, headers


def _segment(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 240:
        raise ValueError("invalid service identifier")
    if value in {".", ".."}:
        raise ValueError("invalid service identifier")
    return quote(value, safe="")


def _request(service: str, path: str, *, query: dict[str, Any] | None = None,
             method: str = "GET", body: dict | None = None) -> dict:
    base, headers = _base(service)
    if not path.startswith("/api/v1/") or ".." in path:
        raise ValueError("non-whitelisted internal API path")
    params = {k: v for k, v in (query or {}).items() if v is not None}
    url = base + path
    if params:
        url += "?" + urlencode(params)
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read(3_000_001)
            if len(raw) > 3_000_000:
                raise ValueError("upstream JSON response exceeds 3 MB")
            decoded = json.loads(raw)
            if not isinstance(decoded, dict):
                raise ValueError("upstream response is not a JSON object")
            return decoded
    except HTTPError as exc:
        # Status is authoritative; do not include secret auth headers.
        raise RuntimeError(f"{service} HTTP {exc.code} on {path}") from exc
    except URLError as exc:
        raise ConnectionError(f"{service} is not reachable: {type(exc.reason).__name__}") from exc


# TradingView Source — exact routes from tradingview-service branch

def scripts_live(page: int = 1, sort: str = "recent_extended", script_type: str = "strategies") -> dict:
    """Tell the existing TradingView collector to fetch the newest public scripts.

    Uses the upstream /scripts/live read endpoint which both collects and stores
    an actual page. It is not a local-generated strategy or a cached DB read.
    """
    return _request("tradingview", "/api/v1/tradingview/scripts/live",
                    query={"page": page, "sort": sort, "script_type": script_type})


def script_catalog(limit: int = 50, offset: int = 0, script_type: str = "all") -> dict:
    return _request("tradingview", "/api/v1/tradingview/scripts/catalog",
                    query={"limit": limit, "offset": offset, "script_type": script_type})


def script_search(q: str, limit: int = 50) -> dict:
    return _request("tradingview", "/api/v1/tradingview/scripts/search",
                    query={"q": q, "limit": limit})


def script_meta(script_id_part: str) -> dict:
    return _request("tradingview", f"/api/v1/tradingview/scripts/{_segment(script_id_part)}/meta")


def script_source(script_id_part: str, version: str = "last") -> dict:
    return _request("tradingview", f"/api/v1/tradingview/scripts/{_segment(script_id_part)}/source",
                    query={"version": version})


def scripts_completion() -> dict:
    return _request("tradingview", "/api/v1/tradingview/scripts/completion")


def idea_list(limit: int = 100) -> dict:
    return _request("tradingview", "/api/v1/tradingview/ideas", query={"limit": limit})


def market_stored(market: str, limit: int = 100, offset: int = 0) -> dict:
    return _request("tradingview", f"/api/v1/tradingview/markets/{_segment(market)}/stored",
                    query={"limit": limit, "offset": offset})


def candidates(limit: int = 100) -> dict:
    return _request("tradingview", "/api/v1/tradingview/candidates", query={"limit": limit})


def agent_plan(agent_id: str) -> dict:
    return _request("tradingview", f"/api/v1/tradingview/agent-plans/{_segment(agent_id)}")


def agent_universe(agent_id: str) -> dict:
    return _request("tradingview", f"/api/v1/tradingview/agent-plans/{_segment(agent_id)}/universe")


# Quant Lab — exact routes from quant-lab-control branch

def quant_readiness() -> dict:
    return _request("quant", "/api/v1/quant/readiness")


def quant_pipeline() -> dict:
    return _request("quant", "/api/v1/quant/pipeline")


def quant_experiments(limit: int = 200) -> dict:
    return _request("quant", "/api/v1/quant/experiments", query={"limit": limit})


def quant_experiment(experiment_id: str) -> dict:
    return _request("quant", f"/api/v1/quant/experiments/{_segment(experiment_id)}")


def quant_experiment_results(experiment_id: str) -> dict:
    return _request("quant", f"/api/v1/quant/experiments/{_segment(experiment_id)}/results")


def quant_market_history(symbol: str, horizon: str, market: str = "", country: str = "") -> dict:
    return _request("quant", "/api/v1/quant/market-data/history",
                    query={"symbol": symbol, "horizon": horizon, "market": market, "country": country})


def quant_macro_snapshot() -> dict:
    return _request("quant", "/api/v1/quant/macro/snapshot")


def quant_handoff_status(min_score: float = 72.0) -> dict:
    return _request("quant", "/api/v1/quant/handoff/status",
                    query={"min_score": min_score})


def quant_experiment_create(agent_id: str, symbols: list[str] | None = None) -> dict:
    return _request("quant", f"/api/v1/quant/experiments/from-agent/{_segment(agent_id)}",
                    method="POST", body={"symbols": symbols or []})


def quant_experiment_run(experiment_id: str, max_symbols: int = 5,
                         commission_bps: float = 5.0, slippage_bps: float = 2.0) -> dict:
    return _request(
        "quant", f"/api/v1/quant/experiments/{_segment(experiment_id)}/run",
        method="POST",
        body={"max_symbols": max_symbols, "commission_bps": commission_bps,
              "slippage_bps": slippage_bps},
    )
