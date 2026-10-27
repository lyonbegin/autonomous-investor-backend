from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any
from urllib import request
from urllib.error import HTTPError

from app.core.internal_http import internal_json_request

from app.core.toss_market import base_interval_for_horizon, credentials_configured
from app.core.macro_data import macro_ready
from app.core.market_history import fetch_history_for_agent
from app.core.strategy_spec import StrategySpecError, compile_pine_to_spec, run_validation

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
        migrations = [
            ("experiments", "strategy_spec_json", "TEXT"),
            ("experiments", "source_hash", "TEXT"),
            ("experiments", "validation_summary_json", "TEXT"),
            ("experiments", "completed_at", "TEXT"),
        ]
        for table, column, definition in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass


def _json_request(
    url: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from urllib.parse import urlsplit

    target = urlsplit(url)
    headers = {}
    for base, name in (
        (TRADINGVIEW_SERVICE_URL, "TRADINGVIEW_SERVICE_TOKEN"),
        (INTEGRATED_SERVICE_URL, "INTEGRATED_SERVICE_TOKEN"),
    ):
        trusted = urlsplit(base)
        if (target.scheme, target.netloc) == (trusted.scheme, trusted.netloc):
            token = os.getenv(name, "")
            if token:
                headers["Authorization"] = "Bearer " + token
            break
    return internal_json_request(url, method=method, payload=payload, timeout=20, headers=headers)

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
        if ticker and ticker not in symbols:
            symbols.append(ticker)
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


def _source_spec(source_id: str) -> tuple[dict[str, Any] | None, str | None]:
    from urllib.parse import quote

    try:
        payload = _json_request(
            f"{TRADINGVIEW_SERVICE_URL}/api/v1/tradingview/scripts/{quote(source_id, safe='')}/source"
        )
        if not payload.get("ok"):
            return None, str(payload.get("reason") or "Pine source unavailable")
        source = str(payload.get("source") or "")
        if not source:
            return None, "Pine source is empty"
        return compile_pine_to_spec(source_id, source), None
    except StrategySpecError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _history_supported(plan: dict[str, Any], symbols: list[str]) -> tuple[bool, str | None]:
    if not symbols:
        return False, "TradingView market pre-screen did not resolve concrete instrument symbols for this Agent."
    text = " ".join([
        str(plan.get("country") or ""),
        str(plan.get("market") or ""),
        " ".join(symbols),
    ]).lower()
    if any(token in text for token in ("vn30", "hose:", "hnx:", "외환", " forex", "fx ")):
        return False, "Historical provider for this FX/Vietnam futures market is not connected yet."
    unsupported_exchanges = ("gate:", "bybit:", "okx:")
    if any(token in text for token in unsupported_exchanges):
        return False, "Historical provider for this crypto exchange is not connected yet."
    return True, None


def _initial_blocker(
    plan: dict[str, Any],
    symbols: list[str],
    spec: dict[str, Any] | None,
    spec_error: str | None,
) -> tuple[str, str | None]:
    if not symbols:
        return "BLOCKED_UNIVERSE", "TradingView market pre-screen did not resolve concrete instrument symbols for this Agent."
    if spec is None:
        return "BLOCKED_STRATEGY_ENGINE", f"StrategySpec-v1 unsupported Pine semantics: {spec_error or 'unknown'}"
    history_ok, history_reason = _history_supported(plan, symbols)
    if not history_ok:
        return "BLOCKED_DATA_SOURCE", history_reason
    return "READY", None


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

    spec, spec_error = _source_spec(str(plan["source_id"]))
    source_hash = str((spec or {}).get("source_hash") or "")
    identity = "|".join(
        [
            agent_id,
            str(plan["source_id"]),
            str(plan["fixed_horizon"]),
            ",".join(symbol_list),
            source_hash,
        ]
    )
    experiment_id = "EXP-" + hashlib.sha1(identity.encode()).hexdigest()[:14].upper()
    status, reason = _initial_blocker(plan, symbol_list, spec, spec_error)
    now = utcnow()
    validation_plan = _default_validation_plan()
    data_source = "Yahoo Finance chart API / Binance public klines"

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
                f"Superseded by {experiment_id} because the Agent experiment inputs/source changed.",
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
                blocked_reason,created_at,updated_at,strategy_spec_json,source_hash
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(experiment_id) DO UPDATE SET
                symbols_json=excluded.symbols_json,
                data_source=excluded.data_source,
                strategy_engine=excluded.strategy_engine,
                validation_plan=excluded.validation_plan,
                status=excluded.status,
                blocked_reason=excluded.blocked_reason,
                strategy_spec_json=excluded.strategy_spec_json,
                source_hash=excluded.source_hash,
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
                data_source,
                base_interval_for_horizon(plan["fixed_horizon"]),
                "StrategySpec-v1" if spec else "UNSUPPORTED_PINE",
                json.dumps(validation_plan, ensure_ascii=False),
                status,
                reason,
                now,
                now,
                json.dumps(spec, ensure_ascii=False) if spec else None,
                source_hash or None,
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
    item["strategy_spec"] = json.loads(item["strategy_spec_json"]) if item.get("strategy_spec_json") else None
    item["validation_summary"] = json.loads(item["validation_summary_json"]) if item.get("validation_summary_json") else None
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
    spec = current.get("strategy_spec")
    status, reason = _initial_blocker(
        plan,
        symbol_list,
        spec,
        None if spec else "StrategySpec not compiled",
    )
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


def _notify_agent_validation_status(
    agent_id: str,
    *,
    promoted: bool,
    experiment_id: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    from urllib.parse import quote

    status = "PAPER_CANDIDATE" if promoted else "REJECTED_VALIDATION"
    reason = (
        "Walk-forward + holdout validation passed"
        if promoted
        else "Walk-forward/holdout validation gate rejected this Agent"
    )
    return _json_request(
        f"{TRADINGVIEW_SERVICE_URL}/api/v1/tradingview/agent-plans/{quote(agent_id, safe='')}/status",
        method="POST",
        payload={
            "status": status,
            "reason": reason,
            "metadata": {
                "experiment_id": experiment_id,
                "pass_ratio": summary.get("pass_ratio"),
                "avg_holdout_return": summary.get("avg_holdout_return"),
                "passed_symbols": summary.get("passed_symbols"),
                "symbols_completed": summary.get("symbols_completed"),
                "promotion": summary.get("promotion"),
            },
        },
    )


def _result_id(experiment_id: str, stage: str) -> str:
    return "RES-" + hashlib.sha1(f"{experiment_id}|{stage}|{utcnow()}".encode()).hexdigest()[:16].upper()


def list_experiment_results(experiment_id: str) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM experiment_results
            WHERE experiment_id=?
            ORDER BY created_at ASC
            """,
            (experiment_id,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metrics"] = json.loads(item.pop("metrics_json") or "{}")
        item["diagnostics"] = json.loads(item.pop("diagnostics_json") or "{}")
        out.append(item)
    return out


def run_experiment(
    experiment_id: str,
    *,
    max_symbols: int = 5,
    commission_bps: float = 5.0,
    slippage_bps: float = 2.0,
) -> dict[str, Any]:
    experiment = get_experiment(experiment_id)
    if experiment["status"] != "READY":
        raise RuntimeError(
            f"experiment is not READY: {experiment['status']} - {experiment.get('blocked_reason') or ''}"
        )
    spec = experiment.get("strategy_spec")
    if not spec:
        raise RuntimeError("StrategySpec is missing")

    symbols = list(experiment.get("symbols") or [])[: min(max(int(max_symbols), 1), 20)]
    now = utcnow()
    with _connect() as conn:
        conn.execute(
            "UPDATE experiments SET status='RUNNING', blocked_reason=NULL, updated_at=? WHERE experiment_id=?",
            (now, experiment_id),
        )

    per_symbol: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for symbol in symbols:
        try:
            history = fetch_history_for_agent(
                symbol,
                horizon=str(experiment["fixed_horizon"]),
                market=str(experiment["market"]),
                country=str(experiment["country"]),
            )
            bars = list(history.get("bars") or [])
            validation = run_validation(
                spec,
                bars,
                folds=5,
                holdout_fraction=0.20,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
            )
            item = {
                "symbol": symbol,
                "provider": history.get("provider"),
                "provider_symbol": history.get("provider_symbol"),
                "base_interval": history.get("base_interval"),
                "effective_interval": history.get("effective_interval"),
                "bar_count": len(bars),
                "validation": validation,
            }
            per_symbol.append(item)

            with _connect() as conn:
                for stage, payload in [
                    ("WALK_FORWARD", validation["walk_forward"]),
                    ("HOLDOUT", validation["holdout"]),
                ]:
                    conn.execute(
                        """
                        INSERT INTO experiment_results (
                            result_id,experiment_id,stage,data_start,data_end,data_hash,
                            metrics_json,diagnostics_json,created_at
                        ) VALUES (?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            _result_id(experiment_id, f"{symbol}:{stage}"),
                            experiment_id,
                            f"{stage}:{symbol}",
                            str(bars[0]["timestamp"]) if bars else None,
                            str(bars[-1]["timestamp"]) if bars else None,
                            hashlib.sha256(
                                json.dumps(bars, separators=(",", ":"), sort_keys=True).encode()
                            ).hexdigest(),
                            json.dumps(payload.get("metrics") or payload, ensure_ascii=False),
                            json.dumps(
                                {
                                    "symbol": symbol,
                                    "provider": history.get("provider"),
                                    "effective_interval": history.get("effective_interval"),
                                    "passed": payload.get("passed"),
                                },
                                ensure_ascii=False,
                            ),
                            utcnow(),
                        ),
                    )
        except Exception as exc:
            failures.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})

    passed_items = [x for x in per_symbol if bool(x["validation"].get("passed"))]
    pass_ratio = len(passed_items) / len(per_symbol) if per_symbol else 0.0
    avg_holdout_return = (
        sum(float(x["validation"]["holdout"]["metrics"]["net_return"]) for x in per_symbol) / len(per_symbol)
        if per_symbol else 0.0
    )
    promoted = bool(per_symbol and pass_ratio >= 0.40 and avg_holdout_return > 0)
    final_status = "COMPLETED" if promoted else "FAILED"
    summary = {
        "symbols_requested": symbols,
        "symbols_completed": len(per_symbol),
        "symbols_failed": len(failures),
        "passed_symbols": len(passed_items),
        "pass_ratio": pass_ratio,
        "avg_holdout_return": avg_holdout_return,
        "promotion": "PAPER_CANDIDATE" if promoted else "REJECTED",
        "performance_semantics": "normalized StrategySpec signal backtest; not TradingView Strategy Tester parity",
        "commission_bps": commission_bps,
        "slippage_bps": slippage_bps,
        "items": per_symbol,
        "failures": failures,
    }
    completed_at = utcnow()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE experiments
            SET status=?, validation_summary_json=?, completed_at=?, updated_at=?
            WHERE experiment_id=?
            """,
            (
                final_status,
                json.dumps(summary, ensure_ascii=False),
                completed_at,
                completed_at,
                experiment_id,
            ),
        )
        decision_id = "DEC-" + hashlib.sha1(
            f"{experiment_id}|{completed_at}|{summary['promotion']}".encode()
        ).hexdigest()[:16].upper()
        conn.execute(
            """
            INSERT INTO promotion_decisions (
                decision_id,experiment_id,from_stage,to_stage,decision,reasons_json,created_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                decision_id,
                experiment_id,
                "RESEARCH",
                "PAPER_CANDIDATE" if promoted else "REJECTED",
                "PROMOTE" if promoted else "REJECT",
                json.dumps(
                    {
                        "pass_ratio": pass_ratio,
                        "avg_holdout_return": avg_holdout_return,
                        "symbols_completed": len(per_symbol),
                        "failures": failures,
                    },
                    ensure_ascii=False,
                ),
                completed_at,
            ),
        )
    notification_error = None
    agent_state = None
    try:
        agent_state = _notify_agent_validation_status(
            str(experiment["agent_id"]),
            promoted=promoted,
            experiment_id=experiment_id,
            summary=summary,
        )
    except Exception as exc:
        notification_error = f"{type(exc).__name__}: {exc}"

    result = get_experiment(experiment_id)
    result["results"] = list_experiment_results(experiment_id)
    result["agent_state"] = agent_state
    result["agent_status_notification_error"] = notification_error
    return result


def _latest_experiment_for_agent(agent_id: str) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT experiment_id
            FROM experiments
            WHERE agent_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (agent_id,),
        ).fetchone()
    if row is None:
        return None
    return get_experiment(str(row["experiment_id"]))


def quant_handoff_status(min_score: float = 72.0) -> dict[str, Any]:
    init_db()
    factory = _json_request(
        f"{TRADINGVIEW_SERVICE_URL}/api/v1/agent-factory/batch/status?min_score={float(min_score):.4f}"
    )
    upstream = _json_request(
        f"{TRADINGVIEW_SERVICE_URL}/api/v1/quant-handoff/agents?limit=1000&min_score={float(min_score):.4f}"
    )
    with _connect() as conn:
        status_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM experiments
            GROUP BY status
            ORDER BY status
            """
        ).fetchall()
        distinct_agents = int(conn.execute(
            "SELECT COUNT(DISTINCT agent_id) FROM experiments"
        ).fetchone()[0])
    return {
        "min_score": float(min_score),
        "factory": factory,
        "research_agents_available": int(upstream.get("count") or 0),
        "experiments_distinct_agents": distinct_agents,
        "experiment_status_counts": {
            str(row["status"]): int(row["count"]) for row in status_rows
        },
        "at": utcnow(),
    }


def run_quant_handoff(
    *,
    limit_candidates: int = 25,
    max_agents_per_candidate: int = 12,
    max_experiments: int = 10,
    min_score: float = 72.0,
    run_ready: bool = True,
    max_symbols: int = 3,
    commission_bps: float = 5.0,
    slippage_bps: float = 2.0,
) -> dict[str, Any]:
    init_db()
    safe_candidates = min(max(int(limit_candidates), 1), 500)
    safe_agents_per_candidate = min(max(int(max_agents_per_candidate), 1), 100)
    safe_experiments = min(max(int(max_experiments), 1), 100)
    safe_symbols = min(max(int(max_symbols), 1), 20)

    factory = _json_request(
        (
            f"{TRADINGVIEW_SERVICE_URL}/api/v1/agent-factory-batch"
            f"?limit_candidates={safe_candidates}"
            f"&min_score={float(min_score):.4f}"
            f"&max_agents_per_candidate={safe_agents_per_candidate}"
        ),
        method="POST",
    )
    queue = _json_request(
        (
            f"{TRADINGVIEW_SERVICE_URL}/api/v1/quant-handoff/agents"
            f"?limit=1000&min_score={float(min_score):.4f}"
        )
    )

    processed = 0
    created = 0
    reused = 0
    executed = 0
    ready = 0
    completed = 0
    failed = 0
    blocked = 0
    skipped_terminal = 0
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for agent in queue.get("items") or []:
        if processed >= safe_experiments:
            break
        agent_id = str(agent.get("agent_id") or "")
        if not agent_id:
            continue
        try:
            experiment = _latest_experiment_for_agent(agent_id)
            if experiment is None:
                experiment = create_experiment(agent_id)
                created += 1
            else:
                reused += 1

            status_before = str(experiment.get("status") or "")
            result = experiment
            action = "REGISTERED" if status_before else "UNKNOWN"

            if status_before == "READY":
                ready += 1
                if run_ready:
                    result = run_experiment(
                        str(experiment["experiment_id"]),
                        max_symbols=safe_symbols,
                        commission_bps=commission_bps,
                        slippage_bps=slippage_bps,
                    )
                    executed += 1
                    action = "EXECUTED"
                else:
                    action = "READY"
            elif status_before in {
                "BLOCKED_UNIVERSE",
                "BLOCKED_DATA_SOURCE",
                "BLOCKED_STRATEGY_ENGINE",
            }:
                blocked += 1
                action = status_before
            elif status_before in {"COMPLETED", "FAILED", "SUPERSEDED"}:
                skipped_terminal += 1
                action = f"EXISTING_{status_before}"
            elif status_before == "RUNNING":
                action = "EXISTING_RUNNING"

            status_after = str(result.get("status") or status_before)
            if status_after == "COMPLETED":
                completed += 1
            elif status_after == "FAILED":
                failed += 1

            items.append({
                "agent_id": agent_id,
                "candidate_id": agent.get("candidate_id"),
                "fit_score": agent.get("fit_score"),
                "fixed_horizon": agent.get("fixed_horizon"),
                "country": agent.get("country"),
                "market": agent.get("market"),
                "universe": agent.get("universe"),
                "experiment_id": result.get("experiment_id"),
                "action": action,
                "status_before": status_before,
                "status_after": status_after,
                "promotion": (result.get("validation_summary") or {}).get("promotion"),
                "blocked_reason": result.get("blocked_reason"),
            })
            processed += 1
        except Exception as exc:
            errors.append({
                "agent_id": agent_id,
                "error": f"{type(exc).__name__}: {exc}",
            })
            processed += 1

    return {
        "factory": factory,
        "upstream_research_agents": int(queue.get("count") or 0),
        "processed": processed,
        "created_experiments": created,
        "reused_experiments": reused,
        "ready_seen": ready,
        "executed": executed,
        "completed": completed,
        "failed": failed,
        "blocked": blocked,
        "skipped_terminal": skipped_terminal,
        "error_count": len(errors),
        "errors": errors[:30],
        "items": items,
        "status": quant_handoff_status(min_score=min_score),
        "at": utcnow(),
    }


def readiness() -> dict[str, Any]:
    toss_ready = credentials_configured()
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
            "strategy_spec_v1": True,
            "policy": "Compile only the supported Pine subset. Unsupported semantics are rejected explicitly; no fabricated performance.",
        },
        "public_history": {
            "yahoo_finance_chart": True,
            "binance_public_klines": True,
            "coverage": "US/KR stock-like symbols and BINANCE crypto; unsupported exchanges remain blocked.",
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
    pine_ready = True
    public_history_ready = True
    macro_data_ready = macro_ready()

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
            "engines": ["TradingAgents", "FinRobot V2", "BLS", "U.S. Treasury"],
            "engine_ready": ready("tradingagents", "finrobot"),
            "state": "DATA_READY" if macro_data_ready else "BLOCKED_DATA_SOURCE",
            "blocker": "BLS·미 재무부 공식 거시 데이터 영구 저장 완료; Agent reasoning 연결 전" if macro_data_ready else "공식 거시 데이터 스냅샷 미수집",
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
            "state": "READY",
            "blocker": "StrategySpec-v1 지원 Pine은 실제 시계열로 바로 실행; 비지원 Pine은 명시적으로 차단",
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
            "state": "READY" if public_history_ready else "BLOCKED_DATA_SOURCE",
            "blocker": None if public_history_ready else "실제 OHLCV 데이터 소스 미연결",
        },
        {
            "order": 10,
            "key": "holdout_validation",
            "name": "Holdout Validation",
            "engines": ["vectorbt", "Qlib"],
            "engine_ready": ready("vectorbt", "qlib"),
            "state": "READY" if public_history_ready else "BLOCKED_DATA_SOURCE",
            "blocker": None if public_history_ready else "실제 OHLCV 데이터 소스 미연결",
        },
        {
            "order": 11,
            "key": "portfolio_engine",
            "name": "Portfolio Engine",
            "engines": ["Riskfolio-Lib", "PyPortfolioOpt", "FinRL-Trading"],
            "engine_ready": ready("riskfolio", "pyportfolioopt", "finrl"),
            "state": "ENGINE_READY" if ready("riskfolio", "pyportfolioopt", "finrl") else "ENGINE_BLOCKED",
            "blocker": "Walk-forward/Holdout 통과 Agent의 TargetPortfolio 자동 생성 연결이 다음 단계" if ready("riskfolio", "pyportfolioopt", "finrl") else "Portfolio 엔진 일부 import 실패",
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
            "state": "READY",
            "blocker": "StrategySpec-v1 검증 통과 Agent만 Paper 후보로 승격",
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
        "strategy_spec_ready": True,
        "public_history_ready": public_history_ready,
        "macro_data_ready": macro_data_ready,
        "stages": stages,
    }
