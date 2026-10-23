from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any
from urllib import request
from urllib.error import HTTPError

from app.core.toss_market import base_interval_for_horizon, credentials_configured

DB_PATH = os.getenv("QUANT_DB_PATH", "/tmp/quant_lab.sqlite3")
TRADINGVIEW_SERVICE_URL = os.getenv(
    "TRADINGVIEW_SERVICE_URL",
    "https://autonomous-investor-tradingview-production.up.railway.app",
).rstrip("/")
INTEGRATED_SERVICE_URL = os.getenv(
    "INTEGRATED_SERVICE_URL",
    "https://autonomous-investor-integrated-production.up.railway.app",
).rstrip("/")

EXPERIMENT_STATUSES = {
    "REGISTERED",
    "BLOCKED_UNIVERSE",
    "BLOCKED_DATA_SOURCE",
    "BLOCKED_STRATEGY_ENGINE",
    "READY",
    "RUNNING",
    "COMPLETED",
    "FAILED",
}


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                fixed_horizon TEXT NOT NULL,
                country TEXT NOT NULL,
                market TEXT NOT NULL,
                universe TEXT NOT NULL,
                symbols_json TEXT NOT NULL,
                data_source TEXT NOT NULL,
                base_interval TEXT NOT NULL,
                strategy_engine TEXT NOT NULL,
                validation_plan TEXT NOT NULL,
                status TEXT NOT NULL,
                blocked_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_experiments_agent
                ON experiments(agent_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS experiment_results (
                result_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                data_start TEXT,
                data_end TEXT,
                data_hash TEXT,
                metrics_json TEXT NOT NULL,
                diagnostics_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS promotion_decisions (
                decision_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                from_stage TEXT NOT NULL,
                to_stage TEXT NOT NULL,
                decision TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def _json_request(url: str, method: str = "GET") -> dict[str, Any]:
    req = request.Request(
        url,
        method=method,
        headers={
            "Accept": "application/json",
            "User-Agent": "AUTONOMOUS-INVESTOR-QuantLab/1.0",
        },
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"upstream HTTP {exc.code}: {detail[:500]}") from exc


def fetch_agent_plan(agent_id: str) -> dict[str, Any]:
    from urllib.parse import quote

    return _json_request(
        f"{TRADINGVIEW_SERVICE_URL}/api/v1/tradingview/agent-plans/{quote(agent_id, safe='')}"
    )


def resolve_agent_symbols(agent_id: str, limit: int = 20) -> list[str]:
    from urllib.parse import quote

    payload = _json_request(
        f"{TRADINGVIEW_SERVICE_URL}/api/v1/tradingview/agent-plans/{quote(agent_id, safe='')}/resolve-universe?limit={min(max(limit,1),100)}",
        method="POST",
    )
    symbols: list[str] = []
    for item in payload.get("items") or []:
        ticker = str(item.get("ticker") or "").strip()
        if not ticker:
            continue
        broker_symbol = ticker.split(":", 1)[-1]
        if broker_symbol and broker_symbol not in symbols:
            symbols.append(broker_symbol)
    return symbols


def _default_validation_plan() -> dict[str, Any]:
    return {
        "screen": {
            "engine": "vectorbt",
            "purpose": "high-throughput screening",
        },
        "walk_forward": {
            "enabled": True,
            "folds": 5,
            "anchored": True,
        },
        "holdout": {
            "enabled": True,
            "fraction": 0.20,
            "untouched_until_final": True,
        },
        "cost_model": {
            "commission": "broker_actual_or_configured",
            "slippage": "market_liquidity_model",
        },
        "final_runtime": {
            "engine": "NautilusTrader",
            "modes": ["backtest", "paper", "live"],
        },
    }


def _toss_supported_for_plan(plan: dict[str, Any]) -> bool:
    country = str(plan.get("country") or "").lower()
    market = str(plan.get("market") or "").lower()
    if "가상자산" in country or country == "fx":
        return False
    if "선물" in country or "cme" in market or "선물" in market:
        return False
    return any(
        token in country or token in market
        for token in ("한국", "미국", "etf", "kospi", "kosdaq", "nasdaq", "nyse")
    )


def _initial_blocker(plan: dict[str, Any], symbols: list[str]) -> tuple[str, str | None]:
    if not symbols:
        return (
            "BLOCKED_UNIVERSE",
            "TradingView market pre-screen did not resolve concrete instrument symbols for this Agent.",
        )
    if not _toss_supported_for_plan(plan):
        return (
            "BLOCKED_DATA_SOURCE",
            "This asset class is outside Toss Securities KR/US stock candle coverage; a matching historical data provider is required.",
        )
    if not credentials_configured():
        return (
            "BLOCKED_DATA_SOURCE",
            "Toss Open API credentials are not configured in Railway.",
        )
    return (
        "BLOCKED_STRATEGY_ENGINE",
        "Historical data can be requested, but a licensed/sandboxed Pine or StrategySpec executor has not been attached yet.",
    )


def create_experiment(agent_id: str, symbols: list[str] | None = None) -> dict[str, Any]:
    init_db()
    plan = fetch_agent_plan(agent_id)
    requested_symbols = [x.strip() for x in (symbols or []) if x and x.strip()]
    if requested_symbols:
        symbol_list = sorted(set(requested_symbols))
    else:
        try:
            symbol_list = resolve_agent_symbols(agent_id, limit=20)
        except Exception:
            symbol_list = []
    identity = "|".join(
        [
            agent_id,
            plan["source_id"],
            plan["fixed_horizon"],
            ",".join(symbol_list),
        ]
    )
    experiment_id = "EXP-" + hashlib.sha1(identity.encode()).hexdigest()[:14].upper()
    status, reason = _initial_blocker(plan, symbol_list)
    now = utcnow()
    validation_plan = _default_validation_plan()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO experiments (
                experiment_id,agent_id,candidate_id,source_id,fixed_horizon,country,market,universe,
                symbols_json,data_source,base_interval,strategy_engine,validation_plan,status,
                blocked_reason,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(experiment_id) DO UPDATE SET
                symbols_json=excluded.symbols_json,
                status=excluded.status,
                blocked_reason=excluded.blocked_reason,
                updated_at=excluded.updated_at
            """,
            (
                experiment_id,
                agent_id,
                plan["candidate_id"],
                plan["source_id"],
                plan["fixed_horizon"],
                plan["country"],
                plan["market"],
                plan["universe"],
                json.dumps(symbol_list, ensure_ascii=False),
                "Toss Securities Open API",
                base_interval_for_horizon(plan["fixed_horizon"]),
                "UNASSIGNED",
                json.dumps(validation_plan, ensure_ascii=False),
                status,
                reason,
                now,
                now,
            ),
        )
    return get_experiment(experiment_id)


def get_experiment(experiment_id: str) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM experiments WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
    if row is None:
        raise KeyError(experiment_id)
    item = dict(row)
    item["symbols"] = json.loads(item.pop("symbols_json"))
    item["validation_plan"] = json.loads(item["validation_plan"])
    return item


def list_experiments(limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT experiment_id FROM experiments ORDER BY created_at DESC LIMIT ?",
            (min(max(limit, 1), 1000),),
        ).fetchall()
    return [get_experiment(str(row["experiment_id"])) for row in rows]


def update_symbols(experiment_id: str, symbols: list[str]) -> dict[str, Any]:
    current = get_experiment(experiment_id)
    symbol_list = sorted({x.strip() for x in symbols if x and x.strip()})
    plan = {
        "source_id": current["source_id"],
        "fixed_horizon": current["fixed_horizon"],
    }
    status, reason = _initial_blocker(plan, symbol_list)
    now = utcnow()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE experiments
            SET symbols_json=?, status=?, blocked_reason=?, updated_at=?
            WHERE experiment_id=?
            """,
            (
                json.dumps(symbol_list, ensure_ascii=False),
                status,
                reason,
                now,
                experiment_id,
            ),
        )
    return get_experiment(experiment_id)


def readiness() -> dict[str, Any]:
    toss_ready = credentials_configured()
    pine_engine_url = os.getenv("PINE_ENGINE_URL")
    return {
        "service": "quant-lab-control",
        "status": "ok",
        "tradingview_source_service": TRADINGVIEW_SERVICE_URL,
        "integrated_quant_service": INTEGRATED_SERVICE_URL,
        "data_sources": {
            "toss": {
                "configured": toss_ready,
                "official_intervals": ["1m", "1d"],
                "role": "KR/US historical OHLCV and later live execution data",
            }
        },
        "strategy_execution": {
            "pine_engine_configured": bool(pine_engine_url),
            "pine_engine_url": pine_engine_url,
            "policy": "Do not fabricate performance. Experiment stays blocked until a licensed/sandboxed executor is attached.",
        },
        "quant_engines": {
            "integrated_service": INTEGRATED_SERVICE_URL,
            "state": "native bridges installed; experiment executor orchestration still being built",
        },
    }
