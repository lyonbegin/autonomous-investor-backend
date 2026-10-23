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
    "SUPERSEDED",
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
            UPDATE experiments
            SET status='SUPERSEDED',
                blocked_reason=?,
                updated_at=?
            WHERE agent_id=?
              AND experiment_id<>?
              AND status IN (
                'REGISTERED','BLOCKED_UNIVERSE','BLOCKED_DATA_SOURCE',
                'BLOCKED_STRATEGY_ENGINE','READY','RUNNING','FAILED'
              )
            """,
            (
                f"Superseded by {experiment_id} because the Agent experiment inputs/universe changed.",
                now,
                agent_id,
                experiment_id,
            ),
        )
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
        "country": current["country"],
        "market": current["market"],
        "universe": current["universe"],
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


def _integration_probe_map() -> tuple[dict[str, bool], str | None]:
    try:
        payload = _json_request(
            f"{INTEGRATED_SERVICE_URL}/api/v1/integrations?probe_runtime=true"
        )
        rows = payload.get("integrations") or []
        return (
            {
                str(row.get("key")): bool(row.get("installed") and row.get("import_ok"))
                for row in rows
            },
            None,
        )
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def pipeline_status() -> dict[str, Any]:
    engines, probe_error = _integration_probe_map()

    def ready(*keys: str) -> bool:
        return bool(keys) and all(engines.get(key, False) for key in keys)

    tv_ready = False
    try:
        tv_health = _json_request(f"{TRADINGVIEW_SERVICE_URL}/health")
        tv_ready = tv_health.get("status") == "ok"
    except Exception:
        tv_ready = False

    toss_ready = credentials_configured()
    pine_ready = bool(os.getenv("PINE_ENGINE_URL"))

    stages = [
        {
            "order": 1,
            "key": "research_agent",
            "name": "Research Agent",
            "engines": ["TradingAgents", "FinRobot V2"],
            "engine_ready": ready("tradingagents", "finrobot"),
            "state": "ENGINE_READY" if ready("tradingagents", "finrobot") else "ENGINE_BLOCKED",
            "blocker": "Research orchestration/API 실행계층은 아직 연결 전" if ready("tradingagents", "finrobot") else "필수 Research 엔진 import 실패",
        },
        {
            "order": 2,
            "key": "market_agent",
            "name": "Market Agent",
            "engines": ["TradingView Source", "TradingAgents"],
            "engine_ready": ready("tradingagents"),
            "state": "DATA_READY" if tv_ready else "BLOCKED_DATA_SOURCE",
            "blocker": "실시간 TradingView 데이터는 연결됨; Agent 연구 오케스트레이션은 다음 단계" if tv_ready else "TradingView Source 서비스 미연결",
        },
        {
            "order": 3,
            "key": "macro_agent",
            "name": "Macro Agent",
            "engines": ["TradingAgents", "FinRobot V2"],
            "engine_ready": ready("tradingagents", "finrobot"),
            "state": "BLOCKED_DATA_SOURCE",
            "blocker": "실제 거시 데이터 공급원(FRED/공식 경제지표) 미연결",
        },
        {
            "order": 4,
            "key": "hypothesis_engine",
            "name": "Hypothesis Engine",
            "engines": ["RD-Agent(Q)"],
            "engine_ready": ready("rdagent"),
            "state": "ENGINE_READY" if ready("rdagent") else "ENGINE_BLOCKED",
            "blocker": "RD-Agent native engine은 준비됨; TradingView Candidate→RD-Agent loop 연결 전" if ready("rdagent") else "RD-Agent import 실패",
        },
        {
            "order": 5,
            "key": "python_experiment_engine",
            "name": "Python Experiment Engine",
            "engines": ["RD-Agent(Q)", "vectorbt"],
            "engine_ready": ready("rdagent", "vectorbt"),
            "state": "CONTROL_READY",
            "blocker": "Experiment Registry/Universe는 동작; 전략 실행기와 시계열 데이터가 준비돼야 실제 실행 가능",
        },
        {
            "order": 6,
            "key": "classical_ml",
            "name": "Classical ML",
            "engines": ["Qlib"],
            "engine_ready": ready("qlib"),
            "state": "ENGINE_READY" if ready("qlib") else "ENGINE_BLOCKED",
            "blocker": "Qlib 모델 학습 orchestration 미연결" if ready("qlib") else "Qlib import 실패",
        },
        {
            "order": 7,
            "key": "foundation_model",
            "name": "Foundation Model",
            "engines": ["Chronos"],
            "engine_ready": ready("chronos"),
            "state": "ENGINE_READY" if ready("chronos") else "ENGINE_BLOCKED",
            "blocker": "Chronos forecast orchestration 미연결" if ready("chronos") else "Chronos import 실패",
        },
        {
            "order": 8,
            "key": "reinforcement_learning",
            "name": "RL",
            "engines": ["Stable-Baselines3", "Ray RLlib", "FinRL-Trading"],
            "engine_ready": ready("sb3", "rllib", "finrl"),
            "state": "ENGINE_READY" if ready("sb3", "rllib", "finrl") else "ENGINE_BLOCKED",
            "blocker": "RL train/eval orchestration 미연결" if ready("sb3", "rllib", "finrl") else "RL 엔진 일부 import 실패",
        },
        {
            "order": 9,
            "key": "walk_forward",
            "name": "Walk-forward Test",
            "engines": ["vectorbt", "Qlib"],
            "engine_ready": ready("vectorbt", "qlib"),
            "state": "BLOCKED_STRATEGY_ENGINE" if not pine_ready else ("BLOCKED_DATA_SOURCE" if not toss_ready else "READY"),
            "blocker": "Pine/StrategySpec 실행기 미연결" if not pine_ready else ("실제 OHLCV 자격증명 미설정" if not toss_ready else None),
        },
        {
            "order": 10,
            "key": "holdout_validation",
            "name": "Holdout Validation",
            "engines": ["vectorbt", "Qlib"],
            "engine_ready": ready("vectorbt", "qlib"),
            "state": "BLOCKED_STRATEGY_ENGINE" if not pine_ready else ("BLOCKED_DATA_SOURCE" if not toss_ready else "READY"),
            "blocker": "Pine/StrategySpec 실행기 미연결" if not pine_ready else ("실제 OHLCV 자격증명 미설정" if not toss_ready else None),
        },
        {
            "order": 11,
            "key": "portfolio_engine",
            "name": "Portfolio Engine",
            "engines": ["Riskfolio-Lib", "PyPortfolioOpt", "FinRL-Trading"],
            "engine_ready": ready("riskfolio", "pyportfolioopt", "finrl"),
            "state": "ENGINE_READY" if ready("riskfolio", "pyportfolioopt", "finrl") else "ENGINE_BLOCKED",
            "blocker": "검증 완료 전략의 TargetPortfolio 연결 전" if ready("riskfolio", "pyportfolioopt", "finrl") else "Portfolio 엔진 일부 import 실패",
        },
        {
            "order": 12,
            "key": "risk_gate",
            "name": "Risk Gate",
            "engines": ["Riskfolio-Lib", "NautilusTrader"],
            "engine_ready": ready("riskfolio", "nautilus"),
            "state": "ENGINE_READY" if ready("riskfolio", "nautilus") else "ENGINE_BLOCKED",
            "blocker": "실제 Portfolio→RiskDecision→Execution 연결 전" if ready("riskfolio", "nautilus") else "Risk/Execution 엔진 import 실패",
        },
        {
            "order": 13,
            "key": "paper_trading",
            "name": "Paper Trading",
            "engines": ["NautilusTrader"],
            "engine_ready": ready("nautilus"),
            "state": "BLOCKED_STRATEGY_ENGINE" if not pine_ready else ("BLOCKED_DATA_SOURCE" if not toss_ready else "READY"),
            "blocker": "검증 가능한 전략 실행기 미연결" if not pine_ready else ("시세/브로커 데이터 자격증명 미설정" if not toss_ready else None),
        },
        {
            "order": 14,
            "key": "live_trading",
            "name": "Live Trading",
            "engines": ["NautilusTrader"],
            "engine_ready": ready("nautilus"),
            "state": "OFF",
            "blocker": "실거래는 의도적으로 OFF. 백테스트→Walk-forward→Holdout→Paper 통과 후에만 승격",
        },
    ]

    return {
        "count": 14,
        "pipeline": "Research Agent → Market Agent → Macro Agent → Hypothesis Engine → Python Experiment Engine → Classical ML / Foundation Model / RL → Walk-forward Test → Holdout Validation → Portfolio Engine → Risk Gate → Paper Trading → Live Trading",
        "integrated_engine_probe_error": probe_error,
        "tradingview_ready": tv_ready,
        "toss_ready": toss_ready,
        "pine_executor_ready": pine_ready,
        "stages": stages,
    }
