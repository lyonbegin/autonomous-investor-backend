"""Investment-specific, versioned and executable node workflow.

Existing 137 callable module API endpoints remain the source of native execution.
This module adds real DAG semantics (parallelism, conditions, joins, typed input
mappings, optional failures and approval barriers), never a replacement engine.

Scope: one pinned process with SQLite audit; no broker/live order execution.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator

from app.alpha_nodes.inventory import ENGINES, OPERATION_MAP, OPERATIONS
from app.alpha_nodes.runtime import ExecuteRequest, _invoke, _validate_gate
from app.alpha_nodes.graph import _resolve, _scrub

FlowStatus = Literal["waiting", "running", "success", "failed", "skipped", "waiting_approval"]
JoinKind = Literal["ALL", "ANY", "QUORUM", "ALL_SETTLED"]
EdgeStatus = Literal["success", "failed", "any"]
_FN_LOCK = threading.RLock()
_INIT_DB: set[str] = set()
_BACKGROUND = ThreadPoolExecutor(max_workers=2, thread_name_prefix="invest-flow")
_ACTIVE: set[str] = set()

CONTROL = {
    "control.join": {"inputs": "Mapped parent node results", "output": "joined"},
    "control.approval": {"inputs": "Explicit human approval", "output": "approved"},
    "control.identity": {"inputs": "Explicit mapped data or node config", "output": "value"},
}
# Native live execution is NEVER available in this workflow, regardless of flags.
NATIVE_SAFE = {
    "orchestration.orchestration.runtime.plan_rebalance",
    "nautilus.app.bridge.risk_config",
    "nautilus.app.bridge.execution_config",
    "nautilus.app.bridge.backtest_engine_config",
    "vectorbt.app.bridge.from_signals",
    "vectorbt.app.bridge.from_orders",
    "vectorbt.lab.bridge.stats",
    "vectorbt.lab.bridge.from_signals",
    "vectorbt.lab.bridge.from_orders",
    "riskfolio.app.bridge.portfolio",
    "riskfolio.app.bridge.estimate",
    "riskfolio.app.bridge.optimize",
    "pypfopt.app.bridge.efficient_frontier",
    "qlib.app.bridge.risk_analysis",
    "finrl.app.bridge.equal_weight",
}
# Source REST methods are GET-only except two guarded QuantLab mutations.
READ_SERVICE = {op["id"] for op in OPERATIONS if op["source"] == "service"
                and op["function"] not in ("quant_experiment_create", "quant_experiment_run")}


class FlowNode(BaseModel):
    id: str = Field(min_length=1, max_length=70, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    operation_id: str = Field(min_length=3, max_length=180)
    arguments: dict[str, Any] = Field(default_factory=dict)
    join: JoinKind = "ALL"
    quorum: int = Field(default=1, ge=1, le=40)
    optional: bool = False
    max_retries: int = Field(default=0, ge=0, le=2)
    x: float = Field(default=0, ge=-100000, le=100000)
    y: float = Field(default=0, ge=-100000, le=100000)


class EdgeCondition(BaseModel):
    path: str = "result"
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "exists"] = "eq"
    value: Any = None


class FlowEdge(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    source: str
    target: str
    target_input: str | None = None
    output_path: str = "result"
    on_status: EdgeStatus = "success"
    optional: bool = False
    when: EdgeCondition | None = None
    transform: Literal["identity", "int", "float", "str", "length"] = "identity"


class FlowDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    description: str = Field(default="", max_length=1000)
    nodes: list[FlowNode] = Field(min_length=1, max_length=40)
    edges: list[FlowEdge] = Field(default_factory=list, max_length=120)


class ExecuteFlow(BaseModel):
    version: int | None = Field(default=None, ge=1)
    mode: Literal["dry_run", "research"] = "dry_run"
    background: bool = False
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=120)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _db() -> sqlite3.Connection:
    path = str(Path(os.getenv("INVESTMENT_FLOW_DB_PATH", "/tmp/autonomous_investment_flows.sqlite3")).resolve())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with _FN_LOCK:
        conn = sqlite3.connect(path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS investment_workflows(
              id TEXT PRIMARY KEY, name TEXT NOT NULL, latest_version INTEGER NOT NULL,
              published_version INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS investment_versions(
              workflow_id TEXT NOT NULL, version INTEGER NOT NULL,
              definition_json TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL, PRIMARY KEY(workflow_id,version));
            CREATE TABLE IF NOT EXISTS investment_runs(
              id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, version INTEGER NOT NULL,
              mode TEXT NOT NULL, snapshot_json TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL,
              state TEXT NOT NULL, idempotency_key TEXT, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL, error_json TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_investment_idem ON
              investment_runs(workflow_id,version,idempotency_key)
              WHERE idempotency_key IS NOT NULL;
            CREATE TABLE IF NOT EXISTS investment_node_runs(
              run_id TEXT NOT NULL, node_id TEXT NOT NULL, operation_id TEXT NOT NULL,
              state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
              input_json TEXT, output_json TEXT, error_json TEXT, updated_at TEXT,
              PRIMARY KEY(run_id,node_id));
            CREATE TABLE IF NOT EXISTS investment_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
              node_id TEXT, kind TEXT NOT NULL, payload TEXT, created_at TEXT NOT NULL);
        """)
        if path not in _INIT_DB:
            conn.execute("UPDATE investment_runs SET state='interrupted',updated_at=? WHERE state='running'", (_now(),))
            conn.execute("UPDATE investment_node_runs SET state='failed',error_json=? WHERE state='running'",
                         (json.dumps({"reason": "worker restarted; replay explicitly"}),))
            _INIT_DB.add(path)
        conn.commit()
    return conn


def _json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _hash(definition: FlowDefinition) -> str:
    return hashlib.sha256(_json(definition.model_dump(mode="json")).encode()).hexdigest()


def _port_names(operation: dict) -> tuple[set[str], bool]:
    args = operation["inputs"]
    return {v["name"] for v in args}, any(v["kind"] == "kwargs" for v in args)


def _operation_status(op_id: str) -> tuple[str, str | None]:
    if op_id in CONTROL:
        return "ready", None
    op = OPERATION_MAP.get(op_id)
    if op is None:
        return "invalid", "unknown operation"
    if op_id not in NATIVE_SAFE and op_id not in READ_SERVICE:
        return "restricted", "native effect/cost not reviewed; metadata-only until explicitly allowlisted"
    try:
        _validate_gate(op)
    except HTTPException as exc:
        return "blocked", str(exc.detail)
    return "ready", None


def palette() -> dict:
    nodes = []
    for op in OPERATIONS:
        state, reason = _operation_status(op["id"])
        nodes.append({
            "operation_id": op["id"], "engine": op["engine"],
            "label": f'{op["engine"]} · {op["function"]}',
            "source": op["source_path"], "inputs": op["inputs"],
            "output": op["output"], "execution": state, "reason": reason,
            "endpoint": op["endpoint"],
        })
    for op_id in CONTROL:
        nodes.append({"operation_id": op_id, "engine": "control",
                      "label": op_id.split(".")[-1], "inputs": [],
                      "output": CONTROL[op_id]["output"], "execution": "ready",
                      "source": "app/alpha_nodes/investment_flow.py"})
    return {"engine_count": len(ENGINES), "native_functions": len(OPERATIONS),
            "node_types": len(nodes), "nodes": nodes,
            "live_orders": "disabled"}


def validate(definition: FlowDefinition) -> dict:
    indexed = {node.id: node for node in definition.nodes}
    if len(indexed) != len(definition.nodes):
        raise ValueError("duplicate node instance id")
    edges = {edge.id: edge for edge in definition.edges}
    if len(edges) != len(definition.edges):
        raise ValueError("duplicate edge id")
    parent: dict[str, set[str]] = {key: set() for key in indexed}
    children: dict[str, set[str]] = {key: set() for key in indexed}
    mapped: dict[str, set[str]] = {key: set() for key in indexed}
    for node in definition.nodes:
        if node.operation_id not in OPERATION_MAP and node.operation_id not in CONTROL:
            raise ValueError(f"{node.id}: unknown existing engine operation {node.operation_id}")
    for edge in definition.edges:
        if edge.source not in indexed or edge.target not in indexed:
            raise ValueError(f"{edge.id}: dangling edge")
        if edge.source == edge.target:
            raise ValueError(f"{edge.id}: self edge")
        parent[edge.target].add(edge.source)
        children[edge.source].add(edge.target)
        if edge.target_input:
            target = indexed[edge.target]
            if target.operation_id not in CONTROL:
                permitted, allows_kwargs = _port_names(OPERATION_MAP[target.operation_id])
                if edge.target_input not in permitted and not allows_kwargs:
                    raise ValueError(f"{edge.id}: unknown native input port {edge.target_input}")
            if edge.target_input in mapped[edge.target] or edge.target_input in target.arguments:
                raise ValueError(f"{edge.id}: input port collision {edge.target_input}")
            mapped[edge.target].add(edge.target_input)
    ready = [node.id for node in definition.nodes if not parent[node.id]]
    order = []
    indeg = {key: len(v) for key, v in parent.items()}
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for child in sorted(children[node_id]):
            indeg[child] -= 1
            if indeg[child] == 0:
                ready.append(child)
    if len(order) != len(definition.nodes):
        raise ValueError("cyclic workflow is not allowed")
    warnings = []
    for node in definition.nodes:
        state, reason = _operation_status(node.operation_id)
        if state != "ready":
            warnings.append({"node": node.id, "state": state, "reason": reason})
        n_in = len([e for e in definition.edges if e.target == node.id and not e.optional])
        if node.join == "QUORUM" and node.quorum > n_in:
            raise ValueError(f"{node.id}: quorum exceeds incoming required edges")
    return {"valid": True, "order": order, "edges": [e.model_dump() for e in definition.edges],
            "parallel_roots": [n.id for n in definition.nodes if not parent[n.id]],
            "warnings": warnings, "node_count": len(indexed),
            "naitulus_execution": "disabled", "live_trading": False}


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found")


def create_workflow(defn: FlowDefinition) -> dict:
    validate(defn)
    ident = uuid.uuid4().hex
    now = _now()
    with _db() as db:
        db.execute("INSERT INTO investment_workflows VALUES(?,?,1,NULL,?,?)",
                   (ident, defn.name, now, now))
        db.execute("INSERT INTO investment_versions VALUES(?,?,?,0,?)",
                   (ident, 1, _json(defn.model_dump(mode="json")), now))
    return {"workflow_id": ident, "version": 1, "published": False, "name": defn.name}


def list_workflows() -> dict:
    with _db() as db:
        rows = db.execute("SELECT * FROM investment_workflows ORDER BY updated_at DESC").fetchall()
    return {"count": len(rows), "items": [dict(x) for x in rows]}


def get_workflow(workflow_id: str, version: int | None = None) -> dict:
    with _db() as db:
        header = db.execute("SELECT * FROM investment_workflows WHERE id=?", (workflow_id,)).fetchone()
        if header is None:
            raise _not_found("workflow")
        selected = version or header["latest_version"]
        row = db.execute("SELECT * FROM investment_versions WHERE workflow_id=? AND version=?",
                         (workflow_id, selected)).fetchone()
        if row is None:
            raise _not_found("workflow version")
    return {"workflow_id": workflow_id, "version": selected, "published": bool(row["published"]),
            "latest_version": header["latest_version"], "published_version": header["published_version"],
            "definition": json.loads(row["definition_json"])}


def update_workflow(workflow_id: str, definition: FlowDefinition, expected_version: int) -> dict:
    validate(definition)
    now = _now()
    with _FN_LOCK, _db() as db:
        row = db.execute("SELECT latest_version FROM investment_workflows WHERE id=?", (workflow_id,)).fetchone()
        if not row:
            raise _not_found("workflow")
        if row["latest_version"] != expected_version:
            raise HTTPException(status_code=409, detail="workflow changed; reload current version")
        version = expected_version + 1
        db.execute("INSERT INTO investment_versions VALUES(?,?,?,0,?)",
                   (workflow_id, version, _json(definition.model_dump(mode="json")), now))
        db.execute("UPDATE investment_workflows SET latest_version=?,name=?,updated_at=? WHERE id=?",
                   (version, definition.name, now, workflow_id))
    return {"workflow_id": workflow_id, "version": version, "published": False}


def publish(workflow_id: str, version: int) -> dict:
    get_workflow(workflow_id, version)
    with _db() as db:
        db.execute("UPDATE investment_versions SET published=0 WHERE workflow_id=?", (workflow_id,))
        db.execute("UPDATE investment_versions SET published=1 WHERE workflow_id=? AND version=?",
                   (workflow_id, version))
        db.execute("UPDATE investment_workflows SET published_version=?,updated_at=? WHERE id=?",
                   (version, _now(), workflow_id))
    return {"workflow_id": workflow_id, "published_version": version}


def _event(db: sqlite3.Connection, run_id: str, node_id: str | None, kind: str, payload: Any) -> None:
    db.execute("INSERT INTO investment_events(run_id,node_id,kind,payload,created_at) VALUES(?,?,?,?,?)",
               (run_id, node_id, kind, _json(_scrub(payload)), _now()))


def _update_node(run_id: str, node_id: str, state: str, *, attempts: int | None = None,
                 inputs: Any = None, output: Any = None, error: Any = None) -> None:
    with _db() as db:
        db.execute("""UPDATE investment_node_runs
        SET state=?, attempts=COALESCE(?,attempts), input_json=COALESCE(?,input_json),
            output_json=COALESCE(?,output_json), error_json=?,updated_at=?
        WHERE run_id=? AND node_id=?""",
                   (state, attempts, _json(_scrub(inputs)) if inputs is not None else None,
                    _json(_scrub(output)) if output is not None else None,
                    _json(_scrub(error)) if error else None, _now(), run_id, node_id))
        _event(db, run_id, node_id, "node_" + state, {"attempts": attempts, "error": error})


def _update_run(run_id: str, state: str, error: Any = None) -> None:
    with _db() as db:
        db.execute("UPDATE investment_runs SET state=?,error_json=?,updated_at=? WHERE id=?",
                   (state, _json(_scrub(error)) if error else None, _now(), run_id))
        _event(db, run_id, None, "workflow_" + state, error or {})


def get_run(run_id: str) -> dict:
    with _db() as db:
        row = db.execute("SELECT * FROM investment_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise _not_found("run")
        steps = db.execute("SELECT * FROM investment_node_runs WHERE run_id=? ORDER BY rowid",
                           (run_id,)).fetchall()
        events = db.execute("SELECT node_id,kind,payload,created_at FROM investment_events WHERE run_id=? ORDER BY id",
                            (run_id,)).fetchall()
    def decoded(x: Any) -> Any:
        return json.loads(x) if x else None
    return {
        "run_id": run_id, "workflow_id": row["workflow_id"], "version": row["version"],
        "mode": row["mode"], "state": row["state"], "snapshot_sha256": row["snapshot_sha256"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "error": decoded(row["error_json"]),
        "nodes": [{**{k: s[k] for k in ("node_id", "operation_id", "state", "attempts", "updated_at")},
                   "inputs": decoded(s["input_json"]), "output": decoded(s["output_json"]),
                   "error": decoded(s["error_json"])} for s in steps],
        "events": [{**{k: event[k] for k in ("node_id", "kind", "created_at")},
                    "payload": decoded(event["payload"])} for event in events],
    }


def _path_get(document: Any, path: str) -> Any:
    if not path:
        return document
    value = document
    for key in path.split("."):
        if isinstance(value, dict):
            if key not in value:
                raise KeyError(f"output path missing: {path}")
            value = value[key]
        elif isinstance(value, list) and key.isdecimal() and int(key) < len(value):
            value = value[int(key)]
        else:
            raise KeyError(f"output path missing: {path}")
    return value


def _check(condition: EdgeCondition | None, parent: dict) -> bool:
    if condition is None:
        return True
    try:
        observed = _path_get(parent, condition.path)
    except KeyError:
        return condition.op == "exists" and condition.value is False
    if condition.op == "exists":
        return observed is not None
    if condition.op == "eq":
        return observed == condition.value
    if condition.op == "ne":
        return observed != condition.value
    if condition.op == "in":
        return isinstance(condition.value, (list, tuple)) and observed in condition.value
    try:
        left = float(observed)
        right = float(condition.value)
    except (ValueError, TypeError):
        return False
    return {"gt": lambda: left > right, "gte": lambda: left >= right,
            "lt": lambda: left < right, "lte": lambda: left <= right}[condition.op]()


def _transform(value: Any, kind: str) -> Any:
    if kind == "identity": return value
    if kind == "int": return int(value)
    if kind == "float": return float(value)
    if kind == "str": return str(value)
    if kind == "length": return len(value)
    raise ValueError("unsupported data transform")


def _node_inputs(node: FlowNode, incoming: list[FlowEdge], outcomes: dict[str, dict]) -> dict:
    params = dict(node.arguments)
    for edge in incoming:
        source = outcomes.get(edge.source)
        if not source:
            continue
        status_match = edge.on_status == "any" or (
            edge.on_status == "success" and source["state"] == "success"
        ) or (edge.on_status == "failed" and source["state"] == "failed")
        if status_match and _check(edge.when, source):
            if edge.target_input:
                params[edge.target_input] = _transform(_path_get(source, edge.output_path), edge.transform)
    return params


def _decision(node: FlowNode, incoming: list[FlowEdge], outcomes: dict[str, dict],
              active: set[str]) -> str:
    if not incoming:
        return "ready"
    # An edge may have a condition, status guard or a nonmandatory source.
    evaluated = []
    for edge in incoming:
        source = outcomes.get(edge.source)
        if source is None:
            evaluated.append((edge, "pending"))
            continue
        eligible = (edge.on_status == "any" or
                    edge.on_status == "success" and source["state"] == "success" or
                    edge.on_status == "failed" and source["state"] == "failed")
        evaluated.append((edge, "satisfied" if eligible and _check(edge.when, source) else "inactive"))
    required = [state for edge, state in evaluated if not edge.optional]
    effective = required if required else [state for _, state in evaluated]
    successes = sum(s == "satisfied" for s in effective)
    pending = sum(s == "pending" for s in effective)
    if node.join == "ALL":
        if pending: return "waiting"
        return "ready" if successes == len(effective) and successes else "skipped"
    if node.join == "ALL_SETTLED":
        return "waiting" if pending else ("ready" if successes else "skipped")
    required_successes = 1 if node.join == "ANY" else node.quorum
    if successes >= required_successes:
        return "ready"
    if successes + pending < required_successes:
        return "skipped"
    return "waiting"


def _call(node: FlowNode, incoming: list[FlowEdge], outcomes: dict[str, dict],
          mode: str) -> dict:
    args = _node_inputs(node, incoming, outcomes)
    if node.operation_id == "control.identity":
        return {"status": "completed", "result": args}
    if node.operation_id == "control.join":
        return {"status": "completed", "result": {"received": args,
                "parents": [e.source for e in incoming if e.source in outcomes]}}
    if node.operation_id == "control.approval":
        raise ValueError("manual approval node cannot be auto-executed")
    state, reason = _operation_status(node.operation_id)
    if state != "ready":
        raise PermissionError(f"{node.operation_id}: {reason}")
    if mode != "research":
        return {"status": "dry_run", "result": {"operation": node.operation_id,
                "inputs": _scrub(args), "executed": False}}
    return _invoke(node.operation_id, ExecuteRequest(arguments=args, background=False))


def _invoke_with_retry(node: FlowNode, incoming: list[FlowEdge], outcomes: dict,
                       mode: str) -> tuple[dict, int]:
    # Retries only allowed for the curated read-only calculation operations.
    for attempt in range(node.max_retries + 1):
        try:
            return _call(node, incoming, outcomes, mode), attempt + 1
        except Exception:
            if attempt >= node.max_retries or node.operation_id.startswith("control."):
                raise
            time.sleep(min(0.15 * (2 ** attempt), 0.5))
    raise RuntimeError("unreachable")


def _execute(run_id: str) -> None:
    with _FN_LOCK:
        if run_id in _ACTIVE:
            return
        _ACTIVE.add(run_id)
    try:
        with _db() as db:
            row = db.execute("SELECT * FROM investment_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise _not_found("run")
            definition = FlowDefinition.model_validate_json(row["snapshot_json"])
            mode = row["mode"]
            old = db.execute("SELECT * FROM investment_node_runs WHERE run_id=?", (run_id,)).fetchall()
        indexed = {node.id: node for node in definition.nodes}
        state = {r["node_id"]: r["state"] for r in old}
        outcomes: dict[str, dict] = {}
        for r in old:
            if r["state"] in ("success", "failed", "skipped"):
                outcomes[r["node_id"]] = {
                    "state": r["state"], "result": json.loads(r["output_json"]) if r["output_json"] else None,
                    "error": json.loads(r["error_json"]) if r["error_json"] else None,
                }
        if mode == "research":
            forbidden = [(n.id, _operation_status(n.operation_id)) for n in definition.nodes
                         if _operation_status(n.operation_id)[0] != "ready"]
            if forbidden:
                _update_run(run_id, "blocked", {"restricted": forbidden})
                return
        _update_run(run_id, "running")
        incoming = {n.id: [e for e in definition.edges if e.target == n.id] for n in definition.nodes}
        workers = min(6, max(1, int(os.getenv("INVESTMENT_FLOW_PARALLELISM", "3"))))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="investment-node") as pool:
            pending: dict[Any, tuple[str, dict]] = {}
            while True:
                launched = False
                for node in definition.nodes:
                    if state[node.id] != "waiting" or len(pending) >= workers:
                        continue
                    decision = _decision(node, incoming[node.id], outcomes, set(state))
                    if decision == "skipped":
                        state[node.id] = "skipped"
                        outcomes[node.id] = {"state": "skipped", "result": None}
                        _update_node(run_id, node.id, "skipped",
                                     error={"reason": "join rule not satisfied"})
                        launched = True
                    elif decision == "ready":
                        if node.operation_id == "control.approval":
                            state[node.id] = "waiting_approval"
                            _update_node(run_id, node.id, "waiting_approval",
                                         inputs=_node_inputs(node, incoming[node.id], outcomes))
                            launched = True
                            continue
                        args = _node_inputs(node, incoming[node.id], outcomes)
                        _update_node(run_id, node.id, "running", inputs=args)
                        snapshot = dict(outcomes)
                        future = pool.submit(_invoke_with_retry, node, incoming[node.id], snapshot, mode)
                        pending[future] = (node.id, args)
                        state[node.id] = "running"
                        launched = True
                if pending:
                    done, _ = wait(tuple(pending), timeout=0.5, return_when=FIRST_COMPLETED)
                    for future in done:
                        node_id, _ = pending.pop(future)
                        try:
                            value, attempts = future.result()
                            state[node_id] = "success"
                            # Native return shape: {"status": "completed", "result": ...}
                            outcomes[node_id] = {"state": "success", "result": value.get("result")}
                            _update_node(run_id, node_id, "success", attempts=attempts,
                                         output=outcomes[node_id])
                        except Exception as exc:
                            state[node_id] = "failed"
                            error = {"type": type(exc).__name__, "message": str(exc)[:300]}
                            outcomes[node_id] = {"state": "failed", "error": error}
                            _update_node(run_id, node_id, "failed", attempts=indexed[node_id].max_retries+1,
                                         error=error)
                if not pending and not launched:
                    break
        if any(v == "waiting_approval" for v in state.values()):
            _update_run(run_id, "waiting_approval")
        elif any(v == "waiting" for v in state.values()):
            _update_run(run_id, "failed", {"error": "unsatisfied dependency or deadlock"})
        elif any(v == "failed" and not indexed[k].optional for k,v in state.items()):
            _update_run(run_id, "partial_failure")
        elif any(v == "skipped" for v in state.values()):
            _update_run(run_id, "partial")
        else:
            _update_run(run_id, "completed")
    except Exception as exc:
        _update_run(run_id, "failed", {"type": type(exc).__name__, "message": str(exc)[:300]})
    finally:
        with _FN_LOCK:
            _ACTIVE.discard(run_id)


def start_run(workflow_id: str, request: ExecuteFlow) -> dict:
    wf = get_workflow(workflow_id, request.version)
    defn = FlowDefinition.model_validate(wf["definition"])
    plan = validate(defn)
    if request.mode == "research" and plan["warnings"]:
        raise HTTPException(status_code=403, detail={"execution_unavailable": plan["warnings"]})
    run_id = uuid.uuid4().hex
    sha = _hash(defn)
    with _FN_LOCK, _db() as db:
        if request.idempotency_key:
            previous = db.execute(
                "SELECT id FROM investment_runs WHERE workflow_id=? AND version=? AND idempotency_key=?",
                (workflow_id, wf["version"], request.idempotency_key)).fetchone()
            if previous:
                return get_run(previous["id"])
        now = _now()
        db.execute("INSERT INTO investment_runs VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (run_id, workflow_id, wf["version"], request.mode,
                    _json(defn.model_dump(mode="json")), sha, "queued",
                    request.idempotency_key, now, now, None))
        db.executemany("INSERT INTO investment_node_runs(run_id,node_id,operation_id,state) VALUES(?,?,?,'waiting')",
                       [(run_id, n.id, n.operation_id) for n in defn.nodes])
        _event(db, run_id, None, "workflow_created",
               {"version": wf["version"], "mode": request.mode, "sha256": sha})
    if request.background:
        _BACKGROUND.submit(_execute, run_id)
        return {"run_id": run_id, "state": "queued", "poll": f"/api/v1/alpha/investment/runs/{run_id}"}
    _execute(run_id)
    return get_run(run_id)


def approve(run_id: str, node_id: str, approver: str, note: str) -> dict:
    if not approver.strip():
        raise HTTPException(status_code=422, detail="approver is required")
    with _FN_LOCK, _db() as db:
        row = db.execute("SELECT * FROM investment_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise _not_found("run")
        if row["state"] != "waiting_approval":
            raise HTTPException(status_code=409, detail="run is not awaiting approval")
        definition = FlowDefinition.model_validate_json(row["snapshot_json"])
        node = next((n for n in definition.nodes if n.id == node_id), None)
        if node is None or node.operation_id != "control.approval":
            raise HTTPException(status_code=422, detail="not an approval node")
        step = db.execute("SELECT state FROM investment_node_runs WHERE run_id=? AND node_id=?",
                          (run_id, node_id)).fetchone()
        if not step or step["state"] != "waiting_approval":
            raise HTTPException(status_code=409, detail="approval node not waiting")
        output = {"state": "success", "result": {"approved": True,
                  "approver": approver.strip(), "note": note[:500], "at": _now()}}
        db.execute("UPDATE investment_node_runs SET state='success',output_json=?,updated_at=? WHERE run_id=? AND node_id=?",
                   (_json(output), _now(), run_id, node_id))
        _event(db, run_id, node_id, "manual_approval", output)
    # Approval never enables blocked native live/trading operations.
    _execute(run_id)
    return get_run(run_id)


def events(run_id: str) -> dict:
    record = get_run(run_id)
    return {"run_id": run_id, "count": len(record["events"]), "events": record["events"]}
