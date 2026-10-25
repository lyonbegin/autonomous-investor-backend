"""Persistent step-by-step *synthetic* scenario execution for n8n and API testing.

Never imports trading runtimes, never calls brokers or native engine functions.
A run advances only after n8n's corresponding workflow HTTP node calls its
authenticated step endpoint; the internal-test mode calls the same function.
"""
from __future__ import annotations

import hmac
import json
import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.alpha_nodes.scenario_catalog import FLOW_NAMES, SCENARIOS

_EXECUTOR = ThreadPoolExecutor(max_workers=5, thread_name_prefix="scenario-test")
_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _path() -> Path:
    return Path(os.getenv("INVESTMENT_SCENARIO_DB_PATH",
               "/tmp/autonomous_investment_scenarios.sqlite3")).resolve()


def _db() -> sqlite3.Connection:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scenario_runs (
          run_id TEXT PRIMARY KEY,
          scenario_id INTEGER NOT NULL,
          engine TEXT NOT NULL,
          status TEXT NOT NULL,
          next_index INTEGER NOT NULL,
          state_json TEXT NOT NULL,
          verification_json TEXT,
          error TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scenario_events (
          run_id TEXT NOT NULL,
          seq INTEGER NOT NULL,
          step_id TEXT NOT NULL,
          flow TEXT NOT NULL,
          action TEXT NOT NULL,
          label TEXT NOT NULL,
          origin TEXT NOT NULL,
          input_json TEXT NOT NULL,
          output_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(run_id,seq)
        );
        CREATE INDEX IF NOT EXISTS idx_scenario_runs_created
          ON scenario_runs(created_at DESC);
    """)
    return conn


def _dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def _initial() -> dict:
    return {
        "cash": 10_000_000, "reserved": 0, "live_orders_sent": 0,
        "strategies": {
            "S100/v2": {"state": "AVAILABLE", "validation": "PASS"},
            "S101/v1": {"state": "AVAILABLE", "validation": "PASS"},
        },
        "agents": {
            "A": {"strategy": "S100/v2", "status": "ACTIVE", "epoch": 1, "positions": 0},
            "B": {"strategy": "S101/v1", "status": "ACTIVE", "epoch": 1, "positions": 0},
            "C": {"strategy": None, "status": "IDLE", "epoch": 0, "positions": 0},
        },
        "assignments": {"S100/v2": "A", "S101/v1": "B"},
        "epochs": {"S100/v2": 1, "S101/v1": 1},
        "orders": {}, "jobs": {}, "audits": [], "decisions": [],
        "approved_versions": ["S100/v2", "S101/v1"],
        "last_signal": None, "blocked": [],
        "proof": [],
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _apply(state: dict, action: str, params: dict) -> dict:
    """State machine with explicit invariant checks for all ten use cases."""
    agents = state["agents"]
    strategies = state["strategies"]
    orders = state["orders"]
    jobs = state["jobs"]
    assignments = state["assignments"]
    strategy = params.get("strategy")
    agent_id = params.get("agent")
    ag = agents.get(agent_id) if agent_id else None

    if action == "discover":
        _require(strategy not in strategies, "duplicate version discovery")
        strategies[strategy] = {"state": "DISCOVERED", "validation": "PENDING"}
        return {"strategy": strategy, "state": "DISCOVERED", "source": "synthetic Pine"}
    if action == "screen":
        _require(strategy in strategies and strategies[strategy]["state"] == "DISCOVERED",
                 "candidate must be newly discovered")
        supported = bool(params["supported"])
        strategies[strategy]["state"] = "EVALUATING" if supported else "REJECTED"
        strategies[strategy]["validation"] = "PENDING" if supported else "UNSUPPORTED_PINE"
        return {"strategy": strategy, "compatible": supported,
                "next": "validation_queue" if supported else "blocked"}
    if action == "job_queue":
        job_id = params["job"]
        _require(job_id not in jobs and strategy in strategies, "job duplicate or unknown strategy")
        jobs[job_id] = {"strategy": strategy, "kind": params.get("kind", "backtest"),
                        "status": "QUEUED", "result": None}
        return {"job_id": job_id, "status": "QUEUED"}
    if action == "job_start":
        job = jobs[params["job"]]
        _require(job["status"] == "QUEUED", "job not queued")
        job["status"] = "RUNNING"
        return {"job_id": params["job"], "status": "RUNNING"}
    if action == "job_done":
        job = jobs[params["job"]]
        _require(job["status"] == "RUNNING", "job was not running")
        job["status"] = "FINISHED"
        job["result"] = params["result"]
        if params.get("eligible"):
            candidate = strategies[job["strategy"]]
            candidate["state"] = "AVAILABLE" if job["result"] == "PASS" else "REJECTED"
            candidate["validation"] = job["result"]
        return {"job_id": params["job"], "status": "FINISHED",
                "result": job["result"], "strategy": job["strategy"]}
    if action == "claim":
        _require(ag is not None and ag["status"] == "IDLE", "agent not idle")
        _require(strategy in strategies and strategies[strategy]["state"] == "AVAILABLE",
                 "strategy not eligible")
        _require(strategy not in assignments, "strategy version already assigned")
        state["epochs"][strategy] = state["epochs"].get(strategy, 0) + 1
        ag.update({"strategy": strategy, "status": "ACTIVE", "epoch": state["epochs"][strategy]})
        assignments[strategy] = agent_id
        return {"agent": agent_id, "strategy": strategy, "epoch": ag["epoch"]}
    if action == "claim_reject":
        _require(strategy not in assignments and strategies[strategy]["state"] == "REJECTED",
                 "rejection expectation not met")
        return {"agent": agent_id, "strategy": strategy, "claim": "DENIED"}
    if action in ("runtime_start", "pinned"):
        _require(ag is not None and ag["status"] == "ACTIVE" and ag["strategy"],
                 "agent not active")
        if strategy is not None:
            _require(ag["strategy"] == strategy, "unexpected strategy version switch")
        return {"agent": agent_id, "strategy": ag["strategy"], "epoch": ag["epoch"]}
    if action == "release":
        _require(strategy in strategies and strategies[strategy]["state"] == "AVAILABLE",
                 "release requires validated strategy")
        _require(strategy not in state["approved_versions"], "duplicate approval")
        state["approved_versions"].append(strategy)
        return {"approved": strategy, "applies_to_existing_agent": False}
    if action == "migrate":
        _require(ag is not None and ag["strategy"], "no active assignment")
        _require(strategy in state["approved_versions"] and
                 strategies[strategy]["state"] == "AVAILABLE",
                 "candidate not approved and available")
        _require(not any(o["agent"] == agent_id and o["status"] in
                         ("ACKED", "PARTIAL", "UNKNOWN") for o in orders.values()),
                 "unresolved orders prohibit migration")
        old = ag["strategy"]
        del assignments[old]
        _require(strategy not in assignments, "target strategy already active")
        state["epochs"][strategy] = state["epochs"].get(strategy, 0) + 1
        ag.update({"strategy": strategy, "epoch": state["epochs"][strategy]})
        assignments[strategy] = agent_id
        return {"agent": agent_id, "from": old, "to": strategy, "epoch": ag["epoch"]}
    if action == "signal":
        _require(ag is not None and ag["status"] == "ACTIVE", "inactive agent generated signal")
        _require(ag["strategy"] not in state["blocked"], "blocked strategy cannot signal")
        state["last_signal"] = {"agent": agent_id, "qty": params["qty"],
                                "price": params["price"], "strategy": ag["strategy"]}
        return dict(state["last_signal"])
    if action == "reserve":
        _require(ag is not None and ag["status"] == "ACTIVE", "inactive worker attempted order")
        _require(ag["strategy"] not in state["blocked"], "blocked strategy order")
        order_id = params["order"]
        _require(order_id not in orders, "duplicate order ID")
        _require(not any(o["agent"] == agent_id and o["status"] in
                         ("ACKED", "PARTIAL", "UNKNOWN") for o in orders.values()),
                 "unresolved previous order")
        notional = int(params["qty"]) * int(params["price"])
        _require(notional <= state["cash"] - state["reserved"], "insufficient free cash")
        orders[order_id] = {"agent": agent_id, "strategy": ag["strategy"],
                            "qty": params["qty"], "filled": 0,
                            "price": params["price"], "status": "ACKED",
                            "reserved": notional, "side": "BUY"}
        state["reserved"] += notional
        return {"order_id": order_id, "status": "ACKED", "reserved": notional,
                "available": state["cash"] - state["reserved"], "broker": "synthetic"}
    if action == "reject_capital":
        _require(ag is not None and ag["status"] == "ACTIVE", "agent inactive")
        needed = int(params["qty"]) * int(params["price"])
        available = state["cash"] - state["reserved"]
        _require(needed > available, "expected insufficient capital")
        return {"agent": agent_id, "risk_decision": "REJECT", "needed": needed,
                "available": available, "new_orders": 0}
    if action == "fill":
        order = orders[params["order"]]
        qty = int(params["qty"])
        _require(order["side"] == "BUY" and order["status"] in ("ACKED", "PARTIAL"),
                 "order not fillable")
        _require(0 < qty <= order["qty"] - order["filled"], "fill quantity exceeds open order")
        amount = qty * order["price"]
        order["filled"] += qty
        order["reserved"] -= amount
        state["cash"] -= amount
        state["reserved"] -= amount
        agents[order["agent"]]["positions"] += qty
        order["status"] = "FILLED" if order["filled"] == order["qty"] else "PARTIAL"
        return {"order_id": params["order"], "filled": order["filled"],
                "remaining": order["qty"] - order["filled"], "status": order["status"],
                "cash": state["cash"]}
    if action == "verify_capital":
        return {"cash": state["cash"], "reserved": state["reserved"],
                "available": state["cash"] - state["reserved"]}
    if action == "prevent_duplicate":
        pending = [o for o in orders.values() if o["agent"] == agent_id and
                   o["status"] in ("ACKED", "PARTIAL", "UNKNOWN")]
        _require(bool(pending), "duplicate prevention requires outstanding order")
        return {"agent": agent_id, "duplicate_prevented": True,
                "pending_qty": sum(o["qty"] - o["filled"] for o in pending),
                "new_orders": 0}
    if action == "timeout":
        order = orders[params["order"]]
        _require(order["status"] == "ACKED", "no such acknowledged order")
        order["status"] = "UNKNOWN"
        return {"order_id": params["order"], "status": "UNKNOWN", "resubmit": False}
    if action == "ack":
        order = orders[params["order"]]
        _require(order["status"] == "UNKNOWN", "no unknown order to reconcile")
        order["status"] = "ACKED"
        return {"order_id": params["order"], "status": "ACKED", "new_orders": 0}
    if action == "audit":
        finding = {"kind": params["kind"], "severity": params.get("severity", "INFO")}
        state["audits"].append(finding)
        return {"audit": finding, "source": "synthetic event ledger"}
    if action == "governance":
        decision = params["decision"]
        state["decisions"].append({"strategy": strategy, "decision": decision})
        if decision == "SUSPEND":
            strategies[strategy]["state"] = "SUSPENDED"
        if decision == "RETIRE":
            strategies[strategy]["state"] = "RETIRED"
        return {"strategy": strategy, "decision": decision}
    if action == "block":
        _require(strategy in strategies, "unknown strategy to block")
        if strategy not in state["blocked"]:
            state["blocked"].append(strategy)
        return {"strategy": strategy, "new_orders_enabled": False}
    if action == "revision_request":
        return {"candidate": strategy, "source_changed": False, "approval_required": True}
    if action == "prevent_blocked":
        _require(ag is not None and (ag["status"] != "ACTIVE" or
                 ag["strategy"] in state["blocked"] or
                 strategies[ag["strategy"]]["state"] in ("SUSPENDED", "RETIRED")),
                 "old worker expected to be blocked")
        return {"agent": agent_id, "new_orders": 0, "blocked": True}
    if action == "reconcile":
        return {"agent": agent_id, "orders_checked": len(orders),
                "positions": ag["positions"], "broker": "synthetic", "matched": True}
    if action == "heartbeat_lost":
        _require(ag is not None and ag["status"] == "ACTIVE", "expected active agent")
        ag["status"] = "CRASHED"
        return {"agent": agent_id, "status": "CRASHED"}
    if action == "fence":
        _require(ag is not None and ag["status"] == "CRASHED", "worker must crash first")
        ag["status"] = "FENCED"
        return {"agent": agent_id, "status": "FENCED", "epoch": ag["epoch"]}
    if action == "release_agent":
        _require(ag is not None and ag["strategy"], "no assignment to release")
        _require(ag["status"] in ("FENCED", "DRAINING"), "worker cannot be safely released")
        _require(ag["positions"] == 0, "live positions require resolution")
        _require(not any(o["agent"] == agent_id and o["status"] in
                         ("ACKED", "PARTIAL", "UNKNOWN") for o in orders.values()),
                 "open order requires reconciliation")
        strategy_key = ag["strategy"]
        del assignments[strategy_key]
        ag.update({"strategy": None, "status": "IDLE" if ag["status"] == "DRAINING" else "FENCED"})
        return {"agent": agent_id, "released": strategy_key, "status": ag["status"]}
    if action == "seed_position":
        _require(ag is not None and ag["positions"] == 0, "position already exists")
        ag["positions"] = int(params["qty"])
        return {"agent": agent_id, "positions": ag["positions"], "source": "synthetic initial condition"}
    if action == "drain":
        _require(ag is not None and strategies[ag["strategy"]]["state"] == "RETIRED",
                 "retirement required before draining")
        ag["status"] = "DRAINING"
        return {"agent": agent_id, "status": "DRAINING", "positions": ag["positions"]}
    if action == "liquidate":
        _require(ag is not None and ag["status"] == "DRAINING", "worker not draining")
        qty = int(params["qty"])
        _require(qty > 0 and qty == ag["positions"], "synthetic liquidation mismatch")
        _require(ag["strategy"] in state["blocked"], "exit policy not applied")
        proceeds = qty * int(params["price"])
        ag["positions"] -= qty
        state["cash"] += proceeds
        orders["CLOSE1"] = {"agent": agent_id, "strategy": ag["strategy"],
                            "qty": qty, "filled": qty, "price": params["price"],
                            "status": "FILLED", "reserved": 0, "side": "SELL"}
        return {"order_id": "CLOSE1", "side": "SELL", "filled": qty,
                "cash": state["cash"], "paper_only": True}
    raise ValueError(f"unknown synthetic action {action}")


def _invariants(state: dict) -> list[dict]:
    checks = [
        ("cash_nonnegative", state["cash"] >= 0),
        ("reservations_reconciled", state["reserved"] ==
         sum(o["reserved"] for o in state["orders"].values())),
        ("capital_limit", 0 <= state["reserved"] <= state["cash"]),
        ("unique_agent_assignment", len(set(state["assignments"].values())) ==
         len(state["assignments"])),
        ("assignment_links", all(state["agents"][aid]["strategy"] == strategy
         for strategy, aid in state["assignments"].items())),
        ("no_live_orders", state["live_orders_sent"] == 0),
    ]
    return [{"name": name, "passed": bool(ok)} for name, ok in checks]


def _scenario_assertions(scenario_id: int, state: dict) -> list[dict]:
    a = state["agents"]
    st = state["strategies"]
    orders = state["orders"]
    jobs = state["jobs"]
    checks: dict[int, list[tuple[str, bool]]] = {
        1: [("verified_before_claim", st.get("S103/v1", {}).get("validation") == "PASS"),
            ("idle_agent_assigned", a["C"]["strategy"] == "S103/v1")],
        2: [("no_unapproved_swap", "S100/v3" in state["approved_versions"]),
            ("v3_migrated", a["A"]["strategy"] == "S100/v3")],
        3: [("only_one_order", len(orders) == 1),
            ("capital_reserved", state["reserved"] == 8_000_000)],
        4: [("one_order_only", len(orders) == 1),
            ("partial_fill", orders.get("O1", {}).get("filled") == 60),
            ("open_reservation", state["reserved"] == 400_000)],
        5: [("three_jobs_finished", len(jobs) == 3 and
             all(j["status"] == "FINISHED" for j in jobs.values())),
            ("transaction_continued", a["A"]["positions"] == 10),
            ("audit_continued", len(state["audits"]) == 1)],
        6: [("old_suspended", st["S101/v1"]["state"] == "SUSPENDED"),
            ("replacement_only_candidate", st["S101/v2"]["state"] == "AVAILABLE" and
             "S101/v2" not in state["approved_versions"]),
            ("old_agent_not_replaced", a["B"]["strategy"] == "S101/v1")],
        7: [("no_duplicate_order", len(orders) == 1),
            ("unknown_reconciled", orders.get("O1", {}).get("status") == "ACKED")],
        8: [("old_worker_fenced", a["A"]["status"] == "FENCED"),
            ("new_assignment", a["C"]["strategy"] == "S100/v2"),
            ("epoch_advanced", a["C"]["epoch"] > a["A"]["epoch"])],
        9: [("unsupported_version_rejected", st["S100/v3"]["state"] == "REJECTED"),
            ("old_version_unchanged", a["A"]["strategy"] == "S100/v2"),
            ("old_version_order_allowed", len(orders) == 1)],
        10: [("strategy_retired", st["S101/v1"]["state"] == "RETIRED"),
             ("position_closed", a["B"]["positions"] == 0),
             ("agent_idle", a["B"]["status"] == "IDLE"),
             ("synthetic_cash_reconciled", state["cash"] == 10_200_000)],
    }
    return _invariants(state) + [
        {"name": name, "passed": bool(passed)}
        for name, passed in checks[scenario_id]
    ]


def _snapshot(run_id: str, db: sqlite3.Connection) -> dict:
    run = db.execute("SELECT * FROM scenario_runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise HTTPException(status_code=404, detail="scenario run not found")
    spec = SCENARIOS[run["scenario_id"]]
    nodes = [{**node, "index": i,
              "state": "success" if i < run["next_index"] else
                       ("running" if i == run["next_index"] and run["status"] == "running"
                        else "waiting")}
             for i, node in enumerate(spec["steps"])]
    events = db.execute("SELECT * FROM scenario_events WHERE run_id=? ORDER BY seq",
                        (run_id,)).fetchall()
    state = json.loads(run["state_json"])
    return {
        "run_id": run_id, "scenario_id": run["scenario_id"],
        "title": spec["title"], "why": spec["why"],
        "engine": run["engine"], "status": run["status"],
        "progress": run["next_index"], "total": len(nodes),
        "progress_pct": round(run["next_index"] * 100 / len(nodes), 1),
        "nodes": nodes,
        "events": [{
            "seq": e["seq"], "step_id": e["step_id"], "flow": e["flow"],
            "flow_label": FLOW_NAMES[e["flow"]], "label": e["label"],
            "action": e["action"], "origin": e["origin"],
            "input": json.loads(e["input_json"]),
            "output": json.loads(e["output_json"]),
            "at": e["created_at"],
        } for e in events],
        "state": state, "verification": json.loads(run["verification_json"] or "[]"),
        "error": run["error"], "created_at": run["created_at"], "updated_at": run["updated_at"],
        "disclaimer": "Synthetic state-transition test. No native market/broker/12-engine computation executed.",
    }


def get_run(run_id: str) -> dict:
    with _db() as db:
        return _snapshot(run_id, db)


def recent_runs(limit: int = 30) -> dict:
    with _db() as db:
        rows = db.execute("""SELECT run_id,scenario_id,engine,status,next_index,
             created_at,updated_at FROM scenario_runs ORDER BY created_at DESC LIMIT ?""",
                          (limit,)).fetchall()
    return {"count": len(rows), "runs": [dict(r) for r in rows]}


def _failure(run_id: str, reason: str) -> None:
    with _LOCK, _db() as db:
        row = db.execute("SELECT status FROM scenario_runs WHERE run_id=?", (run_id,)).fetchone()
        if row and row["status"] not in ("passed", "cancelled"):
            db.execute("UPDATE scenario_runs SET status='failed',error=?,updated_at=? WHERE run_id=?",
                       (str(reason)[:300], _now(), run_id))
            db.commit()


def advance(run_id: str, step_id: str, *, origin: str) -> dict:
    with _LOCK, _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM scenario_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="run not found")
        if (row["engine"] == "n8n" and origin != "n8n") or (
            row["engine"] == "internal-test" and origin != "internal-test"
        ):
            raise HTTPException(status_code=403, detail="execution engine mismatch")
        steps = SCENARIOS[row["scenario_id"]]["steps"]
        completed_ids = [s["id"] for s in steps[:row["next_index"]]]
        if step_id in completed_ids:
            return {"idempotent": True, "step_id": step_id,
                    "run_id": run_id, "status": row["status"]}
        if row["status"] in ("cancelled", "failed", "passed"):
            raise HTTPException(status_code=409, detail="run already terminal")
        if row["next_index"] >= len(steps) or steps[row["next_index"]]["id"] != step_id:
            raise HTTPException(status_code=409, detail="step order violation")
        st = steps[row["next_index"]]
        state = json.loads(row["state_json"])
        try:
            output = _apply(state, st["action"], st["params"])
            checks = _invariants(state)
            if not all(x["passed"] for x in checks):
                raise ValueError("invariant violation: " + _dumps(checks))
        except (ValueError, KeyError, AssertionError) as exc:
            message = f'{st["id"]}: {type(exc).__name__}: {exc}'
            db.execute("UPDATE scenario_runs SET status='failed',error=?,updated_at=? WHERE run_id=?",
                       (message[:300], _now(), run_id))
            db.commit()
            raise HTTPException(status_code=422, detail=message) from exc
        next_idx = row["next_index"] + 1
        verification = _scenario_assertions(row["scenario_id"], state) if next_idx == len(steps) else []
        passed = all(x["passed"] for x in verification)
        status = "passed" if next_idx == len(steps) and passed else (
            "failed" if next_idx == len(steps) else "running")
        failed_names = [x["name"] for x in verification if not x["passed"]]
        db.execute(
            """UPDATE scenario_runs SET next_index=?,state_json=?,verification_json=?,
            status=?,error=?,updated_at=? WHERE run_id=?""",
            (next_idx, _dumps(state), _dumps(verification), status,
             "; ".join(failed_names) or None, _now(), run_id)
        )
        db.execute("""INSERT INTO scenario_events
        (run_id,seq,step_id,flow,action,label,origin,input_json,output_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (run_id, next_idx, st["id"], st["flow"], st["action"], st["label"],
             origin, _dumps(st["params"]), _dumps(output), _now()))
        db.commit()
        return {"run_id": run_id, "step_id": step_id, "status": status,
                "progress": next_idx, "output": output,
                "verification": verification if status != "running" else None}


def _internal_runner(run_id: str, scenario_id: int) -> None:
    delay_ms = int(os.getenv("INVESTMENT_SCENARIO_STEP_DELAY_MS", "300"))
    delay_ms = max(0, min(delay_ms, 5000))
    try:
        for st in SCENARIOS[scenario_id]["steps"]:
            if get_run(run_id)["status"] in ("cancelled", "failed"):
                return
            if delay_ms:
                time.sleep(delay_ms / 1000)
            advance(run_id, st["id"], origin="internal-test")
    except Exception as exc:
        _failure(run_id, "internal scenario runner: " + str(exc))


def _trigger_n8n(run_id: str, scenario_id: int) -> None:
    base = os.getenv("INVESTMENT_N8N_WEBHOOK_BASE", "").rstrip("/")
    if not base or not base.startswith(("http://", "https://")):
        _failure(run_id, "n8n webhook base not configured")
        return
    # scenario_id from immutable catalog; no user-provided URL is accepted.
    url = f"{base}/ai-investment-scenario-{scenario_id:02d}"
    payload = _dumps({"run_id": run_id, "scenario_id": scenario_id}).encode()
    try:
        req = Request(url, data=payload, headers={"Content-Type": "application/json"},
                      method="POST")
        with urlopen(req, timeout=8) as response:
            if response.status not in (200, 201, 202):
                _failure(run_id, f"n8n webhook HTTP {response.status}")
    except (URLError, HTTPError, TimeoutError, ValueError) as exc:
        _failure(run_id, "n8n webhook unavailable: " + str(exc)[:220])


def start_run(scenario_id: int, engine: str) -> dict:
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail="scenario not found")
    if engine not in ("n8n", "internal-test"):
        raise HTTPException(status_code=422, detail="engine must be n8n or internal-test")
    if engine == "n8n" and not os.getenv("INVESTMENT_N8N_WEBHOOK_BASE", ""):
        raise HTTPException(status_code=503, detail="n8n webhook unavailable; use explicit internal-test mode")
    run_id = uuid.uuid4().hex
    now = _now()
    with _db() as db:
        db.execute("""INSERT INTO scenario_runs(
            run_id,scenario_id,engine,status,next_index,state_json,created_at,updated_at)
            VALUES(?,?,?,'running',0,?,?,?)""",
            (run_id, scenario_id, engine, _dumps(_initial()), now, now))
        db.commit()
    if engine == "n8n":
        _EXECUTOR.submit(_trigger_n8n, run_id, scenario_id)
    else:
        _EXECUTOR.submit(_internal_runner, run_id, scenario_id)
    return {"run_id": run_id, "scenario_id": scenario_id, "engine": engine,
            "status": "running", "poll_url": f"/api/v1/alpha/scenarios/runs/{run_id}",
            "step_count": len(SCENARIOS[scenario_id]["steps"])}


def verify(run_id: str) -> dict:
    run = get_run(run_id)
    if run["status"] not in ("passed", "failed"):
        raise HTTPException(status_code=409, detail="scenario run not finished")
    return {"run_id": run_id, "passed": run["status"] == "passed",
            "checks": run["verification"], "status": run["status"],
            "events": len(run["events"]), "engine": run["engine"]}


def cancel_run(run_id: str) -> dict:
    with _LOCK, _db() as db:
        row = db.execute("SELECT status FROM scenario_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="run not found")
        if row["status"] not in ("running",):
            raise HTTPException(status_code=409, detail="run not active")
        db.execute("UPDATE scenario_runs SET status='cancelled',updated_at=? WHERE run_id=?",
                   (_now(), run_id))
        db.commit()
    return {"run_id": run_id, "status": "cancelled"}


def validate_callback_key(supplied: str | None) -> None:
    expected = os.getenv("INVESTMENT_SCENARIO_CALLBACK_KEY", "")
    if not expected or len(expected) < 24:
        raise HTTPException(status_code=503, detail="callback secret missing or too short")
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="invalid internal scenario callback key")
